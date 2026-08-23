"""Supervised fine-tuning: QLoRA on a chat model, on one GPU or several.

Run it directly for a single process:

    python -m recruitgpt_research.train.sft --config configs/qwen3_8b_qlora.yaml

or under accelerate for more than one GPU:

    accelerate launch --config_file accelerate/ddp.yaml \\
        -m recruitgpt_research.train.sft --config configs/qwen3_8b_multi.yaml

DDP is the default for an 8B adapter: a 4-bit base is roughly 5 GB, so a full
copy fits on each GPU and there is nothing to shard. FSDP exists for when that
stops being true, and its awkward interactions with 4-bit quantisation are
handled in `Config.validate` rather than discovered at runtime.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from recruitgpt_research.config import Config, Strategy

log = logging.getLogger("recruitgpt.train")


def world_size() -> int:
    """How many processes are in this run, per the launcher."""
    return int(os.environ.get("WORLD_SIZE", "1"))


def is_main_process() -> bool:
    return int(os.environ.get("RANK", "0")) == 0


def _dtype(name: str):
    import torch

    return {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[name]


def load_model_and_tokenizer(config: Config):
    """The quantised base with an adapter attached."""
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(
        config.model.base,
        revision=config.model.revision,
        trust_remote_code=config.model.trust_remote_code,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    kwargs = {
        "revision": config.model.revision,
        "trust_remote_code": config.model.trust_remote_code,
        "attn_implementation": config.model.attn_implementation,
        "torch_dtype": _dtype(config.model.bnb_4bit_compute_dtype),
    }

    if config.model.load_in_4bit:
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=config.model.bnb_4bit_quant_type,
            bnb_4bit_compute_dtype=_dtype(config.model.bnb_4bit_compute_dtype),
            bnb_4bit_use_double_quant=True,
            # Matching the compute dtype is what lets FSDP flatten these.
            bnb_4bit_quant_storage=_dtype(config.model.bnb_4bit_quant_storage),
        )

    if config.distributed.strategy is Strategy.SINGLE:
        # Let accelerate place the model when it is driving; otherwise pin it,
        # because `device_map="auto"` and DDP both want to own placement and the
        # result is a model split across GPUs that DDP then tries to replicate.
        kwargs["device_map"] = {"": 0} if torch.cuda.is_available() else None

    model = AutoModelForCausalLM.from_pretrained(config.model.base, **kwargs)

    if config.model.load_in_4bit:
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=config.train.gradient_checkpointing
        )

    model = get_peft_model(
        model,
        LoraConfig(
            r=config.lora.r,
            lora_alpha=config.lora.alpha,
            lora_dropout=config.lora.dropout,
            target_modules=config.lora.target_modules,
            bias=config.lora.bias,
            task_type=config.lora.task_type,
        ),
    )
    model.config.use_cache = False  # incompatible with gradient checkpointing
    return model, tokenizer


def build_dataset(config: Config, tokenizer, path: str | Path):
    """Load, filter, render, tokenise."""
    from recruitgpt_research.data.chat import keep_quality, to_chat
    from recruitgpt_research.data.io import read_jsonl
    from recruitgpt_research.train.collate import encode

    examples = keep_quality(read_jsonl(path), config.data.min_quality)
    if config.train.max_examples > 0:
        examples = examples[: config.train.max_examples]
    if not examples:
        raise ValueError(f"No examples in {path} at quality >= {config.data.min_quality}")

    rows = []
    for ex in examples:
        chat = to_chat(
            ex,
            shuffle_candidates=config.data.shuffle_candidates,
            seed=config.data.seed,
            max_candidates=config.data.max_candidates,
        )
        rows.append(encode(tokenizer, chat.messages, config.data.max_seq_len))
    return rows


def training_arguments(config: Config, output_dir: str | Path):
    """Map our config onto the trainer's, including the distributed knobs."""
    from transformers import TrainingArguments

    args = {
        "output_dir": str(output_dir),
        "num_train_epochs": config.train.epochs,
        "max_steps": config.train.max_steps,
        "learning_rate": config.train.learning_rate,
        "per_device_train_batch_size": config.train.batch_size,
        "gradient_accumulation_steps": config.train.gradient_accumulation_steps,
        "warmup_ratio": config.train.warmup_ratio,
        "weight_decay": config.train.weight_decay,
        "lr_scheduler_type": config.train.lr_scheduler_type,
        "max_grad_norm": config.train.max_grad_norm,
        "gradient_checkpointing": config.train.gradient_checkpointing,
        "gradient_checkpointing_kwargs": {
            "use_reentrant": config.train.gradient_checkpointing_use_reentrant
        },
        "optim": config.train.optim,
        "bf16": config.train.bf16,
        "seed": config.train.seed,
        "logging_steps": config.train.logging_steps,
        "save_steps": config.train.save_steps,
        "save_total_limit": 2,
        "report_to": [],
        "remove_unused_columns": False,
    }

    if config.distributed.strategy is Strategy.DDP:
        # An adapter freezes nearly everything, so the default search for unused
        # parameters costs time on every step and finds the same answer.
        args["ddp_find_unused_parameters"] = config.distributed.ddp_find_unused_parameters
        args["ddp_timeout"] = config.distributed.ddp_timeout_seconds
    elif config.distributed.strategy is Strategy.FSDP:
        args["fsdp"] = "full_shard auto_wrap"
        args["fsdp_config"] = {
            "fsdp_transformer_layer_cls_to_wrap": [config.distributed.fsdp_transformer_layer_cls],
            # PEFT wraps the base model; FSDP has to see the real parameters.
            "fsdp_use_orig_params": config.distributed.fsdp_use_orig_params,
            "fsdp_offload_params": config.distributed.fsdp_offload_params,
        }

    return TrainingArguments(**args)


