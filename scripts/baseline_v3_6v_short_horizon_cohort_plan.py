#!/usr/bin/env python3
"""GOTRA v3.6V short-horizon forward-live cohort dry-run planner."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import parse_date, ticker_slug
from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_four_arm as v3


SUMMARY_SCHEMA = "gotra.baseline_v3_6v.short_horizon_cohort_plan_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6v.short_horizon_cohort_plan_manifest.v1"
PLAN_RUN_ID_PREFIX = "baseline_v3_6v_short_horizon_cohort_plan_"
SCRIPT_VERSION = "v3.6v-20260621"

STATUS_PLAN_READY = "SHORT_HORIZON_COHORT_PLAN_READY"
STATUS_BLOCKED_RUN_ID_EXISTS = "SHORT_HORIZON_PLAN_BLOCKED_RUN_ID_EXISTS"
STATUS_BLOCKED_DATA = "SHORT_HORIZON_PLAN_BLOCKED_DATA"

DEFAULT_HORIZONS = (1, 3, 5)


@dataclass(frozen=True)
class PlanConfig:
    plan_run_id: str
    output_dir: Path
    tickers: tuple[str, ...]
    horizons: tuple[int, ...]
    arms: tuple[v3.Arm, ...]
    input_layers: tuple[v3.InputLayer, ...]
    capture_timestamp_utc: datetime
    timezone: str
    price_dir: Path
    provider_model: str
    codex_cli_reasoning_setting: str
    allow_overwrite: bool = False


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def local_capture_date(config: PlanConfig) -> date:
    return config.capture_timestamp_utc.astimezone(ZoneInfo(config.timezone)).date()


def daily_close_available_after_utc(horizon_end_date: date) -> str:
    return datetime.combine(
        horizon_end_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=UTC,
    ).isoformat().replace("+00:00", "Z")


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_horizons(value: str) -> tuple[int, ...]:
    horizons = tuple(int(item) for item in parse_csv(value))
    return tuple(dict.fromkeys(horizons))


def parse_arms(value: str) -> tuple[v3.Arm, ...]:
    if value == "all":
        return v3.ARMS
    return tuple(v3.normalize_arm(item) for item in parse_csv(value))


def parse_input_layers(value: str) -> tuple[v3.InputLayer, ...]:
    if value == "both":
        return v3.INPUT_LAYERS
    return tuple(v3.normalize_input_layer(item) for item in parse_csv(value))


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(PLAN_RUN_ID_PREFIX):
        raise ValueError(f"plan_run_id must start with {PLAN_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("plan_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: PlanConfig) -> None:
    validate_run_id(config.plan_run_id)
    if not config.tickers:
        raise ValueError("at least one ticker is required")
    if not config.horizons:
        raise ValueError("at least one horizon is required")
    if any(horizon <= 0 for horizon in config.horizons):
        raise ValueError("all horizons must be > 0")
    if not config.arms:
        raise ValueError("at least one arm is required")
    if not config.input_layers:
        raise ValueError("at least one input layer is required")
    slugs: dict[str, str] = {}
    for ticker in config.tickers:
        slug = ticker_slug(ticker)
        prior = slugs.get(slug)
        if prior is not None:
            raise ValueError(
                f"duplicate ticker slug: {prior!r} and {ticker!r} both map to {slug!r}"
            )
        slugs[slug] = ticker


def sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def latest_visible_price_for_ticker(
    ticker: str,
    *,
    decision_date_local: date,
    price_dir: Path,
) -> tuple[str, int, int, str]:
    frame = read_price_cache(ticker, price_dir=price_dir)
    dated = frame.copy()
    dated["_gotra_visible_date"] = pd.to_datetime(dated["date"]).dt.date
    visible = dated[dated["_gotra_visible_date"] < decision_date_local]
    if visible.empty:
        raise RuntimeError(f"no visible price rows for {ticker} at {decision_date_local}")
    latest_visible = str(visible.iloc[-1]["date"])
    future_rows_excluded = int(len(dated) - len(visible))
    price_source_path = str(price_dir / f"{ticker}.csv")
    return latest_visible, int(len(visible)), future_rows_excluded, price_source_path


def cohort_points(config: PlanConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decision_date_local = local_capture_date(config)
    points: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for ticker in config.tickers:
        try:
            latest_visible, visible_count, future_rows_excluded, price_source_path = (
                latest_visible_price_for_ticker(
                    ticker,
                    decision_date_local=decision_date_local,
                    price_dir=config.price_dir,
                )
            )
        except Exception as exc:  # noqa: BLE001 - planner must surface local data blockers.
            blockers.append(
                {
                    "ticker": ticker,
                    "reason": "price_cache_unavailable",
                    "error_type": exc.__class__.__name__,
                    "error_message": v3.redact_error(str(exc)),
                }
            )
            continue
        future_violation = parse_date(latest_visible) >= decision_date_local
        for horizon_days in config.horizons:
            horizon_end = decision_date_local + timedelta(days=horizon_days)
            point = {
                "ticker": ticker,
                "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
                    "+00:00",
                    "Z",
                ),
                "decision_date_local": decision_date_local.isoformat(),
                "horizon_days": horizon_days,
                "horizon_end_date": horizon_end.isoformat(),
                "outcome_maturity_rule": "daily close visible at next UTC midnight",
                "outcome_price_available_after_utc": daily_close_available_after_utc(
                    horizon_end,
                ),
                "latest_visible_price_date": latest_visible,
                "visible_price_rows": visible_count,
                "future_rows_excluded": future_rows_excluded,
                "future_data_violation": future_violation,
                "price_source_path": price_source_path,
                "deterministic_reference_expected": True,
                "expected_backend_decisions": len(config.arms) * len(config.input_layers),
                "arms": list(config.arms),
                "input_layers": list(config.input_layers),
            }
            point["point_hash"] = sha256_json(point)
            points.append(point)
    return points, blockers


def blocked_run_id_summary(config: PlanConfig, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "plan_run_id": config.plan_run_id,
        "run_root": str(run_root),
        "status": STATUS_BLOCKED_RUN_ID_EXISTS,
        "evidence_layer": "short-horizon forward-live cohort planning only",
        "blocker_reasons": ["output_run_id_exists"],
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "v3_7_30d_verdict_allowed": False,
    }


def summary_for(
    *,
    config: PlanConfig,
    run_root: Path,
    points: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    future_violations = sum(1 for point in points if point["future_data_violation"])
    expected_backend_decisions = sum(int(point["expected_backend_decisions"]) for point in points)
    deterministic_reference_count = len(points)
    status = (
        STATUS_PLAN_READY
        if points and not blockers and future_violations == 0
        else STATUS_BLOCKED_DATA
    )
    next_maturity = min(
        (str(point["outcome_price_available_after_utc"]) for point in points),
        default="",
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "plan_run_id": config.plan_run_id,
        "run_root": str(run_root),
        "status": status,
        "evidence_layer": "short-horizon forward-live cohort planning only",
        "capture_family": "v3.6v_short_horizon_forward_live",
        "does_not_inherit_30d_conclusions": True,
        "thirty_day_forward_live_verdict_status": "NOT_ENTERED",
        "v3_7_30d_verdict_allowed": False,
        "capture_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "decision_date_local": local_capture_date(config).isoformat(),
        "timezone": config.timezone,
        "tickers": list(config.tickers),
        "horizons": list(config.horizons),
        "arms": list(config.arms),
        "input_layers": list(config.input_layers),
        "cohort_point_count": len(points),
        "expected_backend_decisions_if_captured": expected_backend_decisions,
        "deterministic_reference_expected_count": deterministic_reference_count,
        "future_data_violation_count": future_violations,
        "local_data_blocker_count": len(blockers),
        "blockers": blockers,
        "next_maturity_after_utc": next_maturity,
        "provider_model_default": config.provider_model,
        "codex_cli_reasoning_setting_default": config.codex_cli_reasoning_setting,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a 30D forward-live verdict",
            "not equivalent to the 30D cohort",
        ],
        "cohort_points": points,
        "script_version": SCRIPT_VERSION,
    }


def run_plan(config: PlanConfig) -> dict[str, Any]:
    validate_config(config)
    run_root = config.output_dir / config.plan_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = blocked_run_id_summary(config, run_root)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    points, blockers = cohort_points(config)
    summary = summary_for(config=config, run_root=run_root, points=points, blockers=blockers)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "plan_run_id": config.plan_run_id,
        "run_root": str(run_root),
        "status": summary["status"],
        "input_tickers": list(config.tickers),
        "horizons": list(config.horizons),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
    }
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--tickers", default=",".join(capture_v35a.DEFAULT_TICKERS))
    parser.add_argument("--horizons", default=",".join(str(item) for item in DEFAULT_HORIZONS))
    parser.add_argument("--arms", default="all")
    parser.add_argument("--input-layer", default="both")
    parser.add_argument("--capture-timestamp-utc", default="")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--provider-model", default=v3.DEFAULT_CODEX_CLI_MODEL)
    parser.add_argument(
        "--codex-cli-reasoning-setting",
        default=capture_v35a.DEFAULT_V3_5A_CODEX_CLI_REASONING,
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PlanConfig:
    return PlanConfig(
        plan_run_id=str(args.plan_run_id),
        output_dir=args.output_dir,
        tickers=parse_csv(str(args.tickers)),
        horizons=parse_horizons(str(args.horizons)),
        arms=parse_arms(str(args.arms)),
        input_layers=parse_input_layers(str(args.input_layer)),
        capture_timestamp_utc=parse_timestamp(str(args.capture_timestamp_utc or "")),
        timezone=str(args.timezone),
        price_dir=args.price_dir,
        provider_model=str(args.provider_model),
        codex_cli_reasoning_setting=str(args.codex_cli_reasoning_setting),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_plan(config_from_args(parse_args(argv)))
    return 0 if str(summary.get("status")) == STATUS_PLAN_READY else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
