"""Build and cache the distributions that drive generation.

    python -m recruitgpt_research.sources.profile --categories C++ Python DevOps

Runs over the whole corpus with no model and no API key. The output is what
phase 1's generator samples from, and the `adjacent` list in it is the part that
matters — those are the skills a hard negative should have in depth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from recruitgpt_research.sources import djinni


def build(categories: list[str], out: Path) -> dict:
    dataset = djinni.load()
    vocabulary = djinni.mine_vocabulary(
        dataset["Long Description"], dataset["Primary Keyword"]
    )

    profiles = {}
    for category in categories:
        profile = djinni.skill_profile(dataset, category, vocabulary)
        if profile.postings == 0:
            print(f"  {category}: no postings with a marked requirements section — skipped")
            continue
        required = profile.required()
        adjacent = profile.adjacent()
        profiles[category] = {
            "postings": profile.postings,
            "required": [
                {"skill": s, "mentioned": round(profile.mention_rate[s], 3),
                 "required": round(profile.requirement_rate.get(s, 0.0), 3),
                 "ratio": round(profile.ratio(s), 3)}
                for s in required[:20]
            ],
            "adjacent": [
                {"skill": s, "mentioned": round(profile.mention_rate[s], 3),
                 "required": round(profile.requirement_rate.get(s, 0.0), 3),
                 "ratio": round(profile.ratio(s), 3)}
                for s in adjacent[:20]
            ],
        }
        print(f"  {category}: {profile.postings} postings, "
              f"{len(required)} required-ish, {len(adjacent)} adjacent")

    payload = {
        "dataset": djinni.DATASET,
        "vocabulary_size": len(vocabulary),
        "experience_bands": djinni.experience_bands(dataset),
        "category_mix": djinni.category_mix(dataset),
        "profiles": profiles,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile the Djinni corpus.")
    parser.add_argument("--categories", nargs="+", default=["C++", "Python", "DevOps"])
    parser.add_argument("--out", default="data/djinni_profile.json")
    args = parser.parse_args(argv)

    print(f"profiling {djinni.DATASET} — no model, no API key")
    payload = build(args.categories, Path(args.out))
    print(f"\nvocabulary: {payload['vocabulary_size']} skill-like terms")
    print(f"written to {args.out}")

    for category, profile in payload["profiles"].items():
        print(f"\n{category}")
        print("  required   ", ", ".join(r["skill"] for r in profile["required"][:8]))
        print("  adjacent   ", ", ".join(r["skill"] for r in profile["adjacent"][:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
