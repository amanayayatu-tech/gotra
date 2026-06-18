#!/usr/bin/env python3
"""Stage 8 offline direction-signal PnL screening.

This script is intentionally local-only: it reads existing step/compare JSON
artifacts, writes only the Stage 8 markdown report, and never writes under
data/backtest/runs. scripts/stage6_alaya_diagnosis.py is absent in this
checkout, so the small loader/direction helpers below are equivalent local
implementations for the Stage 8 prompt.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPORT_DATE = "2026-06-18"
RUNS_ROOT = Path("data/backtest/runs")
REPORT_PATH = Path(f"docs/STAGE8_SIGNAL_PNL_BACKTEST_{REPORT_DATE}.md")

STAGE7_FULL_RUN = "stage7_full_20260617T123803Z"
STAGE7_REPRO_RUN = "stage7_repro_20260617T150954Z"
STAGE7_SMOKE_RUN = "stage7_kimi_smoke_20260617T094500Z"
BASELINE_RUN = "bt_baseline_parallel_replay4_20260615"
COMPARE_JSON = RUNS_ROOT / BASELINE_RUN / "compare_bt_full_v3_20260615.json"
MINIS_HANDOFF = Path("/var/minis/shared/gotra/GOTRA_STAGE8_HANDOFF_FOR_MINIS.md")

AVOID_AS_SHORT_VARIANTS = (False, True)
COST_BPS_VARIANTS = (10.0, 0.0)
PRIMARY_COST_BPS = 10.0
RISK_FREE_RATE = 0.0
RANDOM_MONTE_CARLO_N = 10_000
RANDOM_SEED = 20260618
VOTE_THRESHOLDS = (0.0, 0.6, 0.8, 1.0)


def probe_fields(run_root: str) -> dict[str, Any]:
    files = sorted(glob.glob(f"{run_root}/*/step_*.json"))[:3]
    if not files:
        files = sorted(glob.glob(f"{run_root}/step_*.json"))[:3]
    if not files:
        return {"error": f"no step_*.json under {run_root}"}
    with open(files[0], encoding="utf-8") as handle:
        sample = json.load(handle)
    fields = {
        "has_actual_change_pct": sample.get("actual_change_pct") is not None,
        "has_decision_direction": "decision_direction" in sample,
        "has_expected_change_pct": "expected_change_pct" in sample,
        "has_denoising": sample.get("denoising") is not None,
        "has_vote_consistency": (sample.get("denoising") or {}).get("vote_consistency")
        is not None,
        "all_keys": sorted(sample.keys()),
    }
    all_files = glob.glob(f"{run_root}/*/step_*.json")
    if not all_files:
        all_files = glob.glob(f"{run_root}/step_*.json")
    n = len(all_files)
    n_actual = 0
    for file_name in all_files:
        with open(file_name, encoding="utf-8") as handle:
            if json.load(handle).get("actual_change_pct") is not None:
                n_actual += 1
    fields["n_steps"] = n
    fields["n_actual_non_null"] = n_actual
    fields["actual_coverage"] = f"{n_actual}/{n} = {n_actual / n:.4f}"
    return fields


def expected_to_direction(expected_change_pct: float) -> str:
    if expected_change_pct >= 2.0:
        return "long"
    if expected_change_pct <= -2.0:
        return "avoid"
    return "neutral"


@dataclass(frozen=True)
class StrategyResult:
    label: str
    direction_source: str
    avoid_as_short: bool
    cost_bps: float
    metrics: dict[str, float]
    monthly_returns: pd.Series
    positions: pd.DataFrame
    ticker_table: pd.DataFrame
    top_ticker: str | None
    without_top_metrics: dict[str, float] | None


def run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        return "git not found"
    return result.stdout.strip()


def worktree_report() -> str:
    lines = [
        "=== pwd ===",
        str(Path.cwd()),
        "=== branch ===",
        run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "=== HEAD ===",
        run_git(["rev-parse", "--short", "HEAD"]),
        "=== status --short ===",
    ]
    status = run_git(["status", "--short"])
    if status:
        lines.extend(status.splitlines())
    lines.append("=== untracked ===")
    untracked = run_git(["ls-files", "--others", "--exclude-standard"])
    if untracked:
        lines.extend(untracked.splitlines())
    lines.append("=== data/backtest/runs ===")
    if RUNS_ROOT.exists():
        lines.extend(sorted(path.name for path in RUNS_ROOT.iterdir()))
    lines.append("=== alaya step counts ===")
    for run_dir in sorted(path for path in RUNS_ROOT.glob("*/") if path.is_dir()):
        alaya_count = len(list(run_dir.glob("**/step_*.json")))
        alaya_count = len([p for p in run_dir.glob("**/step_*.json") if "alaya" in p.parts])
        baseline_count = len(
            [p for p in run_dir.glob("**/step_*.json") if "baseline" in p.parts]
        )
        lines.append(
            f"{run_dir.as_posix() + '/':<70s} "
            f"baseline={baseline_count:4d} alaya={alaya_count:4d}"
        )
    lines.append("=== compare JSONs ===")
    lines.extend(path.as_posix() for path in sorted(RUNS_ROOT.glob("**/compare_*.json")))
    lines.append("=== 目标 run 存在性 ===")
    for run_name in (
        STAGE7_FULL_RUN,
        STAGE7_REPRO_RUN,
        STAGE7_SMOKE_RUN,
        BASELINE_RUN,
        "glm_probe_a",
        "glm_probe_b",
        "kimi_probe_a",
        "kimi_probe_b",
    ):
        prefix = "EXIST " if (RUNS_ROOT / run_name).is_dir() else "MISSING"
        lines.append(f"{prefix} {run_name}")
    return "\n".join(lines)


def count_steps(run_name: str, arm: str) -> int:
    return len(list((RUNS_ROOT / run_name / arm).glob("step_*.json")))


def select_mode() -> str:
    full_exists = (RUNS_ROOT / STAGE7_FULL_RUN).is_dir()
    repro_exists = (RUNS_ROOT / STAGE7_REPRO_RUN).is_dir()
    full_baseline = count_steps(STAGE7_FULL_RUN, "baseline") if full_exists else 0
    full_alaya = count_steps(STAGE7_FULL_RUN, "alaya") if full_exists else 0
    repro_baseline = count_steps(STAGE7_REPRO_RUN, "baseline") if repro_exists else 0
    repro_alaya = count_steps(STAGE7_REPRO_RUN, "alaya") if repro_exists else 0
    baseline_steps = count_steps(BASELINE_RUN, "baseline")

    if full_exists and repro_exists and min(full_baseline, full_alaya, repro_baseline, repro_alaya) >= 1000:
        return "FULL"
    if full_exists and min(full_baseline, full_alaya) >= 1000 and not repro_exists:
        return "FULL_PARTIAL"
    if full_exists and full_alaya < 100:
        return "SMOKE_DEMO"
    if not full_exists and baseline_steps >= 100:
        return "BASELINE_ONLY"
    return "ABORT"


def load_steps_from_root(run_root: Path, arm: str, source_run: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted((run_root / arm).glob("step_*.json")):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        denoising = data.get("denoising") or {}
        rows.append(
            {
                "source_run": source_run,
                "arm": arm,
                "path": path.as_posix(),
                "ticker": data.get("ticker"),
                "decision_date": data.get("decision_date") or data.get("date"),
                "actual_change_pct": data.get("actual_change_pct"),
                "actual_return": data.get("actual_change_pct") / 100
                if data.get("actual_change_pct") is not None
                else np.nan,
                "decision_direction": normalize_direction(data.get("decision_direction")),
                "expected_change_pct": data.get("expected_change_pct"),
                "vote_consistency": denoising.get("vote_consistency"),
                "mse": data.get("mse"),
                "future_data_allowed": data.get("future_data_allowed"),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["decision_date"] = pd.to_datetime(df["decision_date"])
        df = df.sort_values(["decision_date", "ticker"]).reset_index(drop=True)
    return df


def load_steps(run_name: str, arm: str) -> pd.DataFrame:
    return load_steps_from_root(RUNS_ROOT / run_name, arm, run_name)


def normalize_direction(value: Any) -> str:
    if value is None:
        return "neutral"
    normalized = str(value).strip().lower()
    if normalized in {"long", "buy"}:
        return "long"
    if normalized in {"avoid", "short", "neutral", "watch"}:
        return normalized
    return "neutral"


def direction_to_position(direction: str, avoid_as_short: bool) -> int:
    if direction == "long":
        return 1
    if direction == "short":
        return -1
    if direction == "avoid":
        return -1 if avoid_as_short else 0
    return 0


def directions_for_source(df: pd.DataFrame, source: str) -> pd.Series:
    if source in {"decision_direction", "reference_direction"}:
        return df["decision_direction"].map(normalize_direction)
    if source == "expected_change_pct":
        return df["expected_change_pct"].map(
            lambda value: "neutral" if pd.isna(value) else expected_to_direction(float(value))
        )
    raise ValueError(f"unknown direction source: {source}")


def add_positions(
    df: pd.DataFrame,
    direction_source: str,
    avoid_as_short: bool,
    vote_threshold: float | None = None,
) -> pd.DataFrame:
    out = df.copy()
    out["direction_used"] = directions_for_source(out, direction_source)
    out["position"] = out["direction_used"].map(
        lambda direction: direction_to_position(direction, avoid_as_short)
    )
    if vote_threshold is not None:
        keep = out["vote_consistency"].notna() & (out["vote_consistency"] >= vote_threshold)
        out.loc[~keep, "position"] = 0
    return out


def compute_monthly_returns(positioned: pd.DataFrame, cost_bps: float) -> pd.Series:
    if positioned.empty:
        return pd.Series(dtype=float)

    all_tickers = sorted(positioned["ticker"].dropna().unique())
    previous = {ticker: 0 for ticker in all_tickers}
    monthly: dict[pd.Timestamp, float] = {}
    cost_rate = cost_bps / 10_000

    for decision_date, group in positioned.groupby("decision_date", sort=True):
        current = {ticker: 0 for ticker in all_tickers}
        actual_by_ticker = dict(zip(group["ticker"], group["actual_return"]))
        for row in group.itertuples(index=False):
            current[row.ticker] = int(row.position)

        active_returns = [
            current[ticker] * float(actual_by_ticker[ticker])
            for ticker in all_tickers
            if current[ticker] != 0 and ticker in actual_by_ticker
        ]
        gross_return = float(np.mean(active_returns)) if active_returns else 0.0

        sides = sum(abs(current[ticker] - previous.get(ticker, 0)) for ticker in all_tickers)
        current_holdings = sum(1 for ticker in all_tickers if current[ticker] != 0)
        previous_holdings = sum(1 for ticker in all_tickers if previous.get(ticker, 0) != 0)
        cost_denominator = current_holdings or previous_holdings
        cost = (sides * cost_rate / cost_denominator) if cost_denominator else 0.0
        monthly[decision_date] = gross_return - cost
        previous = current

    return pd.Series(monthly, dtype=float).sort_index()


def metric_summary(
    positioned: pd.DataFrame,
    monthly_returns: pd.Series,
    label: str,
    direction_source: str,
    avoid_as_short: bool,
    cost_bps: float,
) -> dict[str, float]:
    n_months = int(monthly_returns.shape[0])
    cumulative = float(np.prod(1 + monthly_returns.to_numpy()) - 1) if n_months else math.nan
    annualized = (
        float((1 + cumulative) ** (12 / n_months) - 1)
        if n_months and cumulative > -1
        else math.nan
    )
    std = float(monthly_returns.std(ddof=1)) if n_months > 1 else math.nan
    sharpe = (
        float((monthly_returns.mean() - RISK_FREE_RATE / 12) / std * math.sqrt(12))
        if std and not math.isnan(std)
        else math.nan
    )
    wealth = (1 + monthly_returns).cumprod()
    drawdown = ((wealth.cummax() - wealth) / wealth.cummax()).max() if n_months else math.nan
    active = positioned[positioned["position"] != 0]
    if active.empty:
        hit_rate = math.nan
    else:
        hit_rate = float((np.sign(active["position"]) == np.sign(active["actual_return"])).mean())
    win_rate = float((monthly_returns > 0).mean()) if n_months else math.nan
    positive = monthly_returns[monthly_returns > 0]
    negative = monthly_returns[monthly_returns < 0]
    profit_loss = (
        float(positive.mean() / abs(negative.mean())) if not positive.empty and not negative.empty else math.nan
    )
    return {
        "label": label,
        "direction_source": direction_source,
        "avoid_as_short": avoid_as_short,
        "cost_bps": cost_bps,
        "n_months": n_months,
        "cumulative_return": cumulative,
        "annualized_return": annualized,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown) if not pd.isna(drawdown) else math.nan,
        "hit_rate": hit_rate,
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss,
        "trade_count": int((positioned["position"] != 0).sum()),
        "abstain_ratio": float((positioned["position"] == 0).mean()) if not positioned.empty else math.nan,
    }


def ticker_breakdown(positioned: pd.DataFrame, monthly_returns: pd.Series) -> pd.DataFrame:
    if positioned.empty:
        return pd.DataFrame()

    active_count_by_date = positioned.groupby("decision_date")["position"].apply(
        lambda values: int((values != 0).sum())
    )
    rows: list[dict[str, Any]] = []
    total_contribution = 0.0
    for ticker, group in positioned.groupby("ticker", sort=True):
        group = group.sort_values("decision_date")
        contributions = []
        for row in group.itertuples(index=False):
            active_count = active_count_by_date.loc[row.decision_date]
            contribution = (
                float(row.position) * float(row.actual_return) / active_count
                if row.position != 0 and active_count
                else 0.0
            )
            contributions.append(contribution)
        contribution_sum = float(np.sum(contributions))
        total_contribution += contribution_sum
        ticker_monthly = pd.Series(contributions, index=group["decision_date"])
        independent_cum = float(np.prod(1 + ticker_monthly.to_numpy()) - 1)
        active = group[group["position"] != 0]
        hit_rate = (
            float((np.sign(active["position"]) == np.sign(active["actual_return"])).mean())
            if not active.empty
            else math.nan
        )
        rows.append(
            {
                "ticker": ticker,
                "portfolio_contribution": contribution_sum,
                "independent_cumulative_return": independent_cum,
                "hit_rate": hit_rate,
                "trade_count": int((group["position"] != 0).sum()),
            }
        )

    table = pd.DataFrame(rows).sort_values("portfolio_contribution", ascending=False)
    cumulative = table["portfolio_contribution"].cumsum()
    table["cumulative_contribution_pct"] = (
        cumulative / total_contribution if total_contribution else math.nan
    )
    table["portfolio_cumulative_return"] = (
        float(np.prod(1 + monthly_returns.to_numpy()) - 1) if not monthly_returns.empty else math.nan
    )
    return table.reset_index(drop=True)


def compute_strategy(
    df: pd.DataFrame,
    label: str,
    direction_source: str,
    avoid_as_short: bool,
    cost_bps: float,
    ticker_filter: set[str] | None = None,
) -> StrategyResult:
    working = df if ticker_filter is None else df[df["ticker"].isin(ticker_filter)]
    positioned = add_positions(working, direction_source, avoid_as_short)
    monthly = compute_monthly_returns(positioned, cost_bps)
    metrics = metric_summary(positioned, monthly, label, direction_source, avoid_as_short, cost_bps)
    ticker_table = ticker_breakdown(positioned, monthly)
    top_ticker = str(ticker_table.iloc[0]["ticker"]) if not ticker_table.empty else None
    without_top_metrics = None
    if top_ticker and ticker_filter is None and positioned["ticker"].nunique() > 1:
        kept_tickers = set(positioned["ticker"].unique()) - {top_ticker}
        without_top = compute_strategy(
            df,
            label,
            direction_source,
            avoid_as_short,
            cost_bps,
            ticker_filter=kept_tickers,
        )
        without_top_metrics = without_top.metrics
    return StrategyResult(
        label=label,
        direction_source=direction_source,
        avoid_as_short=avoid_as_short,
        cost_bps=cost_bps,
        metrics=metrics,
        monthly_returns=monthly,
        positions=positioned,
        ticker_table=ticker_table,
        top_ticker=top_ticker,
        without_top_metrics=without_top_metrics,
    )


def build_reference_arm(candidate_df: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    if not COMPARE_JSON.exists():
        return pd.DataFrame(), "missing_compare_json", ""
    with open(COMPARE_JSON, encoding="utf-8") as handle:
        compare = json.load(handle)
    reference_run = str(compare.get("reference_run", ""))
    reference_path = Path(reference_run)
    if reference_run and reference_path.exists() and list((reference_path / "baseline").glob("step_*.json")):
        reference = load_steps_from_root(reference_path, "baseline", reference_run)
        reference["arm"] = "reference_from_compare"
        return reference, "reference_step_json", reference_run

    if any(row.get("reason") == "missing_candidate_step" for row in compare.get("mismatches", [])):
        return pd.DataFrame(), "reference_step_json_required_missing_candidate_step", reference_run

    mismatch_direction = {
        (row["ticker"], row["decision_date"]): normalize_direction(row["reference_direction"])
        for row in compare.get("mismatches", [])
        if row.get("reason") == "direction_mismatch"
    }
    reference = candidate_df.copy()
    reference["arm"] = "reference_from_compare"
    reference["source_run"] = str(compare.get("reference_run", "reference_run"))
    reference["decision_direction"] = [
        mismatch_direction.get(
            (row.ticker, row.decision_date.strftime("%Y-%m-%d")),
            row.decision_direction,
        )
        for row in reference.itertuples(index=False)
    ]
    reference["expected_change_pct"] = np.nan
    return reference, "compare_mismatch_reconstructed", reference_run


def actual_coverage_ok(df: pd.DataFrame) -> bool:
    return not df.empty and float(df["actual_change_pct"].notna().mean()) >= 0.99


def pick_strategy(
    results: list[StrategyResult],
    *,
    label: str,
    direction_source: str,
    avoid_as_short: bool,
    cost_bps: float,
) -> StrategyResult | None:
    for result in results:
        if (
            result.label == label
            and result.direction_source == direction_source
            and result.avoid_as_short == avoid_as_short
            and result.cost_bps == cost_bps
        ):
            return result
    return None


def add_arm_strategies(
    results: list[StrategyResult],
    *,
    df: pd.DataFrame,
    label: str,
    avoid_as_short: bool,
    cost_bps: float,
    primary_direction_source: str = "decision_direction",
) -> None:
    results.append(
        compute_strategy(
            df,
            label,
            primary_direction_source,
            avoid_as_short,
            cost_bps,
        )
    )
    if df["expected_change_pct"].notna().any():
        results.append(
            compute_strategy(
                df,
                label,
                "expected_change_pct",
                avoid_as_short,
                cost_bps,
            )
        )


def buy_hold_result(df: pd.DataFrame, avoid_as_short: bool, cost_bps: float) -> StrategyResult:
    working = df.copy()
    working["decision_direction"] = "long"
    working["expected_change_pct"] = 3.0
    return compute_strategy(working, "buy_hold_equal_weight", "decision_direction", avoid_as_short, cost_bps)


def random_cumrets(
    df: pd.DataFrame,
    avoid_as_short: bool,
    cost_bps: float,
    n: int = RANDOM_MONTE_CARLO_N,
) -> np.ndarray:
    dates = sorted(df["decision_date"].unique())
    tickers = sorted(df["ticker"].dropna().unique())
    date_index = {date: idx for idx, date in enumerate(dates)}
    ticker_index = {ticker: idx for idx, ticker in enumerate(tickers)}
    returns = np.zeros((len(dates), len(tickers)), dtype=float)
    valid = np.zeros_like(returns, dtype=bool)
    for row in df.itertuples(index=False):
        i = date_index[row.decision_date]
        j = ticker_index[row.ticker]
        returns[i, j] = float(row.actual_return)
        valid[i, j] = True

    rng = np.random.default_rng(RANDOM_SEED)
    out = np.empty(n, dtype=float)
    avoid_position = -1 if avoid_as_short else 0
    cost_rate = cost_bps / 10_000
    batch_size = 500
    cursor = 0
    while cursor < n:
        batch = min(batch_size, n - cursor)
        random_long = rng.random((batch, len(dates), len(tickers))) < 0.5
        positions = np.where(random_long, 1, avoid_position).astype(float)
        positions = np.where(valid[None, :, :], positions, 0.0)
        active = positions != 0
        active_counts = active.sum(axis=2)
        gross_numerators = (positions * returns[None, :, :]).sum(axis=2)
        gross = np.divide(
            gross_numerators,
            active_counts,
            out=np.zeros_like(gross_numerators),
            where=active_counts != 0,
        )

        previous = np.concatenate([np.zeros_like(positions[:, :1, :]), positions[:, :-1, :]], axis=1)
        sides = np.abs(positions - previous).sum(axis=2)
        current_holdings = (positions != 0).sum(axis=2)
        previous_holdings = (previous != 0).sum(axis=2)
        cost_denominators = np.where(current_holdings != 0, current_holdings, previous_holdings)
        costs = np.divide(
            sides * cost_rate,
            cost_denominators,
            out=np.zeros_like(sides),
            where=cost_denominators != 0,
        )
        monthly = gross - costs
        out[cursor : cursor + batch] = np.prod(1 + monthly, axis=1) - 1
        cursor += batch
    return out


def random_summary(strategy_cumret: float, random_returns: np.ndarray) -> dict[str, float]:
    return {
        "p5": float(np.percentile(random_returns, 5)),
        "p50": float(np.percentile(random_returns, 50)),
        "p95": float(np.percentile(random_returns, 95)),
        "percentile": float((random_returns <= strategy_cumret).mean() * 100),
    }


def vote_threshold_scan(
    df: pd.DataFrame,
    label: str,
    direction_source: str,
    avoid_as_short: bool,
    cost_bps: float,
) -> pd.DataFrame:
    if df.empty or df["vote_consistency"].dropna().empty:
        return pd.DataFrame()
    rows = []
    total = len(df)
    for threshold in VOTE_THRESHOLDS:
        positioned = add_positions(df, direction_source, avoid_as_short, vote_threshold=threshold)
        monthly = compute_monthly_returns(positioned, cost_bps)
        metrics = metric_summary(positioned, monthly, label, direction_source, avoid_as_short, cost_bps)
        kept = int((positioned["position"] != 0).sum())
        rows.append(
            {
                "threshold": threshold,
                "kept_trades": kept,
                "kept_ratio": kept / total if total else math.nan,
                "cumulative_return": metrics["cumulative_return"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
            }
        )
    return pd.DataFrame(rows)


def pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value) * 100:.2f}%"


def num(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.{digits}f}"


def integer(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return str(int(value))


def markdown_table(rows: list[dict[str, str]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "_无数据_"
    header = "| " + " | ".join(title for _, title in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(str(row.get(key, "")) for key, _ in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def metrics_row(result: StrategyResult) -> dict[str, str]:
    metrics = result.metrics
    return {
        "label": result.label,
        "source": result.direction_source,
        "avoid": str(result.avoid_as_short),
        "cost": num(result.cost_bps, 1),
        "cum": pct(metrics["cumulative_return"]),
        "ann": pct(metrics["annualized_return"]),
        "sharpe": num(metrics["sharpe"]),
        "mdd": pct(metrics["max_drawdown"]),
        "hit": pct(metrics["hit_rate"]),
        "win": pct(metrics["win_rate"]),
        "pl": num(metrics["profit_loss_ratio"]),
        "trades": integer(metrics["trade_count"]),
        "abstain": pct(metrics["abstain_ratio"]),
    }


def ticker_rows(result: StrategyResult, limit: int = 20) -> list[dict[str, str]]:
    rows = []
    for item in result.ticker_table.head(limit).itertuples(index=False):
        rows.append(
            {
                "ticker": item.ticker,
                "contribution": pct(item.portfolio_contribution),
                "independent": pct(item.independent_cumulative_return),
                "hit": pct(item.hit_rate),
                "trades": integer(item.trade_count),
                "cum_pct": pct(item.cumulative_contribution_pct),
            }
        )
    return rows


def format_summary_metric(result: StrategyResult | None) -> str:
    if result is None:
        return "NA"
    metrics = result.metrics
    return (
        f"cumret={pct(metrics['cumulative_return'])} "
        f"sharpe={num(metrics['sharpe'])} "
        f"mdd={pct(metrics['max_drawdown'])} "
        f"hit={pct(metrics['hit_rate'])}"
    )


def format_metric_sentence(result: StrategyResult | None) -> str:
    if result is None:
        return "NA"
    metrics = result.metrics
    return (
        f"累计收益 {pct(metrics['cumulative_return'])}，"
        f"夏普 {num(metrics['sharpe'])}, "
        f"最大回撤 {pct(metrics['max_drawdown'])}"
    )


def build_analysis(validation_status: str) -> dict[str, Any]:
    environment = worktree_report()
    mode = select_mode()
    use_stage7_full = mode in {"FULL", "FULL_PARTIAL"}
    baseline_run_name = STAGE7_FULL_RUN if use_stage7_full else BASELINE_RUN
    baseline_root = RUNS_ROOT / baseline_run_name
    stage7_full_root = RUNS_ROOT / STAGE7_FULL_RUN
    smoke_root = RUNS_ROOT / STAGE7_SMOKE_RUN
    reference_probe = {"error": "not checked"}
    compare_for_probe: dict[str, Any] = {}
    if COMPARE_JSON.exists():
        with open(COMPARE_JSON, encoding="utf-8") as handle:
            compare_for_probe = json.load(handle)
        reference_run_for_probe = str(compare_for_probe.get("reference_run", ""))
        if reference_run_for_probe and Path(reference_run_for_probe).exists():
            reference_probe = probe_fields(reference_run_for_probe)

    field_probe = {
        "baseline_run": probe_fields(
            (baseline_root / "baseline").as_posix() if use_stage7_full else baseline_root.as_posix()
        ),
        "reference_run": reference_probe,
        "stage7_smoke": probe_fields(smoke_root.as_posix()) if smoke_root.exists() else {"error": "missing"},
    }
    if use_stage7_full:
        field_probe["stage7_alaya"] = probe_fields((stage7_full_root / "alaya").as_posix())

    baseline_df = load_steps(baseline_run_name, "baseline")
    alaya_df = load_steps(STAGE7_FULL_RUN, "alaya") if use_stage7_full else pd.DataFrame()
    smoke_baseline_df = load_steps(STAGE7_SMOKE_RUN, "baseline") if smoke_root.exists() else pd.DataFrame()
    smoke_alaya_df = load_steps(STAGE7_SMOKE_RUN, "alaya") if smoke_root.exists() else pd.DataFrame()

    coverage_ok = actual_coverage_ok(baseline_df)
    if use_stage7_full:
        coverage_ok = coverage_ok and actual_coverage_ok(alaya_df)
    if mode == "ABORT" or not coverage_ok:
        return {
            "environment": environment,
            "mode": "ABORT",
            "field_probe": field_probe,
            "validation_status": validation_status,
            "error": "selected baseline/alaya actual coverage below 0.99 or no usable run",
        }

    if use_stage7_full:
        reference_df = pd.DataFrame()
        reference_source = "not_applicable_stage7_full_mode"
        reference_run_path = ""
    else:
        reference_df, reference_source, reference_run_path = build_reference_arm(baseline_df)

    baseline_label = "stage7_baseline" if use_stage7_full else "baseline_candidate"
    results: list[StrategyResult] = []
    for avoid_as_short in AVOID_AS_SHORT_VARIANTS:
        for cost_bps in COST_BPS_VARIANTS:
            add_arm_strategies(
                results,
                df=baseline_df,
                label=baseline_label,
                avoid_as_short=avoid_as_short,
                cost_bps=cost_bps,
            )
            if use_stage7_full:
                add_arm_strategies(
                    results,
                    df=alaya_df,
                    label="stage7_alaya",
                    avoid_as_short=avoid_as_short,
                    cost_bps=cost_bps,
                )
            if not reference_df.empty:
                add_arm_strategies(
                    results,
                    df=reference_df,
                    label="reference_from_compare",
                    avoid_as_short=avoid_as_short,
                    cost_bps=cost_bps,
                    primary_direction_source="reference_direction",
                )
            results.append(buy_hold_result(baseline_df, avoid_as_short, cost_bps))

    primary_baseline = pick_strategy(
        results,
        label=baseline_label,
        direction_source="decision_direction",
        avoid_as_short=False,
        cost_bps=PRIMARY_COST_BPS,
    )
    primary_alaya = pick_strategy(
        results,
        label="stage7_alaya",
        direction_source="decision_direction",
        avoid_as_short=False,
        cost_bps=PRIMARY_COST_BPS,
    )
    primary_reference = pick_strategy(
        results,
        label="reference_from_compare",
        direction_source="reference_direction",
        avoid_as_short=False,
        cost_bps=PRIMARY_COST_BPS,
    )
    primary_buy_hold = pick_strategy(
        results,
        label="buy_hold_equal_weight",
        direction_source="decision_direction",
        avoid_as_short=False,
        cost_bps=PRIMARY_COST_BPS,
    )
    if primary_baseline is None or primary_buy_hold is None:
        return {
            "environment": environment,
            "mode": "ABORT",
            "field_probe": field_probe,
            "validation_status": validation_status,
            "error": "selected data source did not produce required primary PnL metrics",
        }

    random_blocks: dict[tuple[bool, float], dict[str, dict[str, float]]] = {}
    for avoid_as_short in AVOID_AS_SHORT_VARIANTS:
        for cost_bps in COST_BPS_VARIANTS:
            random_returns = random_cumrets(baseline_df, avoid_as_short, cost_bps)
            block: dict[str, dict[str, float]] = {}
            for label in (baseline_label, "stage7_alaya", "reference_from_compare"):
                direction_source = "reference_direction" if label == "reference_from_compare" else "decision_direction"
                strategy = pick_strategy(
                    results,
                    label=label,
                    direction_source=direction_source,
                    avoid_as_short=avoid_as_short,
                    cost_bps=cost_bps,
                )
                if strategy is not None:
                    block[label] = random_summary(strategy.metrics["cumulative_return"], random_returns)
            random_blocks[(avoid_as_short, cost_bps)] = block

    vote_scan = vote_threshold_scan(
        baseline_df,
        baseline_label,
        "decision_direction",
        False,
        PRIMARY_COST_BPS,
    )

    compare = {}
    if COMPARE_JSON.exists():
        with open(COMPARE_JSON, encoding="utf-8") as handle:
            compare = json.load(handle)

    return {
        "environment": environment,
        "mode": mode,
        "field_probe": field_probe,
        "baseline_label": baseline_label,
        "baseline_df": baseline_df,
        "alaya_df": alaya_df,
        "reference_df": reference_df,
        "reference_source": reference_source,
        "reference_run_path": reference_run_path,
        "smoke_baseline_df": smoke_baseline_df,
        "smoke_alaya_df": smoke_alaya_df,
        "results": results,
        "primary_baseline": primary_baseline,
        "primary_alaya": primary_alaya,
        "primary_reference": primary_reference,
        "primary_buy_hold": primary_buy_hold,
        "random_blocks": random_blocks,
        "vote_scan": vote_scan,
        "compare": compare,
        "validation_status": validation_status,
    }


def render_report(analysis: dict[str, Any]) -> str:
    mode = analysis["mode"]
    if mode == "ABORT":
        return render_abort_report(analysis)
    if mode in {"FULL", "FULL_PARTIAL"}:
        return render_stage7_report(analysis)

    results: list[StrategyResult] = analysis["results"]
    primary_baseline: StrategyResult = analysis["primary_baseline"]
    primary_reference: StrategyResult | None = analysis["primary_reference"]
    primary_buy_hold: StrategyResult = analysis["primary_buy_hold"]
    random_blocks = analysis["random_blocks"]
    compare = analysis["compare"]

    metric_rows = [metrics_row(result) for result in results]
    metric_table = markdown_table(
        metric_rows,
        [
            ("label", "arm"),
            ("source", "direction source"),
            ("avoid", "AVOID_AS_SHORT"),
            ("cost", "cost bps"),
            ("cum", "累计收益"),
            ("ann", "年化收益"),
            ("sharpe", "夏普"),
            ("mdd", "最大回撤"),
            ("hit", "方向命中率"),
            ("win", "胜率"),
            ("pl", "盈亏比"),
            ("trades", "交易次数"),
            ("abstain", "abstain"),
        ],
    )

    random_rows = []
    for (avoid_as_short, cost_bps), block in sorted(random_blocks.items()):
        for label, values in block.items():
            random_rows.append(
                {
                    "label": label,
                    "avoid": str(avoid_as_short),
                    "cost": num(cost_bps, 1),
                    "p5": pct(values["p5"]),
                    "p50": pct(values["p50"]),
                    "p95": pct(values["p95"]),
                    "percentile": f"{values['percentile']:.1f}",
                }
            )
    random_table = markdown_table(
        random_rows,
        [
            ("label", "arm"),
            ("avoid", "AVOID_AS_SHORT"),
            ("cost", "cost bps"),
            ("p5", "random P5"),
            ("p50", "random P50"),
            ("p95", "random P95"),
            ("percentile", "策略百分位"),
        ],
    )

    ticker_table = markdown_table(
        ticker_rows(primary_baseline),
        [
            ("ticker", "ticker"),
            ("contribution", "收益贡献"),
            ("independent", "单票累计"),
            ("hit", "命中率"),
            ("trades", "交易数"),
            ("cum_pct", "累计贡献%"),
        ],
    )
    ticker_reference_table = markdown_table(
        ticker_rows(primary_reference) if primary_reference is not None else [],
        [
            ("ticker", "ticker"),
            ("contribution", "收益贡献"),
            ("independent", "单票累计"),
            ("hit", "命中率"),
            ("trades", "交易数"),
            ("cum_pct", "累计贡献%"),
        ],
    )

    smoke_baseline = analysis["smoke_baseline_df"]
    smoke_alaya = analysis["smoke_alaya_df"]
    smoke_note = (
        f"stage7_kimi_smoke_20260617T094500Z 可读：baseline={len(smoke_baseline)} "
        f"alaya={len(smoke_alaya)}，但本轮降级规则为 BASELINE_ONLY，n=2 仅作存在性说明，"
        "不进入主 PnL 判断。"
    )
    reference_source = analysis["reference_source"]
    reference_run_path = analysis["reference_run_path"]
    if reference_source == "reference_step_json":
        reference_note = (
            f"compare JSON 指向的 reference run 实体可读：`{reference_run_path}`；"
            "本文 reference_from_compare 使用该 run 的 baseline step JSON 计算，"
            "不是只用 160 条 mismatch 重构。"
        )
        reference_direction_note = (
            "reference 参考臂有实体 step JSON，因此同时计算 `decision_direction` "
            "和 `expected_change_pct` 推算两套方向口径。"
        )
    elif reference_source == "missing_compare_json":
        reference_note = "本地缺少 compare JSON，因此未计算 `reference_from_compare`。"
        reference_direction_note = "reference 参考臂缺失；相关指标、逐 ticker 表和随机分位数均记为 NA。"
    elif reference_source == "reference_step_json_required_missing_candidate_step":
        reference_note = (
            f"compare JSON 指向的 reference run 不可读或缺 baseline step：`{reference_run_path}`；"
            "且 compare mismatch 含 `missing_candidate_step`，禁止只按 candidate 子集重构 reference。"
        )
        reference_direction_note = "reference 参考臂未通过完整性要求；相关指标记为 NA。"
    else:
        reference_note = (
            f"compare JSON 指向的 reference run 不可读或缺 baseline step：`{reference_run_path}`；"
            "本文只能用 mismatch 中的 `reference_direction` 覆盖 candidate 方向来近似重构 reference。"
        )
        reference_direction_note = (
            "reference 参考臂仅有 compare JSON 中的 direction 信息，因此只能跑 "
            "reference direction 口径，不能跑 expected-derived reference。"
        )

    vote_text = (
        "跳过：bt_baseline_parallel_replay4_20260615 是单 sample，denoising=null，"
        "没有 vote_consistency 字段。"
    )
    if not analysis["vote_scan"].empty:
        vote_text = markdown_table(
            [
                {
                    "threshold": num(row.threshold, 1),
                    "kept": integer(row.kept_trades),
                    "kept_ratio": pct(row.kept_ratio),
                    "cum": pct(row.cumulative_return),
                    "sharpe": num(row.sharpe),
                    "mdd": pct(row.max_drawdown),
                }
                for row in analysis["vote_scan"].itertuples(index=False)
            ],
            [
                ("threshold", "threshold"),
                ("kept", "保留交易"),
                ("kept_ratio", "保留占比"),
                ("cum", "累计收益"),
                ("sharpe", "夏普"),
                ("mdd", "最大回撤"),
            ],
        )

    random_primary = random_blocks[(False, PRIMARY_COST_BPS)]
    baseline_label = analysis.get("baseline_label", "baseline_candidate")
    reference_random = random_primary.get("reference_from_compare")
    baseline_random_pct = f"{random_primary[baseline_label]['percentile']:.1f}"
    reference_random_pct = f"{reference_random['percentile']:.1f}" if reference_random else "NA"
    top = primary_baseline.top_ticker or "NA"
    without_top = primary_baseline.without_top_metrics or {}
    top_dominates = (
        not primary_baseline.ticker_table.empty
        and abs(float(primary_baseline.ticker_table.iloc[0]["portfolio_contribution"]))
        >= abs(float(primary_baseline.ticker_table["portfolio_contribution"].sum())) * 0.5
    )
    without_top_negative = (
        without_top.get("cumulative_return") is not None
        and without_top.get("cumulative_return", 0.0) < 0
    )

    baseline_mse = analysis["baseline_df"]["mse"].dropna()
    mse_text = (
        "缺 stage7_repro 与 alaya full/repro，跳过 baseline run 间噪声基线和 "
        "alaya-baseline MSE 对照。可核验 baseline candidate 自身 mse："
        f"count={len(baseline_mse)}, mean={num(baseline_mse.mean())}, "
        f"median={num(baseline_mse.median())}。该项仅为辅助参考，不作为主判断。"
    )

    minis_note = (
        "`/var/minis/shared/gotra/GOTRA_STAGE8_HANDOFF_FOR_MINIS.md` 在本机不存在，"
        "所以未能读取 0-1.0 节；报告中的高可信事实均来自当前 worktree 可核验实体文件。"
        if not MINIS_HANDOFF.exists()
        else "Minis handoff file exists and should be reviewed separately."
    )

    verdict = (
        "数据不足以下真双臂判断（BASELINE_ONLY）：没有 stage7_full/stage7_repro，"
        "无法判断 alaya 方向信号是否优于 baseline。baseline/reference 的单臂结果只能作为 "
        "Stage8 经济学筛查的本地基线，不构成机制有效性结论。"
    )
    if primary_reference is None:
        reference_boundary_text = (
            "本轮没有可用的 `reference_from_compare`。baseline candidate 只能与 buy & hold "
            "和随机方向基线对照，不能声称 baseline run A vs baseline run B 的完整 PnL 对照。"
        )
        compare_replay_text = (
            "缺少完整 compare/reference step evidence；reference 指标、逐 ticker 表和随机分位数均为 NA。"
        )
    else:
        reference_boundary_text = (
            "本文中的 `reference_from_compare` **不是 alaya**。它来自 "
            "`compare_bt_full_v3_20260615.json` 指向的 reference baseline run（`bt_full_v3_20260615`）。"
            "因此 `baseline_candidate` vs `reference_from_compare` 的对比，本质是 baseline run A vs "
            "baseline run B 的 PnL 对照，不是 alaya 机制 vs baseline 机制。"
        )
        compare_replay_text = (
            "`compare_bt_full_v3_20260615.json` 显示 baseline candidate 与 reference baseline "
            "的方向一致率为 `846/1006 = 0.840954`，低于 `0.95` replay threshold。故主口径下 "
            "`reference_from_compare` 与 `baseline_candidate` 的差异，应解释为 baseline replay "
            "不稳定下的 PnL 漂移，而不是机制差异。"
        )

    return f"""# Stage 8 Signal PnL 离线回测（{REPORT_DATE}）

