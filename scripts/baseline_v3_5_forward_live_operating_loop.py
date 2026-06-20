#!/usr/bin/env python3
"""GOTRA v3.5D forward-live operating-loop dry-run orchestrator."""

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
from scripts import baseline_v3_5_forward_live_outcome_scheduler as scheduler


OPERATING_LOOP_SCHEMA = "gotra.baseline_v3_5d.forward_live_operating_loop.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3_5d.forward_live_operating_loop_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_5d.forward_live_operating_loop_manifest.v1"
OPERATING_LOOP_RUN_ID_PREFIX = "baseline_v3_5d_operating_loop_"
OPERATING_LOOP_SCRIPT_VERSION = "v3.5d-20260621"

STATUS_PASS = "OPERATING_LOOP_PASS"
STATUS_FAIL = "OPERATING_LOOP_FAIL"
STATUS_BLOCKED_RUN_ID_EXISTS = "OPERATING_LOOP_BLOCKED_RUN_ID_EXISTS"
STATUS_BLOCKED_SOURCE_FUTURE_DATA = "BLOCKED_SOURCE_FUTURE_DATA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"

OUTCOME_STATUS_NO_CAPTURE_ARTIFACTS = "NO_CAPTURE_ARTIFACTS"
OUTCOME_STATUS_NO_MATURED = "NO_MATURED_OUTCOMES"
OUTCOME_STATUS_DATA_BLOCKED = "DATA_BLOCKED_MISSING_PRICE"
OUTCOME_STATUS_RESOLVED_AVAILABLE = "RESOLVED_OUTCOMES_AVAILABLE_NO_VERDICT"
OUTCOME_STATUS_SOURCE_FUTURE_DATA = "BLOCKED_SOURCE_FUTURE_DATA"
OUTCOME_STATUS_PROVENANCE = "BLOCKED_PROVENANCE"
OUTCOME_STATUS_SCHEDULER_ERROR = "SCHEDULER_ERROR"


@dataclass(frozen=True)
class OperatingLoopConfig:
    capture_run_dir: Path
    operating_loop_run_id: str
    as_of_timestamp_utc: datetime
    price_dir: Path
    output_dir: Path
    outcome_window_days: int = resolver.DEFAULT_OUTCOME_WINDOW_DAYS
    allow_overwrite: bool = False


def parse_as_of_timestamp(value: str | None) -> datetime:
    return scheduler.parse_as_of_timestamp(value)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(OPERATING_LOOP_RUN_ID_PREFIX):
        raise ValueError(f"operating_loop_run_id must start with {OPERATING_LOOP_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("operating_loop_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: OperatingLoopConfig) -> None:
    validate_run_id(config.operating_loop_run_id)
    if not config.capture_run_dir.exists():
        raise FileNotFoundError(f"capture run dir not found: {config.capture_run_dir}")
    if config.outcome_window_days < 0:
        raise ValueError("outcome_window_days must be >= 0")


def scheduler_run_id_for(config: OperatingLoopConfig) -> str:
    suffix = config.operating_loop_run_id.removeprefix(OPERATING_LOOP_RUN_ID_PREFIX)
    return f"{scheduler.SCHEDULER_RUN_ID_PREFIX}operating_loop_{suffix}"


def scheduler_state_dir(config: OperatingLoopConfig) -> Path:
    return config.output_dir / "_v3_5d_scheduler_state"


def scheduler_config_for(config: OperatingLoopConfig) -> scheduler.SchedulerConfig:
    return scheduler.SchedulerConfig(
        capture_run_dir=scheduler.canonical_capture_run_root(config.capture_run_dir),
        scheduler_run_id=scheduler_run_id_for(config),
        as_of_timestamp_utc=config.as_of_timestamp_utc,
        price_dir=config.price_dir,
        output_dir=scheduler_state_dir(config),
        outcome_window_days=config.outcome_window_days,
        allow_overwrite=config.allow_overwrite,
    )


