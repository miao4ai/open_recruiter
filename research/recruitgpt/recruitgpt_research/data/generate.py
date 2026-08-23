"""Generate a dataset and split it.

    python -m recruitgpt_research.data.generate --config configs/debug.yaml --count 40

Phase 0 uses the deterministic template generator, so this runs offline with no
API key. Phase 1 swaps the content for LLM generation seeded from the real
Djinni distributions; the schema, the split, and this entry point do not change.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from recruitgpt_research.config import Config
from recruitgpt_research.data.io import write_jsonl
from recruitgpt_research.data.synthetic import generate_examples
from recruitgpt_research.splits import grouped_split, leaked_groups


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a RecruitGPT dataset.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--count", type=int, default=40, help="Examples to generate")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    out = Path(config.data.train_path).parent

    examples = generate_examples(
        args.count, seed=args.seed, candidates_per_example=config.data.max_candidates
    )
    split = grouped_split(examples, seed=args.seed)

    leaked = leaked_groups(split)
    if leaked:
        # Never write a dataset that would report memorisation as generalisation.
        raise SystemExit(f"Split leaked group(s) across sides: {sorted(leaked)}")

    write_jsonl(split.train, out / "train.jsonl")
    write_jsonl(split.validation, out / "validation.jsonl")
    write_jsonl(split.test, out / "test.jsonl")

    counts = split.counts()
    print(json.dumps({"written_to": str(out), **counts}, indent=2))

    empty = [name for name, n in counts.items() if n == 0]
    if empty:
        print(
            f"\nEmpty: {', '.join(empty)}. Grouped splitting is coarse by design — related "
            "templates travel together, so a whole group can land on one side. The fix is "
            "more templates across more domains, not a looser split."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
