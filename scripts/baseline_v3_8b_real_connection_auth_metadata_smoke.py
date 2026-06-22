#!/usr/bin/env python3
"""GOTRA v3.8B bounded real-connection auth and metadata smoke."""

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
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gotra.backtest.codex_responses_client import CodexResponsesCompletionClient  # noqa: E402
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402
from scripts import baseline_v3_7h_claim_boundary_regression as claim_regression  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_8b.real_connection_auth_metadata_smoke_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8b.real_connection_auth_metadata_smoke_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8b_real_connection_auth_metadata_smoke_"
SCRIPT_VERSION = "v3.8b-20260622"
EVIDENCE_LAYER = "engineering_internal_real_connection_auth_metadata_smoke"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_MAX_CALL_COUNT = 2
DEFAULT_TOKEN_BUDGET = 5000
HARD_TOKEN_BUDGET = 100_000

STATUS_READY = "REAL_CONNECTION_AUTH_READY"
STATUS_BLOCKED_PRE_HTTP = "PROVIDER_BLOCKED_PRE_HTTP"
STATUS_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
STATUS_BLOCKED_USAGE_METADATA = "BLOCKED_USAGE_METADATA"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_RUN_ID_EXISTS = "REAL_CONNECTION_AUTH_METADATA_SMOKE_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}
ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_PRE_HTTP,
    STATUS_AUTH_FAILED,
    STATUS_BLOCKED_USAGE_METADATA,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_RUN_ID_EXISTS,
}
ALLOWED_BACKENDS = {DEFAULT_BACKEND_NAME}
FORBIDDEN_BACKEND_RE = re.compile(r"\b(kimi|glm|deepseek)\b", re.IGNORECASE)
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"access[_-]?token['\"]?\s*[:=]\s*['\"][^'\"]+['\"]|"
    r"api[_-]?key['\"]?\s*[:=]\s*['\"][^'\"]+['\"])",
    re.IGNORECASE,
)
RUNTIME_FALSE_FLAGS = (
    "codex_cli_new_call",
    "codex_cli_called",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
TEXT_SCAN_FIELDS = (
    "backend_name",
    "model",
    "auth_status",
    "smoke_status",
    "evidence_layer",
    "non_claims",
    "blocker_reasons",
)


@dataclass(frozen=True)
class SmokeConfig:
    smoke_run_id: str
    output_dir: Path
    allow_overwrite: bool = False
    real_connection: bool = False
    summary_fixture: Path | None = None
    backend_name: str = DEFAULT_BACKEND_NAME
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    auth_json_path: Path | None = None
    base_url: str | None = None
    timeout_seconds: int = 30
    max_call_count: int = DEFAULT_MAX_CALL_COUNT
    token_budget: int = DEFAULT_TOKEN_BUDGET


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"smoke_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("smoke_run_id may contain only letters, numbers, '_' and '-'")


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
    return bool(SECRET_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True)))


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
    if not isinstance(usage, dict):
        return None
    for key in ("total_tokens", "total", "tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if isinstance(input_tokens, int) and isinstance(output_tokens, int) and input_tokens >= 0 and output_tokens >= 0:
        return input_tokens + output_tokens
    return None


def usage_input(usage: Any) -> int | None:
    return usage.get("input_tokens") if isinstance(usage, dict) and isinstance(usage.get("input_tokens"), int) else None


def usage_output(usage: Any) -> int | None:
    return usage.get("output_tokens") if isinstance(usage, dict) and isinstance(usage.get("output_tokens"), int) else None


def output_path(run_root: Path, name: str) -> Path:
    return run_root / name


def base_summary(config: SmokeConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "smoke_run_id": config.smoke_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "smoke_status": status,
        "validation_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "backend_name": config.backend_name,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "api_client": "gotra.backtest.codex_responses_client.CodexResponsesCompletionClient",
        "api_version": "codex_responses_oauth_streaming",
        "sdk_version": f"python-{platform.python_version()}",
        "auth_status": "not_checked",
        "latency_ms": None,
        "usage_metadata_available": False,
        "prompt_input_hash": "",
        "response_output_hash": "",
        "raw_response_tmp_path": "",
        "raw_response_sha256": "",
        "call_count": 0,
        "max_call_count": config.max_call_count,
        "token_usage_input": 0,
        "token_usage_output": 0,
        "token_usage_total": 0,
        "token_budget": config.token_budget,
        "blocker_reasons": [],
        "blocked_items": [],
        "runtime_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "secret_boundary_status": "clean",
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "evidence_layer": EVIDENCE_LAYER,
        "non_claims": {
            "not_research_packet": True,
            "not_provider_canary_result": True,
            "not_actual_verdict": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
    }


def load_summary_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "forbidden_summary_fixture_path", "summary fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [blocked_item(path, "summary_fixture_read_error", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [blocked_item(path, "summary_fixture_json_decode_error", str(exc))]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "summary_fixture_root_not_object", "summary fixture must be a JSON object")]
    return payload, []


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = summary.get("smoke_status")
    if status not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary", "invalid_smoke_status", "smoke_status is not allowed"))
    backend = str(summary.get("backend_name") or "")
    if backend not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(backend):
        blockers.append(blocked_item("summary.backend_name", "backend_not_allowed", "backend is not allowed for v3.8B"))
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("v3_7_actual_verdict_executable") is not False or summary.get("v3_7_actual_verdict_executed") is not False:
        blockers.append(blocked_item("summary", "actual_verdict_flags_not_false", "actual verdict flags must remain false"))
    for flag in RUNTIME_FALSE_FLAGS:
        if summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false"))
    call_count = summary.get("call_count")
    if not isinstance(call_count, int) or call_count < 0:
        blockers.append(blocked_item("summary.call_count", "call_count_invalid", "call_count must be a non-negative integer"))
    elif call_count > DEFAULT_MAX_CALL_COUNT or call_count > int(summary.get("max_call_count") or DEFAULT_MAX_CALL_COUNT):
        blockers.append(blocked_item("summary.call_count", "call_count_over_budget", "call_count exceeds budget"))
    token_usage_total = summary.get("token_usage_total")
    if not isinstance(token_usage_total, int) or token_usage_total < 0:
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_invalid", "token_usage_total must be a non-negative integer"))
    elif token_usage_total > HARD_TOKEN_BUDGET or token_usage_total > int(summary.get("token_budget") or DEFAULT_TOKEN_BUDGET):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_over_budget", "token usage exceeds budget"))
    if summary.get("provider_or_backend_called") is True and call_count == 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_without_call_count", "called flag requires call_count > 0"))
    if status == STATUS_READY:
        if summary.get("provider_or_backend_called") is not True or call_count < 1:
            blockers.append(blocked_item("summary", "ready_without_real_call", "READY requires one bounded real call"))
        if summary.get("usage_metadata_available") is not True:
            blockers.append(blocked_item("summary.usage_metadata_available", "usage_metadata_missing", "READY requires usage metadata"))
        if not is_non_empty_string(summary.get("raw_response_tmp_path")) or not under_tmp(str(summary.get("raw_response_tmp_path"))):
            blockers.append(blocked_item("summary.raw_response_tmp_path", "raw_response_path_not_tmp", "raw response path must be under /tmp"))
        if not is_non_empty_string(summary.get("raw_response_sha256")):
            blockers.append(blocked_item("summary.raw_response_sha256", "raw_response_hash_missing", "raw response hash is required"))
    if is_non_empty_string(summary.get("raw_response_tmp_path")) and not under_tmp(str(summary.get("raw_response_tmp_path"))):
        blockers.append(blocked_item("summary.raw_response_tmp_path", "raw_response_path_not_tmp", "raw response path must be under /tmp"))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_regression.claim_blockers({field: summary.get(field) for field in TEXT_SCAN_FIELDS}, path="summary"))
    return blockers


def choose_status(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return str(summary.get("smoke_status") or STATUS_BLOCKED_RUNTIME_BOUNDARY)
    reasons = {str(item.get("rule_id")) for item in blockers}
    if "usage_metadata_missing" in reasons:
        return STATUS_BLOCKED_USAGE_METADATA
    if any("auth" in reason for reason in reasons) and summary.get("provider_or_backend_called"):
        return STATUS_AUTH_FAILED
    return STATUS_BLOCKED_RUNTIME_BOUNDARY


def build_from_fixture(config: SmokeConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    summary = base_summary(config, run_root=run_root, status=str(payload.get("smoke_status") or STATUS_BLOCKED_RUNTIME_BOUNDARY) if payload else STATUS_BLOCKED_RUNTIME_BOUNDARY)
    if payload:
        summary.update(payload)
    blockers = load_blockers + validate_summary_payload(summary)
    status = choose_status(summary, blockers)
    summary["smoke_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def pre_http_auth_blockers(config: SmokeConfig) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if config.backend_name not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(config.backend_name):
        blockers.append(blocked_item("backend", "backend_not_allowed", "backend is not allowed for v3.8B"))
    if config.max_call_count > DEFAULT_MAX_CALL_COUNT:
        blockers.append(blocked_item("config.max_call_count", "max_call_count_over_budget", "max_call_count exceeds v3.8B limit"))
    if config.token_budget > HARD_TOKEN_BUDGET:
        blockers.append(blocked_item("config.token_budget", "token_budget_over_hard_limit", "token_budget exceeds hard limit"))
    auth_path = (config.auth_json_path or Path("~/.codex/auth.json")).expanduser()
    if not auth_path.exists():
        blockers.append(blocked_item("auth", "auth_json_not_found", "Codex OAuth auth file is not available"))
    elif claim_scan.forbidden_path(normalize_path(auth_path)):
        blockers.append(blocked_item("auth", "auth_json_path_forbidden", "auth path is forbidden"))
    return blockers


def real_connection_smoke(config: SmokeConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_PRE_HTTP)
    pre_blockers = pre_http_auth_blockers(config)
    if pre_blockers:
        finalize_blockers(summary, pre_blockers)
        return summary

    prompt = (
        "Return exactly this compact JSON object and nothing else: "
        "{\"gotra_v3_8b_auth_metadata_smoke\":true}"
    )
    prompt_hash = sha256_text(prompt)
    client = CodexResponsesCompletionClient(
        auth_json_path=config.auth_json_path,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        base_url=config.base_url,
    )
    started = time.perf_counter()
    try:
        result = client.complete(
            system_prompt="You are a bounded metadata smoke responder. Do not provide advice.",
            user_prompt=prompt,
            max_tokens=64,
            timeout_seconds=config.timeout_seconds,
            temperature=0.0,
        )
    except RuntimeError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = redact_secrets(str(exc))
        status = STATUS_AUTH_FAILED if "authentication failed" in message.lower() or "codex login" in message.lower() else STATUS_BLOCKED_RUNTIME_BOUNDARY
        summary.update(
            {
                "smoke_status": status,
                "auth_status": "failed" if status == STATUS_AUTH_FAILED else "runtime_blocked",
                "latency_ms": elapsed_ms,
                "provider_or_backend_called": True,
                "call_count": 1,
            }
        )
        finalize_blockers(summary, [blocked_item("backend", status.lower(), message)])
        return summary

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    content = str(result.get("content") or "")
    usage = result.get("usage")
    total_tokens = token_total(usage)
    raw_payload = {
        "backend_name": config.backend_name,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "content": content,
        "usage": usage,
        "prompt_input_hash": prompt_hash,
        "captured_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    raw_path = output_path(run_root, "raw_response_metadata.json")
    raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary.update(
        {
            "smoke_status": STATUS_READY,
            "auth_status": "authenticated",
            "latency_ms": elapsed_ms,
            "usage_metadata_available": total_tokens is not None,
            "prompt_input_hash": prompt_hash,
            "response_output_hash": sha256_text(content),
            "raw_response_tmp_path": str(raw_path),
            "raw_response_sha256": sha256_file(raw_path),
            "call_count": 1,
            "token_usage_input": usage_input(usage) or 0,
            "token_usage_output": usage_output(usage) or 0,
            "token_usage_total": total_tokens or 0,
            "provider_or_backend_called": True,
        }
    )
    blockers = validate_summary_payload(summary)
    if total_tokens is None:
        blockers.append(blocked_item("usage", "usage_metadata_missing", "backend response did not include usage metadata"))
    if total_tokens is not None and total_tokens > config.token_budget:
        blockers.append(blocked_item("usage", "token_usage_over_budget", "token usage exceeds configured budget"))
    if blockers:
        status = choose_status(summary, blockers)
        summary["smoke_status"] = status
        finalize_blockers(summary, blockers)
    return summary


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:100]
    summary["blocker_reasons"] = [str(item.get("rule_id")) for item in blockers]
    summary["runtime_boundary_status"] = "blocked" if blockers else "clean"
    summary["claim_boundary_status"] = "blocked" if any("claim" in str(item.get("rule_id")) or "overclaim" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any("path" in str(item.get("rule_id")) or "artifact" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["secret_boundary_status"] = "blocked" if any("secret" in str(item.get("rule_id")) for item in blockers) else "clean"


def build_summary(config: SmokeConfig) -> dict[str, Any]:
    validate_run_id(config.smoke_run_id)
    run_root = config.output_dir / config.smoke_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        finalize_blockers(summary, [blocked_item(run_root, "output_run_id_exists", "output run id exists")])
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if config.summary_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    elif config.real_connection:
        summary = real_connection_smoke(config, run_root=run_root)
    else:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_PRE_HTTP)
        finalize_blockers(summary, [blocked_item("mode", "real_connection_not_requested", "real connection mode was not requested")])
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary["content_boundary_sha256"] = stable_sha256_json(
        {
            "smoke_status": summary.get("smoke_status"),
            "backend_name": summary.get("backend_name"),
            "model": summary.get("model"),
            "call_count": summary.get("call_count"),
            "token_usage_total": summary.get("token_usage_total"),
            "prompt_input_hash": summary.get("prompt_input_hash"),
            "response_output_hash": summary.get("response_output_hash"),
            "runtime_flags": {flag: summary.get(flag) for flag in ("provider_or_backend_called", *RUNTIME_FALSE_FLAGS)},
            "evidence_layer": summary.get("evidence_layer"),
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "smoke_run_id": summary.get("smoke_run_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "content_boundary_sha256": summary.get("content_boundary_sha256"),
        "smoke_status": summary.get("smoke_status"),
        "provider_or_backend_called": summary.get("provider_or_backend_called"),
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8b_real_connection_auth_metadata_smoke/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--real-connection", action="store_true")
    parser.add_argument("--backend-name", default=DEFAULT_BACKEND_NAME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--auth-json-path", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--max-call-count", type=int, default=DEFAULT_MAX_CALL_COUNT)
    parser.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> SmokeConfig:
    return SmokeConfig(
        smoke_run_id=str(args.smoke_run_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        real_connection=bool(args.real_connection),
        summary_fixture=args.summary_fixture,
        backend_name=str(args.backend_name),
        model=str(args.model),
        reasoning_effort=str(args.reasoning_effort),
        auth_json_path=args.auth_json_path,
        base_url=args.base_url,
        timeout_seconds=int(args.timeout_seconds),
        max_call_count=int(args.max_call_count),
        token_budget=int(args.token_budget),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - fail closed without exposing secrets.
        print(f"v3.8B real-connection metadata smoke failed: {redact_secrets(str(exc))}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("smoke_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