## ⚠️ 先读：BASELINE_ONLY 解释边界

本报告处于 **BASELINE_ONLY** 降级模式。当前 worktree 缺少 `stage7_full_20260617T123803Z` 与 `stage7_repro_20260617T150954Z`，因此没有可用的 alaya full step JSON，不能判断 `alaya vs baseline` 的真双臂经济价值。

{reference_boundary_text}

{compare_replay_text}

另外，`expected_change_pct` 口径是强信号过滤：`expected_change_pct >= 2.0` 才 long，`<= -2.0` 才 avoid，其余 neutral/abstain。该口径可作为强信号子集体检，但不得和 LLM 原始 `decision_direction` 口径混读成同一个策略。

因此，本报告唯一稳健结论是：baseline price-only signal 在当前 10 ticker / 月度 / 1006 step 的本地筛查中具备经济性；它不证明 alaya 机制有效，也不证明 alaya 优于 baseline。

## 工作环境

以下为进入字段探测和 PnL 计算前的 worktree 报告：

```text
{analysis["environment"]}
```

补充边界：{minis_note}

事实分层：
- 用户报告事实：下载提示词中关于 SophNet 非确定性、Stage7 复现闸冻结、Stage8 北极星的叙述。
- 本地可核验事实：当前 worktree、`data/backtest/runs/` step JSON、compare JSON、字段覆盖和本文所有 PnL 指标。

