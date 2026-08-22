"""Fakes that let the whole SDK be tested without a network call."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from openrecruiter.config import Config
from openrecruiter.events import TextDelta, ToolCall
from openrecruiter.types import Candidate, Job


class FakeLLM:
    """A scripted stand-in for `LLM`.

    `script` is a list of turns. Each turn is either a string (the model just
    talks) or a list of `(tool_name, arguments)` pairs (the model calls tools).
    Turns are consumed in order, so a test can spell out an entire multi-step
    conversation and then assert on what the agent did with it.
    """

    def __init__(self, script: list | None = None, json_response: object = None) -> None:
        self.script = list(script or [])
        self.json_response = json_response
        self.calls: list[dict] = []
        self.config = Config(anthropic_api_key="test")

    def stream(self, system, messages, tools=None) -> Iterator[TextDelta | ToolCall]:
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        turn = self.script.pop(0) if self.script else "Done."
        if isinstance(turn, str):
            for word in turn.split(" "):
                yield TextDelta(text=word + " ")
            return
        for i, (name, args) in enumerate(turn):
            yield ToolCall(id=f"call_{len(self.calls)}_{i}", name=name, arguments=args)

    def complete(self, system, messages) -> str:
        self.calls.append({"system": system, "messages": list(messages)})
        return json.dumps(self.json_response) if self.json_response is not None else "ok"

    def complete_json(self, system, messages):
        self.calls.append({"system": system, "messages": list(messages)})
        if self.json_response is None:
            return {}
        if isinstance(self.json_response, list) and self.json_response:
            return self.json_response.pop(0)
        return self.json_response


class FakeIndex:
    """A `VectorIndex` that returns whatever the test told it to."""

    def __init__(self, hits: list[tuple[str, float]] | None = None, available: bool = True) -> None:
        self.hits = hits or []
        self._available = available
        self.indexed_jobs: list[Job] = []
        self.indexed_candidates: list[Candidate] = []

    @property
    def available(self) -> bool:
        return self._available

    def index_job(self, job): self.indexed_jobs.append(job)
    def index_candidate(self, c): self.indexed_candidates.append(c)
    def remove_job(self, job_id): ...
    def remove_candidate(self, candidate_id): ...
    def search_candidates(self, job, top_k=20): return self.hits[:top_k]
    def search_jobs(self, candidate, top_k=10): return self.hits[:top_k]


@pytest.fixture
def job() -> Job:
    return Job(
        id="job1",
        title="Senior CUDA Engineer",
        company="Acme",
        required_skills=["CUDA", "PyTorch", "NCCL"],
        summary="Distributed training infrastructure.",
        raw_text="We need someone who has scaled training across many GPUs.",
    )


@pytest.fixture
def candidates() -> list[Candidate]:
    return [
        Candidate(
            id="c1",
            name="Ada",
            current_title="ML Systems Engineer",
            skills=["CUDA", "NCCL", "PyTorch"],
            experience_years=8,
            resume_summary="Scaled distributed training to 512 GPUs.",
        ),
        Candidate(
            id="c2",
            name="Grace",
            current_title="Backend Engineer",
            skills=["Go", "Kubernetes"],
            experience_years=6,
            resume_summary="Built high-throughput services.",
        ),
    ]


@pytest.fixture
def store(tmp_path):
    from openrecruiter.store.sqlite import SQLiteStore

    return SQLiteStore(tmp_path / "test.db")
