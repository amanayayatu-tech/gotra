"""Backtest metric and hypothesis calculations."""

from __future__ import annotations

from collections import defaultdict
from math import erf, sqrt
from statistics import mean
from typing import Any

from gotra.backtest.protocol import STYLE_WINDOWS, parse_date, style_window_for


def summarize_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [step for step in steps if step.get("status") == "scored"]
    by_arm: dict[str, list[float]] = defaultdict(list)
    for step in scored:
        by_arm[str(step["arm"])].append(float(step["mse"]))

    paired = paired_loss_differences(scored)
    h1 = convergence_result([step for step in scored if step.get("arm") == "alaya"])
    h2 = drift_window_results(scored)
    h3 = hac_mean_test(paired)
    return {
        "scored_steps": len(scored),
        "mse_by_arm": {
            arm: round(mean(values), 6) if values else None for arm, values in sorted(by_arm.items())
        },
        "paired_steps": len(paired),
        "differential_mse_mean": round(mean(paired), 6) if paired else None,
        "hypotheses": {
            "H1_convergence": h1,
            "H2_drift_resistance": h2,
            "H3_hac_differential": h3,
        },
    }


def paired_loss_differences(steps: list[dict[str, Any]]) -> list[float]:
    by_key: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for step in steps:
        if step.get("status") != "scored":
            continue
        key = (str(step.get("ticker")), str(step.get("decision_date")))
        by_key[key][str(step.get("arm"))] = float(step["mse"])
    return [
        values["baseline"] - values["alaya"]
        for _key, values in sorted(by_key.items())
        if "baseline" in values and "alaya" in values
    ]


def convergence_result(alaya_steps: list[dict[str, Any]], *, threshold_pct: float = 15.0) -> dict[str, Any]:
    ordered = sorted(alaya_steps, key=lambda item: (str(item.get("decision_date")), str(item.get("ticker"))))
    third = len(ordered) // 3
    if third == 0:
        return {"passed": None, "reason": "not_enough_steps"}
    first = [float(step["mse"]) for step in ordered[:third]]
    final = [float(step["mse"]) for step in ordered[-third:]]
    first_mean = mean(first)
    final_mean = mean(final)
    reduction_pct = ((first_mean - final_mean) / first_mean * 100) if first_mean else 0.0
    return {
        "passed": reduction_pct >= threshold_pct,
        "first_third_mse": round(first_mean, 6),
        "final_third_mse": round(final_mean, 6),
        "reduction_pct": round(reduction_pct, 4),
        "threshold_pct": threshold_pct,
    }


def drift_window_results(steps: list[dict[str, Any]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for window in STYLE_WINDOWS:
        window_steps = [
            step
            for step in steps
            if step.get("status") == "scored" and style_window_for(step["decision_date"]) == window.name
        ]
        by_arm: dict[str, list[float]] = defaultdict(list)
        for step in window_steps:
            by_arm[str(step["arm"])].append(float(step["mse"]))
        baseline = by_arm.get("baseline", [])
        alaya = by_arm.get("alaya", [])
        if not baseline or not alaya:
            results[window.name] = {"passed": None, "reason": "not_enough_paired_steps"}
            continue
        baseline_mean = mean(baseline)
        alaya_mean = mean(alaya)
        results[window.name] = {
            "passed": alaya_mean < baseline_mean,
            "baseline_mse": round(baseline_mean, 6),
            "alaya_mse": round(alaya_mean, 6),
            "steps": min(len(baseline), len(alaya)),
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
        }
    return results


def hac_mean_test(values: list[float], *, max_lag: int | None = None) -> dict[str, Any]:
    n = len(values)
    if n < 3:
        return {"passed": None, "reason": "not_enough_paired_steps", "n": n}
    sample_mean = mean(values)
    lag = min(max_lag if max_lag is not None else int(n ** 0.25), n - 1)
    centered = [value - sample_mean for value in values]
    gamma0 = sum(value * value for value in centered) / n
    long_run_variance = gamma0
    for current_lag in range(1, lag + 1):
        covariance = sum(centered[i] * centered[i - current_lag] for i in range(current_lag, n)) / n
        weight = 1.0 - current_lag / (lag + 1)
        long_run_variance += 2 * weight * covariance
    if long_run_variance <= 0:
        return {
            "passed": sample_mean > 0,
            "mean_loss_diff": round(sample_mean, 6),
            "hac_lag": lag,
            "p_value": 0.0 if sample_mean > 0 else 1.0,
            "n": n,
        }
    standard_error = sqrt(long_run_variance / n)
    z_score = sample_mean / standard_error if standard_error else 0.0
    p_value = 2 * (1 - _normal_cdf(abs(z_score)))
    return {
        "passed": sample_mean > 0 and p_value < 0.05,
        "mean_loss_diff": round(sample_mean, 6),
        "hac_lag": lag,
        "z_score": round(z_score, 6),
        "p_value": round(p_value, 8),
        "n": n,
    }


def cumulative_mse_series(steps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for step in sorted(steps, key=lambda item: (parse_date(item["decision_date"]), str(item["ticker"]))):
        if step.get("status") == "scored":
            by_arm[str(step["arm"])].append(step)
    series: dict[str, list[dict[str, Any]]] = {}
    for arm, arm_steps in by_arm.items():
        values: list[float] = []
        rows: list[dict[str, Any]] = []
        for step in arm_steps:
            values.append(float(step["mse"]))
            rows.append(
                {
                    "decision_date": step["decision_date"],
                    "mse": round(mean(values), 6),
                    "ticker": step["ticker"],
                }
            )
        series[arm] = rows
    return series


def _normal_cdf(value: float) -> float:
    return (1.0 + erf(value / sqrt(2.0))) / 2.0
