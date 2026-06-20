from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from gotra.backtest import kimi_probe as kp
from gotra.backtest.kimi_probe import (
    DecisionPoint,
    ProbeConfig,
    RunStats,
    compare_probe_runs,
    dead_zone_decision_from_median,
    load_decision_points,
)
from gotra.backtest.protocol import TickerSpec
from gotra.backtest.walk_forward import ProviderSample


def test_load_decision_points_dedupes_and_parses_dates(tmp_path: Path) -> None:
    points_file = tmp_path / "points.txt"
    points_file.write_text(
        "# fixture\n0700.HK,2021-10-01\n0700.HK,2021-10-01\nNVDA,2022-04-01\n",
        encoding="utf-8",
    )

    assert load_decision_points(points_file) == [
        DecisionPoint("0700.HK", date(2021, 10, 1)),
        DecisionPoint("NVDA", date(2022, 4, 1)),
    ]


def test_dead_zone_decision_from_median_uses_stage6_epsilon() -> None:
    assert dead_zone_decision_from_median(0.3, epsilon_pct=0.3) == ("neutral", 0.0)
    assert dead_zone_decision_from_median(-0.3, epsilon_pct=0.3) == ("neutral", 0.0)
    assert dead_zone_decision_from_median(0.31, epsilon_pct=0.3) == ("long", 0.31)
    assert dead_zone_decision_from_median(-0.31, epsilon_pct=0.3) == ("avoid", -0.31)


def test_compare_probe_runs_reports_overall_and_hk_rates(tmp_path: Path) -> None:
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    _write_step(run1, "0700.HK", "2021-10-01", "long", 1.2)
    _write_step(run2, "0700.HK", "2021-10-01", "avoid", -1.0)
    _write_step(run1, "NVDA", "2022-04-01", "neutral", 0.0)
    _write_step(run2, "NVDA", "2022-04-01", "neutral", 0.0)

    result = compare_probe_runs(
        run1,
        run2,
        points=[
            DecisionPoint("0700.HK", date(2021, 10, 1)),
            DecisionPoint("NVDA", date(2022, 4, 1)),
        ],
    )

    assert result["same"] == 1
    assert result["total"] == 2
    assert result["rate"] == 0.5
    assert result["hk_same"] == 0
    assert result["hk_total"] == 1
    assert result["hk_rate"] == 0.0
    assert result["mismatches"][0]["ticker"] == "0700.HK"


def test_complete_denoised_passes_kimi_provider_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_complete_one_sample(**kwargs: object) -> ProviderSample:
        sample_index = int(kwargs["sample_index"])
        return ProviderSample(
            sample_index=sample_index,
            direction="long",
            expected_change_pct=float(sample_index),
            confidence=0.6,
            reasoning=f"sample {sample_index}",
            billed_tokens=10,
            token_usage_source="provider_usage",
            attempts=1,
        )

    monkeypatch.setattr(kp, "_complete_one_sample", fake_complete_one_sample)

    config = ProbeConfig(
        data_dir=Path("."),
        points_file=Path("points.txt"),
        run_prefix="stage7_kimi_probe",
        sample_count=2,
        dead_zone_epsilon_pct=0.3,
        timeout_seconds=30,
        sample_retries=1,
        decision_concurrency=1,
        sample_concurrency=1,
        max_connections=1,
        model="kimi-k2",
        base_url="https://example.invalid/v1",
        env_file=None,
        output_name="compare.json",
    )

    decision_payload, billed_tokens, token_usage_source, denoising = kp._complete_denoised(
        client=object(),
        call_limiter=threading.BoundedSemaphore(1),
        prompt="{}",
        token_estimate=10,
        config=config,
        sample_concurrency=1,
        stats=RunStats(),
        phase="test",
    )

    assert decision_payload["reasoning"].startswith("median denoised 2 kimi_sophnet samples")
    assert billed_tokens == 20
    assert token_usage_source == "provider_usage"
    assert denoising["provider_label"] == "kimi_sophnet"


def test_score_point_skips_empty_history_before_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    prices = pd.DataFrame(
        [
            {
                "date": date(2020, 1, 2),
                "adj_close": 100.0,
                "source_url": "fixture://price-cache",
            },
            {
                "date": date(2020, 2, 3),
                "adj_close": 101.0,
                "source_url": "fixture://price-cache",
            },
        ]
    )
    monkeypatch.setattr(kp, "read_price_cache", lambda *args, **kwargs: prices)

    config = ProbeConfig(
        data_dir=Path("."),
        points_file=Path("points.txt"),
        run_prefix="stage7_kimi_probe",
        sample_count=1,
        dead_zone_epsilon_pct=0.3,
        timeout_seconds=30,
        sample_retries=1,
        decision_concurrency=1,
        sample_concurrency=1,
        max_connections=1,
        model="kimi-k2",
        base_url="https://example.invalid/v1",
        env_file=None,
        output_name="compare.json",
    )

    step = kp._score_point(
        point=DecisionPoint("AAPL", date(2020, 1, 1)),
        ticker_spec=TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
        step_index=1,
        run_root=Path("run"),
        run_index=1,
        client=object(),
        call_limiter=threading.BoundedSemaphore(1),
        config=config,
        sample_concurrency=1,
        stats=RunStats(),
        phase="test",
    )

    assert step["status"] == "skipped"
    assert step["skip_reason"] == "insufficient_price_history"
    assert step["provider"] == "kimi_sophnet"


def _write_step(
    run_root: Path,
    ticker: str,
    decision_date: str,
    direction: str,
    expected_change_pct: float,
) -> None:
    path = run_root / "baseline" / f"step_{decision_date}_{ticker.lower().replace('.', '_')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "scored",
                "ticker": ticker,
                "decision_date": decision_date,
                "decision_direction": direction,
                "expected_change_pct": expected_change_pct,
                "denoising": {"raw_median_expected_change_pct": expected_change_pct},
            }
        ),
        encoding="utf-8",
    )
