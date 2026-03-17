"""Candidate Evaluation Swarm — 4 agents run in parallel, synthesizer combines results."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import database as db
from app.config import Config
from app.llm import chat_json
from app.prompts import (
    EVAL_RESUME_AGENT,
    EVAL_CULTURE_AGENT,
    EVAL_RISK_AGENT,
    EVAL_MARKET_AGENT,
    EVAL_SYNTHESIZER,
)

log = logging.getLogger(__name__)

_AGENT_LABELS = {
    "resume": "Skills & Experience",
    "culture": "Culture Fit",
    "risk": "Risk Assessment",
    "market": "Market Position",
}


def _build_candidate_text(candidate: dict) -> str:
    skills = candidate.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
    return (
        f"Name: {candidate.get('name', '')}\n"
        f"Current Title: {candidate.get('current_title', '')}\n"
        f"Current Company: {candidate.get('current_company', '')}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Skills: {skills_str}\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Summary: {candidate.get('resume_summary', '')}"
    )


def _run_agent(cfg: Config, prompt: str, user_msg: str) -> dict:
    try:
        data = chat_json(cfg, system=prompt, messages=[{"role": "user", "content": user_msg}])
        if isinstance(data, list):
            data = data[0] if data else {}
        return {
            "score": int(data.get("score", 50)),
            "verdict": data.get("verdict", ""),
            "findings": data.get("findings", []),
        }
    except Exception as e:
        log.error("Evaluation agent error: %s", e)
        return {"score": 50, "verdict": "Evaluation unavailable.", "findings": []}


def evaluate_candidate_swarm(cfg: Config, candidate_id: str, job_id: str = "") -> dict:
    """Run 4 evaluation agents in parallel and synthesize the results.

    Returns a dict with keys:
      dimensions, overall_score, hire_recommendation, synthesis
    """
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {"error": "Candidate not found"}

    job = db.get_job(job_id) if job_id else None
    candidate_text = _build_candidate_text(candidate)
    job_text = f"\n\n## Job Description\n{job['raw_text']}" if job else ""

    user_msg_with_job = f"## Candidate Profile\n{candidate_text}{job_text}"
    user_msg_no_job = f"## Candidate Profile\n{candidate_text}"

    agent_tasks = [
        ("resume",  EVAL_RESUME_AGENT,  user_msg_with_job),
        ("culture", EVAL_CULTURE_AGENT, user_msg_with_job),
        ("risk",    EVAL_RISK_AGENT,    user_msg_no_job),
        ("market",  EVAL_MARKET_AGENT,  user_msg_with_job),
    ]

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_key = {
            executor.submit(_run_agent, cfg, prompt, user_msg): key
            for key, prompt, user_msg in agent_tasks
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            results[key] = future.result()

    # Build synthesizer input
    synth_msg = (
        f"## Candidate: {candidate.get('name', '')}\n\n"
        f"### Resume/Skills Agent\nScore: {results['resume']['score']}\n"
        f"Verdict: {results['resume']['verdict']}\n"
        f"Findings: {'; '.join(results['resume']['findings'])}\n\n"
        f"### Culture Fit Agent\nScore: {results['culture']['score']}\n"
        f"Verdict: {results['culture']['verdict']}\n"
        f"Findings: {'; '.join(results['culture']['findings'])}\n\n"
        f"### Risk Agent\nScore: {results['risk']['score']}\n"
        f"Verdict: {results['risk']['verdict']}\n"
        f"Findings: {'; '.join(results['risk']['findings'])}\n\n"
        f"### Market Position Agent\nScore: {results['market']['score']}\n"
        f"Verdict: {results['market']['verdict']}\n"
        f"Findings: {'; '.join(results['market']['findings'])}"
    )

    try:
        synth = chat_json(cfg, system=EVAL_SYNTHESIZER, messages=[{"role": "user", "content": synth_msg}])
        if isinstance(synth, list):
            synth = synth[0] if synth else {}
    except Exception as e:
        log.error("Synthesizer error: %s", e)
        scores = [results[k]["score"] for k in ("resume", "culture", "risk", "market")]
        avg = int(scores[0] * 0.4 + scores[1] * 0.25 + scores[2] * 0.2 + scores[3] * 0.15)
        synth = {
            "overall_score": avg,
            "hire_recommendation": "yes" if avg >= 65 else "maybe" if avg >= 45 else "no",
            "synthesis": "Synthesis unavailable — see individual agent findings above.",
        }

    dimensions = [
        {
            "agent": key,
            "label": _AGENT_LABELS[key],
            "score": results[key]["score"],
            "verdict": results[key]["verdict"],
            "findings": results[key]["findings"],
        }
        for key in ("resume", "culture", "risk", "market")
    ]

    return {
        "dimensions": dimensions,
        "overall_score": int(synth.get("overall_score", 50)),
        "hire_recommendation": synth.get("hire_recommendation", "maybe"),
        "synthesis": synth.get("synthesis", ""),
    }
