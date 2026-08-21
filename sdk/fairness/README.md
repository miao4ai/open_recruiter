# openrecruiter-fairness

A fairness-aware `Ranker` implementation: bias evaluation, candidate anonymization,
counterfactual testing, and the relevance/fairness trade-off. Plugs into the `Ranker`
interface in `openrecruiter`, so the product can swap it in without any other change.

Specification pending.

**Status: scaffold.** No implementation yet — see the repo root [README](../../README.md) for where this sits in the plan.

## Install

```bash
pip install openrecruiter-fairness
```

## Build from source

```bash
cd sdk/fairness
uv build --out-dir dist   # -> dist/*.whl, dist/*.tar.gz
```
