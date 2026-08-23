"""The parts of the pipeline that run without a GPU — which is most of it.

Training needs hardware. Everything that decides whether training would be
*correct* — the split, the prompt, the mask, the metrics — does not, and is
tested here.
"""

from __future__ import annotations

import json

import pytest
from recruitgpt import build_prompt, parse_ranking, render_target
from recruitgpt.schemas import Difficulty, LabelQuality

from recruitgpt_research.config import Config, Strategy
from recruitgpt_research.data.chat import keep_quality, to_chat
from recruitgpt_research.data.io import manifest, read_jsonl, write_jsonl
from recruitgpt_research.data.synthetic import generate_examples, true_score
from recruitgpt_research.evaluation.metrics import (
    ndcg_at_k,
    pairwise_accuracy,
    score_predictions,
)
from recruitgpt_research.evaluation.run import keyword_baseline, oracle
from recruitgpt_research.splits import grouped_split, leaked_groups


@pytest.fixture(scope="module")
def examples():
    return generate_examples(80, seed=0, candidates_per_example=5)


# ── generation ───────────────────────────────────────────────────────────


def test_generation_is_deterministic():
    """A dataset that changes between runs cannot be a frozen benchmark."""
    a = generate_examples(5, seed=7)
    b = generate_examples(5, seed=7)
    assert [e.ordering for e in a] == [e.ordering for e in b]
    assert a[0].candidates[0].skills == b[0].candidates[0].skills


def test_the_label_comes_from_ground_truth_not_a_judgement(examples):
    for ex in examples[:10]:
        scores = [true_score(ex.job, c) for c in ex.candidates]
        by_id = dict(zip([c.candidate_id for c in ex.candidates], scores))
        ordered = [by_id[cid] for cid in ex.ordering]
        assert ordered == sorted(ordered, reverse=True)


def test_a_specialist_outranks_a_longer_generalist(examples):
    """The behaviour the whole benchmark exists to measure."""
    checked = 0
    for ex in examples:
        hard = [c for c in ex.candidates if ex.difficulty.get(c.candidate_id) is Difficulty.HARD_NEGATIVE]
        strong = [c for c in ex.candidates if ex.difficulty.get(c.candidate_id) is Difficulty.STRONG]
        if not hard or not strong:
            continue
        checked += 1
        h, s = hard[0], strong[0]
        assert h.experience_years > s.experience_years, "the trap needs the longer record"
        assert ex.ordering.index(s.candidate_id) < ex.ordering.index(h.candidate_id)
    assert checked > 0


def test_the_hard_negative_names_every_required_skill(examples):
    """If it were missing keywords, a keyword scorer would filter it out and the
    example would not be hard at all."""
    for ex in examples[:20]:
        for c in ex.candidates:
            if ex.difficulty.get(c.candidate_id) is not Difficulty.HARD_NEGATIVE:
                continue
            assert set(ex.job.required_skills) <= set(c.skills)
            assert all(c.skills[s] <= 2 for s in ex.job.required_skills), "named, not mastered"


# ── splitting ────────────────────────────────────────────────────────────


def test_no_group_appears_on_two_sides(examples):
    """Random splitting would report memorisation as generalisation."""
    assert leaked_groups(grouped_split(examples, seed=0)) == set()


def test_every_side_gets_examples(examples):
    counts = grouped_split(examples, seed=0).counts()
    assert all(n > 0 for n in counts.values()), counts


def test_the_split_is_stable_when_data_is_added(examples):
    """A frozen test set has to stay frozen as the training set grows."""
    small = grouped_split(examples[:40], seed=0)
    large = grouped_split(examples, seed=0)
    small_test = {ex.example_id for ex in small.test}
    large_ids = {ex.example_id for ex in large.test}
    assert small_test <= large_ids


# ── prompt and target ────────────────────────────────────────────────────


def test_the_prompt_never_contains_a_real_candidate_id(examples):
    """Real ids in the prompt let the model memorise ids instead of ranking."""
    ex = examples[0]
    prompt = build_prompt(ex)
    for c in ex.candidates:
        assert c.candidate_id not in prompt.user


def test_the_target_orders_labels_the_way_the_truth_orders_ids(examples):
    ex = examples[0]
    prompt = build_prompt(ex)
    target = json.loads(render_target(ex, prompt))
    assert target["ranking"] == [prompt.id_to_label[cid] for cid in ex.ordering]