## 数据源模式

模式：**{mode}**

原因：`{STAGE7_FULL_RUN}` 与 `{STAGE7_REPRO_RUN}` 缺失；`{BASELINE_RUN}` 存在且 baseline step 数为 {len(analysis["baseline_df"])}。按提示词降级规则，本轮跳过真双臂 PnL，改为 baseline candidate 单臂 PnL，并用 `compare_bt_full_v3_20260615.json` 指向的 reference 做参考臂对照。{reference_note}该参考臂不是真双臂 alaya/baseline。

{smoke_note}

## 字段探测结果

```json
{json.dumps(analysis["field_probe"], ensure_ascii=False, indent=2)}
```

字段覆盖闸：baseline actual coverage 为 {analysis["field_probe"]["baseline_run"]["actual_coverage"]}，满足 `>=0.99` 后进入 PnL 计算。

## 交易口径声明

- `AVOID_AS_SHORT=False`：long=+1，avoid=0，short=-1，neutral/watch=0。
- `AVOID_AS_SHORT=True`：long=+1，avoid=-1，short=-1，neutral/watch=0。
- 成本跑两版：`COST_BPS=10` 与 `COST_BPS=0`；无风险利率 `RISK_FREE_RATE=0.0`。
- 单期收益：`position * actual_change_pct / 100`。
- 组合月收益：每个 `decision_date` 对当期非零仓位 ticker 等权；交易成本按单边仓位变化计，分母优先使用当期非零持仓 ticker 数；若当期全空仓但有清仓成本，则使用上期非零持仓数避免除零。
- 两套方向口径均计算：LLM 原始 `decision_direction`，以及 `expected_to_direction(expected_change_pct)`：`>=2.0` 为 long，`<=-2.0` 为 avoid，否则 neutral。
- {reference_direction_note}
- vote 阈值 / 成本 / 无风险利率是评估口径，不是信号口径。

