"""Configuration, with attention to the settings that fail quietly.

Multi-GPU QLoRA has a handful of knobs that do not announce themselves when
wrong: the run starts, trains, and produces something — just not what was
intended, or it dies hours later somewhere unrelated. Each of those is a guard
in `Config.validate`, and each guard is tested here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from recruitgpt_research.config import Config, Strategy, TrainConfig
from recruitgpt_research.train import sft

CONFIGS = Path(__file__).resolve().parent.parent / "configs"
ACCELERATE = Path(__file__).resolve().parent.parent / "accelerate"


# ── the enum ─────────────────────────────────────────────────────────────


def test_a_strategy_from_yaml_becomes_an_enum():
    """Left as a string, every `is Strategy.FSDP` below is False and the guards
    in this file never fire — the exact failure this test exists to prevent."""
    cfg = Config.from_dict({"distributed": {"strategy": "ddp"}})
    assert cfg.distributed.strategy is Strategy.DDP


def test_an_unknown_strategy_is_rejected_by_name():
    with pytest.raises(ValueError, match="Unknown distributed strategy"):
        Config.from_dict({"distributed": {"strategy": "horovod"}})


def test_a_typo_in_a_section_is_rejected():
    """A silently ignored key is a silently different experiment."""
    with pytest.raises(ValueError, match="Unknown key"):
        Config.from_dict({"train": {"learnign_rate": 1e-4}})
    with pytest.raises(ValueError, match="Unknown config section"):
        Config.from_dict({"trian": {}})


# ── the guards ───────────────────────────────────────────────────────────


def test_fsdp_rejects_a_mismatched_quant_storage():
    """bitsandbytes stores 4-bit weights as uint8 by default; FSDP cannot flatten
    a parameter whose storage dtype differs, and says so with a shape error deep
    in the flat-parameter code that mentions nothing about quantisation."""
    with pytest.raises(ValueError, match="bnb_4bit_quant_storage"):
        Config.from_dict({
            "distributed": {"strategy": "fsdp"},
            "model": {"bnb_4bit_quant_storage": "uint8", "bnb_4bit_compute_dtype": "bfloat16"},
        })


def test_fsdp_accepts_matching_dtypes():
    cfg = Config.from_dict({
        "distributed": {"strategy": "fsdp"},
        "model": {"bnb_4bit_quant_storage": "bfloat16", "bnb_4bit_compute_dtype": "bfloat16"},
    })
    assert cfg.distributed.strategy is Strategy.FSDP


@pytest.mark.parametrize("strategy", ["ddp", "fsdp"])
def test_reentrant_checkpointing_is_rejected_under_distribution(strategy):
    """Reentrant checkpointing and DDP disagree about which parameters were
    used, and the run dies at the first backward pass."""
    with pytest.raises(ValueError, match="reentrant"):
        Config.from_dict({
            "distributed": {"strategy": strategy},
            "train": {
                "gradient_checkpointing": True,
                "gradient_checkpointing_use_reentrant": True,
            },
        })


def test_reentrant_checkpointing_is_fine_on_one_process():
    Config.from_dict({
        "distributed": {"strategy": "single"},
        "train": {"gradient_checkpointing_use_reentrant": True},
    })


def test_listwise_needs_something_to_compare():
    with pytest.raises(ValueError, match="at least two candidates"):
        Config.from_dict({"data": {"max_candidates": 1}})


# ── batch arithmetic ─────────────────────────────────────────────────────


def test_the_effective_batch_scales_with_the_process_count():
    """Doubling the GPUs doubles the effective batch unless the accumulation
    steps come down. A run that silently changed its batch size is not
    comparable to the one before it."""
    cfg = Config.from_dict({"train": {"batch_size": 2, "gradient_accumulation_steps": 4}})
    assert cfg.distributed.effective_batch_size(cfg.train, 1) == 8
    assert cfg.distributed.effective_batch_size(cfg.train, 4) == 32


def test_the_shipped_single_and_multi_configs_agree_on_effective_batch():
    """The multi-GPU config exists to reproduce the single-GPU experiment on
    more hardware, not to run a different one."""
    single = Config.load(CONFIGS / "qwen3_8b_qlora.yaml")
    multi = Config.load(CONFIGS / "qwen3_8b_multi.yaml")

    assert single.distributed.effective_batch_size(single.train, 1) == 16
    assert multi.distributed.effective_batch_size(multi.train, 4) == 16, (
        "the multi-GPU config is written for four processes"
    )


# ── the shipped configs ──────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["debug", "qwen3_8b_qlora", "qwen3_8b_multi"])
def test_every_shipped_config_loads(name):
    Config.load(CONFIGS / f"{name}.yaml")


def test_the_debug_config_asks_for_nothing_a_laptop_lacks():
    """Phase 0's promise: the pipeline runs on CPU with no API key."""
    cfg = Config.load(CONFIGS / "debug.yaml")

    assert cfg.model.load_in_4bit is False, "bitsandbytes needs a GPU"
    assert cfg.train.optim == "adamw_torch", "the paged optimiser is CUDA-only"
    assert cfg.train.bf16 is False
    assert cfg.distributed.strategy is Strategy.SINGLE


