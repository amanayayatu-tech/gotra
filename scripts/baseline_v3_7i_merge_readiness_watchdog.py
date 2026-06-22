#!/usr/bin/env python3
"""GOTRA v3.7I fixture-only merge-readiness watchdog."""

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

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402
from scripts import baseline_v3_7h_claim_boundary_regression as claim_regression  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7i.merge_readiness_watchdog_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7i.merge_readiness_watchdog_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_7i_merge_readiness_watchdog_"
SCRIPT_VERSION = "v3.7i-20260622"
EVIDENCE_LAYER = "engineering_internal_merge_readiness_watchdog"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "MERGE_READINESS_READY"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_CI = "BLOCKED_CI"
STATUS_BLOCKED_REVIEW = "BLOCKED_REVIEW"
STATUS_BLOCKED_CONFLICT = "BLOCKED_CONFLICT"
STATUS_BLOCKED_DRAFT = "BLOCKED_DRAFT"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_RUN_ID_EXISTS = "MERGE_READINESS_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}

REQUIRED_FIELDS = (
    "base_ref",
    "base_sha",
    "head_ref",
    "head_sha",
    "merge_state_status",
    "is_draft",
    "changed_files",
    "status_checks",
    "review_threads",
    "evidence_layer",
    "actual_30d_readiness_status",
    "v3_7_actual_verdict_executable",
)
REQUIRED_FALSE_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
SHA_RE = re.compile(r"^[a-fA-F0-9]{7,64}$")


@dataclass(frozen=True)
class WatchdogConfig:
    watchdog_run_id: str
    output_dir: Path
    fixture: Path
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"watchdog_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("watchdog_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def normalize_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    return claim_scan.normalize_scan_path(path)


def blocked_item(path: Path | str, rule_id: str, reason: str, *, line_number: int = 0) -> dict[str, Any]:
    return {
        "path": normalize_path(path),
        "line_number": line_number,
        "rule_id": rule_id,
        "reason": reason,
    }


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "forbidden_fixture_path", "fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [blocked_item(path, "fixture_read_error", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [blocked_item(path, "fixture_json_decode_error", str(exc))]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "fixture_root_not_object", "fixture must be a JSON object")]
    return payload, []


def extract_nodes(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("nodes"), list):
            return list(value["nodes"])
        if isinstance(value.get("contexts"), dict):
            return extract_nodes(value["contexts"])
        if isinstance(value.get("files"), dict):
            return extract_nodes(value["files"])
    return []


def path_from_changed_file(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("path") or entry.get("filename") or entry.get("name") or "")
    return ""


