"""What the model is told before it starts working.

The obvious way to give an agent context is to paste the pipeline into the
system prompt. That stops working around the first few hundred candidates: the
prompt either gets truncated or gets expensive, and either way the model sees an
arbitrary slice rather than a relevant one.

So this builds a *small* briefing — what jobs exist, how the pipeline is
distributed, and the handful of candidates most related to what the user just
asked — and leaves everything else to the tools. The agent can call
`search_candidates` or `get_candidate` when it needs more, which is both cheaper
and unbounded.
"""

from __future__ import annotations

from collections import Counter

from openrecruiter.store.base import Store, VectorIndex
from openrecruiter.types import Candidate, Job

#: Jobs are few and each one is short, so they are all listed. Candidates are
#: many, so only the relevant ones are — retrieved, not sliced.
MAX_JOBS = 20
MAX_CANDIDATES = 8


def build_pipeline_context(
    store: Store,
    index: VectorIndex | None = None,
    message: str = "",
    max_jobs: int = MAX_JOBS,
    max_candidates: int = MAX_CANDIDATES,
) -> str:
    """A compact briefing on the recruiter's pipeline."""
    sections: list[str] = []

    jobs = store.list_jobs(limit=max_jobs)
    if jobs:
        sections.append(_render_jobs(jobs))

    # One cheap read that would otherwise cost the model a tool call on almost
    # every turn: how many people are at each stage.
    candidates = store.list_candidates(limit=1000)
    if candidates:
        sections.append(_render_pipeline(candidates))

    relevant, retrieved = _relevant_candidates(candidates, index, message, max_candidates)
    if relevant:
        sections.append(_render_candidates(relevant, retrieved=retrieved))

    if not sections:
        return "The pipeline is empty — no jobs and no candidates yet."

    return "\n\n".join(sections)


def _relevant_candidates(
    candidates: list[Candidate],
    index: VectorIndex | None,
    message: str,
    limit: int,
) -> tuple[list[Candidate], bool]:
    """The candidates worth naming up front, and whether they were retrieved.

    With retrieval, that means the ones related to the question. Without it,
    the most recent — which is at least a defensible ordering, unlike whatever
    the database returns first. The caller needs to know which it got: labelling
    an arbitrary slice as "related to this message" tells the model something
    untrue about its own context.
    """
    if not candidates:
        return [], False

    if message and index is not None and index.available:
        # The query is wrapped as a job so the same embedding path serves both.
        hits = index.search_candidates(Job(raw_text=message, summary=message), top_k=limit)
        by_id = {c.id: c for c in candidates}
        found = [by_id[cid] for cid, _ in hits if cid in by_id]
        if found:
            return found, True

    return candidates[:limit], False


def _render_jobs(jobs: list[Job]) -> str:
    lines = [f"## Open jobs ({len(jobs)})"]
    for job in jobs:
        skills = ", ".join(job.required_skills[:5])
        line = f"- [{job.id}] {job.title}"
        if job.company:
            line += f" at {job.company}"
        if skills:
            line += f" — needs {skills}"
        lines.append(line)
    return "\n".join(lines)


def _render_pipeline(candidates: list[Candidate]) -> str:
    counts = Counter(c.status.value for c in candidates)
    lines = [f"## Pipeline ({len(candidates)} candidates)"]
    lines += [f"- {status}: {n}" for status, n in sorted(counts.items())]
    return "\n".join(lines)


def _render_candidates(candidates: list[Candidate], retrieved: bool) -> str:
    heading = (
        "## Candidates related to this message"
        if retrieved
        else "## Most recent candidates"
    )
    lines = [
        f"{heading} ({len(candidates)})",
        "Use search_candidates or get_candidate for anyone not listed here.",
    ]
    for c in candidates:
        skills = ", ".join(c.skills[:5])
        line = f"- [{c.id}] {c.name}"
        if c.current_title:
            line += f" — {c.current_title}"
            if c.current_company:
                line += f" at {c.current_company}"
        line += f" | {c.status.value}"
        if skills:
            line += f" | {skills}"
        lines.append(line)
    return "\n".join(lines)


__all__ = ["MAX_CANDIDATES", "MAX_JOBS", "build_pipeline_context"]