def test_the_ddp_config_leaves_the_process_count_on_the_command_line():
    """It belongs in the shell history next to the run it produced."""
    raw = yaml.safe_load((ACCELERATE / "ddp.yaml").read_text())
    assert raw["distributed_type"] == "MULTI_GPU"
    assert raw["num_processes"] == 1
    assert raw["mixed_precision"] == "bf16"


def test_the_fsdp_config_carries_the_settings_peft_needs():
    raw = yaml.safe_load((ACCELERATE / "fsdp.yaml").read_text())["fsdp_config"]

    assert raw["fsdp_use_orig_params"] is True, "PEFT wraps the base model"
    assert raw["fsdp_auto_wrap_policy"] == "TRANSFORMER_BASED_WRAP"
    assert raw["fsdp_transformer_layer_cls_to_wrap"], (
        "without a layer class FSDP shards nothing and behaves like slow DDP"
    )


# ── launch plumbing ──────────────────────────────────────────────────────


def test_world_size_reads_the_launcher(monkeypatch):
    monkeypatch.delenv("WORLD_SIZE", raising=False)
    assert sft.world_size() == 1
    monkeypatch.setenv("WORLD_SIZE", "8")
    assert sft.world_size() == 8


def test_only_rank_zero_writes(monkeypatch):
    """Eight processes writing the same run directory is eight ways to lose it."""
    monkeypatch.setenv("RANK", "0")
    assert sft.is_main_process()
    monkeypatch.setenv("RANK", "3")
    assert not sft.is_main_process()


def test_a_dry_run_reports_the_plan_without_loading_a_model(capsys):
    """The cheapest way to catch a wrong effective batch size is before the
    weights download."""
    assert sft.main(["--config", str(CONFIGS / "qwen3_8b_multi.yaml"), "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "Qwen/Qwen3-8B" in out
    assert "strategy          ddp" in out
    assert "effective batch" in out


def test_ddp_training_arguments_disable_the_unused_parameter_search(monkeypatch):
    """With an adapter nearly everything is frozen, so the default search costs
    time on every step and finds the same answer."""
    pytest.importorskip("transformers")
    cfg = Config.load(CONFIGS / "qwen3_8b_multi.yaml")
    args = sft.training_arguments(cfg, "/tmp/out")

    assert args.ddp_find_unused_parameters is False
    assert args.gradient_checkpointing_kwargs == {"use_reentrant": False}


def test_a_distributed_strategy_with_one_process_is_flagged(tmp_path, monkeypatch):
    """Forgetting `accelerate launch` runs a 'multi-GPU' config on one GPU and
    looks completely normal in the logs."""
    from recruitgpt_research.runs import Run

    cfg = Config.load(CONFIGS / "qwen3_8b_multi.yaml")
    monkeypatch.setattr(cfg.run, "output_dir", str(tmp_path))
    info_path = Run(cfg, root=tmp_path).record_environment(world_size=1)

    import json

    assert "warning" in json.loads(info_path.read_text())
