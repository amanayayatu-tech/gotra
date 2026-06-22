#!/usr/bin/env python3
"""GOTRA v3.8M paired cognitive-lift evaluation readiness package."""

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
from scripts import baseline_v3_8j_cognitive_lift_rubric_prereg_schema as rubric  # noqa: E402
from scripts import baseline_v3_8l_evidence_bounded_conclusion_template as conclusion_template  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_8m.paired_cognitive_lift_evaluation_readiness_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8m.paired_cognitive_lift_evaluation_readiness_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8m_paired_cognitive_lift_evaluation_readiness_"
SCRIPT_VERSION = "v3.8m-20260622"
EVIDENCE_LAYER = "engineering_internal_paired_cognitive_lift_evaluation_readiness"
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
ACTUAL_30D_NEXT_CHECK_AFTER = rubric.ACTUAL_30D_NEXT_CHECK_AFTER
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
RUBRIC_SCHEMA_VERSION = rubric.SCHEMA_VERSION
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"
AUTHORIZATION_STATUS = "NOT_EXECUTABLE_PLACEHOLDER_CAPS"

STATUS_READY = "PAIRED_COGNITIVE_LIFT_EVALUATION_READINESS_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE_BOUNDARY"
STATUS_BLOCKED_MATURITY_READINESS = "BLOCKED_MATURITY_READINESS"
STATUS_BLOCKED_STATISTICAL_ELIGIBILITY = "BLOCKED_STATISTICAL_ELIGIBILITY"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_AUTHORIZATION_BOUNDARY = "BLOCKED_AUTHORIZATION_BOUNDARY"
STATUS_BLOCKED_VERDICT_OVERREACH = "BLOCKED_VERDICT_OVERREACH"
STATUS_RUN_ID_EXISTS = "PAIRED_COGNITIVE_LIFT_EVALUATION_READINESS_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_PROVENANCE,
    STATUS_BLOCKED_MISSING_EVIDENCE,
    STATUS_BLOCKED_MATURITY_READINESS,
    STATUS_BLOCKED_STATISTICAL_ELIGIBILITY,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_BLOCKED_AUTHORIZATION_BOUNDARY,
    STATUS_BLOCKED_VERDICT_OVERREACH,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

STAGE_ORDER = (*conclusion_template.STAGE_ORDER, "v3.8L")
EXPECTED_STAGE_EVIDENCE: dict[str, dict[str, Any]] = {
    **conclusion_template.EXPECTED_STAGE_EVIDENCE,
    "v3.8L": {
        "pr_number": 76,
        "head_sha": "834f81236609ed36dbb985b627bab9f1a97ed098",
        "merge_commit": "5bc51cf06cbe9231ddf10231ecb12d9576489133",
        "status": "EVIDENCE_BOUNDED_CONCLUSION_TEMPLATE_READY",
        "evidence_layer": conclusion_template.EVIDENCE_LAYER,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
    },
}

PACKAGE_SECTIONS = (
    "paired_sample_identity_schema",
    "scoring_execution_prerequisites",
    "maturity_readiness_blockers",
    "statistical_eligibility_checklist",
    "claim_boundary_gate",
    "future_provider_30d_verdict_authorization_checklist",
)
PAIRED_IDENTITY_FIELDS = (
    "paired_sample_id",
    "ticker",
    "decision_date",
    "horizon",
    "prompt_hash",
    "input_hash",
    "visible_data_boundary",
    "rubric_version",
    "source_run_id",
    "source_summary_sha256",
    "source_artifact_sha256",
    "arm_identity",
)
ALLOWED_ARMS = ("ksana_real_research", "full_gotra", DIRECT_INTERPRETATION)

SECRET_RE = packet_canary.SECRET_RE
LEGACY_BACKEND_RE = re.compile(
    r"\b(?:" + "ki" + "mi" + r"|g" + "lm" + r"|deep" + "seek" + r")\b",
    re.IGNORECASE,
)
VERDICT_WORD = "verd" + "ict"
COMPARATIVE_RESULT_WORD = "win" + "ner"
RAW_PATH_RE = re.compile(r"(?:^|[/. _-])raw(?:[/. _-]|$)", re.IGNORECASE)
PROVIDER_EXECUTION_CLAIM_RE = re.compile(
    r"(?:\b(?:provider|backend|canary).{0,80}\b(?:called|executed|ran|used|completed)\b"
    r"|\b(?:called|executed|ran|used|completed).{0,80}\b(?:provider|backend|canary)\b)",
    re.IGNORECASE,
)
CODEX_FORMAL_EXECUTION_CLAIM_RE = re.compile(
    r"(?:\b(?:codex(?:\s+cli)?|codex_cli|formal[-_ ]lite).{0,80}\b(?:called|executed|ran|used|completed|entered|made)\b"
    r"|\b(?:called|executed|ran|used|completed|entered|made).{0,80}\b(?:codex(?:\s+cli)?|codex_cli|formal[-_ ]lite)\b)",
    re.IGNORECASE,
)
STATUS_CLAIM_RE = re.compile(
    rf"(?:v3[\._]?7|v3[\._]?8|30d|30-day|actual|cognitive[-_ ]lift).{{0,90}}"
    rf"(?:{VERDICT_WORD}|readiness|executable|superiority).{{0,70}}"
    r"(?:ready|pass|allowed|true|executed|proved|validated|confirmed|succeeded|established|final)",
    re.IGNORECASE,
)
VERDICT_OVERREACH_RE = re.compile(
    rf"(?:superiority|comparative|external|actual).{{0,70}}(?:{VERDICT_WORD}|result|conclusion).{{0,70}}"
    r"(?:ready|proved|confirmed|passed|executed|wins|succeeded|established|final)",
    re.IGNORECASE,
)
COMPARATIVE_CLAIM_RE = re.compile(
    rf"\b(?:{COMPARATIVE_RESULT_WORD}|out"
    + r"perform|pro"
    + r"fit|al"
    + r"pha|trading adv"
    + r"ice|investment adv"
    + r"ice|trading guid"
    + r"ance|investment guid"
    + r"ance|action guid"
    + r"ance|public pr"
    + r"oof|science pr"
    + r"oof|oos pr"
    + r"oof)\b",
    re.IGNORECASE,
)
AFFIRMATIVE_STATUS_TOKEN_RE = re.compile(
    rf"\b(?:ready|pass|allowed|true|executed|proved|validated|confirmed|succeeded|established|final|{COMPARATIVE_RESULT_WORD}|wins)\b",
    re.IGNORECASE,
)
DIRECT_UNSAFE_RE = re.compile(
    r"(?:direct_llm|direct_llm_parametric_memory_control).{0,90}"
    r"(?:clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline)",
    re.IGNORECASE,
)
DIRECT_UNSAFE_ROLE_RE = re.compile(
    r"\b(?:clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline)\b",
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
REQUIRED_STAGE_FIELDS = set(conclusion_template.REQUIRED_STAGE_FIELDS)
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "script_version",
    "readiness_pack_id",
    "generated_at",
    "evidence_layer",
    "readiness_status",
    "package_sections",
    "paired_sample_identity_schema",
    "scoring_execution_prerequisites",
    "maturity_readiness_blockers",
    "statistical_eligibility_checklist",
    "claim_boundary_gate",
    "future_provider_30d_verdict_authorization_checklist",
    "source_stages",
    "source_stage_hashes",
    "source_stage_statuses",
    "source_stage_metadata_sha256",
    "readiness_package_sha256",
    "provider_canary_authorization_status",
    "can_say",
    "cannot_say",
    "missing_before_superiority_verdict",
    "authorization_required_before_execution",
    DIRECT_INTERPRETATION_KEY,
    DIRECT_CLEAN_BASELINE_KEY,
    "actual_30d_readiness_status",
    "next_check_after",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "actual_30d_verdict_executed",
    "provider_or_backend_called",
    "provider_canary_executed",
    "codex_cli_new_call",
    "formal_lite_entered",
    "raw_tmp_only",
    "no_raw_repo",
    "real_calls_count",
    "token_usage_total",
    "cognitive_lift_superiority_verdict_status",
}


