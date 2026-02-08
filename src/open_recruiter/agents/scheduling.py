"""Scheduling Agent — interview coordination (MVP stub)."""

from __future__ import annotations

from open_recruiter.config import Config
from open_recruiter.llm import chat_json
from open_recruiter.prompts import SCHEDULING_AGENT


def suggest_slots(
    config: Config,
    candidate_name: str,
    role: str,
    preferences: str = "",
) -> dict:
    """Suggest interview time slots (MVP: LLM-generated suggestions).

    In a production version this would integrate with Google Calendar API
    to check real availability.
    """
    prompt = (
        f"Suggest interview slots for:\n"
        f"Candidate: {candidate_name}\n"
        f"Role: {role}\n"
    )
    if preferences:
        prompt += f"Preferences / constraints: {preferences}\n"
    prompt += "\nSuggest 3 slots within the next 5 business days."

    return chat_json(
        config,
        system=SCHEDULING_AGENT,
        messages=[{"role": "user", "content": prompt}],
    )
