from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness_v36
from scripts import baseline_v3_6s_actual_maturity_monitor as monitor


def test_monitor_reports_data_insufficient_without_capture_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    config = _monitor_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_6s_actual_maturity_monitor_no_capture",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = monitor.run_monitor(config)

    assert summary["status"] == monitor.STATUS_DATA_INSUFFICIENT
    assert summary["checked_capture_run_count"] == 0
    assert summary["capture_artifact_count"] == 0
    assert summary["next_stage_planning_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_monitor_reports_data_not_matured_for_all_immature_captures(
    tmp_path: Path,
) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_capture("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])
    config = _monitor_config(
        tmp_path,
        input_root=capture_dir,
        run_id="baseline_v3_6s_actual_maturity_monitor_immature",
        as_of="2026-07-19T00:00:00Z",
    )

    summary = monitor.run_monitor(config)

    assert summary["status"] == monitor.STATUS_DATA_NOT_MATURED
    assert summary["checked_capture_run_count"] == 1
    assert summary["not_matured_count"] == 1
    assert summary["matured_candidate_count"] == 0
    assert summary["next_check_after"] == "2026-07-21T00:00:00Z"
    assert "capture_horizons_not_matured" in summary["blocker_reasons"]


def test_monitor_reports_blocked_data_when_matured_price_is_missing(
    tmp_path: Path,
) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_capture("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])
    config = _monitor_config(
        tmp_path,
        input_root=capture_dir,
        run_id="baseline_v3_6s_actual_maturity_monitor_missing_price",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = monitor.run_monitor(config)

    assert summary["status"] == monitor.STATUS_BLOCKED_DATA
    assert summary["matured_candidate_count"] == 1
    assert summary["matured_price_available_count"] == 0
    assert summary["blocked_data_count"] == 1
    assert summary["resolver_path_eligible"] is False


def test_monitor_marks_resolver_path_eligible_when_matured_price_is_available(
    tmp_path: Path,
) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_capture("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    config = _monitor_config(
        tmp_path,
        input_root=capture_dir,
        run_id="baseline_v3_6s_actual_maturity_monitor_price_available",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = monitor.run_monitor(config)

    assert summary["status"] == monitor.STATUS_RESOLVER_PATH_ELIGIBLE
    assert summary["matured_candidate_count"] == 1
    assert summary["matured_price_available_count"] == 1
    assert summary["resolver_path_eligible"] is True
    assert summary["next_stage_planning_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False


def test_monitor_blocks_v3_7_when_readiness_is_not_ready(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_capture("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    readiness_path = _write_readiness_summary(
        tmp_path,
        status=readiness_v36.STATUS_DATA_NOT_MATURED,
    )
    config = _monitor_config(
        tmp_path,
        input_root=capture_dir,
        run_id="baseline_v3_6s_actual_maturity_monitor_readiness_not_ready",
        as_of="2026-07-21T00:00:00Z",
        readiness_summary_path=readiness_path,
    )

    summary = monitor.run_monitor(config)

    assert summary["readiness_status"] == readiness_v36.STATUS_DATA_NOT_MATURED
    assert summary["next_stage_planning_allowed"] is False
    assert summary["v3_7_verdict_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False
    assert "readiness_not_ready" in summary["blocker_reasons"]


def test_monitor_ready_only_allows_next_stage_planning_not_verdict_execution(
    tmp_path: Path,
) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_capture("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    readiness_path = _write_readiness_summary(tmp_path, status=readiness_v36.STATUS_READY)
    config = _monitor_config(
        tmp_path,
        input_root=capture_dir,
        run_id="baseline_v3_6s_actual_maturity_monitor_readiness_ready",
        as_of="2026-07-21T00:00:00Z",
        readiness_summary_path=readiness_path,
    )

    summary = monitor.run_monitor(config)

    assert summary["readiness_status"] == readiness_v36.STATUS_READY
    assert summary["next_stage_planning_allowed"] is True
    assert summary["v3_7_verdict_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False
    assert summary["status"] == monitor.STATUS_RESOLVER_PATH_ELIGIBLE


def _capture(
    ticker: str,
    decision_date: str,
    horizon_end_date: str,
    latest_visible_price_date: str,
) -> dict[str, object]:
    return {
        "schema": capture_v35a.CAPTURE_SCHEMA,
        "run_id": "baseline_v3_5a_forward_live_fixture",
        "capture_status": "captured",
        "arm": "full_gotra",
        "input_layer": "richer_research_packet",
        "ticker": ticker,
        "decision_timestamp_utc": f"{decision_date}T02:00:00Z",
        "decision_date_local": decision_date,
        "horizon_days": 30,
        "horizon_end_date": horizon_end_date,
        "future_outcome_status": "not_matured",
        "future_outcome_scoring_status": "NOT_MATURED",
        "backend": "local_mock",
        "prompt_hash": "fixture_prompt_hash",
        "latest_visible_price_date": latest_visible_price_date,
        "future_data_violation": False,
        "decision": {"direction": "long", "expected_change_pct": 3.0},
    }


def _write_capture_run(tmp_path: Path, artifacts: list[dict[str, object]]) -> Path:
    capture_dir = tmp_path / "capture_run"
    for artifact in artifacts:
        ticker = str(artifact["ticker"]).lower()
        decision_date = str(artifact["decision_date_local"])
        input_layer = str(artifact["input_layer"])
        path = (
            capture_dir
            / "captures"
            / str(artifact["arm"])
            / f"capture_{decision_date}_{ticker}_{input_layer}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return capture_dir


def _write_prices(price_dir: Path, ticker: str, rows: list[tuple[str, float]]) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {
                "date": row_date,
                "ticker": ticker,
                "adj_close": price,
                "source_url": "fixture",
                "evidence_unverified": False,
            }
            for row_date, price in rows
        ]
    )
    frame.to_csv(price_dir / f"{ticker}.csv", index=False)


def _write_readiness_summary(tmp_path: Path, *, status: str) -> Path:
    path = tmp_path / f"readiness_{status}.json"
    path.write_text(
        json.dumps(
            {
                "schema": readiness_v36.SUMMARY_SCHEMA,
                "readiness_run_id": "baseline_v3_6_forward_live_verdict_readiness_fixture",
                "status": status,
                "provider_or_backend_called": False,
                "codex_cli_called": False,
                "formal_lite_entered": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _monitor_config(
    root: Path,
    *,
    input_root: Path,
    run_id: str,
    as_of: str,
    readiness_summary_path: Path | None = None,
) -> monitor.MonitorConfig:
    return monitor.MonitorConfig(
        input_roots=(input_root,),
        monitor_run_id=run_id,
        as_of_timestamp_utc=monitor.parse_as_of_timestamp(as_of),
        price_dir=root / "prices",
        output_dir=root / "runs",
        readiness_summary_path=readiness_summary_path,
    )
