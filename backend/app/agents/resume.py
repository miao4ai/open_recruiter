"""Resume Agent — sends extracted text to LLM for structured parsing.

Pipeline position:
  raw text (from resume_parser) → THIS AGENT → Candidate dict
"""

from __future__ import annotations

from app.config import Config
from app.llm import chat_json
from app.prompts import PARSE_RESUME


def parse_resume_text(cfg: Config, raw_text: str) -> dict:
    """Parse raw resume text into structured candidate fields via LLM.

    Returns a dict with keys matching the Candidate model:
      name, email, phone, current_title, current_company,
      skills, experience_years, location, resume_summary
    """
    data = chat_json(
        cfg,
        system=PARSE_RESUME,
        messages=[{"role": "user", "content": raw_text}],
    )

    # Normalise — the LLM may return slightly different shapes
    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "current_title": data.get("current_title", ""),
        "current_company": data.get("current_company", ""),
        "skills": data.get("skills", []),
        "experience_years": _safe_int(data.get("experience_years")),
        "location": data.get("location", ""),
        "resume_summary": data.get("resume_summary", ""),
    }


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
