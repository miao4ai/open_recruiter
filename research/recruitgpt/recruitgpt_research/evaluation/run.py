"""Run a benchmark and write the three files a result consists of.

    python -m recruitgpt_research.evaluation.run --config configs/debug.yaml --baseline oracle

`metrics.json` is the summary, `predictions.jsonl` is what the model actually
said, and `error_analysis.jsonl` is what it got wrong — which is the input to
phase 4's hard-negative mining, not just a debugging aid.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from recruitgpt_research.config import Config
from recruitgpt_research.data.io import read_jsonl
from recruitgpt_research.evaluation.metrics import score_predictions
from recruitgpt_research.runs import Run
from recruitgpt.schemas import Difficulty, RankingExample


def oracle(examples: list[RankingExample]) -> dict[str, list[str]]:
    """Perfect predictions. Checks the harness, not a model."""
    return {ex.example_id: list(ex.ordering) for ex in examples}


def keyword_baseline(examples: list[RankingExample]) -> dict[str, list[str]]:
    """Rank by how many job skills the candidate names at all.

    The floor every trained model must clear. It is also the behaviour the hard
    negatives are designed to punish — long tenure and a wall of adjacent
    keywords score well here and are wrong.
    """
    out = {}
    for ex in examples:
        wanted = {s.lower() for s in ex.job.required_skills + ex.job.preferred_skills}
        ranked = sorted(
            ex.candidates,
            key=lambda c: (
                len({s.lower() for s in c.skills} & wanted),
                c.experience_years,
            ),
            reverse=True,
        )
        out[ex.example_id] = [c.candidate_id for c in ranked]
    return out


BASELINES = {"oracle": oracle, "keyword": keyword_baseline}


def error_rows(
    examples: list[RankingExample], predictions: dict[str, list[str]]
) -> list[dict]:
    """Every pair the prediction got backwards, with its difficulty band."""
    rows = []
    for ex in examples:
        predicted = predictions.get(ex.example_id) or []
        position = {cid: i for i, cid in enumerate(predicted)}
        for better, worse in ex.pairs():
            wrong = (
                better not in position
                or worse not in position
                or position[better] > position[worse]
            )
            if not wrong:
                continue
            rows.append(
                {
                    "example_id": ex.example_id,
                    "job_title": ex.job.title,
                    "should_rank_higher": better,
                    "ranked_higher_instead": worse,
                    "difficulty_higher": (ex.difficulty.get(better) or Difficulty.GOOD).value,
                    "difficulty_lower": (ex.difficulty.get(worse) or Difficulty.GOOD).value,
                    "involves_hard_negative": Difficulty.HARD_NEGATIVE
                    in (ex.difficulty.get(better), ex.difficulty.get(worse)),
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RecruitBench.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--split", default="test", choices=["validation", "test"])
    parser.add_argument("--baseline", default="keyword", choices=sorted(BASELINES))
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    path = Path(config.data.train_path).parent / f"{args.split}.jsonl"
    examples = read_jsonl(path)

    predictions = BASELINES[args.baseline](examples)
    metrics = score_predictions(examples, predictions)

    run = Run(config)
    run.record_config()
    run.record_environment()
    run.record_metrics({"baseline": args.baseline, "split": args.split, **metrics.to_dict()})
    run.record_predictions(
        [{"example_id": k, "ranking": v} for k, v in predictions.items()]
    )
    errors = error_rows(examples, predictions)
    run.record_errors(errors)

    print(json.dumps({"baseline": args.baseline, **metrics.to_dict()}, indent=2))
    print(f"\n{len(errors)} incorrect pairs -> {run.dir / 'error_analysis.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
