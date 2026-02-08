"""Planning Agent — decomposes user requests into executable task steps."""

from __future__ import annotations

from open_recruiter.config import Config
from open_recruiter.llm import chat_json
from open_recruiter.prompts import PLANNING_AGENT
from open_recruiter.schemas import PlanStep, TaskType


def create_plan(config: Config, user_request: str, context: str = "") -> list[PlanStep]:
    """Break a user request into a sequence of PlanSteps."""
    prompt = user_request
    if context:
        prompt = f"Context:\n{context}\n\nUser request:\n{user_request}"

    data = chat_json(
        config,
        system=PLANNING_AGENT,
        messages=[{"role": "user", "content": prompt}],
    )

    # The LLM returns a JSON array of step dicts
    steps_raw = data if isinstance(data, list) else data.get("steps", [])
    steps: list[PlanStep] = []
    for s in steps_raw:
        try:
            steps.append(PlanStep(
                step=s["step"],
                task_type=TaskType(s["task_type"]),
                description=s["description"],
                depends_on=s.get("depends_on", []),
            ))
        except (KeyError, ValueError):
            continue
    return steps
