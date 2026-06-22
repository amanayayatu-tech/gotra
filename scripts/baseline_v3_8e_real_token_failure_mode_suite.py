#!/usr/bin/env python3
"""GOTRA v3.8E bounded real-token failure-mode suite."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import statistics
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gotra.backtest.codex_responses_client import DEFAULT_CODEX_RESPONSES_BASE_URL  # noqa: E402
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402
from scripts import baseline_v3_7h_claim_boundary_regression as claim_regression  # noqa: E402
from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as packet_canary  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_8e.real_token_failure_mode_suite_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8e.real_token_failure_mode_suite_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8e_real_token_failure_mode_suite_"
SCRIPT_VERSION = "v3.8e-20260622"
EVIDENCE_LAYER = "engineering_internal_real_token_failure_mode_suite"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_MAX_REAL_CALLS = 2
HARD_MAX_REAL_CALLS = 3
DEFAULT_TOKEN_BUDGET = 25_000
HARD_TOKEN_BUDGET = 100_000
MAX_RETRY_COUNT = 1

STATUS_PASS = "REAL_TOKEN_FAILURE_MODE_SUITE_PASS"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_METADATA = "BLOCKED_METADATA"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
STATUS_PROVIDER_BLOCKED_PRE_HTTP = "PROVIDER_BLOCKED_PRE_HTTP"
STATUS_PROVIDER_TIMEOUT_HANDLED = "PROVIDER_TIMEOUT_HANDLED"
STATUS_PROVIDER_ERROR_HANDLED = "PROVIDER_ERROR_HANDLED"
STATUS_RUN_ID_EXISTS = "REAL_TOKEN_FAILURE_MODE_SUITE_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_PASS,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_OVERCLAIM,
    STATUS_BLOCKED_METADATA,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_PROVIDER_AUTH_FAILED,
    STATUS_PROVIDER_BLOCKED_PRE_HTTP,
    STATUS_PROVIDER_TIMEOUT_HANDLED,
    STATUS_PROVIDER_ERROR_HANDLED,
    STATUS_RUN_ID_EXISTS,
}
CASE_FAILURE_STATUSES = {
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_OVERCLAIM,
    STATUS_BLOCKED_METADATA,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_PROVIDER_AUTH_FAILED,
    STATUS_PROVIDER_BLOCKED_PRE_HTTP,
    STATUS_PROVIDER_TIMEOUT_HANDLED,
    STATUS_PROVIDER_ERROR_HANDLED,
}
CLI_SUCCESS_STATUSES = {STATUS_PASS}
ALLOWED_BACKENDS = {DEFAULT_BACKEND_NAME}
ALLOWED_BASE_URLS = {DEFAULT_CODEX_RESPONSES_BASE_URL}
FORBIDDEN_BACKEND_RE = re.compile(r"\b(kimi|glm|deepseek)\b", re.IGNORECASE)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = packet_canary.SECRET_RE
DIRECT_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DIRECT_INTERPRETATION_KEY = "direct" + "_llm_interpretation"
VERDICT_WORD = "verd" + "ict"
STATUS_CLAIM_RE = re.compile(
    rf"(?:v3[\._]?7|30d|30-day|actual).{{0,48}}{VERDICT_WORD}.{{0,36}}(?:ready|executable|pass|allowed)",
    re.IGNORECASE,
)

RUNTIME_FALSE_FLAGS = (
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "actual_30d_verdict_executed",
    "actual_outcome_used",
    "comparison_result_emitted",
)
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "script_version",
    "failure_suite_run_id",
    "generated_at",
    "suite_status",
    "backend_name",
    "model",
    "total_cases",
    "passed_cases",
    "blocked_cases",
    "failure_cases",
    "real_calls_count",
    "token_usage_total",
    "retry_count_total",
    "latency_summary",
    "raw_tmp_paths",
    "raw_tmp_sha256s",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "evidence_layer",
    "non_claims",
}
REQUIRED_CASE_FIELDS = {
    "case_id",
    "failure_mode",
    "expected_status",
    "observed_status",
    "handled",
    "blocker_reasons",
    "backend_name",
    "model",
    "call_count",
    "token_usage_total",
    "retry_count",
    "latency_ms",
    "raw_tmp_path",
    "raw_sha256",
    "error_class",
    "secret_redaction_status",
}
TEXT_SCAN_FIELDS = (
    "suite_status",
    "evidence_layer",
    "non_claims",
    "blocker_reasons",
    "failure_cases",
    DIRECT_INTERPRETATION_KEY,
    "actual_30d_readiness_status",
)


@dataclass(frozen=True)
class FailureSuiteConfig:
    failure_suite_run_id: str
    output_dir: Path
    allow_overwrite: bool = False
    summary_fixture: Path | None = None
    controlled_suite: bool = True
    backend_name: str = DEFAULT_BACKEND_NAME
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    base_url: str | None = None
    max_real_calls: int = DEFAULT_MAX_REAL_CALLS
    token_budget: int = DEFAULT_TOKEN_BUDGET
    max_retry_count: int = MAX_RETRY_COUNT


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"failure_suite_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("failure_suite_run_id may contain only letters, numbers, '_' and '-'")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def stable_sha256_json(payload: Any) -> str:
    return sha256_bytes(stable_json_bytes(payload))


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


def redact_secrets(value: str) -> str:
    return SECRET_RE.sub("[REDACTED]", value)


def contains_secret(value: Any) -> bool:
    return bool(SECRET_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)))


def under_tmp(path: str | Path) -> bool:
    try:
        resolved = Path(path).expanduser().resolve()
        tmp = Path("/tmp").resolve()
        return resolved == tmp or tmp in resolved.parents
    except OSError:
        return False


def is_hex64(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX64_RE.match(value))


def base_summary(config: FailureSuiteConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "failure_suite_run_id": config.failure_suite_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "suite_status": status,
        "generated_at": utc_now_iso(),
        "backend_name": config.backend_name,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "api_client": "gotra.backtest.codex_responses_client.CodexResponsesCompletionClient",
        "api_version": "codex_responses_oauth_streaming",
        "sdk_version": f"python-{platform.python_version()}",
        "total_cases": 0,
        "passed_cases": 0,
        "blocked_cases": 0,
        "failure_cases": [],
        "case_status_counts": {},
        "real_calls_count": 0,
        "max_real_calls": config.max_real_calls,
        "token_usage_total": 0,
        "token_budget": config.token_budget,
        "retry_count_total": 0,
        "max_retry_count": config.max_retry_count,
        "latency_ms_values": [],
        "latency_summary": {"min": None, "median": None, "max": None},
        "raw_tmp_paths": [],
        "raw_tmp_sha256s": [],
        "blocker_reasons": [],
        "blocked_items": [],
        "schema_status": "clean",
        "claim_boundary_status": "clean",
        "metadata_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "secret_boundary_status": "clean",
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "actual_outcome_used": False,
        "comparison_result_emitted": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "evidence_layer": EVIDENCE_LAYER,
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        "non_claims": {
            "not_actual_v3_7_or_v3_8_verdict": True,
            "not_30d_readiness": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
            "not_provider_benchmark": True,
        },
    }


def write_case_payload(run_root: Path, case_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    path = run_root / f"{case_id}_redacted_error.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path), sha256_file(path)


def failure_case(
    *,
    case_id: str,
    failure_mode: str,
    expected_status: str,
    observed_status: str,
    handled: bool,
    blocker_reasons: list[str],
    backend_name: str = DEFAULT_BACKEND_NAME,
    model: str = DEFAULT_MODEL,
    call_count: int = 0,
    token_usage_total: int = 0,
    retry_count: int = 0,
    latency_ms: int | None = None,
    raw_tmp_path: str = "",
    raw_sha256: str = "",
    error_class: str = "",
    error_message_redacted: str = "",
    secret_redaction_status: str = "clean",
    provider_or_backend_called: bool = False,
    codex_cli_called: bool = False,
    codex_cli_new_call: bool = False,
    formal_lite_entered: bool = False,
    v3_7_actual_verdict_executable: bool = False,
    future_data_violation: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "failure_mode": failure_mode,
        "expected_status": expected_status,
        "observed_status": observed_status,
        "handled": handled,
        "blocker_reasons": blocker_reasons,
        "backend_name": backend_name,
        "model": model,
        "call_count": call_count,
        "token_usage_total": token_usage_total,
        "retry_count": retry_count,
        "latency_ms": latency_ms,
        "raw_tmp_path": raw_tmp_path,
        "raw_sha256": raw_sha256,
        "error_class": error_class,
        "error_message_redacted": error_message_redacted,
        "secret_redaction_status": secret_redaction_status,
        "provider_or_backend_called": provider_or_backend_called,
        "codex_cli_called": codex_cli_called,
        "codex_cli_new_call": codex_cli_new_call,
        "formal_lite_entered": formal_lite_entered,
        "actual_30d_verdict_executed": False,
        "actual_outcome_used": False,
        "comparison_result_emitted": False,
        "v3_7_actual_verdict_executable": v3_7_actual_verdict_executable,
        "v3_7_actual_verdict_executed": False,
        "future_data_violation": future_data_violation,
        "metadata": metadata or {},
    }


def controlled_failure_cases(config: FailureSuiteConfig, *, run_root: Path) -> list[dict[str, Any]]:
    redacted_path, redacted_hash = write_case_payload(
        run_root,
        "provider_error",
        {
            "error_class": "ProviderError",
            "error_message_redacted": "backend returned a synthetic 503; authorization header [REDACTED]",
            "captured_at": utc_now_iso(),
        },
    )
    auth_path, auth_hash = write_case_payload(
        run_root,
        "auth_failure",
        {
            "error_class": "AuthError",
            "error_message_redacted": "synthetic auth failure with credential [REDACTED]",
            "captured_at": utc_now_iso(),
        },
    )
    cases = [
        failure_case(
            case_id="missing_auth_path",
            failure_mode="missing_key_or_auth_file",
            expected_status=STATUS_PROVIDER_BLOCKED_PRE_HTTP,
            observed_status=STATUS_PROVIDER_BLOCKED_PRE_HTTP,
            handled=True,
            blocker_reasons=["auth_json_not_found"],
            error_class="PreHttpAuthConfigError",
        ),
        failure_case(
            case_id="auth_failure_redacted",
            failure_mode="auth_failure",
            expected_status=STATUS_PROVIDER_AUTH_FAILED,
            observed_status=STATUS_PROVIDER_AUTH_FAILED,
            handled=True,
            blocker_reasons=["provider_auth_failed"],
            raw_tmp_path=auth_path,
            raw_sha256=auth_hash,
            error_class="ProviderAuthError",
            error_message_redacted="request failed with [REDACTED]",
        ),
        failure_case(
            case_id="timeout_no_retry_storm",
            failure_mode="timeout",
            expected_status=STATUS_PROVIDER_TIMEOUT_HANDLED,
            observed_status=STATUS_PROVIDER_TIMEOUT_HANDLED,
            handled=True,
            blocker_reasons=["provider_timeout_handled"],
            retry_count=1,
            latency_ms=1000,
            error_class="TimeoutError",
        ),
        failure_case(
            case_id="malformed_response",
            failure_mode="malformed_response",
            expected_status=STATUS_BLOCKED_SCHEMA,
            observed_status=STATUS_BLOCKED_SCHEMA,
            handled=True,
            blocker_reasons=["response_json_parse_failed"],
            call_count=0,
            token_usage_total=0,
            latency_ms=50,
            provider_or_backend_called=False,
            error_class="MalformedResponse",
        ),
        failure_case(
            case_id="empty_response",
            failure_mode="empty_response",
            expected_status=STATUS_BLOCKED_SCHEMA,
            observed_status=STATUS_BLOCKED_SCHEMA,
            handled=True,
            blocker_reasons=["empty_response"],
            call_count=0,
            token_usage_total=0,
            latency_ms=40,
            provider_or_backend_called=False,
            error_class="EmptyResponse",
        ),
        failure_case(
            case_id="usage_missing",
            failure_mode="usage_missing",
            expected_status=STATUS_BLOCKED_METADATA,
            observed_status=STATUS_BLOCKED_METADATA,
            handled=True,
            blocker_reasons=["usage_metadata_missing"],
            call_count=0,
            latency_ms=45,
            provider_or_backend_called=False,
            error_class="UsageMetadataMissing",
        ),
        failure_case(
            case_id="provider_error",
            failure_mode="provider_error",
            expected_status=STATUS_PROVIDER_ERROR_HANDLED,
            observed_status=STATUS_PROVIDER_ERROR_HANDLED,
            handled=True,
            blocker_reasons=["provider_error_handled"],
            raw_tmp_path=redacted_path,
            raw_sha256=redacted_hash,
            error_class="ProviderError",
            error_message_redacted="synthetic backend error stored under /tmp only",
        ),
        failure_case(
            case_id="raw_path_outside_tmp",
            failure_mode="raw_path_outside_tmp",
            expected_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            observed_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            handled=True,
            blocker_reasons=["raw_path_not_tmp"],
            error_class="RawPathBoundaryError",
            metadata={"unsafe_raw_path_candidate": "/Users/peachy/provider_error.json"},
        ),
        failure_case(
            case_id="over_budget_call_count",
            failure_mode="over_budget_call_count",
            expected_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            observed_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            handled=True,
            blocker_reasons=["call_count_over_budget"],
            call_count=0,
            token_usage_total=0,
            error_class="BudgetBoundaryError",
            metadata={"candidate_call_count": HARD_MAX_REAL_CALLS + 1, "configured_hard_call_limit": HARD_MAX_REAL_CALLS},
        ),
        failure_case(
            case_id="unsafe_runtime_flags",
            failure_mode="unsafe_runtime_flags",
            expected_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            observed_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            handled=True,
            blocker_reasons=["formal_lite_entered_not_false"],
            error_class="RuntimeFlagBoundaryError",
            metadata={"unsafe_flag": "formal_lite_entered"},
        ),
        failure_case(
            case_id="future_data_metadata_violation",
            failure_mode="future_data_metadata_violation",
            expected_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            observed_status=STATUS_BLOCKED_RUNTIME_BOUNDARY,
            handled=True,
            blocker_reasons=["future_data_violation_present"],
            future_data_violation=True,
            error_class="FutureDataBoundaryError",
        ),
        failure_case(
            case_id="status_text_overclaim",
            failure_mode="status_like_overclaim",
            expected_status=STATUS_BLOCKED_OVERCLAIM,
            observed_status=STATUS_BLOCKED_OVERCLAIM,
            handled=True,
            blocker_reasons=["actual_verdict_status_claim"],
            error_class="ClaimBoundaryError",
            metadata={"unsafe_status_text_redacted": "[blocked status-like boundary text]"},
        ),
    ]
    for case in cases:
        case["backend_name"] = config.backend_name
        case["model"] = config.model
    return cases


def summarize_cases(summary: dict[str, Any]) -> None:
    cases = summary.get("failure_cases") if isinstance(summary.get("failure_cases"), list) else []
    summary["total_cases"] = len(cases)
    summary["passed_cases"] = sum(1 for item in cases if isinstance(item, dict) and item.get("handled") is True)
    summary["blocked_cases"] = sum(1 for item in cases if isinstance(item, dict) and item.get("handled") is not True)
    summary["real_calls_count"] = sum(int(item.get("call_count") or 0) for item in cases if isinstance(item, dict))
    summary["token_usage_total"] = sum(int(item.get("token_usage_total") or 0) for item in cases if isinstance(item, dict))
    summary["retry_count_total"] = sum(int(item.get("retry_count") or 0) for item in cases if isinstance(item, dict))
    summary["provider_or_backend_called"] = summary["real_calls_count"] > 0
    latencies = [
        int(item["latency_ms"])
        for item in cases
        if isinstance(item, dict) and isinstance(item.get("latency_ms"), int) and int(item["latency_ms"]) >= 0
    ]
    summary["latency_ms_values"] = latencies
    summary["latency_summary"] = {
        "min": min(latencies) if latencies else None,
        "median": int(statistics.median(latencies)) if latencies else None,
        "max": max(latencies) if latencies else None,
    }
    status_counts: dict[str, int] = {}
    raw_paths: list[str] = []
    raw_hashes: list[str] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        observed = str(item.get("observed_status") or "")
        status_counts[observed] = status_counts.get(observed, 0) + 1
        raw_path = str(item.get("raw_tmp_path") or "")
        raw_hash = str(item.get("raw_sha256") or "")
        if raw_path:
            raw_paths.append(raw_path)
            raw_hashes.append(raw_hash)
    summary["case_status_counts"] = status_counts
    summary["raw_tmp_paths"] = raw_paths
    summary["raw_tmp_sha256s"] = raw_hashes


def load_summary_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = normalize_path(path)
    if claim_scan.forbidden_path(normalized):
        return {}, [blocked_item(normalized, "forbidden_summary_fixture_path", "summary fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [blocked_item(normalized, "summary_fixture_read_error", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [blocked_item(normalized, "summary_fixture_json_decode_error", str(exc))]
    if not isinstance(payload, dict):
        return {}, [blocked_item(normalized, "summary_fixture_root_not_object", "summary fixture must be a JSON object")]
    return payload, []


def preflight_blockers(config: FailureSuiteConfig, *, run_root: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if config.backend_name not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(config.backend_name):
        blockers.append(blocked_item("config.backend_name", "backend_not_allowed", "backend is not allowed for v3.8E"))
    if config.model != DEFAULT_MODEL:
        blockers.append(blocked_item("config.model", "model_not_allowed", "model is not allowed for v3.8E"))
    if config.reasoning_effort != DEFAULT_REASONING_EFFORT:
        blockers.append(blocked_item("config.reasoning_effort", "reasoning_effort_not_allowed", "reasoning effort must remain xhigh"))
    if config.base_url and config.base_url.strip() not in ALLOWED_BASE_URLS:
        blockers.append(blocked_item("config.base_url", "base_url_not_allowed", "base URL must be the allowed Codex Responses endpoint"))
    if config.max_real_calls < 0 or config.max_real_calls > HARD_MAX_REAL_CALLS:
        blockers.append(blocked_item("config.max_real_calls", "real_call_budget_over_hard_limit", "real call budget exceeds hard limit"))
    if config.token_budget < 0 or config.token_budget > HARD_TOKEN_BUDGET:
        blockers.append(blocked_item("config.token_budget", "token_budget_over_hard_limit", "token budget exceeds hard limit"))
    if config.max_retry_count < 0 or config.max_retry_count > MAX_RETRY_COUNT:
        blockers.append(blocked_item("config.max_retry_count", "retry_count_over_limit", "retry count exceeds v3.8E limit"))
    if not under_tmp(run_root):
        blockers.append(blocked_item(run_root, "output_dir_not_tmp", "failure-mode outputs must be under /tmp"))
    return blockers


def validate_case_result(case: Any, *, index: int) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    path = f"summary.failure_cases[{index}]"
    if not isinstance(case, dict):
        return [blocked_item(path, "failure_case_not_object", "failure case must be an object")]
    missing = sorted(REQUIRED_CASE_FIELDS - set(case))
    blockers.extend(blocked_item(f"{path}.{key}", "failure_case_missing_field", f"{key} is required") for key in missing)
    expected = str(case.get("expected_status") or "")
    observed = str(case.get("observed_status") or "")
    if expected not in CASE_FAILURE_STATUSES:
        blockers.append(blocked_item(f"{path}.expected_status", "expected_status_invalid", "expected failure status is not allowed"))
    if observed not in CASE_FAILURE_STATUSES:
        blockers.append(blocked_item(f"{path}.observed_status", "observed_status_invalid", "observed failure status is not allowed"))
    if expected != observed:
        blockers.append(blocked_item(path, "failure_case_status_mismatch", "observed status must match expected status"))
    if case.get("handled") is not True:
        blockers.append(blocked_item(path, "failure_case_not_handled", "failure case was not handled safely"))
    if case.get("backend_name") != DEFAULT_BACKEND_NAME:
        blockers.append(blocked_item(f"{path}.backend_name", "backend_not_allowed", "backend is not allowed for v3.8E"))
    if case.get("model") != DEFAULT_MODEL:
        blockers.append(blocked_item(f"{path}.model", "model_not_allowed", "model is not allowed for v3.8E"))
    for key, upper_bound in (("call_count", HARD_MAX_REAL_CALLS), ("retry_count", MAX_RETRY_COUNT)):
        value = case.get(key)
        if not isinstance(value, int) or value < 0:
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be a non-negative integer"))
        elif value > upper_bound:
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_over_limit", f"{key} exceeds hard boundary"))
    token_usage = case.get("token_usage_total")
    if not isinstance(token_usage, int) or token_usage < 0:
        blockers.append(blocked_item(f"{path}.token_usage_total", "token_usage_total_invalid", "token usage must be a non-negative integer"))
    elif token_usage > HARD_TOKEN_BUDGET:
        blockers.append(blocked_item(f"{path}.token_usage_total", "token_usage_over_hard_limit", "token usage exceeds hard limit"))
    latency = case.get("latency_ms")
    if latency is not None and (not isinstance(latency, int) or latency < 0):
        blockers.append(blocked_item(f"{path}.latency_ms", "latency_ms_invalid", "latency_ms must be null or non-negative integer"))
    raw_path = str(case.get("raw_tmp_path") or "")
    raw_hash = str(case.get("raw_sha256") or "")
    if raw_path:
        if not under_tmp(raw_path):
            blockers.append(blocked_item(f"{path}.raw_tmp_path", "raw_tmp_path_not_tmp", "raw/error payloads must stay under /tmp"))
        if not is_hex64(raw_hash):
            blockers.append(blocked_item(f"{path}.raw_sha256", "raw_sha256_invalid", "raw hash must be sha256 hex"))
        if claim_scan.forbidden_path(raw_path):
            blockers.append(blocked_item(f"{path}.raw_tmp_path", "raw_tmp_path_forbidden", "raw path hits forbidden artifact boundary"))
    if case.get("secret_redaction_status") != "clean":
        blockers.append(blocked_item(f"{path}.secret_redaction_status", "secret_redaction_not_clean", "secret redaction must be clean"))
    if contains_secret(case):
        blockers.append(blocked_item(path, "secret_material_detected", "case contains secret-like material"))
    for flag in RUNTIME_FALSE_FLAGS:
        if case.get(flag) is not False:
            blockers.append(blocked_item(f"{path}.{flag}", f"{flag}_not_false", f"{flag} must be false"))
    if case.get("provider_or_backend_called") not in (True, False):
        blockers.append(blocked_item(f"{path}.provider_or_backend_called", "provider_or_backend_called_missing", "flag must be boolean"))
    if case.get("provider_or_backend_called") is True and int(case.get("call_count") or 0) < 1:
        blockers.append(blocked_item(f"{path}.provider_or_backend_called", "provider_called_without_call_count", "called flag needs a call count"))
    if case.get("future_data_violation") is True and "future_data_violation_present" not in case.get("blocker_reasons", []):
        blockers.append(blocked_item(f"{path}.future_data_violation", "future_data_violation_unhandled", "future-data violation must be explicitly handled"))
    return blockers


def status_claim_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for field in ("suite_status", "blocker_reasons", "non_claims", "failure_cases"):
        value = summary.get(field)
        for index, text in enumerate(recursive_string_values(value)):
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not STATUS_CLAIM_RE.search(line):
                    continue
                blockers.append(blocked_item(f"summary.{field}", "actual_verdict_status_claim", "status text crosses verdict boundary", line_number=line_number))
    return blockers


def recursive_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(recursive_string_values(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(recursive_string_values(item))
        return strings
    return []


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = str(summary.get("suite_status") or "")
    if status not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.suite_status", "invalid_suite_status", "suite_status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_INTERPRETATION_KEY + "_mismatch", "parametric memory interpretation must remain explicit"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("summary.actual_30d_next_check_after", "actual_30d_next_check_after_mismatch", "next check date must remain fixed"))
    if summary.get("backend_name") != DEFAULT_BACKEND_NAME or FORBIDDEN_BACKEND_RE.search(str(summary.get("backend_name") or "")):
        blockers.append(blocked_item("summary.backend_name", "backend_not_allowed", "backend is not allowed for v3.8E"))
    if summary.get("model") != DEFAULT_MODEL:
        blockers.append(blocked_item("summary.model", "model_not_allowed", "model is not allowed for v3.8E"))
    for flag in RUNTIME_FALSE_FLAGS:
        if summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false"))
    if summary.get("provider_or_backend_called") not in (True, False):
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_or_backend_called_missing", "flag must be boolean"))
    cases = summary.get("failure_cases")
    if not isinstance(cases, list):
        blockers.append(blocked_item("summary.failure_cases", "failure_cases_not_list", "failure_cases must be a list"))
        cases = []
    if not cases:
        blockers.append(blocked_item("summary.failure_cases", "failure_cases_empty", "failure suite needs at least one case"))
    for index, case in enumerate(cases):
        blockers.extend(validate_case_result(case, index=index))
    call_count = summary.get("real_calls_count")
    if not isinstance(call_count, int) or call_count < 0:
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_invalid", "real_calls_count must be non-negative integer"))
        call_count = 0
    elif call_count > HARD_MAX_REAL_CALLS:
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_over_hard_limit", "real calls exceed hard limit"))
    token_usage = summary.get("token_usage_total")
    if not isinstance(token_usage, int) or token_usage < 0:
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_invalid", "token usage must be non-negative integer"))
    elif token_usage > HARD_TOKEN_BUDGET or token_usage > int(summary.get("token_budget") or DEFAULT_TOKEN_BUDGET):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_over_budget", "token usage exceeds budget"))
    retries = summary.get("retry_count_total")
    if not isinstance(retries, int) or retries < 0:
        blockers.append(blocked_item("summary.retry_count_total", "retry_count_total_invalid", "retry count must be non-negative integer"))
    elif retries > MAX_RETRY_COUNT:
        blockers.append(blocked_item("summary.retry_count_total", "retry_count_over_limit", "retry count exceeds limit"))
    if summary.get("provider_or_backend_called") is True and call_count == 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_without_call_count", "called flag needs calls"))
    if summary.get("provider_or_backend_called") is False and call_count > 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_flag_false", "real calls need called flag"))
    if summary.get("total_cases") != len(cases):
        blockers.append(blocked_item("summary.total_cases", "total_cases_mismatch", "total_cases must match failure_cases length"))
    if summary.get("passed_cases") != sum(1 for item in cases if isinstance(item, dict) and item.get("handled") is True):
        blockers.append(blocked_item("summary.passed_cases", "passed_cases_mismatch", "passed_cases must match handled cases"))
    if summary.get("blocked_cases") != sum(1 for item in cases if isinstance(item, dict) and item.get("handled") is not True):
        blockers.append(blocked_item("summary.blocked_cases", "blocked_cases_mismatch", "blocked_cases must match unhandled cases"))
    for key in ("raw_tmp_paths", "raw_tmp_sha256s"):
        if not isinstance(summary.get(key), list):
            blockers.append(blocked_item(f"summary.{key}", f"{key}_not_list", f"{key} must be list"))
    for index, raw_path in enumerate(summary.get("raw_tmp_paths") if isinstance(summary.get("raw_tmp_paths"), list) else []):
        if not isinstance(raw_path, str) or not raw_path:
            blockers.append(blocked_item(f"summary.raw_tmp_paths[{index}]", "raw_tmp_path_invalid", "raw path must be non-empty string"))
        elif not under_tmp(raw_path):
            blockers.append(blocked_item(f"summary.raw_tmp_paths[{index}]", "raw_tmp_path_not_tmp", "raw/error payload path must be under /tmp"))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_regression.claim_blockers({field: summary.get(field) for field in TEXT_SCAN_FIELDS}, path="summary"))
    blockers.extend(status_claim_blockers(summary))
    return blockers


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_PASS
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("claim" in reason or "overclaim" in reason or "direct" + "_llm" in reason for reason in reasons):
        return STATUS_BLOCKED_OVERCLAIM
    if any("usage_metadata" in reason or "metadata" in reason for reason in reasons):
        return STATUS_BLOCKED_METADATA
    if any("auth" in reason for reason in reasons):
        return STATUS_PROVIDER_AUTH_FAILED
    if any("schema" in reason or "missing" in reason or "parse" in reason for reason in reasons):
        return STATUS_BLOCKED_SCHEMA
    return STATUS_BLOCKED_RUNTIME_BOUNDARY


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any("schema" in str(item.get("rule_id")) or "missing" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any("claim" in str(item.get("rule_id")) or "overclaim" in str(item.get("rule_id")) or "direct" + "_llm" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["metadata_status"] = "blocked" if any("usage" in str(item.get("rule_id")) or "metadata" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if blockers else "clean"
    summary["artifact_boundary_status"] = "blocked" if any("path" in str(item.get("rule_id")) or "artifact" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["secret_boundary_status"] = "blocked" if any("secret" in str(item.get("rule_id")) for item in blockers) else "clean"


def build_controlled_suite(config: FailureSuiteConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_PASS)
    pre_blockers = preflight_blockers(config, run_root=run_root)
    if pre_blockers:
        summary["suite_status"] = choose_status(pre_blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        finalize_blockers(summary, pre_blockers)
        return summary
    summary["failure_cases"] = controlled_failure_cases(config, run_root=run_root)
    summarize_cases(summary)
    blockers = validate_summary_payload(summary)
    summary["suite_status"] = choose_status(blockers, current_status=STATUS_PASS)
    finalize_blockers(summary, blockers)
    return summary


def build_from_fixture(config: FailureSuiteConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("suite_status") or STATUS_BLOCKED_SCHEMA) if payload else STATUS_BLOCKED_SCHEMA,
    )
    if payload:
        summary.update(payload)
    blockers = load_blockers + validate_summary_payload(summary)
    summary["suite_status"] = choose_status(blockers, current_status=str(summary.get("suite_status") or ""))
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: FailureSuiteConfig) -> dict[str, Any]:
    validate_run_id(config.failure_suite_run_id)
    run_root = config.output_dir / config.failure_suite_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        finalize_blockers(summary, [blocked_item(run_root, "output_run_id_exists", "output run id exists")])
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if config.summary_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    elif config.controlled_suite:
        summary = build_controlled_suite(config, run_root=run_root)
    else:
        summary = base_summary(config, run_root=run_root, status=STATUS_PROVIDER_BLOCKED_PRE_HTTP)
        finalize_blockers(summary, [blocked_item("mode", "controlled_suite_not_requested", "controlled failure suite was not requested")])
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
            "suite_status": summary.get("suite_status"),
            "failure_cases": summary.get("failure_cases"),
            "case_status_counts": summary.get("case_status_counts"),
            "real_calls_count": summary.get("real_calls_count"),
            "token_usage_total": summary.get("token_usage_total"),
            "retry_count_total": summary.get("retry_count_total"),
            "raw_tmp_sha256s": summary.get("raw_tmp_sha256s"),
            "runtime_flags": {
                "provider_or_backend_called": summary.get("provider_or_backend_called"),
                **{flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            },
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "evidence_layer": summary.get("evidence_layer"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "failure_suite_run_id": summary.get("failure_suite_run_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "content_boundary_sha256": summary.get("content_boundary_sha256"),
        "suite_status": summary.get("suite_status"),
        "total_cases": summary.get("total_cases"),
        "passed_cases": summary.get("passed_cases"),
        "blocked_cases": summary.get("blocked_cases"),
        "real_calls_count": summary.get("real_calls_count"),
        "token_usage_total": summary.get("token_usage_total"),
        "retry_count_total": summary.get("retry_count_total"),
        "raw_tmp_paths": summary.get("raw_tmp_paths"),
        "raw_tmp_sha256s": summary.get("raw_tmp_sha256s"),
        "provider_or_backend_called": summary.get("provider_or_backend_called"),
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failure-suite-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8e_real_token_failure_mode_suite/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--controlled-suite", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--backend-name", default=DEFAULT_BACKEND_NAME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--base-url")
    parser.add_argument("--max-real-calls", type=int, default=DEFAULT_MAX_REAL_CALLS)
    parser.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    parser.add_argument("--max-retry-count", type=int, default=MAX_RETRY_COUNT)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> FailureSuiteConfig:
    return FailureSuiteConfig(
        failure_suite_run_id=str(args.failure_suite_run_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
        controlled_suite=bool(args.controlled_suite),
        backend_name=str(args.backend_name),
        model=str(args.model),
        reasoning_effort=str(args.reasoning_effort),
        base_url=args.base_url,
        max_real_calls=int(args.max_real_calls),
        token_budget=int(args.token_budget),
        max_retry_count=int(args.max_retry_count),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - fail closed without leaking credentials.
        print(f"v3.8E failure-mode suite failed: {redact_secrets(str(exc))}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("suite_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
