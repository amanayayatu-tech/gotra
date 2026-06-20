from __future__ import annotations

import json
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("summary_updates", "expected_reason"),
    [
        ({"status": "PROVIDER_PILOT_FAIL"}, "source_status_not_clean"),
        (
            {"deterministic_price_only_baseline_status": "REFERENCE_NEEDS_FIX"},
            "deterministic_reference_not_ready",
        ),
        ({"research_source_leak_count": 1}, "source_research_source_leak"),
        ({"feedback_source_leak_count": 1}, "source_feedback_source_leak"),
    ],
)
def test_source_audit_failures_downgrade_verdict(
    tmp_path: Path,
    summary_updates: dict[str, object],
    expected_reason: str,
) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[
            _pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0),
            _pair("MSFT", "2024-04-02", det_mse=9.0, full_mse=1.0),
        ],
        summary_updates=summary_updates,
    )

    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id=f"deterministic_price_only_vs_full_gotra_verdict_test_{expected_reason}",
            bootstrap_reps=100,
            bootstrap_seed=7,
            min_paired_points=2,
        )
    )

    assert summary["verdict"] == verdict.VERDICT_DATA_INSUFFICIENT
    assert summary["verdict_reason"] == "source_audit_blocked"
    assert expected_reason in summary["source_audit_blocking_reasons"]


def test_existing_output_run_id_blocks_without_overwrite(tmp_path: Path) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[_pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0)],
    )
    output_dir = tmp_path / "out"
    run_id = "deterministic_price_only_vs_full_gotra_verdict_test_existing"
    run_root = output_dir / run_id
    run_root.mkdir(parents=True)
    existing_summary = {"status": "source_artifact_must_not_be_overwritten"}
    (run_root / "summary.json").write_text(json.dumps(existing_summary), encoding="utf-8")

    summary = verdict.run_verdict(
        verdict.VerdictConfig(source_run_dir=source_run, output_dir=output_dir, run_id=run_id)
    )

    assert summary["status"] == verdict.STATUS_BLOCKED_RUN_ID_EXISTS
    assert summary["artifact_write_blocked"] is True
    assert json.loads((run_root / "summary.json").read_text(encoding="utf-8")) == existing_summary
    assert not (run_root / "pairs.json").exists()
    assert (
        verdict.main(
            [
                "--source-run-dir",
                str(source_run),
                "--output-dir",
                str(output_dir),
                "--run-id",
                run_id,
            ]
        )
        == 1
    )


def test_duplicate_deterministic_reference_key_blocks_verdict(tmp_path: Path) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[
            _pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0),
            _pair("MSFT", "2024-04-02", det_mse=9.0, full_mse=1.0),
        ],
    )
    source = source_run / "deterministic_price_only_baseline" / "reference_2024-04-02_AAPL.json"
    duplicate = source_run / "deterministic_price_only_baseline" / "reference_2024-04-02_AAPL_copy.json"
    duplicate.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id="deterministic_price_only_vs_full_gotra_verdict_test_duplicate_key",
            bootstrap_reps=100,
            bootstrap_seed=7,
            min_paired_points=2,
        )
    )

    assert summary["verdict"] == verdict.VERDICT_DATA_INSUFFICIENT
    assert summary["verdict_reason"] == "duplicate_deterministic_reference_keys"
    assert summary["paired_count"] == 2
    assert summary["duplicate_deterministic_reference_key_count"] == 1


@pytest.mark.parametrize(
    ("deterministic_updates", "full_updates", "expected_reason"),
    [
        ({"baseline": "not_price_only"}, None, "deterministic_identity_mismatch"),
        (None, {"arm": "ksana_real_research"}, "full_gotra_identity_mismatch"),
        (None, {"input_layer": "price_only_packet"}, "missing_full_gotra_primary_input_layer"),
        (None, {"ticker": "MSFT"}, "missing_full_gotra_primary_input_layer"),
    ],
)
def test_artifact_identity_mismatches_do_not_enter_pairs(
    tmp_path: Path,
    deterministic_updates: dict[str, object] | None,
    full_updates: dict[str, object] | None,
    expected_reason: str,
) -> None:
    source_run = _write_source_run(
        tmp_path,
        pairs=[_pair("AAPL", "2024-04-02", det_mse=9.0, full_mse=1.0)],
        deterministic_updates=deterministic_updates,
        full_updates=full_updates,
    )

    summary = verdict.run_verdict(
        verdict.VerdictConfig(
            source_run_dir=source_run,
            output_dir=tmp_path / "out",
            run_id=f"deterministic_price_only_vs_full_gotra_verdict_test_{expected_reason}",
            min_paired_points=1,
        )
    )

    assert summary["paired_count"] == 0
    assert summary["excluded_reason_counts"][expected_reason] == 1


def test_full_gotra_identity_helper_flags_mismatched_key() -> None:
    full = {
        "schema": "gotra.baseline_v3.four_arm_step.v1",
        "arm": "full_gotra",
        "input_layer": verdict.DEFAULT_PRIMARY_INPUT_LAYER,
        "ticker": "MSFT",
        "decision_date": "2024-04-02",
        "horizon_days": 30,
    }

    assert (
        verdict.full_gotra_identity_reason(
            full,
            expected_ticker="AAPL",
            expected_decision_date="2024-04-02",
            expected_horizon_days=30,
            expected_input_layer=verdict.DEFAULT_PRIMARY_INPUT_LAYER,
        )
        == "full_gotra_key_mismatch"
    )


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
    summary_updates: dict[str, object] | None = None,
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
    summary.update(summary_updates or {})
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
            "llm_used": False,
            "provider_or_backend_called": False,
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
