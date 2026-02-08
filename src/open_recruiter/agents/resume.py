"""Resume Agent — parses and analyzes candidate resumes."""

from __future__ import annotations

from open_recruiter.config import Config
from open_recruiter.llm import chat_json
from open_recruiter.prompts import RESUME_AGENT
from open_recruiter.schemas import Candidate


def parse_resume(config: Config, resume_text: str) -> Candidate:
    """Parse raw resume text into a structured Candidate object."""
    data = chat_json(
        config,
        system=RESUME_AGENT,
        messages=[{"role": "user", "content": resume_text}],
    )

    return Candidate(
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        resume_text=resume_text,
        skills=data.get("skills", []),
        experience_years=int(data.get("experience_years", 0)),
        summary=data.get("summary", ""),
    )


def analyze_resume(config: Config, candidate: Candidate, jd_summary: str = "") -> str:
    """Provide a qualitative analysis of a candidate's resume, optionally against a JD."""
    prompt = f"Candidate profile:\n{candidate.summary}\nSkills: {', '.join(candidate.skills)}\nExperience: {candidate.experience_years} years"
    if jd_summary:
        prompt += f"\n\nJob description summary:\n{jd_summary}"
        prompt += "\n\nProvide a brief analysis of this candidate's fit for the role."
    else:
        prompt += "\n\nProvide a brief summary of this candidate's strengths and areas for growth."

    from open_recruiter.llm import chat
    return chat(config, system=RESUME_AGENT, messages=[{"role": "user", "content": prompt}])