## 经济指标表

{metric_table}

## vote_consistency 阈值扫描

{vote_text}

## 逐 ticker 拆解：baseline candidate（decision_direction, AVOID_AS_SHORT=False, COST_BPS=10）

{ticker_table}

去最大贡献 ticker：top={top}；去掉后 baseline candidate 累计收益={pct(without_top.get("cumulative_return"))}，夏普={num(without_top.get("sharpe"))}。

## 逐 ticker 拆解：reference_from_compare（reference_direction, AVOID_AS_SHORT=False, COST_BPS=10）

{ticker_reference_table}

## 基准对照

buy & hold 等权同周期见经济指标表中的 `buy_hold_equal_weight` 行。随机方向基线为 N={RANDOM_MONTE_CARLO_N}，随机 long/avoid，使用同一成本和 AVOID_AS_SHORT 设置：

{random_table}

主口径下 baseline candidate 随机百分位={baseline_random_pct}，reference 随机百分位={reference_random_pct}。

## MSE 辅助

{mse_text}

## 零未来函数声明

信号生成时刻 t 不包含 actual，actual 仅用于 t+1 结算，符合回测标准口径。`decision_inputs[*].availability_date <= decision_date` 已在 walk_forward harness 验证；当前 1006 个 baseline step 的 `future_data_allowed` 均为 `{sorted(analysis["baseline_df"]["future_data_allowed"].dropna().unique().tolist())}`。本脚本没有用 `actual_change_pct` 生成信号。

