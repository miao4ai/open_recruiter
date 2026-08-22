"""Turn tool results into what the chat UI renders.

The client draws two different things. **Blocks** are a list — several can
appear in one message, so anything the agent may do more than once in a turn
belongs here. **Actions** are singular — the message carries at most one, so
only the primary outcome of a turn can be one.

Keeping the mapping in its own module means each shape can be tested against
what the front end actually reads, rather than being asserted indirectly through
a stream.
"""

from __future__ import annotations

from typing import Any

#: Tool results carrying this key are instructions to open a panel, not data.
UI_CARD_KEY = "ui_card"


def as_action(tool_name: str, result: Any) -> dict | None:
    """The one card this turn is primarily about, if any."""
    if not isinstance(result, dict):
        return None

    if UI_CARD_KEY in result:
        card = {k: v for k, v in result.items() if k != "note"}
        card["type"] = card.pop(UI_CARD_KEY)
        return card

    if tool_name == "create_job":
        return {"type": "create_job", "job": result}

    if tool_name == "create_candidate":
        return {"type": "create_candidate", "candidate": result}

    if tool_name in ("draft_email", "recommend_to_employer") and result.get("subject"):
        return {"type": "compose_email", "email": result}

    if tool_name == "market_analysis" and result.get("summary"):
        return {"type": "market_analysis", "report": result}

    if tool_name == "search_web_jobs":
        return None  # handled as a block; the action slot carries the list below

    return None


def as_block(tool_name: str, result: Any) -> dict | None:
    """A card to append to this message, if the tool produced one."""
    if result is None:
        return None

    if tool_name == "rank_candidates" and isinstance(result, list) and result:
        return _match_report(result)

    if tool_name == "evaluate_candidate" and isinstance(result, dict) and not result.get("error"):
        return {"type": "candidate_eval", **result}

    if tool_name == "check_inbox" and isinstance(result, dict) and result.get("messages"):
        messages = result["messages"]
        return {
            "type": "inbox_preview",
            "emails": messages,
            "total": result.get("count", len(messages)),
            "unread": sum(1 for m in messages if m.get("unread")),
        }

    if tool_name == "search_web_jobs" and isinstance(result, list) and result:
        return {"type": "job_search_results", "jobs": result}

    # Presence, not truthiness: a posting whose fields all came back blank is
    # still a result the card should show, rather than one that vanishes.
    if tool_name == "analyze_job_match" and isinstance(result, dict) and "match" in result:
        return {"type": "job_match_result", **result}

    if tool_name == "improve_resume" and isinstance(result, dict) and result.get("suggestions"):
        return {
            "type": "resume_improvement",
            "summary": result.get("summary", ""),
            "job_title": result.get("job_title", ""),
            "job_company": result.get("job_company", ""),
            "match_score": result.get("match_score", 0.0),
            "suggestions": result["suggestions"],
        }

    if tool_name == "generate_cover_letter" and isinstance(result, dict) and result.get("body"):
        return {
            "type": "cover_letter",
            "job_title": result.get("job_title", ""),
            "job_company": result.get("job_company", ""),
            "subject": result.get("subject", ""),
            "body": result["body"],
        }

    return None


def _match_report(matches: list[dict]) -> dict:
    """Candidates ranked for a job.

    The block was designed the other way round — one candidate against many
    jobs — so the job sits in the `candidate` slot. Reusing the shape keeps the
    existing card working; renaming it would be a front-end change for no gain.
    """
    rankings = []
    for m in matches:
        title = m.get("current_title") or ""
        company = m.get("current_company") or ""
        label = f"{title} @ {company}" if title and company else title or company
        years = m.get("experience_years")
        skills = ", ".join(m.get("skills") or [])
        rankings.append(
            {
                "job_id": m.get("candidate_id", ""),  # the card navigates by this
                "candidate_id": m.get("candidate_id", ""),
                "candidate_name": m.get("name") or "Unknown",
                "title": m.get("name") or "Unknown",
                "company": label,
                "score": m.get("score", 0.0),
                "strengths": m.get("strengths") or [],
                "gaps": m.get("gaps") or [],
                "one_liner": m.get("reasoning")
                or f"{years if years is not None else '?'} yrs · {skills}",
            }
        )
    return {
        "type": "match_report",
        "candidate": {"id": "", "name": "Ranked candidates", "current_title": "Job", "skills": []},
        "rankings": rankings,
        "summary": f"Top {len(rankings)} candidates for this role.",
    }


#: Tool -> the panel a result should focus, when the agent touched one entity.
_HINT_BY_TOOL = {
    "get_candidate": "candidate",
    "evaluate_candidate": "candidate",
    "match_candidate": "candidate",
    "set_candidate_status": "candidate",
    "draft_email": "candidate",
    "get_job": "job",
    "create_job": "job",
    "rank_candidates": "job",
}


def as_context_hint(tool_name: str, arguments: dict) -> dict | None:
    """Which record the right-hand panel should show.

    Derived from what the agent actually did, rather than asked of the model as
    a separate field it had to remember to fill in.
    """
    kind = _HINT_BY_TOOL.get(tool_name)
    if kind is None:
        return None
    record_id = arguments.get(f"{kind}_id")
    return {"type": kind, "id": record_id} if record_id else None


__all__ = ["UI_CARD_KEY", "as_action", "as_block", "as_context_hint"]
