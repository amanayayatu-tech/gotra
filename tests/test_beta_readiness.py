from __future__ import annotations

import pytest

from gotra.beta_readiness import build_beta_metrics_template, build_beta_status, load_beta_universe


def test_beta_universe_is_ready_but_not_started():
    universe = load_beta_universe()

    assert universe["beta_clock_started"] is False
    assert universe["paid_subscription_enabled"] is False
    assert 10 <= len(universe["universe"]) <= 20
    assert all(item["review_windows"] == [1, 7, 30, 90] for item in universe["universe"])


def test_beta_status_and_metrics_do_not_claim_launch_or_performance():
    universe = load_beta_universe()

    status = build_beta_status(universe, generated_at="2026-07-06T00:00:00Z")
    metrics = build_beta_metrics_template(universe, generated_at="2026-07-06T00:00:00Z")

    assert status["schema"] == "gotra.launch.beta_status.v1"
    assert status["beta_state"] == "ready_not_started"
    assert status["beta_clock_started"] is False
    assert status["beta_complete"] is False
    assert status["boundary"]["not_investment_advice"] is True
    assert status["boundary"]["launch_ready"] is False

    assert metrics["schema"] == "gotra.launch.beta_metrics.v1"
    assert metrics["elapsed_days"] == 0
    assert metrics["required_days"] == 30
    assert metrics["launch_gate_eligible"] is False
    assert metrics["boundary"]["no_performance_proof"] is True


def test_beta_universe_rejects_started_clock():
    universe = load_beta_universe()
    universe["beta_clock_started"] = True

    with pytest.raises(ValueError, match="beta_clock_must_not_be_started"):
        build_beta_status(universe)