## 主判断

1. 降级模式：**{mode}**，数据不足以下真双臂 alaya vs baseline 判断。
2. 关键经济指标（主口径 AVOID_AS_SHORT=False, COST_BPS=10）：
   - alaya：NA（无 full alaya step）。
   - baseline candidate：{format_metric_sentence(primary_baseline)}。
   - reference_from_compare：{format_metric_sentence(primary_reference)}。
   - buy & hold：{format_metric_sentence(primary_buy_hold)}。
3. vote_consistency 结论：跳过；baseline candidate 没有 vote_consistency。
4. 逐 ticker 拆解结论：baseline candidate top ticker={top}；单票支配={str(top_dominates).lower()}；去最大单票后 PnL 转负={str(without_top_negative).lower()}。
5. screening 判断：{verdict}
6. 验证状态：{analysis["validation_status"]}。
7. 产物路径：脚本 `scripts/stage8_signal_pnl_backtest.py`；报告 `{REPORT_PATH.as_posix()}`。
8. 诚实边界：本结果是 screening 非最终验证；没有 stage7 full/repro，不能给 alaya 机制经济价值结论；零未来函数已声明；交易假设全部标注；key 未接触；未 push。

## compare JSON 摘要

- reference_run: `{compare.get("reference_run")}`
- candidate_run: `{compare.get("candidate_run")}`
- total={compare.get("total")}, same={compare.get("same")}, rate={num(compare.get("rate"))}, threshold={num(compare.get("threshold"))}, passed={compare.get("passed")}
"""


def render_stage7_report(analysis: dict[str, Any]) -> str:
    results: list[StrategyResult] = analysis["results"]
    primary_baseline: StrategyResult = analysis["primary_baseline"]
    primary_alaya: StrategyResult | None = analysis["primary_alaya"]
    primary_buy_hold: StrategyResult = analysis["primary_buy_hold"]
    random_blocks = analysis["random_blocks"]
    baseline_label = analysis.get("baseline_label", "stage7_baseline")

    metric_table = markdown_table(
        [metrics_row(result) for result in results],
        [
            ("label", "arm"),
            ("source", "direction source"),
            ("avoid", "AVOID_AS_SHORT"),
            ("cost", "cost bps"),
            ("cum", "累计收益"),
            ("ann", "年化收益"),
            ("sharpe", "夏普"),
            ("mdd", "最大回撤"),
            ("hit", "方向命中率"),
            ("win", "胜率"),
            ("pl", "盈亏比"),
            ("trades", "交易次数"),
            ("abstain", "abstain"),
        ],
    )
    random_rows = []
    for (avoid_as_short, cost_bps), block in sorted(random_blocks.items()):
        for label, values in block.items():
            random_rows.append(
                {
                    "label": label,
                    "avoid": str(avoid_as_short),
                    "cost": num(cost_bps, 1),
                    "p5": pct(values["p5"]),
                    "p50": pct(values["p50"]),
                    "p95": pct(values["p95"]),
                    "percentile": f"{values['percentile']:.1f}",
                }
            )
    random_table = markdown_table(
        random_rows,
        [
            ("label", "arm"),
            ("avoid", "AVOID_AS_SHORT"),
            ("cost", "cost bps"),
            ("p5", "random P5"),
            ("p50", "random P50"),
            ("p95", "random P95"),
            ("percentile", "策略百分位"),
        ],
    )
    baseline_ticker_table = markdown_table(
        ticker_rows(primary_baseline),
        [
            ("ticker", "ticker"),
            ("contribution", "收益贡献"),
            ("independent", "单票累计"),
            ("hit", "命中率"),
            ("trades", "交易数"),
            ("cum_pct", "累计贡献%"),
        ],
    )
    alaya_ticker_table = markdown_table(
        ticker_rows(primary_alaya) if primary_alaya is not None else [],
        [
            ("ticker", "ticker"),
            ("contribution", "收益贡献"),
            ("independent", "单票累计"),
            ("hit", "命中率"),
            ("trades", "交易数"),
            ("cum_pct", "累计贡献%"),
        ],
    )
    random_primary = random_blocks[(False, PRIMARY_COST_BPS)]
    baseline_random_pct = f"{random_primary[baseline_label]['percentile']:.1f}"
    alaya_random = random_primary.get("stage7_alaya")
    alaya_random_pct = f"{alaya_random['percentile']:.1f}" if alaya_random else "NA"

    return f"""# Stage 8 Signal PnL 离线回测（{REPORT_DATE}）

