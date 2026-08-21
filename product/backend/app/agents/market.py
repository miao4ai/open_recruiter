"""Market Agent — salary benchmarks and market intelligence using LLM knowledge."""

from __future__ import annotations

import logging

from app import database as db
from app.config import Config
from app.llm import chat_json
from app.prompts import MARKET_ANALYSIS

log = logging.getLogger(__name__)


def analyze_market(
    cfg: Config,
    role: str,
    location: str = "",
    industry: str = "",
    context: str = "",
) -> dict:
    """Provide salary benchmarks and market analysis for a role.

    Returns a dict with salary_range, market_demand, key_factors,
    comparable_titles, regional_notes, and summary.
    """
    parts: list[str] = [f"Role: {role}"]
    if location:
        parts.append(f"Location: {location}")
    if industry:
        parts.append(f"Industry: {industry}")
    if context:
        parts.append(f"\nAdditional context:\n{context}")

    user_msg = "\n".join(parts)

    try:
        data = chat_json(
            cfg,
            system=MARKET_ANALYSIS,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        log.error("Market agent LLM call failed: %s", e)
        return {"error": f"LLM error: {e}"}

    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "salary_range": data.get("salary_range", {}),
        "market_demand": data.get("market_demand", "medium"),
        "key_factors": data.get("key_factors", []),
        "comparable_titles": data.get("comparable_titles", []),
        "regional_notes": data.get("regional_notes", ""),
        "summary": data.get("summary", ""),
        "role": role,
        "location": location,
    }
