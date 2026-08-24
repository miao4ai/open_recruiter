"""Cost accounting.

The point of measuring rather than estimating is that the number decides how
large the real dataset gets. A meter that quietly under-reports is worse than no
meter, because the decision still gets made.
"""

from __future__ import annotations

import json

import pytest

from recruitgpt_research.cost import BudgetExceeded, Call, CostMeter, Price

PRICES = {
    "claude": Price(input=3.0, output=15.0, cached_input=0.3),
    "gpt": Price(input=2.5, output=10.0),
}


def usage(prompt=1000, completion=500, cached=0):
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cache_read_input_tokens": cached,
    }


@pytest.fixture
def meter():
    return CostMeter(prices=PRICES)


# ── reading usage ────────────────────────────────────────────────────────


def test_counts_come_from_the_provider_not_a_tokenizer(meter):
    """A local tokenizer disagreeing by a few percent compounds over 100k calls."""
    call = meter.record("jd_render", "claude", usage(prompt=1234, completion=567))
    assert call.input_tokens == 1234
    assert call.output_tokens == 567


def test_usage_objects_are_read_as_well_as_dicts(meter):
    class Usage:
        prompt_tokens = 100
        completion_tokens = 50
        cache_read_input_tokens = 20

    call = meter.record("teacher_a", "gpt", Usage())
    assert (call.input_tokens, call.output_tokens, call.cached_tokens) == (100, 50, 20)


def test_alternative_field_names_are_understood(meter):
    call = meter.record("x", "gpt", {"input_tokens": 10, "output_tokens": 5})
    assert (call.input_tokens, call.output_tokens) == (10, 5)


def test_a_usage_object_with_nothing_useful_records_zero(meter):
    call = meter.record("x", "gpt", object())
    assert call.input_tokens == 0


# ── pricing ──────────────────────────────────────────────────────────────


def test_cost_is_input_plus_output_per_million():
    call = Call("s", "claude", input_tokens=1_000_000, output_tokens=1_000_000)
    assert call.cost(PRICES["claude"]) == pytest.approx(18.0)


def test_cached_input_is_billed_at_the_cached_rate():
    """Counted separately, or caching credits the wrong stage."""
    call = Call("s", "claude", input_tokens=1_000_000, output_tokens=0, cached_tokens=900_000)
    # 100k fresh at 3.0 + 900k cached at 0.3
    assert call.cost(PRICES["claude"]) == pytest.approx(0.3 + 0.27)


def test_an_unpriced_model_is_an_error_not_a_zero(meter):
    """A run reporting a cost that excludes one of its models is worse than one
    that refuses to report."""
    meter.record("s", "mystery-model", usage())
    with pytest.raises(KeyError, match="No price for"):
        _ = meter.spent


# ── budget ───────────────────────────────────────────────────────────────


def test_the_budget_stops_the_run():
    meter = CostMeter(prices=PRICES, budget_usd=0.05)
    for _ in range(4):
        meter.record("gen", "claude", usage(prompt=1_000_000, completion=0))

    with pytest.raises(BudgetExceeded) as exc:
        meter.check()
    assert exc.value.spent >= 0.05
    assert exc.value.limit == 0.05


def test_a_run_under_budget_carries_on():
    meter = CostMeter(prices=PRICES, budget_usd=100.0)
    meter.record("gen", "claude", usage())
    meter.check()
    assert meter.remaining() == pytest.approx(100.0 - meter.spent)


def test_no_budget_means_no_cap(meter):
    meter.record("gen", "claude", usage(prompt=10_000_000))
    meter.check()
    assert meter.remaining() is None


def test_the_budget_can_be_checked_at_the_call_site():
    meter = CostMeter(prices=PRICES, budget_usd=0.001)
    with pytest.raises(BudgetExceeded):
        meter.record("gen", "claude", usage(prompt=1_000_000), check_budget=True)


# ── the report ───────────────────────────────────────────────────────────


def test_the_report_says_where_the_money_went(meter):
    for _ in range(10):
        meter.record("resume_render", "gpt", usage(prompt=300, completion=500))
    for _ in range(2):
        meter.record("teacher_a", "claude", usage(prompt=20_000, completion=2_000))

    report = meter.report(examples=2)
    stages = list(report["by_stage"])

    assert stages[0] == "teacher_a", "the largest stage is reported first"
    assert report["by_stage"]["teacher_a"]["calls"] == 2
    assert report["by_stage"]["resume_render"]["calls"] == 10
    assert report["cost_per_example_usd"] > 0


def test_extrapolation_answers_the_question_phase_one_exists_for(meter):
    for _ in range(10):
        meter.record("gen", "claude", usage())

    report = meter.report(examples=10, scale_to=1000)

    assert report["extrapolation"]["examples"] == 1000
    assert report["extrapolation"]["estimated_usd"] == pytest.approx(
        report["total_cost_usd"] * 100, rel=0.01
    )
    assert "superlinear" in report["extrapolation"]["note"]


def test_the_prices_used_are_recorded_with_the_totals(meter):
    """A run from three months ago has to remain explicable."""
    meter.record("gen", "claude", usage())
    assert meter.report(examples=1)["prices_used"]["claude"]["input"] == 3.0


def test_the_report_is_written_as_json(tmp_path, meter):
    meter.record("gen", "claude", usage())
    path = meter.write(tmp_path / "cost_report.json", examples=1, scale_to=100)

    payload = json.loads(path.read_text())
    assert payload["examples"] == 1
    assert "extrapolation" in payload


def test_an_empty_run_reports_zero_rather_than_dividing_by_zero(meter):
    report = meter.report(examples=0, scale_to=100)
    assert report["cost_per_example_usd"] == 0.0
    assert report["extrapolation"]["estimated_usd"] == 0.0