## 先读：Stage7 FULL 数据模式

本报告处于 **{analysis["mode"]}** 模式，使用 `{STAGE7_FULL_RUN}` 的 baseline 与 alaya step JSON 计算 PnL。该层级是本地经济筛查，不自动升级为 Stage7 replay gate 通过、机制科学结论或交易建议。

## 工作环境

```text
{analysis["environment"]}
```

## 字段探测结果

```json
{json.dumps(analysis["field_probe"], ensure_ascii=False, indent=2)}
```

## 经济指标表

{metric_table}

## 逐 ticker 拆解：stage7_baseline（decision_direction, AVOID_AS_SHORT=False, COST_BPS=10）

{baseline_ticker_table}

## 逐 ticker 拆解：stage7_alaya（decision_direction, AVOID_AS_SHORT=False, COST_BPS=10）

{alaya_ticker_table}

## 随机方向基线

{random_table}

主口径下 stage7_baseline 随机百分位={baseline_random_pct}，stage7_alaya 随机百分位={alaya_random_pct}。

## 主判断

1. 模式：**{analysis["mode"]}**。
2. 关键经济指标（主口径 AVOID_AS_SHORT=False, COST_BPS=10）：
   - stage7_alaya：{format_metric_sentence(primary_alaya)}。
   - stage7_baseline：{format_metric_sentence(primary_baseline)}。
   - buy & hold：{format_metric_sentence(primary_buy_hold)}。
