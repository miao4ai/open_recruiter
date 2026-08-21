#!/usr/bin/env python3
"""Enforce the repository's dependency boundaries.

    product  ->  sdk          allowed
    research ->  sdk          allowed
    product  ->  research     FORBIDDEN

Production code must never import training or experimental research code, and a
normal install must never pull a training stack. Run it locally the same way CI
does:

    python .github/scripts/check_architecture.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Distribution names that mean "this is a training stack", not "this is an app".
HEAVY = {
    "torch", "torchvision", "torchaudio",
    "transformers", "sentence-transformers", "datasets",
    "accelerate", "deepspeed", "peft", "bitsandbytes",
    "onnxruntime", "onnxruntime-gpu", "optimum",
    "scipy", "scikit-learn", "faster-whisper",
}

# Top-level module names owned by the research layer.
RESEARCH_MODULES = {
    p.name
    for d in (ROOT / "research").glob("*/")
    for p in d.iterdir()
    if p.is_dir() and (p / "__init__.py").is_file()
}

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(?P<from>[\w.]+)|import\s+(?P<import>[\w.]+))", re.MULTILINE
)


def _dist_name(spec: str) -> str:
    """'torch>=2.0' -> 'torch'"""
    return re.split(r"[<>=!~\[; ]", spec.strip(), maxsplit=1)[0].lower()


def check_product_does_not_import_research() -> list[str]:
    if not RESEARCH_MODULES:
        return []
    errors = []
    for py in (ROOT / "product").rglob("*.py"):
        for m in _IMPORT_RE.finditer(py.read_text(encoding="utf-8", errors="ignore")):
            mod = (m.group("from") or m.group("import")).split(".")[0]
            if mod in RESEARCH_MODULES:
                rel = py.relative_to(ROOT)
                errors.append(f"{rel}: imports research module '{mod}'")
    return errors


def check_no_training_deps() -> list[str]:
    """The product and the core SDK must install without a training stack.

    Research packages and the optional Ranker backends may depend on whatever
    they need — that is what optional extras and separate distributions are for.
    """
    errors = []
    for rel in ("product/backend/pyproject.toml", "sdk/core/pyproject.toml"):
        path = ROOT / rel
        if not path.is_file():
            continue
        data = tomllib.loads(path.read_text())
        for spec in data.get("project", {}).get("dependencies", []):
            name = _dist_name(spec)
            if name in HEAVY:
                errors.append(
                    f"{rel}: '{name}' is a required dependency — "
                    f"move it to [project.optional-dependencies]"
                )
    return errors


def main() -> int:
    checks = [
        ("product/ does not import research/", check_product_does_not_import_research),
        ("no training deps in the default install", check_no_training_deps),
    ]
    failed = False
    for label, fn in checks:
        errors = fn()
        if errors:
            failed = True
            print(f"FAIL  {label}")
            for e in errors:
                print(f"        {e}")
        else:
            print(f"ok    {label}")
    if failed:
        print("\nSee the architecture section of CONTRIBUTING.md.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
