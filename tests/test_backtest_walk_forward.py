from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from gotra.backtest.audit import audit_step
from gotra.backtest.protocol import TickerSpec, decision_dates
from gotra.backtest.walk_forward import BacktestConfig, run_backtest


def test_decision_dates_start_after_initial_window() -> None:
    dates = decision_dates(
        start=date(2016, 1, 1),
        end=date(2017, 7, 1),
        step_months=3,
    )

    assert dates == (
        date(2017, 1, 1),
        date(2017, 4, 1),
        date(2017, 7, 1),
    )


def test_audit_step_rejects_future_decision_input() -> None:
    violations = audit_step(
        {
            "decision_date": "2020-01-01",
            "outcome_as_of": "2020-02-03",
            "future_data_allowed": False,
            "provider_network_enabled": False,
            "audit_actor": "backtest/walk_forward",
            "decision_inputs": [
                {
                    "name": "bad_news",
                    "availability_date": "2020-01-02",
                    "source": "fixture",
                }
            ],
            "outcome_inputs": [
                {
                    "name": "outcome_price",
                    "availability_date": "2020-02-03",
                    "source": "fixture",
                }
            ],
        }
    )

    assert [violation.code for violation in violations] == ["decision_input_future"]


def test_sampled_backtest_writes_steps_audit_summary_and_report(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=560)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="sampled_test",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 4, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=10_000,
        )
    )

    run_root = tmp_path / "runs" / "sampled_test"
    baseline_steps = sorted((run_root / "baseline").glob("step_*.json"))
    alaya_steps = sorted((run_root / "alaya").glob("step_*.json"))

    assert summary["audit"]["ok"] is True
    assert summary["audit"]["steps_checked"] == 4
    assert summary["metrics"]["scored_steps"] == 4
    assert summary["metrics"]["paired_steps"] == 2
    assert baseline_steps
    assert alaya_steps
    assert (run_root / "event_log.jsonl").exists()
    assert (run_root / "system_health.json").exists()
    assert (tmp_path / "REPORT_backtest.md").exists()
    assert (tmp_path / "REPORT_backtest_mse.svg").exists()
    system_health = json.loads((run_root / "system_health.json").read_text(encoding="utf-8"))
    assert system_health["status"] == "ok"
    assert system_health["token_budget"]["max_tokens"] == 10_000

    step = json.loads(alaya_steps[0].read_text(encoding="utf-8"))
    assert step["future_data_allowed"] is False
    assert step["provider_network_enabled"] is False
    assert step["audit_actor"] == "backtest/walk_forward"
    assert all(item["availability_date"] <= step["decision_date"] for item in step["decision_inputs"])


def test_backtest_pauses_when_token_budget_is_exceeded(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "MSFT", start="2016-01-01", days=470)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="budget_test",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),),
            token_budget=1,
        )
    )

    assert summary["paused"] is True
    assert "token budget exceeded" in summary["pause_reason"].lower()
    assert summary["system_health"]["status"] == "paused"
    assert summary["system_health"]["alerts"] == [summary["pause_reason"]]
    assert summary["token_budget"]["spent_tokens"] == 0
    run_root = tmp_path / "runs" / "budget_test"
    assert (run_root / "summary.json").exists()
    assert (run_root / "system_health.json").exists()


def _write_prices(price_dir: Path, ticker: str, *, start: str, days: int) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    start_date = date.fromisoformat(start)
    rows = []
    price = 100.0
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        price += 0.05 + (offset % 11) * 0.01
        rows.append(
            {
                "date": current.isoformat(),
                "ticker": ticker,
                "adj_close": round(price, 4),
                "source_url": "fixture",
                "evidence_unverified": False,
            }
        )
    pd.DataFrame(rows).to_csv(price_dir / f"{ticker}.csv", index=False)
