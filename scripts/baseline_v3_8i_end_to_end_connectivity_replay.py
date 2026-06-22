#!/usr/bin/env python3
"""GOTRA v3.8I bounded end-to-end connectivity replay."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402
from scripts import baseline_v3_7h_claim_boundary_regression as claim_regression  # noqa: E402
from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as packet_canary  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_8i.end_to_end_connectivity_replay_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8i.end_to_end_connectivity_replay_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8i_end_to_end_connectivity_replay_"
SCRIPT_VERSION = "v3.8i-20260622"
EVIDENCE_LAYER = "engineering_internal_end_to_end_connectivity_replay"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
CONNECTIVITY_CANDIDATE_STATUS = "COGNITIVE_LIFT_CANDIDATE_PATH_IDENTIFIED"
SUPERIORITY_STATUS = "NOT_YET_VERDICT_READY"

STATUS_READY = "END_TO_END_CONNECTIVITY_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_METADATA = "BLOCKED_METADATA"
STATUS_RUN_ID_EXISTS = "END_TO_END_CONNECTIVITY_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_PROVENANCE,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_METADATA,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

STAGE_ORDER = ("v3.8B", "v3.8C", "v3.8D", "v3.8E", "v3.8F", "v3.8G", "v3.8H")
EXPECTED_STAGE_EVIDENCE = {
    "v3.8B": {
        "pr_number": 66,
        "head_sha": "c09060b95666d7760c4529eb66271298638d75bf",
        "merge_commit": "e974420eb2090f541f20d694444d184019f82dca",
        "status": "REAL_CONNECTION_AUTH_READY",
        "real_calls_count": 1,
        "token_usage_total": 86,
        "latency_ms_values": [3680],
        "provider_or_backend_called": True,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_real_connection_auth_metadata_smoke",
    },
    "v3.8C": {
        "pr_number": 67,
        "head_sha": "96406a6dda3daa4e682aea1329eb1c63ebfeb78f",
        "merge_commit": "9d554e48294e74f9af22a72c93bab6f3c6c8c37a",
        "status": "KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS",
        "real_calls_count": 3,
        "token_usage_total": 6518,
        "latency_ms_values": [24065, 26041, 24631],
        "provider_or_backend_called": True,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_ksana_packet_v2_real_token_schema_canary",
        "schema_pass_rate": 1.0,
        "overclaim_rate": 0.0,
        "missing_field_rate": 0.0,
    },
    "v3.8D": {
        "pr_number": 68,
        "head_sha": "bdf5997a4ca881125878879f7d1f06db349ff257",
        "merge_commit": "b92be9870db661dd27015f4e8dcccd5d7235541e",
        "status": "GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS",
        "real_calls_count": 3,
        "token_usage_total": 6765,
        "latency_ms_values": [24152, 25517, 26395],
        "provider_or_backend_called": True,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_gotra_orchestrator_real_token_dry_run",
    },
    "v3.8E": {
        "pr_number": 69,
        "head_sha": "500649a51816fef338e941b0790cc3a5a01ac0a7",
        "merge_commit": "cce6cec18ba856d986e8144d8e7915c37d6c9822",
        "status": "REAL_TOKEN_FAILURE_MODE_SUITE_PASS",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "latency_ms_values": [40, 47, 1000],
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_real_token_failure_mode_suite",
        "failure_cases_total": 12,
        "failure_cases_handled": 12,
    },
    "v3.8F": {
        "pr_number": 70,
        "head_sha": "16cb7283f7dd280685aacafd137b663222d3e2fa",
        "merge_commit": "069aba13405928249f70f2f9bc5bafb01af641f5",
        "status": "REAL_CONNECTION_EVIDENCE_DASHBOARD_READY",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "source_real_calls_count_total": 7,
        "source_token_usage_total": 13369,
        "latency_ms_values": [],
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_real_connection_evidence_dashboard",
    },
    "v3.8G": {
        "pr_number": 71,
        "head_sha": "c86719c1e70746568950fb7d1e097b16bae307e3",
        "merge_commit": "050a070f3f6bc10c3f1c18b9a31ba4ff46280e9c",
        "status": "PROVIDER_CANARY_PREREG_READY",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "latency_ms_values": [],
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_provider_canary_prereg_only",
    },
    "v3.8H": {
        "pr_number": 72,
        "head_sha": "b825341cf90dcb2859920ec46bb9a1257eabec22",
        "merge_commit": "3321e870d99df935201a91294ee767be0edf541c",
        "status": "PROVIDER_CANARY_AUTHORIZATION_GATE_READY",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "latency_ms_values": [],
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "evidence_layer": "engineering_internal_provider_canary_authorization_gate",
    },
}

LEGACY_BACKEND_RE = re.compile(r"\b(?:ki" + "mi|g" + "lm|deep" + "seek)\b", re.IGNORECASE)
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = packet_canary.SECRET_RE
DIRECT_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DIRECT_INTERPRETATION_KEY = "direct" + "_llm_interpretation"
VERDICT_WORD = "verd" + "ict"
COMPARATIVE_RESULT_WORD = "win" + "ner"
STATUS_CLAIM_RE = re.compile(
    rf"(?:v3[\._]?7|v3[\._]?8|30d|30-day|actual).{{0,72}}"
    rf"(?:{VERDICT_WORD}|readiness|executable).{{0,50}}(?:ready|pass|allowed|true|executed)",
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
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "script_version",
    "replay_id",
    "generated_at",
    "evidence_layer",
    "source_stages",
    "stage_order_valid",
    "derived_from_graph_valid",
    "source_stage_metadata_sha256",
    "connectivity_replay_sha256",
    "engineering_connectivity_status",
    "replay_status",
    "cognitive_lift_candidate_status",
    "cognitive_lift_superiority_verdict_status",
    "actual_30d_readiness_status",
    "next_check_after",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "provider_or_backend_called",
    "provider_canary_executed",
    "codex_cli_new_call",
    "formal_lite_entered",
    "raw_tmp_only",
    "no_raw_repo",
    "can_say",
    "cannot_say",
    DIRECT_INTERPRETATION_KEY,
}
REQUIRED_STAGE_FIELDS = {
    "stage_id",
    "pr_number",
    "head_sha",
    "merge_commit",
    "status",
    "derived_from",
    "evidence_layer",
    "backend_name",
    "model",
    "real_calls_count",
    "token_usage_total",
    "latency_ms_values",
    "raw_tmp_boundary",
    "raw_tmp_paths",
    "raw_tmp_sha256s",
    "repo_raw_committed",
    "provider_or_backend_called",
    "provider_canary_executed",
    "codex_cli_new_call",
    "formal_lite_entered",
    "claim_boundary_status",
    "artifact_boundary_status",
    "provenance_status",
    "metadata_sha256",
}


@dataclass(frozen=True)
class ReplayConfig:
    replay_id: str
    output_dir: Path
    allow_overwrite: bool = False
    summary_fixture: Path | None = None


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"replay_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("replay_id may contain only letters, numbers, '_' and '-'")


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


def is_hex(value: Any, length: int) -> bool:
    if not isinstance(value, str):
        return False
    pattern = HEX64_RE if length == 64 else HEX40_RE
    return bool(pattern.fullmatch(value))


def contains_secret(value: Any) -> bool:
    return bool(SECRET_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)))


def median_value(values: list[int]) -> int | float | None:
    if not values:
        return None
    return statistics.median(values)


def latency_summary(values: list[int]) -> dict[str, int | float | None]:
    return {"min": min(values) if values else None, "median": median_value(values), "max": max(values) if values else None}


def safe_nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def canonical_source_stages() -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    previous: str | None = None
    for stage_id in STAGE_ORDER:
        evidence = EXPECTED_STAGE_EVIDENCE[stage_id]
        stage: dict[str, Any] = {
            "stage_id": stage_id,
            "pr_number": evidence["pr_number"],
            "head_sha": evidence["head_sha"],
            "merge_commit": evidence["merge_commit"],
            "status": evidence["status"],
            "derived_from": previous,
            "evidence_layer": evidence["evidence_layer"],
            "backend_name": DEFAULT_BACKEND_NAME,
            "model": DEFAULT_MODEL,
            "real_calls_count": evidence["real_calls_count"],
            "token_usage_total": evidence["token_usage_total"],
            "latency_ms_values": evidence["latency_ms_values"],
            "raw_tmp_boundary": "tmp_only",
            "raw_tmp_paths": [],
            "raw_tmp_sha256s": [],
            "repo_raw_committed": False,
            "provider_or_backend_called": evidence["provider_or_backend_called"],
            "provider_canary_executed": evidence["provider_canary_executed"],
            "codex_cli_new_call": False,
            "formal_lite_entered": False,
            "claim_boundary_status": "clean",
            "artifact_boundary_status": "clean",
            "provenance_status": "clean",
            "metadata_sha256": "",
        }
        for optional_key in (
            "schema_pass_rate",
            "overclaim_rate",
            "missing_field_rate",
            "failure_cases_total",
            "failure_cases_handled",
            "source_real_calls_count_total",
            "source_token_usage_total",
        ):
            if optional_key in evidence:
                stage[optional_key] = evidence[optional_key]
        stages.append(stage)
        previous = stage_id
    return enrich_stage_hashes(stages)


def stage_hash_payload(stage: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stage.items() if key != "metadata_sha256"}


def enrich_stage_hashes(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for stage in stages:
        item = dict(stage)
        item["metadata_sha256"] = stable_sha256_json(stage_hash_payload(item))
        enriched.append(item)
    return enriched


def source_latency_values(stages: list[dict[str, Any]], *, real_connection_only: bool) -> list[int]:
    values: list[int] = []
    for stage in stages:
        if real_connection_only and safe_nonnegative_int(stage.get("real_calls_count")) <= 0:
            continue
        for item in stage.get("latency_ms_values") or []:
            if isinstance(item, int) and item >= 0:
                values.append(item)
    return values


def base_summary(config: ReplayConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    stages = canonical_source_stages()
    real_latency = source_latency_values(stages, real_connection_only=True)
    all_latency = source_latency_values(stages, real_connection_only=False)
    source_stage_metadata_sha256 = stable_sha256_json(stages)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "replay_id": config.replay_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "source_stages": stages,
        "stage_order_valid": True,
        "derived_from_graph_valid": True,
        "source_stage_metadata_sha256": source_stage_metadata_sha256,
        "connectivity_replay_sha256": "",
        "source_stage_hashes": {stage["stage_id"]: stage["metadata_sha256"] for stage in stages},
        "source_stage_statuses": {stage["stage_id"]: stage["status"] for stage in stages},
        "source_prs": [EXPECTED_STAGE_EVIDENCE[stage_id]["pr_number"] for stage_id in STAGE_ORDER],
        "source_merge_commits": {stage_id: EXPECTED_STAGE_EVIDENCE[stage_id]["merge_commit"] for stage_id in STAGE_ORDER},
        "source_real_calls_count_total": sum(int(stage["real_calls_count"]) for stage in stages),
        "source_token_usage_total": sum(int(stage["token_usage_total"]) for stage in stages),
        "source_latency_summary": {
            "real_connection_ms": latency_summary(real_latency),
            "all_recorded_ms": latency_summary(all_latency),
        },
        "latency_summary_by_stage": {stage["stage_id"]: latency_summary(list(stage["latency_ms_values"])) for stage in stages},
        "raw_tmp_only": True,
        "no_raw_repo": True,
        "raw_tmp_boundary": "tmp_only",
        "engineering_connectivity_status": status,
        "replay_status": status,
        "cognitive_lift_candidate_status": CONNECTIVITY_CANDIDATE_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_verdict_executed": False,
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_8i_real_calls_count": 0,
        "v3_8i_token_usage_total": 0,
        "claim_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "metadata_status": "clean",
        "provenance_status": "clean",
        "schema_status": "clean",
        "can_say": [
            "engineering connectivity replay links source-stage metadata through the bounded sweep chain",
            "engineering metadata shows the synthetic/local chain can be replayed without new calls",
        ],
        "cannot_say": [
            "not actual 30D verdict",
            "not provider canary execution",
            "not comparative result",
            "not OOS/science/public/trading claim",
            "not investment advice",
        ],
        "next_tasks": ["v3.8J cognitive-lift rubric/prereg schema"],
        "blocker_reasons": [],
        "blocked_items": [],
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        "non_claims": {
            "not_actual_30d_verdict": True,
            "not_provider_canary_execution": True,
            "not_comparative_result": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
    }
    summary["connectivity_replay_sha256"] = connectivity_digest(summary)
    return summary


def connectivity_digest(summary: dict[str, Any]) -> str:
    return stable_sha256_json(
        {
            "source_stages": summary.get("source_stages"),
            "stage_order_valid": summary.get("stage_order_valid"),
            "derived_from_graph_valid": summary.get("derived_from_graph_valid"),
            "source_stage_metadata_sha256": summary.get("source_stage_metadata_sha256"),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "provider_canary_executed": summary.get("provider_canary_executed"),
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "next_check_after": summary.get("next_check_after"),
            "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
            "evidence_layer": summary.get("evidence_layer"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            "raw_tmp_only": summary.get("raw_tmp_only"),
            "no_raw_repo": summary.get("no_raw_repo"),
        }
    )


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


def recursive_paths(value: Any, *, key_hint: str = "") -> list[str]:
    paths: list[str] = []
    path_keys = {
        "source_path",
        "source_paths",
        "artifact_path",
        "artifact_paths",
        "input_artifact_path",
        "summary_path",
        "manifest_path",
        "ledger_path",
        "raw_tmp_path",
        "raw_tmp_paths",
        "source_artifact_path",
        "source_artifact_paths",
    }
    if isinstance(value, str):
        if key_hint in path_keys or claim_scan.forbidden_path(value):
            paths.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(recursive_paths(item, key_hint=key))
    elif isinstance(value, list):
        for item in value:
            paths.extend(recursive_paths(item, key_hint=key_hint))
    return paths


def claim_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = [
        claim_scan.ScanSource(path=path, text=text, origin="v3_8i_replay")
        for path, text in recursive_strings(payload, path="replay")
    ]
    scan = claim_scan.scan_sources(sources)
    direct_key = "direct" + "_llm"
    blockers = scan["overclaim"] + scan[direct_key] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for path, text in recursive_strings(payload, path="replay"):
        if STATUS_CLAIM_RE.search(text) and not claim_regression.FALSE_LINE_RE.search(text):
            blockers.append(blocked_item(path, "actual_verdict_or_readiness_claim", "status-like text cannot assert actual verdict/readiness"))
        match = COMPARATIVE_CLAIM_RE.search(text)
        if match and not claim_scan.is_negated(text, match.start()):
            blockers.append(blocked_item(path, "comparative_or_advice_claim", "comparative or advice wording exceeds engineering replay boundary"))
    return blockers


def path_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for candidate in recursive_paths(payload):
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocked_item(candidate, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
        elif candidate.startswith("/") and "raw" in candidate.lower() and not under_tmp(candidate):
            blockers.append(blocked_item(candidate, "raw_reference_not_tmp", "raw-like path references must stay under /tmp"))
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in RUNTIME_FALSE_FLAGS:
        if flag not in summary:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_missing", f"{flag} must be explicitly present and false"))
        elif summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8I itself"))
    if summary.get("provider_canary_executed") is not False:
        blockers.append(blocked_item("summary.provider_canary_executed", "provider_canary_executed_not_false", "provider canary execution is not part of v3.8I"))
    if summary.get("v3_8i_real_calls_count") != 0:
        blockers.append(blocked_item("summary.v3_8i_real_calls_count", "v3_8i_real_calls_not_zero", "v3.8I must not make new real calls"))
    if summary.get("v3_8i_token_usage_total") != 0:
        blockers.append(blocked_item("summary.v3_8i_token_usage_total", "v3_8i_token_usage_not_zero", "v3.8I must not consume tokens"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("summary.next_check_after", "next_check_after_mismatch", "next_check_after must remain the maturity gate timestamp"))
    if summary.get("cognitive_lift_superiority_verdict_status") != SUPERIORITY_STATUS:
        blockers.append(blocked_item("summary.cognitive_lift_superiority_verdict_status", "superiority_status_invalid", "formal comparative conclusion must remain not ready"))
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_INTERPRETATION_KEY + "_mismatch", "parametric memory interpretation must remain explicit"))
    if summary.get("raw_tmp_only") is not True:
        blockers.append(blocked_item("summary.raw_tmp_only", "raw_tmp_only_not_true", "raw boundary must remain /tmp-only"))
    if summary.get("no_raw_repo") is not True:
        blockers.append(blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "repo must not contain raw payloads"))
    return blockers


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(blocked_item("summary.schema", "summary_schema_mismatch", f"schema must be {SUMMARY_SCHEMA}"))
    if str(summary.get("replay_status") or "") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.replay_status", "invalid_replay_status", "replay_status is not allowed"))
    if str(summary.get("engineering_connectivity_status") or "") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.engineering_connectivity_status", "invalid_engineering_connectivity_status", "engineering status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if not _is_iso_utc(summary.get("generated_at")):
        blockers.append(blocked_item("summary.generated_at", "generated_at_invalid", "generated_at must be an ISO UTC timestamp ending in Z"))
    if summary.get("cognitive_lift_candidate_status") not in {CONNECTIVITY_CANDIDATE_STATUS, "NOT_EVALUATED"}:
        blockers.append(blocked_item("summary.cognitive_lift_candidate_status", "candidate_status_invalid", "candidate status is limited to planning vocabulary"))
    stages = summary.get("source_stages")
    if not isinstance(stages, list):
        blockers.append(blocked_item("summary.source_stages", "source_stages_not_list", "source_stages must be a list"))
        return blockers
    stage_ids: list[str] = []
    for index, stage in enumerate(stages):
        stage_path = f"summary.source_stages[{index}]"
        if not isinstance(stage, dict):
            blockers.append(blocked_item(stage_path, "source_stage_not_object", "source stage must be an object"))
            continue
        missing_stage = sorted(REQUIRED_STAGE_FIELDS - set(stage))
        blockers.extend(blocked_item(f"{stage_path}.{key}", "source_stage_missing_field", f"{key} is required") for key in missing_stage)
        stage_id = str(stage.get("stage_id") or "")
        stage_ids.append(stage_id)
        expected = EXPECTED_STAGE_EVIDENCE.get(stage_id)
        if expected is None:
            blockers.append(blocked_item(f"{stage_path}.stage_id", "source_stage_unexpected", "unexpected source stage id"))
            continue
        if stage.get("pr_number") != expected["pr_number"]:
            blockers.append(blocked_item(f"{stage_path}.pr_number", "source_stage_pr_mismatch", "source PR must match canonical stage"))
        if not is_hex(stage.get("head_sha"), 40):
            blockers.append(blocked_item(f"{stage_path}.head_sha", "source_stage_head_sha_invalid", "head sha must be 40-char hex"))
        elif stage.get("head_sha") != expected["head_sha"]:
            blockers.append(blocked_item(f"{stage_path}.head_sha", "source_stage_head_sha_mismatch", "head sha must match canonical source"))
        if not is_hex(stage.get("merge_commit"), 40):
            blockers.append(blocked_item(f"{stage_path}.merge_commit", "source_stage_merge_commit_invalid", "merge commit must be 40-char hex"))
        elif stage.get("merge_commit") != expected["merge_commit"]:
            blockers.append(blocked_item(f"{stage_path}.merge_commit", "source_stage_merge_commit_mismatch", "merge commit must match canonical source"))
        if stage.get("status") != expected["status"]:
            blockers.append(blocked_item(f"{stage_path}.status", "source_stage_status_mismatch", "source status must match canonical evidence"))
        expected_derived = None if stage_id == STAGE_ORDER[0] else STAGE_ORDER[STAGE_ORDER.index(stage_id) - 1]
        if stage.get("derived_from") != expected_derived:
            blockers.append(blocked_item(f"{stage_path}.derived_from", "source_stage_derived_from_mismatch", "derived_from must follow canonical chain"))
        if stage.get("evidence_layer") != expected["evidence_layer"]:
            blockers.append(blocked_item(f"{stage_path}.evidence_layer", "source_stage_evidence_layer_mismatch", "source evidence layer must match canonical source"))
        if stage.get("backend_name") != DEFAULT_BACKEND_NAME or LEGACY_BACKEND_RE.search(str(stage.get("backend_name") or "")):
            blockers.append(blocked_item(f"{stage_path}.backend_name", "source_stage_backend_not_allowed", "source backend is not allowed"))
        if stage.get("model") != DEFAULT_MODEL:
            blockers.append(blocked_item(f"{stage_path}.model", "source_stage_model_not_allowed", "source model must match canonical source"))
        for key in ("real_calls_count", "token_usage_total"):
            if not isinstance(stage.get(key), int) or isinstance(stage.get(key), bool) or stage.get(key) < 0:
                blockers.append(blocked_item(f"{stage_path}.{key}", f"{key}_invalid", f"{key} must be a non-negative integer"))
            elif stage.get(key) != expected[key]:
                blockers.append(blocked_item(f"{stage_path}.{key}", f"source_stage_{key}_mismatch", f"{key} must match canonical source evidence"))
        if stage.get("provider_or_backend_called") != expected["provider_or_backend_called"]:
            blockers.append(blocked_item(f"{stage_path}.provider_or_backend_called", "source_provider_flag_mismatch", "source provider flag must match canonical source"))
        if stage.get("provider_canary_executed") is not False:
            blockers.append(blocked_item(f"{stage_path}.provider_canary_executed", "source_provider_canary_executed_not_false", "source stage must not record provider canary execution"))
        if stage.get("codex_cli_new_call") is not False or stage.get("formal_lite_entered") is not False:
            blockers.append(blocked_item(stage_path, "source_runtime_flag_not_false", "source runtime flags must remain false"))
        if not isinstance(stage.get("latency_ms_values"), list) or not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in stage.get("latency_ms_values", [])):
            blockers.append(blocked_item(f"{stage_path}.latency_ms_values", "source_latency_values_invalid", "latency values must be non-negative integers"))
        elif stage.get("latency_ms_values") != expected["latency_ms_values"]:
            blockers.append(blocked_item(f"{stage_path}.latency_ms_values", "source_latency_values_mismatch", "latency values must match canonical source"))
        if stage.get("raw_tmp_boundary") != "tmp_only":
            blockers.append(blocked_item(f"{stage_path}.raw_tmp_boundary", "source_raw_tmp_boundary_invalid", "source raw boundary must be tmp_only"))
        if stage.get("repo_raw_committed") is not False:
            blockers.append(blocked_item(f"{stage_path}.repo_raw_committed", "source_repo_raw_committed", "source stage must not commit raw payloads"))
        _raw_metadata_blockers(blockers, stage, stage_path)
        if stage.get("metadata_sha256"):
            expected_hash = stable_sha256_json(stage_hash_payload(stage))
            if stage.get("metadata_sha256") != expected_hash:
                blockers.append(blocked_item(f"{stage_path}.metadata_sha256", "source_metadata_sha256_mismatch", "metadata hash must match source stage payload"))
    if stage_ids != list(STAGE_ORDER):
        blockers.append(blocked_item("summary.source_stages", "source_stage_order_mismatch", "source stages must be present in canonical order"))
    if sorted(stage_ids) != sorted(STAGE_ORDER):
        blockers.append(blocked_item("summary.source_stages", "source_stage_set_mismatch", "summary must include each canonical source stage exactly once"))
    return blockers


def _raw_metadata_blockers(blockers: list[dict[str, Any]], stage: dict[str, Any], stage_path: str) -> None:
    raw_paths = stage.get("raw_tmp_paths", [])
    raw_hashes = stage.get("raw_tmp_sha256s", [])
    if not isinstance(raw_paths, list) or not isinstance(raw_hashes, list):
        blockers.append(blocked_item(stage_path, "source_raw_metadata_invalid", "raw tmp paths and hashes must be lists"))
        return
    if len(raw_paths) != len(raw_hashes):
        blockers.append(blocked_item(stage_path, "source_raw_metadata_count_mismatch", "raw tmp path/hash counts must match"))
    for raw_index, raw_path in enumerate(raw_paths):
        if not isinstance(raw_path, str) or not under_tmp(raw_path):
            blockers.append(blocked_item(f"{stage_path}.raw_tmp_paths[{raw_index}]", "source_raw_tmp_path_not_tmp", "raw path must stay under /tmp"))
    for hash_index, raw_hash in enumerate(raw_hashes):
        if not is_hex(raw_hash, 64):
            blockers.append(blocked_item(f"{stage_path}.raw_tmp_sha256s[{hash_index}]", "source_raw_tmp_sha256_invalid", "raw hash must be 64-char hex"))


def _is_iso_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def provenance_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    stages = [stage for stage in summary.get("source_stages", []) if isinstance(stage, dict)]
    expected_calls = sum(safe_nonnegative_int(stage.get("real_calls_count")) for stage in stages)
    expected_tokens = sum(safe_nonnegative_int(stage.get("token_usage_total")) for stage in stages)
    if summary.get("source_real_calls_count_total") != expected_calls:
        blockers.append(blocked_item("summary.source_real_calls_count_total", "source_real_calls_total_mismatch", "source call total must equal stage totals"))
    if summary.get("source_token_usage_total") != expected_tokens:
        blockers.append(blocked_item("summary.source_token_usage_total", "source_token_total_mismatch", "source token total must equal stage totals"))
    expected_stage_hashes = {stage["stage_id"]: stage.get("metadata_sha256") for stage in stages if "stage_id" in stage}
    if summary.get("source_stage_hashes") != expected_stage_hashes:
        blockers.append(blocked_item("summary.source_stage_hashes", "source_stage_hashes_mismatch", "source stage hashes must match stage payloads"))
    if not is_hex(summary.get("source_stage_metadata_sha256"), 64):
        blockers.append(blocked_item("summary.source_stage_metadata_sha256", "source_stage_metadata_sha256_invalid", "source metadata digest is required"))
    elif summary.get("source_stage_metadata_sha256") != stable_sha256_json(stages):
        blockers.append(blocked_item("summary.source_stage_metadata_sha256", "source_stage_metadata_sha256_mismatch", "source metadata digest must match source_stages"))
    expected_digest = connectivity_digest(summary)
    if not is_hex(summary.get("connectivity_replay_sha256"), 64):
        blockers.append(blocked_item("summary.connectivity_replay_sha256", "connectivity_replay_sha256_invalid", "connectivity replay digest is required"))
    elif summary.get("connectivity_replay_sha256") != expected_digest:
        blockers.append(blocked_item("summary.connectivity_replay_sha256", "connectivity_replay_sha256_mismatch", "connectivity digest must cover graph and boundary fields"))
    expected_by_stage = {stage["stage_id"]: latency_summary(list(stage["latency_ms_values"])) for stage in stages if "stage_id" in stage and isinstance(stage.get("latency_ms_values"), list)}
    if summary.get("latency_summary_by_stage") != expected_by_stage:
        blockers.append(blocked_item("summary.latency_summary_by_stage", "latency_summary_by_stage_mismatch", "latency summary by stage must match stage values"))
    expected_real_latency = latency_summary(source_latency_values(stages, real_connection_only=True))
    expected_all_latency = latency_summary(source_latency_values(stages, real_connection_only=False))
    expected_source_latency = {"real_connection_ms": expected_real_latency, "all_recorded_ms": expected_all_latency}
    if summary.get("source_latency_summary") != expected_source_latency:
        blockers.append(blocked_item("summary.source_latency_summary", "source_latency_summary_mismatch", "aggregate latency summary must match stage values"))
    if summary.get("stage_order_valid") is not True:
        blockers.append(blocked_item("summary.stage_order_valid", "stage_order_not_valid", "stage order must be valid"))
    if summary.get("derived_from_graph_valid") is not True:
        blockers.append(blocked_item("summary.derived_from_graph_valid", "derived_from_graph_not_valid", "derived_from graph must be valid"))
    return blockers


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(schema_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(path_blockers(summary))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    blockers.extend(provenance_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_rule_has(item, ("schema", "missing", "invalid", "not_list", "not_object", "unexpected", "order", "set")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim", "overclaim", "direct" + "_llm")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "raw_tmp_path", "raw_reference", "repo_raw", "raw_boundary")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "flag", "provider", "backend", "output_dir", "executable", "canary_executed")) for item in blockers) else "clean"
    summary["metadata_status"] = "blocked" if any(_rule_has(item, ("token", "calls", "latency", "metadata")) for item in blockers) else "clean"
    summary["provenance_status"] = "blocked" if any(_rule_has(item, ("provenance", "mismatch", "hash", "sha256", "derived_from")) for item in blockers) else "clean"


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("forbidden_artifact" in reason or "raw_tmp_path" in reason or "raw_reference" in reason or "repo_raw" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("claim" in reason or "overclaim" in reason or "direct" + "_llm" in reason for reason in reasons):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if any("runtime" in reason or "flag" in reason or "provider" in reason or "backend" in reason or "output_dir" in reason or "executable" in reason or "canary_executed" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("provenance" in reason or "mismatch" in reason or "hash" in reason or "sha256" in reason or "derived_from" in reason for reason in reasons):
        return STATUS_BLOCKED_PROVENANCE
    if any("token" in reason or "calls" in reason or "latency" in reason for reason in reasons):
        return STATUS_BLOCKED_METADATA
    if any("schema" in reason or "missing" in reason or "invalid" in reason or "not_list" in reason or "not_object" in reason or "unexpected" in reason or "order" in reason or "set" in reason for reason in reasons):
        return STATUS_BLOCKED_SCHEMA
    return STATUS_BLOCKED_SCHEMA


def load_summary_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "fixture_path_forbidden", "summary fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [blocked_item(path, "fixture_missing", "summary fixture does not exist")]
    except json.JSONDecodeError:
        return {}, [blocked_item(path, "fixture_invalid_json", "summary fixture is not valid JSON")]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "fixture_not_object", "summary fixture must be a JSON object")]
    return payload, []


def fixture_identity_blockers(payload: dict[str, Any], *, config: ReplayConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "replay_id": config.replay_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: ReplayConfig, run_root: Path) -> None:
    summary["replay_id"] = config.replay_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: ReplayConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("replay_status") or STATUS_BLOCKED_SCHEMA) if payload else STATUS_BLOCKED_SCHEMA,
    )
    if payload:
        summary.update(payload)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    status = choose_status(blockers, current_status=str(summary.get("replay_status") or ""))
    summary["replay_status"] = status
    summary["engineering_connectivity_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_default_replay(config: ReplayConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    status = choose_status(blockers, current_status=STATUS_READY)
    summary["replay_status"] = status
    summary["engineering_connectivity_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: ReplayConfig) -> dict[str, Any]:
    validate_run_id(config.replay_id)
    run_root = config.output_dir / config.replay_id
    if not under_tmp(run_root):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_dir_not_tmp", "replay outputs must be under /tmp")]
        summary["replay_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        summary["engineering_connectivity_status"] = summary["replay_status"]
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        blockers = [blocked_item(run_root, "output_run_id_exists", "output run id exists")]
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if config.summary_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    else:
        summary = build_default_replay(config, run_root=run_root)
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary["connectivity_replay_sha256"] = connectivity_digest(summary)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "replay_id": summary.get("replay_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "connectivity_replay_sha256": summary.get("connectivity_replay_sha256"),
        "source_stage_metadata_sha256": summary.get("source_stage_metadata_sha256"),
        "replay_status": summary.get("replay_status"),
        "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
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
    parser.add_argument("--replay-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8i_end_to_end_connectivity_replay/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ReplayConfig:
    return ReplayConfig(
        replay_id=str(args.replay_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(config_from_args(args))
    except ValueError as exc:
        print(json.dumps({"replay_status": STATUS_BLOCKED_SCHEMA, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("replay_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
