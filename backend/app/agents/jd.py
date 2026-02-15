"""JD Agent — sends extracted JD text to LLM for structured parsing.

Pipeline position:
  raw text (from resume_parser.extract_text) → THIS AGENT → Job dict
"""

from __future__ import annotations

from app.config import Config
from app.llm import chat_json
from app.prompts import PARSE_JD


def parse_jd_text(cfg: Config, raw_text: str) -> dict:
    """Parse raw JD text into structured job fields via LLM.

    Returns a dict with keys matching the Job model:
      title, company, required_skills, preferred_skills,
      experience_years, location, remote, salary_range, summary
    """
    data = chat_json(
        cfg,
        system=PARSE_JD,
        messages=[{"role": "user", "content": raw_text}],
    )

    # Normalise — the LLM may return slightly different shapes
    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "title": data.get("title", ""),
        "company": data.get("company", ""),
        "required_skills": data.get("required_skills", []),
        "preferred_skills": data.get("preferred_skills", []),
        "experience_years": _safe_int(data.get("experience_years")),
        "location": data.get("location", ""),
        "remote": bool(data.get("remote", False)),
        "salary_range": data.get("salary_range", ""),
        "summary": data.get("summary", ""),
    }


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
