#!/usr/bin/env python3
"""GOTRA v3.8J cognitive-lift rubric/prereg schema validator."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_8j.cognitive_lift_rubric_prereg_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8j.cognitive_lift_rubric_prereg_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8j_cognitive_lift_rubric_prereg_"
SCRIPT_VERSION = "v3.8j-20260622"
SCHEMA_VERSION = "v3.8j.cognitive_lift_rubric.v1"
EVIDENCE_LAYER = "engineering_internal_cognitive_lift_rubric_prereg_schema"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
SUPERIORITY_STATUS = "NOT_YET_VERDICT_READY"
CL_CANDIDATE_STATUS = "RUBRIC_PREREG_DEFINED_ONLY"

STATUS_READY = "COGNITIVE_LIFT_RUBRIC_PREREG_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROTOCOL = "BLOCKED_PROTOCOL"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_RUN_ID_EXISTS = "COGNITIVE_LIFT_RUBRIC_PREREG_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_PROTOCOL,
    STATUS_BLOCKED_PROVENANCE,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

DIMENSIONS = (
    "problem_decomposition",
    "evidence_grounding",
    "provenance_completeness",
    "uncertainty_calibration",
    "overclaim_avoidance",
    "failure_recovery",
    "determinism_stability",
    "actionability",
)
ALLOWED_ARMS = ("ksana_real_research", "full_gotra", claim_scan.DIRECT_LLM_INTERPRETATION)
DIRECT_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DIRECT_PREFIX = "direct" + "_llm"
DIRECT_INTERPRETATION_KEY = "direct" + "_llm_interpretation"
DIRECT_CLEAN_BASELINE_KEY = "direct" + "_llm_clean_baseline"
SECRET_RE = packet_canary.SECRET_RE
LEGACY_BACKEND_RE = re.compile(r"\b(?:ki" + "mi|g" + "lm|deep" + "seek)\b", re.IGNORECASE)
VERDICT_WORD = "verd" + "ict"
COMPARATIVE_RESULT_WORD = "win" + "ner"
STATUS_CLAIM_RE = re.compile(
    rf"(?:v3[\._]?7|v3[\._]?8|30d|30-day|actual|cognitive[-_ ]lift).{{0,90}}"
    rf"(?:{VERDICT_WORD}|readiness|executable|superiority).{{0,70}}(?:ready|pass|allowed|true|executed|proved|validated)",
    re.IGNORECASE,
)
COMPARATIVE_CLAIM_RE = re.compile(
    rf"\b(?:{COMPARATIVE_RESULT_WORD}|out" + r"perform|pro" + r"fit|al" + r"pha|trading adv" + r"ice|investment adv" + r"ice)\b",
    re.IGNORECASE,
)
DIRECT_UNSAFE_RE = re.compile(
    r"(?:direct_llm|direct_llm_parametric_memory_control).{0,80}(?:clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline)",
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
    "schema_version",
    "script_version",
    "prereg_id",
    "generated_at",
    "evidence_layer",
    "rubric_status",
    "dimension_count",
    "dimensions",
    "paired_comparison_protocol",
    "allowed_arms",
    DIRECT_INTERPRETATION_KEY,
    DIRECT_CLEAN_BASELINE_KEY,
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
    "cognitive_lift_candidate_status",
    "cognitive_lift_superiority_verdict_status",
    "can_say",
    "cannot_say",
}
REQUIRED_DIMENSION_FIELDS = {
    "dimension_id",
    "description",
    "allowed_score_range",
    "required_evidence_fields",
    "blocker_conditions",
    "claim_boundary_notes",
    "minimum_provenance_requirements",
}
REQUIRED_PROTOCOL_FIELDS = {
    "arms",
    "primary_arms",
    "diagnostic_control_arm",
    "paired_keys",
    "matched_prompt_input_identity_required",
    "same_visible_data_boundary_required",
    "same_horizon_readiness_gate_required",
    "same_scoring_rubric_version_required",
    "blind_or_locked_scoring_metadata_required",
    "per_dimension_scores_required",
    "aggregate_score_rules",
    "missing_data_handling",
    "tie_inconclusive_handling",
    "overclaim_block_conditions",
    "future_data_block_conditions",
    "minimum_provenance_requirements",
}


@dataclass(frozen=True)
class RubricConfig:
    prereg_id: str
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


def base_dimensions() -> list[dict[str, Any]]:
    descriptions = {
        "problem_decomposition": "Breaks a synthetic research problem into explicit subquestions and decision-relevant unknowns.",
        "evidence_grounding": "Links each conclusion candidate to visible input facts and structured evidence fields.",
        "provenance_completeness": "Carries run, prompt, input, and artifact identity through each scored record.",
        "uncertainty_calibration": "Separates confidence, uncertainty sources, and falsification triggers.",
        "overclaim_avoidance": "Keeps engineering evidence separate from external proof or advice wording.",
        "failure_recovery": "Records parse, schema, metadata, and boundary failures without retry storms.",
        "determinism_stability": "Supports repeatable fixture scoring and stable digest comparison.",
        "actionability": "Produces bounded next-step information without issuing recommendations.",
    }
    dimensions: list[dict[str, Any]] = []
    for dimension_id in DIMENSIONS:
        dimensions.append(
            {
                "dimension_id": dimension_id,
                "description": descriptions[dimension_id],
                "allowed_score_range": {"type": "integer", "min": 0, "max": 4},
                "required_evidence_fields": [
                    "paired_sample_id",
                    "input_hash",
                    "prompt_hash",
                    f"{dimension_id}_evidence",
                ],
                "blocker_conditions": [
                    "missing paired sample identity",
                    "missing source hash or run id",
                    "future-visible data boundary mismatch",
                ],
                "claim_boundary_notes": [
                    "score is fixture/prereg evidence only",
                    "do not convert score into public proof or advice",
                ],
                "minimum_provenance_requirements": [
                    "source_run_id",
                    "source_summary_sha256",
                    "source_artifact_sha256",
                ],
            }
        )
    return dimensions


def base_protocol() -> dict[str, Any]:
    return {
        "arms": list(ALLOWED_ARMS),
        "primary_arms": ["ksana_real_research", "full_gotra"],
        "diagnostic_control_arm": DIRECT_INTERPRETATION,
        "control_arm_role": "historical diagnostic/control arm with parametric memory boundary",
        "paired_keys": [
            "paired_sample_id",
            "ticker",
            "decision_date",
            "horizon",
            "prompt_hash",
            "input_hash",
        ],
        "matched_prompt_input_identity_required": True,
        "same_visible_data_boundary_required": True,
        "same_horizon_readiness_gate_required": True,
        "same_scoring_rubric_version_required": True,
        "blind_or_locked_scoring_metadata_required": True,
        "per_dimension_scores_required": True,
        "aggregate_score_rules": {
            "method": "pre_registered_dimension_sum_with_inconclusive_ties",
            "requires_all_dimensions": True,
            "score_range": {"type": "integer", "min": 0, "max": 4},
        },
        "missing_data_handling": "mark paired sample inconclusive; do not impute",
        "tie_inconclusive_handling": "tie or missing critical provenance stays inconclusive",
        "overclaim_block_conditions": [
            "comparative result phrased as proof",
            "external proof or advice wording",
        ],
        "future_data_block_conditions": [
            "visible data timestamp after decision boundary",
            "readiness gate mismatch",
        ],
        "minimum_provenance_requirements": [
            "source_run_id",
            "source_summary_sha256",
            "source_artifact_sha256",
            "prompt_hash",
            "input_hash",
            "visible_data_boundary",
        ],
    }


def base_summary(config: RubricConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    dimensions = base_dimensions()
    summary = {
        "schema": SUMMARY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "prereg_id": config.prereg_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "rubric_status": status,
        "dimension_count": len(dimensions),
        "dimensions": dimensions,
        "paired_comparison_protocol": base_protocol(),
        "allowed_arms": list(ALLOWED_ARMS),
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
        "v3_8j_real_calls_count": 0,
        "v3_8j_token_usage_total": 0,
        "cognitive_lift_candidate_status": CL_CANDIDATE_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "rubric_prereg_sha256": "",
        "schema_status": "clean",
        "protocol_status": "clean",
        "provenance_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "direct_llm_boundary_status": "clean",
        "can_say": ["rubric/prereg schema for future cognitive-lift paired evaluation is available for fixture-level validation"],
        "cannot_say": [
            "not actual evaluation",
            "not comparative result",
            "not actual 30D verdict",
            "not provider canary execution",
            "not OOS/science/public/trading claim",
            "not investment advice",
        ],
        "blocker_reasons": [],
        "blocked_items": [],
        "non_claims": {
            "not_actual_evaluation": True,
            "not_comparative_result": True,
            "not_actual_30d_verdict": True,
            "not_provider_canary_execution": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
    }
    summary["rubric_prereg_sha256"] = rubric_digest(summary)
    return summary


def rubric_digest(summary: dict[str, Any]) -> str:
    return stable_sha256_json(
        {
            "schema_version": summary.get("schema_version"),
            "dimensions": summary.get("dimensions"),
            "paired_comparison_protocol": summary.get("paired_comparison_protocol"),
            "allowed_arms": summary.get("allowed_arms"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "next_check_after": summary.get("next_check_after"),
            "cognitive_lift_candidate_status": summary.get("cognitive_lift_candidate_status"),
            "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
            "evidence_layer": summary.get("evidence_layer"),
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
        claim_scan.ScanSource(path=path, text=text, origin="v3_8j_rubric")
        for path, text in recursive_strings(payload, path="rubric")
    ]
    scan = claim_scan.scan_sources(sources)
    blockers = scan["overclaim"] + scan[DIRECT_PREFIX] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for path, text in recursive_strings(payload, path="rubric"):
        if STATUS_CLAIM_RE.search(text) and not claim_regression.FALSE_LINE_RE.search(text):
            blockers.append(blocked_item(path, "actual_or_superiority_verdict_claim", "text cannot assert current actual or superiority verdict readiness"))
        match = COMPARATIVE_CLAIM_RE.search(text)
        if match and not claim_scan.is_negated(text, match.start()):
            blockers.append(blocked_item(path, "comparative_or_advice_claim", "comparative or advice wording exceeds prereg boundary"))
    return blockers


def direct_boundary_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if payload.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(
            blocked_item(
                f"summary.{DIRECT_INTERPRETATION_KEY}",
                DIRECT_PREFIX + "_interpretation_mismatch",
                "direct_llm_parametric_memory_control interpretation must remain explicit",
            )
        )
    if payload.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(
            blocked_item(
                f"summary.{DIRECT_CLEAN_BASELINE_KEY}",
                DIRECT_PREFIX + "_clean_baseline_not_false",
                "direct_llm_parametric_memory_control cannot be a clean baseline",
            )
        )
    protocol = payload.get("paired_comparison_protocol")
    if isinstance(protocol, dict):
        if protocol.get("diagnostic_control_arm") != DIRECT_INTERPRETATION:
            blockers.append(blocked_item("summary.paired_comparison_protocol.diagnostic_control_arm", "direct_control_arm_mismatch", "diagnostic control arm must be parametric-memory control"))
        primary = protocol.get("primary_arms")
        if isinstance(primary, list) and DIRECT_INTERPRETATION in primary:
            blockers.append(blocked_item("summary.paired_comparison_protocol.primary_arms", "direct_control_as_primary_arm", "direct control arm cannot be primary comparator"))
    for path, text in recursive_strings(payload, path="rubric"):
        if DIRECT_UNSAFE_RE.search(text):
            blockers.append(
                blocked_item(
                    path,
                    DIRECT_PREFIX + "_unsafe_role_wording",
                    "direct_llm_parametric_memory_control cannot be clean/no-future/no-memory or primary comparator",
                )
            )
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
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8J itself"))
    if summary.get("provider_canary_executed") is not False:
        blockers.append(blocked_item("summary.provider_canary_executed", "provider_canary_executed_not_false", "provider canary execution is not part of v3.8J"))
    if summary.get("v3_8j_real_calls_count") != 0:
        blockers.append(blocked_item("summary.v3_8j_real_calls_count", "v3_8j_real_calls_not_zero", "v3.8J must not make real calls"))
    if summary.get("v3_8j_token_usage_total") != 0:
        blockers.append(blocked_item("summary.v3_8j_token_usage_total", "v3_8j_token_usage_not_zero", "v3.8J must not consume tokens"))
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


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(blocked_item("summary.schema", "summary_schema_mismatch", f"schema must be {SUMMARY_SCHEMA}"))
    if summary.get("schema_version") != SCHEMA_VERSION:
        blockers.append(blocked_item("summary.schema_version", "schema_version_mismatch", f"schema_version must be {SCHEMA_VERSION}"))
    if str(summary.get("rubric_status") or "") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.rubric_status", "invalid_rubric_status", "rubric_status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if not _is_iso_utc(summary.get("generated_at")):
        blockers.append(blocked_item("summary.generated_at", "generated_at_invalid", "generated_at must be an ISO UTC timestamp ending in Z"))
    if summary.get("cognitive_lift_candidate_status") != CL_CANDIDATE_STATUS:
        blockers.append(blocked_item("summary.cognitive_lift_candidate_status", "candidate_status_invalid", "candidate status must be planning-only"))
    dimensions = summary.get("dimensions")
    if not isinstance(dimensions, list):
        blockers.append(blocked_item("summary.dimensions", "dimensions_not_list", "dimensions must be a list"))
        return blockers
    if summary.get("dimension_count") != len(dimensions):
        blockers.append(blocked_item("summary.dimension_count", "dimension_count_mismatch", "dimension_count must match dimensions"))
    dimension_ids: list[str] = []
    for index, dimension in enumerate(dimensions):
        path = f"summary.dimensions[{index}]"
        if not isinstance(dimension, dict):
            blockers.append(blocked_item(path, "dimension_not_object", "dimension must be an object"))
            continue
        missing_dimension = sorted(REQUIRED_DIMENSION_FIELDS - set(dimension))
        blockers.extend(blocked_item(f"{path}.{key}", "dimension_missing_field", f"{key} is required") for key in missing_dimension)
        dimension_id = str(dimension.get("dimension_id") or "")
        dimension_ids.append(dimension_id)
        if dimension_id not in DIMENSIONS:
            blockers.append(blocked_item(f"{path}.dimension_id", "dimension_unexpected", "unexpected dimension id"))
        _validate_dimension(dimension, path, blockers)
    if dimension_ids != list(DIMENSIONS):
        blockers.append(blocked_item("summary.dimensions", "dimension_order_or_set_mismatch", "rubric must contain the eight required dimensions in order"))
    return blockers


def _validate_dimension(dimension: dict[str, Any], path: str, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(dimension.get("description"), str) or not dimension.get("description", "").strip():
        blockers.append(blocked_item(f"{path}.description", "dimension_description_missing", "dimension description must be non-empty"))
    score_range = dimension.get("allowed_score_range")
    if not isinstance(score_range, dict):
        blockers.append(blocked_item(f"{path}.allowed_score_range", "score_range_not_object", "score range must be an object"))
    else:
        min_score = score_range.get("min")
        max_score = score_range.get("max")
        if (
            score_range.get("type") != "integer"
            or not isinstance(min_score, int)
            or isinstance(min_score, bool)
            or not isinstance(max_score, int)
            or isinstance(max_score, bool)
            or min_score < 0
            or max_score <= min_score
        ):
            blockers.append(blocked_item(f"{path}.allowed_score_range", "score_range_invalid", "score range must be integer min/max with max > min"))
    for key in (
        "required_evidence_fields",
        "blocker_conditions",
        "claim_boundary_notes",
        "minimum_provenance_requirements",
    ):
        values = dimension.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))


def protocol_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    protocol = summary.get("paired_comparison_protocol")
    if not isinstance(protocol, dict):
        return [blocked_item("summary.paired_comparison_protocol", "protocol_not_object", "paired comparison protocol must be an object")]
    missing = sorted(REQUIRED_PROTOCOL_FIELDS - set(protocol))
    blockers.extend(blocked_item(f"summary.paired_comparison_protocol.{key}", "protocol_missing_field", f"{key} is required") for key in missing)
    if protocol.get("arms") != list(ALLOWED_ARMS):
        blockers.append(blocked_item("summary.paired_comparison_protocol.arms", "protocol_arms_mismatch", "protocol arms must match allowed arms"))
    if summary.get("allowed_arms") != list(ALLOWED_ARMS):
        blockers.append(blocked_item("summary.allowed_arms", "allowed_arms_mismatch", "allowed arms must be fixed"))
    if protocol.get("primary_arms") != ["ksana_real_research", "full_gotra"]:
        blockers.append(blocked_item("summary.paired_comparison_protocol.primary_arms", "protocol_primary_arms_mismatch", "primary arms must be ksana_real_research and full_gotra"))
    required_keys = {"paired_sample_id", "ticker", "decision_date", "horizon", "prompt_hash", "input_hash"}
    paired_keys = protocol.get("paired_keys")
    if not isinstance(paired_keys, list) or not required_keys.issubset(set(paired_keys)):
        blockers.append(blocked_item("summary.paired_comparison_protocol.paired_keys", "protocol_paired_keys_incomplete", "paired protocol needs sample/input identity keys"))
    for key in (
        "matched_prompt_input_identity_required",
        "same_visible_data_boundary_required",
        "same_horizon_readiness_gate_required",
        "same_scoring_rubric_version_required",
        "blind_or_locked_scoring_metadata_required",
        "per_dimension_scores_required",
    ):
        if protocol.get(key) is not True:
            blockers.append(blocked_item(f"summary.paired_comparison_protocol.{key}", f"{key}_not_true", f"{key} must be true"))
    aggregate = protocol.get("aggregate_score_rules")
    if not isinstance(aggregate, dict) or aggregate.get("requires_all_dimensions") is not True:
        blockers.append(blocked_item("summary.paired_comparison_protocol.aggregate_score_rules", "aggregate_score_rules_invalid", "aggregate rules must require all dimensions"))
    for key in (
        "missing_data_handling",
        "tie_inconclusive_handling",
        "overclaim_block_conditions",
        "future_data_block_conditions",
        "minimum_provenance_requirements",
    ):
        value = protocol.get(key)
        if isinstance(value, list):
            if not value or not all(isinstance(item, str) and item.strip() for item in value):
                blockers.append(blocked_item(f"summary.paired_comparison_protocol.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))
        elif not isinstance(value, str) or not value.strip():
            blockers.append(blocked_item(f"summary.paired_comparison_protocol.{key}", f"{key}_invalid", f"{key} must be non-empty"))
    return blockers


def provenance_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    protocol = summary.get("paired_comparison_protocol")
    if isinstance(protocol, dict):
        provenance = protocol.get("minimum_provenance_requirements")
        required = {"source_run_id", "source_summary_sha256", "source_artifact_sha256", "prompt_hash", "input_hash", "visible_data_boundary"}
        if not isinstance(provenance, list) or not required.issubset(set(provenance)):
            blockers.append(blocked_item("summary.paired_comparison_protocol.minimum_provenance_requirements", "protocol_provenance_incomplete", "protocol provenance requirements are incomplete"))
    if not isinstance(summary.get("rubric_prereg_sha256"), str) or len(str(summary.get("rubric_prereg_sha256"))) != 64:
        blockers.append(blocked_item("summary.rubric_prereg_sha256", "rubric_prereg_sha256_invalid", "rubric digest is required"))
    elif summary.get("rubric_prereg_sha256") != rubric_digest(summary):
        blockers.append(blocked_item("summary.rubric_prereg_sha256", "rubric_prereg_sha256_mismatch", "rubric digest must cover boundary-critical fields"))
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
    blockers.extend(protocol_blockers(summary))
    blockers.extend(provenance_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(path_blockers(summary))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_rule_has(item, ("schema", "missing", "invalid", "not_list", "not_object", "dimension")) for item in blockers) else "clean"
    summary["protocol_status"] = "blocked" if any(_rule_has(item, ("protocol", "paired", "aggregate")) for item in blockers) else "clean"
    summary["provenance_status"] = "blocked" if any(_rule_has(item, ("provenance", "sha256", "hash", "digest")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim", "overclaim")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "flag", "provider", "backend", "executable", "canary", "calls", "token", "output_dir")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "raw_reference", "raw_tmp_path", "repo_raw")) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control")) for item in blockers) else "clean"


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def choose_status(blockers: list[dict[str, Any]], current_status: str | None = None) -> str:
    if not blockers:
        return current_status if current_status in ALLOWED_STATUSES else STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any(DIRECT_PREFIX in reason or "direct_control" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("forbidden_artifact" in reason or "raw_reference" in reason or "raw_tmp_path" in reason or "repo_raw" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("claim" in reason or "overclaim" in reason for reason in reasons):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if any("runtime" in reason or "flag" in reason or "provider" in reason or "backend" in reason or "executable" in reason or "canary" in reason or "calls" in reason or "token" in reason or "output_dir" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any(
        "protocol" in reason
        or "paired" in reason
        or "aggregate" in reason
        or "visible_data_boundary" in reason
        or "horizon_readiness_gate" in reason
        or "scoring_rubric" in reason
        or "per_dimension" in reason
        for reason in reasons
    ):
        return STATUS_BLOCKED_PROTOCOL
    if any("schema" in reason or "missing" in reason or "invalid" in reason or "not_list" in reason or "not_object" in reason or "dimension" in reason for reason in reasons):
        return STATUS_BLOCKED_SCHEMA
    if any("provenance" in reason or "sha256" in reason or "hash" in reason or "digest" in reason for reason in reasons):
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


def fixture_identity_blockers(payload: dict[str, Any], *, config: RubricConfig, run_root: Path) -> list[dict[str, Any]]:
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


def restore_config_identity(summary: dict[str, Any], *, config: RubricConfig, run_root: Path) -> None:
    summary["prereg_id"] = config.prereg_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: RubricConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("rubric_status") or STATUS_BLOCKED_SCHEMA) if payload else STATUS_BLOCKED_SCHEMA,
    )
    if payload:
        summary.update(payload)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    summary["rubric_status"] = choose_status(blockers, current_status=str(summary.get("rubric_status") or ""))
    finalize_blockers(summary, blockers)
    return summary


def build_default_rubric(config: RubricConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    summary["rubric_status"] = choose_status(blockers, current_status=STATUS_READY)
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: RubricConfig) -> dict[str, Any]:
    validate_run_id(config.prereg_id)
    run_root = config.output_dir / config.prereg_id
    if not under_tmp(run_root):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_dir_not_tmp", "rubric outputs must be under /tmp")]
        summary["rubric_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
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
        summary = build_default_rubric(config, run_root=run_root)
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary["rubric_prereg_sha256"] = rubric_digest(summary)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "prereg_id": summary.get("prereg_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "rubric_prereg_sha256": summary.get("rubric_prereg_sha256"),
        "rubric_status": summary.get("rubric_status"),
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
    parser.add_argument("--prereg-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8j_cognitive_lift_rubric_prereg/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RubricConfig:
    return RubricConfig(
        prereg_id=str(args.prereg_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(config_from_args(args))
    except ValueError as exc:
        print(json.dumps({"rubric_status": STATUS_BLOCKED_SCHEMA, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("rubric_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
