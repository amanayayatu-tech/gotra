#!/usr/bin/env python3
"""GOTRA v3.6T forward-live maturity monitor operations ledger."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness_v36
from scripts import baseline_v3_6s_actual_maturity_monitor as monitor_v36s


SUMMARY_SCHEMA = "gotra.baseline_v3_6t.forward_live_monitor_ops_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6t.forward_live_monitor_ops_manifest.v1"
LEDGER_SCHEMA = "gotra.baseline_v3_6t.forward_live_monitor_ops_ledger.v1"
OPS_RUN_ID_PREFIX = "baseline_v3_6t_monitor_ops_"
OPS_SCRIPT_VERSION = "v3.6t-20260621"

STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_RUN_ID_EXISTS = "MONITOR_OPS_BLOCKED_RUN_ID_EXISTS"

RECOMMEND_WAIT_UNTIL_NEXT_CHECK = "WAIT_UNTIL_NEXT_CHECK"
RECOMMEND_RECHECK_NOW_ALLOWED = "RECHECK_NOW_ALLOWED"
RECOMMEND_FIX_BLOCKER = "FIX_BLOCKER"
RECOMMEND_PLAN_V3_7_ONLY_IF_READY = "PLAN_V3_7_ONLY_IF_READY"

BLOCKED_STATUSES = {
    monitor_v36s.STATUS_BLOCKED_DATA,
    monitor_v36s.STATUS_BLOCKED_SOURCE_FUTURE_DATA,
    monitor_v36s.STATUS_BLOCKED_RUN_ID_EXISTS,
    monitor_v36s.STATUS_FAIL,
    "BLOCKED_PROVENANCE",
}


@dataclass(frozen=True)
class OpsConfig:
    input_roots: tuple[Path, ...]
    ops_run_id: str
    output_dir: Path
    as_of_timestamp_utc: datetime
    allow_overwrite: bool = False


@dataclass(frozen=True)
class MonitorEntry:
    path: Path
    sha256: str
    payload: dict[str, Any]


def parse_as_of_timestamp(value: str | None) -> datetime:
    return monitor_v36s.parse_as_of_timestamp(value)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(OPS_RUN_ID_PREFIX):
        raise ValueError(f"ops_run_id must start with {OPS_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("ops_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: OpsConfig) -> None:
    validate_run_id(config.ops_run_id)
    if not config.input_roots:
        raise ValueError("at least one input root is required")
    for root in config.input_roots:
        if not root.exists():
            raise FileNotFoundError(f"input root not found: {root}")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_json_paths(input_roots: tuple[Path, ...]) -> list[Path]:
    paths: set[Path] = set()
    for root in input_roots:
        if root.is_file() and root.suffix.lower() == ".json":
            paths.add(root)
        elif root.is_dir():
            paths.update(root.glob("**/*.json"))
    return sorted(paths)


def find_monitor_summaries(input_roots: tuple[Path, ...]) -> list[MonitorEntry]:
    entries: list[MonitorEntry] = []
    for path in candidate_json_paths(input_roots):
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == monitor_v36s.SUMMARY_SCHEMA:
            entries.append(MonitorEntry(path=path, sha256=sha256_file(path), payload=payload))
    return sorted(entries, key=entry_sort_key)


def parse_timestamp(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def entry_sort_key(entry: MonitorEntry) -> tuple[datetime, datetime, str, str]:
    payload = entry.payload
    return (
        parse_timestamp(payload.get("as_of_timestamp_utc")),
        parse_timestamp(payload.get("completed_at")),
        str(payload.get("monitor_run_id") or ""),
        str(entry.path),
    )


def latest_entry(entries: list[MonitorEntry]) -> MonitorEntry | None:
    if not entries:
        return None
    return max(entries, key=entry_sort_key)


def readiness_ready_for_current_monitor(payload: dict[str, Any]) -> bool:
    return (
        str(payload.get("readiness_status") or "") == readiness_v36.STATUS_READY
        and payload.get("next_stage_planning_allowed") is True
        and payload.get("resolver_path_eligible") is True
        and str(payload.get("status") or "") == monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE
        and payload.get("v3_7_verdict_executed") is False
    )


def next_check_due(payload: dict[str, Any], *, as_of_timestamp_utc: datetime) -> bool:
    next_check_after = str(payload.get("next_check_after") or "")
    if not next_check_after:
        return False
    return parse_timestamp(next_check_after) <= as_of_timestamp_utc


def recommendation_for(
    payload: dict[str, Any],
    *,
    as_of_timestamp_utc: datetime,
) -> str:
    status = str(payload.get("status") or "")
    if readiness_ready_for_current_monitor(payload):
        return RECOMMEND_PLAN_V3_7_ONLY_IF_READY
    if str(payload.get("readiness_status") or "") == readiness_v36.STATUS_READY:
        return RECOMMEND_FIX_BLOCKER
    if status in BLOCKED_STATUSES:
        return RECOMMEND_FIX_BLOCKER
    if status == monitor_v36s.STATUS_DATA_NOT_MATURED:
        if next_check_due(payload, as_of_timestamp_utc=as_of_timestamp_utc):
            return RECOMMEND_RECHECK_NOW_ALLOWED
        return RECOMMEND_WAIT_UNTIL_NEXT_CHECK
    if status == monitor_v36s.STATUS_DATA_INSUFFICIENT:
        return RECOMMEND_FIX_BLOCKER
    if status == monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE:
        return RECOMMEND_RECHECK_NOW_ALLOWED
    return RECOMMEND_FIX_BLOCKER


def ledger_entry_for(entry: MonitorEntry) -> dict[str, Any]:
    payload = entry.payload
    return {
        "summary_path": str(entry.path),
        "summary_sha256": entry.sha256,
        "monitor_run_id": str(payload.get("monitor_run_id") or ""),
        "status": str(payload.get("status") or ""),
        "as_of_timestamp_utc": str(payload.get("as_of_timestamp_utc") or ""),
        "completed_at": str(payload.get("completed_at") or ""),
        "next_check_after": str(payload.get("next_check_after") or ""),
        "checked_capture_run_count": int(payload.get("checked_capture_run_count") or 0),
        "not_matured_count": int(payload.get("not_matured_count") or 0),
        "matured_candidate_count": int(payload.get("matured_candidate_count") or 0),
        "blocked_data_count": int(payload.get("blocked_data_count") or 0),
        "resolved_count": int(payload.get("resolved_count") or 0),
        "scored_count": int(payload.get("scored_count") or 0),
        "readiness_status": str(payload.get("readiness_status") or ""),
        "next_stage_planning_allowed": payload.get("next_stage_planning_allowed") is True,
        "resolver_path_eligible": payload.get("resolver_path_eligible") is True,
        "v3_7_verdict_executed": payload.get("v3_7_verdict_executed") is True,
    }


def blocked_run_id_summary(config: OpsConfig, output_root: Path) -> dict[str, Any]:
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "latest_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "next_action_recommendation": RECOMMEND_FIX_BLOCKER,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def base_summary(*, config: OpsConfig, output_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "ops_run_id": config.ops_run_id,
        "run_root": str(output_root),
        "status": STATUS_DATA_INSUFFICIENT,
        "evidence_layer": "engineering/local monitor operations only",
        "input_roots": [str(root) for root in config.input_roots],
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "monitor_run_count": 0,
        "latest_monitor_run_id": "",
        "latest_status": STATUS_DATA_INSUFFICIENT,
        "latest_next_check_after": "",
        "checked_capture_run_count": 0,
        "not_matured_count": 0,
        "matured_candidate_count": 0,
        "blocked_data_count": 0,
        "resolved_count": 0,
        "scored_count": 0,
        "readiness_status": monitor_v36s.READINESS_NOT_RUN,
        "next_stage_planning_allowed": False,
        "next_action_recommendation": RECOMMEND_FIX_BLOCKER,
        "v3_7_verdict_allowed": False,
        "v3_7_verdict_executed": False,
        "ledger_entry_count": 0,
        "ledger_entries": [],
        "latest_summary_path": "",
        "latest_summary_sha256": "",
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a forward-live verdict",
            "no full_gotra/deterministic/ksana winner verdict",
        ],
        "blocker_reasons": ["no_monitor_summaries_found"],
    }


def run_ops(config: OpsConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.ops_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    entries = find_monitor_summaries(config.input_roots)
    latest = latest_entry(entries)
    ledger_entries = [ledger_entry_for(entry) for entry in entries]
    summary = base_summary(config=config, output_root=output_root)
    if latest is not None:
        latest_payload = latest.payload
        recommendation = recommendation_for(
            latest_payload,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
        )
        v3_7_allowed = recommendation == RECOMMEND_PLAN_V3_7_ONLY_IF_READY
        summary.update(
            {
                "status": str(latest_payload.get("status") or ""),
                "monitor_run_count": len(entries),
                "latest_monitor_run_id": str(latest_payload.get("monitor_run_id") or ""),
                "latest_status": str(latest_payload.get("status") or ""),
                "latest_next_check_after": str(latest_payload.get("next_check_after") or ""),
                "checked_capture_run_count": int(
                    latest_payload.get("checked_capture_run_count") or 0
                ),
                "not_matured_count": int(latest_payload.get("not_matured_count") or 0),
                "matured_candidate_count": int(
                    latest_payload.get("matured_candidate_count") or 0
                ),
                "blocked_data_count": int(latest_payload.get("blocked_data_count") or 0),
                "resolved_count": int(latest_payload.get("resolved_count") or 0),
                "scored_count": int(latest_payload.get("scored_count") or 0),
                "readiness_status": str(latest_payload.get("readiness_status") or ""),
                "next_stage_planning_allowed": latest_payload.get(
                    "next_stage_planning_allowed",
                )
                is True,
                "next_action_recommendation": recommendation,
                "v3_7_verdict_allowed": v3_7_allowed,
                "v3_7_verdict_executed": False,
                "ledger_entry_count": len(ledger_entries),
                "ledger_entries": ledger_entries,
                "latest_summary_path": str(latest.path),
                "latest_summary_sha256": latest.sha256,
                "provider_or_backend_called": False,
                "codex_cli_called": False,
                "formal_lite_entered": False,
                "blocker_reasons": list(latest_payload.get("blocker_reasons") or []),
            }
        )
    summary.update(
        {
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
                "+00:00",
                "Z",
            ),
            "ops_script_version": OPS_SCRIPT_VERSION,
        }
    )
    manifest = manifest_for(config=config, output_root=output_root, summary=summary)
    ledger = {
        "schema": LEDGER_SCHEMA,
        "ops_run_id": config.ops_run_id,
        "monitor_run_count": len(entries),
        "latest_monitor_run_id": summary["latest_monitor_run_id"],
        "entries": ledger_entries,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(
    *,
    config: OpsConfig,
    output_root: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "ops_run_id": config.ops_run_id,
        "run_root": str(output_root),
        "input_roots": [str(root) for root in config.input_roots],
        "status": summary["status"],
        "latest_monitor_run_id": summary["latest_monitor_run_id"],
        "monitor_run_count": summary["monitor_run_count"],
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "engineering/local monitor operations only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", action="append", type=Path, required=True)
    parser.add_argument("--ops-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> OpsConfig:
    return OpsConfig(
        input_roots=tuple(args.input_root),
        ops_run_id=str(args.ops_run_id),
        output_dir=args.output_dir,
        as_of_timestamp_utc=parse_as_of_timestamp(str(args.as_of_timestamp_utc or "")),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_ops(config_from_args(parse_args(argv)))
    return 1 if str(summary.get("status")) == STATUS_BLOCKED_RUN_ID_EXISTS else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
