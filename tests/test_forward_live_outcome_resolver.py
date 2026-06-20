from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver


def test_immature_decision_remains_not_matured_without_outcome_fields(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-20", 110.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_immature",
        as_of="2026-07-19T00:00:00Z",
    )

    summary = resolver.run_resolver(config)
    record = _only_record(tmp_path, config.resolver_run_id, resolver.STATUS_NOT_MATURED)

    assert summary["status"] == "OUTCOME_RESOLVER_PASS"
    assert summary["not_matured_count"] == 1
    assert summary["resolved_count"] == 0
    assert record["outcome_status"] == resolver.STATUS_NOT_MATURED
    assert record["outcome_price"] is None
    assert record["actual_change_pct"] is None
    assert record["actual_direction"] is None
    assert "before horizon_end_date" in record["provenance"]["no_future_data_decision"]


def test_matured_decision_resolves_when_prices_are_available(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-20", 110.0),
            ("2026-07-21", 120.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_resolved",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = resolver.run_resolver(config)
    record = _only_record(tmp_path, config.resolver_run_id, resolver.STATUS_RESOLVED)

    assert summary["status"] == "OUTCOME_RESOLVER_PASS"
    assert summary["resolved_count"] == 1
    assert record["outcome_status"] == resolver.STATUS_RESOLVED
    assert record["decision_price"] == 100.0
    assert record["outcome_price_date"] == "2026-07-20"
    assert record["outcome_price"] == 110.0
    assert record["actual_change_pct"] == 10.000000000000009
    assert record["actual_direction"] == "long"


def test_matured_decision_with_missing_outcome_price_is_blocked_data(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(tmp_path / "prices", "AAPL", [("2026-06-19", 100.0)])
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_blocked_data",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = resolver.run_resolver(config)
    record = _only_record(tmp_path, config.resolver_run_id, resolver.STATUS_BLOCKED_DATA)

    assert summary["blocked_data_count"] == 1
    assert record["outcome_status"] == resolver.STATUS_BLOCKED_DATA
    assert record["outcome_price"] is None
    assert record["actual_change_pct"] is None
    assert record["actual_direction"] is None


def test_resolver_does_not_use_prices_after_allowed_outcome_window(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-25", 130.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_future_guard",
        as_of="2026-07-30T00:00:00Z",
        outcome_window_days=2,
    )

    summary = resolver.run_resolver(config)
    record = _only_record(tmp_path, config.resolver_run_id, resolver.STATUS_BLOCKED_DATA)

    assert summary["future_data_violation_count"] == 0
    assert summary["blocked_data_count"] == 1
    assert record["outcome_price_date"] is None
    assert record["outcome_price"] is None
    assert "required decision or outcome price was unavailable" in record["provenance"][
        "no_future_data_decision"
    ]


def test_source_future_data_flag_blocks_before_resolution(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        ticker="AAPL",
        artifact_updates={"future_data_violation": True},
    )
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-20", 110.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_source_flag",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = resolver.run_resolver(config)
    record = _only_record(
        tmp_path,
        config.resolver_run_id,
        resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA,
    )

    assert summary["status"] == "OUTCOME_RESOLVER_FAIL"
    assert summary["source_future_data_violation_count"] == 1
    assert summary["future_data_violation_count"] == 1
    assert summary["blocked_source_future_data_count"] == 1
    assert record["source_future_data_violation"] is True
    assert record["outcome_price"] is None
    assert "source_future_data_violation_flag" in record[
        "source_future_data_violation_reasons"
    ]


def test_latest_visible_price_after_capture_allowed_date_blocks_source(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(
        tmp_path,
        ticker="AAPL",
        artifact_updates={"latest_visible_price_date": "2026-06-21"},
    )
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-06-21", 105.0),
            ("2026-07-20", 110.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_source_latest_visible",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = resolver.run_resolver(config)
    record = _only_record(
        tmp_path,
        config.resolver_run_id,
        resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA,
    )

    assert summary["status"] == "OUTCOME_RESOLVER_FAIL"
    assert summary["source_future_data_violation_count"] == 1
    assert record["actual_change_pct"] is None
    assert "latest_visible_price_date_after_capture_allowed_date" in record[
        "source_future_data_violation_reasons"
    ]


def test_same_day_daily_close_is_not_visible_until_next_day_utc(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-20", 110.0),
        ],
    )
    same_day_config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_same_day_close",
        as_of="2026-07-20T00:00:00Z",
    )

    same_day_summary = resolver.run_resolver(same_day_config)
    same_day_record = _only_record(
        tmp_path,
        same_day_config.resolver_run_id,
        resolver.STATUS_BLOCKED_DATA,
    )

    assert same_day_summary["status"] == "OUTCOME_RESOLVER_PASS"
    assert same_day_summary["blocked_data_count"] == 1
    assert same_day_record["outcome_price_date"] is None
    assert "next-day daily-close availability" in same_day_record["provenance"][
        "no_future_data_decision"
    ]

    next_day_config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_next_day_close",
        as_of="2026-07-21T00:00:00Z",
    )

    next_day_summary = resolver.run_resolver(next_day_config)
    next_day_record = _only_record(
        tmp_path,
        next_day_config.resolver_run_id,
        resolver.STATUS_RESOLVED,
    )

    assert next_day_summary["status"] == "OUTCOME_RESOLVER_PASS"
    assert next_day_record["outcome_price_date"] == "2026-07-20"
    assert next_day_record["actual_direction"] == "long"


def test_actual_direction_uses_v3_direction_buckets() -> None:
    assert resolver.actual_direction(0.5) == "neutral"
    assert resolver.actual_direction(2.0) == "long"
    assert resolver.actual_direction(-2.0) == "avoid"


def test_provenance_links_back_to_source_capture_artifact(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-20", 90.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_provenance",
        as_of="2026-07-25T00:00:00Z",
    )

    summary = resolver.run_resolver(config)
    record = _only_record(tmp_path, config.resolver_run_id, resolver.STATUS_RESOLVED)
    provenance = record["provenance"]

    assert summary["provenance_reverse_lookup_status"] == "PASS"
    assert provenance["source_capture_run_id"] == "baseline_v3_5a_forward_live_fixture"
    assert provenance["source_decision_id"] == record["source_decision_id"]
    assert provenance["source_artifact_ref"].startswith("captures/direct_llm/")
    assert Path(provenance["source_artifact_path"]).exists()
    assert provenance["resolver_run_id"] == config.resolver_run_id


def test_existing_resolver_run_id_is_blocked_by_default(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    run_id = "baseline_v3_5b_outcome_resolver_existing"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id=run_id,
        as_of="2026-07-25T00:00:00Z",
    )

    summary = resolver.run_resolver(config)

    assert summary["status"] == resolver.STATUS_BLOCKED_RUN_ID_EXISTS
    assert summary["capture_artifact_count"] == 0
    assert summary["provider_or_backend_called"] is False


def test_main_returns_nonzero_when_resolver_run_id_is_blocked(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    run_id = "baseline_v3_5b_outcome_resolver_cli_existing"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")

    code = resolver.main(
        [
            "--capture-run-dir",
            str(capture_dir),
            "--resolver-run-id",
            run_id,
            "--as-of-timestamp-utc",
            "2026-07-25T00:00:00Z",
            "--price-dir",
            str(tmp_path / "prices"),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert code == 1


def test_resolved_outcome_artifact_schema_has_required_fields(tmp_path: Path) -> None:
    capture_dir = _write_capture_run(tmp_path, ticker="AAPL")
    _write_prices(
        tmp_path / "prices",
        "AAPL",
        [
            ("2026-06-19", 100.0),
            ("2026-07-20", 100.0),
        ],
    )
    config = _resolver_config(
        tmp_path,
        capture_dir=capture_dir,
        run_id="baseline_v3_5b_outcome_resolver_schema",
        as_of="2026-07-25T00:00:00Z",
    )

    resolver.run_resolver(config)
    record = _only_record(tmp_path, config.resolver_run_id, resolver.STATUS_RESOLVED)

    required = {
        "schema",
        "resolver_run_id",
        "source_run_id",
        "source_decision_id",
        "source_decision_artifact",
        "ticker",
        "decision_date",
        "horizon_days",
        "horizon_end_date",
        "outcome_status",
        "outcome_price_date",
        "decision_price",
        "outcome_price",
        "actual_change_pct",
        "actual_direction",
        "resolved_at",
        "provenance",
    }
    assert required <= set(record)
    assert record["actual_direction"] == "neutral"


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
    path.write_text(
        json.dumps(
            artifact,
            indent=2,
            sort_keys=True,
        ),
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


def _resolver_config(
    root: Path,
    *,
    capture_dir: Path,
    run_id: str,
    as_of: str,
    outcome_window_days: int = resolver.DEFAULT_OUTCOME_WINDOW_DAYS,
) -> resolver.ResolverConfig:
    return resolver.ResolverConfig(
        capture_run_dir=capture_dir,
        resolver_run_id=run_id,
        as_of_timestamp_utc=resolver.parse_as_of_timestamp(as_of),
        price_dir=root / "prices",
        output_dir=root / "runs",
        outcome_window_days=outcome_window_days,
    )


def _only_record(tmp_path: Path, run_id: str, status: str) -> dict[str, object]:
    paths = list((tmp_path / "runs" / run_id / "outcomes" / status.lower()).glob("*.json"))
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8"))
