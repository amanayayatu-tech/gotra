#!/usr/bin/env python3
"""GOTRA v3.5C forward-live outcome maturity scheduler."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver
from scripts import baseline_v3_four_arm as v3


SCHEDULER_SCHEMA = "gotra.baseline_v3_5c.forward_live_outcome_scheduler.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3_5c.forward_live_outcome_scheduler_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_5c.forward_live_outcome_scheduler_manifest.v1"
SCHEDULER_RUN_ID_PREFIX = "baseline_v3_5c_outcome_scheduler_"
SCHEDULER_SCRIPT_VERSION = "v3.5c-20260621"

STATUS_PASS = "OUTCOME_SCHEDULER_PASS"
STATUS_FAIL = "OUTCOME_SCHEDULER_FAIL"
STATUS_BLOCKED_RUN_ID_EXISTS = "OUTCOME_SCHEDULER_BLOCKED_RUN_ID_EXISTS"


@dataclass(frozen=True)
class SchedulerConfig:
    capture_run_dir: Path
    scheduler_run_id: str
    as_of_timestamp_utc: datetime
    price_dir: Path
    output_dir: Path
    outcome_window_days: int = resolver.DEFAULT_OUTCOME_WINDOW_DAYS
    allow_overwrite: bool = False


def parse_as_of_timestamp(value: str | None) -> datetime:
    return resolver.parse_as_of_timestamp(value)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(SCHEDULER_RUN_ID_PREFIX):
        raise ValueError(f"scheduler_run_id must start with {SCHEDULER_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("scheduler_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: SchedulerConfig) -> None:
    validate_run_id(config.scheduler_run_id)
    if not config.capture_run_dir.exists():
        raise FileNotFoundError(f"capture run dir not found: {config.capture_run_dir}")
    if config.outcome_window_days < 0:
        raise ValueError("outcome_window_days must be >= 0")


def resolver_run_id_for(config: SchedulerConfig) -> str:
    suffix = config.scheduler_run_id.removeprefix(SCHEDULER_RUN_ID_PREFIX)
    return f"{resolver.RESOLVER_RUN_ID_PREFIX}scheduled_{suffix}"


def resolver_config_for(config: SchedulerConfig) -> resolver.ResolverConfig:
    return resolver.ResolverConfig(
        capture_run_dir=canonical_capture_run_root(config.capture_run_dir),
        resolver_run_id=resolver_run_id_for(config),
        as_of_timestamp_utc=config.as_of_timestamp_utc,
        price_dir=config.price_dir,
        output_dir=config.output_dir,
        outcome_window_days=config.outcome_window_days,
        allow_overwrite=config.allow_overwrite,
    )


def load_json(path: Path) -> dict[str, Any]:
    return resolver.load_json(path)


def canonical_capture_run_root(capture_run_dir: Path) -> Path:
    """Return the capture run root for either run root or its captures/ child."""

    if capture_run_dir.name == "captures":
        return capture_run_dir.parent
    return capture_run_dir


def capture_source_run_ids(capture_paths: list[Path]) -> list[str]:
    run_ids: set[str] = set()
    for path in capture_paths:
        try:
            payload = load_json(path)
        except Exception:
            continue
        run_id = str(payload.get("run_id") or "")
        if run_id:
            run_ids.add(run_id)
    return sorted(run_ids)


def source_id_for_capture(path: Path, capture_run_dir: Path) -> str:
    capture_run_dir = canonical_capture_run_root(capture_run_dir)
    payload = load_json(path)
    artifact_ref = resolver.source_artifact_ref(path, capture_run_dir)
    return resolver.source_decision_id(payload, artifact_ref)


def source_future_data_guard_record(
    *,
    config: SchedulerConfig,
    source_path: Path,
    capture_run_dir: Path,
) -> dict[str, Any] | None:
    capture_run_dir = canonical_capture_run_root(capture_run_dir)
    payload = load_json(source_path)
    decision_date = resolver.date_from_capture(payload, "decision_date_local", "decision_date")
    latest_visible_date = resolver.date_from_capture(
        payload,
        "latest_visible_price_date",
        "decision_date_local",
    )
    reasons = resolver.source_future_data_violation_reasons(
        payload=payload,
        decision_date=decision_date,
        latest_visible_date=latest_visible_date,
    )
    if not reasons:
        return None
    artifact_ref = resolver.source_artifact_ref(source_path, capture_run_dir)
    source_id = resolver.source_decision_id(payload, artifact_ref)
    horizon_end = resolver.date_from_capture(payload, "horizon_end_date")
    record = {
        "schema": resolver.RESOLVER_SCHEMA,
        "resolver_run_id": resolver_run_id_for(config),
        "source_run_id": str(payload.get("run_id") or ""),
        "source_decision_id": source_id,
        "source_decision_artifact": artifact_ref,
        "ticker": str(payload["ticker"]),
        "arm": str(payload.get("arm") or ""),
        "input_layer": str(payload.get("input_layer") or ""),
        "decision_date": decision_date.isoformat(),
        "horizon_days": int(payload.get("horizon_days") or v3.WINDOW_DAYS),
        "horizon_end_date": horizon_end.isoformat(),
        "outcome_status": resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA,
        "outcome_price_date": None,
        "decision_price_date": None,
        "decision_price": None,
        "outcome_price": None,
        "actual_change_pct": None,
        "actual_direction": None,
        "source_future_data_violation": True,
        "source_future_data_violation_reasons": reasons,
        "resolved_at": config.as_of_timestamp_utc.isoformat().replace("+00:00", "Z"),
        "provenance": {
            "source_capture_run_id": str(payload.get("run_id") or ""),
            "source_decision_id": source_id,
            "source_artifact_path": str(source_path),
            "source_artifact_ref": artifact_ref,
            "resolver_run_id": resolver_run_id_for(config),
            "resolver_script_version": resolver.RESOLVER_SCRIPT_VERSION,
            "resolver_schema": resolver.RESOLVER_SCHEMA,
            "price_source_path": "",
            "price_row_dates_used": [],
            "as_of_date": config.as_of_timestamp_utc.date().isoformat(),
            "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
                "+00:00", "Z"
            ),
            "daily_close_availability_rule": (
                "daily close row D is visible at D+1 00:00:00 UTC or later"
            ),
            "outcome_window_days": config.outcome_window_days,
            "no_future_data_decision": (
                "source capture artifact had decision-side future-data contamination; "
                f"blocked before duplicate/existing outcome skip: {', '.join(reasons)}"
            ),
        },
    }
    resolver.validate_resolution_record(record)
    return record


def existing_resolved_source_ids(output_dir: Path, *, exclude_root: Path | None = None) -> set[str]:
    source_ids: set[str] = set()
    if not output_dir.exists():
        return source_ids
    for path in sorted(output_dir.glob("**/outcomes/resolved/*.json")):
        if exclude_root is not None:
            try:
                path.relative_to(exclude_root)
                continue
            except ValueError:
                pass
        try:
            payload = load_json(path)
        except Exception:
            continue
        if (
            payload.get("schema") == resolver.RESOLVER_SCHEMA
            and payload.get("outcome_status") == resolver.STATUS_RESOLVED
        ):
            source_id = str(payload.get("source_decision_id") or "")
            if source_id:
                source_ids.add(source_id)
    return source_ids


def add_scheduler_provenance(
    record: dict[str, Any],
    *,
    config: SchedulerConfig,
    resolver_run_id: str,
) -> dict[str, Any]:
    updated = dict(record)
    updated["scheduler_run_id"] = config.scheduler_run_id
    updated["scheduler_schema"] = SCHEDULER_SCHEMA
    updated["scheduler_script_version"] = SCHEDULER_SCRIPT_VERSION
    provenance = dict(updated.get("provenance") or {})
    provenance.update(
        {
            "scheduler_run_id": config.scheduler_run_id,
            "scheduler_schema": SCHEDULER_SCHEMA,
            "scheduler_script_version": SCHEDULER_SCRIPT_VERSION,
            "resolver_run_id": resolver_run_id,
        }
    )
    updated["provenance"] = provenance
    resolver.validate_resolution_record(updated)
    return updated


def provenance_link_ok(record: dict[str, Any]) -> bool:
    provenance = record.get("provenance") or {}
    return bool(
        record.get("scheduler_run_id")
        and record.get("resolver_run_id")
        and record.get("source_decision_id")
        and record.get("source_decision_artifact")
        and provenance.get("scheduler_run_id")
        and provenance.get("resolver_run_id")
        and provenance.get("source_decision_id")
        and provenance.get("source_artifact_ref")
    )


def blocked_run_id_summary(config: SchedulerConfig, output_root: Path) -> dict[str, Any]:
    summary = {
        "schema": SUMMARY_SCHEMA,
        "scheduler_run_id": config.scheduler_run_id,
        "status": STATUS_BLOCKED_RUN_ID_EXISTS,
        "run_root": str(output_root),
        "source_capture_run_id": "",
        "source_capture_run_ids": [],
        "source_capture_path": str(canonical_capture_run_root(config.capture_run_dir)),
        "resolver_run_ids": [],
        "scanned_decision_count": 0,
        "not_matured_count": 0,
        "resolved_count": 0,
        "blocked_data_count": 0,
        "blocked_future_data_count": 0,
        "duplicate_or_existing_outcome_count": 0,
        "future_data_violation_count": 0,
        "provenance_link_count": 0,
        "scheduler_error_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "engineering/local validation only",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_scheduler(config: SchedulerConfig) -> dict[str, Any]:
    validate_config(config)
    capture_root = canonical_capture_run_root(config.capture_run_dir)
    output_root = config.output_dir / config.scheduler_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    capture_paths = resolver.find_capture_artifacts(capture_root)
    source_run_ids = capture_source_run_ids(capture_paths)
    resolver_run_id = resolver_run_id_for(config)
    resolver_output_root = output_root / "resolver_outputs" / resolver_run_id
    resolver_output_root.mkdir(parents=True, exist_ok=True)
    manifest = manifest_for(
        config=config,
        output_root=output_root,
        resolver_run_id=resolver_run_id,
        source_run_ids=source_run_ids,
    )
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    existing_resolved = existing_resolved_source_ids(config.output_dir, exclude_root=output_root)
    seen_source_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    duplicate_or_existing = 0
    resolver_config = resolver_config_for(config)
    for source_path in capture_paths:
        try:
            source_id = source_id_for_capture(source_path, capture_root)
            guard_record = source_future_data_guard_record(
                config=config,
                source_path=source_path,
                capture_run_dir=capture_root,
            )
            if guard_record is not None:
                guard_record = add_scheduler_provenance(
                    guard_record,
                    config=config,
                    resolver_run_id=resolver_run_id,
                )
                resolver.write_resolution_record(guard_record, resolver_output_root)
                records.append(guard_record)
                seen_source_ids.add(source_id)
                continue
            if source_id in existing_resolved or source_id in seen_source_ids:
                duplicate_or_existing += 1
                continue
            seen_source_ids.add(source_id)
            record = resolver.resolve_capture_artifact(
                config=resolver_config,
                source_path=source_path,
                output_root=resolver_output_root,
            )
            record = add_scheduler_provenance(
                record,
                config=config,
                resolver_run_id=resolver_run_id,
            )
            resolver.write_resolution_record(record, resolver_output_root)
            records.append(record)
        except Exception as exc:  # noqa: BLE001 - scheduler summary preserves blockers.
            errors.append(
                {
                    "source_artifact": str(source_path),
                    "error_type": exc.__class__.__name__,
                    "error_message": v3.redact_error(str(exc)),
                }
            )

    summary = summary_for(
        config=config,
        output_root=output_root,
        records=records,
        errors=errors,
        capture_paths=capture_paths,
        source_run_ids=source_run_ids,
        resolver_run_id=resolver_run_id,
        duplicate_or_existing=duplicate_or_existing,
        started_at=started_at,
        completed_at=datetime.now(UTC).replace(microsecond=0),
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(
    *,
    config: SchedulerConfig,
    output_root: Path,
    resolver_run_id: str,
    source_run_ids: list[str],
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "scheduler_run_id": config.scheduler_run_id,
        "run_root": str(output_root),
        "source_capture_run_id": source_run_ids[0] if len(source_run_ids) == 1 else "",
        "source_capture_run_ids": source_run_ids,
        "source_capture_path": str(canonical_capture_run_root(config.capture_run_dir)),
        "resolver_run_ids": [resolver_run_id],
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
    config: SchedulerConfig,
    output_root: Path,
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    capture_paths: list[Path],
    source_run_ids: list[str],
    resolver_run_id: str,
    duplicate_or_existing: int,
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, Any]:
    status_counts = {
        resolver.STATUS_NOT_MATURED: 0,
        resolver.STATUS_BLOCKED_DATA: 0,
        resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA: 0,
        resolver.STATUS_RESOLVED: 0,
    }
    for record in records:
        status_counts[str(record["outcome_status"])] += 1
    future_data_violations = status_counts[resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA]
    provenance_links = sum(1 for record in records if provenance_link_ok(record))
    provenance_ok = provenance_links == len(records)
    status = (
        STATUS_PASS
        if capture_paths
        and not errors
        and future_data_violations == 0
        and provenance_ok
        else STATUS_FAIL
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "scheduler_run_id": config.scheduler_run_id,
        "status": status,
        "run_root": str(output_root),
        "source_capture_run_id": source_run_ids[0] if len(source_run_ids) == 1 else "",
        "source_capture_run_ids": source_run_ids,
        "source_capture_path": str(canonical_capture_run_root(config.capture_run_dir)),
        "resolver_run_ids": [resolver_run_id] if records else [],
        "scanned_decision_count": len(capture_paths),
        "not_matured_count": status_counts[resolver.STATUS_NOT_MATURED],
        "resolved_count": status_counts[resolver.STATUS_RESOLVED],
        "blocked_data_count": status_counts[resolver.STATUS_BLOCKED_DATA],
        "blocked_future_data_count": status_counts[resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA],
        "duplicate_or_existing_outcome_count": duplicate_or_existing,
        "future_data_violation_count": future_data_violations,
        "source_future_data_violation_count": future_data_violations,
        "provenance_link_count": provenance_links,
        "scheduler_error_count": len(errors),
        "scheduler_errors": errors[:10],
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "forward-live scheduler engineering/local validation only",
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
    parser.add_argument("--scheduler-run-id", required=True)
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--outcome-window-days", type=int, default=resolver.DEFAULT_OUTCOME_WINDOW_DAYS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> SchedulerConfig:
    return SchedulerConfig(
        capture_run_dir=args.capture_run_dir,
        scheduler_run_id=str(args.scheduler_run_id),
        as_of_timestamp_utc=parse_as_of_timestamp(str(args.as_of_timestamp_utc or "")),
        price_dir=args.price_dir,
        output_dir=args.output_dir,
        outcome_window_days=int(args.outcome_window_days),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_scheduler(config_from_args(parse_args(argv)))
    return 0 if str(summary.get("status")) == STATUS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