def train(config: Config) -> Path:
    """Run one training job. Returns the run directory."""
    from transformers import Trainer

    from recruitgpt_research.data.io import manifest
    from recruitgpt_research.runs import Run
    from recruitgpt_research.train.collate import Collator

    size = world_size()
    run = Run(config)
    if is_main_process():
        run.record_config()
        run.record_environment(world_size=size)
        run.record_dataset(
            manifest({"train": config.data.train_path, "validation": config.data.eval_path})
        )
        log.info(
            "run=%s strategy=%s world_size=%d effective_batch=%d",
            run.dir.name,
            config.distributed.strategy.value,
            size,
            config.distributed.effective_batch_size(config.train, size),
        )

    model, tokenizer = load_model_and_tokenizer(config)
    train_rows = build_dataset(config, tokenizer, config.data.train_path)

    trainer = Trainer(
        model=model,
        args=training_arguments(config, run.dir / "checkpoints"),
        train_dataset=train_rows,
        data_collator=Collator(pad_token_id=tokenizer.pad_token_id),
    )
    result = trainer.train()

    if is_main_process():
        adapter = run.dir / "adapter"
        model.save_pretrained(adapter)
        tokenizer.save_pretrained(adapter)
        run.record_metrics({"train": result.metrics, "world_size": size})
        log.info("adapter written to %s", adapter)

    return run.dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fine-tune RecruitGPT with QLoRA.")
    parser.add_argument("--config", required=True, help="Path to a YAML run config")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the config and report the plan without loading a model.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = Config.load(args.config)
    size = world_size()

    print(f"base model        {config.model.base}@{config.model.revision}")
    print(f"strategy          {config.distributed.strategy.value}")
    print(f"world size        {size}")
    print(f"per-device batch  {config.train.batch_size}")
    print(f"grad accumulation {config.train.gradient_accumulation_steps}")
    print(f"effective batch   {config.distributed.effective_batch_size(config.train, size)}")
    print(f"LoRA              r={config.lora.r} alpha={config.lora.alpha}")
    print(f"sequence length   {config.data.max_seq_len}")

    if args.dry_run:
        print("\ndry run: config is valid, nothing loaded")
        return 0

    train(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
