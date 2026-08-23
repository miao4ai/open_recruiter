"""One directory per run, holding everything needed to explain it later.

Checkpoints are not among those things. Weights go to a model registry; what
stays here is the configuration, the dataset fingerprint, the environment, and
the results — small enough to commit, complete enough to reproduce.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from recruitgpt_research.config import Config


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False
        )
        commit = out.stdout.strip()
    except Exception:
        return "unknown"
    if not commit:
        return "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5, check=False
    ).stdout.strip()
    # A dirty tree means the commit does not describe what actually ran.
    return f"{commit[:12]}{'-dirty' if dirty else ''}"


def _accelerator() -> dict[str, Any]:
    """What the run is executing on. Absent torch, say so rather than guess."""
    try:
        import torch
    except ImportError:
        return {"available": False, "reason": "torch is not installed"}

    if not torch.cuda.is_available():
        return {"available": False, "backend": "cpu", "torch": torch.__version__}
    return {
        "available": True,
        "backend": "cuda",
        "torch": torch.__version__,
        "device_count": torch.cuda.device_count(),
        "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        "capability": list(torch.cuda.get_device_capability(0)),
    }


class Run:
    """A run directory: config, manifest, environment, metrics."""

    def __init__(self, config: Config, root: str | Path | None = None) -> None:
        self.config = config
        base = Path(root or config.run.output_dir)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.dir = base / f"{config.run.name}-{stamp}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.started = datetime.now(timezone.utc)

    def record_config(self) -> Path:
        return self._write("config.json", self.config.to_dict())

    def record_dataset(self, manifest: dict) -> Path:
        return self._write("dataset_manifest.json", manifest)

    def record_environment(self, world_size: int = 1) -> Path:
        from recruitgpt_research.config import Strategy

        info = {
            "git_commit": _git_commit(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "started_utc": self.started.isoformat(),
            "accelerator": _accelerator(),
            "world_size": world_size,
            "strategy": self.config.distributed.strategy.value,
            "effective_batch_size": self.config.distributed.effective_batch_size(
                self.config.train, world_size
            ),
            "base_model": self.config.model.base,
            "base_model_revision": self.config.model.revision,
        }
        if self.config.distributed.strategy is not Strategy.SINGLE and world_size == 1:
            info["warning"] = (
                "A distributed strategy is configured but only one process is running — "
                "the launcher probably was not used."
            )
        return self._write("run_info.json", info)

    def record_metrics(self, metrics: dict) -> Path:
        return self._write("metrics.json", metrics)

    def record_predictions(self, rows: list[dict]) -> Path:
        path = self.dir / "predictions.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return path

    def record_errors(self, rows: list[dict]) -> Path:
        """The examples the model got wrong. Phase 4 mines hard negatives here."""
        path = self.dir / "error_analysis.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return path

    def _write(self, name: str, payload: dict) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return path


__all__ = ["Run"]
