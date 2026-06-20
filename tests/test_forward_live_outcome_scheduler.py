from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver
from scripts import baseline_v3_5_forward_live_outcome_scheduler as scheduler


def test_scheduler_keeps_immature_decision_not_matured(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0), ("2026-07-20", 110.0)])
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_immature",
        as_of="2026-07-19T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)
    record = _only_scheduler_record(tmp_path, config.scheduler_run_id, resolver.STATUS_NOT_MATURED)

    assert summary["status"] == scheduler.STATUS_PASS
    assert summary["scanned_decision_count"] == 1
    assert summary["not_matured_count"] == 1
    assert record["scheduler_run_id"] == config.scheduler_run_id
    assert record["outcome_price"] is None
    assert record["actual_change_pct"] is None


def test_scheduler_resolves_matured_decision(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_resolved",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)
    record = _only_scheduler_record(tmp_path, config.scheduler_run_id, resolver.STATUS_RESOLVED)

    assert summary["status"] == scheduler.STATUS_PASS
    assert summary["resolved_count"] == 1
    assert record["outcome_price_date"] == "2026-07-20"
    assert record["actual_direction"] == "long"
    assert record["provenance"]["scheduler_run_id"] == config.scheduler_run_id


def test_scheduler_blocks_matured_decision_with_missing_price(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_blocked_data",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)
    record = _only_scheduler_record(tmp_path, config.scheduler_run_id, resolver.STATUS_BLOCKED_DATA)

    assert summary["status"] == scheduler.STATUS_PASS
    assert summary["blocked_data_count"] == 1
    assert record["outcome_price"] is None
    assert record["actual_direction"] is None


def test_scheduler_skips_existing_resolved_outcome_idempotently(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    first = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_first_resolved",
        as_of="2026-07-21T00:00:00Z",
    )
    second = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_second_idempotent",
        as_of="2026-07-22T00:00:00Z",
    )

    first_summary = scheduler.run_scheduler(first)
    second_summary = scheduler.run_scheduler(second)

    assert first_summary["resolved_count"] == 1
    assert second_summary["status"] == scheduler.STATUS_PASS
    assert second_summary["resolved_count"] == 0
    assert second_summary["duplicate_or_existing_outcome_count"] == 1
    second_root = tmp_path / "runs" / second.scheduler_run_id
    assert not list(second_root.glob("resolver_outputs/**/outcomes/resolved/*.json"))


def test_scheduler_blocks_and_counts_source_future_data(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        ticker="AAPL",
        artifact_updates={"future_data_violation": True},
    )
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_source_future",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)
    record = _only_scheduler_record(
        tmp_path,
        config.scheduler_run_id,
        resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA,
    )

    assert summary["status"] == scheduler.STATUS_FAIL
    assert summary["blocked_future_data_count"] == 1
    assert summary["future_data_violation_count"] == 1
    assert record["source_future_data_violation"] is True
    assert record["actual_change_pct"] is None


def test_scheduler_preserves_same_day_daily_close_visibility(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 110.0)],
    )
    same_day = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_same_day_close",
        as_of="2026-07-20T00:00:00Z",
    )
    next_day = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_next_day_close",
        as_of="2026-07-21T00:00:00Z",
    )

    same_day_summary = scheduler.run_scheduler(same_day)
    same_day_record = _only_scheduler_record(
        tmp_path,
        same_day.scheduler_run_id,
        resolver.STATUS_BLOCKED_DATA,
    )
    next_day_summary = scheduler.run_scheduler(next_day)
    next_day_record = _only_scheduler_record(
        tmp_path,
        next_day.scheduler_run_id,
        resolver.STATUS_RESOLVED,
    )

    assert same_day_summary["status"] == scheduler.STATUS_PASS
    assert same_day_summary["blocked_data_count"] == 1
    assert same_day_record["outcome_price"] is None
    assert next_day_summary["status"] == scheduler.STATUS_PASS
    assert next_day_record["outcome_price_date"] == "2026-07-20"


