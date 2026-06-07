# Testing — Pytest Harness

## Run

```bash
cd backend && uv run python -m pytest ../tests/harness/ -v
```

All tests are pure unit tests with mocked LLM/IMAP/Whisper calls — no network, runs in <1s.

## What's covered

| File | Cases | Coverage |
|------|-------|----------|
| `test_intent_detection.py` | ~40 | Keyword fallback (resume / JD upload, match_job, inbox), seeker vs recruiter whitelist, intent disambiguation |
| `test_guardrails.py` | ~70 | Prompt injection (13 attack patterns), PII detection, content safety, hallucination, action limits, severity priority |
| `test_transcribe.py` | 22 | Voice input: Whisper transcription, language detection, error paths (mocked) |
| `test_memory.py` | 22 | 4-tier memory: sensory ring buffer, working state, entity rolling summary, 4-layer loader |

Total: 159+ test cases.

## Run subsets

```bash
# Single file
uv run python -m pytest ../tests/harness/test_guardrails.py -v

# Single class
uv run python -m pytest ../tests/harness/test_guardrails.py::TestInputInjection -v

# Single case
uv run python -m pytest ../tests/harness/test_guardrails.py::TestInputInjection::test_injection_blocked -v
```

## Adding tests

Use `@pytest.mark.parametrize("msg", [...])` for batch phrasings. Example:

```python
@pytest.mark.parametrize("msg", [
    "check my inbox",
    "查看收件箱",
    "fetch my recent emails",
])
def test_inbox_check_detected(self, msg: str):
    result = _detect_action_from_keywords(msg)
    assert result is not None
    assert result["type"] == "check_inbox"
```

## When a test fails

Three possibilities — **never** modify a test just to make it pass:

1. **Real regression** — code change broke behavior. Fix the code.
2. **Coverage gap** — the LLM/regex doesn't yet cover a phrasing. Fix the prompt or regex (the test discovered a real gap — keep it).
3. **Stale fixture** — test data references a format that changed. Fix the test.

## Frontend type check

```bash
cd frontend && npx tsc --noEmit
```

Required after every change to `types/index.ts` or any component.
