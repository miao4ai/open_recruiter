"""Reading and writing datasets. JSON Lines, one example per line."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from recruitgpt.schemas import RankingExample


def write_jsonl(examples: list[RankingExample], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(ex.model_dump_json() + "\n")
    return path


def read_jsonl(path: str | Path) -> list[RankingExample]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No dataset at {path}")
    with path.open(encoding="utf-8") as fh:
        return [RankingExample.model_validate_json(line) for line in fh if line.strip()]


def fingerprint(path: str | Path) -> str:
    """A content hash, recorded with every run.

    "Which dataset was this trained on" has to be answerable from the run
    directory alone, months later, without trusting a filename.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def manifest(paths: dict[str, str | Path]) -> dict:
    """What went into a run, by name, size, and hash."""
    out = {}
    for name, path in paths.items():
        p = Path(path)
        if not p.is_file():
            continue
        out[name] = {
            "path": str(p),
            "examples": sum(1 for line in p.open(encoding="utf-8") if line.strip()),
            "bytes": p.stat().st_size,
            "sha256": fingerprint(p),
        }
    return out


__all__ = ["fingerprint", "manifest", "read_jsonl", "write_jsonl"]
