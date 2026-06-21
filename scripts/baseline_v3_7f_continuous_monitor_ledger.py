#!/usr/bin/env python3
"""GOTRA v3.7F continuous monitor ledger / index validator."""

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


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7f.continuous_monitor_ledger_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7f.continuous_monitor_ledger_manifest.v1"
LEDGER_SCHEMA_VERSION = "gotra.baseline_v3_7f.continuous_monitor_ledger.v1"
RUN_ID_PREFIX = "baseline_v3_7f_continuous_monitor_ledger_"
SCRIPT_VERSION = "v3.7f-20260622"
EVIDENCE_LAYER = "engineering_internal_continuous_monitor_ledger"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_7_CONTINUOUS_MONITOR_LEDGER_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_RUN_ID_EXISTS = "CONTINUOUS_MONITOR_LEDGER_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}

REQUIRED_STRING_FIELDS = (
    "ledger_schema_version",
    "generated_at",
    "main_commit",
    "main_ci_status",
    "latest_merged_pr_head",
    "latest_merged_pr_commit",
    "actual_30d_readiness_status",
    "actual_30d_next_check_after",
    "short_horizon_status",
    "v3_7a_fixture_harness_status",
    "v3_7b_report_schema_status",
    "v3_7c_stat_preflight_status",
    "v3_7d_short_horizon_recheck_status",
    "v3_7e_dashboard_status",
    "evidence_layer",
    "direct_llm_interpretation",
)
REQUIRED_INT_FIELDS = (
    "open_pr_count",
    "latest_merged_pr",
    "actual_30d_checked_capture_run_count",
    "actual_30d_capture_artifact_count",
    "actual_30d_matured_candidate_count",
    "actual_30d_resolved_count",
    "actual_30d_scored_count",
)
REQUIRED_LIST_FIELDS = (
    "actual_30d_blocker_reasons",
    "known_blockers",
    "next_safe_actions",
)
FALSE_FLAGS = (
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
)
STATUS_FIELDS = (
    "short_horizon_status",
    "v3_7a_fixture_harness_status",
    "v3_7b_report_schema_status",
    "v3_7c_stat_preflight_status",
    "v3_7d_short_horizon_recheck_status",
    "v3_7e_dashboard_status",
)
TEXT_SCAN_KEYS = {
    "actual_30d_blocker_reasons",
    "can_say",
    "cannot_say",
    "claim",
    "claims",
    "conclusion",
    "known_blockers",
    "narrative",
    "next_safe_actions",
    "non_claims",
    "notes",
    "rationale",
    "reasoning",
    "statement",
    "summary",
    "title",
    "verdict",
    "winner",
}
PATH_KEYS = {
    "path",
    "paths",
    "source_path",
    "source_paths",
    "source_artifact_path",
    "source_artifact_paths",
    "source_documents",
    "source_document_path",
    "source_summaries",
    "source_summary_path",
    "source_summary_paths",
    "summary_path",
    "manifest_path",
    "raw_artifact_path",
    "transcript_path",
}


@dataclass(frozen=True)
class LedgerConfig:
    ledger_run_id: str
    output_dir: Path
    ledger_fixture: Path
    allow_overwrite: bool = False


class LedgerError(Exception):
    def __init__(self, status: str, rule_id: str, reason: str, path: str = "") -> None:
        super().__init__(reason)
        self.status = status
        self.rule_id = rule_id
        self.reason = reason
        self.path = path


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"ledger_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("ledger_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    return claim_scan.normalize_scan_path(path)


def blocker(path: Path | str, rule_id: str, reason: str) -> dict[str, Any]:
    return {"path": normalize_path(path), "rule_id": rule_id, "reason": reason}