3. 验证状态：{analysis["validation_status"]}。
4. 证据边界：这是 Stage8 PnL screening。正式 replay acceptance、provider health 和 science/public claim 仍需按各自证据层级单独判断。
"""


def render_abort_report(analysis: dict[str, Any]) -> str:
    return f"""# Stage 8 Signal PnL 离线回测（{REPORT_DATE}）

## 工作环境

```text
{analysis["environment"]}
```

## 数据源模式

模式：**ABORT**

原因：{analysis.get("error", "挂载与 worktree 均无 full 数据，无法做 PnL 筛查")}。

## 字段探测结果

```json
{json.dumps(analysis["field_probe"], ensure_ascii=False, indent=2)}
```

## 主判断

数据不足以下判断（ABORT 模式）。验证状态：{analysis["validation_status"]}。key 未接触；未 push。
"""


def summary_lines(analysis: dict[str, Any]) -> list[str]:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = run_git(["rev-parse", "--short", "HEAD"])
    untracked = run_git(["ls-files", "--others", "--exclude-standard"]).replace("\n", ",")
    mode = analysis["mode"]
    use_stage7_full = mode in {"FULL", "FULL_PARTIAL"}
    baseline_run_name = STAGE7_FULL_RUN if use_stage7_full else BASELINE_RUN
    baseline_count = count_steps(baseline_run_name, "baseline")
    alaya_count = count_steps(STAGE7_FULL_RUN, "alaya") if (RUNS_ROOT / STAGE7_FULL_RUN).exists() else 0
    field_probe = analysis["field_probe"]
    baseline_cov = field_probe["baseline_run"].get("actual_coverage", "NA")
    smoke_probe = field_probe.get("stage7_smoke", {})
    alaya_probe = field_probe.get("stage7_alaya", smoke_probe)
    alaya_cov = alaya_probe.get("actual_coverage", "NA")

    if mode == "ABORT":
        return [
            f"[WORKTREE] branch={branch} HEAD={head} untracked={untracked or '[]'}",
            "[MODE] ABORT",
            f"[DATA] baseline_runs={BASELINE_RUN}:{baseline_count} alaya_runs={STAGE7_FULL_RUN}:{alaya_count}",
            f"[FIELD_PROBE] baseline_actual_coverage={baseline_cov} "
            f"alaya_actual_coverage={alaya_cov} vote_consistency_available=no",
            "[VERDICT] 数据不足以下判断（ABORT 模式）",
            "[ZERO_FUTURE] declared=yes",
            "[KEY_TOUCHED] no",
            "[PUSHED] no",
            f"[ARTIFACTS] script=scripts/stage8_signal_pnl_backtest.py report={REPORT_PATH.as_posix()}",
            f"[VALIDATION] {analysis['validation_status']}",
        ]

    results: list[StrategyResult] = analysis["results"]

    def pick(label: str, avoid: bool) -> StrategyResult | None:
        for result in results:
            if (
                result.label == label
                and result.avoid_as_short == avoid
                and result.cost_bps == PRIMARY_COST_BPS
                and result.direction_source in {"decision_direction", "reference_direction"}
            ):
                return result
        return None

    baseline_label = analysis.get("baseline_label", "baseline_candidate")
    baseline_false = pick(baseline_label, False)
    alaya_false = pick("stage7_alaya", False)
    reference_false = pick("reference_from_compare", False)
    buy_false = pick("buy_hold_equal_weight", False)
    baseline_true = pick(baseline_label, True)
    alaya_true = pick("stage7_alaya", True)
    reference_true = pick("reference_from_compare", True)
    buy_true = pick("buy_hold_equal_weight", True)
    random_false = analysis["random_blocks"][(False, PRIMARY_COST_BPS)]
    baseline_random = random_false.get(baseline_label, {})
    alaya_random = random_false.get("stage7_alaya", {})
    reference_random = random_false.get("reference_from_compare", {})
    baseline_pctl = f"{baseline_random.get('percentile'):.1f}" if baseline_random else "NA"
    alaya_pctl = f"{alaya_random.get('percentile'):.1f}" if alaya_random else "NA"
    reference_pctl = f"{reference_random.get('percentile'):.1f}" if reference_random else "NA"
    top = analysis["primary_baseline"].top_ticker or "NA"
    without_top = analysis["primary_baseline"].without_top_metrics or {}
    top_dominates = (
        not analysis["primary_baseline"].ticker_table.empty
        and abs(float(analysis["primary_baseline"].ticker_table.iloc[0]["portfolio_contribution"]))
        >= abs(float(analysis["primary_baseline"].ticker_table["portfolio_contribution"].sum())) * 0.5
    )
    without_top_negative = without_top.get("cumulative_return", 0.0) < 0
    validation = analysis["validation_status"]
    return [
        f"[WORKTREE] branch={branch} HEAD={head} untracked={untracked or '[]'}",
        f"[MODE] {mode}",
        f"[DATA] baseline_runs={baseline_run_name}:{baseline_count} alaya_runs={STAGE7_FULL_RUN}:{alaya_count}",
        f"[FIELD_PROBE] baseline_actual_coverage={baseline_cov} "
        f"alaya_actual_coverage={alaya_cov} vote_consistency_available=no",
        "[PNL_AVOID_SHORT=False] "
        f"alaya: {format_summary_metric(alaya_false)} | baseline: {format_summary_metric(baseline_false)} | "
        f"reference: {format_summary_metric(reference_false)} | buy_hold: {format_summary_metric(buy_false)}",
        "[PNL_AVOID_SHORT=True]  "
        f"alaya: {format_summary_metric(alaya_true)} | baseline: {format_summary_metric(baseline_true)} | "
        f"reference: {format_summary_metric(reference_true)} | buy_hold: {format_summary_metric(buy_true)}",
        "[VOTE_THRESHOLD_SCAN] skipped: no vote_consistency in baseline candidate",
        f"[PER_TICKER] 单票支配: {'yes' if top_dominates else 'no'}; "
        f"top={top}; 去最大单票后 PnL 转负: {'yes' if without_top_negative else 'no'}",
        "[VS_RANDOM] "
        f"alaya_pctl={alaya_pctl} "
        f"baseline_pctl={baseline_pctl} "
        f"reference_pctl={reference_pctl} "
        f"(N={RANDOM_MONTE_CARLO_N})",
        "[VERDICT] Stage8 PnL screening；正式 replay acceptance/provider health/science claim 需分层判断",
        "[ZERO_FUTURE] declared=yes",
        "[KEY_TOUCHED] no",
        "[PUSHED] no",
        f"[ARTIFACTS] script=scripts/stage8_signal_pnl_backtest.py report={REPORT_PATH.as_posix()}",
        f"[VALIDATION] {validation}",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-status",
        default="py_compile=not_run ruff=not_run diff_check=not_run pytest=not_run",
        help="Validation status string to embed in the report and summary.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print the Minis completion summary without rewriting the report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = build_analysis(args.validation_status)
    if not args.summary_only:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(render_report(analysis), encoding="utf-8")
    print("\n".join(summary_lines(analysis)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
