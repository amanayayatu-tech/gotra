"""Diagnostic Kimi reproducibility probe for hard Stage 6 BT points."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from gotra.backtest.budget import estimate_tokens
from gotra.backtest.kimi_client import (
    DEFAULT_KIMI_MODEL,
    DEFAULT_SOPHNET_BASE_URL,
    KimiCompletionClient,
    load_env_file,
)
from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import TickerSpec, parse_date, selected_universe, style_window_for
from gotra.backtest.walk_forward import (
    BT_CODEX_SYSTEM_PROMPT,
    FULL_PROMPT_VERSION,
    ProviderSample,
    _aggregate_denoising_samples,
    _build_codex_prompt_payload,
    _change_pct,
    _completion_text_and_usage,
    _parse_decision_json,
    _row_on_or_after,
    _rows_on_or_before,
    _rounded,
)


DEFAULT_POINTS_FILE = Path("data/backtest/kimi_hk_error_points_20260616.txt")
DEFAULT_OUTPUT_NAME = "kimi_probe_compare.json"


@dataclass(frozen=True)
class DecisionPoint:
    ticker: str
    decision_date: date


@dataclass(frozen=True)
class ProbeConfig:
    data_dir: Path
    points_file: Path
    run_prefix: str
    sample_count: int
    dead_zone_epsilon_pct: float
    timeout_seconds: int
    sample_retries: int
    decision_concurrency: int
    sample_concurrency: int
    max_connections: int
    model: str
    base_url: str
    env_file: Path | None
    output_name: str


class RunStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[dict[str, Any]] = []

    def record_call(
        self,
        *,
        phase: str,
        ok: bool,
        elapsed_ms: int,
        error_type: str = "",
    ) -> None:
        with self._lock:
            self._calls.append(
                {
                    "phase": phase,
                    "ok": ok,
                    "elapsed_ms": elapsed_ms,
                    "error_type": error_type,
                }
            )

    def snapshot(self, *, planned_samples: int) -> dict[str, Any]:
        with self._lock:
            calls = list(self._calls)
        return {
            "planned_samples": planned_samples,
            **_provider_call_stats(calls),
            "by_phase": {
                phase: _provider_call_stats([call for call in calls if call["phase"] == phase])
                for phase in sorted({str(call["phase"]) for call in calls})
            },
        }


_EVENT_LOCK = threading.Lock()


def run_probe(config: ProbeConfig) -> dict[str, Any]:
    if config.env_file is not None:
        load_env_file(config.env_file)

    points = load_decision_points(config.points_file)
    tickers_by_symbol = {ticker.symbol: ticker for ticker in selected_universe()}
    client = KimiCompletionClient(base_url=config.base_url, model=config.model)
    call_limiter = threading.BoundedSemaphore(max(1, config.max_connections))
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_roots = [
        config.data_dir / "runs" / f"{config.run_prefix}_run1_{timestamp}",
        config.data_dir / "runs" / f"{config.run_prefix}_run2_{timestamp}",
    ]

    run_summaries = [
        _run_one_replay(
            run_root=run_root,
            run_index=index + 1,
            points=points,
            tickers_by_symbol=tickers_by_symbol,
            client=client,
            call_limiter=call_limiter,
            config=config,
        )
        for index, run_root in enumerate(run_roots)
    ]
    compare = compare_probe_runs(run_roots[0], run_roots[1], points=points)
    result = {
        "schema": "gotra.bt.kimi_probe_compare.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "probe": {
            "model": config.model,
            "base_url": config.base_url,
            "temperature": 0.0,
            "sample_count": config.sample_count,
            "decision_concurrency": config.decision_concurrency,
            "sample_concurrency": config.sample_concurrency,
            "max_connections": config.max_connections,
            "dead_zone_epsilon_pct": config.dead_zone_epsilon_pct,
            "prompt_version": FULL_PROMPT_VERSION,
            "system_prompt": "BT_CODEX_SYSTEM_PROMPT",
            "points_file": str(config.points_file),
            "gpt55_reference_rate": 0.8421052631578947,
        },
        "run_summaries": run_summaries,
        "comparison": compare,
    }
    output_path = config.data_dir / "runs" / config.output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return result


def load_decision_points(path: Path) -> list[DecisionPoint]:
    points: list[DecisionPoint] = []
    seen: set[tuple[str, date]] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            raise ValueError(f"{path}:{line_number}: expected TICKER,YYYY-MM-DD")
        ticker = parts[0].upper()
        decision_date = parse_date(parts[1])
        key = (ticker, decision_date)
        if key not in seen:
            seen.add(key)
            points.append(DecisionPoint(ticker=ticker, decision_date=decision_date))
    if not points:
        raise ValueError(f"no decision points loaded from {path}")
    return points


def compare_probe_runs(
    reference_run: Path,
    candidate_run: Path,
    *,
    points: list[DecisionPoint],
) -> dict[str, Any]:
    reference = _load_probe_steps(reference_run)
    candidate = _load_probe_steps(candidate_run)
    rows: list[dict[str, Any]] = []
    same = 0
    same_hk = 0
    total_hk = 0
    for point in points:
        key = (point.ticker, point.decision_date.isoformat())
        reference_step = reference.get(key)
        candidate_step = candidate.get(key)
        row = {
            "ticker": point.ticker,
            "decision_date": point.decision_date.isoformat(),
            "reference_direction": None,
            "candidate_direction": None,
            "reference_expected_change_pct": None,
            "candidate_expected_change_pct": None,
            "agreement": False,
            "reason": "",
        }
        if reference_step is None or candidate_step is None:
            row["reason"] = "missing_step"
        else:
            reference_direction = reference_step.get("decision_direction")
            candidate_direction = candidate_step.get("decision_direction")
            row.update(
                {
                    "reference_direction": reference_direction,
                    "candidate_direction": candidate_direction,
                    "reference_expected_change_pct": reference_step.get("expected_change_pct"),
                    "candidate_expected_change_pct": candidate_step.get("expected_change_pct"),
                    "reference_raw_median_expected_change_pct": (
                        reference_step.get("denoising") or {}
                    ).get("raw_median_expected_change_pct"),
                    "candidate_raw_median_expected_change_pct": (
                        candidate_step.get("denoising") or {}
                    ).get("raw_median_expected_change_pct"),
                    "agreement": reference_direction == candidate_direction,
                    "reason": "direction_match"
                    if reference_direction == candidate_direction
                    else "direction_mismatch",
                }
            )
            if row["agreement"]:
                same += 1
        if point.ticker.endswith(".HK"):
            total_hk += 1
            if row["agreement"]:
                same_hk += 1
        rows.append(row)

    total = len(points)
    return {
        "reference_run": str(reference_run),
        "candidate_run": str(candidate_run),
        "same": same,
        "total": total,
        "rate": same / total if total else None,
        "hk_same": same_hk,
        "hk_total": total_hk,
        "hk_rate": same_hk / total_hk if total_hk else None,
        "mismatches": [row for row in rows if not row["agreement"]],
        "points": rows,
    }


def _run_one_replay(
    *,
    run_root: Path,
    run_index: int,
    points: list[DecisionPoint],
    tickers_by_symbol: dict[str, TickerSpec],
    client: KimiCompletionClient,
    call_limiter: threading.BoundedSemaphore,
    config: ProbeConfig,
) -> dict[str, Any]:
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "baseline").mkdir(parents=True, exist_ok=True)
    steps_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    stats = RunStats()
    started = time.perf_counter()
    indexed_points = list(enumerate(points, 1))
    with ThreadPoolExecutor(max_workers=max(1, config.decision_concurrency)) as executor:
        futures = {
            executor.submit(
                _score_indexed_point,
                indexed_point=indexed_point,
                run_root=run_root,
                run_index=run_index,
                tickers_by_symbol=tickers_by_symbol,
                client=client,
                call_limiter=call_limiter,
                config=config,
                sample_concurrency=config.sample_concurrency,
                stats=stats,
                phase="aggressive",
            ): indexed_point
            for indexed_point in indexed_points
        }
        for future in as_completed(futures):
            point, step = future.result()
            steps_by_key[(point.ticker, point.decision_date.isoformat())] = step
            _write_json(_step_path(run_root, point=point), step)
            _append_event(run_root, step)

    fallback_points = [
        (index, point)
        for index, point in indexed_points
        if (
            step := steps_by_key.get((point.ticker, point.decision_date.isoformat()))
        ) is None
        or step.get("status") == "provider_error"
    ]
    for indexed_point in fallback_points:
        point, step = _score_indexed_point(
            indexed_point=indexed_point,
            run_root=run_root,
            run_index=run_index,
            tickers_by_symbol=tickers_by_symbol,
            client=client,
            call_limiter=call_limiter,
            config=config,
            sample_concurrency=1,
            stats=stats,
            phase="fallback",
        )
        steps_by_key[(point.ticker, point.decision_date.isoformat())] = step
        _write_json(_step_path(run_root, point=point), step)
        _append_event(run_root, step)

    audit = _audit_probe_run(run_root)
    steps = [
        steps_by_key[(point.ticker, point.decision_date.isoformat())]
        for point in points
        if (point.ticker, point.decision_date.isoformat()) in steps_by_key
    ]
    provider_errors = sum(1 for step in steps if step.get("status") == "provider_error")
    json_attempts = sum(_json_parse_attempts(step) for step in steps)
    json_successes = sum(_json_parse_successes(step) for step in steps)
    fence_stripped = sum(_fence_stripped_count(step) for step in steps)
    summary = {
        "schema": "gotra.bt.kimi_probe_run_summary.v1",
        "run_id": run_root.name,
        "run_root": str(run_root),
        "provider": "kimi_sophnet",
        "model": config.model,
        "temperature": 0.0,
        "sample_count": config.sample_count,
        "decision_concurrency": config.decision_concurrency,
        "sample_concurrency": config.sample_concurrency,
        "max_connections": config.max_connections,
        "dead_zone_epsilon_pct": config.dead_zone_epsilon_pct,
        "points": len(points),
        "scored_steps": sum(1 for step in steps if step.get("status") == "scored"),
        "provider_errors": provider_errors,
        "json_parse_successes": json_successes,
        "json_parse_attempts": json_attempts,
        "json_parse_success_rate": json_successes / json_attempts if json_attempts else None,
        "markdown_json_fence_stripped": fence_stripped,
        "fallback_points": [
            {
                "ticker": point.ticker,
                "decision_date": point.decision_date.isoformat(),
            }
            for _index, point in fallback_points
        ],
        "provider_call_stats": stats.snapshot(planned_samples=len(points) * config.sample_count),
        "elapsed_seconds": _rounded(time.perf_counter() - started),
        "audit": audit,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(
        run_root / "system_health.json",
        {
            "status": "ok" if provider_errors == 0 and audit.get("ok") else "failed",
            "provider": "kimi_sophnet",
            "provider_errors": provider_errors,
            "audit_ok": audit.get("ok"),
        },
    )
    return summary


def _score_indexed_point(
    *,
    indexed_point: tuple[int, DecisionPoint],
    run_root: Path,
    run_index: int,
    tickers_by_symbol: dict[str, TickerSpec],
    client: KimiCompletionClient,
    call_limiter: threading.BoundedSemaphore,
    config: ProbeConfig,
    sample_concurrency: int,
    stats: RunStats,
    phase: str,
) -> tuple[DecisionPoint, dict[str, Any]]:
    step_index, point = indexed_point
    ticker_spec = tickers_by_symbol.get(point.ticker)
    if ticker_spec is None:
        raise ValueError(f"unknown ticker in probe points: {point.ticker}")
    step = _score_point(
        point=point,
        ticker_spec=ticker_spec,
        step_index=step_index,
        run_root=run_root,
        run_index=run_index,
        client=client,
        call_limiter=call_limiter,
        config=config,
        sample_concurrency=sample_concurrency,
        stats=stats,
        phase=phase,
    )
    return point, step


def _score_point(
    *,
    point: DecisionPoint,
    ticker_spec: TickerSpec,
    step_index: int,
    run_root: Path,
    run_index: int,
    client: KimiCompletionClient,
    call_limiter: threading.BoundedSemaphore,
    config: ProbeConfig,
    sample_concurrency: int,
    stats: RunStats,
    phase: str,
) -> dict[str, Any]:
    prices = read_price_cache(point.ticker, price_dir=config.data_dir / "prices")
    decision_slice = _rows_on_or_before(prices, point.decision_date)
    start_row = _row_on_or_after(prices, point.decision_date)
    outcome_date = point.decision_date + timedelta(days=30)
    end_row = _row_on_or_after(prices, outcome_date)
    if decision_slice.empty or start_row is None or end_row is None:
        return {
            "schema": "gotra.bt.kimi_probe_step.v1",
            "step": step_index,
            "status": "skipped",
            "ticker": point.ticker,
            "ticker_name": ticker_spec.name,
            "arm": "baseline",
            "decision_date": point.decision_date.isoformat(),
            "provider": "kimi_sophnet",
            "provider_metadata": _provider_metadata(config=config),
            "prompt_hash": "",
            "skip_reason": "insufficient_price_history",
            "future_data_allowed": False,
            "audit_actor": "backtest/kimi_probe",
        }

    prompt_payload = _build_codex_prompt_payload(
        ticker=point.ticker,
        decision_date=point.decision_date,
        price_rows=decision_slice,
        feedback=[],
    )
    prompt = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True, indent=2)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    token_estimate = estimate_tokens(BT_CODEX_SYSTEM_PROMPT + "\n" + prompt)

    try:
        decision_payload, billed_tokens, token_usage_source, denoising = _complete_denoised(
            client=client,
            call_limiter=call_limiter,
            prompt=prompt,
            token_estimate=token_estimate,
            config=config,
            sample_concurrency=sample_concurrency,
            stats=stats,
            phase=phase,
        )
    except Exception as exc:  # noqa: BLE001 - external provider output is untrusted.
        return _provider_error_step(
            point=point,
            ticker_spec=ticker_spec,
            step_index=step_index,
            run_index=run_index,
            outcome_date=outcome_date,
            end_row=end_row,
            decision_slice=decision_slice,
            prompt_hash=prompt_hash,
            estimated_tokens=token_estimate * config.sample_count,
            error_message=str(exc),
            config=config,
        )

    actual_change_pct = _change_pct(float(start_row["adj_close"]), float(end_row["adj_close"]))
    expected_change_pct = float(decision_payload["expected_change_pct"])
    error = round(actual_change_pct - expected_change_pct, 6)
    return {
        "schema": "gotra.bt.kimi_probe_step.v1",
        "step": step_index,
        "run_index": run_index,
        "date": point.decision_date.isoformat(),
        "run_mode": "diagnostic_probe",
        "status": "scored",
        "ticker": point.ticker,
        "ticker_name": ticker_spec.name,
        "arm": "baseline",
        "decision_date": point.decision_date.isoformat(),
        "window_days": 30,
        "window_end_date": outcome_date.isoformat(),
        "outcome_as_of": str(end_row["date"]),
        "decision_direction": decision_payload["direction"],
        "expected_change_pct": expected_change_pct,
        "actual_change_pct": actual_change_pct,
        "error": error,
        "mse": round(error * error, 6),
        "confidence": float(decision_payload["confidence"]),
        "reasoning": str(decision_payload["reasoning"]),
        "prompt_hash": prompt_hash,
        "estimated_tokens": billed_tokens,
        "token_usage_source": token_usage_source,
        "cache_hit": False,
        "cache_namespace": run_root.name,
        "provider": "kimi_sophnet",
        "provider_metadata": _provider_metadata(config=config),
        "provider_network_enabled": False,
        "denoising": denoising,
        "style_window": style_window_for(point.decision_date),
        "decision_inputs": _decision_inputs(decision_slice),
        "outcome_inputs": _outcome_inputs(end_row),
        "future_data_allowed": False,
        "audit_actor": "backtest/kimi_probe",
    }


def _complete_denoised(
    *,
    client: KimiCompletionClient,
    call_limiter: threading.BoundedSemaphore,
    prompt: str,
    token_estimate: int,
    config: ProbeConfig,
    sample_concurrency: int,
    stats: RunStats,
    phase: str,
) -> tuple[dict[str, Any], int, str, dict[str, Any]]:
    sample_indexes = list(range(1, config.sample_count + 1))
    if sample_concurrency <= 1:
        samples = [
            _complete_one_sample(
                client=client,
                call_limiter=call_limiter,
                prompt=prompt,
                token_estimate=token_estimate,
                sample_index=sample_index,
                config=config,
                stats=stats,
                phase=phase,
            )
            for sample_index in sample_indexes
        ]
    else:
        samples = []
        with ThreadPoolExecutor(max_workers=min(config.sample_count, sample_concurrency)) as executor:
            futures = {
                executor.submit(
                    _complete_one_sample,
                    client=client,
                    call_limiter=call_limiter,
                    prompt=prompt,
                    token_estimate=token_estimate,
                    sample_index=sample_index,
                    config=config,
                    stats=stats,
                    phase=phase,
                ): sample_index
                for sample_index in sample_indexes
            }
            for future in as_completed(futures):
                samples.append(future.result())
        samples = sorted(samples, key=lambda sample: sample.sample_index)
    decision_payload, billed_tokens, token_usage_source, denoising = _aggregate_denoising_samples(
        samples=samples,
        sample_count=config.sample_count,
        sample_concurrency=sample_concurrency,
        provider_name="kimi_sophnet",
    )
    raw_median = float(median([sample.expected_change_pct for sample in samples]))
    final_direction, final_expected = dead_zone_decision_from_median(
        raw_median,
        epsilon_pct=config.dead_zone_epsilon_pct,
    )
    denoising.update(
        {
            "provider_label": "kimi_sophnet",
            "dead_zone_epsilon_pct": _rounded(config.dead_zone_epsilon_pct),
            "raw_median_expected_change_pct": _rounded(raw_median),
            "dead_zone_applied": final_direction == "neutral",
            "json_parse_successes": len(samples),
            "json_parse_attempts": sum(_sample_attempt_count(sample) for sample in samples),
            "markdown_json_fence_stripped": sum(
                1 for sample in samples if getattr(sample, "markdown_json_fence_stripped", False)
            ),
        }
    )
    decision_payload["direction"] = final_direction
    decision_payload["expected_change_pct"] = _rounded(final_expected)
    decision_payload["reasoning"] = (
        f"median denoised {config.sample_count} kimi_sophnet samples; "
        f"dead-zone epsilon={config.dead_zone_epsilon_pct:g}; "
        f"representative sample: {decision_payload['reasoning']}"
    )
    return decision_payload, billed_tokens, token_usage_source, denoising


def _complete_one_sample(
    *,
    client: KimiCompletionClient,
    call_limiter: threading.BoundedSemaphore,
    prompt: str,
    token_estimate: int,
    sample_index: int,
    config: ProbeConfig,
    stats: RunStats,
    phase: str,
) -> ProviderSample:
    last_error = ""
    for attempt in range(1, config.sample_retries + 2):
        started = time.perf_counter()
        try:
            with call_limiter:
                completion = client.complete(
                    system_prompt=BT_CODEX_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    max_tokens=700,
                    timeout_seconds=config.timeout_seconds,
                    temperature=0.0,
                )
            text, provider_tokens = _completion_text_and_usage(completion)
            decision_payload = _parse_decision_json(text)
            stats.record_call(
                phase=phase,
                ok=True,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
            billed_tokens = provider_tokens if provider_tokens is not None else token_estimate
            sample = ProviderSample(
                sample_index=sample_index,
                direction=str(decision_payload["direction"]),
                expected_change_pct=float(decision_payload["expected_change_pct"]),
                confidence=float(decision_payload["confidence"]),
                reasoning=str(decision_payload["reasoning"]),
                billed_tokens=billed_tokens,
                token_usage_source="provider_usage" if provider_tokens is not None else "estimated",
                attempts=attempt,
            )
            metadata = completion.get("response_metadata") if isinstance(completion, dict) else {}
            object.__setattr__(
                sample,
                "markdown_json_fence_stripped",
                bool((metadata or {}).get("markdown_json_fence_stripped")),
            )
            return sample
        except Exception as exc:  # noqa: BLE001 - transport and JSON failures are retried.
            last_error = str(exc)
            stats.record_call(
                phase=phase,
                ok=False,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                error_type=_error_type(exc),
            )
    raise RuntimeError(f"sample {sample_index} failed after retry: {last_error}")


def dead_zone_decision_from_median(median_expected: float, *, epsilon_pct: float) -> tuple[str, float]:
    if epsilon_pct > 0 and abs(median_expected) <= epsilon_pct:
        return "neutral", 0.0
    if median_expected > 0:
        return "long", median_expected
    if median_expected < 0:
        return "avoid", median_expected
    return "neutral", 0.0


def _provider_error_step(
    *,
    point: DecisionPoint,
    ticker_spec: TickerSpec,
    step_index: int,
    run_index: int,
    outcome_date: date,
    end_row: pd.Series,
    decision_slice: pd.DataFrame,
    prompt_hash: str,
    estimated_tokens: int,
    error_message: str,
    config: ProbeConfig,
) -> dict[str, Any]:
    return {
        "schema": "gotra.bt.kimi_probe_step.v1",
        "step": step_index,
        "run_index": run_index,
        "date": point.decision_date.isoformat(),
        "error_type": "provider_error",
        "run_mode": "diagnostic_probe",
        "status": "provider_error",
        "ticker": point.ticker,
        "ticker_name": ticker_spec.name,
        "arm": "baseline",
        "decision_date": point.decision_date.isoformat(),
        "window_days": 30,
        "window_end_date": outcome_date.isoformat(),
        "outcome_as_of": str(end_row["date"]),
        "decision_direction": None,
        "expected_change_pct": None,
        "actual_change_pct": None,
        "error": None,
        "mse": None,
        "confidence": None,
        "reasoning": "",
        "prompt_hash": prompt_hash,
        "estimated_tokens": estimated_tokens,
        "token_usage_source": "estimated",
        "cache_hit": False,
        "provider": "kimi_sophnet",
        "provider_metadata": _provider_metadata(config=config),
        "provider_network_enabled": False,
        "denoising": None,
        "provider_error": error_message,
        "style_window": style_window_for(point.decision_date),
        "decision_inputs": _decision_inputs(decision_slice),
        "outcome_inputs": _outcome_inputs(end_row),
        "future_data_allowed": False,
        "audit_actor": "backtest/kimi_probe",
    }


def _decision_inputs(decision_slice: pd.DataFrame) -> list[dict[str, Any]]:
    latest_decision_row = decision_slice.iloc[-1]
    return [
        {
            "name": "adjusted_close_history",
            "kind": "price",
            "source": str(latest_decision_row["source_url"]),
            "availability_date": str(latest_decision_row["date"]),
            "rows": int(len(decision_slice)),
        }
    ]


def _outcome_inputs(end_row: pd.Series) -> list[dict[str, Any]]:
    return [
        {
            "name": "outcome_adjusted_close",
            "kind": "price",
            "source": str(end_row["source_url"]),
            "availability_date": str(end_row["date"]),
        }
    ]


def _provider_metadata(*, config: ProbeConfig) -> dict[str, Any]:
    return {
        "transport": "sophnet_chat_completions",
        "base_url": config.base_url,
        "model": config.model,
        "temperature": 0.0,
        "auth_source": "SOPHNET_API_KEY",
        "denoising": {
            "method": "median_expected_change_pct",
            "sample_count": config.sample_count,
            "sample_concurrency": config.sample_concurrency,
            "decision_concurrency": config.decision_concurrency,
            "max_connections": config.max_connections,
            "single_sample_retries": config.sample_retries,
            "dead_zone_epsilon_pct": config.dead_zone_epsilon_pct,
            "vote_consistency": "modal_pre_deadzone_direction_fraction",
        },
    }


def _provider_call_stats(calls: list[dict[str, Any]]) -> dict[str, Any]:
    total_calls = len(calls)
    error_calls = sum(1 for call in calls if not call["ok"])
    success_calls = total_calls - error_calls
    latencies = [int(call["elapsed_ms"]) for call in calls]
    error_types: dict[str, int] = {}
    for call in calls:
        error_type = str(call.get("error_type") or "")
        if error_type:
            error_types[error_type] = error_types.get(error_type, 0) + 1
    return {
        "total_calls": total_calls,
        "success_calls": success_calls,
        "error_calls": error_calls,
        "error_rate": error_calls / total_calls if total_calls else None,
        "error_types": dict(sorted(error_types.items())),
        "avg_latency_ms": _rounded(sum(latencies) / len(latencies)) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
    }


def _error_type(exc: Exception) -> str:
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return type(cause).__name__
    text = str(exc)
    if "HTTP 429" in text:
        return "HTTP_429"
    if "timed out" in text.lower():
        return "Timeout"
    if "JSON" in text:
        return "JSONParseError"
    return type(exc).__name__


def _audit_probe_run(run_root: Path) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    steps_checked = 0
    for step_path in sorted((run_root / "baseline").glob("step_*.json")):
        step = json.loads(step_path.read_text(encoding="utf-8"))
        steps_checked += 1
        violations.extend(_audit_probe_step(step, path=str(step_path)))

    event_rows_checked = 0
    event_log = run_root / "event_log.jsonl"
    if event_log.exists():
        for line_number, line in enumerate(event_log.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            event_rows_checked += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                violations.append(
                    {
                        "code": "event_log_json",
                        "message": f"invalid JSON: {exc}",
                        "path": f"{event_log}:{line_number}",
                    }
                )
                continue
            if event.get("actor") != "backtest/kimi_probe":
                violations.append(
                    {
                        "code": "event_actor",
                        "message": f"unexpected event actor: {event.get('actor')!r}",
                        "path": f"{event_log}:{line_number}",
                    }
                )
    elif steps_checked:
        violations.append(
            {
                "code": "event_log_missing",
                "message": "event_log.jsonl missing",
                "path": str(event_log),
            }
        )
    return {
        "ok": not violations,
        "steps_checked": steps_checked,
        "event_rows_checked": event_rows_checked,
        "violations": violations,
    }


def _audit_probe_step(step: dict[str, Any], *, path: str) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    decision_date = _date_or_violation(step.get("decision_date"), "decision_date", violations, path)
    outcome_as_of = _date_or_violation(step.get("outcome_as_of"), "outcome_as_of", violations, path)
    if step.get("future_data_allowed") is not False:
        violations.append(
            {
                "code": "future_data_allowed",
                "message": "future_data_allowed must be false",
                "path": path,
            }
        )
    if step.get("provider_network_enabled") is not False:
        violations.append(
            {
                "code": "provider_network_enabled",
                "message": "BT prompt must not use network research",
                "path": path,
            }
        )
    if step.get("audit_actor") != "backtest/kimi_probe":
        violations.append(
            {
                "code": "audit_actor",
                "message": f"unexpected audit_actor: {step.get('audit_actor')!r}",
                "path": path,
            }
        )
    if decision_date is not None:
        _audit_items(
            step.get("decision_inputs") or [],
            cutoff=decision_date,
            code="decision_input_future",
            path=path,
            violations=violations,
        )
    if outcome_as_of is not None:
        _audit_items(
            step.get("outcome_inputs") or [],
            cutoff=outcome_as_of,
            code="outcome_input_future",
            path=path,
            violations=violations,
        )
    return violations


def _audit_items(
    items: list[dict[str, Any]],
    *,
    cutoff: date,
    code: str,
    path: str,
    violations: list[dict[str, str]],
) -> None:
    for item in items:
        availability = _date_or_violation(
            item.get("availability_date"),
            "availability_date",
            violations,
            path,
        )
        if availability is not None and availability > cutoff:
            violations.append(
                {
                    "code": code,
                    "message": (
                        f"{item.get('name') or item.get('source')} "
                        f"availability_date={availability} is after cutoff={cutoff}"
                    ),
                    "path": path,
                }
            )


def _date_or_violation(
    value: Any,
    field_name: str,
    violations: list[dict[str, str]],
    path: str,
) -> date | None:
    try:
        return parse_date(str(value))
    except (TypeError, ValueError):
        violations.append(
            {
                "code": "invalid_date",
                "message": f"invalid {field_name}: {value!r}",
                "path": path,
            }
        )
        return None


def _load_probe_steps(run_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    steps: dict[tuple[str, str], dict[str, Any]] = {}
    for step_path in sorted((run_root / "baseline").glob("step_*.json")):
        step = json.loads(step_path.read_text(encoding="utf-8"))
        if step.get("status") != "scored":
            continue
        key = (str(step.get("ticker")), str(step.get("decision_date")))
        steps[key] = step
    return steps


def _step_path(run_root: Path, *, point: DecisionPoint) -> Path:
    slug = point.ticker.lower().replace(".", "_")
    return run_root / "baseline" / f"step_{point.decision_date.isoformat()}_{slug}.json"


def _append_event(run_root: Path, step: dict[str, Any]) -> None:
    event = {
        "actor": "backtest/kimi_probe",
        "event_type": "bt_step_scored" if step.get("status") == "scored" else "bt_provider_error",
        "ticker": step["ticker"],
        "arm": step["arm"],
        "decision_date": step["decision_date"],
        "created_at": datetime.now(UTC).isoformat(),
    }
    if step.get("provider_error"):
        event["provider_error"] = step["provider_error"]
    with (run_root / "event_log.jsonl").open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _json_parse_attempts(step: dict[str, Any]) -> int:
    denoising = step.get("denoising")
    if not isinstance(denoising, dict):
        return 0
    return int(denoising.get("json_parse_attempts") or 0)


def _json_parse_successes(step: dict[str, Any]) -> int:
    denoising = step.get("denoising")
    if not isinstance(denoising, dict):
        return 0
    return int(denoising.get("json_parse_successes") or 0)


def _fence_stripped_count(step: dict[str, Any]) -> int:
    denoising = step.get("denoising")
    if not isinstance(denoising, dict):
        return 0
    return int(denoising.get("markdown_json_fence_stripped") or 0)


def _sample_attempt_count(sample: ProviderSample) -> int:
    return int(sample.attempts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Kimi Stage 7 diagnostic probe.")
    parser.add_argument("--data-dir", default="data/backtest")
    parser.add_argument("--points-file", default=str(DEFAULT_POINTS_FILE))
    parser.add_argument("--run-prefix", default="stage7_kimi_probe")
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--dead-zone-epsilon-pct", type=float, default=0.3)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--sample-retries", type=int, default=2)
    parser.add_argument("--decision-concurrency", type=int, default=10)
    parser.add_argument("--sample-concurrency", type=int, default=5)
    parser.add_argument("--max-connections", type=int, default=20)
    parser.add_argument("--model", default=DEFAULT_KIMI_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_SOPHNET_BASE_URL)
    parser.add_argument("--env-file", default="")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_probe(
        ProbeConfig(
            data_dir=Path(args.data_dir),
            points_file=Path(args.points_file),
            run_prefix=args.run_prefix,
            sample_count=args.sample_count,
            dead_zone_epsilon_pct=args.dead_zone_epsilon_pct,
            timeout_seconds=args.timeout_seconds,
            sample_retries=args.sample_retries,
            decision_concurrency=args.decision_concurrency,
            sample_concurrency=args.sample_concurrency,
            max_connections=args.max_connections,
            model=args.model,
            base_url=args.base_url,
            env_file=Path(args.env_file) if args.env_file else None,
            output_name=args.output_name,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    comparison = result["comparison"]
    return 0 if comparison["total"] and comparison["rate"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