def blocked_run_id_summary(config: OperatingLoopConfig, output_root: Path) -> dict[str, Any]:
    summary = {
        "schema": SUMMARY_SCHEMA,
        "operating_loop_run_id": config.operating_loop_run_id,
        "status": STATUS_BLOCKED_RUN_ID_EXISTS,
        "outcome_scoring_status": STATUS_BLOCKED_RUN_ID_EXISTS,
        "run_root": str(output_root),
        "capture_count": 0,
        "not_matured_count": 0,
        "resolved_count": 0,
        "blocked_data_count": 0,
        "blocked_future_data_count": 0,
        "duplicate_existing_count": 0,
        "provenance_link_count": 0,
        "audit_event_count": 0,
        "audit_event_status": "not_connected",
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "forward-live operating-loop engineering/local validation only",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_operating_loop(config: OperatingLoopConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.operating_loop_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    sched_config = scheduler_config_for(config)
    scheduler_summary = scheduler.run_scheduler(sched_config)
    scheduler_summary_path = scheduler_state_dir(config) / sched_config.scheduler_run_id / "summary.json"
    outcome_paths = scheduler_outcome_paths(sched_config)
    provenance_links = provenance_links_for(
        outcome_paths=outcome_paths,
        scheduler_summary_path=scheduler_summary_path,
    )
    summary = summary_for(
        config=config,
        output_root=output_root,
        scheduler_summary=scheduler_summary,
        scheduler_summary_path=scheduler_summary_path,
        provenance_links=provenance_links,
        started_at=started_at,
        completed_at=datetime.now(UTC).replace(microsecond=0),
    )
    manifest = manifest_for(config=config, output_root=output_root, summary=summary)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def scheduler_outcome_paths(config: scheduler.SchedulerConfig) -> list[Path]:
    root = config.output_dir / config.scheduler_run_id
    return sorted(root.glob("resolver_outputs/**/outcomes/**/*.json"))


def provenance_links_for(
    *,
    outcome_paths: list[Path],
    scheduler_summary_path: Path,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for outcome_path in outcome_paths:
        try:
            record = scheduler.load_json(outcome_path)
        except Exception:
            continue
        provenance = record.get("provenance") or {}
        source_artifact_path = str(provenance.get("source_artifact_path") or "")
        link = {
            "source_capture_run_id": str(provenance.get("source_capture_run_id") or ""),
            "source_decision_id": str(record.get("source_decision_id") or ""),
            "source_decision_artifact": str(record.get("source_decision_artifact") or ""),
            "source_artifact_path": source_artifact_path,
            "source_artifact_exists": bool(source_artifact_path)
            and Path(source_artifact_path).exists(),
            "scheduler_run_id": str(record.get("scheduler_run_id") or ""),
            "scheduler_summary_path": str(scheduler_summary_path),
            "scheduler_summary_exists": scheduler_summary_path.exists(),
            "resolver_run_id": str(record.get("resolver_run_id") or ""),
            "outcome_status": str(record.get("outcome_status") or ""),
            "outcome_artifact_path": str(outcome_path),
            "outcome_artifact_exists": outcome_path.exists(),
            "audit_event_hash": None,
            "audit_event_status": "not_connected",
        }
        link["provenance_ok"] = bool(
            link["source_capture_run_id"]
            and link["source_decision_id"]
            and link["source_decision_artifact"]
            and link["source_artifact_exists"]
            and link["scheduler_run_id"]
            and link["scheduler_summary_exists"]
            and link["resolver_run_id"]
            and link["outcome_artifact_exists"]
        )
        links.append(link)
    return links


def summary_for(
    *,
    config: OperatingLoopConfig,
    output_root: Path,
    scheduler_summary: dict[str, Any],
    scheduler_summary_path: Path,
    provenance_links: list[dict[str, Any]],
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, Any]:
    capture_count = int(scheduler_summary.get("scanned_decision_count") or 0)
    not_matured = int(scheduler_summary.get("not_matured_count") or 0)
    resolved = int(scheduler_summary.get("resolved_count") or 0)
    blocked_data = int(scheduler_summary.get("blocked_data_count") or 0)
    blocked_future = int(scheduler_summary.get("blocked_future_data_count") or 0)
    duplicate_existing = int(scheduler_summary.get("duplicate_or_existing_outcome_count") or 0)
    scheduler_errors = int(scheduler_summary.get("scheduler_error_count") or 0)
    provenance_ok = all(bool(link.get("provenance_ok")) for link in provenance_links)
    if not provenance_links and capture_count > duplicate_existing:
        provenance_ok = False
    outcome_status = outcome_scoring_status(
        capture_count=capture_count,
        not_matured_count=not_matured,
        resolved_count=resolved,
        blocked_data_count=blocked_data,
        blocked_future_data_count=blocked_future,
        scheduler_error_count=scheduler_errors,
        provenance_ok=provenance_ok,
    )
    status = operating_loop_status(
        scheduler_status=str(scheduler_summary.get("status") or ""),
        capture_count=capture_count,
        blocked_future_data_count=blocked_future,
        scheduler_error_count=scheduler_errors,
        provenance_ok=provenance_ok,
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "operating_loop_run_id": config.operating_loop_run_id,
        "status": status,
        "outcome_scoring_status": outcome_status,
        "run_root": str(output_root),
        "capture_run_dir": str(scheduler.canonical_capture_run_root(config.capture_run_dir)),
        "capture_count": capture_count,
        "not_matured_count": not_matured,
        "resolved_count": resolved,
        "blocked_data_count": blocked_data,
        "blocked_future_data_count": blocked_future,
        "duplicate_existing_count": duplicate_existing,
        "provenance_link_count": sum(1 for link in provenance_links if link["provenance_ok"]),
        "provenance_links": provenance_links,
        "audit_event_count": 0,
        "audit_event_status": "not_connected",
        "audit_event_note": (
            "v3.5D writes ignored local run artifacts and does not perform a "
            "Judge/Gate knowledge transition; audit chain wiring is intentionally "
            "not connected in this engineering dry-run."
        ),
        "scheduler_run_id": str(scheduler_summary.get("scheduler_run_id") or ""),
        "scheduler_status": str(scheduler_summary.get("status") or ""),
        "scheduler_summary_path": str(scheduler_summary_path),
        "resolver_run_ids": list(scheduler_summary.get("resolver_run_ids") or []),
        "source_capture_run_id": str(scheduler_summary.get("source_capture_run_id") or ""),
        "source_capture_run_ids": list(scheduler_summary.get("source_capture_run_ids") or []),
        "source_future_data_violation_count": int(
            scheduler_summary.get("source_future_data_violation_count") or 0
        ),
        "future_data_violation_count": int(
            scheduler_summary.get("future_data_violation_count") or 0
        ),
        "scheduler_error_count": scheduler_errors,
        "scheduler_errors": list(scheduler_summary.get("scheduler_errors") or []),
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "forward-live operating-loop engineering/local validation only",
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not formal-lite",
            "no full_gotra/ksana/alaya win-loss verdict",
        ],
    }


def outcome_scoring_status(
    *,
    capture_count: int,
    not_matured_count: int,
    resolved_count: int,
    blocked_data_count: int,
    blocked_future_data_count: int,
    scheduler_error_count: int,
    provenance_ok: bool,
) -> str:
    if capture_count == 0:
        return OUTCOME_STATUS_NO_CAPTURE_ARTIFACTS
    if scheduler_error_count:
        return OUTCOME_STATUS_SCHEDULER_ERROR
    if blocked_future_data_count:
        return OUTCOME_STATUS_SOURCE_FUTURE_DATA
    if not provenance_ok:
        return OUTCOME_STATUS_PROVENANCE
    if resolved_count:
        return OUTCOME_STATUS_RESOLVED_AVAILABLE
    if blocked_data_count:
        return OUTCOME_STATUS_DATA_BLOCKED
    if not_matured_count:
        return OUTCOME_STATUS_NO_MATURED
    return OUTCOME_STATUS_NO_CAPTURE_ARTIFACTS


def operating_loop_status(
    *,
    scheduler_status: str,
    capture_count: int,
    blocked_future_data_count: int,
    scheduler_error_count: int,
    provenance_ok: bool,
) -> str:
    if blocked_future_data_count:
        return STATUS_BLOCKED_SOURCE_FUTURE_DATA
    if scheduler_error_count:
        return STATUS_FAIL
    if not provenance_ok:
        return STATUS_BLOCKED_PROVENANCE
    if scheduler_status != scheduler.STATUS_PASS or capture_count == 0:
        return STATUS_FAIL
    return STATUS_PASS


def manifest_for(
    *,
    config: OperatingLoopConfig,
    output_root: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "operating_loop_run_id": config.operating_loop_run_id,
        "run_root": str(output_root),
        "capture_run_dir": str(scheduler.canonical_capture_run_root(config.capture_run_dir)),
        "scheduler_run_id": summary["scheduler_run_id"],
        "resolver_run_ids": summary["resolver_run_ids"],
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "price_dir": str(config.price_dir),
        "outcome_window_days": config.outcome_window_days,
        "operating_loop_script_version": OPERATING_LOOP_SCRIPT_VERSION,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "forward-live operating-loop engineering/local validation only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-run-dir", type=Path, required=True)
    parser.add_argument("--operating-loop-run-id", required=True)
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument(
        "--outcome-window-days",
        type=int,
        default=resolver.DEFAULT_OUTCOME_WINDOW_DAYS,
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> OperatingLoopConfig:
    return OperatingLoopConfig(
        capture_run_dir=args.capture_run_dir,
        operating_loop_run_id=str(args.operating_loop_run_id),
        as_of_timestamp_utc=parse_as_of_timestamp(str(args.as_of_timestamp_utc or "")),
        price_dir=args.price_dir,
        output_dir=args.output_dir,
        outcome_window_days=int(args.outcome_window_days),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_operating_loop(config_from_args(parse_args(argv)))
    return 0 if str(summary.get("status")) == STATUS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
