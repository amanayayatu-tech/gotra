#!/usr/bin/env python3
"""GOTRA v3.8H provider canary authorization gate / execution guard."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_8h.provider_canary_authorization_gate_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8h.provider_canary_authorization_gate_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8h_provider_canary_authorization_gate_"
SCRIPT_VERSION = "v3.8h-20260622"
EVIDENCE_LAYER = "engineering_internal_provider_canary_authorization_gate"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_BACKEND_FAMILY = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_MAX_CALLS = 3
HARD_MAX_CALLS = 5
DEFAULT_MAX_TOKENS = 25_000
HARD_MAX_TOKENS = 100_000

STATUS_READY = "PROVIDER_CANARY_AUTHORIZATION_GATE_READY"
STATUS_BLOCKED_AUTHORIZATION_BOUNDARY = "BLOCKED_AUTHORIZATION_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_METADATA = "BLOCKED_METADATA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_AUTHORIZATION_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_METADATA,
    STATUS_BLOCKED_OVERCLAIM,
    STATUS_BLOCKED_SCHEMA,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}
LEGACY_BACKEND_RE = re.compile(r"(?:ki" + "mi|g" + "lm|deep" + "seek)", re.IGNORECASE)
SECRET_RE = packet_canary.SECRET_RE
DIRECT_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DIRECT_INTERPRETATION_KEY = "direct" + "_llm_interpretation"
VERDICT_WORD = "verd" + "ict"
COMPARATIVE_RESULT_WORD = "win" + "ner"
STATUS_CLAIM_RE = re.compile(
    rf"(?:provider canary|benchmark|v3[\._]?7|v3[\._]?8|30d|actual).{{0,72}}"
    rf"(?:executed|completed|ready|pass|allowed|executable|{VERDICT_WORD}|{COMPARATIVE_RESULT_WORD})",
    re.IGNORECASE,
)
COMPARATIVE_CLAIM_RE = re.compile(
    rf"\b(?:{COMPARATIVE_RESULT_WORD}|out" + r"perform|pro" + r"fit|al" + r"pha|trading adv" + r"ice|investment adv" + r"ice)\b",
    re.IGNORECASE,
)

RUNTIME_FALSE_FLAGS = (
    "provider_or_backend_called",
    "provider_canary_executed",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "actual_30d_verdict_executed",
)
AUTHORIZATION_REQUIRED_FIELDS = {
    "user_authorization_present",
    "authorization_id",
    "authorized_at",
    "provider_family",
    "backend",
    "model",
    "max_calls",
    "max_tokens",
    "raw_tmp_only",
    "no_raw_repo",
    "usage_metadata_required",
}
REQUIRED_FIELDS = {
    "schema",
    "script_version",
    "gate_run_id",
    "generated_at",
    "gate_status",
    "evidence_layer",
    "authorization_packet",
    "observed_provider_or_backend_called",
    "observed_provider_canary_executed",
    "observed_backend_family",
    "observed_backend",
    "observed_model",
    "observed_call_count",
    "observed_token_usage_total",
    "observed_calls",
    "max_calls",
    "hard_max_calls",
    "max_tokens",
    "hard_max_tokens",
    "raw_tmp_only",
    "no_raw_repo",
    "usage_metadata_required",
    "raw_tmp_paths",
    "changed_files",
    "runtime_flags",
    "actual_30d_readiness_status",
    "next_check_after",
    "non_claims",
    "can_say",
    "cannot_say",
    "blocker_reasons",
    "blocked_items",
    DIRECT_INTERPRETATION_KEY,
}


@dataclass(frozen=True)
class GateConfig:
    gate_run_id: str
    output_dir: Path
    allow_overwrite: bool = False
    summary_fixture: Path | None = None
    files: tuple[Path, ...] = ()
    repo_root: Path = REPO_ROOT


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"gate_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("gate_run_id may contain only letters, numbers, '_' and '-'")


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


def is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def provider_called(summary: dict[str, Any]) -> bool:
    observed_count = summary.get("observed_call_count")
    return (
        summary.get("provider_or_backend_called") is True
        or summary.get("provider_canary_executed") is True
        or summary.get("observed_provider_or_backend_called") is True
        or summary.get("observed_provider_canary_executed") is True
        or (isinstance(observed_count, int) and not isinstance(observed_count, bool) and observed_count > 0)
    )


def read_json_object(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "fixture_path_forbidden", "fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [blocked_item(path, "fixture_missing", "fixture does not exist")]
    except json.JSONDecodeError:
        return {}, [blocked_item(path, "fixture_invalid_json", "fixture is not valid JSON")]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "fixture_not_object", "fixture must be JSON object")]
    return payload, []


def read_file_sources(config: GateConfig) -> tuple[list[claim_scan.ScanSource], list[dict[str, Any]], int]:
    sources: list[claim_scan.ScanSource] = []
    blockers: list[dict[str, Any]] = []
    checked_count = 0
    for path in sorted(set(config.files)):
        normalized = normalize_path(path)
        if claim_scan.forbidden_path(normalized):
            blockers.append(blocked_item(normalized, "forbidden_file_path", "file path is forbidden; content was not read"))
            continue
        absolute = path if path.is_absolute() else config.repo_root / path
        if not absolute.exists():
            blockers.append(blocked_item(normalized, "file_missing", "listed file does not exist"))
            continue
        if not absolute.is_file():
            blockers.append(blocked_item(normalized, "file_not_regular", "listed file is not a regular file"))
            continue
        text = absolute.read_text(encoding="utf-8")
        checked_count += 1
        sources.append(claim_scan.ScanSource(path=normalized, text=text, origin="v3_8h_file"))
    return sources, blockers, checked_count


def base_summary(config: GateConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "gate_run_id": config.gate_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "gate_status": status,
        "evidence_layer": EVIDENCE_LAYER,
        "authorization_packet": None,
        "observed_provider_or_backend_called": False,
        "observed_provider_canary_executed": False,
        "observed_backend_family": DEFAULT_BACKEND_FAMILY,
        "observed_backend": DEFAULT_BACKEND_FAMILY,
        "observed_model": DEFAULT_MODEL,
        "observed_call_count": 0,
        "observed_token_usage_total": 0,
        "observed_calls": [],
        "max_calls": DEFAULT_MAX_CALLS,
        "hard_max_calls": HARD_MAX_CALLS,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "hard_max_tokens": HARD_MAX_TOKENS,
        "raw_tmp_only": True,
        "no_raw_repo": True,
        "usage_metadata_required": True,
        "raw_tmp_paths": [],
        "changed_files": [],
        "checked_file_count": 0,
        "runtime_flags": {flag: False for flag in RUNTIME_FALSE_FLAGS},
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_verdict_executed": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        "non_claims": {
            "not_provider_canary_execution": True,
            "not_provider_benchmark": True,
            "not_actual_30d_verdict": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
        "can_say": [
            "provider canary authorization gate is locally validated",
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
        "blocked_items": [],
        "blocker_reasons": [],
        "schema_status": "clean",
        "authorization_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "metadata_status": "clean",
        "claim_boundary_status": "clean",
    }


def schema_blockers(summary: dict[str, Any], *, fixture_payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(blocked_item("summary.schema", "summary_schema_mismatch", f"schema must be {SUMMARY_SCHEMA}"))
    if summary.get("gate_status") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.gate_status", "gate_status_invalid", "gate_status is not allowed"))
    missing = sorted(REQUIRED_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if fixture_payload is not None:
        fixture_missing = sorted((REQUIRED_FIELDS - {"gate_run_id"}) - set(fixture_payload))
        blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in fixture_missing)
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("summary.next_check_after", "next_check_after_mismatch", "next_check_after must remain fixed"))
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_INTERPRETATION_KEY + "_mismatch", "parametric memory interpretation must remain explicit"))
    for key, cap in (("max_calls", HARD_MAX_CALLS), ("hard_max_calls", HARD_MAX_CALLS), ("max_tokens", DEFAULT_MAX_TOKENS)):
        value = summary.get(key)
        if not is_positive_int(value):
            blockers.append(blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be positive integer"))
        elif value > cap:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_over_cap", f"{key} exceeds allowed cap"))
    hard_tokens = summary.get("hard_max_tokens")
    if not is_positive_int(hard_tokens) or hard_tokens < DEFAULT_MAX_TOKENS or hard_tokens > HARD_MAX_TOKENS:
        blockers.append(blocked_item("summary.hard_max_tokens", "hard_max_tokens_invalid", "hard token ceiling must be within guard bounds"))
    for key in ("observed_call_count", "observed_token_usage_total"):
        if not non_negative_int(summary.get(key)):
            blockers.append(blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be non-negative integer"))
    if not isinstance(summary.get("observed_calls"), list):
        blockers.append(blocked_item("summary.observed_calls", "observed_calls_not_list", "observed_calls must be a list"))
    if not isinstance(summary.get("changed_files"), list):
        blockers.append(blocked_item("summary.changed_files", "changed_files_not_list", "changed_files must be a list"))
    if not isinstance(summary.get("raw_tmp_paths"), list):
        blockers.append(blocked_item("summary.raw_tmp_paths", "raw_tmp_paths_not_list", "raw_tmp_paths must be a list"))
    if not isinstance(summary.get("non_claims"), dict) or not all(summary.get("non_claims", {}).values()):
        blockers.append(blocked_item("summary.non_claims", "non_claims_invalid", "non-claim attestations must be true"))
    return blockers


def authorization_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    auth = summary.get("authorization_packet")
    has_auth = isinstance(auth, dict)
    if provider_called(summary) and not has_auth:
        blockers.append(blocked_item("summary.authorization_packet", "provider_execution_without_authorization_packet", "provider execution requires separate authorization packet"))
    if not has_auth:
        return blockers
    missing = sorted(AUTHORIZATION_REQUIRED_FIELDS - set(auth))
    blockers.extend(blocked_item(f"summary.authorization_packet.{key}", "authorization_missing_field", f"{key} is required") for key in missing)
    if auth.get("user_authorization_present") is not True:
        blockers.append(blocked_item("summary.authorization_packet.user_authorization_present", "user_authorization_not_present", "future execution requires explicit user authorization"))
    for key in ("authorization_id", "authorized_at", "provider_family", "backend", "model"):
        if not isinstance(auth.get(key), str) or not auth.get(key, "").strip():
            blockers.append(blocked_item(f"summary.authorization_packet.{key}", f"authorization_{key}_invalid", f"{key} must be non-empty string"))
    provider_family = str(auth.get("provider_family") or "")
    observed_family = str(summary.get("observed_backend_family") or "")
    observed_backend = str(summary.get("observed_backend") or "")
    if provider_called(summary):
        if provider_family and observed_family and provider_family != observed_family:
            blockers.append(blocked_item("summary.authorization_packet.provider_family", "authorization_provider_family_mismatch", "authorization provider family must bind observed family"))
        if auth.get("backend") and observed_backend and auth.get("backend") != observed_backend:
            blockers.append(blocked_item("summary.authorization_packet.backend", "authorization_backend_mismatch", "authorization backend must bind observed backend"))
        if auth.get("model") and summary.get("observed_model") and auth.get("model") != summary.get("observed_model"):
            blockers.append(blocked_item("summary.authorization_packet.model", "authorization_model_mismatch", "authorization model must bind observed model"))
    if LEGACY_BACKEND_RE.search(provider_family + " " + observed_family + " " + observed_backend):
        if auth.get("legacy_provider_explicitly_named") is not True:
            blockers.append(blocked_item("summary.authorization_packet.legacy_provider_explicitly_named", "legacy_provider_without_explicit_named_authorization", "legacy provider needs explicit named future authorization"))
    for key, cap in (("max_calls", HARD_MAX_CALLS), ("max_tokens", DEFAULT_MAX_TOKENS)):
        value = auth.get(key)
        if not is_positive_int(value):
            blockers.append(blocked_item(f"summary.authorization_packet.{key}", f"authorization_{key}_invalid", f"{key} must be positive integer"))
        elif value > cap:
            blockers.append(blocked_item(f"summary.authorization_packet.{key}", f"authorization_{key}_over_cap", f"{key} exceeds guard cap"))
    for key in ("raw_tmp_only", "no_raw_repo", "usage_metadata_required"):
        if auth.get(key) is not True:
            blockers.append(blocked_item(f"summary.authorization_packet.{key}", f"authorization_{key}_not_true", f"{key} must be true"))
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    runtime_flags = summary.get("runtime_flags")
    if not isinstance(runtime_flags, dict):
        blockers.append(blocked_item("summary.runtime_flags", "runtime_flags_not_object", "runtime_flags must be object"))
        runtime_flags = {}
    for flag in RUNTIME_FALSE_FLAGS:
        if summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8H itself"))
        if runtime_flags.get(flag) is not False:
            blockers.append(blocked_item(f"summary.runtime_flags.{flag}", f"runtime_{flag}_not_false", f"runtime flag {flag} must be false"))
    if summary.get("raw_tmp_only") is not True:
        blockers.append(blocked_item("summary.raw_tmp_only", "raw_tmp_only_not_true", "raw output boundary must be /tmp only"))
    if summary.get("no_raw_repo") is not True:
        blockers.append(blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "repo raw outputs must remain disallowed"))
    if summary.get("usage_metadata_required") is not True:
        blockers.append(blocked_item("summary.usage_metadata_required", "usage_metadata_required_not_true", "usage metadata must be required"))
    if LEGACY_BACKEND_RE.search(str(summary.get("observed_backend_family") or "") + " " + str(summary.get("observed_backend") or "")) and not isinstance(summary.get("authorization_packet"), dict):
        blockers.append(blocked_item("summary.observed_backend_family", "legacy_provider_without_authorization_packet", "legacy provider reference requires explicit authorization packet"))
    observed_calls = summary.get("observed_calls") if isinstance(summary.get("observed_calls"), list) else []
    observed_total = 0
    observed_tokens = 0
    for index, call in enumerate(observed_calls):
        if not isinstance(call, dict):
            blockers.append(blocked_item(f"summary.observed_calls[{index}]", "observed_call_not_object", "observed call must be object"))
            continue
        count = call.get("call_count", 1)
        tokens = call.get("token_usage_total", 0)
        if not non_negative_int(count):
            blockers.append(blocked_item(f"summary.observed_calls[{index}].call_count", "observed_call_count_invalid", "call count must be non-negative integer"))
        else:
            observed_total += count
        if not non_negative_int(tokens):
            blockers.append(blocked_item(f"summary.observed_calls[{index}].token_usage_total", "observed_call_tokens_invalid", "token usage must be non-negative integer"))
        else:
            observed_tokens += tokens
    if observed_calls and non_negative_int(summary.get("observed_call_count")) and summary.get("observed_call_count") != observed_total:
        blockers.append(blocked_item("summary.observed_call_count", "observed_call_count_mismatch", "observed_call_count must match observed_calls aggregate"))
    if observed_calls and non_negative_int(summary.get("observed_token_usage_total")) and summary.get("observed_token_usage_total") != observed_tokens:
        blockers.append(blocked_item("summary.observed_token_usage_total", "observed_token_usage_total_mismatch", "observed token total must match observed_calls aggregate"))
    if non_negative_int(summary.get("observed_call_count")) and summary.get("observed_call_count", 0) > HARD_MAX_CALLS:
        blockers.append(blocked_item("summary.observed_call_count", "observed_call_count_over_cap", "observed call count exceeds hard cap"))
    if non_negative_int(summary.get("observed_token_usage_total")) and summary.get("observed_token_usage_total", 0) > DEFAULT_MAX_TOKENS:
        blockers.append(blocked_item("summary.observed_token_usage_total", "observed_token_usage_over_cap", "observed token usage exceeds default cap"))
    return blockers


def metadata_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not provider_called(summary):
        return blockers
    if summary.get("usage_metadata_required") is not True:
        blockers.append(blocked_item("summary.usage_metadata_required", "usage_metadata_required_not_true", "usage metadata must be required"))
    observed_calls = summary.get("observed_calls") if isinstance(summary.get("observed_calls"), list) else []
    if not observed_calls and int(summary.get("observed_call_count") or 0) > 0:
        blockers.append(blocked_item("summary.observed_calls", "observed_calls_missing_for_execution", "executed calls must include per-call metadata"))
    for index, call in enumerate(observed_calls):
        if not isinstance(call, dict):
            continue
        if call.get("usage_metadata_available") is not True:
            blockers.append(blocked_item(f"summary.observed_calls[{index}].usage_metadata_available", "usage_metadata_missing", "usage metadata must be available for every call"))
        if not is_positive_int(call.get("token_usage_total")):
            blockers.append(blocked_item(f"summary.observed_calls[{index}].token_usage_total", "token_usage_missing", "token usage must be positive for executed call"))
    return blockers


def path_blockers(summary: dict[str, Any], *, file_blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers = list(file_blockers)
    for path, text in recursive_strings(summary, path="summary"):
        if claim_scan.forbidden_path(text):
            blockers.append(blocked_item(path, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
    for key in ("raw_tmp_paths", "changed_files"):
        values = summary.get(key)
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if not isinstance(value, str):
                blockers.append(blocked_item(f"summary.{key}[{index}]", f"{key}_entry_not_string", f"{key} entries must be strings"))
                continue
            if key == "raw_tmp_paths" and not under_tmp(value):
                blockers.append(blocked_item(f"summary.{key}[{index}]", "raw_tmp_path_not_tmp", "raw paths must stay under /tmp"))
            if claim_scan.forbidden_path(value):
                blockers.append(blocked_item(f"summary.{key}[{index}]", "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
    observed_calls = summary.get("observed_calls") if isinstance(summary.get("observed_calls"), list) else []
    for index, call in enumerate(observed_calls):
        if isinstance(call, dict):
            raw_path = call.get("raw_tmp_path")
            if isinstance(raw_path, str) and not under_tmp(raw_path):
                blockers.append(blocked_item(f"summary.observed_calls[{index}].raw_tmp_path", "raw_tmp_path_not_tmp", "call raw path must stay under /tmp"))
    return blockers


def claim_blockers(summary: dict[str, Any], file_sources: list[claim_scan.ScanSource]) -> list[dict[str, Any]]:
    sources = [
        claim_scan.ScanSource(path=path, text=text, origin="v3_8h_authorization_gate")
        for path, text in recursive_strings(summary, path="summary")
    ]
    sources.extend(file_sources)
    scan = claim_scan.scan_sources(sources)
    direct_key = "direct" + "_llm"
    blockers = scan["overclaim"] + scan[direct_key] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for source in sources:
        if source.path.endswith("_path") or source.path.endswith("_paths") or source.path.endswith(".run_root"):
            continue
        if STATUS_CLAIM_RE.search(source.text) and not claim_regression.FALSE_LINE_RE.search(source.text):
            blockers.append(blocked_item(source.path, "provider_canary_or_verdict_claim", "text cannot claim canary execution, benchmark, or actual verdict readiness"))
        match = COMPARATIVE_CLAIM_RE.search(source.text)
        if match and not claim_scan.is_negated(source.text, match.start()):
            blockers.append(blocked_item(source.path, "comparative_or_advice_claim", "comparative or advice wording exceeds gate boundary"))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    reasons = " ".join(summary["blocker_reasons"])
    summary["schema_status"] = "blocked" if any(token in reasons for token in ("schema", "missing_field", "invalid", "mismatch", "not_list", "not_object")) else "clean"
    summary["authorization_boundary_status"] = "blocked" if "authorization" in reasons else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(token in reasons for token in ("runtime", "provider_or_backend_called", "provider_canary_executed", "codex_cli", "formal_lite", "raw_tmp_only", "no_raw_repo", "observed_call", "output_dir")) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(token in reasons for token in ("artifact", "raw_tmp_path", "forbidden_file_path")) else "clean"
    summary["metadata_status"] = "blocked" if "metadata" in reasons or "token_usage_missing" in reasons else "clean"
    summary["claim_boundary_status"] = "blocked" if any(token in reasons for token in ("claim", "overclaim", "direct" + "_llm", "verdict", "comparative")) else "clean"


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("artifact" in reason or "raw_tmp_path" in reason or "forbidden_file_path" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("claim" in reason or "overclaim" in reason or "direct" + "_llm" in reason or "verdict" in reason or "comparative" in reason for reason in reasons):
        return STATUS_BLOCKED_OVERCLAIM
    if any("authorization" in reason or "legacy_provider" in reason for reason in reasons):
        return STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    if any("metadata" in reason or "token_usage_missing" in reason for reason in reasons):
        return STATUS_BLOCKED_METADATA
    if any("runtime" in reason or "provider_or_backend_called" in reason or "provider_canary_executed" in reason or "codex_cli" in reason or "formal_lite" in reason or "raw_tmp_only" in reason or "no_raw_repo" in reason or "observed_call" in reason or "output_dir" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    return STATUS_BLOCKED_SCHEMA


def validate_summary_payload(
    summary: dict[str, Any],
    *,
    fixture_payload: dict[str, Any] | None,
    file_sources: list[claim_scan.ScanSource],
    file_blockers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(schema_blockers(summary, fixture_payload=fixture_payload))
    blockers.extend(authorization_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(metadata_blockers(summary))
    blockers.extend(path_blockers(summary, file_blockers=file_blockers))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary, file_sources))
    return blockers


def fixture_identity_blockers(payload: dict[str, Any], *, config: GateConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "gate_run_id": config.gate_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: GateConfig, run_root: Path) -> None:
    summary["gate_run_id"] = config.gate_run_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_summary(config: GateConfig) -> dict[str, Any]:
    validate_run_id(config.gate_run_id)
    run_root = config.output_dir / config.gate_run_id
    if not under_tmp(run_root):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_dir_not_tmp", "gate outputs must be under /tmp")]
        summary["gate_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_run_id_exists", "output run id exists")]
        summary["gate_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    file_sources, file_blockers, checked_file_count = read_file_sources(config)
    fixture_payload: dict[str, Any] | None = None
    fixture_load_blockers: list[dict[str, Any]] = []
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    if config.summary_fixture is not None:
        fixture_payload, fixture_load_blockers = read_json_object(config.summary_fixture)
        if fixture_payload:
            summary.update(fixture_payload)
        restore_config_identity(summary, config=config, run_root=run_root)
    summary["checked_file_count"] = checked_file_count
    blockers = fixture_load_blockers + fixture_identity_blockers(fixture_payload or {}, config=config, run_root=run_root)
    blockers.extend(
        validate_summary_payload(
            summary,
            fixture_payload=fixture_payload,
            file_sources=file_sources,
            file_blockers=file_blockers,
        )
    )
    summary["gate_status"] = choose_status(blockers, current_status=str(summary.get("gate_status") or ""))
    finalize_blockers(summary, blockers)
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
            "authorization_packet": summary.get("authorization_packet"),
            "observed_provider_or_backend_called": summary.get("observed_provider_or_backend_called"),
            "observed_provider_canary_executed": summary.get("observed_provider_canary_executed"),
            "observed_backend_family": summary.get("observed_backend_family"),
            "observed_backend": summary.get("observed_backend"),
            "observed_model": summary.get("observed_model"),
            "observed_call_count": summary.get("observed_call_count"),
            "observed_token_usage_total": summary.get("observed_token_usage_total"),
            "runtime_flags": summary.get("runtime_flags"),
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "next_check_after": summary.get("next_check_after"),
            "evidence_layer": summary.get("evidence_layer"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "gate_run_id": summary.get("gate_run_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "content_boundary_sha256": summary.get("content_boundary_sha256"),
        "gate_status": summary.get("gate_status"),
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8h_provider_canary_authorization_gate/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> GateConfig:
    return GateConfig(
        gate_run_id=str(args.gate_run_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
        files=tuple(args.file or ()),
        repo_root=args.repo_root,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(config_from_args(args))
    except ValueError as exc:
        print(json.dumps({"gate_status": STATUS_BLOCKED_SCHEMA, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("gate_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
