"""Quarterly-first Phase BT walk-forward runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from gotra.backtest.audit import audit_run
from gotra.backtest.budget import BudgetExceeded, TokenBudget, estimate_tokens
from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import (
    DEFAULT_END,
    DEFAULT_START,
    SAMPLED_STEP_MONTHS,
    WINDOW_DAYS,
    TickerSpec,
    decision_dates,
    parse_date,
    selected_universe,
    style_window_for,
    ticker_slug,
)
from gotra.backtest.report import write_backtest_report
from gotra.backtest.statistics import summarize_steps


Arm = Literal["baseline", "alaya"]
ProviderName = Literal["heuristic"]
RunMode = Literal["sampled", "full"]


@dataclass(frozen=True)
class BacktestConfig:
    data_dir: Path = Path("data/backtest")
    run_id: str = ""
    mode: RunMode = "sampled"
    provider: ProviderName = "heuristic"
    start: date = DEFAULT_START
    end: date = DEFAULT_END
    step_months: int = SAMPLED_STEP_MONTHS
    tickers: tuple[TickerSpec, ...] = selected_universe()
    window_days: int = WINDOW_DAYS
    token_budget: int | None = None
    max_steps: int | None = None


@dataclass(frozen=True)
class Decision:
    direction: str
    expected_change_pct: float
    confidence: float
    reasoning: str
    prompt_hash: str
    estimated_tokens: int
    cache_hit: bool


class DecisionCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.values = self._load()

    def get(self, key: str) -> dict[str, Any] | None:
        value = self.values.get(key)
        return dict(value) if isinstance(value, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, indent=2, sort_keys=True), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))


class HeuristicDecisionProvider:
    """Deterministic provider for sampled correctness validation.

    This provider is intentionally local and non-networked. It validates the Phase BT
    cache/audit/budget/report chain without claiming to prove the preregistered LLM hypothesis.
    """

    network_enabled = False

    def decide(
        self,
        *,
        ticker: str,
        arm: Arm,
        decision_date: date,
        price_rows: pd.DataFrame,
        feedback: list[dict[str, Any]],
        cache: DecisionCache,
        budget: TokenBudget,
    ) -> Decision:
        features = _price_features(price_rows)
        prompt_payload = {
            "ticker": ticker,
            "arm": arm,
            "decision_date": decision_date.isoformat(),
            "features": features,
            "feedback": feedback if arm == "alaya" else [],
            "provider": "heuristic",
            "version": "bt-sampled-v1",
        }
        prompt = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_key = f"{ticker}:{decision_date.isoformat()}:{arm}:heuristic:{prompt_hash}"
        cached = cache.get(cache_key)
        token_estimate = estimate_tokens(prompt)
        budget.charge(
            cache_key=cache_key,
            estimated_tokens=token_estimate,
            cache_hit=cached is not None,
        )
        if cached is not None:
            return Decision(
                direction=str(cached["direction"]),
                expected_change_pct=float(cached["expected_change_pct"]),
                confidence=float(cached["confidence"]),
                reasoning=str(cached["reasoning"]),
                prompt_hash=prompt_hash,
                estimated_tokens=token_estimate,
                cache_hit=True,
            )

        expected = 0.55 * features["return_63d_pct"] + 0.45 * features["return_21d_pct"]
        if arm == "alaya" and feedback:
            recent_errors = [float(item["error"]) for item in feedback[-6:] if item.get("error") is not None]
            if recent_errors:
                expected += 0.35 * sum(recent_errors) / len(recent_errors)
        expected = round(max(min(expected, 25.0), -25.0), 4)
        direction = "long" if expected >= 2.0 else "avoid" if expected <= -2.0 else "watch"
        confidence = round(min(0.85, 0.45 + abs(expected) / 50 + min(len(feedback), 6) * 0.015), 4)
        reasoning = (
            "deterministic sampled validation; uses trailing adjusted-close momentum"
            + (" plus matured prior error feedback" if arm == "alaya" else "")
        )
        cache.set(
            cache_key,
            {
                "direction": direction,
                "expected_change_pct": expected,
                "confidence": confidence,
                "reasoning": reasoning,
            },
        )
        return Decision(
            direction=direction,
            expected_change_pct=expected,
            confidence=confidence,
            reasoning=reasoning,
            prompt_hash=prompt_hash,
            estimated_tokens=token_estimate,
            cache_hit=False,
        )


def run_backtest(config: BacktestConfig) -> dict[str, Any]:
    _enforce_backtest_env()
    run_id = config.run_id or datetime.now(UTC).strftime("bt_%Y%m%dT%H%M%SZ")
    run_root = config.data_dir / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    for arm in ("baseline", "alaya"):
        (run_root / arm).mkdir(parents=True, exist_ok=True)

    cache = DecisionCache(config.data_dir / "runs" / "decision_cache.json")
    budget = TokenBudget.from_env(config.token_budget)
    provider = HeuristicDecisionProvider()
    steps: list[dict[str, Any]] = []
    feedback_by_ticker: dict[str, list[dict[str, Any]]] = {}
    skipped: list[dict[str, Any]] = []
    budget_error = ""

    try:
        for decision_date in decision_dates(
            start=config.start,
            end=config.end,
            step_months=config.step_months,
        ):
            for ticker in config.tickers:
                if config.max_steps is not None and len(steps) >= config.max_steps:
                    break
                ticker_steps = _run_ticker_step(
                    ticker=ticker,
                    decision_date=decision_date,
                    config=config,
                    provider=provider,
                    cache=cache,
                    budget=budget,
                    feedback_by_ticker=feedback_by_ticker,
                    run_root=run_root,
                    skipped=skipped,
                )
                steps.extend(ticker_steps)
            if config.max_steps is not None and len(steps) >= config.max_steps:
                break
    except BudgetExceeded as exc:
        budget_error = str(exc)

    audit = audit_run(run_root)
    metrics = summarize_steps(steps)
    system_health = _build_system_health(
        budget=budget,
        budget_error=budget_error,
        audit_ok=audit.ok,
        run_mode=config.mode,
        provider=config.provider,
    )
    (run_root / "system_health.json").write_text(
        json.dumps(system_health, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    summary = {
        "run_id": run_id,
        "mode": config.mode,
        "provider": config.provider,
        "sampled_validation_only": config.mode == "sampled" or config.provider == "heuristic",
        "start": config.start.isoformat(),
        "end": config.end.isoformat(),
        "step_months": config.step_months,
        "tickers": [ticker.symbol for ticker in config.tickers],
        "window_days": config.window_days,
        "steps_written": len(steps),
        "skipped": skipped,
        "paused": bool(budget_error),
        "pause_reason": budget_error,
        "price_cache_network_after_cache": False,
        "perplexity_disabled": True,
        "token_budget": budget.snapshot(),
        "system_health": system_health,
        "audit": audit.to_dict(),
        "metrics": metrics,
    }
    report_path, chart_path = write_backtest_report(
        data_dir=config.data_dir,
        run_root=run_root,
        summary=summary,
        steps=steps,
    )
    summary["report_path"] = str(report_path)
    summary["chart_path"] = str(chart_path)
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _build_system_health(
    *,
    budget: TokenBudget,
    budget_error: str,
    audit_ok: bool,
    run_mode: RunMode,
    provider: ProviderName,
) -> dict[str, Any]:
    alerts: list[str] = []
    if budget_error:
        alerts.append(budget_error)
    if not audit_ok and not budget_error:
        alerts.append("future-function audit failed")
    return {
        "status": "paused" if budget_error else "failed" if not audit_ok else "ok",
        "paused": bool(budget_error),
        "pause_reason": budget_error,
        "alerts": alerts,
        "run_mode": run_mode,
        "provider": provider,
        "sampled_validation_only": run_mode == "sampled" or provider == "heuristic",
        "token_budget": budget.snapshot(),
    }


def _run_ticker_step(
    *,
    ticker: TickerSpec,
    decision_date: date,
    config: BacktestConfig,
    provider: HeuristicDecisionProvider,
    cache: DecisionCache,
    budget: TokenBudget,
    feedback_by_ticker: dict[str, list[dict[str, Any]]],
    run_root: Path,
    skipped: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if decision_date < ticker.listing_date:
        skipped.append(
            {
                "ticker": ticker.symbol,
                "decision_date": decision_date.isoformat(),
                "reason": "listed_after_decision_date",
            }
        )
        return []

    prices = read_price_cache(ticker.symbol, price_dir=config.data_dir / "prices")
    decision_slice = _rows_on_or_before(prices, decision_date)
    start_row = _row_on_or_after(prices, decision_date)
    outcome_date = decision_date + timedelta(days=config.window_days)
    end_row = _row_on_or_after(prices, outcome_date)
    if decision_slice.empty or start_row is None or end_row is None:
        skipped.append(
            {
                "ticker": ticker.symbol,
                "decision_date": decision_date.isoformat(),
                "reason": "insufficient_price_history",
            }
        )
        return []

    steps: list[dict[str, Any]] = []
    matured_feedback = [
        item
        for item in feedback_by_ticker.get(ticker.symbol, [])
        if parse_date(item["outcome_availability_date"]) <= decision_date
    ]
    for arm in ("baseline", "alaya"):
        decision = provider.decide(
            ticker=ticker.symbol,
            arm=arm,  # type: ignore[arg-type]
            decision_date=decision_date,
            price_rows=decision_slice,
            feedback=matured_feedback if arm == "alaya" else [],
            cache=cache,
            budget=budget,
        )
        actual_change = _change_pct(float(start_row["adj_close"]), float(end_row["adj_close"]))
        error = round(actual_change - decision.expected_change_pct, 6)
        mse = round(error * error, 6)
        step = _build_step(
            ticker=ticker,
            arm=arm,  # type: ignore[arg-type]
            decision_date=decision_date,
            outcome_date=outcome_date,
            start_row=start_row,
            end_row=end_row,
            decision_slice=decision_slice,
            decision=decision,
            actual_change_pct=actual_change,
            error=error,
            mse=mse,
            feedback=matured_feedback if arm == "alaya" else [],
            provider=provider,
            config=config,
        )
        _write_step(run_root, step)
        _append_event(run_root, step)
        steps.append(step)
        if arm == "alaya":
            feedback_by_ticker.setdefault(ticker.symbol, []).append(
                {
                    "decision_date": decision_date.isoformat(),
                    "outcome_availability_date": step["outcome_as_of"],
                    "error": error,
                    "actual_change_pct": actual_change,
                    "expected_change_pct": decision.expected_change_pct,
                }
            )
    return steps


def _build_step(
    *,
    ticker: TickerSpec,
    arm: Arm,
    decision_date: date,
    outcome_date: date,
    start_row: pd.Series,
    end_row: pd.Series,
    decision_slice: pd.DataFrame,
    decision: Decision,
    actual_change_pct: float,
    error: float,
    mse: float,
    feedback: list[dict[str, Any]],
    provider: HeuristicDecisionProvider,
    config: BacktestConfig,
) -> dict[str, Any]:
    latest_decision_row = decision_slice.iloc[-1]
    decision_inputs = [
        {
            "name": "adjusted_close_history",
            "kind": "price",
            "source": str(latest_decision_row["source_url"]),
            "availability_date": str(latest_decision_row["date"]),
            "rows": int(len(decision_slice)),
        }
    ]
    for index, item in enumerate(feedback):
        decision_inputs.append(
            {
                "name": f"matured_feedback_{index}",
                "kind": "alaya_feedback",
                "source": "prior_step_outcome",
                "availability_date": item["outcome_availability_date"],
            }
        )
    outcome_inputs = [
        {
            "name": "outcome_adjusted_close",
            "kind": "price",
            "source": str(end_row["source_url"]),
            "availability_date": str(end_row["date"]),
        }
    ]
    return {
        "schema": "gotra.bt.step.v1",
        "run_mode": config.mode,
        "status": "scored",
        "ticker": ticker.symbol,
        "ticker_name": ticker.name,
        "arm": arm,
        "decision_date": decision_date.isoformat(),
        "window_days": config.window_days,
        "window_end_date": outcome_date.isoformat(),
        "outcome_as_of": str(end_row["date"]),
        "decision_direction": decision.direction,
        "expected_change_pct": decision.expected_change_pct,
        "actual_change_pct": actual_change_pct,
        "error": error,
        "mse": mse,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "prompt_hash": decision.prompt_hash,
        "estimated_tokens": decision.estimated_tokens,
        "cache_hit": decision.cache_hit,
        "provider": config.provider,
        "provider_network_enabled": provider.network_enabled,
        "style_window": style_window_for(decision_date),
        "decision_inputs": decision_inputs,
        "outcome_inputs": outcome_inputs,
        "future_data_allowed": False,
        "audit_actor": "backtest/walk_forward",
    }


def _write_step(run_root: Path, step: dict[str, Any]) -> None:
    arm_dir = run_root / str(step["arm"])
    filename = f"step_{step['decision_date']}_{ticker_slug(step['ticker'])}.json"
    (arm_dir / filename).write_text(
        json.dumps(step, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _append_event(run_root: Path, step: dict[str, Any]) -> None:
    event = {
        "actor": "backtest/walk_forward",
        "event_type": "bt_step_scored",
        "ticker": step["ticker"],
        "arm": step["arm"],
        "decision_date": step["decision_date"],
        "mse": step["mse"],
        "created_at": datetime.now(UTC).isoformat(),
    }
    with (run_root / "event_log.jsonl").open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _price_features(rows: pd.DataFrame) -> dict[str, float]:
    closes = [float(value) for value in rows["adj_close"].tolist()]
    latest = closes[-1]
    return {
        "return_21d_pct": _trailing_return(closes, latest=latest, days=21),
        "return_63d_pct": _trailing_return(closes, latest=latest, days=63),
        "history_rows": float(len(closes)),
    }


def _trailing_return(closes: list[float], *, latest: float, days: int) -> float:
    if len(closes) <= days:
        return 0.0
    past = closes[-days - 1]
    return _change_pct(past, latest)


def _change_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return round((end - start) / start * 100, 6)


def _rows_on_or_before(frame: pd.DataFrame, target: date) -> pd.DataFrame:
    dates = pd.to_datetime(frame["date"]).dt.date
    return frame.loc[dates <= target].reset_index(drop=True)


def _row_on_or_after(frame: pd.DataFrame, target: date) -> pd.Series | None:
    dates = pd.to_datetime(frame["date"]).dt.date
    filtered = frame.loc[dates >= target]
    if filtered.empty:
        return None
    return filtered.iloc[0]


def _enforce_backtest_env() -> None:
    if os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY"):
        raise RuntimeError("Phase BT must run with Perplexity API keys unset")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase BT walk-forward backtest.")
    parser.add_argument("--data-dir", default="data/backtest")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mode", choices=["sampled", "full"], default="sampled")
    parser.add_argument("--provider", choices=["heuristic"], default="heuristic")
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument("--step-months", type=int, default=SAMPLED_STEP_MONTHS)
    parser.add_argument("--tickers", default="")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    parser.add_argument("--token-budget", type=int)
    parser.add_argument("--max-steps", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    symbols = [item.strip() for item in args.tickers.split(",") if item.strip()]
    summary = run_backtest(
        BacktestConfig(
            data_dir=Path(args.data_dir),
            run_id=args.run_id,
            mode=args.mode,
            provider=args.provider,
            start=parse_date(args.start),
            end=parse_date(args.end),
            step_months=args.step_months,
            tickers=selected_universe(symbols),
            window_days=args.window_days,
            token_budget=args.token_budget,
            max_steps=args.max_steps,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary.get("paused"):
        return 2
    if not (summary.get("audit") or {}).get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