def changed_file_paths(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("changed_files", payload.get("files", []))
    entries = extract_nodes(raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return []
    return [path for path in (path_from_changed_file(entry) for entry in entries) if path]


def schema_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for field in REQUIRED_FIELDS:
        if field not in payload:
            blockers.append(blocked_item("fixture", f"missing_{field}", f"{field} is required"))
    if blockers:
        return blockers

    for field in ("base_ref", "head_ref"):
        if not is_non_empty_string(payload.get(field)):
            blockers.append(blocked_item("fixture", f"{field}_invalid", f"{field} must be a non-empty string"))
    for field in ("base_sha", "head_sha"):
        value = payload.get(field)
        if not isinstance(value, str) or not SHA_RE.fullmatch(value.strip()):
            blockers.append(blocked_item("fixture", f"{field}_invalid", f"{field} must be a git SHA-like string"))
    if not isinstance(payload.get("is_draft"), bool):
        blockers.append(blocked_item("fixture", "is_draft_not_bool", "is_draft must be boolean"))
    if not isinstance(payload.get("changed_files"), (list, dict)):
        blockers.append(blocked_item("fixture", "changed_files_invalid", "changed_files must be a list or GitHub connection object"))
    if not isinstance(payload.get("status_checks"), (list, dict)):
        blockers.append(blocked_item("fixture", "status_checks_invalid", "status_checks must be a list or GitHub connection object"))
    if not isinstance(payload.get("review_threads"), (list, dict)):
        blockers.append(blocked_item("fixture", "review_threads_invalid", "review_threads must be a list or GitHub connection object"))
    if payload.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("fixture", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if payload.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(
            blocked_item(
                "fixture",
                "actual_30d_readiness_status_not_data_not_matured",
                "actual 30D readiness must remain DATA_NOT_MATURED",
            )
        )
    if payload.get("actual_30d_next_check_after", ACTUAL_30D_NEXT_CHECK_AFTER) != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(
            blocked_item(
                "fixture",
                "actual_30d_next_check_after_mismatch",
                "actual 30D next_check_after must remain 2026-07-21T00:00:00Z",
            )
        )
    if payload.get("direct_llm_interpretation", DIRECT_LLM_INTERPRETATION) != DIRECT_LLM_INTERPRETATION:
        blockers.append(
            blocked_item(
                "fixture",
                "direct_llm_interpretation_mismatch",
                "direct_llm_interpretation must be direct_llm_parametric_memory_control",
            )
        )
    return blockers


def runtime_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in REQUIRED_FALSE_FLAGS:
        if flag not in payload:
            blockers.append(blocked_item("fixture", f"missing_{flag}", f"{flag} must be explicitly present and false"))
        elif payload.get(flag) is not False:
            blockers.append(blocked_item("fixture", f"{flag}_not_false", f"{flag} must be false"))
    return blockers


def artifact_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path in changed_file_paths(payload):
        if claim_scan.forbidden_path(path):
            blockers.append(blocked_item(path, "forbidden_changed_file_path", "changed file path violates artifact boundary"))
    blockers.extend(claim_regression.path_blockers(payload, path="fixture"))
    return blockers


def check_status_ok(status: str, conclusion: str) -> bool:
    status_upper = status.upper()
    conclusion_upper = conclusion.upper()
    if status_upper == "SUCCESS" and conclusion_upper in {"", "SUCCESS"}:
        return True
    return status_upper == "COMPLETED" and conclusion_upper == "SUCCESS"


def check_name(check: dict[str, Any]) -> str:
    return str(check.get("name") or check.get("context") or check.get("workflowName") or "")


def status_check_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("status_checks", payload.get("statusCheckRollup", []))
    entries = extract_nodes(raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def ci_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    checks = status_check_entries(payload)
    if not checks:
        return [blocked_item("fixture.status_checks", "ci_no_checks", "at least one CI check is required")]

    required_raw = payload.get("required_status_checks", payload.get("required_checks", []))
    required = [str(item) for item in required_raw] if isinstance(required_raw, list) else []
    by_name = {check_name(check): check for check in checks if check_name(check)}
    for required_name in required:
        if required_name not in by_name:
            blockers.append(blocked_item("fixture.status_checks", "ci_missing_required_check", required_name))
    for index, check in enumerate(checks):
        name = check_name(check) or f"check[{index}]"
        status = str(check.get("status") or "")
        conclusion = str(check.get("conclusion") or "")
        if not check_status_ok(status, conclusion):
            blockers.append(
                blocked_item(
                    f"fixture.status_checks[{index}]",
                    "ci_check_not_success",
                    f"{name} must be COMPLETED/SUCCESS",
                )
            )
    return blockers


def review_thread_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("review_threads", payload.get("reviewThreads", []))
    entries = extract_nodes(raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def is_thread_resolved(thread: dict[str, Any]) -> bool:
    return bool(thread.get("is_resolved", thread.get("isResolved", thread.get("resolved", False))))


def is_thread_outdated(thread: dict[str, Any]) -> bool:
    return bool(thread.get("is_outdated", thread.get("isOutdated", thread.get("outdated", False))))


def thread_priority(thread: dict[str, Any]) -> str:
    explicit = str(thread.get("priority") or thread.get("severity") or "").upper()
    if explicit in {"P1", "P2", "P3"}:
        return explicit
    text = " ".join(
        str(thread.get(key) or "")
        for key in ("title", "body", "comment", "summary")
    )
    if re.search(r"\bP1\b", text, re.IGNORECASE):
        return "P1"
    if re.search(r"\bP2\b", text, re.IGNORECASE):
        return "P2"
    return explicit


def review_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for index, thread in enumerate(review_thread_entries(payload)):
        priority = thread_priority(thread)
        if priority in {"P1", "P2"} and not is_thread_resolved(thread) and not is_thread_outdated(thread):
            blockers.append(
                blocked_item(
                    f"fixture.review_threads[{index}]",
                    "active_p1_p2_review_thread",
                    f"active {priority} review thread blocks merge-readiness",
                )
            )
    return blockers


def claim_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return claim_regression.claim_blockers(payload, path="fixture")


def choose_status(
    *,
    schema: list[dict[str, Any]],
    runtime: list[dict[str, Any]],
    artifact: list[dict[str, Any]],
    claim: list[dict[str, Any]],
    draft: list[dict[str, Any]],
    conflict: list[dict[str, Any]],
    ci: list[dict[str, Any]],
    review: list[dict[str, Any]],
) -> str:
    if schema or runtime:
        return STATUS_BLOCKED_SCHEMA
    if artifact:
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if draft:
        return STATUS_BLOCKED_DRAFT
    if conflict:
        return STATUS_BLOCKED_CONFLICT
    if ci:
        return STATUS_BLOCKED_CI
    if review:
        return STATUS_BLOCKED_REVIEW
    if claim:
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    return STATUS_READY


def base_summary(config: WatchdogConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "watchdog_run_id": config.watchdog_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "watchdog_status": status,
        "watchdog_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "base_ref": "",
        "base_sha": "",
        "head_ref": "",
        "head_sha": "",
        "merge_state_status": "",
        "merge_state_boundary_status": "unknown",
        "ci_status": "unknown",
        "review_status": "unknown",
        "draft_status": "unknown",
        "artifact_boundary_status": "unknown",
        "claim_boundary_status": "unknown",
        "runtime_boundary_status": "unknown",
        "schema_boundary_status": "unknown",
        "changed_file_count": 0,
        "status_check_count": 0,
        "required_status_check_count": 0,
        "active_p1_p2_review_thread_count": 0,
        "review_thread_count": 0,
        "blocked_item_count": 0,
        "blocker_reasons": [],
        "blocked_items": [],
        "ready_for_judge_auto_merge_gate": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "watchdog_content_sha256": "",
        "non_claims": {
            "not_actual_30d_verdict": True,
            "not_oos_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_provider_run": True,
        },
    }


def build_summary(config: WatchdogConfig) -> dict[str, Any]:
    validate_run_id(config.watchdog_run_id)
    run_root = config.output_dir / config.watchdog_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["blocked_item_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        summary["blocked_items"] = [blocked_item(run_root, "output_run_id_exists", "output run id exists")]
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    payload, fixture_blockers = load_fixture(config.fixture)
    schema = fixture_blockers + (schema_blockers(payload) if payload else [])
    runtime = runtime_blockers(payload) if payload else []
    artifact = artifact_blockers(payload) if payload else []
    claim = claim_blockers(payload) if payload else []
    draft = []
    conflict = []
    ci = []
    review = []

    if payload:
        if payload.get("is_draft") is True:
            draft.append(blocked_item("fixture.is_draft", "draft_pr", "draft PR cannot be merge-ready"))
        if str(payload.get("merge_state_status") or "").upper() != "CLEAN":
            conflict.append(
                blocked_item(
                    "fixture.merge_state_status",
                    "merge_state_not_clean",
                    "merge_state_status must be CLEAN",
                )
            )
        ci = ci_blockers(payload)
        review = review_blockers(payload)

    status = choose_status(
        schema=schema,
        runtime=runtime,
        artifact=artifact,
        claim=claim,
        draft=draft,
        conflict=conflict,
        ci=ci,
        review=review,
    )
    run_root.mkdir(parents=True, exist_ok=True)
    summary = base_summary(config, run_root=run_root, status=status)
    blocked_items = schema + runtime + artifact + draft + conflict + ci + review + claim
    review_threads = review_thread_entries(payload) if payload else []
    required_raw = payload.get("required_status_checks", payload.get("required_checks", [])) if payload else []
    required_checks = required_raw if isinstance(required_raw, list) else []
    summary.update(
        {
            "watchdog_status": status,
            "base_ref": str(payload.get("base_ref") or ""),
            "base_sha": str(payload.get("base_sha") or ""),
            "head_ref": str(payload.get("head_ref") or ""),
            "head_sha": str(payload.get("head_sha") or ""),
            "merge_state_status": str(payload.get("merge_state_status") or ""),
            "merge_state_boundary_status": "blocked" if conflict else "clean",
            "ci_status": "blocked" if ci else "clean",
            "review_status": "blocked" if review else "clean",
            "draft_status": "blocked" if draft else "clean",
            "artifact_boundary_status": "blocked" if artifact else "clean",
            "claim_boundary_status": "blocked" if claim else "clean",
            "runtime_boundary_status": "blocked" if runtime else "clean",
            "schema_boundary_status": "blocked" if schema else "clean",
            "changed_file_count": len(changed_file_paths(payload)) if payload else 0,
            "status_check_count": len(status_check_entries(payload)) if payload else 0,
            "required_status_check_count": len(required_checks),
            "active_p1_p2_review_thread_count": len(review),
            "review_thread_count": len(review_threads),
            "blocked_item_count": len(blocked_items),
            "blocker_reasons": [str(item["rule_id"]) for item in blocked_items],
            "blocked_items": blocked_items[:100],
            "ready_for_judge_auto_merge_gate": status == STATUS_READY,
            "provider_or_backend_called": bool(payload.get("provider_or_backend_called")) if payload else False,
            "codex_cli_new_call": bool(payload.get("codex_cli_new_call")) if payload else False,
            "formal_lite_entered": bool(payload.get("formal_lite_entered")) if payload else False,
            "v3_7_actual_verdict_executable": bool(payload.get("v3_7_actual_verdict_executable")) if payload else False,
            "v3_7_actual_verdict_executed": bool(payload.get("v3_7_actual_verdict_executed")) if payload else False,
            "actual_30d_readiness_status": str(payload.get("actual_30d_readiness_status") or ACTUAL_30D_READINESS_STATUS),
            "actual_30d_next_check_after": str(payload.get("actual_30d_next_check_after") or ACTUAL_30D_NEXT_CHECK_AFTER),
            "direct_llm_interpretation": str(payload.get("direct_llm_interpretation") or DIRECT_LLM_INTERPRETATION),
            "watchdog_content_sha256": stable_sha256_json(
                {
                    "schema": SUMMARY_SCHEMA,
                    "payload": payload,
                    "status": status,
                    "blocker_reasons": [str(item["rule_id"]) for item in blocked_items],
                }
            ),
        }
    )
    write_outputs(config, summary, run_root=run_root)
    return summary


def write_outputs(config: WatchdogConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "watchdog_run_id": config.watchdog_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "watchdog_content_sha256": summary.get("watchdog_content_sha256"),
        "watchdog_status": summary.get("watchdog_status"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watchdog-run-id", default=default_run_id())
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7i_merge_readiness_watchdog/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> WatchdogConfig:
    return WatchdogConfig(
        watchdog_run_id=str(args.watchdog_run_id),
        output_dir=args.output_dir,
        fixture=args.fixture,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed with redacted stderr.
        print(f"merge-readiness watchdog failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("watchdog_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
