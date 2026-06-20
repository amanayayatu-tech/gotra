from __future__ import annotations

from pathlib import Path

import pytest

from gotra.judge_agent.temporal_replay import (
    POLICY_CANDIDATE,
    POLICY_CURRENT,
    TERMINAL_FUTURE_LEAK,
    TERMINAL_PASS,
    ReplayCase,
    audit_future_input,
    classify_replay,
    load_replay_cases,
    run_temporal_replay,
    visible_context,
)


FIXTURE = Path("tests/fixtures/judge_temporal_replay/golden_cases.json")


def test_temporal_replay_fixture_loads_visible_inputs_and_scoring_labels() -> None:
    cases = load_replay_cases(FIXTURE)

    assert len(cases) == 10
    first = cases[0]
    assert first.case_id == "meaning_clear_useful_evidence"
    assert first.visible["gate_type"] == "meaning"
    assert first.labels["expected_decision"] == "approve"
    assert "expected_decision" not in first.visible
    assert "risk_outcome" not in first.visible
    assert visible_context(first) == first.visible


def test_future_input_audit_catches_scoring_only_fields_in_visible_context() -> None:
    case = ReplayCase(
        case_id="bad_future_visible",
        gate_type="meaning",
        decision_date="2026-02-01",
        available_at="2026-02-01T09:00:00Z",
        visible={
            "gate_type": "meaning",
            "payload": {
                "prompt_text": "bad",
                "expected_decision": "approve",
            },
            "signals": {"risk_score": 0.1, "future_return": 0.12},
        },
        labels={
            "expected_decision": "approve",
            "risk_outcome": "safe",
            "valuable_evidence": True,
            "should_defer": False,
            "would_create_independent_feedback": True,
        },
    )

    audit = audit_future_input(case)
    assert audit["future_input_violation_count"] == 2
    assert audit["future_input_violation_keys"] == [
        "payload.expected_decision",
        "signals.future_return",
    ]
    with pytest.raises(ValueError, match="future/scoring-only fields"):
        visible_context(case)


def test_temporal_replay_metrics_and_verdict_are_deterministic() -> None:
    summary = run_temporal_replay(load_replay_cases(FIXTURE))
    current = summary["policy_results"][POLICY_CURRENT]["metrics"]
    candidate = summary["policy_results"][POLICY_CANDIDATE]["metrics"]

    assert summary["verdict"] == TERMINAL_PASS
    assert summary["future_input_violation_count"] == 0
    assert current["case_count"] == candidate["case_count"] == 10
    assert candidate["high_risk_false_pass_rate"] < current["high_risk_false_pass_rate"]
    assert candidate["useful_evidence_false_kill_rate"] <= current["useful_evidence_false_kill_rate"]
    assert candidate["defer_reasonableness_rate"] >= current["defer_reasonableness_rate"]
    assert candidate["over_defer_rate_on_safe_cases"] <= current["over_defer_rate_on_safe_cases"]
    assert candidate["brier_score"] <= current["brier_score"]
    assert candidate["decision_accuracy"] > current["decision_accuracy"]
    assert candidate["expected_feedback_substrate_yield"] == 3
    assert current["expected_feedback_substrate_yield"] == 3


def test_candidate_policy_rows_do_not_use_scoring_only_labels_for_visible_hashes() -> None:
    summary = run_temporal_replay(load_replay_cases(FIXTURE))
    rows = summary["policy_results"][POLICY_CANDIDATE]["rows"]

    assert rows
    for row in rows:
        assert row["visible_input_hash"]
        assert row["expected_decision"] in {"approve", "reject", "defer"}
        assert row["risk_outcome"] in {"safe", "high_risk", "uncertain"}


def test_confidence_calibration_bins_are_deterministic() -> None:
    summary = run_temporal_replay(load_replay_cases(FIXTURE))
    bins = summary["policy_results"][POLICY_CANDIDATE]["metrics"]["calibration_bins"]

    assert [item["bin"] for item in bins] == ["low", "mid", "high"]
    assert sum(item["count"] for item in bins) == 10
    assert all(item["accuracy"] is None or 0.0 <= item["accuracy"] <= 1.0 for item in bins)


def test_future_input_violation_forces_fail_status() -> None:
    current = {
        "high_risk_false_pass_rate": 0.5,
        "useful_evidence_false_kill_rate": 0.0,
        "defer_reasonableness_rate": 0.5,
        "over_defer_rate_on_safe_cases": 0.0,
        "brier_score": 0.2,
    }
    candidate = {
        "high_risk_false_pass_rate": 0.0,
        "useful_evidence_false_kill_rate": 0.0,
        "defer_reasonableness_rate": 1.0,
        "over_defer_rate_on_safe_cases": 0.0,
        "brier_score": 0.1,
    }

    assert (
        classify_replay(
            current=current,
            candidate=candidate,
            future_input_violation_count=1,
        )
        == TERMINAL_FUTURE_LEAK
    )