def test_scheduler_provenance_links_to_capture_and_resolver(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [("2026-06-19", 100.0), ("2026-07-20", 90.0)],
    )
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_provenance",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)
    record = _only_scheduler_record(tmp_path, config.scheduler_run_id, resolver.STATUS_RESOLVED)
    provenance = record["provenance"]

    assert summary["provenance_link_count"] == 1
    assert summary["source_capture_run_id"] == "baseline_v3_5a_forward_live_fixture"
    assert summary["resolver_run_ids"]
    assert provenance["scheduler_run_id"] == config.scheduler_run_id
    assert provenance["resolver_run_id"] == record["resolver_run_id"]
    assert provenance["source_capture_run_id"] == "baseline_v3_5a_forward_live_fixture"
    assert Path(provenance["source_artifact_path"]).exists()


def test_empty_capture_grid_cannot_pass(tmp_path: Path) -> None:
    capture_dir = tmp_path / "capture_run"
    (capture_dir / "captures").mkdir(parents=True)
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_empty",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)

    assert summary["status"] == scheduler.STATUS_FAIL
    assert summary["scanned_decision_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_scheduler_run_id_collision_returns_nonzero_cli(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    run_id = "baseline_v3_5c_outcome_scheduler_existing"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")

    code = scheduler.main(
        [
            "--capture-run-dir",
            str(capture_dir),
            "--scheduler-run-id",
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


def test_scheduler_summary_never_reports_provider_backend_or_formal_lite(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])
    config = _scheduler_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5c_outcome_scheduler_no_backend",
        as_of="2026-07-19T00:00:00Z",
    )

    summary = scheduler.run_scheduler(config)

    assert summary["status"] == scheduler.STATUS_PASS
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["evidence_layer"] == "forward-live scheduler engineering/local validation only"


def _write_capture_run(
    tmp_path: Path,
    *,
    ticker: str,
    artifact_updates: dict[str, object] | None = None,
) -> Path:
    capture_dir = tmp_path / "capture_run"
    path = (
        capture_dir
        / "captures"
        / "direct_llm"
        / f"capture_2026-06-20_{ticker.lower()}_price_only_packet.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema": capture_v35a.CAPTURE_SCHEMA,
        "run_id": "baseline_v3_5a_forward_live_fixture",
        "capture_status": "captured",
        "arm": "direct_llm",
        "input_layer": "price_only_packet",
        "ticker": ticker,
        "decision_timestamp_utc": "2026-06-20T02:00:00Z",
        "decision_date_local": "2026-06-20",
        "horizon_days": 30,
        "horizon_end_date": "2026-07-20",
        "future_outcome_status": "not_matured",
        "future_outcome_scoring_status": "NOT_MATURED",
        "backend": "local_mock",
        "prompt_hash": "fixture_prompt_hash",
        "latest_visible_price_date": "2026-06-19",
        "future_data_violation": False,
        "decision": {"direction": "long"},
    }
    artifact.update(artifact_updates or {})
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


def _scheduler_config(
    root: Path,
    *,
    capture_dir: Path,
    run_id: str,
    as_of: str,
    outcome_window_days: int = resolver.DEFAULT_OUTCOME_WINDOW_DAYS,
) -> scheduler.SchedulerConfig:
    return scheduler.SchedulerConfig(
        capture_run_dir=capture_dir,
        scheduler_run_id=run_id,
        as_of_timestamp_utc=scheduler.parse_as_of_timestamp(as_of),
        price_dir=root / "prices",
        output_dir=root / "runs",
        outcome_window_days=outcome_window_days,
    )


def _only_scheduler_record(tmp_path: Path, run_id: str, status: str) -> dict[str, object]:
    paths = list(
        (
            tmp_path
            / "runs"
            / run_id
            / "resolver_outputs"
            / scheduler.resolver_run_id_for(
                scheduler.SchedulerConfig(
                    capture_run_dir=tmp_path / "capture_run",
                    scheduler_run_id=run_id,
                    as_of_timestamp_utc=scheduler.parse_as_of_timestamp("2026-07-21T00:00:00Z"),
                    price_dir=tmp_path / "prices",
                    output_dir=tmp_path / "runs",
                )
            )
            / "outcomes"
            / status.lower()
        ).glob("*.json")
    )
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8"))
