from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import baseline_v3_6v_short_horizon_cohort_plan as plan


CAPTURE_TS = datetime(2026, 6, 21, 3, 0, tzinfo=UTC)


def test_short_horizon_plan_ready_without_provider_calls(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    _write_prices(tmp_path / "prices", "MSFT")
    config = _plan_config(
        tmp_path,
        tickers=("AAPL", "MSFT"),
        horizons=(1, 3, 5),
    )

    summary = plan.run_plan(config)

    assert summary["status"] == plan.STATUS_PLAN_READY
    assert summary["cohort_point_count"] == 6
    assert summary["expected_backend_decisions_if_captured"] == 48
    assert summary["deterministic_reference_expected_count"] == 6
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_30d_verdict_allowed"] is False
    assert summary["does_not_inherit_30d_conclusions"] is True
    assert summary["direct_llm_interpretation"] == "direct_llm_parametric_memory_control"
    assert {point["horizon_days"] for point in summary["cohort_points"]} == {1, 3, 5}


def test_short_horizon_plan_records_daily_close_maturity_rule(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _plan_config(tmp_path, tickers=("AAPL",), horizons=(1,))

    summary = plan.run_plan(config)

    point = summary["cohort_points"][0]
    assert point["horizon_end_date"] == "2026-06-22"
    assert point["outcome_price_available_after_utc"] == "2026-06-23T00:00:00Z"
    assert point["outcome_maturity_rule"] == "daily close visible at next UTC midnight"
    assert summary["next_maturity_after_utc"] == "2026-06-23T00:00:00Z"


@pytest.mark.parametrize("horizons", [(), (0,), (-1,), (1, 0)])
def test_short_horizon_plan_rejects_empty_or_invalid_horizons(
    tmp_path: Path,
    horizons: tuple[int, ...],
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _plan_config(tmp_path, tickers=("AAPL",), horizons=horizons)

    with pytest.raises(ValueError):
        plan.run_plan(config)


def test_short_horizon_plan_blocks_missing_price_cache(tmp_path: Path) -> None:
    config = _plan_config(tmp_path, tickers=("MISSING",), horizons=(1,))

    summary = plan.run_plan(config)

    assert summary["status"] == plan.STATUS_BLOCKED_DATA
    assert summary["cohort_point_count"] == 0
    assert summary["local_data_blocker_count"] == 1
    assert summary["blockers"][0]["reason"] == "price_cache_unavailable"


@pytest.mark.parametrize("tickers", [("AAPL", "AAPL"), ("BRK.B", "BRK-B")])
def test_short_horizon_plan_rejects_duplicate_ticker_slugs(
    tmp_path: Path,
    tickers: tuple[str, ...],
) -> None:
    config = _plan_config(tmp_path, tickers=tickers, horizons=(1,))

    with pytest.raises(ValueError, match="duplicate ticker slug"):
        plan.run_plan(config)
    assert not (tmp_path / "runs" / config.plan_run_id).exists()


def test_short_horizon_existing_run_id_blocks_without_overwrite(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _plan_config(tmp_path, tickers=("AAPL",), horizons=(1,))
    run_root = config.output_dir / config.plan_run_id
    run_root.mkdir(parents=True)
    existing_summary = {"status": "must_not_overwrite"}
    (run_root / "summary.json").write_text(json.dumps(existing_summary), encoding="utf-8")

    summary = plan.run_plan(config)

    assert summary["status"] == plan.STATUS_BLOCKED_RUN_ID_EXISTS
    assert json.loads((run_root / "summary.json").read_text(encoding="utf-8")) == existing_summary
    assert plan.main(
        [
            "--plan-run-id",
            config.plan_run_id,
            "--output-dir",
            str(config.output_dir),
            "--tickers",
            "AAPL",
            "--horizons",
            "1",
            "--capture-timestamp-utc",
            "2026-06-21T03:00:00Z",
            "--price-dir",
            str(config.price_dir),
        ]
    ) == 1


def _price_rows(days: int = 40) -> pd.DataFrame:
    start = date(2026, 5, 1)
    rows = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        rows.append(
            {
                "date": current.isoformat(),
                "ticker": "AAPL",
                "adj_close": 100 + offset,
                "source_url": "fixture",
                "evidence_unverified": False,
            }
        )
    return pd.DataFrame(rows)


def _write_prices(price_dir: Path, ticker: str) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    _price_rows().assign(ticker=ticker).to_csv(price_dir / f"{ticker}.csv", index=False)


def _plan_config(
    root: Path,
    *,
    tickers: tuple[str, ...],
    horizons: tuple[int, ...],
) -> plan.PlanConfig:
    return plan.PlanConfig(
        plan_run_id="baseline_v3_6v_short_horizon_cohort_plan_test",
        output_dir=root / "runs",
        tickers=tickers,
        horizons=horizons,
        arms=("direct_llm", "ksana_formatting_only", "ksana_real_research", "full_gotra"),
        input_layers=("price_only_packet", "richer_research_packet"),
        capture_timestamp_utc=CAPTURE_TS,
        timezone="Asia/Shanghai",
        price_dir=root / "prices",
        provider_model="gpt-5.5",
        codex_cli_reasoning_setting="high",
    )
