from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_operating_loop as operating_loop


def test_operating_loop_summarizes_matured_not_matured_and_blocked_data(
    tmp_path: Path,
) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [
            _artifact("AAPL", "2026-06-20", "2026-07-20", "2026-06-19"),
            _artifact("MSFT", "2026-06-20", "2026-07-20", "2026-06-19"),
            _artifact("NVDA", "2026-07-01", "2026-07-31", "2026-06-30"),
        ],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0), ("2026-07-20", 110.0)])
    _write_prices(tmp_path / "prices", "MSFT", [("2026-06-19", 200.0)])
    _write_prices(tmp_path / "prices", "NVDA", [("2026-06-30", 300.0)])
    config = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_mixed",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = operating_loop.run_operating_loop(config)

    assert summary["status"] == operating_loop.STATUS_PASS
    assert summary["outcome_scoring_status"] == operating_loop.OUTCOME_STATUS_RESOLVED_AVAILABLE
    assert summary["capture_count"] == 3
    assert summary["resolved_count"] == 1
    assert summary["blocked_data_count"] == 1
    assert summary["not_matured_count"] == 1
    assert summary["blocked_future_data_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_operating_loop_reports_no_matured_outcomes_without_verdict(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [
            _artifact("AAPL", "2026-06-20", "2026-07-20", "2026-06-19"),
            _artifact("MSFT", "2026-06-20", "2026-07-20", "2026-06-19"),
        ],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])
    _write_prices(tmp_path / "prices", "MSFT", [("2026-06-19", 200.0)])
    config = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_no_matured",
        as_of="2026-07-19T00:00:00Z",
    )

    summary = operating_loop.run_operating_loop(config)

    assert summary["status"] == operating_loop.STATUS_PASS
    assert summary["outcome_scoring_status"] == operating_loop.OUTCOME_STATUS_NO_MATURED
    assert summary["resolved_count"] == 0
    assert summary["not_matured_count"] == 2
    assert summary["outcome_scoring_status"] != operating_loop.OUTCOME_STATUS_RESOLVED_AVAILABLE


def test_operating_loop_is_idempotent_for_existing_resolved_outcomes(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_artifact("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0), ("2026-07-20", 110.0)])
    first = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_first",
        as_of="2026-07-21T00:00:00Z",
    )
    second = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_second",
        as_of="2026-07-22T00:00:00Z",
    )

    first_summary = operating_loop.run_operating_loop(first)
    second_summary = operating_loop.run_operating_loop(second)

    assert first_summary["resolved_count"] == 1
    assert second_summary["status"] == operating_loop.STATUS_PASS
    assert second_summary["resolved_count"] == 0
    assert second_summary["duplicate_existing_count"] == 1
    second_scheduler_root = (
        operating_loop.scheduler_state_dir(second)
        / operating_loop.scheduler_run_id_for(second)
    )
    assert not list(second_scheduler_root.glob("resolver_outputs/**/outcomes/resolved/*.json"))


def test_operating_loop_provenance_links_capture_scheduler_resolver_and_outcome(
    tmp_path: Path,
) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_artifact("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0), ("2026-07-20", 90.0)])
    config = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_provenance",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = operating_loop.run_operating_loop(config)
    link = summary["provenance_links"][0]

    assert summary["provenance_link_count"] == 1
    assert link["provenance_ok"] is True
    assert Path(link["source_artifact_path"]).exists()
    assert Path(link["scheduler_summary_path"]).exists()
    assert Path(link["outcome_artifact_path"]).exists()
    assert link["scheduler_run_id"] == summary["scheduler_run_id"]
    assert link["resolver_run_id"] in summary["resolver_run_ids"]
    assert link["audit_event_status"] == "not_connected"
    assert summary["audit_event_count"] == 0


def test_operating_loop_blocks_source_future_data(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [
            _artifact(
                "AAPL",
                "2026-06-20",
                "2026-07-20",
                "2026-06-19",
                future_data_violation=True,
            )
        ],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0), ("2026-07-20", 110.0)])
    config = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_source_future",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = operating_loop.run_operating_loop(config)

    assert summary["status"] == operating_loop.STATUS_BLOCKED_SOURCE_FUTURE_DATA
    assert summary["outcome_scoring_status"] == operating_loop.OUTCOME_STATUS_SOURCE_FUTURE_DATA
    assert summary["blocked_future_data_count"] == 1
    assert summary["future_data_violation_count"] == 1


def test_operating_loop_empty_capture_grid_fails_without_verdict(tmp_path: Path) -> None:
    capture_dir = tmp_path / "capture_run"
    (capture_dir / "captures").mkdir(parents=True)
    config = _operating_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5d_operating_loop_empty",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = operating_loop.run_operating_loop(config)

    assert summary["status"] == operating_loop.STATUS_FAIL
    assert summary["outcome_scoring_status"] == operating_loop.OUTCOME_STATUS_NO_CAPTURE_ARTIFACTS
    assert summary["capture_count"] == 0
    assert summary["provider_or_backend_called"] is False


def test_operating_loop_run_id_collision_returns_nonzero_cli(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_artifact("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    run_id = "baseline_v3_5d_operating_loop_existing"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")

    code = operating_loop.main(
        [
            "--capture-run-dir",
            str(capture_dir),
            "--operating-loop-run-id",
            run_id,
            "--as-of-timestamp-utc",
            "2026-07-21T00:00:00Z",
            "--price-dir",
            str(tmp_path / "prices"),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert code == 1


def test_operating_loop_no_matured_cli_success(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        [_artifact("AAPL", "2026-06-20", "2026-07-20", "2026-06-19")],
    )
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])

    code = operating_loop.main(
        [
            "--capture-run-dir",
            str(capture_dir),
            "--operating-loop-run-id",
            "baseline_v3_5d_operating_loop_no_matured_cli",
            "--as-of-timestamp-utc",
            "2026-07-19T00:00:00Z",
            "--price-dir",
            str(tmp_path / "prices"),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert code == 0


def _artifact(
    ticker: str,
    decision_date: str,
    horizon_end_date: str,
    latest_visible_price_date: str,
    *,
    future_data_violation: bool = False,
) -> dict[str, object]:
    return {
        "schema": capture_v35a.CAPTURE_SCHEMA,
        "run_id": "baseline_v3_5a_forward_live_fixture",
        "capture_status": "captured",
        "arm": "direct_llm",
        "input_layer": "price_only_packet",
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
        "future_data_violation": future_data_violation,
        "decision": {"direction": "long"},
    }


def _write_capture_run(tmp_path: Path, artifacts: list[dict[str, object]]) -> Path:
    capture_dir = tmp_path / "capture_run"
    for artifact in artifacts:
        ticker = str(artifact["ticker"])
        decision_date = str(artifact["decision_date_local"])
        path = (
            capture_dir
            / "captures"
            / "direct_llm"
            / f"capture_{decision_date}_{ticker.lower()}_price_only_packet.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
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


def _operating_config(
    root: Path,
    *,
    capture_dir: Path,
    run_id: str,
    as_of: str,
) -> operating_loop.OperatingLoopConfig:
    return operating_loop.OperatingLoopConfig(
        capture_run_dir=capture_dir,
        operating_loop_run_id=run_id,
        as_of_timestamp_utc=operating_loop.parse_as_of_timestamp(as_of),
        price_dir=root / "prices",
        output_dir=root / "runs",
    )
