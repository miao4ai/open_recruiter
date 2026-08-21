# openrecruiter

The agent toolkit behind Open Recruiter: recruiting tools (parse, match, draft, schedule), an agent loop over them, and the SQLite + vector stores they read. The desktop app is a consumer of this package.

**Status: scaffold.** No implementation yet — see the repo root [README](../../README.md) for where this sits in the plan.

## Install

```bash
pip install openrecruiter
```

## Build from source

```bash
cd sdk/core
uv build --out-dir dist   # -> dist/*.whl, dist/*.tar.gz
```
