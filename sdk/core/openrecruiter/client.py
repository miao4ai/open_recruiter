"""`Recruiter` — the front door of the SDK.

Everything below it is swappable: the store, the vector index, the ranker, and
the tool set are all constructor arguments with working defaults. Used plainly:

    from openrecruiter import Recruiter

    r = Recruiter(anthropic_api_key="sk-ant-...", voyage_api_key="pa-...")
    job = r.add_job(open("jd.txt").read())
    r.add_candidate(open("resume.txt").read())

    for match in r.rank(job.id):
        print(match.score, match.candidate_id, match.reasoning)

    for event in r.chat("draft an intro email to the strongest candidate"):
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from openrecruiter.agent import Agent, PendingApproval
from openrecruiter.config import Config
from openrecruiter.context import build_pipeline_context
from openrecruiter.events import Event
from openrecruiter.prompts import AGENT_SYSTEM, DRAFT_EMAIL, PARSE_JD, PARSE_RESUME
from openrecruiter.providers.llm import LLM
from openrecruiter.ranking.api import APIRanker
from openrecruiter.ranking.base import Ranker
from openrecruiter.ranking.embedding import EmbeddingRanker
from openrecruiter.ranking.two_stage import TwoStageRanker
from openrecruiter.store.base import NullVectorIndex, Store, VectorIndex
from openrecruiter.store.sqlite import SQLiteStore
from openrecruiter.store.vector import ChromaVectorIndex
from openrecruiter.tools.base import Tool, ToolRegistry
from openrecruiter.tools.recruiting import build_recruiting_tools
from openrecruiter.types import Candidate, CandidateStatus, EmailDraft, Job, Match

log = logging.getLogger(__name__)


class Recruiter:
    """A recruiting pipeline: storage, retrieval, ranking, and an agent over them."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        store: Store | None = None,
        index: VectorIndex | None = None,
        ranker: Ranker | None = None,
        extra_tools: list[Tool] | None = None,
        system: str = AGENT_SYSTEM,
        data_dir: str | Path = ".",
        **config_kwargs,
    ) -> None:
        self.config = config or Config(**config_kwargs)
        self.llm = LLM(self.config)

        data_dir = Path(data_dir)
        self.store = store or SQLiteStore(data_dir / "openrecruiter.db")
        self.index = index if index is not None else self._default_index(data_dir)
        self.ranker = ranker or self._default_ranker()

        self.tools = ToolRegistry(build_recruiting_tools(self))
        if extra_tools:
            self.tools.extend(extra_tools)
        self.system = system

    # ── defaults ─────────────────────────────────────────────────────────

    def _default_index(self, data_dir: Path) -> VectorIndex:
        if not self.config.voyage_api_key:
            log.info("No Voyage key — semantic retrieval disabled, ranking falls back to the LLM.")
            return NullVectorIndex()
        # The config object is passed by reference so a key set later still applies.
        return ChromaVectorIndex(lambda: self.config, data_dir / "chroma_data")

    def _default_ranker(self) -> Ranker:
        """Retrieve then rerank when embeddings exist; otherwise rerank directly.

        Running the LLM over the whole pool is only affordable because a pool
        without embeddings is, in practice, a small one.
        """
        reranker = APIRanker(self.llm)
        if self.index.available:
            return TwoStageRanker(EmbeddingRanker(self.index), reranker)
        return reranker

    # ── ingest ───────────────────────────────────────────────────────────

    def add_job(self, raw_text: str) -> Job:
        """Parse a job description into a `Job`, store it, and index it."""
        parsed = self._parse(PARSE_JD, raw_text)
        job = Job(
            title=str(parsed.get("title") or ""),
            company=str(parsed.get("company") or ""),
            required_skills=list(parsed.get("required_skills") or []),
            preferred_skills=list(parsed.get("preferred_skills") or []),
            experience_years=_as_int(parsed.get("experience_years")),
            location=str(parsed.get("location") or ""),
            remote=bool(parsed.get("remote") or False),
            salary_range=str(parsed.get("salary_range") or ""),
            summary=str(parsed.get("summary") or ""),
            raw_text=raw_text,
        )
        self.store.add_job(job)
        self.index.index_job(job)
        return job

    def add_candidate(self, raw_text: str) -> Candidate:
        """Parse resume text into a `Candidate`, store it, and index it."""
        parsed = self._parse(PARSE_RESUME, raw_text)
        candidate = Candidate(
            name=str(parsed.get("name") or ""),
            email=str(parsed.get("email") or ""),
            phone=str(parsed.get("phone") or ""),
            current_title=str(parsed.get("current_title") or ""),
            current_company=str(parsed.get("current_company") or ""),
            skills=list(parsed.get("skills") or []),
            experience_years=_as_int(parsed.get("experience_years")),
            location=str(parsed.get("location") or ""),
            resume_summary=str(parsed.get("resume_summary") or ""),
            raw_resume_text=raw_text,
        )
        self.store.add_candidate(candidate)
        self.index.index_candidate(candidate)
        return candidate

    def _parse(self, system: str, raw_text: str) -> dict:
        data = self.llm.complete_json(system, [{"role": "user", "content": raw_text}])
        if isinstance(data, list):
            data = data[0] if data else {}
        return data if isinstance(data, dict) else {}

    # ── ranking ──────────────────────────────────────────────────────────

    def rank(self, job_id: str, top_k: int = 20, ranker: Ranker | None = None) -> list[Match]:
        """Order the candidate pool against a job, best fit first."""
        job = self.store.get_job(job_id)
        if job is None:
            return []
        candidates = self.store.list_candidates(limit=1000)
        matches = (ranker or self.ranker).rank(job, candidates, top_k=top_k)
        for match in matches:
            self.store.save_match(match)
        return matches

    def match(self, candidate_id: str, job_id: str) -> Match:
        """Assess one candidate against one job, with strengths and gaps."""
        job = self.store.get_job(job_id)
        candidate = self.store.get_candidate(candidate_id)
        if job is None or candidate is None:
            return Match(
                candidate_id=candidate_id,
                job_id=job_id,
                reasoning="Job or candidate not found.",
            )
        result = APIRanker(self.llm).score(job, candidate)
        self.store.save_match(result)
        return result

    def search_candidates(self, query: str, top_k: int = 10) -> list[tuple[Candidate, float]]:
        """Free-text semantic search over candidates.

        The query is wrapped in a throwaway `Job` so the same embedding path
        serves both — which keeps `VectorIndex` down to two search methods
        instead of four.
        """
        hits = self.index.search_candidates(Job(raw_text=query, summary=query), top_k=top_k)
        found = []
        for cid, score in hits:
            candidate = self.store.get_candidate(cid)
            if candidate is not None:
                found.append((candidate, score))
        return found

    def set_status(self, candidate_id: str, status: str | CandidateStatus) -> bool:
        try:
            value = CandidateStatus(status)
        except ValueError:
            return False
        return self.store.set_candidate_status(candidate_id, value)

    # ── outreach ─────────────────────────────────────────────────────────

    def draft_email(
        self,
        candidate_id: str,
        job_id: str = "",
        email_type: str = "outreach",
        instructions: str = "",
    ) -> EmailDraft:
        """Write a personalised email. Returns a draft — nothing is sent."""
        candidate = self.store.get_candidate(candidate_id)
        if candidate is None:
            return EmailDraft(candidate_id=candidate_id, job_id=job_id, email_type=email_type)

        parts = [f"## Candidate\n{candidate.profile_text()}"]
        job = self.store.get_job(job_id) if job_id else None
        if job is not None:
            parts.append(
                f"\n## Job\nTitle: {job.title}\nCompany: {job.company}\n"
                f"Required skills: {', '.join(job.required_skills)}\n"
                f"Summary: {job.summary}"
            )
        parts.append(
            f"\n## Task\nEmail type: {email_type}\n"
            f"Instructions: {instructions or 'none — use your judgement'}"
        )

        data = self._parse(DRAFT_EMAIL, "\n".join(parts))
        return EmailDraft(
            candidate_id=candidate_id,
            job_id=job_id,
            email_type=email_type,
            subject=str(data.get("subject") or ""),
            body=str(data.get("body") or ""),
        )

    # ── context ──────────────────────────────────────────────────────────

    def pipeline_context(self, message: str = "") -> str:
        """A briefing to splice into a system prompt.

        Small on purpose: the tools handle retrieval, so the prompt does not
        have to carry the pipeline and does not grow with it.
        """
        return build_pipeline_context(self.store, self.index, message)

    # ── agent ────────────────────────────────────────────────────────────

    def agent(self, max_steps: int = 8) -> Agent:
        return Agent(self.llm, self.tools, system=self.system, max_steps=max_steps)

    def chat(
        self,
        message: str,
        history: list[dict] | None = None,
        max_steps: int = 8,
    ) -> Iterator[Event]:
        """Run the agent, streaming events as they happen."""
        yield from self.agent(max_steps=max_steps).run(message, history=history)

    def ask(self, message: str, history: list[dict] | None = None) -> str:
        """Run the agent and return only the final text. For scripts and tests."""
        from openrecruiter.events import Finished, TextDelta

        text: list[str] = []
        for event in self.chat(message, history=history):
            if isinstance(event, TextDelta):
                text.append(event.text)
            elif isinstance(event, Finished) and event.text:
                return event.text
        return "".join(text)


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


__all__ = ["PendingApproval", "Recruiter"]
