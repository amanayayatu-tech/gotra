#!/usr/bin/env python3
"""GOTRA v3.7E internal evidence dashboard hardening."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_7e.evidence_dashboard_hardening_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7e.evidence_dashboard_hardening_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_7e_evidence_dashboard_hardening_"
SCRIPT_VERSION = "v3.7e-20260622"
EVIDENCE_LAYER = "engineering_internal_evidence_dashboard"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_7_EVIDENCE_DASHBOARD_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_RUN_ID_EXISTS = "EVIDENCE_DASHBOARD_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}

REQUIRED_SECTIONS = ("main", "readiness", "provenance", "sections")
REQUIRED_STAGE_FIELDS = (
    "short_horizon_status",
    "v3_7a_fixture_harness_status",
    "v3_7b_report_schema_status",
    "v3_7c_stat_preflight_status",
    "v3_7d_short_horizon_recheck_status",
    "v3_7k_ksana_packet_v2_status",
)
REQUIRED_SECTION_LISTS = ("known_blockers", "can_say", "cannot_say", "next_safe_actions")
FALSE_RUNTIME_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
TEXT_SCAN_KEYS = {
    "title",
    "summary",
    "claim",
    "claims",
    "conclusion",
    "notes",
    "narrative",
    "rationale",
    "reasoning",
    "statement",
    "verdict",
    "winner",
    "known_blockers",
    "can_say",
    "cannot_say",
    "next_safe_actions",
    "non_claims",
}
PATH_KEYS = {
    "path",
    "paths",
    "source_path",
    "source_paths",
    "source_artifact_path",
    "source_artifact_paths",
    "summary_path",
    "manifest_path",
    "source_documents",
    "source_document_path",
    "raw_artifact_path",
    "transcript_path",
}


@dataclass(frozen=True)
class DashboardConfig:
    dashboard_run_id: str
    output_dir: Path
    dashboard_fixture: Path
    allow_overwrite: bool = False


class DashboardError(Exception):
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
        raise ValueError(f"dashboard_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("dashboard_run_id may contain only letters, numbers, '_' and '-'")


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
        raise DashboardError(STATUS_BLOCKED_ARTIFACT, "forbidden_dashboard_fixture_path", "dashboard fixture path is forbidden", str(path))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DashboardError(STATUS_BLOCKED_SCHEMA, "dashboard_fixture_read_error", str(exc), str(path)) from exc
    except json.JSONDecodeError as exc:
        raise DashboardError(STATUS_BLOCKED_SCHEMA, "dashboard_fixture_json_decode_error", str(exc), str(path)) from exc
    if not isinstance(payload, dict):
        raise DashboardError(STATUS_BLOCKED_SCHEMA, "dashboard_fixture_root_not_object", "dashboard fixture must be a JSON object", str(path))
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


def bool_false(value: Any) -> bool:
    return isinstance(value, bool) and value is False


def section(payload: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    raw = payload.get(key)
    if not isinstance(raw, dict):
        raise DashboardError(STATUS_BLOCKED_SCHEMA, f"missing_{key}_section", f"dashboard fixture missing object section: {key}", str(path))
    return raw


def recursive_sources(value: Any, *, path: str, key_hint: str = "") -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    if isinstance(value, str):
        if key_hint in TEXT_SCAN_KEYS or not key_hint:
            sources.append(claim_scan.ScanSource(path=path, text=value, origin="v3_7e_dashboard"))
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
        blockers.append(blocker(path, "forbidden_dashboard_fixture_path", "dashboard fixture path is forbidden"))
    for candidate in recursive_paths(payload):
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocker(candidate, "forbidden_dashboard_artifact_path", "dashboard references a forbidden artifact path"))
    return blockers


def require_list(section_payload: dict[str, Any], key: str, *, path: Path) -> list[Any]:
    value = section_payload.get(key)
    if not isinstance(value, list):
        raise DashboardError(STATUS_BLOCKED_SCHEMA, f"missing_{key}", f"dashboard section field must be a list: {key}", str(path))
    return value


def validate_fixture(payload: dict[str, Any], *, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for required in REQUIRED_SECTIONS:
        section(payload, required, path)
    main = section(payload, "main", path)
    readiness = section(payload, "readiness", path)
    provenance = section(payload, "provenance", path)
    sections = section(payload, "sections", path)

    schema_blockers: list[dict[str, Any]] = []
    for key in ("main_commit", "main_ci_status"):
        if not is_non_empty_string(main.get(key)):
            schema_blockers.append(blocker(path, f"missing_main_{key}", f"main.{key} is required"))
    if int_value(main.get("open_pr_count")) is None:
        schema_blockers.append(blocker(path, "missing_open_pr_count", "main.open_pr_count must be a non-negative integer"))

    if readiness.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        schema_blockers.append(
            blocker(
                path,
                "actual_30d_readiness_status_not_data_not_matured",
                "actual 30D readiness must remain DATA_NOT_MATURED for this dashboard",
            )
        )
    if readiness.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        schema_blockers.append(
            blocker(path, "actual_30d_next_check_after_mismatch", "actual 30D next_check_after must match the maturity gate")
        )
    for flag in FALSE_RUNTIME_FLAGS:
        if readiness.get(flag, payload.get(flag)) is not False:
            schema_blockers.append(blocker(path, f"{flag}_not_false", f"{flag} must be false"))
    for flag in ("provider_or_backend_called", "codex_cli_new_call", "formal_lite_entered"):
        if payload.get(flag, readiness.get(flag, False)) is not False:
            schema_blockers.append(blocker(path, f"{flag}_not_false", f"{flag} must be false"))

    for field in REQUIRED_STAGE_FIELDS:
        if not is_non_empty_string(sections.get(field)):
            schema_blockers.append(blocker(path, f"missing_{field}", f"sections.{field} is required"))
    for field in REQUIRED_SECTION_LISTS:
        require_list(sections, field, path=path)
    if sections.get("evidence_layer", payload.get("evidence_layer")) != EVIDENCE_LAYER:
        schema_blockers.append(blocker(path, "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))

    if not isinstance(provenance.get("source_documents"), list) or not provenance["source_documents"]:
        schema_blockers.append(blocker(path, "missing_provenance_source_documents", "provenance.source_documents must be a non-empty list"))
    if not is_non_empty_string(provenance.get("builder_input_mode")):
        schema_blockers.append(blocker(path, "missing_provenance_builder_input_mode", "provenance.builder_input_mode is required"))
    if provenance.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        schema_blockers.append(
            blocker(
                path,
                "direct_llm_interpretation_mismatch",
                "provenance.direct_llm_interpretation must be direct_llm_parametric_memory_control",
            )
        )

    if schema_blockers:
        return {}, schema_blockers

    open_pr_count = int_value(main.get("open_pr_count")) or 0
    dashboard = {
        "main_commit": str(main["main_commit"]),
        "open_pr_count": open_pr_count,
        "main_ci_status": str(main["main_ci_status"]),
        "actual_30d_readiness_status": str(readiness["actual_30d_readiness_status"]),
        "actual_30d_next_check_after": str(readiness["actual_30d_next_check_after"]),
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "short_horizon_status": str(sections["short_horizon_status"]),
        "v3_7a_fixture_harness_status": str(sections["v3_7a_fixture_harness_status"]),
        "v3_7b_report_schema_status": str(sections["v3_7b_report_schema_status"]),
        "v3_7c_stat_preflight_status": str(sections["v3_7c_stat_preflight_status"]),
        "v3_7d_short_horizon_recheck_status": str(sections["v3_7d_short_horizon_recheck_status"]),
        "v3_7k_ksana_packet_v2_status": str(sections["v3_7k_ksana_packet_v2_status"]),
        "known_blockers": list(sections["known_blockers"]),
        "can_say": list(sections["can_say"]),
        "cannot_say": list(sections["cannot_say"]),
        "next_safe_actions": list(sections["next_safe_actions"]),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
    }
    return dashboard, []


def choose_status(*, artifact_blockers: list[dict[str, Any]], schema_blockers: list[dict[str, Any]], overclaim_blockers: list[dict[str, Any]]) -> str:
    if artifact_blockers:
        return STATUS_BLOCKED_ARTIFACT
    if schema_blockers:
        return STATUS_BLOCKED_SCHEMA
    if overclaim_blockers:
        return STATUS_BLOCKED_OVERCLAIM
    return STATUS_READY


def base_summary(*, config: DashboardConfig, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "dashboard_run_id": config.dashboard_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "dashboard_status": status,
        "main_commit": "",
        "open_pr_count": 0,
        "main_ci_status": "",
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "short_horizon_status": "",
        "v3_7a_fixture_harness_status": "",
        "v3_7b_report_schema_status": "",
        "v3_7c_stat_preflight_status": "",
        "v3_7d_short_horizon_recheck_status": "",
        "v3_7k_ksana_packet_v2_status": "",
        "known_blockers": [],
        "can_say": [],
        "cannot_say": [],
        "next_safe_actions": [],
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


def build_summary(config: DashboardConfig) -> dict[str, Any]:
    validate_run_id(config.dashboard_run_id)
    run_root = config.output_dir / config.dashboard_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config=config, run_root=run_root, status=STATUS_BLOCKED_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["schema_blocker_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    try:
        payload = load_json_object(config.dashboard_fixture)
        artifacts = path_blockers(payload, path=config.dashboard_fixture)
        dashboard, schemas = validate_fixture(payload, path=config.dashboard_fixture)
        overclaims = claim_blockers(payload, path=config.dashboard_fixture) if not artifacts else []
        status = choose_status(artifact_blockers=artifacts, schema_blockers=schemas, overclaim_blockers=overclaims)
    except DashboardError as exc:
        artifacts = [blocker(exc.path or config.dashboard_fixture, exc.rule_id, exc.reason)] if exc.status == STATUS_BLOCKED_ARTIFACT else []
        schemas = [blocker(exc.path or config.dashboard_fixture, exc.rule_id, exc.reason)] if exc.status == STATUS_BLOCKED_SCHEMA else []
        overclaims = [blocker(exc.path or config.dashboard_fixture, exc.rule_id, exc.reason)] if exc.status == STATUS_BLOCKED_OVERCLAIM else []
        dashboard = {}
        status = exc.status

    summary = base_summary(config=config, run_root=run_root, status=status)
    if dashboard:
        summary.update(dashboard)
    blocked_items = artifacts + schemas + overclaims
    summary.update(
        {
            "dashboard_status": status,
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


def write_outputs(config: DashboardConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "dashboard_run_id": config.dashboard_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "dashboard_fixture": str(config.dashboard_fixture),
        "dashboard_status": summary.get("dashboard_status"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard-run-id", default=default_run_id())
    parser.add_argument("--dashboard-fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7e_evidence_dashboard_hardening/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> DashboardConfig:
    return DashboardConfig(
        dashboard_run_id=str(args.dashboard_run_id),
        output_dir=args.output_dir,
        dashboard_fixture=args.dashboard_fixture,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should return a non-zero failure with redacted stderr.
        print(f"evidence dashboard hardening failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("dashboard_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
