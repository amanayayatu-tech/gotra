#!/usr/bin/env python3
"""GOTRA v3.7B verdict report schema / provenance validator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness_v36  # noqa: E402
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7b.verdict_report_schema_validator_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7b.verdict_report_schema_validator_manifest.v1"
TARGET_REPORT_SCHEMA = "gotra.baseline_v3_7.forward_live_verdict_report.v1"
RUN_ID_PREFIX = "baseline_v3_7b_verdict_report_schema_validator_"
SCRIPT_VERSION = "v3.7b-20260621"
EVIDENCE_LAYER = "engineering/local v3.7 verdict report schema validator"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_7_REPORT_SCHEMA_READY"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_FUTURE_DATA = "BLOCKED_FUTURE_DATA"
STATUS_BLOCKED_PAIRING = "BLOCKED_PAIRING"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"

BLOCKED_STATUSES = {
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_PROVENANCE,
    STATUS_BLOCKED_FUTURE_DATA,
    STATUS_BLOCKED_PAIRING,
    STATUS_BLOCKED_OVERCLAIM,
}

HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
CLAIM_TEXT_FIELDS = (
    "title",
    "summary",
    "claim",
    "claims",
    "conclusion",
    "narrative",
    "notes",
    "non_claims",
    "verdict",
    "verdict_claim",
    "winner",
    "winner_claim",
)
COUNT_FIELDS = (
    "matured_count",
    "scored_count",
    "paired_clean_count",
    "full_gotra_available_count",
    "deterministic_reference_available_count",
    "future_data_violation_count",
    "provenance_blocker_count",
    "pairing_blocker_count",
)


@dataclass(frozen=True)
class ValidatorConfig:
    validator_run_id: str
    output_dir: Path
    reports: tuple[Path, ...] = ()
    report_manifest: Path | None = None
    allow_overwrite: bool = False


@dataclass(frozen=True)
class ValidatedReport:
    path: str
    payload: dict[str, Any]


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"validator_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("validator_run_id may contain only letters, numbers, '_' and '-'")


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def blocker(path: Path | str, rule_id: str, reason: str) -> dict[str, Any]:
    return {
        "path": normalize_path(path),
        "rule_id": rule_id,
        "reason": reason,
    }


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def hash_is_valid(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value.strip()))


def path_exists_for_hash_check(path_value: Any) -> Path | None:
    if not is_non_empty_string(path_value):
        return None
    path = Path(str(path_value)).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if path.exists() and path.is_file():
        return path
    return None


def load_report_manifest(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        return [], [blocker(path, "malformed_manifest_root", "report manifest must be a JSON object")]
    raw = payload.get("reports", payload.get("artifacts", []))
    if not isinstance(raw, list):
        return [], [
            blocker(
                path,
                "malformed_manifest_reports",
                "report manifest reports/artifacts must be a list",
            )
        ]
    reports: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            blockers.append(
                blocker(
                    path,
                    "malformed_manifest_report_entry",
                    f"report manifest entry {index} must be an object",
                )
            )
            continue
        if "payload" in entry:
            payload_entry = entry.get("payload")
            if not isinstance(payload_entry, dict):
                blockers.append(
                    blocker(
                        path,
                        "malformed_manifest_payload",
                        f"report manifest entry {index} payload must be an object",
                    )
                )
                continue
            report = dict(payload_entry)
            if entry.get("path") and not report.get("report_path"):
                report["report_path"] = str(entry["path"])
            reports.append(report)
            continue
        if entry.get("path") and set(entry).issubset({"path", "filename"}):
            report_path = Path(str(entry.get("path") or entry.get("filename") or ""))
            if not report_path.is_absolute():
                report_path = path.parent / report_path
            loaded, path_blockers = load_report_file(report_path)
            reports.extend(loaded)
            blockers.extend(path_blockers)
            continue
        reports.append(dict(entry))
    return reports, blockers


def load_report_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized = normalize_path(path)
    if claim_scan.forbidden_path(normalized):
        return [], [blocker(normalized, "forbidden_report_path", "report path is forbidden")]
    payload = load_json(path)
    if isinstance(payload, list):
        reports: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        for index, entry in enumerate(payload):
            if isinstance(entry, dict):
                report = dict(entry)
                report.setdefault("report_path", normalized)
                reports.append(report)
            else:
                blockers.append(
                    blocker(normalized, "malformed_report_row", f"report row {index} must be an object")
                )
        return reports, blockers
    if isinstance(payload, dict) and isinstance(payload.get("reports"), list):
        reports = []
        blockers = []
        for index, entry in enumerate(payload["reports"]):
            if isinstance(entry, dict):
                report = dict(entry)
                report.setdefault("report_path", normalized)
                reports.append(report)
            else:
                blockers.append(
                    blocker(normalized, "malformed_report_row", f"report row {index} must be an object")
                )
        return reports, blockers
    if isinstance(payload, dict):
        report = dict(payload)
        report.setdefault("report_path", normalized)
        return [report], []
    return [], [blocker(normalized, "malformed_report_root", "report JSON must be an object or list")]


def collect_report_payloads(
    config: ValidatorConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reports: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if config.report_manifest:
        manifest_path = normalize_path(config.report_manifest)
        if claim_scan.forbidden_path(manifest_path):
            blockers.append(blocker(manifest_path, "forbidden_manifest_path", "manifest path is forbidden"))
        else:
            manifest_reports, manifest_blockers = load_report_manifest(config.report_manifest)
            reports.extend(manifest_reports)
            blockers.extend(manifest_blockers)
    for path in config.reports:
        loaded, path_blockers = load_report_file(path)
        reports.extend(loaded)
        blockers.extend(path_blockers)
    return reports, blockers


def source_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result = []
    for item in value:
        if not is_non_empty_string(item):
            return None
        result.append(str(item))
    return result


def source_path_blockers(report: dict[str, Any], path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    paths = source_list(report.get("source_artifact_paths"))
    if paths is None:
        return [blocker(path, "invalid_source_artifact_paths", "source_artifact_paths must be a list of strings")]
    if not paths:
        blockers.append(blocker(path, "missing_source_artifact_paths", "source_artifact_paths cannot be empty"))
    for item in paths:
        if claim_scan.forbidden_path(item):
            blockers.append(
                blocker(
                    item,
                    "forbidden_source_artifact_path",
                    "source artifact path is forbidden",
                )
            )
    return blockers


def claim_sources(path: str, report: dict[str, Any]) -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    for field in CLAIM_TEXT_FIELDS:
        if field not in report:
            continue
        value = report[field]
        if isinstance(value, str):
            text = value
        elif isinstance(value, list):
            text = "\n".join(str(item) for item in value if isinstance(item, str))
        elif isinstance(value, dict):
            text = "\n".join(str(item) for item in value.values() if isinstance(item, str))
        else:
            text = ""
        if text:
            sources.append(
                claim_scan.ScanSource(
                    path=f"{path}#{field}",
                    text=text,
                    origin="report_field",
                )
            )
    return sources


def winner_or_verdict_executed(report: dict[str, Any]) -> bool:
    if report.get("winner_emitted") is True:
        return True
    if report.get("actual_30d_verdict_executed") is True:
        return True
    for field in ("winner", "winner_claim", "verdict", "verdict_claim"):
        if field not in report:
            continue
        value = report[field]
        if value in (False, None, "", [], {}):
            continue
        if isinstance(value, str) and value.strip().lower() in {"none", "not_emitted", "not emitted"}:
            continue
        return True
    return False


def readiness_status_is_ready(payload: dict[str, Any]) -> bool:
    readiness_status = str(payload.get("readiness_status") or payload.get("status") or "")
    return readiness_status == readiness_v36.STATUS_READY


def verify_summary_hash(
    report: dict[str, Any],
    *,
    path: str,
    path_field: str,
    hash_field: str,
) -> tuple[bool, list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    hash_value = report.get(hash_field)
    path_value = report.get(path_field)
    if not hash_is_valid(hash_value):
        blockers.append(blocker(path, f"missing_or_invalid_{hash_field}", f"{hash_field} must be a 64-char sha256 hex string"))
        return False, blockers
    local_path = path_exists_for_hash_check(path_value)
    if local_path is None:
        return True, blockers
    actual = sha256_file(local_path)
    if actual != str(hash_value).lower():
        blockers.append(
            blocker(
                str(path_value),
                f"{hash_field}_mismatch",
                f"{hash_field} does not match local file bytes",
            )
        )
        return False, blockers
    return True, blockers


def validate_counts(report: dict[str, Any], path: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    values: dict[str, int] = {}
    blockers: list[dict[str, Any]] = []
    for field in COUNT_FIELDS:
        value = int_value(report.get(field))
        if value is None or value < 0:
            blockers.append(blocker(path, f"invalid_{field}", f"{field} must be a non-negative integer"))
            values[field] = 0
        else:
            values[field] = value
    return values, blockers


def validate_pairing_coverage(
    counts: dict[str, int],
    path: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    matured = counts["matured_count"]
    scored = counts["scored_count"]
    paired = counts["paired_clean_count"]
    full = counts["full_gotra_available_count"]
    deterministic = counts["deterministic_reference_available_count"]
    if scored > matured:
        blockers.append(blocker(path, "scored_count_exceeds_matured_count", "scored_count cannot exceed matured_count"))
    if paired > scored:
        blockers.append(blocker(path, "paired_clean_count_exceeds_scored_count", "paired_clean_count cannot exceed scored_count"))
    if paired > full or paired > deterministic:
        blockers.append(blocker(path, "paired_clean_count_exceeds_available_count", "paired_clean_count cannot exceed available arm counts"))
    if full != deterministic or paired != full or paired != deterministic:
        blockers.append(
            blocker(
                path,
                "paired_coverage_inconsistent",
                "full_gotra and deterministic availability must exactly match paired_clean_count",
            )
        )
    if counts["pairing_blocker_count"] > 0:
        blockers.append(blocker(path, "pairing_blocker_count_nonzero", "pairing_blocker_count must be zero"))
    return blockers


def validate_provenance(report: dict[str, Any], path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        return [blocker(path, "missing_provenance", "report provenance object is required")]

    run_id = str(report.get("verdict_report_run_id") or "").strip()
    provenance_run_id = str(provenance.get("verdict_report_run_id") or "").strip()
    if not run_id:
        blockers.append(blocker(path, "missing_verdict_report_run_id", "verdict_report_run_id is required"))
    if not provenance_run_id:
        blockers.append(blocker(path, "missing_provenance_verdict_report_run_id", "provenance.verdict_report_run_id is required"))
    if run_id and provenance_run_id and run_id != provenance_run_id:
        blockers.append(blocker(path, "verdict_report_run_id_mismatch", "verdict_report_run_id must match provenance.verdict_report_run_id"))

    source_run_ids = source_list(report.get("source_run_ids"))
    provenance_source_run_ids = source_list(provenance.get("source_run_ids"))
    if source_run_ids is None:
        blockers.append(blocker(path, "invalid_source_run_ids", "source_run_ids must be a list of strings"))
    elif not source_run_ids:
        blockers.append(blocker(path, "missing_source_run_ids", "source_run_ids cannot be empty"))
    if provenance_source_run_ids is None:
        blockers.append(blocker(path, "invalid_provenance_source_run_ids", "provenance.source_run_ids must be a list of strings"))
    if source_run_ids is not None and provenance_source_run_ids is not None and source_run_ids != provenance_source_run_ids:
        blockers.append(blocker(path, "source_run_ids_mismatch", "source_run_ids must match provenance.source_run_ids"))

    blockers.extend(source_path_blockers(report, path))
    return blockers


def validate_schema(report: dict[str, Any], path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if report.get("report_schema") != TARGET_REPORT_SCHEMA:
        blockers.append(blocker(path, "report_schema_mismatch", f"report_schema must be {TARGET_REPORT_SCHEMA}"))
    for field in (
        "source_readiness_summary_path",
        "source_scored_summary_path",
        "evidence_layer",
    ):
        if not is_non_empty_string(report.get(field)):
            blockers.append(blocker(path, f"missing_{field}", f"{field} is required"))
    if not isinstance(report.get("non_claims"), (list, dict)):
        blockers.append(blocker(path, "invalid_non_claims", "non_claims must be a list or object"))
    for field in (
        "winner_emitted",
        "actual_30d_verdict_executed",
        "v3_7_actual_verdict_executable",
        "provider_or_backend_called",
        "codex_cli_called",
        "formal_lite_entered",
    ):
        if not is_bool(report.get(field)):
            blockers.append(blocker(path, f"invalid_{field}", f"{field} must be boolean"))
    for field in ("provider_or_backend_called", "codex_cli_called", "formal_lite_entered"):
        if report.get(field) is True:
            blockers.append(blocker(path, f"{field}_true", f"{field} must be false for validator inputs"))
    return blockers


def validate_executable_flag(
    report: dict[str, Any],
    path: str,
) -> list[dict[str, Any]]:
    if report.get("v3_7_actual_verdict_executable") is not True:
        return []
    readiness_path = path_exists_for_hash_check(report.get("source_readiness_summary_path"))
    if readiness_path is None:
        return [
            blocker(
                path,
                "actual_verdict_executable_without_local_readiness_summary",
                "v3_7_actual_verdict_executable=true requires a local readiness summary",
            )
        ]
    try:
        readiness_payload = load_json(readiness_path)
    except Exception:  # noqa: BLE001 - converted to provenance blocker.
        return [blocker(path, "readiness_summary_unreadable", "readiness summary is unreadable")]
    if not isinstance(readiness_payload, dict) or not readiness_status_is_ready(readiness_payload):
        return [
            blocker(
                path,
                "actual_verdict_executable_without_ready_source",
                "v3_7_actual_verdict_executable=true requires READY source readiness",
            )
        ]
    return []


def validate_report_payload(
    report: dict[str, Any],
) -> tuple[ValidatedReport | None, dict[str, int], dict[str, bool], list[dict[str, Any]]]:
    path = str(report.get("report_path") or "inline_report")
    blockers: list[dict[str, Any]] = []
    counts, count_blockers = validate_counts(report, path)
    blockers.extend(count_blockers)
    blockers.extend(validate_schema(report, path))
    readiness_hash_valid, readiness_blockers = verify_summary_hash(
        report,
        path=path,
        path_field="source_readiness_summary_path",
        hash_field="source_readiness_summary_sha256",
    )
    scored_hash_valid, scored_blockers = verify_summary_hash(
        report,
        path=path,
        path_field="source_scored_summary_path",
        hash_field="source_scored_summary_sha256",
    )
    blockers.extend(readiness_blockers)
    blockers.extend(scored_blockers)
    blockers.extend(validate_provenance(report, path))
    blockers.extend(validate_pairing_coverage(counts, path))
    blockers.extend(validate_executable_flag(report, path))

    if counts["future_data_violation_count"] > 0:
        blockers.append(blocker(path, "future_data_violation_count_nonzero", "future_data_violation_count must be zero"))
    if counts["provenance_blocker_count"] > 0:
        blockers.append(blocker(path, "provenance_blocker_count_nonzero", "provenance_blocker_count must be zero"))

    if winner_or_verdict_executed(report):
        blockers.append(
            blocker(
                path,
                "winner_or_actual_verdict_present",
                "validator inputs cannot emit a winner or execute actual 30D verdict",
            )
        )

    claim_result = claim_scan.scan_sources(claim_sources(path, report))
    for category in ("overclaim", "direct_llm", "maturity_gate", "short_horizon_as_30d"):
        for item in claim_result[category]:
            blockers.append(
                blocker(
                    item.get("path", path),
                    str(item.get("rule_id") or category),
                    str(item.get("reason") or "claim boundary violation"),
                )
            )

    if blockers:
        return None, counts, {
            "readiness_summary_hash_valid": readiness_hash_valid,
            "scored_summary_hash_valid": scored_hash_valid,
        }, blockers
    return (
        ValidatedReport(path=normalize_path(path), payload=report),
        counts,
        {
            "readiness_summary_hash_valid": readiness_hash_valid,
            "scored_summary_hash_valid": scored_hash_valid,
        },
        blockers,
    )


def blocker_count(blocked_items: list[dict[str, Any]], prefixes: tuple[str, ...], exact: set[str] | None = None) -> int:
    exact = exact or set()
    count = 0
    for item in blocked_items:
        rule_id = str(item.get("rule_id") or "")
        if rule_id in exact or rule_id.startswith(prefixes):
            count += 1
    return count


def status_for_summary(summary: dict[str, Any]) -> str:
    if summary["overclaim_blocker_count"]:
        return STATUS_BLOCKED_OVERCLAIM
    if summary["schema_blocker_count"]:
        return STATUS_BLOCKED_SCHEMA
    if summary["future_data_violation_count"]:
        return STATUS_BLOCKED_FUTURE_DATA
    if summary["provenance_blocker_count"]:
        return STATUS_BLOCKED_PROVENANCE
    if summary["pairing_blocker_count"]:
        return STATUS_BLOCKED_PAIRING
    if summary["report_fixture_count"] == 0 or summary["matured_count"] == 0:
        return STATUS_DATA_INSUFFICIENT
    return STATUS_READY


def base_summary(config: ValidatorConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "validator_run_id": config.validator_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "validator_status": STATUS_DATA_INSUFFICIENT,
        "report_schema_valid": False,
        "readiness_summary_hash_valid": False,
        "scored_summary_hash_valid": False,
        "report_fixture_count": 0,
        "matured_count": 0,
        "scored_count": 0,
        "paired_clean_count": 0,
        "full_gotra_available_count": 0,
        "deterministic_reference_available_count": 0,
        "future_data_violation_count": 0,
        "provenance_blocker_count": 0,
        "pairing_blocker_count": 0,
        "schema_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "blocker_reasons": [],
        "blocked_items": [],
        "winner_emitted": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": EVIDENCE_LAYER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "non_claims": [
            "not an actual 30D forward-live verdict",
            "not OOS evidence",
            "not science/public proof",
            "not trading or investment advice",
            "no deterministic/full_gotra/ksana winner emitted",
            "does not bypass the 2026-07-21 30D maturity gate",
        ],
    }


def build_summary(config: ValidatorConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    raw_reports, collection_blockers = collect_report_payloads(config)
    blocked_items = list(collection_blockers)
    valid_reports: list[ValidatedReport] = []
    aggregate_counts = {field: 0 for field in COUNT_FIELDS}
    readiness_hash_valid = bool(raw_reports)
    scored_hash_valid = bool(raw_reports)

    for report in raw_reports:
        if not isinstance(report, dict):
            blocked_items.append(blocker("inline_report", "malformed_report_row", "report row must be an object"))
            continue
        validated, counts, hash_flags, report_blockers = validate_report_payload(report)
        for field in COUNT_FIELDS:
            aggregate_counts[field] += counts.get(field, 0)
        readiness_hash_valid = readiness_hash_valid and hash_flags["readiness_summary_hash_valid"]
        scored_hash_valid = scored_hash_valid and hash_flags["scored_summary_hash_valid"]
        blocked_items.extend(report_blockers)
        if validated is not None:
            valid_reports.append(validated)

    schema_blocker_count = blocker_count(
        blocked_items,
        (
            "malformed_",
            "invalid_",
            "missing_source_",
            "missing_evidence",
            "report_schema",
            "provider_or_backend_called",
            "codex_cli_called",
            "formal_lite_entered",
        ),
        exact={
            "missing_source_readiness_summary_path",
            "missing_source_scored_summary_path",
            "missing_or_invalid_source_readiness_summary_sha256",
            "missing_or_invalid_source_scored_summary_sha256",
        },
    )
    provenance_blocker_count = blocker_count(
        blocked_items,
        (
            "source_",
            "verdict_report_run_id",
            "forbidden_",
            "readiness_",
            "actual_verdict_executable",
        ),
        exact={
            "missing_provenance",
            "missing_verdict_report_run_id",
            "missing_provenance_verdict_report_run_id",
            "missing_source_run_ids",
            "invalid_provenance_source_run_ids",
            "source_readiness_summary_sha256_mismatch",
            "source_scored_summary_sha256_mismatch",
        },
    )
    pairing_blocker_count = blocker_count(
        blocked_items,
        ("paired_", "pairing_", "scored_count_exceeds",),
    )
    future_blocker_count = blocker_count(
        blocked_items,
        ("future_data_",),
    )
    overclaim_blocker_count = blocker_count(
        blocked_items,
        (),
        exact={
            "winner_or_actual_verdict_present",
            "oos_science_public_trading_claim",
            "provider_runtime_as_public_claim",
            "direct_llm_without_parametric_memory_control",
            "direct_llm_clean_no_future_baseline",
            "v3_7_allowed_true",
            "v3_7_verdict_allowed",
            "v3_7_plain_allowed",
            "thirty_day_forward_live_verdict",
            "short_horizon_as_30d_verdict",
        },
    )

    summary.update(
        {
            "report_fixture_count": len(raw_reports),
            "report_schema_valid": bool(valid_reports) and not schema_blocker_count,
            "readiness_summary_hash_valid": readiness_hash_valid,
            "scored_summary_hash_valid": scored_hash_valid,
            "matured_count": aggregate_counts["matured_count"],
            "scored_count": aggregate_counts["scored_count"],
            "paired_clean_count": aggregate_counts["paired_clean_count"],
            "full_gotra_available_count": aggregate_counts["full_gotra_available_count"],
            "deterministic_reference_available_count": aggregate_counts["deterministic_reference_available_count"],
            "future_data_violation_count": aggregate_counts["future_data_violation_count"] + future_blocker_count,
            "provenance_blocker_count": aggregate_counts["provenance_blocker_count"] + provenance_blocker_count,
            "pairing_blocker_count": aggregate_counts["pairing_blocker_count"] + pairing_blocker_count,
            "schema_blocker_count": schema_blocker_count,
            "overclaim_blocker_count": overclaim_blocker_count,
            "winner_emitted": any(report.payload.get("winner_emitted") is True for report in valid_reports),
            "actual_30d_verdict_executed": any(report.payload.get("actual_30d_verdict_executed") is True for report in valid_reports),
            "v3_7_actual_verdict_executable": all(
                report.payload.get("v3_7_actual_verdict_executable") is True
                for report in valid_reports
            )
            if valid_reports
            else False,
            "provider_or_backend_called": any(report.payload.get("provider_or_backend_called") is True for report in valid_reports),
            "codex_cli_called": any(report.payload.get("codex_cli_called") is True for report in valid_reports),
            "formal_lite_entered": any(report.payload.get("formal_lite_entered") is True for report in valid_reports),
            "blocked_items": blocked_items,
        }
    )
    summary["validator_status"] = status_for_summary(summary)
    summary["blocker_reasons"] = sorted(
        {
            str(item.get("rule_id") or "")
            for item in blocked_items
            if str(item.get("rule_id") or "")
        }
    )
    return summary


def write_outputs(config: ValidatorConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "validator_run_id": config.validator_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "validator_status": summary["validator_status"],
        "reports": [normalize_path(path) for path in config.reports],
        "report_manifest": normalize_path(config.report_manifest),
        "winner_emitted": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def blocked_run_id_summary(config: ValidatorConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "validator_status": STATUS_BLOCKED_SCHEMA,
            "schema_blocker_count": 1,
            "blocker_reasons": ["output_run_id_exists"],
            "blocked_items": [
                blocker(run_root, "output_run_id_exists", "output run id exists")
            ],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_validator(config: ValidatorConfig) -> dict[str, Any]:
    validate_run_id(config.validator_run_id)
    run_root = config.output_dir / config.validator_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    summary = build_summary(config, run_root=run_root)
    write_outputs(config, summary, run_root=run_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", type=Path, default=[])
    parser.add_argument("--report-manifest", type=Path, default=None)
    parser.add_argument("--validator-run-id", default=default_run_id())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_7b_verdict_report_schema_validator/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ValidatorConfig:
    return ValidatorConfig(
        validator_run_id=str(args.validator_run_id),
        output_dir=args.output_dir,
        reports=tuple(args.report or ()),
        report_manifest=args.report_manifest,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_validator(config_from_args(parse_args(argv)))
    return 1 if summary.get("validator_status") in BLOCKED_STATUSES else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