@dataclass(frozen=True)
class ReadinessConfig:
    readiness_pack_id: str
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
        raise ValueError(f"readiness_pack_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("readiness_pack_id may contain only letters, numbers, '_' and '-'")


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
    return isinstance(value, str) and bool(re.fullmatch(rf"[0-9a-f]{{{length}}}", value))


def contains_secret(value: Any) -> bool:
    return bool(SECRET_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)))


def is_numeric_zero(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def safe_nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def stage_hash_payload(stage: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stage.items() if key != "metadata_sha256"}


def enrich_stage_hashes(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for stage in stages:
        item = dict(stage)
        item["metadata_sha256"] = stable_sha256_json(stage_hash_payload(item))
        enriched.append(item)
    return enriched


def canonical_source_stages() -> list[dict[str, Any]]:
    stages = [dict(stage) for stage in conclusion_template.canonical_source_stages()]
    stage = {
        "stage_id": "v3.8L",
        "pr_number": EXPECTED_STAGE_EVIDENCE["v3.8L"]["pr_number"],
        "head_sha": EXPECTED_STAGE_EVIDENCE["v3.8L"]["head_sha"],
        "merge_commit": EXPECTED_STAGE_EVIDENCE["v3.8L"]["merge_commit"],
        "status": EXPECTED_STAGE_EVIDENCE["v3.8L"]["status"],
        "derived_from": "v3.8K",
        "evidence_layer": EXPECTED_STAGE_EVIDENCE["v3.8L"]["evidence_layer"],
        "backend_name": DEFAULT_BACKEND_NAME,
        "model": DEFAULT_MODEL,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "raw_tmp_boundary": "tmp_only",
        "raw_tmp_paths": [],
        "raw_tmp_sha256s": [],
        "repo_raw_committed": False,
        "claim_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "provenance_status": "clean",
        "metadata_sha256": "",
    }
    stages.extend(enrich_stage_hashes([stage]))
    return stages


def canonical_stage_map() -> dict[str, dict[str, Any]]:
    return {stage["stage_id"]: stage for stage in canonical_source_stages()}


def paired_sample_identity_schema() -> dict[str, Any]:
    return {
        "required_fields": list(PAIRED_IDENTITY_FIELDS),
        "allowed_arms": list(ALLOWED_ARMS),
        "arm_identity_required": True,
        "matched_identity_fields": [
            "paired_sample_id",
            "ticker",
            "decision_date",
            "horizon",
            "prompt_hash",
            "input_hash",
            "visible_data_boundary",
            "rubric_version",
        ],
        "direct_control_role": "historical diagnostic/control arm with parametric memory boundary",
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
        "minimum_provenance_requirements": [
            "source_run_id",
            "source_summary_sha256",
            "source_artifact_sha256",
        ],
    }


def scoring_execution_prerequisites() -> dict[str, Any]:
    return {
        "locked_rubric_required": True,
        "rubric_version": RUBRIC_SCHEMA_VERSION,
        "paired_records_completeness_required": True,
        "source_hashes_required": True,
        "blind_or_locked_scoring_metadata_required": True,
        "missing_inconclusive_handling": "missing or partial paired evidence stays inconclusive",
        "deterministic_scorer_constraints": [
            "same rubric version",
            "same visible data boundary",
            "stable digest over scoring inputs",
        ],
        "raw_output_boundary": "/tmp only",
        "real_scoring_executed": False,
    }


def maturity_readiness_blockers() -> dict[str, Any]:
    return {
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "mature_paired_evidence_available": False,
        "actual_v3_7_verdict_executable": False,
        "actual_v3_7_verdict_executed": False,
        "blocker_reasons": [
            "actual_30d_readiness_not_matured",
            "mature_paired_evidence_missing",
            "actual_verdict_not_executable",
        ],
    }


def statistical_eligibility_checklist() -> dict[str, Any]:
    return {
        "sample_size_ready": False,
        "paired_clean_count_ready": False,
        "same_horizon_required": True,
        "bootstrap_hac_eligible": False,
        "effect_estimate_field_boundary": "no effect estimate, p-value, confidence interval, bootstrap, or HAC fields before eligibility",
        "p_value_before_eligibility_allowed": False,
        "estimate_before_eligibility_allowed": False,
        "confidence_interval_before_eligibility_allowed": False,
        "bootstrap_hac_fields_before_eligibility_allowed": False,
        "inconclusive_tie_handling": "tie or insufficient paired evidence stays inconclusive",
    }


def claim_boundary_gate() -> dict[str, Any]:
    return {
        "blocks": [
            "formal comparative conclusion overreach",
            "external proof wording",
            "action-boundary wording",
            "actual 30D readiness bypass",
        ],
        "engineering_connectivity_conclusion": "engineering evidence only",
        "cognitive_lift_candidate_conclusion": "candidate evaluation path only",
        "cognitive_lift_superiority_verdict": SUPERIORITY_STATUS,
        "no_public_science_trading_claim": True,
        "no_investment_or_trading_guidance": True,
    }


def future_provider_30d_verdict_authorization_checklist() -> dict[str, Any]:
    return {
        "candidate_provider_backend_model": f"{DEFAULT_BACKEND_NAME} / {DEFAULT_MODEL}",
        "call_cap": "X",
        "token_cap": "Y",
        "cost_cap": "Z",
        "placeholder_caps_only": True,
        "execution_allowed": False,
        "provider_canary_execution_allowed": False,
        "actual_30d_verdict_execution_allowed": False,
        "raw_output_boundary": "/tmp only",
        "usage_metadata_required": True,
        "no_actual_30d_verdict": True,
        "no_superiority_verdict": True,
        "no_public_science_trading_claim": True,
        "authorization_status": AUTHORIZATION_STATUS,
        "authorization_required_before_execution": True,
    }


def base_summary(config: ReadinessConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    stages = canonical_source_stages()
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "readiness_pack_id": config.readiness_pack_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "readiness_status": status,
        "package_sections": list(PACKAGE_SECTIONS),
        "paired_sample_identity_schema": paired_sample_identity_schema(),
        "scoring_execution_prerequisites": scoring_execution_prerequisites(),
        "maturity_readiness_blockers": maturity_readiness_blockers(),
        "statistical_eligibility_checklist": statistical_eligibility_checklist(),
        "claim_boundary_gate": claim_boundary_gate(),
        "future_provider_30d_verdict_authorization_checklist": future_provider_30d_verdict_authorization_checklist(),
        "source_stages": stages,
        "source_stage_hashes": {stage["stage_id"]: stage["metadata_sha256"] for stage in stages},
        "source_stage_statuses": {stage["stage_id"]: stage["status"] for stage in stages},
        "source_stage_metadata_sha256": stable_sha256_json(stages),
        "readiness_package_sha256": "",
        "can_say": [
            "paired cognitive-lift evaluation readiness checklist is available for internal engineering review",
            "source-stage engineering evidence is canonical and bound by digest",
        ],
        "cannot_say": [
            "not paired evaluation execution",
            "not provider canary execution",
            "not actual 30D verdict",
            "not formal comparative conclusion",
            "not action guidance",
        ],
        "missing_before_superiority_verdict": [
            "mature paired evidence",
            "locked scoring execution",
            "statistical eligibility",
            "actual 30D readiness gate",
            "clean claim boundary at conclusion time",
        ],
        "authorization_required_before_execution": [
            "separate user authorization",
            "concrete call, token, and cost caps",
            "usage metadata",
            "/tmp raw-output boundary",
        ],
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
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
        "raw_tmp_only": True,
        "no_raw_repo": True,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "provider_canary_authorization_status": AUTHORIZATION_STATUS,
        "schema_status": "clean",
        "provenance_status": "clean",
        "missing_evidence_boundary_status": "clean",
        "maturity_readiness_status": "blocked_expected",
        "statistical_eligibility_status": "blocked_expected",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "authorization_boundary_status": "clean",
        "verdict_boundary_status": "clean",
        "blocker_reasons": [],
        "blocked_items": [],
        "non_claims": {
            "not_paired_evaluation_execution": True,
            "not_provider_canary_execution": True,
            "not_actual_30d_verdict": True,
            "not_formal_comparative_conclusion": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_or_trading_guidance": True,
        },
    }
    summary["readiness_package_sha256"] = readiness_package_digest(summary)
    return summary


def readiness_package_digest(summary: dict[str, Any]) -> str:
    return stable_sha256_json(
        {
            "package_sections": summary.get("package_sections"),
            "paired_sample_identity_schema": summary.get("paired_sample_identity_schema"),
            "scoring_execution_prerequisites": summary.get("scoring_execution_prerequisites"),
            "maturity_readiness_blockers": summary.get("maturity_readiness_blockers"),
            "statistical_eligibility_checklist": summary.get("statistical_eligibility_checklist"),
            "claim_boundary_gate": summary.get("claim_boundary_gate"),
            "future_provider_30d_verdict_authorization_checklist": summary.get("future_provider_30d_verdict_authorization_checklist"),
            "source_stages": summary.get("source_stages"),
            "source_stage_metadata_sha256": summary.get("source_stage_metadata_sha256"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "next_check_after": summary.get("next_check_after"),
            "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
            "provider_canary_authorization_status": summary.get("provider_canary_authorization_status"),
            "evidence_layer": summary.get("evidence_layer"),
            "raw_tmp_only": summary.get("raw_tmp_only"),
            "no_raw_repo": summary.get("no_raw_repo"),
            "real_calls_count": summary.get("real_calls_count"),
            "token_usage_total": summary.get("token_usage_total"),
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


def recursive_paths(value: Any, *, key_hint: str = "") -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
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
        "transcript_path",
        "transcript_paths",
        "path",
        "paths",
    }
    if isinstance(value, str):
        if key_hint in path_keys or claim_scan.forbidden_path(value) or _looks_like_raw_path(value) or _looks_like_transcript_path(value):
            paths.append((key_hint, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(recursive_paths(item, key_hint=key))
    elif isinstance(value, list):
        for item in value:
            paths.extend(recursive_paths(item, key_hint=key_hint))
    return paths


def claim_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    text_items = recursive_strings(payload, path="readiness")
    sources = [
        claim_scan.ScanSource(path=path, text=text, origin="v3_8m_readiness_pack")
        for path, text in text_items
    ]
    scan = claim_scan.scan_sources(sources)
    blockers = scan["overclaim"] + scan[DIRECT_PREFIX] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for path, text in text_items:
        for status_match in STATUS_CLAIM_RE.finditer(text):
            if _has_unnegated_affirmative_token(text, status_match):
                blockers.append(blocked_item(path, "actual_or_superiority_verdict_claim", "status-like text cannot assert actual or formal comparative readiness"))
        for verdict_match in VERDICT_OVERREACH_RE.finditer(text):
            if _has_unnegated_affirmative_token(text, verdict_match):
                blockers.append(blocked_item(path, "verdict_overreach_wording", "text exceeds paired-readiness boundary"))
        for provider_match in PROVIDER_EXECUTION_CLAIM_RE.finditer(text):
            if not _is_locally_negated(text, provider_match.start()):
                blockers.append(blocked_item(path, "provider_canary_execution_text_claim", "text cannot claim provider/backend/canary execution in v3.8M"))
        for runtime_match in CODEX_FORMAL_EXECUTION_CLAIM_RE.finditer(text):
            if not _is_locally_negated(text, runtime_match.start()):
                blockers.append(blocked_item(path, "codex_or_formal_lite_execution_text_claim", "text cannot claim Codex CLI or formal-lite execution in v3.8M"))
        for legacy_match in LEGACY_BACKEND_RE.finditer(text):
            if not _is_locally_negated(text, legacy_match.start()):
                blockers.append(blocked_item(path, "legacy_backend_reference", "legacy provider/backend references are not authorized in v3.8M"))
        for match in COMPARATIVE_CLAIM_RE.finditer(text):
            if not claim_scan.is_negated(text, match.start()):
                blockers.append(blocked_item(path, "comparative_or_action_guidance_claim", "comparative or action-guidance wording exceeds readiness boundary"))
    return blockers


def _has_unnegated_affirmative_token(text: str, match: re.Match[str]) -> bool:
    for token in AFFIRMATIVE_STATUS_TOKEN_RE.finditer(match.group(0)):
        if not _is_locally_negated(text, match.start() + token.start()):
            return True
    return False


def _is_locally_negated(text: str, position: int) -> bool:
    lowered = text.lower()
    clause_start = 0
    for separator in (".", ";", "\n"):
        idx = lowered.rfind(separator, 0, position)
        if idx >= 0:
            clause_start = max(clause_start, idx + 1)
    for separator in (" but ", " however ", " yet "):
        idx = lowered.rfind(separator, 0, position)
        if idx >= 0:
            clause_start = max(clause_start, idx + len(separator))
    window = lowered[clause_start : min(len(lowered), position + 40)]
    return bool(re.search(r"\b(?:not|no|never|without|false|forbidden|blocked|remain(?:s)? not)\b.{0,40}$", window[: max(0, position - clause_start)]))


def direct_boundary_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if payload.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_PREFIX + "_interpretation_mismatch", "direct_llm_parametric_memory_control interpretation must remain explicit"))
    if payload.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(blocked_item(f"summary.{DIRECT_CLEAN_BASELINE_KEY}", DIRECT_PREFIX + "_clean_baseline_not_false", "direct_llm_parametric_memory_control cannot be a clean baseline"))
    identity = payload.get("paired_sample_identity_schema")
    if isinstance(identity, dict):
        if identity.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
            blockers.append(blocked_item("summary.paired_sample_identity_schema", DIRECT_PREFIX + "_identity_clean_baseline_not_false", "paired identity schema must keep direct control non-clean"))
        if identity.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
            blockers.append(blocked_item("summary.paired_sample_identity_schema", DIRECT_PREFIX + "_identity_interpretation_mismatch", "paired identity schema must name the parametric-memory control"))
    for path, text in recursive_strings(payload, path="readiness"):
        for match in DIRECT_UNSAFE_RE.finditer(text):
            role_match = DIRECT_UNSAFE_ROLE_RE.search(match.group(0))
            role_start = match.start() + role_match.start() if role_match else match.start()
            if not claim_scan.is_negated(text, role_start):
                blockers.append(blocked_item(path, DIRECT_PREFIX + "_unsafe_role_wording", "direct_llm_parametric_memory_control cannot be clean/no-future/no-memory or primary comparator"))
    return blockers


def path_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for key_hint, candidate in recursive_paths(payload):
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocked_item(candidate, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
        elif (key_hint.startswith("raw") or _looks_like_raw_path(candidate) or _looks_like_transcript_path(candidate)) and not under_tmp(candidate):
            blockers.append(blocked_item(candidate, "raw_reference_not_tmp", "raw-like or transcript path references must stay under /tmp"))
    return blockers


def _looks_like_raw_path(value: str) -> bool:
    if not RAW_PATH_RE.search(value):
        return False
    lowered = value.lower()
    if re.search(r"\s", value) and not lowered.endswith((".json", ".jsonl", ".txt", ".md", ".log")):
        return False
    return "/" in value or "\\" in value or lowered.endswith((".json", ".jsonl", ".txt", ".md", ".log"))


def _looks_like_transcript_path(value: str) -> bool:
    if "transcript" not in value.lower():
        return False
    lowered = value.lower()
    if re.search(r"\s", value) and not lowered.endswith((".txt", ".json", ".jsonl", ".md", ".log")):
        return False
    return "/" in value or "\\" in value or lowered.endswith((".txt", ".json", ".jsonl", ".md", ".log"))


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in RUNTIME_FALSE_FLAGS:
        if flag not in summary:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_missing", f"{flag} must be explicitly present and false"))
        elif summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8M itself"))
    if not is_numeric_zero(summary.get("real_calls_count")):
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_not_numeric_zero", "v3.8M real call count must be integer zero"))
    if not is_numeric_zero(summary.get("token_usage_total")):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_not_numeric_zero", "v3.8M token usage must be integer zero"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("summary.next_check_after", "next_check_after_mismatch", "next_check_after must remain the maturity gate timestamp"))
    if summary.get("cognitive_lift_superiority_verdict_status") != SUPERIORITY_STATUS:
        blockers.append(blocked_item("summary.cognitive_lift_superiority_verdict_status", "superiority_status_invalid", "formal comparative conclusion must remain not ready"))
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("summary.evidence_layer", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if summary.get("raw_tmp_only") is not True:
        blockers.append(blocked_item("summary.raw_tmp_only", "raw_tmp_only_not_true", "raw boundary must remain /tmp-only"))
    if summary.get("no_raw_repo") is not True:
        blockers.append(blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "repo must not contain raw payloads"))
    return blockers


def authorization_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("provider_canary_authorization_status") != AUTHORIZATION_STATUS:
        blockers.append(blocked_item("summary.provider_canary_authorization_status", "provider_canary_authorization_status_not_placeholder", "top-level provider canary authorization status must remain non-executable placeholder"))
    checklist = summary.get("future_provider_30d_verdict_authorization_checklist")
    if not isinstance(checklist, dict):
        return [blocked_item("summary.future_provider_30d_verdict_authorization_checklist", "authorization_checklist_not_object", "authorization checklist must be an object")]
    required = {
        "candidate_provider_backend_model",
        "call_cap",
        "token_cap",
        "cost_cap",
        "placeholder_caps_only",
        "execution_allowed",
        "provider_canary_execution_allowed",
        "actual_30d_verdict_execution_allowed",
        "raw_output_boundary",
        "usage_metadata_required",
        "no_actual_30d_verdict",
        "no_superiority_verdict",
        "no_public_science_trading_claim",
        "authorization_status",
        "authorization_required_before_execution",
    }
    blockers.extend(
        blocked_item(f"summary.future_provider_30d_verdict_authorization_checklist.{key}", "authorization_missing_field", f"{key} is required")
        for key in sorted(required - set(checklist))
    )
    if checklist.get("candidate_provider_backend_model") != f"{DEFAULT_BACKEND_NAME} / {DEFAULT_MODEL}":
        blockers.append(blocked_item("authorization.candidate_provider_backend_model", "authorization_backend_model_mismatch", "candidate backend/model must match bounded Codex backend metadata"))
    if checklist.get("authorization_status") != AUTHORIZATION_STATUS:
        blockers.append(blocked_item("authorization.authorization_status", "authorization_status_not_placeholder", "v3.8M can only record non-executable placeholder caps"))
    if checklist.get("call_cap") != "X" or checklist.get("token_cap") != "Y" or checklist.get("cost_cap") != "Z":
        blockers.append(blocked_item("authorization.placeholder_caps", "authorization_concrete_caps_not_allowed", "concrete caps require a future separate user authorization"))
    if checklist.get("placeholder_caps_only") is not True:
        blockers.append(blocked_item("authorization.placeholder_caps_only", "placeholder_caps_only_not_true", "X/Y/Z caps must remain non-executable placeholders"))
    for key in ("execution_allowed", "provider_canary_execution_allowed", "actual_30d_verdict_execution_allowed"):
        if checklist.get(key) is not False:
            blockers.append(blocked_item(f"authorization.{key}", f"{key}_not_false", "execution is not authorized in v3.8M"))
    for key in ("usage_metadata_required", "no_actual_30d_verdict", "no_superiority_verdict", "no_public_science_trading_claim", "authorization_required_before_execution"):
        if checklist.get(key) is not True:
            blockers.append(blocked_item(f"authorization.{key}", f"{key}_not_true", "authorization checklist boundary attestation must be true"))
    if checklist.get("raw_output_boundary") != "/tmp only":
        blockers.append(blocked_item("authorization.raw_output_boundary", "authorization_raw_boundary_invalid", "future raw outputs must remain /tmp-only"))
    return blockers


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(blocked_item("summary.schema", "summary_schema_mismatch", f"schema must be {SUMMARY_SCHEMA}"))
    if str(summary.get("readiness_status") or "") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.readiness_status", "invalid_readiness_status", "readiness_status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if not _is_iso_utc(summary.get("generated_at")):
        blockers.append(blocked_item("summary.generated_at", "generated_at_invalid", "generated_at must be an ISO UTC timestamp ending in Z"))
    if summary.get("package_sections") != list(PACKAGE_SECTIONS):
        blockers.append(blocked_item("summary.package_sections", "package_sections_mismatch", "package sections must match v3.8M contract"))
    _validate_identity_schema(summary.get("paired_sample_identity_schema"), blockers)
    _validate_scoring_prerequisites(summary.get("scoring_execution_prerequisites"), blockers)
    _validate_maturity(summary.get("maturity_readiness_blockers"), blockers)
    _validate_statistical(summary.get("statistical_eligibility_checklist"), blockers)
    _validate_claim_gate(summary.get("claim_boundary_gate"), blockers)
    for key in ("can_say", "cannot_say", "missing_before_superiority_verdict", "authorization_required_before_execution"):
        value = summary.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            blockers.append(blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))
    return blockers


def _validate_identity_schema(value: Any, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        blockers.append(blocked_item("summary.paired_sample_identity_schema", "paired_identity_schema_not_object", "paired identity schema must be object"))
        return
    fields = value.get("required_fields")
    if not isinstance(fields, list) or set(fields) != set(PAIRED_IDENTITY_FIELDS):
        blockers.append(blocked_item("summary.paired_sample_identity_schema.required_fields", "paired_identity_required_fields_mismatch", "paired identity schema must include every required identity field"))
    if value.get("allowed_arms") != list(ALLOWED_ARMS):
        blockers.append(blocked_item("summary.paired_sample_identity_schema.allowed_arms", "paired_identity_allowed_arms_mismatch", "paired identity schema must list all arms"))
    if value.get("arm_identity_required") is not True:
        blockers.append(blocked_item("summary.paired_sample_identity_schema.arm_identity_required", "arm_identity_required_not_true", "arm identity is required"))
    if value.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(blocked_item("summary.paired_sample_identity_schema", DIRECT_PREFIX + "_identity_clean_baseline_not_false", "direct control cannot be clean baseline"))
    if value.get("matched_identity_fields") != [
        "paired_sample_id",
        "ticker",
        "decision_date",
        "horizon",
        "prompt_hash",
        "input_hash",
        "visible_data_boundary",
        "rubric_version",
    ]:
        blockers.append(blocked_item("summary.paired_sample_identity_schema.matched_identity_fields", "paired_identity_matched_fields_mismatch", "paired identity schema must preserve prompt/input and visible-boundary matching"))
    if value.get("minimum_provenance_requirements") != [
        "source_run_id",
        "source_summary_sha256",
        "source_artifact_sha256",
    ]:
        blockers.append(blocked_item("summary.paired_sample_identity_schema.minimum_provenance_requirements", "paired_identity_minimum_provenance_mismatch", "paired identity schema must preserve source run and hash provenance requirements"))
    role = value.get("direct_control_role")
    if role != "historical diagnostic/control arm with parametric memory boundary":
        blockers.append(blocked_item("summary.paired_sample_identity_schema.direct_control_role", "direct_control_role_mismatch", "direct control role must remain historical diagnostic/control with parametric-memory boundary"))
    if isinstance(role, str) and DIRECT_UNSAFE_ROLE_RE.search(role):
        blockers.append(blocked_item("summary.paired_sample_identity_schema.direct_control_role", DIRECT_PREFIX + "_unsafe_identity_role", "direct control role cannot be clean/no-future/no-memory or primary comparator"))


def _validate_scoring_prerequisites(value: Any, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        blockers.append(blocked_item("summary.scoring_execution_prerequisites", "scoring_prerequisites_not_object", "scoring prerequisites must be object"))
        return
    for key in ("locked_rubric_required", "paired_records_completeness_required", "source_hashes_required", "blind_or_locked_scoring_metadata_required"):
        if value.get(key) is not True:
            blockers.append(blocked_item(f"summary.scoring_execution_prerequisites.{key}", f"{key}_not_true", "scoring prerequisite is required"))
    if value.get("rubric_version") != RUBRIC_SCHEMA_VERSION:
        blockers.append(blocked_item("summary.scoring_execution_prerequisites.rubric_version", "rubric_version_mismatch", "rubric version must match v3.8J"))
    if value.get("raw_output_boundary") != "/tmp only":
        blockers.append(blocked_item("summary.scoring_execution_prerequisites.raw_output_boundary", "scoring_raw_boundary_invalid", "raw boundary must be /tmp only"))
    if value.get("real_scoring_executed") is not False:
        blockers.append(blocked_item("summary.scoring_execution_prerequisites.real_scoring_executed", "real_scoring_executed_not_false", "v3.8M cannot execute scoring"))


def _validate_maturity(value: Any, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        blockers.append(blocked_item("summary.maturity_readiness_blockers", "maturity_readiness_not_object", "maturity readiness blockers must be object"))
        return
    if value.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.maturity_readiness_blockers.actual_30d_readiness_status", "maturity_readiness_status_not_data_not_matured", "maturity blocker must preserve DATA_NOT_MATURED"))
    if value.get("next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("summary.maturity_readiness_blockers.next_check_after", "maturity_next_check_after_mismatch", "maturity next check timestamp mismatch"))
    if value.get("mature_paired_evidence_available") is not False:
        blockers.append(blocked_item("summary.maturity_readiness_blockers.mature_paired_evidence_available", "mature_paired_evidence_not_false", "mature paired evidence is not available"))
    if value.get("actual_v3_7_verdict_executable") is not False:
        blockers.append(blocked_item("summary.maturity_readiness_blockers.actual_v3_7_verdict_executable", "actual_v3_7_verdict_executable_not_false", "actual verdict remains not executable"))
    if value.get("actual_v3_7_verdict_executed") is not False:
        blockers.append(blocked_item("summary.maturity_readiness_blockers.actual_v3_7_verdict_executed", "actual_v3_7_verdict_executed_not_false", "actual verdict remains not executed"))


def _validate_statistical(value: Any, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        blockers.append(blocked_item("summary.statistical_eligibility_checklist", "statistical_checklist_not_object", "statistical checklist must be object"))
        return
    for key in ("sample_size_ready", "paired_clean_count_ready", "bootstrap_hac_eligible"):
        if value.get(key) is not False:
            blockers.append(blocked_item(f"summary.statistical_eligibility_checklist.{key}", f"{key}_not_false", "statistical eligibility is not satisfied in v3.8M"))
    for key in ("same_horizon_required",):
        if value.get(key) is not True:
            blockers.append(blocked_item(f"summary.statistical_eligibility_checklist.{key}", f"{key}_not_true", "same-horizon rule is required"))
    for key in ("p_value_before_eligibility_allowed", "estimate_before_eligibility_allowed", "confidence_interval_before_eligibility_allowed", "bootstrap_hac_fields_before_eligibility_allowed"):
        if value.get(key) is not False:
            blockers.append(blocked_item(f"summary.statistical_eligibility_checklist.{key}", f"{key}_not_false", "estimate/statistical fields are blocked before eligibility"))


def _validate_claim_gate(value: Any, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        blockers.append(blocked_item("summary.claim_boundary_gate", "claim_gate_not_object", "claim-boundary gate must be object"))
        return
    if value.get("cognitive_lift_superiority_verdict") != SUPERIORITY_STATUS:
        blockers.append(blocked_item("summary.claim_boundary_gate.cognitive_lift_superiority_verdict", "claim_gate_superiority_status_invalid", "formal comparative conclusion remains not ready"))
    for key in ("no_public_science_trading_claim", "no_investment_or_trading_guidance"):
        if value.get(key) is not True:
            blockers.append(blocked_item(f"summary.claim_boundary_gate.{key}", f"{key}_not_true", "claim boundary attestation is required"))


def source_stage_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    stages = summary.get("source_stages")
    if not isinstance(stages, list):
        return [blocked_item("summary.source_stages", "source_stages_not_list", "source_stages must be list")]
    canonical_by_id = canonical_stage_map()
    stage_ids: list[str] = []
    for index, stage in enumerate(stages):
        stage_path = f"summary.source_stages[{index}]"
        if not isinstance(stage, dict):
            blockers.append(blocked_item(stage_path, "source_stage_not_object", "source stage must be object"))
            continue
        missing = sorted(REQUIRED_STAGE_FIELDS - set(stage))
        blockers.extend(blocked_item(f"{stage_path}.{key}", "source_stage_missing_field", f"{key} is required") for key in missing)
        stage_id = str(stage.get("stage_id") or "")
        stage_ids.append(stage_id)
        expected = EXPECTED_STAGE_EVIDENCE.get(stage_id)
        if expected is None:
            blockers.append(blocked_item(f"{stage_path}.stage_id", "source_stage_unexpected", "unexpected source stage id"))
            continue
        canonical_stage = canonical_by_id[stage_id]
        for canonical_key, canonical_value in canonical_stage.items():
            if canonical_key == "metadata_sha256":
                continue
            if stage.get(canonical_key) != canonical_value:
                blockers.append(blocked_item(f"{stage_path}.{canonical_key}", f"source_stage_{canonical_key}_canonical_mismatch", f"{canonical_key} must match canonical source-stage payload"))
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
        if stage.get("metadata_sha256") != canonical_stage["metadata_sha256"]:
            blockers.append(blocked_item(f"{stage_path}.metadata_sha256", "source_metadata_sha256_mismatch", "metadata hash must match canonical source-stage payload"))
    if stage_ids != list(STAGE_ORDER):
        blockers.append(blocked_item("summary.source_stages", "source_stage_order_mismatch", "source stages must be present in canonical order"))
    if sorted(stage_ids) != sorted(STAGE_ORDER):
        blockers.append(blocked_item("summary.source_stages", "source_stage_set_mismatch", "summary must include each canonical source stage exactly once"))
    return blockers


def evidence_digest_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    canonical_stages = canonical_source_stages()
    canonical_hashes = {stage["stage_id"]: stage.get("metadata_sha256") for stage in canonical_stages}
    canonical_statuses = {stage["stage_id"]: stage.get("status") for stage in canonical_stages}
    if summary.get("source_stage_hashes") != canonical_hashes:
        blockers.append(blocked_item("summary.source_stage_hashes", "source_stage_hashes_mismatch", "source stage hashes must match canonical source-stage payloads"))
    if summary.get("source_stage_statuses") != canonical_statuses:
        blockers.append(blocked_item("summary.source_stage_statuses", "source_stage_statuses_mismatch", "source stage statuses must match canonical evidence"))
    if not is_hex(summary.get("source_stage_metadata_sha256"), 64):
        blockers.append(blocked_item("summary.source_stage_metadata_sha256", "source_stage_metadata_sha256_invalid", "source metadata digest is required"))
    elif summary.get("source_stage_metadata_sha256") != stable_sha256_json(canonical_stages):
        blockers.append(blocked_item("summary.source_stage_metadata_sha256", "source_stage_metadata_sha256_mismatch", "source metadata digest must match canonical source-stage payloads"))
    if not is_hex(summary.get("readiness_package_sha256"), 64):
        blockers.append(blocked_item("summary.readiness_package_sha256", "readiness_package_sha256_invalid", "readiness package digest is required"))
    elif summary.get("readiness_package_sha256") != readiness_package_digest(summary):
        blockers.append(blocked_item("summary.readiness_package_sha256", "readiness_package_sha256_mismatch", "readiness package digest must cover boundary-critical fields"))
    return blockers


def _is_iso_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(schema_blockers(summary))
    blockers.extend(source_stage_blockers(summary))
    blockers.extend(evidence_digest_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(authorization_blockers(summary))
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(path_blockers(summary))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_rule_has(item, ("schema", "missing", "invalid", "not_object", "not_list")) for item in blockers) else "clean"
    summary["provenance_status"] = "blocked" if any(_rule_has(item, ("source_stage", "source_", "metadata_sha256", "readiness_package_sha256")) for item in blockers) else "clean"
    summary["missing_evidence_boundary_status"] = "blocked" if summary["provenance_status"] == "blocked" else "clean"
    summary["maturity_readiness_status"] = "blocked" if any(_rule_has(item, ("maturity", "actual_30d", "next_check", "verdict_executable", "verdict_executed")) for item in blockers) else "blocked_expected"
    summary["statistical_eligibility_status"] = "blocked" if any(_rule_has(item, ("statistical", "sample_size", "paired_clean", "p_value", "estimate", "bootstrap", "confidence_interval")) for item in blockers) else "blocked_expected"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim", "overclaim", "comparative_or_action")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "flag", "provider", "backend", "executable", "canary", "codex", "formal", "calls", "token", "scoring_executed")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "raw_reference", "raw_tmp", "repo_raw", "transcript")) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control")) for item in blockers) else "clean"
    summary["authorization_boundary_status"] = "blocked" if any(_rule_has(item, ("authorization", "placeholder_cap", "execution_allowed", "legacy_backend")) for item in blockers) else "clean"
    summary["verdict_boundary_status"] = "blocked" if any(_rule_has(item, ("verdict_overreach", "actual_or_superiority_verdict")) for item in blockers) else "clean"


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def choose_status(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any(DIRECT_PREFIX in reason or "direct_control" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("forbidden_artifact" in reason or "raw_reference" in reason or "raw_tmp" in reason or "transcript" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("provider_canary_execution_text_claim" in reason or "codex_or_formal_lite_execution_text_claim" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("legacy_backend_reference" in reason for reason in reasons):
        return STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    if any("authorization" in reason or "placeholder_cap" in reason or "execution_allowed" in reason for reason in reasons):
        return STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    if any("verdict_overreach" in reason or "actual_or_superiority_verdict" in reason or "comparative_or_action" in reason for reason in reasons):
        return STATUS_BLOCKED_VERDICT_OVERREACH
    if any("maturity" in reason or "actual_30d" in reason or "next_check" in reason or "verdict_executable" in reason or "verdict_executed" in reason for reason in reasons):
        return STATUS_BLOCKED_MATURITY_READINESS
    if any("statistical" in reason or "sample_size" in reason or "paired_clean" in reason or "p_value" in reason or "estimate" in reason or "bootstrap" in reason for reason in reasons):
        return STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    if any("source_stage" in reason or "source_" in reason or "metadata_sha256" in reason or "readiness_package_sha256" in reason for reason in reasons):
        return STATUS_BLOCKED_MISSING_EVIDENCE
    if any(reason.endswith("_not_false") or "real_calls_count" in reason or "token_usage_total" in reason or "runtime" in reason or "flag" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("claim" in reason or "overclaim" in reason for reason in reasons):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if any("provenance" in reason for reason in reasons):
        return STATUS_BLOCKED_PROVENANCE
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


def fixture_identity_blockers(payload: dict[str, Any], *, config: ReadinessConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "readiness_pack_id": config.readiness_pack_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: ReadinessConfig, run_root: Path) -> None:
    summary["readiness_pack_id"] = config.readiness_pack_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_summary(config: ReadinessConfig) -> dict[str, Any]:
    try:
        validate_run_id(config.readiness_pack_id)
    except ValueError:
        safe_config = ReadinessConfig(
            readiness_pack_id=f"{RUN_ID_PREFIX}invalid",
            output_dir=Path("/tmp") / "gotra_v3_8m_invalid_readiness_pack_id",
            allow_overwrite=False,
            summary_fixture=config.summary_fixture,
        )
        run_root = safe_config.output_dir / safe_config.readiness_pack_id
        summary = base_summary(safe_config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
        blockers = [blocked_item("summary.readiness_pack_id", "readiness_pack_id_invalid", "readiness_pack_id failed validation")]
        summary["requested_readiness_pack_id"] = str(config.readiness_pack_id)
        summary["readiness_status"] = choose_status(blockers)
        finalize_blockers(summary, blockers)
        return summary
    run_root = config.output_dir / config.readiness_pack_id
    if not under_tmp(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(config.output_dir, "output_dir_not_tmp", "output_dir must be under /tmp")]
        summary["readiness_status"] = choose_status(blockers)
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        blockers = [blocked_item(run_root, "run_id_exists", "readiness_pack_id already exists; use --allow-overwrite")]
        summary["readiness_status"] = STATUS_RUN_ID_EXISTS
        finalize_blockers(summary, blockers)
        return summary
    if config.summary_fixture:
        fixture_payload, fixture_errors = load_summary_fixture(config.summary_fixture)
        if fixture_errors:
            summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
            summary["readiness_status"] = choose_status(fixture_errors)
            finalize_blockers(summary, fixture_errors)
            write_outputs(summary, config=config, run_root=run_root)
            return summary
        identity_errors = fixture_identity_blockers(fixture_payload, config=config, run_root=run_root)
        summary = dict(fixture_payload)
        restore_config_identity(summary, config=config, run_root=run_root)
        blockers = identity_errors + validate_summary_payload(summary)
        summary["readiness_status"] = choose_status(blockers)
        finalize_blockers(summary, blockers)
        write_outputs(summary, config=config, run_root=run_root)
        return summary
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    summary["readiness_status"] = choose_status(blockers)
    finalize_blockers(summary, blockers)
    write_outputs(summary, config=config, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, config: ReadinessConfig, run_root: Path) -> None:
    if run_root.exists():
        if not config.allow_overwrite:
            raise FileExistsError(f"{run_root} already exists")
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observed_authorization_status = summary.get("provider_canary_authorization_status")
    manifest_authorization_status = (
        observed_authorization_status
        if observed_authorization_status == AUTHORIZATION_STATUS
        else AUTHORIZATION_STATUS
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "readiness_pack_id": summary.get("readiness_pack_id"),
        "readiness_status": summary.get("readiness_status"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "provider_or_backend_called": summary.get("provider_or_backend_called"),
        "provider_canary_executed": summary.get("provider_canary_executed"),
        "real_calls_count": summary.get("real_calls_count"),
        "token_usage_total": summary.get("token_usage_total"),
        "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
        "provider_canary_authorization_status": manifest_authorization_status,
        "provider_canary_authorization_status_observed": observed_authorization_status,
        "evidence_layer": summary.get("evidence_layer"),
        "generated_at": utc_now_iso(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-pack-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8m_paired_cognitive_lift_evaluation_readiness"))
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_run_id(args.readiness_pack_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    config = ReadinessConfig(
        readiness_pack_id=args.readiness_pack_id,
        output_dir=args.output_dir,
        allow_overwrite=args.allow_overwrite,
        summary_fixture=args.summary_fixture,
    )
    summary = build_summary(config)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("readiness_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
