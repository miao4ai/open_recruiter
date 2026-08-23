"""Every Python block in the README is executed.

Documentation that is never run stops being true. This repository has already
paid for that once: `agents/jd.py` was a syntax error through five releases
because nothing imported it eagerly, and the README claimed a test count that
had not been right for two versions.

So the blocks are extracted and run in order, in one namespace, the way a reader
goes through the page. Missing pieces — a mail client, a calendar, resume files
— are supplied by the fixture below rather than skipped, so the examples are
checked as written and not as an approximation of what was written.

A block that genuinely cannot run is marked in the README with an HTML comment:

    <!-- readme-test: skip -->
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"

_BLOCK = re.compile(
    r"(?P<skip><!--\s*readme-test:\s*skip\s*-->\s*)?```python\n(?P<code>.*?)```",
    re.DOTALL,
)


def _blocks() -> list[tuple[int, str]]:
    """(line number, source) for each runnable block, in document order."""
    text = README.read_text()
    out = []
    for m in _BLOCK.finditer(text):
        if m.group("skip"):
            continue
        out.append((text[: m.start()].count("\n") + 1, m.group("code")))
    return out


class _FakeLLM:
    """Answers each prompt with something shaped like the real thing.

    Dispatch is on each prompt's distinctive opening rather than a keyword,
    because several of them mention "job description".
    """

    def __init__(self, config):
        self.config = config
        self.turn = 0

    def complete_json(self, system, messages):
        if "resume analysis agent" in system:
            return {
                "name": "Ada Lovelace",
                "current_title": "ML Systems Engineer",
                "current_company": "Acme",
                "skills": ["CUDA", "NCCL"],
                "experience_years": 8,
                "resume_summary": "Scaled distributed training to 512 GPUs.",
            }
        if "Extract structured information" in system:
            return {
                "title": "Senior CUDA Engineer",
                "company": "Acme",
                "required_skills": ["CUDA", "NCCL", "PyTorch Distributed"],
                "experience_years": 8,
                "summary": "Scale distributed training across thousands of GPUs.",
            }
        if "recruiter writing to a candidate" in system:
            return {"subject": "CUDA work at Acme", "body": "Hi Ada, your NCCL work stood out."}
        if "matching agent" in system:
            return {
                "score": 0.91,
                "strengths": ["Has shipped NCCL at scale"],
                "gaps": ["No Triton"],
                "reasoning": "Direct match on the hard requirement.",
            }
        raise AssertionError(f"unrecognised prompt: {system[:80]!r}")

    def stream(self, system, messages, tools=None):
        from openrecruiter.events import TextDelta, ToolCall

        offered = {t["function"]["name"] for t in (tools or [])}
        answered = any(m.get("role") == "tool" for m in messages)

        if not answered:
            # The approval example is only meaningful if the model reaches for
            # the gated tool, so call it whenever the example registered one.
            if "send_email" in offered:
                yield ToolCall(id="c1", name="send_email", arguments={"to": "ada@example.com"})
                return
            if offered:
                yield ToolCall(id="c1", name="list_jobs", arguments={})
                return

        for word in "Ada Lovelace is the strongest fit.".split(" "):
            yield TextDelta(text=word + " ")


@pytest.fixture(scope="module")
def namespace(tmp_path_factory, module_mocker=None):
    """The world the README's examples assume they are running in."""
    import openrecruiter.client as sdk_client
    from openrecruiter import Config, NullVectorIndex, Recruiter, SQLiteStore, Tool

    original_llm = sdk_client.LLM
    sdk_client.LLM = _FakeLLM

    tmp = tmp_path_factory.mktemp("readme")
    for name in ("jd.txt", "ada.txt", "grace.txt", "alan.txt", "resume.txt"):
        (tmp / name).write_text("Ada Lovelace — ML systems engineer, CUDA and NCCL.")

    import os

    cwd = os.getcwd()
    os.chdir(tmp)

    config = Config(anthropic_api_key="test-key")
    r = Recruiter(config, data_dir=tmp)
    job = r.add_job("Senior CUDA Engineer at Acme.")
    r.add_candidate("Ada Lovelace, ML systems.")

    class _Mail:
        sent: list = []

        def send(self, to):
            self.sent.append(to)
            return {"sent": True, "to": to}

    class _Calendar:
        def free_slots(self, days=7):
            return [{"start": "2026-09-01T10:00", "end": "2026-09-01T11:00"}]

    ns = {
        "r": r,
        "config": config,
        "job": job,
        "mail": _Mail(),
        "calendar": _Calendar(),
        "my_store": SQLiteStore(tmp / "byo.db"),
        "my_index": NullVectorIndex(),
        "my_ranker": r.ranker,
        "my_tool": Tool(name="noop", description="does nothing", fn=lambda: None),
        # The approval example asks; answer it without a terminal.
        "input": lambda prompt="": "y",
        "print": lambda *a, **k: None,
    }
    yield ns

    os.chdir(cwd)
    sdk_client.LLM = original_llm


def test_the_readme_has_examples():
    assert len(_blocks()) >= 15, "the examples went missing"


@pytest.mark.parametrize(
    ("line", "code"), _blocks(), ids=[f"L{line}" for line, _ in _blocks()]
)
def test_readme_block_runs(line, code, namespace):
    """Run one block in the shared namespace, as a reader would reach it."""
    try:
        exec(compile(code, f"README.md:{line}", "exec"), namespace)
    except Exception as exc:  # pragma: no cover - only on failure
        pytest.fail(f"README.md line {line} raised {type(exc).__name__}: {exc}\n\n{code}")
