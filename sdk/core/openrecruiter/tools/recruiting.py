"""The recruiting tools the agent is given by default.

Each one is a thin wrapper over the client — the logic lives there, so the same
capability is available whether it is reached through the agent or called
directly. Descriptions are written for the model: they say when to reach for the
tool, not just what it does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openrecruiter.tools.base import Tool

if TYPE_CHECKING:  # pragma: no cover
    from openrecruiter.client import Recruiter


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


_STR = {"type": "string"}
_INT = {"type": "integer"}


def build_recruiting_tools(client: "Recruiter") -> list[Tool]:
    """Bind the built-in tools to a client."""

    def list_jobs(limit: int = 20) -> list[dict]:
        return [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "required_skills": j.required_skills,
            }
            for j in client.store.list_jobs(limit=limit)
        ]

    def get_job(job_id: str) -> dict | None:
        job = client.store.get_job(job_id)
        return job.model_dump() if job else None

    def create_job(raw_text: str) -> dict:
        return client.add_job(raw_text).model_dump()

    def list_candidates(limit: int = 30) -> list[dict]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "current_title": c.current_title,
                "current_company": c.current_company,
                "skills": c.skills,
                "experience_years": c.experience_years,
                "status": c.status.value,
            }
            for c in client.store.list_candidates(limit=limit)
        ]

    def get_candidate(candidate_id: str) -> dict | None:
        candidate = client.store.get_candidate(candidate_id)
        return candidate.model_dump() if candidate else None

    def create_candidate(raw_text: str) -> dict:
        return client.add_candidate(raw_text).model_dump()

    def rank_candidates(job_id: str, top_k: int = 10) -> list[dict]:
        """Ranked matches, carrying enough of each candidate to talk about them.

        Returning bare ids would force a follow-up call per candidate just to
        say a name, which is a slow way to answer "who should I look at".
        """
        results = []
        for match in client.rank(job_id, top_k=top_k):
            candidate = client.store.get_candidate(match.candidate_id)
            results.append(
                {
                    **match.model_dump(),
                    "name": candidate.name if candidate else "",
                    "current_title": candidate.current_title if candidate else "",
                    "current_company": candidate.current_company if candidate else "",
                    "experience_years": candidate.experience_years if candidate else None,
                    "skills": candidate.skills[:5] if candidate else [],
                }
            )
        return results

    def match_candidate(candidate_id: str, job_id: str) -> dict:
        return client.match(candidate_id, job_id).model_dump()

    def search_candidates(query: str, top_k: int = 10) -> list[dict]:
        return [
            {"id": c.id, "name": c.name, "current_title": c.current_title, "score": score}
            for c, score in client.search_candidates(query, top_k=top_k)
        ]

    def set_candidate_status(candidate_id: str, status: str) -> dict:
        ok = client.set_status(candidate_id, status)
        return {"updated": ok, "candidate_id": candidate_id, "status": status}

    def draft_email(
        candidate_id: str,
        job_id: str = "",
        email_type: str = "outreach",
        instructions: str = "",
    ) -> dict:
        return client.draft_email(
            candidate_id, job_id=job_id, email_type=email_type, instructions=instructions
        ).model_dump()

    return [
        Tool(
            name="list_jobs",
            description="List the jobs in the pipeline. Call this first when the user names a role but not an id.",
            parameters=_obj({"limit": _INT}),
            fn=list_jobs,
        ),
        Tool(
            name="get_job",
            description="Full detail for one job, including the original description text.",
            parameters=_obj({"job_id": _STR}, ["job_id"]),
            fn=get_job,
        ),
        Tool(
            name="create_job",
            description=(
                "Create a job from a raw job description. The text is parsed into "
                "title, company, skills and requirements automatically."
            ),
            parameters=_obj({"raw_text": _STR}, ["raw_text"]),
            fn=create_job,
        ),
        Tool(
            name="list_candidates",
            description="List candidates with their headline details and pipeline status.",
            parameters=_obj({"limit": _INT}),
            fn=list_candidates,
        ),
        Tool(
            name="get_candidate",
            description="Full detail for one candidate, including the resume summary.",
            parameters=_obj({"candidate_id": _STR}, ["candidate_id"]),
            fn=get_candidate,
        ),
        Tool(
            name="create_candidate",
            description=(
                "Create a candidate from raw resume text. The text is parsed into "
                "name, contact details, skills and experience automatically."
            ),
            parameters=_obj({"raw_text": _STR}, ["raw_text"]),
            fn=create_candidate,
        ),
        Tool(
            name="rank_candidates",
            description=(
                "Rank the candidate pool against a job, best fit first. Use this for "
                "'who should I look at for X' — it returns scores with strengths and gaps."
            ),
            parameters=_obj({"job_id": _STR, "top_k": _INT}, ["job_id"]),
            fn=rank_candidates,
        ),
        Tool(
            name="match_candidate",
            description="Assess one specific candidate against one specific job in detail.",
            parameters=_obj({"candidate_id": _STR, "job_id": _STR}, ["candidate_id", "job_id"]),
            fn=match_candidate,
        ),
        Tool(
            name="search_candidates",
            description=(
                "Semantic search over candidates by free text, for questions like "
                "'anyone who has done distributed training'. Not tied to a job."
            ),
            parameters=_obj({"query": _STR, "top_k": _INT}, ["query"]),
            fn=search_candidates,
        ),
        Tool(
            name="set_candidate_status",
            description=(
                "Move a candidate through the pipeline. One of: new, contacted, replied, "
                "interviewing, offered, hired, rejected, archived."
            ),
            parameters=_obj({"candidate_id": _STR, "status": _STR}, ["candidate_id", "status"]),
            fn=set_candidate_status,
        ),
        Tool(
            name="draft_email",
            description=(
                "Write a personalised email to a candidate about a job. Returns a draft "
                "for review — it does not send anything."
            ),
            parameters=_obj(
                {
                    "candidate_id": _STR,
                    "job_id": _STR,
                    "email_type": {
                        "type": "string",
                        "enum": ["outreach", "followup", "interview_invite", "rejection"],
                    },
                    "instructions": _STR,
                },
                ["candidate_id"],
            ),
            fn=draft_email,
        ),
    ]


__all__ = ["build_recruiting_tools"]
