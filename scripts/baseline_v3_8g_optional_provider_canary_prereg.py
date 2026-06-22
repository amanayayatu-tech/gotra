#!/usr/bin/env python3
"""GOTRA v3.8G optional bounded provider canary prereg validator."""

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
from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as packet_canary  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_8g.optional_provider_canary_prereg_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8g.optional_provider_canary_prereg_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8g_optional_provider_canary_prereg_"
SCRIPT_VERSION = "v3.8g-20260622"
EVIDENCE_LAYER = "engineering_internal_provider_canary_prereg_only"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_ALLOWED_BACKEND_FAMILY = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_MAX_CALLS = 3
HARD_MAX_CALLS = 5
DEFAULT_MAX_TOKENS = 25_000
HARD_MAX_TOKENS = 100_000

STATUS_READY = "PROVIDER_CANARY_PREREG_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_AUTHORIZATION_BOUNDARY = "BLOCKED_AUTHORIZATION_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_OVERCLAIM,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_AUTHORIZATION_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}
FUTURE_CANARY_ALLOWED_STATUSES = [
    "PROVIDER_CANARY_READY_TO_RUN_AFTER_AUTHORIZATION",
    "PROVIDER_CANARY_COMPLETED_WITH_METADATA",
    "BLOCKED_METADATA",
    "BLOCKED_RUNTIME_BOUNDARY",
    "BLOCKED_AUTHORIZATION_BOUNDARY",
    "BLOCKED_ARTIFACT_BOUNDARY",
    "BLOCKED_OVERCLAIM",
]
LEGACY_BACKEND_RE = re.compile(r"(?:ki" + "mi|g" + "lm|deep" + "seek)", re.IGNORECASE)
SECRET_RE = packet_canary.SECRET_RE
DIRECT_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DIRECT_INTERPRETATION_KEY = "direct" + "_llm_interpretation"
VERDICT_WORD = "verd" + "ict"
COMPARATIVE_RESULT_WORD = "win" + "ner"
STATUS_CLAIM_RE = re.compile(
    rf"(?:provider canary|benchmark|v3[\._]?7|v3[\._]?8|30d|actual).{{0,72}}"
    rf"(?:executed|completed|ready|pass|{VERDICT_WORD}|{COMPARATIVE_RESULT_WORD})",
    re.IGNORECASE,
)
COMPARATIVE_CLAIM_RE = re.compile(
    rf"\b(?:{COMPARATIVE_RESULT_WORD}|out" + r"perform|pro" + r"fit|al" + r"pha|trading adv" + r"ice|investment adv" + r"ice)\b",
    re.IGNORECASE,
)

RUNTIME_FALSE_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "actual_30d_verdict_executed",
    "provider_canary_executed",
    "actual_outcome_used",
    "comparison_result_emitted",
)
REQUIRED_FIELDS = {
    "schema",
    "script_version",
    "prereg_id",
    "generated_at",
    "prereg_status",
    "evidence_layer",
    "allowed_backend_family",
    "allowed_model",
    "explicit_user_authorization_required",
    "next_step_requires_user_authorization",
    "future_user_authorization_present",
    "provider_family_explicitly_authorized_by_user",
    "max_calls",
    "hard_max_calls",
    "max_tokens",
    "hard_max_tokens",
    "max_cost_usd_optional",
    "raw_tmp_only",
    "no_raw_repo",
    "allowed_statuses",
    "runtime_flags",
    "actual_30d_readiness_status",
    "actual_30d_next_check_after",
    "non_claims",
    "can_say",
    "cannot_say",
    "stop_conditions",
    "required_metadata",
    "artifact_boundary",
    "blocker_reasons",
    "blocked_items",
    DIRECT_INTERPRETATION_KEY,
}
REQUIRED_METADATA_FIELDS = {
    "backend_name",
    "model",
    "call_count",
    "token_usage_total",
    "usage_metadata",
    "latency_ms",
    "prompt_hash",
    "input_fixture_hash",
    "raw_tmp_path",
    "raw_tmp_sha256",
    "summary_status",
}


@dataclass(frozen=True)
class PreregConfig:
    prereg_id: str
    output_dir: Path
    allow_overwrite: bool = False
    prereg_fixture: Path | None = None


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"prereg_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("prereg_id may contain only letters, numbers, '_' and '-'")


def stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_sha256_json(payload: Any) -> str:
    return sha256_bytes(stable_json_bytes(payload))


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


def under_tmp(path: str | Path) -> bool:
    try:
        resolved = Path(path).expanduser().resolve()
        tmp = Path("/tmp").resolve()
        return resolved == tmp or tmp in resolved.parents
    except OSError:
        return False


def contains_secret(value: Any) -> bool:
    return bool(SECRET_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)))


