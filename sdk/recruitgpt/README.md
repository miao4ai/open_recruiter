# recruitgpt

RecruitGPT — a compact distilled ranking model, packaged as a `LocalSLMRanker`
implementation of the `Ranker` interface in `openrecruiter`.

Heavyweight dependencies (torch, transformers) live behind optional extras and the model
is lazy-loaded, so installing `openrecruiter` never pulls them in.

Specification pending.

**Status: scaffold.** No implementation yet — see the repo root [README](../../README.md) for where this sits in the plan.

## Install

```bash
pip install recruitgpt
```

## Build from source

```bash
cd sdk/recruitgpt
uv build --out-dir dist   # -> dist/*.whl, dist/*.tar.gz
```