def test_a_target_round_trips_through_the_parser(examples):
    ex = examples[0]
    prompt = build_prompt(ex)
    ordering, assessments = parse_ranking(render_target(ex, prompt), prompt)
    assert ordering == ex.ordering
    assert len(assessments) == len(ex.candidates)


def test_the_parser_survives_a_base_model_wrapping_its_json(examples):
    """A baseline that loses on formatting would flatter the trained model."""
    ex = examples[0]
    prompt = build_prompt(ex)
    messy = f"Sure! Here is my ranking:\n```json\n{render_target(ex, prompt)}\n```\nHope that helps."
    ordering, _ = parse_ranking(messy, prompt)
    assert ordering == ex.ordering


def test_unparseable_output_yields_nothing_rather_than_raising(examples):
    prompt = build_prompt(examples[0])
    assert parse_ranking("I cannot help with that.", prompt) == ([], [])
    assert parse_ranking("", prompt) == ([], [])


def test_candidate_order_in_the_prompt_is_shuffled(examples):
    """Otherwise position leaks the answer and the model learns 'pick the first'."""
    ex = examples[0]
    layouts = {
        tuple(to_chat(ex, seed=s).prompt.label_to_id.values()) for s in range(6)
    }
    assert len(layouts) > 1


def test_quality_filtering(examples):
    ex = examples[0].model_copy(update={"quality": LabelQuality.AMBIGUOUS})
    assert keep_quality([ex], "silver") == []
    assert keep_quality([ex], "ambiguous") == [ex]


# ── metrics ──────────────────────────────────────────────────────────────


def test_pairwise_accuracy_counts_every_pair():
    assert pairwise_accuracy(["a", "b", "c"], ["a", "b", "c"]) == (3, 3)
    assert pairwise_accuracy(["a", "b", "c"], ["c", "b", "a"]) == (0, 3)


def test_a_missing_candidate_counts_as_wrong_not_skipped():
    """Ranking two of five and ignoring the rest is not doing the task."""
    assert pairwise_accuracy(["a", "b", "c"], ["a", "b"]) == (1, 3)


def test_ndcg_rewards_getting_the_top_right():
    assert ndcg_at_k(["a", "b", "c"], ["a", "b", "c"], 3) == 1.0
    assert ndcg_at_k(["a", "b", "c"], ["c", "b", "a"], 3) < 1.0


def test_an_empty_prediction_is_scored_not_dropped(examples):
    subset = examples[:4]
    metrics = score_predictions(subset, {})
    assert metrics.examples == 4
    assert metrics.pairwise_accuracy == 0.0
    assert metrics.parse_rate == 0.0


def test_the_oracle_scores_perfectly(examples):
    """If this ever fails, the harness is broken, not the model."""
    metrics = score_predictions(examples, oracle(examples))
    assert metrics.pairwise_accuracy == 1.0
    assert metrics.hard_pairwise_accuracy == 1.0


def test_the_keyword_baseline_fails_on_the_hard_pairs(examples):
    """A benchmark a term-overlap scorer can pass is not measuring ranking."""
    metrics = score_predictions(examples, keyword_baseline(examples))

    assert metrics.hard_pairwise_accuracy < 0.5
    assert metrics.hard_pairwise_accuracy < metrics.pairwise_accuracy, (
        "the hard pairs must be harder than the average pair"
    )


# ── io ───────────────────────────────────────────────────────────────────


def test_datasets_round_trip(tmp_path, examples):
    path = write_jsonl(examples[:5], tmp_path / "d.jsonl")
    loaded = read_jsonl(path)
    assert [e.example_id for e in loaded] == [e.example_id for e in examples[:5]]
    assert loaded[0].candidates[0].skills == examples[0].candidates[0].skills


def test_the_manifest_fingerprints_content(tmp_path, examples):
    a = write_jsonl(examples[:5], tmp_path / "a.jsonl")
    b = write_jsonl(examples[:5], tmp_path / "b.jsonl")
    c = write_jsonl(examples[:6], tmp_path / "c.jsonl")

    m = manifest({"a": a, "b": b, "c": c})
    assert m["a"]["sha256"] == m["b"]["sha256"]
    assert m["a"]["sha256"] != m["c"]["sha256"]
    assert m["c"]["examples"] == 6
