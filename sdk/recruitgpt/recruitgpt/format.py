"""Turning a ranking example into text, and reading the answer back.

Candidates are labelled A, B, C… *within* an example rather than by their real
ids. Ids are random hex: putting them in the prompt would let the model memorise
which id ranks highly instead of learning why, and the memorisation would look
like accuracy right up until the benchmark used different ids.
"""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass

from recruitgpt.schemas import Assessment, RankingExample

SYSTEM = (
    "You are RecruitGPT, an expert technical recruiter. You are given a job and a "
    "shortlist of candidates, and you rank the candidates for that job, best first.\n\n"
    "Judge on evidence relevant to the job. Depth in a required skill outweighs breadth "
    "across unrelated ones, and years of experience are not a substitute for the specific "
    "experience the role asks for. A candidate with a long record in an adjacent area may "
    "rank below a shorter record in exactly the right one.\n\n"
    "Never use age, gender, nationality, ethnicity, or any other protected characteristic, "
    "and do not treat a name or a location as a proxy for one.\n\n"
    "Respond with JSON only."
)

#: A, B, ... Z. Past 26 candidates a listwise prompt is not the right tool.
LABELS = string.ascii_uppercase

_JSON = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ListwisePrompt:
    """A rendered example, plus the mapping needed to read the answer."""

    system: str
    user: str
    #: "A" -> candidate_id
    label_to_id: dict[str, str]

    @property
    def id_to_label(self) -> dict[str, str]:
        return {v: k for k, v in self.label_to_id.items()}


def build_prompt(example: RankingExample, order: list[str] | None = None) -> ListwisePrompt:
    """Render a job and its shortlist.

    `order` is the sequence candidates appear in — shuffled during training so
    position carries no signal. The label is the ordering, not the layout.
    """
    ids = order or [c.candidate_id for c in example.candidates]
    by_id = {c.candidate_id: c for c in example.candidates}
    if len(ids) > len(LABELS):
        raise ValueError(f"{len(ids)} candidates exceeds the {len(LABELS)} available labels")

    label_to_id = {LABELS[i]: cid for i, cid in enumerate(ids)}

    job = example.job
    parts = [
        "## Job",
        f"Title: {job.title}",
        f"Level: {job.level.value}",
    ]
    if job.domain:
        parts.append(f"Domain: {job.domain}")
    if job.required_skills:
        parts.append(f"Required: {', '.join(job.required_skills)}")
    if job.preferred_skills:
        parts.append(f"Preferred: {', '.join(job.preferred_skills)}")
    if job.minimum_experience_years:
        parts.append(f"Minimum experience: {job.minimum_experience_years} years")
    if job.description:
        parts.append(f"\n{job.description}")

    parts.append("\n## Candidates")
    for label, cid in label_to_id.items():
        parts.append(f"\n[{label}]\n{by_id[cid].profile_text()}")

    parts.append(
        "\n## Task\n"
        "Rank every candidate for this job, best first. Return JSON:\n"
        '{"ranking": ["<label>", ...], "assessments": '
        '[{"label": "<label>", "match_score": 0.0-1.0, "strengths": [...], '
        '"gaps": [...], "recommendation": "strong_match|good_match|weak_match"}]}'
    )

    return ListwisePrompt(system=SYSTEM, user="\n".join(parts), label_to_id=label_to_id)


def render_target(example: RankingExample, prompt: ListwisePrompt) -> str:
    """The assistant turn a training example should learn to produce."""
    id_to_label = prompt.id_to_label
    by_id = {a.candidate_id: a for a in example.assessments}

    assessments = []
    for cid in example.ordering:
        a = by_id.get(cid) or Assessment(candidate_id=cid)
        assessments.append(
            {
                "label": id_to_label[cid],
                "match_score": round(a.match_score, 3),
                "strengths": a.strengths,
                "gaps": a.gaps,
                "recommendation": a.recommendation,
            }
        )

    return json.dumps(
        {"ranking": [id_to_label[cid] for cid in example.ordering], "assessments": assessments},
        ensure_ascii=False,
    )


def parse_ranking(text: str, prompt: ListwisePrompt) -> tuple[list[str], list[Assessment]]:
    """Read a model's answer back into candidate ids.

    Tolerant on purpose: a base model with no fine-tuning will wrap its JSON in
    prose, and the benchmark has to be able to score it anyway — otherwise the
    baseline loses on formatting rather than on ranking, which would flatter the
    trained model for the wrong reason.
    """
    match = _JSON.search(text or "")
    if match is None:
        return [], []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [], []
    if not isinstance(data, dict):
        return [], []

    label_to_id = prompt.label_to_id
    seen: set[str] = set()
    ordering: list[str] = []
    for label in data.get("ranking") or []:
        cid = label_to_id.get(str(label).strip().upper().strip("[]"))
        if cid and cid not in seen:
            seen.add(cid)
            ordering.append(cid)

    assessments = []
    for raw in data.get("assessments") or []:
        if not isinstance(raw, dict):
            continue
        cid = label_to_id.get(str(raw.get("label", "")).strip().upper().strip("[]"))
        if cid is None:
            continue
        assessments.append(
            Assessment(
                candidate_id=cid,
                match_score=_score(raw.get("match_score")),
                strengths=[str(s) for s in (raw.get("strengths") or [])],
                gaps=[str(s) for s in (raw.get("gaps") or [])],
                recommendation=str(raw.get("recommendation") or "weak_match"),
            )
        )
    return ordering, assessments


def _score(value: object) -> float:
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if score > 1.0:
        score /= 100.0
    return round(max(0.0, min(1.0, score)), 4)


__all__ = ["LABELS", "ListwisePrompt", "SYSTEM", "build_prompt", "parse_ranking", "render_target"]
