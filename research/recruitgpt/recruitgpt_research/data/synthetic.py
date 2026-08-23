"""A deterministic generator, for making the pipeline runnable before it is real.

No model is called. Jobs and candidates come from templates and a seeded RNG,
and the ordering is computed from the structured ground truth rather than
judged — which is the point: phase 0 needs a dataset shaped correctly so the
training and evaluation code can be exercised, not a dataset worth training on.

Phase 1 replaces the *content* with LLM generation seeded from the real Djinni
distributions. The schema, the difficulty bands, and the scoring rule below stay.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from recruitgpt.schemas import (
    Assessment,
    CandidateSpec,
    Difficulty,
    JobSpec,
    LabelQuality,
    RankingExample,
    Seniority,
)


@dataclass(frozen=True)
class RoleTemplate:
    """A job archetype, and the traps that go with it."""

    template_id: str
    title: str
    domain: str
    required: tuple[str, ...]
    preferred: tuple[str, ...]
    #: Skills that read as relevant and are not. The whole difficulty of the
    #: task lives here: "10 years of PyTorch" is not CUDA experience.
    adjacent: tuple[str, ...]
    min_years: int = 4


TEMPLATES = (
    RoleTemplate(
        template_id="cuda_perf",
        title="CUDA Performance Engineer",
        domain="ML Infrastructure",
        required=("CUDA", "C++", "Nsight"),
        preferred=("TensorRT", "NCCL"),
        adjacent=("PyTorch", "TensorFlow", "Python", "Keras"),
        min_years=4,
    ),
    RoleTemplate(
        template_id="dist_training",
        title="Distributed Training Engineer",
        domain="ML Infrastructure",
        required=("NCCL", "PyTorch Distributed", "CUDA"),
        preferred=("Megatron", "DeepSpeed"),
        adjacent=("Kubernetes", "Airflow", "Spark"),
        min_years=5,
    ),
    RoleTemplate(
        template_id="compiler",
        title="ML Compiler Engineer",
        domain="Compilers",
        required=("LLVM", "MLIR", "C++"),
        preferred=("TVM", "Triton"),
        adjacent=("Python", "PyTorch", "ONNX"),
        min_years=5,
    ),
    RoleTemplate(
        template_id="embedded",
        title="Embedded Systems Engineer",
        domain="Embedded",
        required=("C", "RTOS", "ARM"),
        preferred=("Zephyr", "CAN"),
        adjacent=("Python", "Linux", "Docker"),
        min_years=4,
    ),
    RoleTemplate(
        template_id="db_internals",
        title="Database Internals Engineer",
        domain="Databases",
        required=("C++", "Query Optimisation", "Storage Engines"),
        preferred=("Raft", "RocksDB"),
        adjacent=("SQL", "Postgres", "Python"),
        min_years=5,
    ),
    RoleTemplate(
        template_id="security",
        title="Application Security Engineer",
        domain="Security",
        required=("Threat Modelling", "SAST", "Cryptography"),
        preferred=("Fuzzing", "eBPF"),
        adjacent=("Python", "AWS", "Terraform"),
        min_years=4,
    ),
    RoleTemplate(
        template_id="frontend_perf",
        title="Frontend Performance Engineer",
        domain="Frontend",
        required=("JavaScript", "Browser Rendering", "Profiling"),
        preferred=("WebAssembly", "Service Workers"),
        adjacent=("React", "TypeScript", "CSS"),
        min_years=3,
    ),
    RoleTemplate(
        template_id="sre",
        title="Site Reliability Engineer",
        domain="Reliability",
        required=("Linux Internals", "Observability", "Incident Response"),
        preferred=("eBPF", "Chaos Engineering"),
        adjacent=("Kubernetes", "Terraform", "Python"),
        min_years=4,
    ),
)

#: How a required skill at level `n` counts toward coverage. Below 3 the
#: candidate has touched it; at 4 they have shipped with it.
_LEVEL_WEIGHT = {0: 0.0, 1: 0.15, 2: 0.35, 3: 0.6, 4: 0.85, 5: 1.0}


def _coverage(skills: dict[str, int], wanted: tuple[str, ...]) -> float:
    if not wanted:
        return 1.0
    return sum(_LEVEL_WEIGHT.get(skills.get(s, 0), 0.0) for s in wanted) / len(wanted)


def true_score(job: JobSpec, candidate: CandidateSpec) -> float:
    """The ground-truth fit, computed rather than judged.

    Required coverage dominates. Experience only matters up to what the job
    asked for — this is what makes a ten-year generalist lose to a four-year
    specialist, and it is the behaviour the whole benchmark is built to test.
    """
    required = _coverage(candidate.skills, tuple(job.required_skills))
    preferred = _coverage(candidate.skills, tuple(job.preferred_skills))
    seniority = min(1.0, candidate.experience_years / max(1, job.minimum_experience_years))
    return round(0.70 * required + 0.15 * preferred + 0.15 * seniority, 4)


def _assess(job: JobSpec, candidate: CandidateSpec) -> Assessment:
    required = _coverage(candidate.skills, tuple(job.required_skills))
    score = true_score(job, candidate)
    have = [s for s in job.required_skills if candidate.skills.get(s, 0) >= 3]
    missing = [s for s in job.required_skills if candidate.skills.get(s, 0) < 3]
    return Assessment(
        candidate_id=candidate.candidate_id,
        match_score=score,
        required_skill_coverage=round(required, 4),
        preferred_skill_coverage=round(_coverage(candidate.skills, tuple(job.preferred_skills)), 4),
        strengths=[f"{s} at depth" for s in have[:3]],
        gaps=[f"no demonstrated {s}" for s in missing[:3]],
        recommendation=(
            "strong_match" if score >= 0.75 else "good_match" if score >= 0.5 else "weak_match"
        ),
    )


def _candidate(
    rng: random.Random,
    index: int,
    template: RoleTemplate,
    difficulty: Difficulty,
) -> CandidateSpec:
    """Build a candidate to sit in a particular difficulty band."""
    skills: dict[str, int] = {}
    years = rng.randint(3, 8)

    if difficulty is Difficulty.STRONG:
        skills = {s: rng.randint(4, 5) for s in template.required}
        skills |= {s: rng.randint(3, 5) for s in template.preferred}
        years = template.min_years + rng.randint(1, 4)
    elif difficulty is Difficulty.GOOD:
        skills = {s: rng.randint(3, 4) for s in template.required}
        years = template.min_years + rng.randint(0, 2)
    elif difficulty is Difficulty.BORDERLINE:
        skills = {s: rng.randint(2, 3) for s in template.required[:-1]}
        years = max(1, template.min_years - 1)
    elif difficulty is Difficulty.WEAK:
        skills = {s: rng.randint(1, 2) for s in template.adjacent[:2]}
        years = rng.randint(1, 3)
    else:  # HARD_NEGATIVE
        # The trap: every keyword the job asked for is present, and none of them
        # at depth. Add a long record and a wall of adjacent technologies, and a
        # scorer that counts term overlap ranks this first. That is the point —
        # a benchmark a keyword baseline can pass is not measuring ranking.
        skills = {s: rng.randint(1, 2) for s in template.required}
        skills |= {s: rng.randint(3, 5) for s in template.preferred}
        skills |= {s: rng.randint(4, 5) for s in template.adjacent}
        years = template.min_years + rng.randint(5, 8)

    seniority = (
        Seniority.SENIOR if years >= 8 else Seniority.MID if years >= 4 else Seniority.JUNIOR
    )
    return CandidateSpec(
        candidate_id=f"syn_{template.template_id}_{index:05d}",
        experience_years=years,
        skills=skills,
        domains=[template.domain] if difficulty is not Difficulty.WEAK else ["Web"],
        roles=[f"{seniority.value.title()} Engineer"],
        seniority=seniority,
        resume=_render_resume(years, seniority, skills),
        template_id=f"{template.template_id}:{difficulty.value}",
    )


def _render_resume(years: int, seniority: Seniority, skills: dict[str, int]) -> str:
    """Structured truth rendered into prose. Never the source of the truth.

    Deliberately plain: phase 1 replaces this with a model, calibrated against
    the real CVs in the Djinni corpus so generated resumes read like real ones.
    """
    top = ", ".join(k for k, v in sorted(skills.items(), key=lambda kv: -kv[1])[:5])
    return (
        f"{seniority.value.title()} engineer with {years} years of experience. "
        f"Primary technologies: {top}."
    )


def generate_examples(
    count: int,
    seed: int = 0,
    candidates_per_example: int = 5,
) -> list[RankingExample]:
    """A deterministic dataset. The same seed gives the same examples."""
    rng = random.Random(seed)
    bands = [
        Difficulty.STRONG,
        Difficulty.HARD_NEGATIVE,
        Difficulty.GOOD,
        Difficulty.BORDERLINE,
        Difficulty.WEAK,
    ]

    examples = []
    for i in range(count):
        template = TEMPLATES[i % len(TEMPLATES)]
        job = JobSpec(
            job_id=f"syn_job_{i:05d}",
            title=template.title,
            level=Seniority.SENIOR,
            domain=template.domain,
            required_skills=list(template.required),
            preferred_skills=list(template.preferred),
            minimum_experience_years=template.min_years,
            description=(
                f"We are hiring a {template.title}. You will work on "
                f"{template.domain.lower()}."
            ),
            template_id=template.template_id,
        )

        chosen = bands[:candidates_per_example]
        candidates = [
            _candidate(rng, i * 100 + j, template, band) for j, band in enumerate(chosen)
        ]
        assessments = [_assess(job, c) for c in candidates]

        # The label comes from the ground truth, not from a judgement.
        ordering = [
            a.candidate_id
            for a in sorted(assessments, key=lambda a: a.match_score, reverse=True)
        ]

        examples.append(
            RankingExample(
                example_id=f"syn_{i:05d}",
                job=job,
                candidates=candidates,
                ordering=ordering,
                assessments=assessments,
                difficulty={c.candidate_id: b for c, b in zip(candidates, chosen)},
                quality=LabelQuality.GOLD,
                # Grouped splitting keys: an example must not be able to share a
                # template with one on the other side of the split.
                group_keys=[template.template_id, template.domain],
            )
        )
    return examples


__all__ = ["TEMPLATES", "RoleTemplate", "generate_examples", "true_score"]
