#!/usr/bin/env python3
"""GOTRA v3.7H claim-boundary CI/local regression guard."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7h.claim_boundary_regression_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7h.claim_boundary_regression_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_7h_claim_boundary_regression_"
SCRIPT_VERSION = "v3.7h-20260622"
EVIDENCE_LAYER = "engineering_internal_claim_boundary_regression"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"

STATUS_READY = "V3_7_CLAIM_BOUNDARY_REGRESSION_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_DIGEST_BOUNDARY = "BLOCKED_DIGEST_BOUNDARY"
STATUS_RUN_ID_EXISTS = "CLAIM_BOUNDARY_REGRESSION_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}

RUNTIME_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "codex_cli_called",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
REQUIRED_ROOT_FALSE_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
BOUNDARY_CRITICAL_DIGEST_FIELDS = (
    "direct_llm_interpretation",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
PATH_KEYS = {
    "artifact_manifest_path",
    "artifact_path",
    "artifact_paths",
    "hash_index_path",
    "input_artifact_path",
    "input_artifact_paths",
    "ledger_path",
    "ledger_paths",
    "manifest_path",
    "output_artifact_path",
    "output_artifact_paths",
    "path",
    "paths",
    "raw_artifact_path",
    "source_artifact_path",
    "source_artifact_paths",
    "source_path",
    "source_paths",
    "source_summary_path",
    "source_summary_paths",
    "summary_path",
    "transcript_path",
}
TEXT_KEYS = {
    "body",
    "can_say",
    "cannot_say",
    "claim",
    "claims",
    "conclusion",
    "description",
    "known_blockers",
    "narrative",
    "next_safe_actions",
    "non_claims",
    "notes",
    "rationale",
    "reasoning",
    "statement",
    "summary",
    "text",
    "title",
    "verdict",
    "winner",
}
STATUS_LIKE_KEYS = {
    "actual_30d_readiness_status",
    "readiness_status",
    "status",
    "verdict_status",
    "v3_7_actual_verdict_status",
}
STATUS_OVERCLAIM_PATTERNS = (
    (
        "ready_for_forward_live_verdict_status",
        re.compile(r"\bREADY_FOR_FORWARD_LIVE_VERDICT\b", re.IGNORECASE),
    ),
    (
        "actual_verdict_executable_status",
        re.compile(
            r"\b(actual\s+)?(?:30D\s+)?(?:v3[._-]?7\s+)?verdict\b.{0,50}"
            r"\b(executable|executed|ready|allowed|pass)\b",
            re.IGNORECASE,
        ),
    ),
)
SHORT_HORIZON_UPGRADE_RE = re.compile(
    r"\b(short[-_ ]horizon|canary|dashboard|harness|schema|preflight)\b.{0,80}"
    r"\b(actual\s+)?(?:30D\s+)?(?:v3[._-]?7\s+)?verdict\b.{0,50}\b(ready|allowed|pass|executable|equivalent)\b",
    re.IGNORECASE,
)
EXTRA_OVERCLAIM_RE = re.compile(
    r"\b(winner|outperform|profit|alpha)\b.{0,60}\b(claim|proof|recommendation|advice|guarantee|accepted|validated)\b",
    re.IGNORECASE,
)
FALSE_LINE_RE = re.compile(r"[:=]\s*(false|no)\b|\bnot\s+(ready|allowed|pass|executable|executed)\b", re.IGNORECASE)


@dataclass(frozen=True)
class RegressionConfig:
    regression_run_id: str
    output_dir: Path
    fixture: Path | None = None
    files: tuple[Path, ...] = ()
    repo_root: Path = REPO_ROOT
    tracked_scan: bool = False
    pathspecs: tuple[str, ...] = ()
    allow_negative_test_paths: tuple[str, ...] = ()
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"regression_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("regression_run_id may contain only letters, numbers, '_' and '-'")


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


def blocked_item(path: Path | str, rule_id: str, reason: str, *, line_number: int = 0) -> dict[str, Any]:
    return {
        "path": normalize_path(path),
        "line_number": line_number,
        "rule_id": rule_id,
        "reason": reason,
    }


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_status_like_key(key: str) -> bool:
    return key in STATUS_LIKE_KEYS or key.endswith("_status")


def is_text_key(key: str) -> bool:
    return key in TEXT_KEYS or is_status_like_key(key)


def is_negative_context(path: str, *, explicit: bool, allow_patterns: tuple[str, ...]) -> bool:
    if explicit:
        return True
    normalized = normalize_path(path)
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in allow_patterns)


def read_json_object(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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


def collect_file_entries(config: RegressionConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    skipped_forbidden = 0
    for path in sorted(set(config.files)):
        normalized = normalize_path(path)
        if claim_scan.forbidden_path(normalized):
            blockers.append(blocked_item(normalized, "forbidden_file_path", "file path is forbidden; content was not read"))
            skipped_forbidden += 1
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            blockers.append(blocked_item(path, "file_read_error", str(exc)))
            continue
        entries.append({"path": normalized, "text": text, "source_mode": "file"})
    if config.tracked_scan:
        tracked_paths = git_tracked_files(config.repo_root, config.pathspecs)
        for rel_path in tracked_paths:
            normalized = normalize_path(config.repo_root / rel_path)
            if claim_scan.forbidden_path(normalized):
                blockers.append(blocked_item(normalized, "forbidden_tracked_path", "tracked path is forbidden; content was not read"))
                skipped_forbidden += 1
                continue
            full_path = config.repo_root / rel_path
            if not full_path.is_file() or full_path.is_symlink():
                continue
            try:
                text = full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                blockers.append(blocked_item(normalized, "tracked_file_read_error", str(exc)))
                continue
            entries.append({"path": normalized, "text": text, "source_mode": "tracked_file"})
    return entries, blockers, skipped_forbidden


def git_tracked_files(repo_root: Path, pathspecs: tuple[str, ...]) -> list[str]:
    cmd = ["git", "-C", str(repo_root), "ls-files"]
    if pathspecs:
        cmd.extend(["--", *pathspecs])
    output = subprocess.check_output(cmd, text=True)  # noqa: S603 - fixed git subcommand, repo-local read only.
    return [line for line in output.splitlines() if line.strip()]


def fixture_entries(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    payload, blockers = read_json_object(path)
    if blockers:
        return {}, [], blockers
    raw_documents = payload.get("documents", payload.get("files", []))
    if raw_documents is None:
        raw_documents = []
    if not isinstance(raw_documents, list):
        return payload, [], [blocked_item(path, "documents_not_list", "documents/files must be a list")]
    entries: list[dict[str, Any]] = []
    schema_blockers: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_documents):
        if not isinstance(entry, dict):
            schema_blockers.append(blocked_item(f"{path}#documents[{index}]", "document_not_object", "document entries must be objects"))
            continue
        entries.append(dict(entry))
    return payload, entries, schema_blockers


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


def recursive_text_sources(value: Any, *, path: str, key_hint: str = "") -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    if isinstance(value, str):
        if is_text_key(key_hint) or not key_hint:
            sources.append(claim_scan.ScanSource(path=path, text=value, origin="v3_7h_regression"))
    elif isinstance(value, dict):
        for key, item in sorted(value.items()):
            sources.extend(recursive_text_sources(item, path=f"{path}.{key}", key_hint=key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            sources.extend(recursive_text_sources(item, path=f"{path}[{index}]", key_hint=key_hint))
    return sources


def path_blockers(value: Any, *, path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for candidate in recursive_paths(value):
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocked_item(candidate, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
    return blockers


def claim_blockers(value: Any, *, path: str) -> list[dict[str, Any]]:
    sources = recursive_text_sources(value, path=path)
    scan = claim_scan.scan_sources(sources)
    blockers = scan["overclaim"] + scan["direct_llm"] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(extra_text_blockers(sources))
    return blockers


def extra_text_blockers(sources: list[claim_scan.ScanSource]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for source in sources:
        for line_number, line in enumerate(source.text.splitlines(), start=1):
            for rule_id, pattern in STATUS_OVERCLAIM_PATTERNS:
                if pattern.search(line) and not FALSE_LINE_RE.search(line):
                    blockers.append(
                        blocked_item(
                            source.path,
                            rule_id,
                            "status-like wording cannot assert forward-live or actual verdict readiness",
                            line_number=line_number,
                        )
                    )
            if SHORT_HORIZON_UPGRADE_RE.search(line) and not FALSE_LINE_RE.search(line):
                blockers.append(
                    blocked_item(
                        source.path,
                        "short_horizon_or_prep_as_actual_30d_verdict",
                        "short-horizon/canary/dashboard/harness/schema/preflight evidence cannot authorize actual 30D verdict",
                        line_number=line_number,
                    )
                )
            if EXTRA_OVERCLAIM_RE.search(line) and not claim_scan.is_negated(line, EXTRA_OVERCLAIM_RE.search(line).start()):
                blockers.append(
                    blocked_item(
                        source.path,
                        "winner_outperform_profit_alpha_claim",
                        "winner/outperform/profit/alpha wording exceeds engineering/internal boundary",
                        line_number=line_number,
                    )
                )
    return blockers


def runtime_flag_blockers(value: Any, *, path: str, require_explicit: bool) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if isinstance(value, dict):
        current_requires = require_explicit or "evidence_layer" in value or any(flag in value for flag in RUNTIME_FLAGS)
        if current_requires:
            for flag in REQUIRED_ROOT_FALSE_FLAGS:
                if flag not in value:
                    blockers.append(blocked_item(path, f"missing_{flag}", f"{flag} must be explicitly present and false"))
                elif value.get(flag) is not False:
                    blockers.append(blocked_item(path, f"{flag}_not_false", f"{flag} must be false"))
        for key, item in value.items():
            blockers.extend(runtime_flag_blockers(item, path=f"{path}.{key}", require_explicit=False))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            blockers.extend(runtime_flag_blockers(item, path=f"{path}[{index}]", require_explicit=False))
    return blockers


def digest_blockers(value: Any, *, path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if isinstance(value, dict):
        declarations = value.get("digest_declarations")
        if declarations is not None and not isinstance(declarations, list):
            return [blocked_item(path, "digest_declarations_not_list", "digest_declarations must be a list")]
        if isinstance(declarations, list):
            for index, entry in enumerate(declarations):
                entry_path = f"{path}.digest_declarations[{index}]"
                if not isinstance(entry, dict):
                    blockers.append(blocked_item(entry_path, "digest_declaration_not_object", "digest declaration must be an object"))
                    continue
                digest_name = str(entry.get("digest_name") or entry.get("name") or "")
                covered = entry.get("covered_fields", [])
                if not isinstance(covered, list) or not all(is_non_empty_string(item) for item in covered):
                    blockers.append(blocked_item(entry_path, "digest_covered_fields_invalid", "covered_fields must be non-empty strings"))
                    continue
                if "graph" in digest_name or "content" in digest_name or "boundary" in digest_name:
                    missing = [field for field in BOUNDARY_CRITICAL_DIGEST_FIELDS if field not in covered]
                    if missing:
                        blockers.append(
                            blocked_item(
                                entry_path,
                                "boundary_critical_digest_fields_omitted",
                                "graph/content digest must cover boundary-critical fields: " + ",".join(missing),
                            )
                        )
    return blockers


def schema_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if payload.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("fixture", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if payload.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("fixture", "actual_30d_readiness_status_not_data_not_matured", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if payload.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("fixture", "actual_30d_next_check_after_mismatch", "actual 30D next_check_after must remain 2026-07-21T00:00:00Z"))
    if payload.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        blockers.append(blocked_item("fixture", "direct_llm_interpretation_mismatch", "direct_llm_interpretation must be direct_llm_parametric_memory_control"))
    return blockers


def choose_status(
    *,
    artifact_blockers: list[dict[str, Any]],
    digest_blockers_: list[dict[str, Any]],
    runtime_blockers: list[dict[str, Any]],
    overclaim_blockers: list[dict[str, Any]],
    schema_blockers_: list[dict[str, Any]],
) -> str:
    if artifact_blockers:
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if digest_blockers_:
        return STATUS_BLOCKED_DIGEST_BOUNDARY
    if runtime_blockers:
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if overclaim_blockers:
        return STATUS_BLOCKED_OVERCLAIM
    if schema_blockers_:
        return STATUS_BLOCKED_SCHEMA
    return STATUS_READY


def base_summary(*, config: RegressionConfig, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "regression_run_id": config.regression_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "regression_status": status,
        "scan_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_mode": "fixture" if config.fixture else ("tracked_scan" if config.tracked_scan else "files"),
        "scanned_file_count": 0,
        "checked_payload_count": 0,
        "negative_test_context_count": 0,
        "skipped_forbidden_file_count": 0,
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "digest_boundary_status": "clean",
        "schema_boundary_status": "clean",
        "artifact_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "runtime_blocker_count": 0,
        "digest_blocker_count": 0,
        "schema_blocker_count": 0,
        "status_like_blocker_count": 0,
        "direct_llm_blocker_count": 0,
        "blocker_reasons": [],
        "blocked_items": [],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "non_claims": {
            "not_actual_30d_verdict": True,
            "not_oos_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_provider_run": True,
        },
    }


def build_summary(config: RegressionConfig) -> dict[str, Any]:
    validate_run_id(config.regression_run_id)
    run_root = config.output_dir / config.regression_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config=config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["schema_blocker_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    artifact_blockers: list[dict[str, Any]] = []
    overclaim_blockers: list[dict[str, Any]] = []
    runtime_blockers: list[dict[str, Any]] = []
    digest_blockers_: list[dict[str, Any]] = []
    schema_blockers_: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    checked_payload_count = 0
    negative_context_count = 0
    skipped_forbidden = 0

    if config.fixture:
        payload, fixture_entries_, fixture_schema_blockers = fixture_entries(config.fixture)
        schema_blockers_.extend(fixture_schema_blockers)
        if payload:
            schema_blockers_.extend(schema_blockers(payload))
            runtime_blockers.extend(runtime_flag_blockers(payload, path="fixture", require_explicit=True))
            artifact_blockers.extend(path_blockers(payload, path=normalize_path(config.fixture)))
            digest_blockers_.extend(digest_blockers(payload, path=normalize_path(config.fixture)))
            entries.extend(fixture_entries_)
            checked_payload_count += 1

    file_entries, file_artifacts, skipped_file_count = collect_file_entries(config)
    entries.extend(file_entries)
    artifact_blockers.extend(file_artifacts)
    skipped_forbidden += skipped_file_count

    for index, entry in enumerate(entries):
        entry_path = normalize_path(entry.get("path") or f"entry[{index}]")
        explicit_negative = bool(entry.get("negative_test_context"))
        negative_context = is_negative_context(
            entry_path,
            explicit=explicit_negative,
            allow_patterns=config.allow_negative_test_paths,
        )
        if negative_context:
            negative_context_count += 1
        if claim_scan.forbidden_path(entry_path):
            artifact_blockers.append(blocked_item(entry_path, "forbidden_entry_path", "entry path is forbidden; content was not read"))
            skipped_forbidden += 1
            continue
        payload = entry.get("payload")
        if payload is not None:
            if not isinstance(payload, dict):
                schema_blockers_.append(blocked_item(entry_path, "payload_not_object", "payload must be an object"))
            else:
                checked_payload_count += 1
                if not negative_context:
                    artifact_blockers.extend(path_blockers(payload, path=entry_path))
                    overclaim_blockers.extend(claim_blockers(payload, path=entry_path))
                runtime_blockers.extend(
                    runtime_flag_blockers(
                        payload,
                        path=entry_path,
                        require_explicit=bool(entry.get("require_boundary_flags", True)),
                    )
                )
                digest_blockers_.extend(digest_blockers(payload, path=entry_path))
        text = entry.get("text")
        if is_non_empty_string(text) and not negative_context:
            source = claim_scan.ScanSource(path=entry_path, text=str(text), origin="v3_7h_text")
            scan = claim_scan.scan_sources([source])
            overclaim_blockers.extend(
                scan["overclaim"]
                + scan["direct_llm"]
                + scan["maturity_gate"]
                + scan["short_horizon_as_30d"]
                + extra_text_blockers([source])
            )

    status = choose_status(
        artifact_blockers=artifact_blockers,
        digest_blockers_=digest_blockers_,
        runtime_blockers=runtime_blockers,
        overclaim_blockers=overclaim_blockers,
        schema_blockers_=schema_blockers_,
    )
    run_root.mkdir(parents=True, exist_ok=True)
    summary = base_summary(config=config, run_root=run_root, status=status)
    blocked_items = artifact_blockers + digest_blockers_ + runtime_blockers + overclaim_blockers + schema_blockers_
    summary.update(
        {
            "regression_status": status,
            "scanned_file_count": len([entry for entry in entries if entry.get("text")]),
            "checked_payload_count": checked_payload_count,
            "negative_test_context_count": negative_context_count,
            "skipped_forbidden_file_count": skipped_forbidden,
            "artifact_boundary_status": "blocked" if artifact_blockers else "clean",
            "claim_boundary_status": "blocked" if overclaim_blockers else "clean",
            "runtime_boundary_status": "blocked" if runtime_blockers else "clean",
            "digest_boundary_status": "blocked" if digest_blockers_ else "clean",
            "schema_boundary_status": "blocked" if schema_blockers_ else "clean",
            "artifact_blocker_count": len(artifact_blockers),
            "overclaim_blocker_count": len(overclaim_blockers),
            "runtime_blocker_count": len(runtime_blockers),
            "digest_blocker_count": len(digest_blockers_),
            "schema_blocker_count": len(schema_blockers_),
            "status_like_blocker_count": sum(1 for item in overclaim_blockers if "status" in str(item.get("rule_id", ""))),
            "direct_llm_blocker_count": sum(1 for item in overclaim_blockers if "direct_llm" in str(item.get("rule_id", ""))),
            "blocker_reasons": [str(item["rule_id"]) for item in blocked_items],
            "blocked_items": blocked_items[:100],
        }
    )
    write_outputs(config, summary, run_root=run_root)
    return summary


def write_outputs(config: RegressionConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "regression_run_id": config.regression_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "regression_status": summary.get("regression_status"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regression-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7h_claim_boundary_regression/runs"))
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--tracked-scan", action="store_true")
    parser.add_argument("--pathspec", action="append", default=[])
    parser.add_argument("--allow-negative-test-path", action="append", default=[])
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RegressionConfig:
    return RegressionConfig(
        regression_run_id=str(args.regression_run_id),
        output_dir=args.output_dir,
        fixture=args.fixture,
        files=tuple(args.file or ()),
        repo_root=args.repo_root,
        tracked_scan=bool(args.tracked_scan),
        pathspecs=tuple(args.pathspec or ()),
        allow_negative_test_paths=tuple(args.allow_negative_test_path or ()),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed with redacted stderr.
        print(f"claim-boundary regression failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("regression_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
