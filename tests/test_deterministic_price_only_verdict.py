from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_deterministic_price_only_verdict as verdict


def test_full_gotra_better_verdict_when_mse_ci_positive(tmp_path: Path) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[
            _pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0),
            _pair("AAPL", "2024-05-02", det_mse=16.0, full_mse=4.0),
            _pair("MSFT", "2024-04-02", det_mse=25.0, full_mse=9.0),
            _pair("MSFT", "2024-05-02", det_mse=36.0, full_mse=16.0),
        ],
    )
    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id="deterministic_price_only_vs_full_gotra_verdict_test_better",
            bootstrap_reps=200,
            bootstrap_seed=7,
            min_paired_points=2,
        )
    )

    assert summary["verdict"] == verdict.VERDICT_FULL_GOTRA_BETTER
    assert summary["paired_count"] == 4
    assert summary["cluster_count"] == 2
    assert summary["future_data_violation_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["direct_llm_caveat"].startswith("direct_llm is")


def test_data_insufficient_when_primary_full_gotra_missing(tmp_path: Path) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[_pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0)],
        omit_full=True,
    )

    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id="deterministic_price_only_vs_full_gotra_verdict_test_insufficient",
            min_paired_points=1,
        )
    )

    assert summary["verdict"] == verdict.VERDICT_DATA_INSUFFICIENT
    assert summary["paired_count"] == 0
    assert summary["excluded_reason_counts"]["missing_full_gotra_primary_input_layer"] == 1


def test_future_data_violations_force_data_insufficient(tmp_path: Path) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[_pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0)],
        deterministic_updates={"future_data_violation": True},
    )

    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id="deterministic_price_only_vs_full_gotra_verdict_test_future",
            min_paired_points=1,
        )
    )

    assert summary["verdict"] == verdict.VERDICT_DATA_INSUFFICIENT
    assert summary["future_data_violation_count"] == 1
    assert summary["excluded_reason_counts"]["deterministic_future_data_violation"] == 1


def test_outcome_mismatch_is_excluded(tmp_path: Path) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[_pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0)],
        full_updates={"actual_change_pct": -3.0, "actual_direction": "avoid"},
    )

    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id="deterministic_price_only_vs_full_gotra_verdict_test_mismatch",
            min_paired_points=1,
        )
    )

    assert summary["paired_count"] == 0
    assert summary["excluded_reason_counts"]["outcome_mismatch"] == 1


def _pair(ticker: str, decision_date: str, *, det_mse: float, full_mse: float) -> dict[str, object]:
    return {
        "ticker": ticker,
        "decision_date": decision_date,
        "det_mse": det_mse,
        "full_mse": full_mse,
    }


def _write_source_run(
    tmp_path: Path,
    *,
    pairs: list[dict[str, object]],
    omit_full: bool = False,
    deterministic_updates: dict[str, object] | None = None,
    full_updates: dict[str, object] | None = None,
) -> Path:
    run = tmp_path / "source_run"
    (run / "deterministic_price_only_baseline").mkdir(parents=True)
    (run / "full_gotra").mkdir(parents=True)
    summary = {
        "status": "PROVIDER_PILOT_PASS",
        "provider": "codex_cli_llm_backend",
        "backend_name": "codex_cli_llm_backend",
        "expected_steps": len(pairs) * 8,
        "scored_step_count": len(pairs) * 8,
        "paired_coverage": 1.0,
        "future_data_violation_count": 0,
        "research_source_leak_count": 0,
        "feedback_source_leak_count": 0,
        "deterministic_price_only_baseline_status": "REFERENCE_READY",
        "deterministic_price_only_baseline_count": len(pairs),
        "clean_historical_reference_status": "PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE",
    }
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    for item in pairs:
        ticker = str(item["ticker"])
        decision_date = str(item["decision_date"])
        actual_change = 4.0
        det = {
            "schema": "gotra.baseline_v3_4b.deterministic_price_only_reference.v1",
            "run_id": "source_run",
            "status": "scored",
            "baseline": "deterministic_price_only_baseline",
            "ticker": ticker,
            "decision_date": decision_date,
            "horizon_days": 30,
            "actual_change_pct": actual_change,
            "actual_direction": "long",
            "direction_hit": False,
            "mse": item["det_mse"],
            "mae": 3.0,
            "policy_a_return_pct": 0.0,
            "future_data_violation": False,
        }
        det.update(deterministic_updates or {})
        (run / "deterministic_price_only_baseline" / f"reference_{decision_date}_{ticker}.json").write_text(
            json.dumps(det),
            encoding="utf-8",
        )
        if omit_full:
            continue
        full = {
            "schema": "gotra.baseline_v3.four_arm_step.v1",
            "run_id": "source_run",
            "status": "scored",
            "arm": "full_gotra",
            "input_layer": verdict.DEFAULT_PRIMARY_INPUT_LAYER,
            "ticker": ticker,
            "decision_date": decision_date,
            "horizon_days": 30,
            "scoring_segment": "scored",
            "actual_change_pct": actual_change,
            "actual_direction": "long",
            "direction_hit": True,
            "mse": item["full_mse"],
            "mae": 1.0,
            "policy_a_return_pct": 4.0,
            "future_data_violation": False,
            "research_source_leak": False,
            "feedback_source_leak": False,
        }
        full.update(full_updates or {})
        (run / "full_gotra" / f"step_{decision_date}_{ticker}_richer_research_packet.json").write_text(
            json.dumps(full),
            encoding="utf-8",
        )
    return run
