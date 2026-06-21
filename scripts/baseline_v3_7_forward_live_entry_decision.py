#!/usr/bin/env python3
"""GOTRA v3.7 forward-live entry decision / readiness-blocked closeout."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_7.forward_live_entry_decision_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7.forward_live_entry_decision_manifest.v1"
ENTRY_RUN_ID_PREFIX = "baseline_v3_7_forward_live_entry_decision_"
SCRIPT_VERSION = "v3.7-entry-20260621"

STATUS_READY_FOR_VERDICT_WORKFLOW = "V3_7_READY_FOR_FORWARD_LIVE_VERDICT_WORKFLOW"
STATUS_BLOCKED_BY_ACTUAL_READINESS = "V3_7_VERDICT_BLOCKED_BY_ACTUAL_READINESS"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_RUN_ID_EXISTS = "V3_7_ENTRY_BLOCKED_RUN_ID_EXISTS"

ACTION_EXECUTE_SEPARATE_VERDICT_STAGE = "PLAN_SEPARATE_V3_7_FORWARD_LIVE_VERDICT_STAGE"
ACTION_PREPARE_HARNESS_AND_RECHECK = "PREPARE_HARNESS_AND_RECHECK_ACTUAL_READINESS"
ACTION_FIX_PROVENANCE = "FIX_ACTUAL_READINESS_PROVENANCE"
ACTION_FIX_RUNTIME_BOUNDARY = "FIX_RUNTIME_BOUNDARY"

NON_BLOCKING_BLOCKED_TASKS = (
    "v3_7_verdict_harness_fixture_dry_run",
    "v3_7_report_schema_and_provenance_validator",
    "dashboard_hardening_without_30d_verdict",
    "short_horizon_outcome_recheck_without_30d_substitution",
)


@dataclass(frozen=True)
class EntryDecisionConfig:
    readiness_summary_path: Path
    entry_run_id: str
    output_dir: Path
    as_of_timestamp_utc: datetime
    readiness_summary_sha256: str = ""
    allow_overwrite: bool = False


def parse_as_of_timestamp(value: str | None) -> datetime:
    return monitor_v36s.parse_as_of_timestamp(value)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(ENTRY_RUN_ID_PREFIX):
        raise ValueError(f"entry_run_id must start with {ENTRY_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("entry_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: EntryDecisionConfig) -> None:
    validate_run_id(config.entry_run_id)
    if not config.readiness_summary_path.exists():
        raise FileNotFoundError(
            f"readiness summary path not found: {config.readiness_summary_path}"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def count_from(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def actual_readiness_status(payload: dict[str, Any]) -> str:
    readiness_status = str(payload.get("readiness_status") or "")
    monitor_status = str(payload.get("status") or "")
    if readiness_status and readiness_status != monitor_v36s.READINESS_NOT_RUN:
        return readiness_status
    return monitor_status


def runtime_boundary_reasons(payload: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if payload.get("provider_or_backend_called") is True:
        reasons.append("provider_or_backend_called")
    if payload.get("codex_cli_called") is True:
        reasons.append("codex_cli_called")
    if payload.get("formal_lite_entered") is True:
        reasons.append("formal_lite_entered")
    return reasons


def provenance_reasons(
    *,
    payload: dict[str, Any] | None,
    source_sha256: str,
    expected_sha256: str,
) -> list[str]:
    reasons: list[str] = []
    if payload is None:
        return ["source_summary_unreadable"]
    if expected_sha256 and source_sha256 != expected_sha256:
        reasons.append("source_summary_sha256_mismatch")
    if payload.get("schema") != monitor_v36s.SUMMARY_SCHEMA:
        reasons.append("source_summary_schema_mismatch")
    if not str(payload.get("monitor_run_id") or ""):
        reasons.append("source_monitor_run_id_missing")
    if not str(payload.get("status") or ""):
        reasons.append("source_status_missing")
    if payload.get("v3_7_verdict_executed") is True:
        reasons.append("source_already_executed_v3_7_verdict")
    return reasons


def source_is_current_ready(payload: dict[str, Any]) -> bool:
    return (
        str(payload.get("status") or "") == monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE
        and str(payload.get("readiness_status") or "") == readiness_v36.STATUS_READY
        and payload.get("next_stage_planning_allowed") is True
        and payload.get("resolver_path_eligible") is True
        and payload.get("v3_7_verdict_executed") is False
    )


def base_summary(
    *,
    config: EntryDecisionConfig,
    output_root: Path,
    source_sha256: str = "",
) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "entry_run_id": config.entry_run_id,
        "run_root": str(output_root),
        "status": STATUS_BLOCKED_PROVENANCE,
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "evidence_layer": "engineering/local v3.7 entry decision only",
        "source_summary_path": str(config.readiness_summary_path),
        "source_summary_sha256": source_sha256,
        "source_summary_sha256_expected": config.readiness_summary_sha256,
        "readiness_status": STATUS_BLOCKED_PROVENANCE,
        "source_monitor_status": "",
        "source_readiness_gate_status": "",
        "checked_capture_run_count": 0,
        "matured_candidate_count": 0,
        "resolved_count": 0,
        "scored_count": 0,
        "paired_clean_count": 0,
        "full_gotra_available_count": 0,
        "deterministic_reference_available_count": 0,
        "blocker_reasons": [],
        "next_check_after": "",
        "next_action": ACTION_FIX_PROVENANCE,
        "non_blocking_next_tasks": [],
        "v3_7_actual_verdict_executable": False,
        "v3_7_verdict_executed": False,
        "v3_7_verdict_harness_prep_allowed": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a 30D forward-live verdict",
            "no full_gotra/deterministic/ksana winner verdict",
        ],
    }


def blocked_run_id_summary(config: EntryDecisionConfig, output_root: Path) -> dict[str, Any]:
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "readiness_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_entry_decision(config: EntryDecisionConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.entry_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    source_sha256 = sha256_file(config.readiness_summary_path)
    source_payload: dict[str, Any] | None
    try:
        source_payload = load_json(config.readiness_summary_path)
    except Exception:  # noqa: BLE001 - converted to provenance blocker below.
        source_payload = None

    summary = base_summary(
        config=config,
        output_root=output_root,
        source_sha256=source_sha256,
    )
    provenance_blockers = provenance_reasons(
        payload=source_payload,
        source_sha256=source_sha256,
        expected_sha256=config.readiness_summary_sha256,
    )
    runtime_blockers = runtime_boundary_reasons(source_payload or {})

    if source_payload is not None:
        source_status = str(source_payload.get("status") or "")
        source_readiness = str(source_payload.get("readiness_status") or "")
        summary.update(
            {
                "readiness_status": actual_readiness_status(source_payload),
                "source_monitor_status": source_status,
                "source_readiness_gate_status": source_readiness,
                "checked_capture_run_count": count_from(
                    source_payload,
                    "checked_capture_run_count",
                ),
                "matured_candidate_count": count_from(
                    source_payload,
                    "matured_candidate_count",
                ),
                "resolved_count": count_from(source_payload, "resolved_count"),
                "scored_count": count_from(source_payload, "scored_count"),
                "paired_clean_count": count_from(source_payload, "paired_clean_count"),
                "full_gotra_available_count": count_from(
                    source_payload,
                    "full_gotra_available_count",
                ),
                "deterministic_reference_available_count": count_from(
                    source_payload,
                    "deterministic_reference_available_count",
                ),
                "next_check_after": str(source_payload.get("next_check_after") or ""),
                "provider_or_backend_called": source_payload.get(
                    "provider_or_backend_called"
                )
                is True,
                "codex_cli_called": source_payload.get("codex_cli_called") is True,
                "formal_lite_entered": source_payload.get("formal_lite_entered") is True,
            }
        )

    if provenance_blockers:
        summary.update(
            {
                "status": STATUS_BLOCKED_PROVENANCE,
                "readiness_status": (
                    summary["readiness_status"]
                    if summary["readiness_status"] != STATUS_BLOCKED_PROVENANCE
                    else STATUS_BLOCKED_PROVENANCE
                ),
                "blocker_reasons": sorted(provenance_blockers),
                "next_action": ACTION_FIX_PROVENANCE,
            }
        )
    elif runtime_blockers:
        summary.update(
            {
                "status": STATUS_BLOCKED_RUNTIME_BOUNDARY,
                "blocker_reasons": sorted(runtime_blockers),
                "next_action": ACTION_FIX_RUNTIME_BOUNDARY,
            }
        )
    elif source_payload is not None and source_is_current_ready(source_payload):
        summary.update(
            {
                "status": STATUS_READY_FOR_VERDICT_WORKFLOW,
                "readiness_status": readiness_v36.STATUS_READY,
                "blocker_reasons": [],
                "next_action": ACTION_EXECUTE_SEPARATE_VERDICT_STAGE,
                "v3_7_actual_verdict_executable": True,
                "v3_7_verdict_executed": False,
                "v3_7_verdict_harness_prep_allowed": True,
            }
        )
    else:
        source_blockers = list((source_payload or {}).get("blocker_reasons") or [])
        if not source_blockers:
            source_blockers = ["actual_readiness_not_ready"]
        summary.update(
            {
                "status": STATUS_BLOCKED_BY_ACTUAL_READINESS,
                "blocker_reasons": sorted(set(str(reason) for reason in source_blockers)),
                "next_action": ACTION_PREPARE_HARNESS_AND_RECHECK,
                "non_blocking_next_tasks": list(NON_BLOCKING_BLOCKED_TASKS),
                "v3_7_actual_verdict_executable": False,
                "v3_7_verdict_executed": False,
                "v3_7_verdict_harness_prep_allowed": True,
            }
        )

    summary.update(
        {
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
                "+00:00",
                "Z",
            ),
            "entry_script_version": SCRIPT_VERSION,
        }
    )
    summary_path = output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = manifest_for(config=config, output_root=output_root, summary=summary)
    manifest["summary_sha256"] = sha256_file(summary_path)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(
    *,
    config: EntryDecisionConfig,
    output_root: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "entry_run_id": config.entry_run_id,
        "run_root": str(output_root),
        "status": summary["status"],
        "readiness_status": summary["readiness_status"],
        "source_summary_path": summary["source_summary_path"],
        "source_summary_sha256": summary["source_summary_sha256"],
        "v3_7_actual_verdict_executable": summary["v3_7_actual_verdict_executable"],
        "v3_7_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "engineering/local v3.7 entry decision only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-summary-path", type=Path, required=True)
    parser.add_argument("--readiness-summary-sha256", default="")
    parser.add_argument("--entry-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> EntryDecisionConfig:
    return EntryDecisionConfig(
        readiness_summary_path=args.readiness_summary_path,
        readiness_summary_sha256=str(args.readiness_summary_sha256 or ""),
        entry_run_id=str(args.entry_run_id),
        output_dir=args.output_dir,
        as_of_timestamp_utc=parse_as_of_timestamp(str(args.as_of_timestamp_utc or "")),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_entry_decision(config_from_args(parse_args(argv)))
    hard_blocked = {
        STATUS_BLOCKED_PROVENANCE,
        STATUS_BLOCKED_RUNTIME_BOUNDARY,
        STATUS_BLOCKED_RUN_ID_EXISTS,
    }
    return 1 if str(summary.get("status")) in hard_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
