from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from gotra.backtest.kimi_probe import (
    DecisionPoint,
    compare_probe_runs,
    dead_zone_decision_from_median,
    load_decision_points,
)


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
