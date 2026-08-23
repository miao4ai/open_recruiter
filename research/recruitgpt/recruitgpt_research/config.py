"""Run configuration, loaded from YAML.

One object holds everything a run needs and everything it has to record. The
defaults encode the settings that make QLoRA work across several GPUs — most of
them are not obvious, and getting them wrong fails quietly rather than loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


class Strategy(str, Enum):
    """How the run is spread over devices."""

    #: One process. Also what a CPU debug run uses.
    SINGLE = "single"
    #: A full model copy per GPU, gradients all-reduced. The right default for
    #: QLoRA on 8B: a 4-bit base is about 5 GB, so it fits many times over, and
    #: DDP avoids the sharding complexity entirely.
    DDP = "ddp"
    #: Parameters sharded across GPUs. Needed when a copy no longer fits —
    #: larger bases, or full fine-tuning rather than an adapter.
    FSDP = "fsdp"


@dataclass
class ModelConfig:
    base: str = "Qwen/Qwen3-8B"
    #: Pin the weights. "main" moves; a run that cannot be reproduced is not a result.
    revision: str = "main"
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_compute_dtype: str = "bfloat16"
    #: Must equal the compute dtype under FSDP. bitsandbytes stores 4-bit weights
    #: as uint8 by default, and FSDP cannot flatten a parameter whose storage
    #: dtype differs from the rest — the failure is an obscure shape error deep
    #: in the flat-parameter code, not a message about quantisation.
    bnb_4bit_quant_storage: str = "bfloat16"
    attn_implementation: str = "sdpa"
    trust_remote_code: bool = False


@dataclass
class LoraConfig_:
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    #: Attention and MLP projections. Naming follows Qwen/Llama; a different
    #: family needs a different list, which is why it is configuration.
    target_modules: list[str] = field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]
    )
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


@dataclass
class DataConfig:
    train_path: str = "data/train.jsonl"
    eval_path: str = "data/validation.jsonl"
    #: How many candidates go into one listwise example. Larger is a better
    #: signal and a longer sequence; this is the knob that trades them off.
    max_candidates: int = 8
    max_seq_len: int = 4096
    #: Drop examples whose label was not trustworthy.
    min_quality: str = "silver"
    shuffle_candidates: bool = True
    seed: int = 17


@dataclass
class TrainConfig:
    epochs: float = 2.0
    #: Stop after this many optimiser steps regardless of epochs. -1 disables.
    #: The debug config uses it to prove the loop runs in a minute rather than
    #: an hour — a smoke test nobody waits for is a smoke test nobody runs.
    max_steps: int = -1
    #: Cap the dataset. Also for the debug path; -1 uses everything.
    max_examples: int = -1
    learning_rate: float = 1e-4
    #: Per device. The effective batch is this * grad_accum * world_size, which
    #: is what has to stay constant when the GPU count changes.
    batch_size: int = 1
    gradient_accumulation_steps: int = 8
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    lr_scheduler_type: str = "cosine"
    max_grad_norm: float = 0.3
    gradient_checkpointing: bool = True
    #: The reentrant implementation and DDP disagree about which parameters were
    #: used, and the run dies at the first backward pass.
    gradient_checkpointing_use_reentrant: bool = False
    optim: str = "paged_adamw_8bit"
    bf16: bool = True
    seed: int = 42
    logging_steps: int = 10
    save_steps: int = 200
    eval_steps: int = 200


@dataclass
class DistributedConfig:
    strategy: Strategy = Strategy.SINGLE

    ddp_find_unused_parameters: bool = False
    ddp_timeout_seconds: int = 1800
    #: PEFT wraps the base model, so FSDP has to see the real parameters rather
    #: than the wrapper's views.
    fsdp_use_orig_params: bool = True
    fsdp_sharding_strategy: str = "FULL_SHARD"
    fsdp_transformer_layer_cls: str = "Qwen3DecoderLayer"
    fsdp_offload_params: bool = False

    def __post_init__(self) -> None:
        # YAML hands over a plain string. Left as one, every `is Strategy.FSDP`
        # below is silently False and the guards that exist to catch a broken
        # FSDP setup never fire — the run starts and dies much later, somewhere
        # unrelated.
        if not isinstance(self.strategy, Strategy):
            try:
                self.strategy = Strategy(str(self.strategy))
            except ValueError:
                raise ValueError(
                    f"Unknown distributed strategy {self.strategy!r}; "
                    f"expected one of {', '.join(s.value for s in Strategy)}"
                ) from None

    #: With an adapter, most parameters are frozen. Transformers otherwise
    #: assumes some may go unused and pays for a search on every step.
    def effective_batch_size(self, train: TrainConfig, world_size: int) -> int:
        """What the optimiser actually sees per step.

        Worth printing at startup: doubling the GPUs doubles this unless the
        accumulation steps come down, and a run that silently changed its batch
        size is not comparable to the one before it.
        """
        return train.batch_size * train.gradient_accumulation_steps * max(1, world_size)


@dataclass
class RunConfig:
    name: str = "recruitgpt-dev"
    output_dir: str = "runs"
    #: Where a trained adapter is pushed. Never into git.
    hub_repo: str = ""
    notes: str = ""


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    lora: LoraConfig_ = field(default_factory=LoraConfig_)
    data: DataConfig = field(default_factory=DataConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    distributed: DistributedConfig = field(default_factory=DistributedConfig)
    run: RunConfig = field(default_factory=RunConfig)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        import yaml

        raw = yaml.safe_load(Path(path).read_text()) or {}
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        unknown = set(raw) - {"model", "lora", "data", "train", "distributed", "run"}
        if unknown:
            # A typo in a config is a silently different experiment.
            raise ValueError(f"Unknown config section(s): {', '.join(sorted(unknown))}")

        sections = {
            "model": ModelConfig,
            "lora": LoraConfig_,
            "data": DataConfig,
            "train": TrainConfig,
            "distributed": DistributedConfig,
            "run": RunConfig,
        }
        built = {}
        for key, klass in sections.items():
            values = raw.get(key) or {}
            valid = {f for f in klass.__dataclass_fields__}
            bad = set(values) - valid
            if bad:
                raise ValueError(f"Unknown key(s) in '{key}': {', '.join(sorted(bad))}")
            built[key] = klass(**values)

        cfg = cls(**built)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.distributed.strategy is Strategy.FSDP:
            if self.model.bnb_4bit_quant_storage != self.model.bnb_4bit_compute_dtype:
                raise ValueError(
                    "FSDP needs bnb_4bit_quant_storage to match bnb_4bit_compute_dtype "
                    f"(got {self.model.bnb_4bit_quant_storage!r} and "
                    f"{self.model.bnb_4bit_compute_dtype!r}); otherwise FSDP cannot flatten "
                    "the quantised parameters and fails with a shape error far from the cause."
                )
        if self.train.gradient_checkpointing and self.distributed.strategy is not Strategy.SINGLE:
            if self.train.gradient_checkpointing_use_reentrant:
                raise ValueError(
                    "Reentrant gradient checkpointing does not work with DDP or FSDP — "
                    "set train.gradient_checkpointing_use_reentrant to false."
                )
        if self.data.max_candidates < 2:
            raise ValueError("Listwise ranking needs at least two candidates to compare.")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["distributed"]["strategy"] = self.distributed.strategy.value
        return d


__all__ = ["Config", "DataConfig", "DistributedConfig", "LoraConfig_", "ModelConfig",
           "RunConfig", "Strategy", "TrainConfig"]
