#!/usr/bin/env python3
"""GOTRA v3.5B forward-live outcome maturity resolver."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd

from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import parse_date, ticker_slug
from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_four_arm as v3


RESOLVER_SCHEMA = "gotra.baseline_v3_5b.forward_live_outcome_resolution.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3_5b.forward_live_outcome_resolver_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_5b.forward_live_outcome_resolver_manifest.v1"
RESOLVER_RUN_ID_PREFIX = "baseline_v3_5b_outcome_resolver_"
RESOLVER_SCRIPT_VERSION = "v3.5b-20260620"
DEFAULT_OUTCOME_WINDOW_DAYS = 7

STATUS_NOT_MATURED = "NOT_MATURED"
STATUS_BLOCKED_DATA = "BLOCKED_DATA"
STATUS_BLOCKED_SOURCE_FUTURE_DATA = "BLOCKED_SOURCE_FUTURE_DATA"
STATUS_RESOLVED = "RESOLVED"
STATUS_BLOCKED_RUN_ID_EXISTS = "BLOCKED_RUN_ID_EXISTS"

OUTCOME_FIELDS = {
    "outcome_price_date",
    "outcome_price",
    "actual_change_pct",
    "actual_direction",
}


@dataclass(frozen=True)
class ResolverConfig:
    capture_run_dir: Path
    resolver_run_id: str
    as_of_timestamp_utc: datetime
    price_dir: Path
    output_dir: Path
    outcome_window_days: int = DEFAULT_OUTCOME_WINDOW_DAYS
    allow_overwrite: bool = False


def parse_as_of_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RESOLVER_RUN_ID_PREFIX):
        raise ValueError(f"resolver_run_id must start with {RESOLVER_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("resolver_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: ResolverConfig) -> None:
    validate_run_id(config.resolver_run_id)
    if not config.capture_run_dir.exists():
        raise FileNotFoundError(f"capture run dir not found: {config.capture_run_dir}")
    if config.outcome_window_days < 0:
        raise ValueError("outcome_window_days must be >= 0")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def find_capture_artifacts(capture_run_dir: Path) -> list[Path]:
    search_root = capture_run_dir / "captures" if (capture_run_dir / "captures").exists() else capture_run_dir
    paths = []
    for path in sorted(search_root.glob("**/*.json")):
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == capture_v35a.CAPTURE_SCHEMA:
            paths.append(path)
    return paths


def date_from_capture(payload: dict[str, Any], *keys: str) -> date:
    for key in keys:
        value = payload.get(key)
        if value:
            return parse_date(str(value))
    raise ValueError(f"capture artifact missing date keys: {keys}")


def float_from_row(row: pd.Series) -> float:
    return float(row["adj_close"])


def daily_close_available_cutoff(as_of_timestamp_utc: datetime) -> date:
    """Daily close row D is visible only at D+1 00:00:00 UTC or later."""
    return as_of_timestamp_utc.astimezone(UTC).date() - timedelta(days=1)


def price_on_or_before(
    *,
    ticker: str,
    target_date: date,
    price_dir: Path,
    as_of_timestamp_utc: datetime,
) -> tuple[date, float, str]:
    available_cutoff = daily_close_available_cutoff(as_of_timestamp_utc)
    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=available_cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    visible = frame.loc[dates <= target_date]
    if visible.empty:
        raise LookupError(f"missing decision price for {ticker} on/before {target_date}")
    row = visible.iloc[-1]
    return parse_date(str(row["date"])), float_from_row(row), str(price_dir / f"{ticker}.csv")


def outcome_price_in_window(
    *,
    ticker: str,
    horizon_end_date: date,
    as_of_timestamp_utc: datetime,
    price_dir: Path,
    outcome_window_days: int,
) -> tuple[date, float, str] | None:
    allowed_end = horizon_end_date + timedelta(days=outcome_window_days)
    cutoff = min(daily_close_available_cutoff(as_of_timestamp_utc), allowed_end)
    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    candidates = frame.loc[(dates >= horizon_end_date) & (dates <= cutoff)]
    if candidates.empty:
        return None
    row = candidates.iloc[0]
    return parse_date(str(row["date"])), float_from_row(row), str(price_dir / f"{ticker}.csv")


def source_artifact_ref(path: Path, capture_run_dir: Path) -> str:
    try:
        return str(path.relative_to(capture_run_dir))
    except ValueError:
        return str(path)


def source_decision_id(payload: dict[str, Any], artifact_ref: str) -> str:
    return v3.stable_json_hash(
        {
            "source_run_id": payload.get("run_id", ""),
            "artifact_ref": artifact_ref,
            "ticker": payload.get("ticker", ""),
            "decision_date": payload.get("decision_date_local")
            or payload.get("decision_date", ""),
            "arm": payload.get("arm", ""),
            "input_layer": payload.get("input_layer", ""),
            "prompt_hash": payload.get("prompt_hash", ""),
        }
    )


def empty_outcome_fields() -> dict[str, Any]:
    return {
        "outcome_price_date": None,
        "outcome_price": None,
        "actual_change_pct": None,
        "actual_direction": None,
    }


def actual_direction(actual_change_pct: float) -> str:
    return v3.actual_direction(actual_change_pct)


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def source_capture_timestamp(payload: dict[str, Any]) -> datetime | None:
    value = payload.get("decision_timestamp_utc")
    if not value:
        return None
    try:
        return parse_as_of_timestamp(str(value))
    except ValueError:
        return None


def source_future_data_violation_reasons(
    *,
    payload: dict[str, Any],
    decision_date: date,
    latest_visible_date: date,
) -> list[str]:
    reasons: list[str] = []
    if boolish(payload.get("future_data_violation")):
        reasons.append("source_future_data_violation_flag")
    capture_timestamp = source_capture_timestamp(payload)
    allowed_visible_date = decision_date
    if capture_timestamp is not None:
        allowed_visible_date = min(
            allowed_visible_date,
            daily_close_available_cutoff(capture_timestamp),
        )
    if latest_visible_date > allowed_visible_date:
        reasons.append("latest_visible_price_date_after_capture_allowed_date")
    return reasons


def resolve_capture_artifact(
    *,
    config: ResolverConfig,
    source_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    payload = load_json(source_path)
    artifact_ref = source_artifact_ref(source_path, config.capture_run_dir)
    ticker = str(payload["ticker"])
    decision_date = date_from_capture(payload, "decision_date_local", "decision_date")
    horizon_days = int(payload.get("horizon_days") or v3.WINDOW_DAYS)
    horizon_end = date_from_capture(payload, "horizon_end_date")
    as_of_date = config.as_of_timestamp_utc.date()
    source_id = source_decision_id(payload, artifact_ref)
    latest_visible_date = date_from_capture(payload, "latest_visible_price_date", "decision_date_local")
    source_future_reasons = source_future_data_violation_reasons(
        payload=payload,
        decision_date=decision_date,
        latest_visible_date=latest_visible_date,
    )

    decision_price_date: date | None = None
    decision_price: float | None = None
    decision_price_source = ""
    if not source_future_reasons:
        try:
            decision_price_date, decision_price, decision_price_source = price_on_or_before(
                ticker=ticker,
                target_date=latest_visible_date,
                price_dir=config.price_dir,
                as_of_timestamp_utc=config.as_of_timestamp_utc,
            )
        except (FileNotFoundError, LookupError, ValueError):
            decision_price_date = None
            decision_price = None

    outcome_status = STATUS_NOT_MATURED
    outcome = empty_outcome_fields()
    no_future_decision = (
        f"as_of_date {as_of_date.isoformat()} is before horizon_end_date "
        f"{horizon_end.isoformat()}; outcome fields withheld"
    )
    price_source_path = decision_price_source
    price_row_dates_used = [decision_price_date.isoformat()] if decision_price_date else []

    if source_future_reasons:
        outcome_status = STATUS_BLOCKED_SOURCE_FUTURE_DATA
        no_future_decision = (
            "source capture artifact had decision-side future-data contamination; "
            f"blocked before outcome resolution: {', '.join(source_future_reasons)}"
        )
    elif as_of_date >= horizon_end:
        outcome_status = STATUS_BLOCKED_DATA
        no_future_decision = (
            "matured horizon, but required decision or outcome price was unavailable "
            "under next-day daily-close availability"
        )
        selected = None
        if decision_price is not None:
            selected = outcome_price_in_window(
                ticker=ticker,
                horizon_end_date=horizon_end,
                as_of_timestamp_utc=config.as_of_timestamp_utc,
                price_dir=config.price_dir,
                outcome_window_days=config.outcome_window_days,
            )
        if decision_price is not None and selected is not None:
            outcome_date, outcome_price, outcome_source = selected
            change = ((outcome_price / decision_price) - 1.0) * 100.0
            outcome = {
                "outcome_price_date": outcome_date.isoformat(),
                "outcome_price": outcome_price,
                "actual_change_pct": change,
                "actual_direction": actual_direction(change),
            }
            outcome_status = STATUS_RESOLVED
            price_source_path = outcome_source
            price_row_dates_used.append(outcome_date.isoformat())
            no_future_decision = (
                "selected first valid price date on or after horizon_end_date "
                f"within {config.outcome_window_days}-day outcome window, <= as_of_date, "
                "and visible under next-day daily-close availability"
            )

    record = {
        "schema": RESOLVER_SCHEMA,
        "resolver_run_id": config.resolver_run_id,
        "source_run_id": str(payload.get("run_id") or ""),
        "source_decision_id": source_id,
        "source_decision_artifact": artifact_ref,
        "ticker": ticker,
        "arm": str(payload.get("arm") or ""),
        "input_layer": str(payload.get("input_layer") or ""),
        "decision_date": decision_date.isoformat(),
        "horizon_days": horizon_days,
        "horizon_end_date": horizon_end.isoformat(),
        "outcome_status": outcome_status,
        "outcome_price_date": outcome["outcome_price_date"],
        "decision_price_date": decision_price_date.isoformat() if decision_price_date else None,
        "decision_price": decision_price,
        "outcome_price": outcome["outcome_price"],
        "actual_change_pct": outcome["actual_change_pct"],
        "actual_direction": outcome["actual_direction"],
        "source_future_data_violation": bool(source_future_reasons),
        "source_future_data_violation_reasons": source_future_reasons,
        "resolved_at": config.as_of_timestamp_utc.isoformat().replace("+00:00", "Z"),
        "provenance": {
            "source_capture_run_id": str(payload.get("run_id") or ""),
            "source_decision_id": source_id,
            "source_artifact_path": str(source_path),
            "source_artifact_ref": artifact_ref,
            "resolver_run_id": config.resolver_run_id,
            "resolver_script_version": RESOLVER_SCRIPT_VERSION,
            "resolver_schema": RESOLVER_SCHEMA,
            "price_source_path": price_source_path,
            "price_row_dates_used": price_row_dates_used,
            "as_of_date": as_of_date.isoformat(),
            "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
                "+00:00", "Z"
            ),
            "daily_close_availability_rule": (
                "daily close row D is visible at D+1 00:00:00 UTC or later"
            ),
            "outcome_window_days": config.outcome_window_days,
            "no_future_data_decision": no_future_decision,
        },
    }
    validate_resolution_record(record)
    write_resolution_record(record, output_root)
    return record


def validate_resolution_record(record: dict[str, Any]) -> None:
    status = str(record["outcome_status"])
    if status in {STATUS_NOT_MATURED, STATUS_BLOCKED_DATA, STATUS_BLOCKED_SOURCE_FUTURE_DATA}:
        present = [field for field in OUTCOME_FIELDS if record.get(field) is not None]
        if present:
            raise ValueError(f"{status} record must not populate outcome fields: {present}")
    if status == STATUS_RESOLVED:
        missing = [field for field in OUTCOME_FIELDS if record.get(field) is None]
        if missing:
            raise ValueError(f"RESOLVED record missing outcome fields: {missing}")


def write_resolution_record(record: dict[str, Any], output_root: Path) -> Path:
    path = (
        output_root
        / "outcomes"
        / str(record["outcome_status"]).lower()
        / f"outcome_{record['decision_date']}_{ticker_slug(str(record['ticker']))}_"
        f"{record['arm']}_{record['input_layer']}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def blocked_run_id_summary(config: ResolverConfig, output_root: Path) -> dict[str, Any]:
    summary = {
        "schema": SUMMARY_SCHEMA,
        "resolver_run_id": config.resolver_run_id,
        "status": STATUS_BLOCKED_RUN_ID_EXISTS,
        "run_root": str(output_root),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "capture_artifact_count": 0,
        "not_matured_count": 0,
        "blocked_data_count": 0,
        "blocked_source_future_data_count": 0,
        "resolved_count": 0,
        "source_future_data_violation_count": 0,
        "future_data_violation_count": 0,
        "provenance_reverse_lookup_status": "NOT_RUN",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_resolver(config: ResolverConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.resolver_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = manifest_for(config, output_root)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for source_path in find_capture_artifacts(config.capture_run_dir):
        try:
            records.append(
                resolve_capture_artifact(
                    config=config,
                    source_path=source_path,
                    output_root=output_root,
                )
            )
        except Exception as exc:  # noqa: BLE001 - resolver summaries preserve blockers.
            errors.append(
                {
                    "source_artifact": str(source_path),
                    "error_type": exc.__class__.__name__,
                    "error_message": v3.redact_error(str(exc)),
                }
            )

    summary = summary_for(config=config, output_root=output_root, records=records, errors=errors)
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(config: ResolverConfig, output_root: Path) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "resolver_run_id": config.resolver_run_id,
        "run_root": str(output_root),
        "capture_run_dir": str(config.capture_run_dir),
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "price_dir": str(config.price_dir),
        "outcome_window_days": config.outcome_window_days,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
    }


def summary_for(
    *,
    config: ResolverConfig,
    output_root: Path,
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = {
        STATUS_NOT_MATURED: 0,
        STATUS_BLOCKED_DATA: 0,
        STATUS_BLOCKED_SOURCE_FUTURE_DATA: 0,
        STATUS_RESOLVED: 0,
    }
    for record in records:
        status_counts[str(record["outcome_status"])] += 1
    source_future_violations = sum(
        1 for record in records if bool(record.get("source_future_data_violation"))
    )
    provenance_ok = all(
        record.get("provenance", {}).get("source_capture_run_id")
        and record.get("provenance", {}).get("source_decision_id")
        and record.get("provenance", {}).get("source_artifact_ref")
        for record in records
    )
    summary_status = (
        "OUTCOME_RESOLVER_PASS"
        if records and not errors and provenance_ok and source_future_violations == 0
        else "OUTCOME_RESOLVER_FAIL"
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "resolver_run_id": config.resolver_run_id,
        "status": summary_status,
        "run_root": str(output_root),
        "capture_run_dir": str(config.capture_run_dir),
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "outcome_window_days": config.outcome_window_days,
        "capture_artifact_count": len(records),
        "not_matured_count": status_counts[STATUS_NOT_MATURED],
        "blocked_data_count": status_counts[STATUS_BLOCKED_DATA],
        "blocked_source_future_data_count": status_counts[STATUS_BLOCKED_SOURCE_FUTURE_DATA],
        "resolved_count": status_counts[STATUS_RESOLVED],
        "resolver_error_count": len(errors),
        "resolver_errors": errors[:10],
        "source_future_data_violation_count": source_future_violations,
        "future_data_violation_count": source_future_violations,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "provenance_reverse_lookup_status": "PASS" if provenance_ok and records else "FAIL",
        "evidence_layer": "local engineering validation only; outcome maturity resolution",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not formal-lite",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-run-dir", type=Path, required=True)
    parser.add_argument("--resolver-run-id", required=True)
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--outcome-window-days", type=int, default=DEFAULT_OUTCOME_WINDOW_DAYS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ResolverConfig:
    return ResolverConfig(
        capture_run_dir=args.capture_run_dir,
        resolver_run_id=str(args.resolver_run_id),
        as_of_timestamp_utc=parse_as_of_timestamp(str(args.as_of_timestamp_utc or "")),
        price_dir=args.price_dir,
        output_dir=args.output_dir,
        outcome_window_days=int(args.outcome_window_days),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_resolver(config_from_args(parse_args(argv)))
    return 0 if str(summary.get("status")) == "OUTCOME_RESOLVER_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
