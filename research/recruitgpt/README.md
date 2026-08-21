# recruitgpt-research

Two-stage candidate ranking research behind `recruitgpt`: LLM-as-a-judge soft labels,
hard-negative mining, knowledge distillation into a compact ranker, and ranking evaluation.

Specification pending.

**Status: scaffold.** No implementation yet — see the repo root [README](../../README.md) for where this sits in the plan.

## Install

```bash
pip install recruitgpt-research
```

## Build from source

```bash
cd research/recruitgpt
uv build --out-dir dist   # -> dist/*.whl, dist/*.tar.gz
```
