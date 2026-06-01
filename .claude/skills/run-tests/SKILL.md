---
name: run-tests
description: Run the Open Recruiter test harness (intent detection + guardrails + voice). Use when the user asks to run tests, verify behavior, check the harness, or before committing.
---

# Run the Test Harness

## Run all tests

```bash
cd backend && uv run python -m pytest ../tests/harness/ -v
```

Should print `XXX passed in <1s` (mocked; no real LLM/IMAP/Whisper calls).

## Run a single file

```bash
cd backend && uv run python -m pytest ../tests/harness/test_intent_detection.py -v
cd backend && uv run python -m pytest ../tests/harness/test_guardrails.py -v
```

## Run a single class or case

```bash
cd backend && uv run python -m pytest ../tests/harness/test_guardrails.py::TestInputInjection -v
cd backend && uv run python -m pytest ../tests/harness/test_guardrails.py::TestInputInjection::test_injection_blocked -v
```

## What's covered

| File | Coverage |
|------|----------|
| `test_intent_detection.py` | Keyword fallback (resume/JD upload, match_job, inbox), seeker vs recruiter whitelist, intent disambiguation |
| `test_guardrails.py` | Prompt injection (13 attack patterns), PII detection, content safety, hallucination, action limits, severity priority |

## When tests fail

A failing test is usually one of:
1. **Real regression** — a code change broke behavior. Fix the code.
2. **Intent gap** — the LLM/regex doesn't cover a phrasing yet. Fix the prompt or regex.
3. **Stale test data** — test fixture references a job ID / candidate name that doesn't match production format. Fix the test.

Never modify a test just to make it pass — first verify which category the failure falls into.

## Adding new tests

Use `@pytest.mark.parametrize("msg", [...])` for batch coverage of phrasings. See `TestKeywordFallback` for the pattern.
