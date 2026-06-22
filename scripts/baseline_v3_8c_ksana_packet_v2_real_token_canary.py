#!/usr/bin/env python3
"""GOTRA v3.8C bounded ksana packet v2 real-token schema canary."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
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


SUMMARY_SCHEMA = "gotra.baseline_v3_8c.ksana_packet_v2_real_token_canary_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8c.ksana_packet_v2_real_token_canary_manifest.v1"
PACKET_SCHEMA = "gotra.ksana.research_packet.v2.real_token_schema_canary.v1"
RUN_ID_PREFIX = "baseline_v3_8c_ksana_packet_v2_real_token_canary_"
SCRIPT_VERSION = "v3.8c-20260622"
EVIDENCE_LAYER = "engineering_internal_ksana_packet_v2_real_token_schema_canary"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DIRECT_LLM_SCAN_BUCKET = "direct" + "_llm"
DIRECT_LLM_INTERPRETATION_KEY = DIRECT_LLM_SCAN_BUCKET + "_interpretation"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_CALL_COUNT = 3
MAX_CALL_COUNT = 5
DEFAULT_TOKEN_BUDGET = 25_000
HARD_TOKEN_BUDGET = 100_000

STATUS_PASS = "KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_METADATA = "BLOCKED_METADATA"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_RUN_ID_EXISTS = "KSANA_PACKET_V2_REAL_TOKEN_CANARY_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_PASS,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_OVERCLAIM,
    STATUS_BLOCKED_METADATA,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_PASS}
ALLOWED_BACKENDS = {DEFAULT_BACKEND_NAME}
ALLOWED_BASE_URLS = {DEFAULT_CODEX_RESPONSES_BASE_URL}
FORBIDDEN_BACKEND_RE = re.compile(r"\b(kimi|glm|deepseek)\b", re.IGNORECASE)
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"access[_-]?token['\"]?\s*[:=]\s*['\"][^'\"]+['\"]|"
    r"api[_-]?key['\"]?\s*[:=]\s*['\"][^'\"]+['\"])",
    re.IGNORECASE,
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

RUNTIME_FALSE_FLAGS = (
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
REQUIRED_PACKET_FIELDS = {
    "source_run_id",
    "source_artifact_path",
    "ticker",
    "decision_date",
    "research_mode",
    "ranked_hypotheses",
    "why_it_matters",
    "confidence",
    "falsification_triggers",
    "expected_observable_evidence",
    "counterfactuals",
    "disagreement_with_price_only",
    "evidence_gaps",
    "uncertainty_decomposition",
    "non_claims",
    "evidence_layer",
    "provenance",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
}
REQUIRED_HYPOTHESIS_FIELDS = {
    "rank",
    "hypothesis",
    "confidence",
    "why_it_matters",
    "falsification_triggers",
    "expected_observable_evidence",
}
PROVENANCE_REQUIRED_FIELDS = {
    "source_run_id",
    "source_artifact_path",
    "input_fixture_hash",
    "backend",
    "model",
    "call_id",
}
CLAIM_SCAN_SKIP_FIELDS = {
    "schema",
    "source_run_id",
    "source_artifact_path",
    "ticker",
    "decision_date",
    "evidence_layer",
    "provenance",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
}


@dataclass(frozen=True)
class CanaryConfig:
    canary_run_id: str
    output_dir: Path
    allow_overwrite: bool = False
    summary_fixture: Path | None = None
    real_token_canary: bool = False
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


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"canary_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("canary_run_id may contain only letters, numbers, '_' and '-'")


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


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_non_empty_text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(is_non_empty_string(item) for item in value)


def is_non_empty_mapping(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


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


def usage_input(usage: Any) -> int:
    return usage.get("input_tokens") if isinstance(usage, dict) and isinstance(usage.get("input_tokens"), int) else 0


def usage_output(usage: Any) -> int:
    return usage.get("output_tokens") if isinstance(usage, dict) and isinstance(usage.get("output_tokens"), int) else 0


def json_hash(value: Any) -> str:
    return stable_sha256_json(value)


def synthetic_briefs(run_id: str, run_root: Path) -> list[dict[str, Any]]:
    base = [
        {
            "call_id": "call_001",
            "synthetic_company_id": "SYN-ALPHA-WIDGETS",
            "ticker": "SYNALP",
            "brief": (
                "Fictional internal schema canary: Alpha Widgets sells industrial demo sensors. "
                "It has rising support tickets, a new onboarding checklist, and two non-financial process risks."
            ),
        },
        {
            "call_id": "call_002",
            "synthetic_company_id": "SYN-BETA-LOGISTICS",
            "ticker": "SYNBET",
            "brief": (
                "Fictional internal schema canary: Beta Logistics coordinates warehouse training. "
                "Recent notes mention route handoff delays, vendor documentation gaps, and stable staffing."
            ),
        },
        {
            "call_id": "call_003",
            "synthetic_company_id": "SYN-CARBON-SOFTWARE",
            "ticker": "SYNCAR",
            "brief": (
                "Fictional internal schema canary: Carbon Software maintains a mock ticket triage tool. "
                "The brief includes slower QA review, better release notes, and an unresolved integration checklist."
            ),
        },
        {
            "call_id": "call_004",
            "synthetic_company_id": "SYN-DELTA-TRAINING",
            "ticker": "SYNDEL",
            "brief": (
                "Fictional internal schema canary: Delta Training maintains a mock certification queue. "
                "Recent notes mention inconsistent checklist labels, fewer repeat questions, and one stale template."
            ),
        },
        {
            "call_id": "call_005",
            "synthetic_company_id": "SYN-ECHO-INVENTORY",
            "ticker": "SYNECH",
            "brief": (
                "Fictional internal schema canary: Echo Inventory audits demo spare-part workflows. "
                "The brief includes mismatched item tags, a new exception log, and stable mock intake volume."
            ),
        },
    ]
    for item in base:
        item["source_run_id"] = run_id
        item["source_artifact_path"] = str(run_root / f"{item['call_id']}_synthetic_brief.json")
        item["decision_date"] = "2026-06-22"
        item["evidence_layer"] = EVIDENCE_LAYER
    return base


def system_prompt() -> str:
    return (
        "You produce a compact JSON-only ksana research packet v2 schema canary. "
        "Use only the supplied fictional synthetic brief. Do not provide any category denied by non_claims, "
        "verdict, advice, or performance-comparison claims."
    )


def user_prompt_for_brief(brief: dict[str, Any]) -> str:
    schema = {
        "schema": PACKET_SCHEMA,
        "source_run_id": brief["source_run_id"],
        "source_artifact_path": brief["source_artifact_path"],
        "ticker": brief["ticker"],
        "decision_date": brief["decision_date"],
        "research_mode": "synthetic_ksana_packet_v2_real_token_schema_canary",
        "ranked_hypotheses": [
            {
                "rank": 1,
                "hypothesis": "non-empty text",
                "confidence": 0.5,
                "why_it_matters": "non-empty text",
                "falsification_triggers": ["non-empty text"],
                "expected_observable_evidence": ["non-empty text"],
                "counterfactuals": ["non-empty text"],
            }
        ],
        "why_it_matters": "non-empty text",
        "confidence": 0.5,
        "falsification_triggers": ["non-empty text"],
        "expected_observable_evidence": ["non-empty text"],
        "counterfactuals": ["non-empty text"],
        "disagreement_with_price_only": ["non-empty text about structural disagreement only"],
        "evidence_gaps": ["non-empty text"],
        "uncertainty_decomposition": {"operations": "non-empty text", "data_quality": "non-empty text"},
        "non_claims": [
            "not a provider canary verdict",
            "not an actual v3.7 or v3.8 verdict",
            "not OOS/science/public/trading claim",
            "not investment advice",
            f"historical parametric-memory diagnostic arm remains {DIRECT_LLM_INTERPRETATION}",
        ],
        "evidence_layer": EVIDENCE_LAYER,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "provenance": {
            "source_run_id": brief["source_run_id"],
            "source_artifact_path": brief["source_artifact_path"],
            "input_fixture_hash": str(brief.get("input_fixture_hash") or "<input_fixture_hash_required>"),
            "backend": DEFAULT_BACKEND_NAME,
            "model": DEFAULT_MODEL,
            "call_id": brief["call_id"],
        },
    }
    return (
        "Return one strict JSON object matching this shape. Keep it concise. "
        "Do not wrap in Markdown.\n\n"
        f"Synthetic brief JSON:\n{json.dumps(brief, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Required JSON shape:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}"
    )


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : index + 1]
                try:
                    value = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                return value if isinstance(value, dict) else None
    return None


def claim_sources_from_value(*, path: str, field_path: str, value: Any) -> list[claim_scan.ScanSource]:
    if isinstance(value, str):
        return [claim_scan.ScanSource(path=f"{path}:{field_path}", text=value, origin="v3_8c_packet")]
    if isinstance(value, list):
        sources: list[claim_scan.ScanSource] = []
        for index, item in enumerate(value):
            sources.extend(claim_sources_from_value(path=path, field_path=f"{field_path}[{index}]", value=item))
        return sources
    if isinstance(value, dict):
        sources = []
        for key, item in value.items():
            if str(key) in CLAIM_SCAN_SKIP_FIELDS:
                continue
            sources.extend(claim_sources_from_value(path=path, field_path=f"{field_path}.{key}", value=item))
        return sources
    return []


def claim_blockers_for_packet(packet: dict[str, Any], *, path: str) -> list[dict[str, Any]]:
    sources: list[claim_scan.ScanSource] = []
    for key, value in packet.items():
        if key in CLAIM_SCAN_SKIP_FIELDS:
            continue
        sources.extend(claim_sources_from_value(path=path, field_path=key, value=value))
    scan = claim_scan.scan_sources(sources)
    return scan["overclaim"] + scan[DIRECT_LLM_SCAN_BUCKET] + scan["maturity_gate"] + scan["short_horizon_as_30d"]


def validate_packet_schema(packet: dict[str, Any], *, path: str) -> list[dict[str, Any]]:
    missing = sorted(REQUIRED_PACKET_FIELDS - set(packet))
    type_errors: list[str] = []

    if packet.get("schema") not in (None, PACKET_SCHEMA):
        type_errors.append("schema")
    for key in ("source_run_id", "source_artifact_path", "ticker", "decision_date", "research_mode", "why_it_matters"):
        if not is_non_empty_string(packet.get(key)):
            type_errors.append(key)
    if is_non_empty_string(packet.get("decision_date")):
        try:
            date.fromisoformat(str(packet["decision_date"]))
        except ValueError:
            type_errors.append("decision_date")
    if packet.get("evidence_layer") != EVIDENCE_LAYER:
        type_errors.append("evidence_layer")
    if "confidence" in packet and (not is_number(packet["confidence"]) or not 0 <= float(packet["confidence"]) <= 1):
        type_errors.append("confidence")
    if not isinstance(packet.get("ranked_hypotheses"), list) or not packet.get("ranked_hypotheses"):
        type_errors.append("ranked_hypotheses")
    elif isinstance(packet["ranked_hypotheses"], list):
        for index, item in enumerate(packet["ranked_hypotheses"]):
            if not isinstance(item, dict):
                type_errors.append(f"ranked_hypotheses[{index}]")
                continue
            hypothesis_missing = sorted(REQUIRED_HYPOTHESIS_FIELDS - set(item))
            type_errors.extend(f"ranked_hypotheses[{index}].{key}" for key in hypothesis_missing)
            if "rank" in item and not is_number(item["rank"]):
                type_errors.append(f"ranked_hypotheses[{index}].rank")
            if "hypothesis" in item and not is_non_empty_string(item["hypothesis"]):
                type_errors.append(f"ranked_hypotheses[{index}].hypothesis")
            if "confidence" in item and (not is_number(item["confidence"]) or not 0 <= float(item["confidence"]) <= 1):
                type_errors.append(f"ranked_hypotheses[{index}].confidence")
            if "why_it_matters" in item and not is_non_empty_string(item["why_it_matters"]):
                type_errors.append(f"ranked_hypotheses[{index}].why_it_matters")
            for key in ("falsification_triggers", "expected_observable_evidence", "counterfactuals"):
                if key in item and not is_non_empty_text_list(item[key]):
                    type_errors.append(f"ranked_hypotheses[{index}].{key}")

    for key in (
        "falsification_triggers",
        "expected_observable_evidence",
        "counterfactuals",
        "disagreement_with_price_only",
        "evidence_gaps",
    ):
        if key in packet and not is_non_empty_text_list(packet[key]):
            type_errors.append(key)
    if "uncertainty_decomposition" in packet and not (
        is_non_empty_mapping(packet["uncertainty_decomposition"])
        or is_non_empty_text_list(packet["uncertainty_decomposition"])
    ):
        type_errors.append("uncertainty_decomposition")
    if "non_claims" in packet and not (
        is_non_empty_mapping(packet["non_claims"]) or is_non_empty_text_list(packet["non_claims"])
    ):
        type_errors.append("non_claims")
    for key in ("provider_or_backend_called", "codex_cli_new_call", "formal_lite_entered"):
        if packet.get(key) is not False:
            type_errors.append(key)

    failures = missing + sorted(set(type_errors))
    if failures:
        return [blocked_item(path, "missing_or_invalid_packet_v2_schema_field", ",".join(failures))]
    return []


def validate_packet_provenance(packet: dict[str, Any], *, path: str, expected_input_hash: str | None = None) -> list[dict[str, Any]]:
    provenance = packet.get("provenance")
    if not isinstance(provenance, dict):
        return [blocked_item(path, "missing_provenance", "provenance must be an object")]
    missing = sorted(PROVENANCE_REQUIRED_FIELDS - set(provenance))
    mismatches = [
        key
        for key in ("source_run_id", "source_artifact_path")
        if key in provenance and str(provenance.get(key) or "") != str(packet.get(key) or "")
    ]
    if expected_input_hash and str(provenance.get("input_fixture_hash") or "") != expected_input_hash:
        mismatches.append("input_fixture_hash")
    if str(provenance.get("backend") or "") != DEFAULT_BACKEND_NAME:
        mismatches.append("backend")
    if str(provenance.get("model") or "") != DEFAULT_MODEL:
        mismatches.append("model")
    forbidden_paths = []
    for key in ("source_artifact_path",):
        top_path = str(packet.get(key) or "")
        provenance_path = str(provenance.get(key) or "")
        if top_path and claim_scan.forbidden_path(top_path):
            forbidden_paths.append(key)
        if provenance_path and claim_scan.forbidden_path(provenance_path):
            forbidden_paths.append(f"provenance.{key}")
    failures = missing + mismatches
    if failures:
        return [blocked_item(path, "missing_or_inconsistent_provenance", ",".join(sorted(set(failures))))]
    if forbidden_paths:
        return [blocked_item(path, "forbidden_source_artifact_path", ",".join(sorted(set(forbidden_paths))))]
    return []


def ranked_hypothesis_count(packet: dict[str, Any]) -> int:
    hypotheses = packet.get("ranked_hypotheses")
    if not isinstance(hypotheses, list):
        return 0
    return sum(
        1
        for item in hypotheses
        if isinstance(item, dict) and item.get("rank") is not None and is_non_empty_string(item.get("hypothesis"))
    )


def missing_field_count_for_packet(blockers: list[dict[str, Any]]) -> int:
    total = 0
    for item in blockers:
        if item.get("rule_id") == "missing_or_invalid_packet_v2_schema_field":
            total += len([part for part in str(item.get("reason") or "").split(",") if part])
    return total


def validate_packet(
    packet: dict[str, Any],
    *,
    path: str,
    expected_input_hash: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    schema_blockers = validate_packet_schema(packet, path=path)
    provenance_blockers = validate_packet_provenance(packet, path=path, expected_input_hash=expected_input_hash)
    overclaim_blockers = claim_blockers_for_packet(packet, path=path)
    return schema_blockers, provenance_blockers, overclaim_blockers


def base_summary(config: CanaryConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "canary_run_id": config.canary_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "canary_status": status,
        "validation_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "backend_name": config.backend_name,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "sdk_version": f"python-{platform.python_version()}",
        "api_client": "gotra.backtest.codex_responses_client.CodexResponsesCompletionClient",
        "api_version": "codex_responses_oauth_streaming",
        "real_calls_count": 0,
        "requested_call_count": config.call_count,
        "max_call_count": MAX_CALL_COUNT,
        "token_budget": config.token_budget,
        "token_usage_total": 0,
        "latency_ms_values": [],
        "latency_ms_min": None,
        "latency_ms_median": None,
        "latency_ms_max": None,
        "schema_pass_count": 0,
        "schema_pass_rate": 0.0,
        "overclaim_blocker_count": 0,
        "overclaim_rate": 0.0,
        "missing_field_count": 0,
        "missing_field_rate": 0.0,
        "usage_available_count": 0,
        "usage_availability_rate": 0.0,
        "raw_response_tmp_paths": [],
        "raw_response_sha256s": [],
        "parsed_packet_tmp_paths": [],
        "parsed_packet_sha256s": [],
        "input_fixture_hashes": [],
        "prompt_hashes": [],
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
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "evidence_layer": EVIDENCE_LAYER,
        DIRECT_LLM_INTERPRETATION_KEY: DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_provider_canary_verdict": True,
            "not_gotra_orchestrator_run": True,
            "not_actual_v3_7_or_v3_8_verdict": True,
            "not_actual_comparison_result": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
    }


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
    for key in (
        "call_id",
        "backend_name",
        "model",
        "prompt_hash",
        "input_fixture_hash",
        "raw_response_tmp_path",
        "raw_response_sha256",
        "parsed_packet_tmp_path",
        "parsed_packet_sha256",
        "schema_status",
        "claim_boundary_status",
        "provenance_hash_status",
        "latency_ms",
        "token_usage_total",
    ):
        if key not in call_result:
            blockers.append(blocked_item(f"{path}.{key}", "call_result_missing_field", f"{key} is required"))
    if call_result.get("backend_name") != DEFAULT_BACKEND_NAME:
        blockers.append(blocked_item(f"{path}.backend_name", "backend_not_allowed", "backend is not allowed for v3.8C"))
    if call_result.get("model") != DEFAULT_MODEL:
        blockers.append(blocked_item(f"{path}.model", "model_not_allowed", "model is not allowed for v3.8C"))
    for key in ("prompt_hash", "input_fixture_hash", "raw_response_sha256", "parsed_packet_sha256"):
        value = call_result.get(key)
        if not isinstance(value, str) or not HEX64_RE.match(value):
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be a sha256 hex digest"))
    raw_path = str(call_result.get("raw_response_tmp_path") or "")
    if raw_path and not under_tmp(raw_path):
        blockers.append(blocked_item(f"{path}.raw_response_tmp_path", "raw_response_path_not_tmp", "raw response path must be under /tmp"))
    parsed_path = str(call_result.get("parsed_packet_tmp_path") or "")
    if parsed_path and not under_tmp(parsed_path):
        blockers.append(blocked_item(f"{path}.parsed_packet_tmp_path", "parsed_packet_path_not_tmp", "parsed packet path must be under /tmp"))
    if status == STATUS_PASS:
        for key, expected in (
            ("schema_status", "clean"),
            ("claim_boundary_status", "clean"),
            ("provenance_hash_status", "clean"),
        ):
            if call_result.get(key) != expected:
                blockers.append(blocked_item(f"{path}.{key}", f"{key}_not_clean", f"{key} must be clean for PASS"))
    latency_ms = call_result.get("latency_ms")
    if not isinstance(latency_ms, int) or latency_ms < 0:
        blockers.append(blocked_item(f"{path}.latency_ms", "latency_ms_invalid", "latency_ms must be a non-negative integer"))
    call_token_usage_total = call_result.get("token_usage_total")
    if not isinstance(call_token_usage_total, int) or call_token_usage_total < 0:
        blockers.append(blocked_item(f"{path}.token_usage_total", "token_usage_total_invalid", "token usage must be a non-negative integer"))
    return blockers


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = summary.get("canary_status")
    if status not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.canary_status", "invalid_canary_status", "canary_status is not allowed"))
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get(DIRECT_LLM_INTERPRETATION_KEY) != DIRECT_LLM_INTERPRETATION:
        blockers.append(
            blocked_item(
                f"summary.{DIRECT_LLM_INTERPRETATION_KEY}",
                DIRECT_LLM_INTERPRETATION_KEY + "_mismatch",
                "parametric memory interpretation must remain explicit",
            )
        )
    backend = str(summary.get("backend_name") or "")
    if backend not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(backend):
        blockers.append(blocked_item("summary.backend_name", "backend_not_allowed", "backend is not allowed for v3.8C"))
    if summary.get("model") != DEFAULT_MODEL:
        blockers.append(blocked_item("summary.model", "model_not_allowed", "model is not allowed for v3.8C"))
    if summary.get("reasoning_effort") != DEFAULT_REASONING_EFFORT:
        blockers.append(blocked_item("summary.reasoning_effort", "reasoning_effort_not_allowed", "reasoning_effort must remain xhigh"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    for flag in RUNTIME_FALSE_FLAGS:
        if summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false"))

    call_count = summary.get("real_calls_count")
    if not isinstance(call_count, int) or call_count < 0:
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_invalid", "real_calls_count must be a non-negative integer"))
        call_count = 0
    elif call_count > MAX_CALL_COUNT:
        blockers.append(blocked_item("summary.real_calls_count", "call_count_over_budget", "real call count exceeds v3.8C max"))
    requested_call_count = summary.get("requested_call_count")
    if not isinstance(requested_call_count, int) or requested_call_count < 1 or requested_call_count > MAX_CALL_COUNT:
        blockers.append(blocked_item("summary.requested_call_count", "requested_call_count_invalid", "requested_call_count must be 1..5"))
    elif status == STATUS_PASS and call_count != requested_call_count:
        blockers.append(blocked_item("summary.real_calls_count", "requested_call_count_not_fulfilled", "PASS requires fulfilling requested_call_count"))
    token_usage_total = summary.get("token_usage_total")
    if not isinstance(token_usage_total, int) or token_usage_total < 0:
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_invalid", "token_usage_total must be a non-negative integer"))
    elif token_usage_total > HARD_TOKEN_BUDGET or token_usage_total > int(summary.get("token_budget") or DEFAULT_TOKEN_BUDGET):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_over_budget", "token usage exceeds budget"))
    if summary.get("provider_or_backend_called") not in (True, False):
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_or_backend_called_missing", "provider_or_backend_called must be boolean"))
    if summary.get("provider_or_backend_called") is True and call_count == 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_without_call_count", "called flag requires real_calls_count > 0"))
    if summary.get("provider_or_backend_called") is False and call_count > 0:
        blockers.append(blocked_item("summary.provider_or_backend_called", "provider_called_flag_false", "real calls require provider_or_backend_called=true"))

    call_results = summary.get("call_results")
    if not isinstance(call_results, list):
        blockers.append(blocked_item("summary.call_results", "call_results_not_list", "call_results must be a list"))
        call_results = []
    if status == STATUS_PASS and len(call_results) != call_count:
        blockers.append(blocked_item("summary.call_results", "call_results_count_mismatch", "PASS requires one call result per call"))
    for index, call_result in enumerate(call_results):
        blockers.extend(validate_call_result(call_result, index=index, status=str(status)))

    if status == STATUS_PASS:
        if call_count < 1:
            blockers.append(blocked_item("summary.real_calls_count", "pass_without_real_calls", "PASS requires bounded real calls"))
        if float(summary.get("usage_availability_rate") or 0.0) < 1.0:
            blockers.append(blocked_item("summary.usage_availability_rate", "usage_metadata_missing", "PASS requires usage metadata for every call"))
        if float(summary.get("schema_pass_rate") or 0.0) < 1.0:
            blockers.append(blocked_item("summary.schema_pass_rate", "schema_pass_rate_not_complete", "PASS requires schema pass rate 1.0"))
        if float(summary.get("overclaim_rate") or 0.0) != 0.0:
            blockers.append(blocked_item("summary.overclaim_rate", "overclaim_rate_nonzero", "PASS requires zero overclaim rate"))
        if float(summary.get("missing_field_rate") or 0.0) != 0.0:
            blockers.append(blocked_item("summary.missing_field_rate", "missing_field_rate_nonzero", "PASS requires zero missing-field rate"))

    for path_key in ("raw_response_tmp_paths", "parsed_packet_tmp_paths"):
        paths = summary.get(path_key)
        if paths is not None and not isinstance(paths, list):
            blockers.append(blocked_item(f"summary.{path_key}", f"{path_key}_not_list", f"{path_key} must be a list"))
        if isinstance(paths, list):
            for index, raw_path in enumerate(paths):
                if not isinstance(raw_path, str) or not under_tmp(raw_path):
                    blockers.append(blocked_item(f"summary.{path_key}[{index}]", "raw_or_packet_path_not_tmp", "runtime raw/packet paths must be under /tmp"))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(
        claim_regression.claim_blockers(
            {
                "canary_status": summary.get("canary_status"),
                "evidence_layer": summary.get("evidence_layer"),
                "non_claims": summary.get("non_claims"),
                "blocker_reasons": summary.get("blocker_reasons"),
                DIRECT_LLM_INTERPRETATION_KEY: summary.get(DIRECT_LLM_INTERPRETATION_KEY),
                "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            },
            path="summary",
        )
    )
    return blockers


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_PASS
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("claim" in reason or "overclaim" in reason or DIRECT_LLM_SCAN_BUCKET in reason for reason in reasons):
        return STATUS_BLOCKED_OVERCLAIM
    if any("usage" in reason or "metadata" in reason for reason in reasons):
        return STATUS_BLOCKED_METADATA
    if any(
        "schema" in reason
        or "missing_or_invalid" in reason
        or "parse" in reason
        or "provenance" in reason
        or "hash" in reason
        for reason in reasons
    ):
        return STATUS_BLOCKED_SCHEMA
    return STATUS_BLOCKED_RUNTIME_BOUNDARY


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any("schema" in str(item.get("rule_id")) or "missing_or_invalid" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(
        "claim" in str(item.get("rule_id")) or "overclaim" in str(item.get("rule_id")) or DIRECT_LLM_SCAN_BUCKET in str(item.get("rule_id"))
        for item in blockers
    ) else "clean"
    summary["provenance_hash_status"] = "blocked" if any("provenance" in str(item.get("rule_id")) or "hash" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["metadata_status"] = "blocked" if any("usage" in str(item.get("rule_id")) or "metadata" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if blockers else "clean"
    summary["artifact_boundary_status"] = "blocked" if any("path" in str(item.get("rule_id")) or "artifact" in str(item.get("rule_id")) for item in blockers) else "clean"
    summary["secret_boundary_status"] = "blocked" if any("secret" in str(item.get("rule_id")) for item in blockers) else "clean"


def summarize_rates(summary: dict[str, Any]) -> None:
    count = int(summary.get("real_calls_count") or 0)
    latencies = [int(value) for value in summary.get("latency_ms_values", []) if isinstance(value, int)]
    summary["latency_ms_min"] = min(latencies) if latencies else None
    summary["latency_ms_median"] = int(statistics.median(latencies)) if latencies else None
    summary["latency_ms_max"] = max(latencies) if latencies else None
    if count > 0:
        summary["schema_pass_rate"] = round(float(summary.get("schema_pass_count") or 0) / count, 4)
        summary["overclaim_rate"] = round(float(summary.get("overclaim_blocker_count") or 0) / count, 4)
        summary["missing_field_rate"] = round(float(summary.get("missing_field_count") or 0) / count, 4)
        summary["usage_availability_rate"] = round(float(summary.get("usage_available_count") or 0) / count, 4)


def build_from_fixture(config: CanaryConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("canary_status") or STATUS_BLOCKED_RUNTIME_BOUNDARY) if payload else STATUS_BLOCKED_RUNTIME_BOUNDARY,
    )
    if payload:
        summary.update(payload)
    summarize_rates(summary)
    blockers = load_blockers + validate_summary_payload(summary)
    summary["canary_status"] = choose_status(blockers, current_status=str(summary.get("canary_status") or ""))
    finalize_blockers(summary, blockers)
    return summary


def resolved_auth_json_path(config: CanaryConfig) -> Path:
    if config.auth_json_path is not None:
        return config.auth_json_path.expanduser()
    env_path = os.environ.get("CODEX_AUTH_JSON", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.codex/auth.json").expanduser()


def pre_http_blockers(config: CanaryConfig, *, run_root: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if config.backend_name not in ALLOWED_BACKENDS or FORBIDDEN_BACKEND_RE.search(config.backend_name):
        blockers.append(blocked_item("config.backend_name", "backend_not_allowed", "backend is not allowed for v3.8C"))
    if config.model != DEFAULT_MODEL:
        blockers.append(blocked_item("config.model", "model_not_allowed", "model is not allowed for v3.8C"))
    if config.reasoning_effort != DEFAULT_REASONING_EFFORT:
        blockers.append(blocked_item("config.reasoning_effort", "reasoning_effort_not_allowed", "reasoning_effort must remain xhigh"))
    if config.base_url and config.base_url.strip() not in ALLOWED_BASE_URLS:
        blockers.append(blocked_item("config.base_url", "base_url_not_allowed", "base_url must be the Codex Responses endpoint"))
    if config.call_count < 1 or config.call_count > MAX_CALL_COUNT:
        blockers.append(blocked_item("config.call_count", "call_count_over_budget", "call count must be between 1 and 5"))
    if config.token_budget > HARD_TOKEN_BUDGET:
        blockers.append(blocked_item("config.token_budget", "token_budget_over_hard_limit", "token budget exceeds hard limit"))
    if not under_tmp(run_root):
        blockers.append(blocked_item(run_root, "real_output_dir_not_tmp", "real-token raw output directory must be under /tmp"))
    auth_path = resolved_auth_json_path(config)
    if not auth_path.exists():
        blockers.append(blocked_item("auth", "auth_json_not_found", "Codex OAuth auth file is not available"))
    elif claim_scan.forbidden_path(normalize_path(auth_path)):
        blockers.append(blocked_item("auth", "auth_json_path_forbidden", "auth path is forbidden"))
    return blockers


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
    summary["missing_field_count"] += missing_field_count_for_packet(schema_blockers)
    summary["raw_response_tmp_paths"].append(call_result.get("raw_response_tmp_path", ""))
    summary["raw_response_sha256s"].append(call_result.get("raw_response_sha256", ""))
    summary["parsed_packet_tmp_paths"].append(call_result.get("parsed_packet_tmp_path", ""))
    summary["parsed_packet_sha256s"].append(call_result.get("parsed_packet_sha256", ""))
    summary["input_fixture_hashes"].append(call_result.get("input_fixture_hash", ""))
    summary["prompt_hashes"].append(call_result.get("prompt_hash", ""))
    if provenance_blockers:
        call_result["provenance_hash_status"] = "blocked"


def real_token_canary(config: CanaryConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
    pre_blockers = pre_http_blockers(config, run_root=run_root)
    if pre_blockers:
        finalize_blockers(summary, pre_blockers)
        return summary

    auth_path = resolved_auth_json_path(config)
    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        base_url=config.base_url,
    )
    all_blockers: list[dict[str, Any]] = []
    for brief in synthetic_briefs(config.canary_run_id, run_root)[: config.call_count]:
        call_id = str(brief["call_id"])
        brief_path = Path(str(brief["source_artifact_path"]))
        brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        input_hash = sha256_file(brief_path)
        prompt = user_prompt_for_brief({**brief, "input_fixture_hash": input_hash})
        prompt_hash = sha256_text(system_prompt() + "\n" + prompt)
        started = time.perf_counter()
        try:
            result = client.complete(
                system_prompt=system_prompt(),
                user_prompt=prompt,
                max_tokens=1600,
                timeout_seconds=config.timeout_seconds,
                temperature=0.0,
            )
        except RuntimeError as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            summary["provider_or_backend_called"] = True
            summary["real_calls_count"] = len(summary["call_results"]) + 1
            all_blockers.append(blocked_item(call_id, "backend_runtime_error", redact_secrets(str(exc))))
            summary["latency_ms_values"].append(elapsed_ms)
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
            "captured_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        raw_path = run_root / f"{call_id}_raw_response.json"
        raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        raw_hash = sha256_file(raw_path)

        schema_blockers: list[dict[str, Any]] = []
        provenance_blockers: list[dict[str, Any]] = []
        overclaim_blockers: list[dict[str, Any]] = []
        packet = extract_json_object(content)
        parsed_packet_path = run_root / f"{call_id}_parsed_packet.json"
        parsed_packet_hash = ""
        ranked_count = 0
        if packet is None:
            schema_blockers.append(blocked_item(call_id, "parsed_packet_json_parse_failed", "response did not contain a JSON object"))
            parsed_packet_path.write_text("{}", encoding="utf-8")
            parsed_packet_hash = sha256_file(parsed_packet_path)
        else:
            parsed_packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            parsed_packet_hash = sha256_file(parsed_packet_path)
            schema_blockers, provenance_blockers, overclaim_blockers = validate_packet(
                packet,
                path=f"{call_id}_parsed_packet",
                expected_input_hash=input_hash,
            )
            ranked_count = ranked_hypothesis_count(packet)
        usage_available = total_tokens is not None
        if total_tokens is None:
            all_blockers.append(blocked_item(call_id, "usage_metadata_missing", "backend response did not include usage metadata"))
            total_tokens = 0
        call_result = {
            "run_id": config.canary_run_id,
            "call_id": call_id,
            "backend_name": config.backend_name,
            "model": config.model,
            "sdk_version": f"python-{platform.python_version()}",
            "api_version": "codex_responses_oauth_streaming",
            "prompt_hash": prompt_hash,
            "input_fixture_hash": input_hash,
            "raw_response_tmp_path": str(raw_path),
            "raw_response_sha256": raw_hash,
            "parsed_packet_tmp_path": str(parsed_packet_path),
            "parsed_packet_sha256": parsed_packet_hash,
            "schema_status": "blocked" if schema_blockers else "clean",
            "claim_boundary_status": "blocked" if overclaim_blockers else "clean",
            "provenance_hash_status": "blocked" if provenance_blockers else "clean",
            "latency_ms": elapsed_ms,
            "token_usage_input": usage_input(usage),
            "token_usage_output": usage_output(usage),
            "token_usage_total": total_tokens,
            "ranked_hypothesis_count": ranked_count,
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
    status = choose_status(all_blockers, current_status=STATUS_PASS if not all_blockers else None)
    summary["canary_status"] = status
    finalize_blockers(summary, all_blockers)
    return summary


def build_summary(config: CanaryConfig) -> dict[str, Any]:
    validate_run_id(config.canary_run_id)
    run_root = config.output_dir / config.canary_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        finalize_blockers(summary, [blocked_item(run_root, "output_run_id_exists", "output run id exists")])
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if config.summary_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    elif config.real_token_canary:
        summary = real_token_canary(config, run_root=run_root)
    else:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        finalize_blockers(summary, [blocked_item("mode", "real_token_canary_not_requested", "real-token canary mode was not requested")])
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
            "canary_status": summary.get("canary_status"),
            "backend_name": summary.get("backend_name"),
            "model": summary.get("model"),
            "real_calls_count": summary.get("real_calls_count"),
            "token_usage_total": summary.get("token_usage_total"),
            "raw_response_sha256s": summary.get("raw_response_sha256s"),
            "parsed_packet_sha256s": summary.get("parsed_packet_sha256s"),
            "prompt_hashes": summary.get("prompt_hashes"),
            "input_fixture_hashes": summary.get("input_fixture_hashes"),
            "runtime_flags": {
                "provider_or_backend_called": summary.get("provider_or_backend_called"),
                **{flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            },
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "evidence_layer": summary.get("evidence_layer"),
            DIRECT_LLM_INTERPRETATION_KEY: summary.get(DIRECT_LLM_INTERPRETATION_KEY),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "canary_run_id": summary.get("canary_run_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "content_boundary_sha256": summary.get("content_boundary_sha256"),
        "canary_status": summary.get("canary_status"),
        "real_calls_count": summary.get("real_calls_count"),
        "token_usage_total": summary.get("token_usage_total"),
        "raw_response_tmp_paths": summary.get("raw_response_tmp_paths"),
        "raw_response_sha256s": summary.get("raw_response_sha256s"),
        "parsed_packet_sha256s": summary.get("parsed_packet_sha256s"),
        "provider_or_backend_called": summary.get("provider_or_backend_called"),
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8c_ksana_packet_v2_real_token_canary/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--real-token-canary", action="store_true")
    parser.add_argument("--backend-name", default=DEFAULT_BACKEND_NAME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--auth-json-path", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--call-count", type=int, default=DEFAULT_CALL_COUNT)
    parser.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> CanaryConfig:
    return CanaryConfig(
        canary_run_id=str(args.canary_run_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
        real_token_canary=bool(args.real_token_canary),
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
        print(f"v3.8C ksana packet v2 real-token canary failed: {redact_secrets(str(exc))}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("canary_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
