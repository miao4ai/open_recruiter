# recruitgpt-research

Two-stage candidate ranking research behind `recruitgpt`: a domain-specialised recruiting
model built by adapting Qwen3-8B with QLoRA, the generation pipeline that feeds it, and the
benchmark that tests whether specialisation beats a good prompt.

**[PLAN.md](PLAN.md) is the specification** — phases, verification criteria, data sourcing,
and the decisions that differ from the original proposal and why.

Nothing is implemented yet. Phase 0 builds a pipeline that runs end to end on CPU with no API
key, so the shape can be checked before anything is generated or trained.

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