def recursive_strings(value: Any, *, path: str) -> list[tuple[str, str]]:
    strings: list[tuple[str, str]] = []
    if isinstance(value, str):
        strings.append((path, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            strings.extend(recursive_strings(item, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            strings.extend(recursive_strings(item, path=f"{path}[{index}]"))
    return strings


def path_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path, text in recursive_strings(payload, path="prereg"):
        if claim_scan.forbidden_path(text):
            blockers.append(blocked_item(path, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
    artifact_boundary = payload.get("artifact_boundary")
    if isinstance(artifact_boundary, dict):
        for key in ("raw_output_root", "allowed_raw_output_root"):
            value = artifact_boundary.get(key)
            if isinstance(value, str) and not under_tmp(value):
                blockers.append(blocked_item(f"prereg.artifact_boundary.{key}", "raw_output_root_not_tmp", "raw output root must stay under /tmp"))
    return blockers


def claim_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = [
        claim_scan.ScanSource(path=path, text=text, origin="v3_8g_provider_canary_prereg")
        for path, text in recursive_strings(payload, path="prereg")
    ]
    scan = claim_scan.scan_sources(sources)
    direct_key = "direct" + "_llm"
    blockers = scan["overclaim"] + scan[direct_key] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for path, text in recursive_strings(payload, path="prereg"):
        if STATUS_CLAIM_RE.search(text) and not claim_regression.FALSE_LINE_RE.search(text):
            blockers.append(blocked_item(path, "provider_canary_or_verdict_claim", "prereg text cannot claim canary execution, benchmark, or actual verdict readiness"))
        match = COMPARATIVE_CLAIM_RE.search(text)
        if match and not claim_scan.is_negated(text, match.start()):
            blockers.append(blocked_item(path, "comparative_or_advice_claim", "comparative or advice wording exceeds prereg boundary"))
    return blockers


def base_summary(config: PreregConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "prereg_id": config.prereg_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "prereg_status": status,
        "evidence_layer": EVIDENCE_LAYER,
        "allowed_backend_family": DEFAULT_ALLOWED_BACKEND_FAMILY,
        "allowed_model": DEFAULT_MODEL,
        "explicit_user_authorization_required": True,
        "next_step_requires_user_authorization": True,
        "future_user_authorization_present": False,
        "provider_family_explicitly_authorized_by_user": False,
        "old_provider_family_allowed": False,
        "max_calls": DEFAULT_MAX_CALLS,
        "hard_max_calls": HARD_MAX_CALLS,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "hard_max_tokens": HARD_MAX_TOKENS,
        "max_cost_usd_optional": None,
        "raw_tmp_only": True,
        "no_raw_repo": True,
        "allowed_statuses": list(FUTURE_CANARY_ALLOWED_STATUSES),
        "runtime_flags": {flag: False for flag in RUNTIME_FALSE_FLAGS},
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_verdict_executed": False,
        "provider_canary_executed": False,
        "actual_outcome_used": False,
        "comparison_result_emitted": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "non_claims": {
            "not_provider_canary_execution": True,
            "not_provider_benchmark": True,
            "not_actual_30d_verdict": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
        "can_say": [
            "future optional bounded provider canary prereg/runbook/schema is locally validated",
        ],
        "cannot_say": [
            "not provider canary execution",
            "not provider benchmark",
            "not model-comparison result",
            "actual 30D execution is false",
            "not OOS/science/public/trading claim",
            "not investment advice",
            "not readiness gate passed",
        ],
        "stop_conditions": [
            "missing explicit future user authorization",
            "usage metadata missing",
            "raw output path outside /tmp",
            "token or call budget exceeded",
            "claim-boundary blocker",
            "artifact-boundary blocker",
            "future-data metadata violation",
            "actual 30D maturity gate remains unavailable in this prereg-only stage",
        ],
        "required_metadata": sorted(REQUIRED_METADATA_FIELDS),
        "artifact_boundary": {
            "raw_tmp_only": True,
            "no_raw_repo": True,
            "allowed_raw_output_root": "/tmp",
        },
        "usage_metadata_required": True,
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        "blocked_items": [],
        "blocker_reasons": [],
        "schema_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "authorization_boundary_status": "clean",
        "artifact_boundary_status": "clean",
    }


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(blocked_item("summary.schema", "summary_schema_mismatch", f"schema must be {SUMMARY_SCHEMA}"))
    if summary.get("prereg_status") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.prereg_status", "invalid_prereg_status", "prereg_status is not allowed"))
    missing = sorted(REQUIRED_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("summary.actual_30d_next_check_after", "actual_30d_next_check_after_mismatch", "next_check_after must remain fixed"))
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_INTERPRETATION_KEY + "_mismatch", "parametric memory interpretation must remain explicit"))
    allowed_family = str(summary.get("allowed_backend_family") or "")
    if not allowed_family:
        blockers.append(blocked_item("summary.allowed_backend_family", "allowed_backend_family_missing", "backend family is required"))
    if LEGACY_BACKEND_RE.search(allowed_family) and summary.get("provider_family_explicitly_authorized_by_user") is not True:
        blockers.append(blocked_item("summary.allowed_backend_family", "legacy_provider_without_future_user_authorization", "legacy provider family needs separate explicit future authorization"))
    if not LEGACY_BACKEND_RE.search(allowed_family) and allowed_family != DEFAULT_ALLOWED_BACKEND_FAMILY:
        blockers.append(blocked_item("summary.allowed_backend_family", "allowed_backend_family_not_current", "default prereg backend family must be current allowed backend"))
    if summary.get("allowed_model") != DEFAULT_MODEL:
        blockers.append(blocked_item("summary.allowed_model", "allowed_model_mismatch", "model must match current bounded prereg default"))
    for key, hard in (("max_calls", HARD_MAX_CALLS), ("hard_max_calls", HARD_MAX_CALLS), ("max_tokens", DEFAULT_MAX_TOKENS)):
        value = summary.get(key)
        if not isinstance(value, int) or value < 1:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be positive integer"))
        elif value > hard:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_over_cap", f"{key} exceeds current cap"))
    hard_tokens = summary.get("hard_max_tokens")
    if not isinstance(hard_tokens, int) or hard_tokens < DEFAULT_MAX_TOKENS or hard_tokens > HARD_MAX_TOKENS:
        blockers.append(blocked_item("summary.hard_max_tokens", "hard_max_tokens_invalid", "hard token ceiling must be within prereg bounds"))
    if summary.get("allowed_statuses") != FUTURE_CANARY_ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.allowed_statuses", "allowed_statuses_mismatch", "allowed statuses must match prereg contract"))
    if not isinstance(summary.get("required_metadata"), list) or set(summary.get("required_metadata") or []) != REQUIRED_METADATA_FIELDS:
        blockers.append(blocked_item("summary.required_metadata", "required_metadata_mismatch", "required metadata set must be complete"))
    if not isinstance(summary.get("stop_conditions"), list) or not summary.get("stop_conditions"):
        blockers.append(blocked_item("summary.stop_conditions", "stop_conditions_missing", "stop conditions are required"))
    if not isinstance(summary.get("non_claims"), dict) or not all(summary.get("non_claims", {}).values()):
        blockers.append(blocked_item("summary.non_claims", "non_claims_invalid", "non_claim attestations must be true"))
    return blockers


def authorization_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for key in ("explicit_user_authorization_required", "next_step_requires_user_authorization"):
        if summary.get(key) is not True:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_not_true", f"{key} must be true"))
    if summary.get("future_user_authorization_present") is not False:
        blockers.append(blocked_item("summary.future_user_authorization_present", "future_user_authorization_present_not_false", "this prereg-only stage must not claim authorization is present"))
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    runtime_flags = summary.get("runtime_flags")
    if not isinstance(runtime_flags, dict):
        blockers.append(blocked_item("summary.runtime_flags", "runtime_flags_not_object", "runtime_flags must be object"))
        runtime_flags = {}
    for flag in RUNTIME_FALSE_FLAGS:
        top_value = summary.get(flag)
        runtime_value = runtime_flags.get(flag)
        if top_value is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false in prereg-only stage"))
        if runtime_value is not False:
            blockers.append(blocked_item(f"summary.runtime_flags.{flag}", f"runtime_{flag}_not_false", f"runtime flag {flag} must be false"))
    if summary.get("raw_tmp_only") is not True:
        blockers.append(blocked_item("summary.raw_tmp_only", "raw_tmp_only_not_true", "raw outputs must be /tmp only"))
    if summary.get("no_raw_repo") is not True:
        blockers.append(blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "repo must not receive raw outputs"))
    if summary.get("usage_metadata_required") is not True:
        blockers.append(blocked_item("summary.usage_metadata_required", "usage_metadata_required_not_true", "usage metadata must be required"))
    artifact_boundary = summary.get("artifact_boundary")
    if not isinstance(artifact_boundary, dict):
        blockers.append(blocked_item("summary.artifact_boundary", "artifact_boundary_not_object", "artifact boundary must be object"))
    else:
        if artifact_boundary.get("raw_tmp_only") is not True:
            blockers.append(blocked_item("summary.artifact_boundary.raw_tmp_only", "artifact_raw_tmp_only_not_true", "artifact boundary must require /tmp raw outputs"))
        if artifact_boundary.get("no_raw_repo") is not True:
            blockers.append(blocked_item("summary.artifact_boundary.no_raw_repo", "artifact_no_raw_repo_not_true", "artifact boundary must reject repo raw outputs"))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any("schema" in str(item.get("rule_id")) or "missing" in str(item.get("rule_id")) or "invalid" in str(item.get("rule_id")) or "mismatch" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any("claim" in str(item.get("rule_id")) or "overclaim" in str(item.get("rule_id")) or "direct" + "_llm" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any("runtime" in str(item.get("rule_id")) or "provider_or_backend_called" in str(item.get("rule_id")) or "formal_lite" in str(item.get("rule_id")) or "codex_cli" in str(item.get("rule_id")) or "raw_tmp_only" in str(item.get("rule_id")) or "usage_metadata" in str(item.get("rule_id")) or "output_dir" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["authorization_boundary_status"] = "blocked" if any("authorization" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any("artifact" in str(item.get("rule_id")) or "raw_output_root" in str(item.get("rule_id")) or "forbidden_artifact" in str(item.get("rule_id")) for item in blockers) else "clean"


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("forbidden_artifact" in reason or "raw_output_root" in reason or "artifact_" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("claim" in reason or "overclaim" in reason or "direct" + "_llm" in reason for reason in reasons):
        return STATUS_BLOCKED_OVERCLAIM
    if any("authorization" in reason or "legacy_provider" in reason for reason in reasons):
        return STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    if any("runtime" in reason or "provider_or_backend_called" in reason or "codex_cli" in reason or "formal_lite" in reason or "raw_tmp_only" in reason or "usage_metadata" in reason or "output_dir" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    return STATUS_BLOCKED_SCHEMA


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(schema_blockers(summary))
    blockers.extend(authorization_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(path_blockers(summary))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def load_prereg_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "fixture_path_forbidden", "prereg fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [blocked_item(path, "fixture_missing", "prereg fixture does not exist")]
    except json.JSONDecodeError:
        return {}, [blocked_item(path, "fixture_invalid_json", "prereg fixture is not valid JSON")]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "fixture_not_object", "prereg fixture must be JSON object")]
    return payload, []


def fixture_identity_blockers(payload: dict[str, Any], *, config: PreregConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "prereg_id": config.prereg_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def fixture_required_field_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    missing = sorted(REQUIRED_FIELDS - set(payload))
    return [blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing]


def restore_config_identity(summary: dict[str, Any], *, config: PreregConfig, run_root: Path) -> None:
    summary["prereg_id"] = config.prereg_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: PreregConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_prereg_fixture(config.prereg_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    required_field_blockers = fixture_required_field_blockers(payload) if payload else []
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("prereg_status") or STATUS_BLOCKED_SCHEMA) if payload else STATUS_BLOCKED_SCHEMA,
    )
    if payload:
        summary.update(payload)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + required_field_blockers + validate_summary_payload(summary)
    summary["prereg_status"] = choose_status(blockers, current_status=str(summary.get("prereg_status") or ""))
    finalize_blockers(summary, blockers)
    return summary


def build_default_summary(config: PreregConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    summary["prereg_status"] = choose_status(blockers, current_status=STATUS_READY)
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: PreregConfig) -> dict[str, Any]:
    validate_run_id(config.prereg_id)
    run_root = config.output_dir / config.prereg_id
    if not under_tmp(run_root):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_dir_not_tmp", "prereg outputs must be under /tmp")]
        summary["prereg_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_run_id_exists", "output run id exists")]
        summary["prereg_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if config.prereg_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    else:
        summary = build_default_summary(config, run_root=run_root)
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary["content_boundary_sha256"] = stable_sha256_json(
        {
            "allowed_backend_family": summary.get("allowed_backend_family"),
            "allowed_model": summary.get("allowed_model"),
            "authorization": {
                "explicit_user_authorization_required": summary.get("explicit_user_authorization_required"),
                "next_step_requires_user_authorization": summary.get("next_step_requires_user_authorization"),
                "future_user_authorization_present": summary.get("future_user_authorization_present"),
            },
            "budgets": {
                "max_calls": summary.get("max_calls"),
                "max_tokens": summary.get("max_tokens"),
                "hard_max_calls": summary.get("hard_max_calls"),
                "hard_max_tokens": summary.get("hard_max_tokens"),
            },
            "runtime_flags": summary.get("runtime_flags"),
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "actual_30d_next_check_after": summary.get("actual_30d_next_check_after"),
            "artifact_boundary": summary.get("artifact_boundary"),
            "evidence_layer": summary.get("evidence_layer"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "prereg_id": summary.get("prereg_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "content_boundary_sha256": summary.get("content_boundary_sha256"),
        "prereg_status": summary.get("prereg_status"),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8g_optional_provider_canary_prereg/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--prereg-fixture", type=Path)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PreregConfig:
    return PreregConfig(
        prereg_id=str(args.prereg_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        prereg_fixture=args.prereg_fixture,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(config_from_args(args))
    except ValueError as exc:
        print(json.dumps({"prereg_status": STATUS_BLOCKED_SCHEMA, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("prereg_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
