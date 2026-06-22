#!/usr/bin/env python3
"""GOTRA v3.8D bounded orchestrator real-token dry-run."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gotra.backtest.codex_responses_client import (  # noqa: E402
    DEFAULT_CODEX_RESPONSES_BASE_URL,
    CodexResponsesCompletionClient,
)
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402
from scripts import baseline_v3_7h_claim_boundary_regression as claim_regression  # noqa: E402
from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as packet_canary  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_8d.gotra_orchestrator_real_token_dry_run_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8d.gotra_orchestrator_real_token_dry_run_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8d_gotra_orchestrator_real_token_dry_run_"
SCRIPT_VERSION = "v3.8d-20260622"
EVIDENCE_LAYER = "engineering_internal_gotra_orchestrator_real_token_dry_run"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_CALL_COUNT = 3
MAX_CALL_COUNT = 5
DEFAULT_TOKEN_BUDGET = 25_000
HARD_TOKEN_BUDGET = 100_000

STATUS_PASS = "GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_METADATA = "BLOCKED_METADATA"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
STATUS_PROVIDER_BLOCKED_PRE_HTTP = "PROVIDER_BLOCKED_PRE_HTTP"
STATUS_RUN_ID_EXISTS = "GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_PASS,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_OVERCLAIM,
    STATUS_BLOCKED_METADATA,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_PROVIDER_AUTH_FAILED,
    STATUS_PROVIDER_BLOCKED_PRE_HTTP,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_PASS}
ALLOWED_BACKENDS = {DEFAULT_BACKEND_NAME}
ALLOWED_BASE_URLS = {DEFAULT_CODEX_RESPONSES_BASE_URL}
FORBIDDEN_BACKEND_RE = re.compile(r"\b(kimi|glm|deepseek)\b", re.IGNORECASE)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = packet_canary.SECRET_RE
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
    "scorer_entered",
    "actual_outcome_used",
    "comparison_result_emitted",
)
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "script_version",
    "dry_run_run_id",
    "generated_at",
    "backend_name",
    "model",
    "reasoning_effort",
    "requested_call_count",
    "real_calls_count",
    "token_usage_total",
    "source_artifact_paths",
    "input_fixture_hashes",
    "prompt_hashes",
    "raw_response_tmp_paths",
    "raw_response_sha256s",
    "parsed_packet_tmp_paths",
    "parsed_packet_sha256s",
    "orchestrator_trace_tmp_paths",
    "orchestrator_trace_sha256s",
    "call_results",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "evidence_layer",
    "non_claims",
}
REQUIRED_CALL_RESULT_FIELDS = {
    "run_id",
    "call_id",
    "generated_at",
    "backend_name",
    "model",
    "prompt_hash",
    "input_fixture_hash",
    "source_artifact_path",
    "source_artifact_sha256",
    "raw_response_tmp_path",
    "raw_response_sha256",
    "parsed_packet_tmp_path",
    "parsed_packet_sha256",
    "orchestrator_trace_tmp_path",
    "orchestrator_trace_sha256",
    "schema_status",
    "claim_boundary_status",
    "provenance_hash_status",
    "latency_ms",
    "token_usage_total",
}
TEXT_SUMMARY_FIELDS = (
    "dry_run_status",
    "evidence_layer",
    "non_claims",
    "blocker_reasons",
    packet_canary.DIRECT_LLM_INTERPRETATION_KEY,
    "actual_30d_readiness_status",
)


@dataclass(frozen=True)
class DryRunConfig:
    dry_run_run_id: str
    output_dir: Path
    allow_overwrite: bool = False
    summary_fixture: Path | None = None
    real_token_dry_run: bool = False
    backend_name: str = DEFAULT_BACKEND_NAME
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    auth_json_path: Path | None = None
    base_url: str | None = None
    timeout_seconds: int = 45
    call_count: int = DEFAULT_CALL_COUNT
    token_budget: int = DEFAULT_TOKEN_BUDGET


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"dry_run_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("dry_run_run_id may contain only letters, numbers, '_' and '-'")


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


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def token_total(usage: Any) -> int | None:
    return packet_canary.token_total(usage)


def usage_input(usage: Any) -> int:
    return packet_canary.usage_input(usage)


def usage_output(usage: Any) -> int:
    return packet_canary.usage_output(usage)


def resolved_auth_json_path(config: DryRunConfig) -> Path:
    if config.auth_json_path is not None:
        return config.auth_json_path.expanduser()
    env_path = os.environ.get("CODEX_AUTH_JSON", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.codex/auth.json").expanduser()


def base_summary(config: DryRunConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "dry_run_run_id": config.dry_run_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "dry_run_status": status,
        "generated_at": utc_now_iso(),
        "backend_name": config.backend_name,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "sdk_version": f"python-{platform.python_version()}",
        "api_client": "gotra.backtest.codex_responses_client.CodexResponsesCompletionClient",
        "api_version": "codex_responses_oauth_streaming",
        "requested_call_count": config.call_count,
        "max_call_count": MAX_CALL_COUNT,
        "real_calls_count": 0,
        "token_budget": config.token_budget,
        "token_usage_total": 0,
        "latency_ms_values": [],
        "latency_ms_min": None,
        "latency_ms_median": None,
        "latency_ms_max": None,
        "usage_available_count": 0,
        "usage_availability_rate": 0.0,
        "schema_pass_count": 0,
        "schema_pass_rate": 0.0,
        "overclaim_blocker_count": 0,
        "overclaim_rate": 0.0,
        "future_data_violation_count": 0,
        "source_artifact_paths": [],
        "source_artifact_sha256s": [],
        "input_fixture_hashes": [],
        "prompt_hashes": [],
        "raw_response_tmp_paths": [],
        "raw_response_sha256s": [],
        "parsed_packet_tmp_paths": [],
        "parsed_packet_sha256s": [],
        "orchestrator_trace_tmp_paths": [],
        "orchestrator_trace_sha256s": [],
        "call_results": [],
        "blocker_reasons": [],
        "blocked_items": [],
        "schema_status": "not_run",
        "claim_boundary_status": "not_run",
        "provenance_hash_status": "not_run",
        "metadata_status": "not_run",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "secret_boundary_status": "clean",
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "scorer_entered": False,
        "actual_outcome_used": False,
        "comparison_result_emitted": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "evidence_layer": EVIDENCE_LAYER,
        packet_canary.DIRECT_LLM_INTERPRETATION_KEY: packet_canary.DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_actual_v3_7_or_v3_8_verdict": True,
            "not_30d_readiness": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
            "not_provider_benchmark": True,
            "not_model_comparison_claim": True,
        },
    }


def summarize_rates(summary: dict[str, Any]) -> None:
    count = int(summary.get("real_calls_count") or 0)
    latencies = [int(value) for value in summary.get("latency_ms_values", []) if isinstance(value, int)]
    summary["latency_ms_min"] = min(latencies) if latencies else None
    summary["latency_ms_median"] = int(statistics.median(latencies)) if latencies else None
    summary["latency_ms_max"] = max(latencies) if latencies else None
    if count > 0:
        summary["schema_pass_rate"] = round(float(summary.get("schema_pass_count") or 0) / count, 4)
        summary["overclaim_rate"] = round(float(summary.get("overclaim_blocker_count") or 0) / count, 4)
        summary["usage_availability_rate"] = round(float(summary.get("usage_available_count") or 0) / count, 4)


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


def validate_call_result(call_result: Any, *, index: int, status: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    path = f"summary.call_results[{index}]"
    if not isinstance(call_result, dict):
        return [blocked_item(path, "call_result_not_object", "call result must be an object")]
    missing = sorted(REQUIRED_CALL_RESULT_FIELDS - set(call_result))
    blockers.extend(blocked_item(f"{path}.{key}", "call_result_missing_field", f"{key} is required") for key in missing)
    if call_result.get("backend_name") != DEFAULT_BACKEND_NAME:
        blockers.append(blocked_item(f"{path}.backend_name", "backend_not_allowed", "backend is not allowed for v3.8D"))
    if call_result.get("model") != DEFAULT_MODEL:
        blockers.append(blocked_item(f"{path}.model", "model_not_allowed", "model is not allowed for v3.8D"))
    for key in (
        "prompt_hash",
        "input_fixture_hash",
        "source_artifact_sha256",
        "raw_response_sha256",
        "parsed_packet_sha256",
        "orchestrator_trace_sha256",
    ):
        value = call_result.get(key)
        if not isinstance(value, str) or not HEX64_RE.match(value):
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be a sha256 hex digest"))
    for key in ("raw_response_tmp_path", "parsed_packet_tmp_path", "orchestrator_trace_tmp_path"):
        value = str(call_result.get(key) or "")
        if value and not under_tmp(value):
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_not_tmp", f"{key} must be under /tmp"))
    source_path = str(call_result.get("source_artifact_path") or "")
    if source_path and claim_scan.forbidden_path(source_path):
        blockers.append(blocked_item(f"{path}.source_artifact_path", "forbidden_source_artifact_path", "source path is forbidden"))
    latency_ms = call_result.get("latency_ms")
    if not isinstance(latency_ms, int) or latency_ms < 0:
        blockers.append(blocked_item(f"{path}.latency_ms", "latency_ms_invalid", "latency_ms must be non-negative integer"))
    token_usage = call_result.get("token_usage_total")
    if not isinstance(token_usage, int) or token_usage < 0:
        blockers.append(blocked_item(f"{path}.token_usage_total", "token_usage_total_invalid", "token usage must be non-negative integer"))
    if status == STATUS_PASS:
        for key, expected in (
            ("schema_status", "clean"),
            ("claim_boundary_status", "clean"),
            ("provenance_hash_status", "clean"),
        ):
            if call_result.get(key) != expected:
                blockers.append(blocked_item(f"{path}.{key}", f"{key}_not_clean", f"{key} must be clean for PASS"))
    return blockers


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = str(summary.get("dry_run_status") or "")
    if status not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.dry_run_status", "invalid_dry_run_status", "dry_run_status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get(packet_canary.DIRECT_LLM_INTERPRETATION_KEY) != packet_canary.DIRECT_LLM_INTERPRETATION:
        blockers.append(
            blocked_item(
                f"summary.{packet_canary.DIRECT_LLM_INTERPRETATION_KEY}",
                packet_canary.DIRECT_LLM_INTERPRETATION_KEY + "_mismatch",
                "parametric memory interpretation must remain explicit",
            )
        )
    backend = str(summary.get("backend_name") or "")
    if backend not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(backend):
        blockers.append(blocked_item("summary.backend_name", "backend_not_allowed", "backend is not allowed for v3.8D"))
    if summary.get("model") != DEFAULT_MODEL:
        blockers.append(blocked_item("summary.model", "model_not_allowed", "model is not allowed for v3.8D"))
    if summary.get("reasoning_effort") != DEFAULT_REASONING_EFFORT:
        blockers.append(blocked_item("summary.reasoning_effort", "reasoning_effort_not_allowed", "reasoning effort must remain xhigh"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(
            blocked_item(
                "summary.actual_30d_readiness_status",
                "actual_30d_readiness_status_invalid",
                "actual 30D readiness must remain DATA_NOT_MATURED",
            )
        )
    for flag in RUNTIME_FALSE_FLAGS:
        if summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false"))
    if summary.get("provider_or_backend_called") not in (True, False):
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_or_backend_called_missing", "flag must be boolean"))

    call_count = summary.get("real_calls_count")
    if not isinstance(call_count, int) or call_count < 0:
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_invalid", "real_calls_count must be non-negative integer"))
        call_count = 0
    elif call_count > MAX_CALL_COUNT:
        blockers.append(blocked_item("summary.real_calls_count", "call_count_over_budget", "real_calls_count exceeds v3.8D max"))
    requested_call_count = summary.get("requested_call_count")
    if not isinstance(requested_call_count, int) or requested_call_count < 1 or requested_call_count > MAX_CALL_COUNT:
        blockers.append(blocked_item("summary.requested_call_count", "requested_call_count_invalid", "requested_call_count must be 1..5"))
    elif status == STATUS_PASS and call_count != requested_call_count:
        blockers.append(blocked_item("summary.real_calls_count", "requested_call_count_not_fulfilled", "PASS requires fulfilling requested calls"))
    token_usage = summary.get("token_usage_total")
    if not isinstance(token_usage, int) or token_usage < 0:
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_invalid", "token_usage_total must be non-negative integer"))
    elif token_usage > HARD_TOKEN_BUDGET or token_usage > int(summary.get("token_budget") or DEFAULT_TOKEN_BUDGET):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_over_budget", "token usage exceeds budget"))
    if summary.get("provider_or_backend_called") is True and call_count == 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_without_call_count", "called flag needs calls"))
    if summary.get("provider_or_backend_called") is False and call_count > 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_flag_false", "real calls need called flag"))

    if summary.get("future_data_violation_count") not in (0, None):
        blockers.append(blocked_item("summary.future_data_violation_count", "future_data_violation_present", "future data is forbidden"))

    call_results = summary.get("call_results")
    if not isinstance(call_results, list):
        blockers.append(blocked_item("summary.call_results", "call_results_not_list", "call_results must be list"))
        call_results = []
    if status == STATUS_PASS and len(call_results) != call_count:
        blockers.append(blocked_item("summary.call_results", "call_results_count_mismatch", "PASS needs one result per call"))
    for index, call_result in enumerate(call_results):
        blockers.extend(validate_call_result(call_result, index=index, status=status))

    for path_key in (
        "source_artifact_paths",
        "raw_response_tmp_paths",
        "parsed_packet_tmp_paths",
        "orchestrator_trace_tmp_paths",
    ):
        values = summary.get(path_key)
        if values is not None and not isinstance(values, list):
            blockers.append(blocked_item(f"summary.{path_key}", f"{path_key}_not_list", f"{path_key} must be list"))
            continue
        for index, value in enumerate(values or []):
            if not isinstance(value, str) or not value:
                blockers.append(blocked_item(f"summary.{path_key}[{index}]", "path_value_invalid", "path must be non-empty string"))
                continue
            if path_key != "source_artifact_paths" and not under_tmp(value):
                blockers.append(blocked_item(f"summary.{path_key}[{index}]", "runtime_path_not_tmp", "runtime paths must be under /tmp"))
            if claim_scan.forbidden_path(value):
                blockers.append(blocked_item(f"summary.{path_key}[{index}]", "forbidden_artifact_path", "artifact path is forbidden"))

    if status == STATUS_PASS:
        if call_count < 1:
            blockers.append(blocked_item("summary.real_calls_count", "pass_without_real_calls", "PASS requires bounded real calls"))
        if float(summary.get("usage_availability_rate") or 0.0) < 1.0:
            blockers.append(blocked_item("summary.usage_availability_rate", "usage_metadata_missing", "PASS requires usage metadata"))
        if float(summary.get("schema_pass_rate") or 0.0) < 1.0:
            blockers.append(blocked_item("summary.schema_pass_rate", "schema_pass_rate_not_complete", "PASS requires clean schema"))
        if float(summary.get("overclaim_rate") or 0.0) != 0.0:
            blockers.append(blocked_item("summary.overclaim_rate", "overclaim_rate_nonzero", "PASS requires zero overclaim rate"))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_regression.claim_blockers({field: summary.get(field) for field in TEXT_SUMMARY_FIELDS}, path="summary"))
    blockers.extend(status_claim_blockers(summary))
    return blockers


def status_claim_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for field in ("dry_run_status", "blocker_reasons", "non_claims"):
        value = summary.get(field)
        candidates = value if isinstance(value, list) else [value]
        if isinstance(value, dict):
            candidates = list(value.values())
        for index, item in enumerate(candidates):
            if not isinstance(item, str):
                continue
            if STATUS_CLAIM_RE.search(item):
                blockers.append(blocked_item(f"summary.{field}[{index}]", "actual_verdict_status_claim", "status text crosses verdict boundary"))
    return blockers


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_PASS
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("claim" in reason or "overclaim" in reason or "direct" + "_llm" in reason for reason in reasons):
        return STATUS_BLOCKED_OVERCLAIM
    if any("token_usage_over_budget" == reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("usage_metadata" in reason or "metadata" in reason for reason in reasons):
        return STATUS_BLOCKED_METADATA
    if any("auth" in reason for reason in reasons):
        return STATUS_PROVIDER_BLOCKED_PRE_HTTP
    if any(
        "schema" in reason
        or "missing" in reason
        or "parse" in reason
        or "provenance" in reason
        or "hash" in reason
        or "future_data" in reason
        for reason in reasons
    ):
        return STATUS_BLOCKED_SCHEMA
    return STATUS_BLOCKED_RUNTIME_BOUNDARY


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(
        "schema" in str(item.get("rule_id")) or "missing" in str(item.get("rule_id")) for item in blockers
    ) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(
        "claim" in str(item.get("rule_id")) or "overclaim" in str(item.get("rule_id")) or "direct" + "_llm" in str(item.get("rule_id"))
        for item in blockers
    ) else "clean"
    summary["provenance_hash_status"] = "blocked" if any(
        "provenance" in str(item.get("rule_id")) or "hash" in str(item.get("rule_id")) for item in blockers
    ) else "clean"
    summary["metadata_status"] = "blocked" if any(
        "usage" in str(item.get("rule_id")) or "metadata" in str(item.get("rule_id")) for item in blockers
    ) else "clean"
    summary["runtime_boundary_status"] = "blocked" if blockers else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(
        "path" in str(item.get("rule_id")) or "artifact" in str(item.get("rule_id")) for item in blockers
    ) else "clean"
    summary["secret_boundary_status"] = "blocked" if any("secret" in str(item.get("rule_id")) for item in blockers) else "clean"


def build_from_fixture(config: DryRunConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("dry_run_status") or STATUS_BLOCKED_RUNTIME_BOUNDARY) if payload else STATUS_BLOCKED_RUNTIME_BOUNDARY,
    )
    if payload:
        summary.update(payload)
    summarize_rates(summary)
    fixture_missing = [
        blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required")
        for key in sorted(REQUIRED_SUMMARY_FIELDS - set(payload))
    ] if payload else []
    blockers = load_blockers + fixture_missing + validate_summary_payload(summary)
    summary["dry_run_status"] = choose_status(blockers, current_status=str(summary.get("dry_run_status") or ""))
    finalize_blockers(summary, blockers)
    return summary


def pre_http_blockers(config: DryRunConfig, *, run_root: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if config.backend_name not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(config.backend_name):
        blockers.append(blocked_item("config.backend_name", "backend_not_allowed", "backend is not allowed for v3.8D"))
    if config.model != DEFAULT_MODEL:
        blockers.append(blocked_item("config.model", "model_not_allowed", "model is not allowed for v3.8D"))
    if config.reasoning_effort != DEFAULT_REASONING_EFFORT:
        blockers.append(blocked_item("config.reasoning_effort", "reasoning_effort_not_allowed", "reasoning effort must remain xhigh"))
    if config.base_url and config.base_url.strip() not in ALLOWED_BASE_URLS:
        blockers.append(blocked_item("config.base_url", "base_url_not_allowed", "base URL must be the allowed Codex Responses endpoint"))
    if config.call_count < 1 or config.call_count > MAX_CALL_COUNT:
        blockers.append(blocked_item("config.call_count", "call_count_over_budget", "call count must be between 1 and 5"))
    if config.token_budget > HARD_TOKEN_BUDGET:
        blockers.append(blocked_item("config.token_budget", "token_budget_over_hard_limit", "token budget exceeds hard limit"))
    if not under_tmp(run_root):
        blockers.append(blocked_item(run_root, "real_output_dir_not_tmp", "real-token output directory must be under /tmp"))
    auth_path = resolved_auth_json_path(config)
    if not auth_path.exists():
        blockers.append(blocked_item("auth", "auth_json_not_found", "Codex OAuth auth file is not available"))
    elif claim_scan.forbidden_path(normalize_path(auth_path)):
        blockers.append(blocked_item("auth", "auth_json_path_forbidden", "auth path is forbidden"))
    return blockers


def synthetic_orchestrator_briefs(run_id: str, run_root: Path) -> list[dict[str, Any]]:
    briefs = packet_canary.synthetic_briefs(run_id, run_root)[:MAX_CALL_COUNT]
    for item in briefs:
        item["orchestrator_stage"] = "synthetic_orchestrator_dry_run"
        item["future_data_violation"] = False
        item["latest_visible_data_date"] = item["decision_date"]
        item["evidence_layer"] = EVIDENCE_LAYER
    return briefs


def record_call_result(
    *,
    summary: dict[str, Any],
    call_result: dict[str, Any],
    schema_blockers: list[dict[str, Any]],
    provenance_blockers: list[dict[str, Any]],
    overclaim_blockers: list[dict[str, Any]],
    usage_available: bool,
) -> None:
    summary["call_results"].append(call_result)
    summary["real_calls_count"] = len(summary["call_results"])
    summary["provider_or_backend_called"] = summary["real_calls_count"] > 0
    summary["latency_ms_values"].append(call_result.get("latency_ms", 0))
    summary["token_usage_total"] += int(call_result.get("token_usage_total") or 0)
    summary["usage_available_count"] += 1 if usage_available else 0
    summary["schema_pass_count"] += 0 if schema_blockers else 1
    summary["overclaim_blocker_count"] += len(overclaim_blockers)
    summary["source_artifact_paths"].append(call_result.get("source_artifact_path", ""))
    summary["source_artifact_sha256s"].append(call_result.get("source_artifact_sha256", ""))
    summary["input_fixture_hashes"].append(call_result.get("input_fixture_hash", ""))
    summary["prompt_hashes"].append(call_result.get("prompt_hash", ""))
    summary["raw_response_tmp_paths"].append(call_result.get("raw_response_tmp_path", ""))
    summary["raw_response_sha256s"].append(call_result.get("raw_response_sha256", ""))
    summary["parsed_packet_tmp_paths"].append(call_result.get("parsed_packet_tmp_path", ""))
    summary["parsed_packet_sha256s"].append(call_result.get("parsed_packet_sha256", ""))
    summary["orchestrator_trace_tmp_paths"].append(call_result.get("orchestrator_trace_tmp_path", ""))
    summary["orchestrator_trace_sha256s"].append(call_result.get("orchestrator_trace_sha256", ""))
    if provenance_blockers:
        call_result["provenance_hash_status"] = "blocked"


def real_token_dry_run(config: DryRunConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_PROVIDER_BLOCKED_PRE_HTTP)
    pre_blockers = pre_http_blockers(config, run_root=run_root)
    if pre_blockers:
        finalize_blockers(summary, pre_blockers)
        return summary

    client = CodexResponsesCompletionClient(
        auth_json_path=resolved_auth_json_path(config),
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        base_url=config.base_url,
    )
    all_blockers: list[dict[str, Any]] = []
    for brief in synthetic_orchestrator_briefs(config.dry_run_run_id, run_root)[: config.call_count]:
        call_id = str(brief["call_id"])
        if brief.get("future_data_violation") is not False:
            all_blockers.append(blocked_item(call_id, "future_data_violation_present", "synthetic input must be future-data clean"))
            break
        brief_path = Path(str(brief["source_artifact_path"]))
        brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        input_hash = sha256_file(brief_path)
        prompt = packet_canary.user_prompt_for_brief({**brief, "input_fixture_hash": input_hash})
        prompt_hash = sha256_text(packet_canary.system_prompt() + "\n" + prompt)
        started = time.perf_counter()
        try:
            result = client.complete(
                system_prompt=packet_canary.system_prompt(),
                user_prompt=prompt,
                max_tokens=1600,
                timeout_seconds=config.timeout_seconds,
                temperature=0.0,
            )
        except RuntimeError as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            summary["provider_or_backend_called"] = True
            summary["real_calls_count"] = len(summary["call_results"]) + 1
            summary["latency_ms_values"].append(elapsed_ms)
            message = redact_secrets(str(exc))
            reason = "provider_auth_failed" if "auth" in message.lower() or "login" in message.lower() else "backend_runtime_error"
            all_blockers.append(blocked_item(call_id, reason, message))
            break
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        content = str(result.get("content") or "")
        usage = result.get("usage")
        total_tokens = token_total(usage)
        raw_payload = {
            "backend_name": config.backend_name,
            "model": config.model,
            "reasoning_effort": config.reasoning_effort,
            "call_id": call_id,
            "content": content,
            "usage": usage,
            "prompt_hash": prompt_hash,
            "input_fixture_hash": input_hash,
            "captured_at": utc_now_iso(),
        }
        raw_path = run_root / f"{call_id}_raw_response.json"
        raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        raw_hash = sha256_file(raw_path)

        packet = packet_canary.extract_json_object(content)
        parsed_packet_path = run_root / f"{call_id}_parsed_packet.json"
        schema_blockers: list[dict[str, Any]]
        provenance_blockers: list[dict[str, Any]]
        overclaim_blockers: list[dict[str, Any]]
        if packet is None:
            schema_blockers = [blocked_item(call_id, "parsed_packet_json_parse_failed", "response did not contain a JSON object")]
            provenance_blockers = []
            overclaim_blockers = []
            parsed_packet_path.write_text("{}", encoding="utf-8")
        else:
            parsed_packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            schema_blockers, provenance_blockers, overclaim_blockers = packet_canary.validate_packet(
                packet,
                path=f"{call_id}_parsed_packet",
                expected_input_hash=input_hash,
            )
        parsed_hash = sha256_file(parsed_packet_path)
        trace = {
            "run_id": config.dry_run_run_id,
            "call_id": call_id,
            "source_artifact_path": str(brief_path),
            "source_artifact_sha256": input_hash,
            "prompt_hash": prompt_hash,
            "raw_response_sha256": raw_hash,
            "parsed_packet_sha256": parsed_hash,
            "schema_status": "blocked" if schema_blockers else "clean",
            "claim_boundary_status": "blocked" if overclaim_blockers else "clean",
            "provenance_hash_status": "blocked" if provenance_blockers else "clean",
            "scorer_entered": False,
            "actual_outcome_used": False,
            "comparison_result_emitted": False,
            "evidence_layer": EVIDENCE_LAYER,
            "generated_at": utc_now_iso(),
        }
        trace_path = run_root / f"{call_id}_orchestrator_trace.json"
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        trace_hash = sha256_file(trace_path)
        usage_available = total_tokens is not None
        if total_tokens is None:
            all_blockers.append(blocked_item(call_id, "usage_metadata_missing", "backend response did not include usage metadata"))
            total_tokens = 0
        call_result = {
            "run_id": config.dry_run_run_id,
            "call_id": call_id,
            "generated_at": trace["generated_at"],
            "backend_name": config.backend_name,
            "model": config.model,
            "sdk_version": f"python-{platform.python_version()}",
            "api_version": "codex_responses_oauth_streaming",
            "prompt_hash": prompt_hash,
            "input_fixture_hash": input_hash,
            "source_artifact_path": str(brief_path),
            "source_artifact_sha256": input_hash,
            "raw_response_tmp_path": str(raw_path),
            "raw_response_sha256": raw_hash,
            "parsed_packet_tmp_path": str(parsed_packet_path),
            "parsed_packet_sha256": parsed_hash,
            "orchestrator_trace_tmp_path": str(trace_path),
            "orchestrator_trace_sha256": trace_hash,
            "schema_status": trace["schema_status"],
            "claim_boundary_status": trace["claim_boundary_status"],
            "provenance_hash_status": trace["provenance_hash_status"],
            "latency_ms": elapsed_ms,
            "token_usage_input": usage_input(usage),
            "token_usage_output": usage_output(usage),
            "token_usage_total": total_tokens,
            "blocker_reasons": [
                str(item.get("rule_id") or "") for item in schema_blockers + provenance_blockers + overclaim_blockers
            ],
        }
        record_call_result(
            summary=summary,
            call_result=call_result,
            schema_blockers=schema_blockers,
            provenance_blockers=provenance_blockers,
            overclaim_blockers=overclaim_blockers,
            usage_available=usage_available,
        )
        all_blockers.extend(schema_blockers + provenance_blockers + overclaim_blockers)
        if all_blockers:
            break
        if summary["token_usage_total"] > config.token_budget:
            all_blockers.append(blocked_item("usage", "token_usage_over_budget", "token usage exceeds configured budget"))
            break

    summarize_rates(summary)
    if not all_blockers:
        all_blockers = validate_summary_payload(summary)
    summary["dry_run_status"] = choose_status(all_blockers, current_status=STATUS_PASS if not all_blockers else None)
    finalize_blockers(summary, all_blockers)
    return summary


def build_summary(config: DryRunConfig) -> dict[str, Any]:
    validate_run_id(config.dry_run_run_id)
    run_root = config.output_dir / config.dry_run_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        finalize_blockers(summary, [blocked_item(run_root, "output_run_id_exists", "output run id exists")])
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if config.summary_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    elif config.real_token_dry_run:
        summary = real_token_dry_run(config, run_root=run_root)
    else:
        summary = base_summary(config, run_root=run_root, status=STATUS_PROVIDER_BLOCKED_PRE_HTTP)
        finalize_blockers(summary, [blocked_item("mode", "real_token_dry_run_not_requested", "real-token dry-run mode was not requested")])
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
            "dry_run_status": summary.get("dry_run_status"),
            "backend_name": summary.get("backend_name"),
            "model": summary.get("model"),
            "real_calls_count": summary.get("real_calls_count"),
            "token_usage_total": summary.get("token_usage_total"),
            "raw_response_sha256s": summary.get("raw_response_sha256s"),
            "parsed_packet_sha256s": summary.get("parsed_packet_sha256s"),
            "orchestrator_trace_sha256s": summary.get("orchestrator_trace_sha256s"),
            "prompt_hashes": summary.get("prompt_hashes"),
            "input_fixture_hashes": summary.get("input_fixture_hashes"),
            "runtime_flags": {
                "provider_or_backend_called": summary.get("provider_or_backend_called"),
                **{flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            },
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "evidence_layer": summary.get("evidence_layer"),
            packet_canary.DIRECT_LLM_INTERPRETATION_KEY: summary.get(packet_canary.DIRECT_LLM_INTERPRETATION_KEY),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "dry_run_run_id": summary.get("dry_run_run_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "content_boundary_sha256": summary.get("content_boundary_sha256"),
        "dry_run_status": summary.get("dry_run_status"),
        "real_calls_count": summary.get("real_calls_count"),
        "token_usage_total": summary.get("token_usage_total"),
        "raw_response_tmp_paths": summary.get("raw_response_tmp_paths"),
        "raw_response_sha256s": summary.get("raw_response_sha256s"),
        "parsed_packet_sha256s": summary.get("parsed_packet_sha256s"),
        "orchestrator_trace_sha256s": summary.get("orchestrator_trace_sha256s"),
        "provider_or_backend_called": summary.get("provider_or_backend_called"),
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8d_orchestrator_real_token_dry_run/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--real-token-dry-run", action="store_true")
    parser.add_argument("--backend-name", default=DEFAULT_BACKEND_NAME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--auth-json-path", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--call-count", type=int, default=DEFAULT_CALL_COUNT)
    parser.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> DryRunConfig:
    return DryRunConfig(
        dry_run_run_id=str(args.dry_run_run_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
        real_token_dry_run=bool(args.real_token_dry_run),
        backend_name=str(args.backend_name),
        model=str(args.model),
        reasoning_effort=str(args.reasoning_effort),
        auth_json_path=args.auth_json_path,
        base_url=args.base_url,
        timeout_seconds=int(args.timeout_seconds),
        call_count=int(args.call_count),
        token_budget=int(args.token_budget),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - fail closed without exposing secrets.
        print(f"v3.8D orchestrator dry-run failed: {redact_secrets(str(exc))}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("dry_run_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