def load_json_object(path: Path) -> dict[str, Any]:
    if claim_scan.forbidden_path(normalize_path(path)):
        raise LedgerError(STATUS_BLOCKED_ARTIFACT, "forbidden_ledger_fixture_path", "ledger fixture path is forbidden", str(path))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LedgerError(STATUS_BLOCKED_SCHEMA, "ledger_fixture_read_error", str(exc), str(path)) from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(STATUS_BLOCKED_SCHEMA, "ledger_fixture_json_decode_error", str(exc), str(path)) from exc
    if not isinstance(payload, dict):
        raise LedgerError(STATUS_BLOCKED_SCHEMA, "ledger_fixture_root_not_object", "ledger fixture must be a JSON object", str(path))
    return payload


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def extract_entries(payload: dict[str, Any], *, path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if "ledger_entries" in payload:
        raw_entries = payload.get("ledger_entries")
        if not isinstance(raw_entries, list):
            return [], [blocker(path, "ledger_entries_not_list", "ledger_entries must be a list")], -1
        if not raw_entries:
            return [], [blocker(path, "ledger_entries_empty", "ledger_entries must not be empty")], -1
        entries: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        for index, entry in enumerate(raw_entries):
            if not isinstance(entry, dict):
                blockers.append(blocker(path, "ledger_entry_not_object", f"ledger_entries[{index}] must be an object"))
                continue
            entries.append(dict(entry))
        selected_index = select_latest_entry_index(entries)
        return entries, blockers, selected_index
    if isinstance(payload.get("ledger"), dict):
        return [dict(payload["ledger"])], [], 0
    return [dict(payload)], [], 0


def select_latest_entry_index(entries: list[dict[str, Any]]) -> int:
    if not entries:
        return -1
    candidates: list[tuple[tuple[str, str, str, int], int]] = []
    for index, entry in enumerate(entries):
        candidates.append(
            (
                (
                    str(entry.get("generated_at", "")),
                    str(entry.get("main_commit", "")),
                    str(entry.get("latest_merged_pr_commit", "")),
                    -index,
                ),
                index,
            )
        )
    return max(candidates, key=lambda item: item[0])[1]


def recursive_sources(value: Any, *, path: str, key_hint: str = "") -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    if isinstance(value, str):
        if key_hint in TEXT_SCAN_KEYS or not key_hint:
            sources.append(claim_scan.ScanSource(path=path, text=value, origin="v3_7f_ledger"))
    elif isinstance(value, dict):
        for key, item in sorted(value.items()):
            sources.extend(recursive_sources(item, path=f"{path}.{key}", key_hint=key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            sources.extend(recursive_sources(item, path=f"{path}[{index}]", key_hint=key_hint))
    return sources


def recursive_paths(value: Any, *, key_hint: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, str) and key_hint in PATH_KEYS:
        paths.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(recursive_paths(item, key_hint=key))
    elif isinstance(value, list):
        for item in value:
            paths.extend(recursive_paths(item, key_hint=key_hint))
    return paths


def claim_blockers(payload: dict[str, Any], *, path: Path) -> list[dict[str, Any]]:
    scan = claim_scan.scan_sources(recursive_sources(payload, path=normalize_path(path)))
    return (
        scan["overclaim"]
        + scan["direct_llm"]
        + scan["maturity_gate"]
        + scan["short_horizon_as_30d"]
    )


def path_blockers(payload: dict[str, Any], *, path: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if claim_scan.forbidden_path(normalize_path(path)):
        blockers.append(blocker(path, "forbidden_ledger_fixture_path", "ledger fixture path is forbidden"))
    for candidate in recursive_paths(payload):
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocker(candidate, "forbidden_ledger_artifact_path", "ledger references a forbidden artifact path"))
    return blockers


def list_value(entry: dict[str, Any], key: str, *, path: Path) -> list[Any] | None:
    value = entry.get(key)
    if not isinstance(value, list):
        return None
    return value


def validate_selected_entry(entry: dict[str, Any], *, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    schema_blockers: list[dict[str, Any]] = []
    for key in REQUIRED_STRING_FIELDS:
        if not is_non_empty_string(entry.get(key)):
            schema_blockers.append(blocker(path, f"missing_{key}", f"{key} is required"))
    for key in REQUIRED_INT_FIELDS:
        value = int_value(entry.get(key))
        if value is None or value < 0:
            schema_blockers.append(blocker(path, f"{key}_not_non_negative_int", f"{key} must be a non-negative integer"))
    for key in REQUIRED_LIST_FIELDS:
        if list_value(entry, key, path=path) is None:
            schema_blockers.append(blocker(path, f"{key}_not_list", f"{key} must be a list"))

    source_documents = entry.get("source_documents")
    source_summaries = entry.get("source_summaries")
    if not isinstance(source_documents, list) and not isinstance(source_summaries, list):
        schema_blockers.append(
            blocker(
                path,
                "missing_source_documents_or_summaries",
                "ledger must include source_documents or source_summaries",
            )
        )
    for key in ("source_documents", "source_summaries"):
        if key in entry and not all(is_non_empty_string(item) for item in entry.get(key, [])):
            schema_blockers.append(blocker(path, f"{key}_invalid", f"{key} entries must be non-empty strings"))

    for flag in FALSE_FLAGS:
        if entry.get(flag) is not False:
            schema_blockers.append(blocker(path, f"{flag}_not_false", f"{flag} must be false"))
    if entry.get("ledger_schema_version") != LEDGER_SCHEMA_VERSION:
        schema_blockers.append(blocker(path, "ledger_schema_version_mismatch", f"ledger_schema_version must be {LEDGER_SCHEMA_VERSION}"))
    if entry.get("evidence_layer") != EVIDENCE_LAYER:
        schema_blockers.append(blocker(path, "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if entry.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        schema_blockers.append(
            blocker(path, "direct_llm_interpretation_mismatch", "direct_llm_interpretation must be direct_llm_parametric_memory_control")
        )
    if entry.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        schema_blockers.append(
            blocker(path, "actual_30d_readiness_status_not_data_not_matured", "actual 30D readiness must remain DATA_NOT_MATURED")
        )
    if entry.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        schema_blockers.append(blocker(path, "actual_30d_next_check_after_mismatch", "actual 30D next_check_after must match the maturity gate"))

    if schema_blockers:
        return {}, schema_blockers

    normalized = {key: entry[key] for key in REQUIRED_STRING_FIELDS}
    normalized.update({key: int_value(entry[key]) or 0 for key in REQUIRED_INT_FIELDS})
    normalized.update({key: list(entry[key]) for key in REQUIRED_LIST_FIELDS})
    for flag in FALSE_FLAGS:
        normalized[flag] = False
    for key in ("source_documents", "source_summaries"):
        normalized[key] = list(entry.get(key, [])) if isinstance(entry.get(key), list) else []
    return normalized, []


def choose_status(*, artifact_blockers: list[dict[str, Any]], schema_blockers: list[dict[str, Any]], overclaim_blockers: list[dict[str, Any]]) -> str:
    if artifact_blockers:
        return STATUS_BLOCKED_ARTIFACT
    if schema_blockers:
        return STATUS_BLOCKED_SCHEMA
    if overclaim_blockers:
        return STATUS_BLOCKED_OVERCLAIM
    return STATUS_READY


def base_summary(*, config: LedgerConfig, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "ledger_run_id": config.ledger_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "ledger_status": status,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "generated_at": "",
        "selected_ledger_entry_index": -1,
        "ledger_entry_count": 0,
        "main_commit": "",
        "main_ci_status": "",
        "open_pr_count": 0,
        "latest_merged_pr": 0,
        "latest_merged_pr_head": "",
        "latest_merged_pr_commit": "",
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "actual_30d_checked_capture_run_count": 0,
        "actual_30d_capture_artifact_count": 0,
        "actual_30d_matured_candidate_count": 0,
        "actual_30d_resolved_count": 0,
        "actual_30d_scored_count": 0,
        "actual_30d_blocker_reasons": [],
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "short_horizon_status": "",
        "v3_7a_fixture_harness_status": "",
        "v3_7b_report_schema_status": "",
        "v3_7c_stat_preflight_status": "",
        "v3_7d_short_horizon_recheck_status": "",
        "v3_7e_dashboard_status": "",
        "known_blockers": [],
        "next_safe_actions": [],
        "source_documents": [],
        "source_summaries": [],
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "schema_boundary_status": "clean",
        "artifact_blocker_count": 0,
        "schema_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "blocker_reasons": [],
        "blocked_items": [],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
    }


def build_summary(config: LedgerConfig) -> dict[str, Any]:
    validate_run_id(config.ledger_run_id)
    run_root = config.output_dir / config.ledger_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config=config, run_root=run_root, status=STATUS_BLOCKED_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["schema_blocker_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    try:
        payload = load_json_object(config.ledger_fixture)
        artifacts = path_blockers(payload, path=config.ledger_fixture)
        entries, entry_schema_blockers, selected_index = extract_entries(payload, path=config.ledger_fixture)
        selected_entry = entries[selected_index] if 0 <= selected_index < len(entries) else {}
        ledger, selected_schema_blockers = validate_selected_entry(selected_entry, path=config.ledger_fixture) if selected_entry else ({}, [])
        schemas = entry_schema_blockers + selected_schema_blockers
        if not selected_entry and not entry_schema_blockers:
            schemas.append(blocker(config.ledger_fixture, "missing_selected_ledger_entry", "no ledger entry was available for selection"))
        overclaims = claim_blockers(payload, path=config.ledger_fixture) if not artifacts else []
        status = choose_status(artifact_blockers=artifacts, schema_blockers=schemas, overclaim_blockers=overclaims)
    except LedgerError as exc:
        artifacts = [blocker(exc.path or config.ledger_fixture, exc.rule_id, exc.reason)] if exc.status == STATUS_BLOCKED_ARTIFACT else []
        schemas = [blocker(exc.path or config.ledger_fixture, exc.rule_id, exc.reason)] if exc.status == STATUS_BLOCKED_SCHEMA else []
        overclaims = [blocker(exc.path or config.ledger_fixture, exc.rule_id, exc.reason)] if exc.status == STATUS_BLOCKED_OVERCLAIM else []
        entries = []
        selected_index = -1
        ledger = {}
        status = exc.status

    summary = base_summary(config=config, run_root=run_root, status=status)
    summary["ledger_entry_count"] = len(entries)
    summary["selected_ledger_entry_index"] = selected_index
    if ledger:
        summary.update(ledger)
        summary["ledger_entry_count"] = len(entries)
        summary["selected_ledger_entry_index"] = selected_index
    blocked_items = artifacts + schemas + overclaims
    summary.update(
        {
            "ledger_status": status,
            "artifact_boundary_status": "blocked" if artifacts else "clean",
            "claim_boundary_status": "blocked" if overclaims else "clean",
            "schema_boundary_status": "blocked" if schemas else "clean",
            "artifact_blocker_count": len(artifacts),
            "schema_blocker_count": len(schemas),
            "overclaim_blocker_count": len(overclaims),
            "blocker_reasons": [str(item["rule_id"]) for item in blocked_items],
            "blocked_items": blocked_items[:50],
        }
    )
    write_outputs(config, summary, run_root=run_root)
    return summary


def write_outputs(config: LedgerConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "ledger_run_id": config.ledger_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "ledger_fixture": str(config.ledger_fixture),
        "ledger_status": summary.get("ledger_status"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-run-id", default=default_run_id())
    parser.add_argument("--ledger-fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7f_continuous_monitor_ledger/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> LedgerConfig:
    return LedgerConfig(
        ledger_run_id=str(args.ledger_run_id),
        output_dir=args.output_dir,
        ledger_fixture=args.ledger_fixture,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should return a non-zero failure with redacted stderr.
        print(f"continuous monitor ledger failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("ledger_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
