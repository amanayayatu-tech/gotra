#!/usr/bin/env python3
"""GOTRA v3.8S rubric reasoning scored-record validator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import re
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_8j_cognitive_lift_rubric_prereg_schema as rubric  # noqa: E402
from scripts import baseline_v3_8r_rubric_anchored_reasoning_quality_prereg as prereg  # noqa: E402


SUMMARY_SCHEMA = "gotra.v3_8s.rubric_reasoning_scored_record_validation_summary.v1"
MANIFEST_SCHEMA = "gotra.v3_8s.rubric_reasoning_scored_record_validation_manifest.v1"
SCORED_RECORD_SCHEMA_ID = "gotra.v3_8r.rubric_anchored_reasoning_quality_scored_record.v1"
RUN_ID_PREFIX = "gotra_v3_8s_rubric_reasoning_scored_records_"
RUN_ID_RE = re.compile(rf"^{RUN_ID_PREFIX}[0-9TZ_-]+$")
SCRIPT_VERSION = "v3.8s-20260622"
EVIDENCE_LAYER = "local_checks_rubric_reasoning_scored_record_validation"
RUBRIC_VERSION = rubric.SCHEMA_VERSION
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
RAW_OUTPUT_BOUNDARY = "/tmp only"

STATUS_READY = "RUBRIC_ANCHORED_REASONING_QUALITY_EVALUATION_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_IDENTITY = "BLOCKED_IDENTITY"
STATUS_BLOCKED_BLIND_SCORING = "BLOCKED_BLIND_SCORING"
STATUS_BLOCKED_SCORER_RELIABILITY = "BLOCKED_SCORER_RELIABILITY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_COMPARATOR_BOUNDARY = "BLOCKED_COMPARATOR_BOUNDARY"
STATUS_BLOCKED_RAW_BOUNDARY = "BLOCKED_RAW_BOUNDARY"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_EFFECTIVE_N = "BLOCKED_EFFECTIVE_N"
STATUS_BLOCKED_STATISTICAL_ELIGIBILITY = "BLOCKED_STATISTICAL_ELIGIBILITY"
STATUS_RUN_ID_EXISTS = "RUBRIC_ANCHORED_REASONING_QUALITY_EVALUATION_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_IDENTITY,
    STATUS_BLOCKED_BLIND_SCORING,
    STATUS_BLOCKED_SCORER_RELIABILITY,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_BLOCKED_COMPARATOR_BOUNDARY,
    STATUS_BLOCKED_RAW_BOUNDARY,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_EFFECTIVE_N,
    STATUS_BLOCKED_STATISTICAL_ELIGIBILITY,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

ALLOWED_ARMS = ("full_gotra", "ksana_real_research", DIRECT_INTERPRETATION)
CANDIDATE_ARMS = ("full_gotra", "ksana_real_research")
CLEAN_COMPARATORS = (
    "deterministic_price_only",
    "simple_statistical_reference",
    "preregistered_non_direct_control",
)
DIMENSIONS = rubric.DIMENSIONS
DIMENSION_WEIGHTS = {dimension: 0.125 for dimension in DIMENSIONS}
MATCHED_IDENTITY_FIELDS = (
    "paired_sample_id",
    "ticker",
    "decision_date",
    "horizon",
    "probe_variant_id",
    "prompt_hash",
    "input_hash",
    "visible_data_boundary",
    "rubric_version",
)
RECORD_REQUIRED_FIELDS = {
    "schema_id",
    "paired_sample_id",
    "ticker",
    "decision_date",
    "horizon",
    "probe_variant_id",
    "arm_identity_blinded",
    "arm_identity_unblinded_hash",
    "rubric_version",
    "prompt_hash",
    "input_hash",
    "visible_data_boundary",
    "source_run_id",
    "source_summary_sha256",
    "source_artifact_sha256",
    "source_stage_metadata_sha256",
    "scorer_id",
    "scorer_seed",
    "scoring_blind",
    "scoring_timestamp_utc",
    "dimension_scores",
    "dimension_rationales_hashes",
    "composite_score",
    "score_schema_valid",
    "raw_output_tmp_path",
    "raw_output_sha256",
}
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "schema_id",
    "script_version",
    "validation_id",
    "created_at_utc",
    "evidence_layer",
    "scored_record_schema_id",
    "rubric_version",
    "rubric_sha256",
    "rubric_lock_status",
    "score_range",
    "dimension_weights",
    "scorer_reliability",
    "paired_identity_policy",
    "clean_comparator_policy",
    "actual_30d_readiness_status",
    "cognitive_lift_superiority_verdict_status",
    "rubric_anchored_reasoning_quality_verdict_status",
    DIRECT_INTERPRETATION_KEY,
    DIRECT_CLEAN_BASELINE_KEY,
    "raw_output_boundary",
    "no_raw_repo",
    "provider_or_backend_called",
    "provider_or_backend_called_for_evaluation",
    "provider_canary_executed",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "real_calls_count",
    "token_usage_total",
    "scored_records",
    "work_unit_counts",
    "effective_n_policy",
    "statistical_eligibility",
    "effect_fields_allowed_before_eligibility",
    "effect_summary",
    "can_say",
    "cannot_say",
    "non_claims",
}
RUNTIME_FALSE_FLAGS = (
    "provider_or_backend_called",
    "provider_or_backend_called_for_evaluation",
    "provider_canary_executed",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "actual_30d_verdict_executed",
)
ELIGIBILITY_FLAGS = (
    "sample_size_ready",
    "effective_n_ready",
    "paired_clean_count_ready",
    "scorer_reliability_ready",
    "bootstrap_hac_eligible",
    "claim_boundary_clean",
    "direct_llm_boundary_clean",
    "comparator_boundary_clean",
    "raw_artifact_boundary_clean",
)
FORBIDDEN_EFFECT_KEYS = {
    "p_value",
    "effect_estimate",
    "confidence_interval",
    "bootstrap_interval",
    "hac_adjusted_standard_error",
    "winner",
    "proved",
    "established",
    "outperformed",
}
ARM_HASHES = {arm: prereg.stable_sha256_json({"arm_identity": arm}) for arm in ALLOWED_ARMS}
CLEAN_COMPARATOR_HASHES = {
    comparator: prereg.stable_sha256_json({"clean_comparator": comparator}) for comparator in CLEAN_COMPARATORS
}
DIRECT_HASH = ARM_HASHES[DIRECT_INTERPRETATION]
RAW_ARM_NAME_RE = re.compile("|".join(re.escape(arm) for arm in ALLOWED_ARMS), re.IGNORECASE)
SCORER_FACING_KEY_RE = re.compile(r"(?:scorer|facing|rationale)", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RAW_CONTENT_RE = re.compile(r"\b(?:full transcript|raw transcript|raw output|provider transcript)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ScoredRecordConfig:
    validation_id: str
    output_dir: Path
    allow_overwrite: bool = False
    summary_fixture: Path | None = None


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> list[dict[str, Any]]:
    if RUN_ID_RE.fullmatch(run_id) is None:
        return [prereg.blocked_item("summary.validation_id", "validation_id_invalid", "validation_id has invalid shape")]
    return []


def arm_hash(arm: str) -> str:
    return ARM_HASHES[arm]


def clean_comparator_hash(comparator: str) -> str:
    return CLEAN_COMPARATOR_HASHES[comparator]


def synthetic_hash(label: str) -> str:
    return prereg.stable_sha256_json({"v3_8s_fixture": label})


def scorer_reliability_policy() -> dict[str, Any]:
    return {
        "minimum_scorers_per_record": 2,
        "adjudication_required_if_score_delta_gt": 1.0,
        "reliability_metric": ["intraclass_correlation", "kendall_tau_rank_stability"],
        "reliability_minimum": "PREREGISTERED",
        "blocked_status_if_failed": STATUS_BLOCKED_SCORER_RELIABILITY,
    }


def clean_comparator_policy() -> dict[str, Any]:
    return {
        "direct_llm_diagnostic_only": True,
        "required_non_direct_comparator": True,
        "direct_llm_hash": DIRECT_HASH,
        "clean_comparator_hashes": [clean_comparator_hash("deterministic_price_only")],
    }


def paired_identity_policy() -> dict[str, Any]:
    return {
        "matched_identity_fields": list(MATCHED_IDENTITY_FIELDS),
        "candidate_arm_hashes": [arm_hash(arm) for arm in CANDIDATE_ARMS],
        "diagnostic_arm_hash": DIRECT_HASH,
        "direct_llm_role": "diagnostic_only_not_claim_comparator",
        "raw_arm_names_available_to_scorer": False,
    }


def effective_n_policy() -> dict[str, Any]:
    return {
        "raw_unit_count_field": "clean_paired_unit_count",
        "effective_n_field": "effective_independent_pair_count",
        "clustering_dimensions": ["ticker", "decision_date", "probe_family"],
        "minimum_effective_n": "PREREGISTERED",
        "effective_n_estimator": [
            "cluster_bootstrap",
            "block_bootstrap_by_decision_date",
            "sensitivity_analysis_by_ticker_cluster",
        ],
        "raw_count_used_as_independent_n": False,
        "blocked_status_if_failed": STATUS_BLOCKED_EFFECTIVE_N,
    }


def statistical_eligibility() -> dict[str, bool]:
    return {key: False for key in ELIGIBILITY_FLAGS}


def default_scored_records() -> list[dict[str, Any]]:
    base = {
        "schema_id": SCORED_RECORD_SCHEMA_ID,
        "paired_sample_id": "pair-0001",
        "ticker": "AAPL",
        "decision_date": "2026-02-10",
        "horizon": "30d",
        "probe_variant_id": "baseline",
        "rubric_version": RUBRIC_VERSION,
        "prompt_hash": synthetic_hash("prompt"),
        "input_hash": synthetic_hash("input"),
        "visible_data_boundary": "2026-02-10",
        "source_run_id": "v3_8s_fixture_source",
        "source_summary_sha256": synthetic_hash("source_summary"),
        "source_artifact_sha256": synthetic_hash("source_artifact"),
        "source_stage_metadata_sha256": synthetic_hash("source_stage_metadata"),
        "scoring_blind": True,
        "scoring_timestamp_utc": "2026-06-22T00:00:00Z",
        "dimension_scores": {dimension: 3.5 for dimension in DIMENSIONS},
        "dimension_rationales_hashes": {dimension: synthetic_hash(f"rationale:{dimension}") for dimension in DIMENSIONS},
        "composite_score": 3.5,
        "score_schema_valid": True,
        "raw_output_tmp_path": None,
        "raw_output_sha256": None,
        "scorer_facing_metadata": {
            "arm_identity_blinded": None,
            "rubric_version": RUBRIC_VERSION,
            "no_raw_arm_identity_visible": True,
        },
    }
    records: list[dict[str, Any]] = []
    blinded_ids = {
        "full_gotra": "arm_alpha",
        "ksana_real_research": "arm_beta",
        DIRECT_INTERPRETATION: "arm_gamma",
    }
    for arm in ALLOWED_ARMS:
        for scorer_id in ("scorer_alpha", "scorer_beta"):
            record = dict(base)
            record["dimension_scores"] = dict(base["dimension_scores"])
            record["dimension_rationales_hashes"] = dict(base["dimension_rationales_hashes"])
            record["scorer_facing_metadata"] = dict(base["scorer_facing_metadata"])
            record["arm_identity_blinded"] = blinded_ids[arm]
            record["arm_identity_unblinded_hash"] = arm_hash(arm)
            record["scorer_id"] = scorer_id
            record["scorer_seed"] = synthetic_hash(f"{arm}:{scorer_id}")[:16]
            record["scorer_facing_metadata"]["arm_identity_blinded"] = blinded_ids[arm]
            records.append(record)
    return records


def base_summary(config: ScoredRecordConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    records = default_scored_records()
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "schema_id": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "validation_id": config.validation_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "created_at_utc": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "scored_record_schema_id": SCORED_RECORD_SCHEMA_ID,
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": prereg.rubric_lock_digest(),
        "rubric_lock_status": "LOCKED_AT_T0",
        "score_range": {"min": 0, "max": 5, "step": 0.5},
        "dimension_weights": dict(DIMENSION_WEIGHTS),
        "scorer_reliability": scorer_reliability_policy(),
        "paired_identity_policy": paired_identity_policy(),
        "clean_comparator_policy": clean_comparator_policy(),
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "rubric_anchored_reasoning_quality_verdict_status": status,
        "evaluation_status": status,
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "no_raw_repo": True,
        "repo_raw_artifacts": [],
        "raw_paths": [],
        "provider_or_backend_called": False,
        "provider_or_backend_called_for_evaluation": False,
        "provider_canary_executed": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_verdict_executed": False,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "usage_metadata_available": False,
        "scored_records": records,
        "work_unit_counts": {
            "total_scored_records": len(records),
            "scored_record_group_count": 3,
            "clean_paired_unit_count": 0,
            "effective_independent_pair_count": 0,
            "effective_independent_pair_count_source": "not_computed_before_eligibility",
            "raw_count_used_as_independent_n": False,
        },
        "effective_n_policy": effective_n_policy(),
        "statistical_eligibility": statistical_eligibility(),
        "effect_fields_allowed_before_eligibility": False,
        "forbidden_before_eligibility": sorted(FORBIDDEN_EFFECT_KEYS),
        "effect_summary": {"emitted": False, "values": None},
        "can_say": ["v3.8S scored-record schema and paired-identity local checks are ready"],
        "cannot_say": [
            "not_actual_30d_verdict",
            "not_forward_live_outcome_superiority",
            "not_realized_pnl_verdict",
            "not_public_science_proof",
            "not_trading_or_investment_advice",
            "not_superiority_over_direct_llm_as_clean_baseline",
        ],
        "non_claims": [
            "not_market_edge_verdict",
            "not_realized_pnl_verdict",
            "not_actual_30d_verdict",
            "not_forward_live_outcome_superiority",
            "not_public_science_proof",
            "not_trading_or_investment_advice",
            "direct_llm_is_parametric_memory_control_only",
        ],
        "schema_status": "clean",
        "paired_identity_status": "clean",
        "blind_scoring_status": "clean",
        "scorer_reliability_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "raw_boundary_status": "clean",
        "claim_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "comparator_boundary_status": "clean",
        "effective_n_status": "blocked_expected_before_eligibility",
        "statistical_eligibility_status": "blocked_expected_before_eligibility",
        "blocker_reasons": [],
        "blocked_items": [],
    }
    summary["validation_sha256"] = validation_digest(summary)
    return summary


def validation_digest(summary: dict[str, Any]) -> str:
    return prereg.stable_sha256_json(
        {
            "schema": summary.get("schema"),
            "scored_record_schema_id": summary.get("scored_record_schema_id"),
            "rubric_version": summary.get("rubric_version"),
            "rubric_sha256": summary.get("rubric_sha256"),
            "score_range": summary.get("score_range"),
            "dimension_weights": summary.get("dimension_weights"),
            "scorer_reliability": summary.get("scorer_reliability"),
            "paired_identity_policy": summary.get("paired_identity_policy"),
            "clean_comparator_policy": summary.get("clean_comparator_policy"),
            "record_count": len(summary.get("scored_records") or []),
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "raw_output_boundary": summary.get("raw_output_boundary"),
            "no_raw_repo": summary.get("no_raw_repo"),
        }
    )


def is_iso_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def is_iso_or_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if DATE_RE.fullmatch(value):
        return True
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def is_score_step(value: Any) -> bool:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return False
    if value < 0 or value > 5:
        return False
    return math.isclose(float(value) * 2, round(float(value) * 2), abs_tol=1e-9)


def composite_score(scores: dict[str, Any]) -> float:
    return sum(float(scores[dimension]) * DIMENSION_WEIGHTS[dimension] for dimension in DIMENSIONS)


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = validate_run_id(str(summary.get("validation_id") or ""))
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(prereg.blocked_item("summary.schema", "summary_schema_mismatch", "schema must match v3.8S"))
    if summary.get("schema_id") != SUMMARY_SCHEMA:
        blockers.append(prereg.blocked_item("summary.schema_id", "summary_schema_id_mismatch", "schema_id must match v3.8S"))
    if summary.get("scored_record_schema_id") != SCORED_RECORD_SCHEMA_ID:
        blockers.append(prereg.blocked_item("summary.scored_record_schema_id", "scored_record_schema_id_mismatch", "scored record schema must match plan section 5.1"))
    if summary.get("script_version") != SCRIPT_VERSION:
        blockers.append(prereg.blocked_item("summary.script_version", "script_version_mismatch", "script version mismatch"))
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(prereg.blocked_item("summary.evidence_layer", "evidence_layer_mismatch", "v3.8S is local checks only"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(prereg.blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    status = str(summary.get("rubric_anchored_reasoning_quality_verdict_status") or "")
    if status not in ALLOWED_STATUSES:
        blockers.append(prereg.blocked_item("summary.rubric_anchored_reasoning_quality_verdict_status", "invalid_status", "status is not allowed"))
    if not is_iso_utc(summary.get("created_at_utc")):
        blockers.append(prereg.blocked_item("summary.created_at_utc", "created_at_utc_invalid", "created_at_utc must end in Z"))
    if summary.get("rubric_version") != RUBRIC_VERSION:
        blockers.append(prereg.blocked_item("summary.rubric_version", "rubric_version_mismatch", "rubric version must match v3.8J"))
    if not prereg.is_hex(summary.get("rubric_sha256"), 64):
        blockers.append(prereg.blocked_item("summary.rubric_sha256", "rubric_sha256_missing_or_invalid", "rubric hash must be 64 hex"))
    if summary.get("rubric_lock_status") != "LOCKED_AT_T0":
        blockers.append(prereg.blocked_item("summary.rubric_lock_status", "rubric_lock_status_invalid", "rubric must remain locked"))
    if summary.get("score_range") != {"min": 0, "max": 5, "step": 0.5}:
        blockers.append(prereg.blocked_item("summary.score_range", "score_range_invalid", "score range must be 0..5 step 0.5"))
    if summary.get("dimension_weights") != DIMENSION_WEIGHTS:
        blockers.append(prereg.blocked_item("summary.dimension_weights", "dimension_weights_mismatch", "dimension weights must remain equal and locked"))
    if summary.get("effect_fields_allowed_before_eligibility") is not False:
        blockers.append(prereg.blocked_item("summary.effect_fields_allowed_before_eligibility", "effect_fields_allowed_before_eligibility_not_false", "effect fields are blocked before eligibility"))
    for key in ("can_say", "cannot_say", "non_claims"):
        value = summary.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            blockers.append(prereg.blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))
    records = summary.get("scored_records")
    if not isinstance(records, list) or not records:
        blockers.append(prereg.blocked_item("summary.scored_records", "scored_records_missing_or_empty", "scored records are required"))
    elif not all(isinstance(record, dict) for record in records):
        blockers.append(prereg.blocked_item("summary.scored_records", "scored_records_not_objects", "each scored record must be an object"))
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in RUNTIME_FALSE_FLAGS:
        if flag not in summary:
            blockers.append(prereg.blocked_item(f"summary.{flag}", f"{flag}_missing", f"{flag} must be present and false"))
        elif summary.get(flag) is not False:
            blockers.append(prereg.blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must remain false"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(prereg.blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("cognitive_lift_superiority_verdict_status") != SUPERIORITY_STATUS:
        blockers.append(prereg.blocked_item("summary.cognitive_lift_superiority_verdict_status", "cognitive_lift_superiority_status_invalid", "cognitive-lift superiority status must remain not ready"))
    if summary.get("raw_output_boundary") != RAW_OUTPUT_BOUNDARY:
        blockers.append(prereg.blocked_item("summary.raw_output_boundary", "raw_output_boundary_invalid", "raw output boundary must be /tmp only"))
    if summary.get("no_raw_repo") is not True:
        blockers.append(prereg.blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "repo-facing fields must not include raw payloads"))
    for key in ("real_calls_count", "token_usage_total"):
        if not prereg.is_numeric_zero(summary.get(key)):
            blockers.append(prereg.blocked_item(f"summary.{key}", f"{key}_not_numeric_zero", f"{key} must be integer zero"))
    return blockers


def record_schema_blockers(record: dict[str, Any], index: int) -> list[dict[str, Any]]:
    path = f"summary.scored_records[{index}]"
    blockers: list[dict[str, Any]] = []
    missing = sorted(RECORD_REQUIRED_FIELDS - set(record))
    blockers.extend(prereg.blocked_item(f"{path}.{key}", "scored_record_missing_field", f"{key} is required") for key in missing)
    if record.get("schema_id") != SCORED_RECORD_SCHEMA_ID:
        blockers.append(prereg.blocked_item(f"{path}.schema_id", "scored_record_schema_id_mismatch", "record schema_id mismatch"))
    for key in (
        "paired_sample_id",
        "ticker",
        "horizon",
        "probe_variant_id",
        "arm_identity_blinded",
        "source_run_id",
        "scorer_id",
        "scorer_seed",
    ):
        if not isinstance(record.get(key), str) or not str(record.get(key)).strip():
            blockers.append(prereg.blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be a non-empty string"))
    if not isinstance(record.get("decision_date"), str) or DATE_RE.fullmatch(str(record.get("decision_date"))) is None:
        blockers.append(prereg.blocked_item(f"{path}.decision_date", "decision_date_invalid", "decision_date must be YYYY-MM-DD"))
    if not is_iso_or_date(record.get("visible_data_boundary")):
        blockers.append(prereg.blocked_item(f"{path}.visible_data_boundary", "visible_data_boundary_invalid", "visible data boundary must be a date or ISO timestamp"))
    if record.get("rubric_version") != RUBRIC_VERSION:
        blockers.append(prereg.blocked_item(f"{path}.rubric_version", "record_rubric_version_mismatch", "record rubric version mismatch"))
    for key in (
        "arm_identity_unblinded_hash",
        "prompt_hash",
        "input_hash",
        "source_summary_sha256",
        "source_artifact_sha256",
        "source_stage_metadata_sha256",
    ):
        if not prereg.is_hex(record.get(key), 64):
            blockers.append(prereg.blocked_item(f"{path}.{key}", f"{key}_invalid_64_hex", f"{key} must be 64 lowercase hex"))
    if record.get("score_schema_valid") is not True:
        blockers.append(prereg.blocked_item(f"{path}.score_schema_valid", "score_schema_valid_not_true", "score schema valid flag must be true"))
    if not is_iso_utc(record.get("scoring_timestamp_utc")):
        blockers.append(prereg.blocked_item(f"{path}.scoring_timestamp_utc", "scoring_timestamp_utc_invalid", "scoring timestamp must be ISO UTC ending Z"))
    blockers.extend(dimension_score_blockers(record, path=path))
    blockers.extend(record_raw_blockers(record, path=path))
    return blockers


def dimension_score_blockers(record: dict[str, Any], *, path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    scores = record.get("dimension_scores")
    rationales = record.get("dimension_rationales_hashes")
    if not isinstance(scores, dict):
        return [prereg.blocked_item(f"{path}.dimension_scores", "dimension_scores_not_object", "dimension scores must be an object")]
    if set(scores) != set(DIMENSIONS):
        blockers.append(prereg.blocked_item(f"{path}.dimension_scores", "dimension_scores_dimension_mismatch", "dimension scores must cover locked dimensions exactly"))
    for dimension, score in scores.items():
        if not is_score_step(score):
            blockers.append(prereg.blocked_item(f"{path}.dimension_scores.{dimension}", "dimension_score_invalid_range_or_step", "dimension scores must be 0..5 in 0.5 steps"))
    if not isinstance(rationales, dict):
        blockers.append(prereg.blocked_item(f"{path}.dimension_rationales_hashes", "dimension_rationales_hashes_not_object", "rationale hashes must be an object"))
    else:
        if set(rationales) != set(DIMENSIONS):
            blockers.append(prereg.blocked_item(f"{path}.dimension_rationales_hashes", "dimension_rationales_dimension_mismatch", "rationale hashes must cover locked dimensions exactly"))
        for dimension, digest in rationales.items():
            if not prereg.is_hex(digest, 64):
                blockers.append(prereg.blocked_item(f"{path}.dimension_rationales_hashes.{dimension}", "dimension_rationale_hash_invalid_64_hex", "rationale hash must be 64 lowercase hex"))
    if set(scores) == set(DIMENSIONS):
        observed = record.get("composite_score")
        if not isinstance(observed, int | float) or isinstance(observed, bool):
            blockers.append(prereg.blocked_item(f"{path}.composite_score", "composite_score_not_numeric", "composite score must be numeric"))
        else:
            expected = composite_score(scores)
            if not math.isclose(float(observed), expected, abs_tol=1e-9):
                blockers.append(prereg.blocked_item(f"{path}.composite_score", "composite_score_mismatch", "composite score must equal locked equal-weight average"))
    return blockers


def record_raw_blockers(record: dict[str, Any], *, path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    raw_path = record.get("raw_output_tmp_path")
    raw_sha = record.get("raw_output_sha256")
    if raw_path is None:
        if raw_sha is not None:
            blockers.append(prereg.blocked_item(f"{path}.raw_output_sha256", "raw_output_sha256_without_path", "raw sha must be null when raw path is null"))
    elif not isinstance(raw_path, str) or not prereg.under_tmp(raw_path):
        blockers.append(prereg.blocked_item(f"{path}.raw_output_tmp_path", "raw_reference_not_tmp", "raw output path must be under /tmp"))
    elif not prereg.is_hex(raw_sha, 64):
        blockers.append(prereg.blocked_item(f"{path}.raw_output_sha256", "raw_output_sha256_invalid_64_hex", "raw sha must be 64 lowercase hex"))
    return blockers


def blind_scoring_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for index, record in enumerate(summary.get("scored_records") or []):
        if not isinstance(record, dict):
            continue
        path = f"summary.scored_records[{index}]"
        if record.get("scoring_blind") is not True:
            blockers.append(prereg.blocked_item(f"{path}.scoring_blind", "scoring_blind_not_true", "scoring_blind must be true"))
        blinded = record.get("arm_identity_blinded")
        if isinstance(blinded, str) and RAW_ARM_NAME_RE.search(blinded):
            blockers.append(prereg.blocked_item(f"{path}.arm_identity_blinded", "arm_identity_blinded_leaks_raw_arm", "blinded arm id cannot include raw arm identity"))
        for item_path, key, value in prereg.recursive_key_values(record, path=path):
            if key == "arm_identity_unblinded_hash":
                continue
            if _raw_arm_leak_in_scorer_facing(key, value):
                blockers.append(prereg.blocked_item(item_path, "scorer_facing_raw_arm_identity_leak", "scorer-facing fields cannot expose raw arm identity"))
    return blockers


def _raw_arm_leak_in_scorer_facing(key: str, value: Any) -> bool:
    if not SCORER_FACING_KEY_RE.search(key):
        return False
    for _, text in prereg.recursive_strings(value, path="value"):
        if RAW_ARM_NAME_RE.search(text):
            return True
    return False


def paired_identity_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    policy = summary.get("paired_identity_policy")
    if not isinstance(policy, dict):
        blockers.append(prereg.blocked_item("summary.paired_identity_policy", "paired_identity_policy_not_object", "paired identity policy must be an object"))
    else:
        if policy.get("matched_identity_fields") != list(MATCHED_IDENTITY_FIELDS):
            blockers.append(prereg.blocked_item("summary.paired_identity_policy.matched_identity_fields", "matched_identity_fields_mismatch", "matched identity fields are not locked"))
        if policy.get("candidate_arm_hashes") != [arm_hash(arm) for arm in CANDIDATE_ARMS]:
            blockers.append(prereg.blocked_item("summary.paired_identity_policy.candidate_arm_hashes", "candidate_arm_hashes_mismatch", "candidate arm hashes must match locked arms"))
        if policy.get("diagnostic_arm_hash") != DIRECT_HASH:
            blockers.append(prereg.blocked_item("summary.paired_identity_policy.diagnostic_arm_hash", "diagnostic_arm_hash_mismatch", "direct diagnostic hash mismatch"))
        if policy.get("direct_llm_role") != "diagnostic_only_not_claim_comparator":
            blockers.append(prereg.blocked_item("summary.paired_identity_policy.direct_llm_role", "direct_control_role_mismatch", "direct control must remain diagnostic only"))
    records = [record for record in summary.get("scored_records") or [] if isinstance(record, dict)]
    for index, record in enumerate(records):
        if prereg.is_hex(record.get("arm_identity_unblinded_hash"), 64) and record.get("arm_identity_unblinded_hash") not in set(ARM_HASHES.values()):
            blockers.append(prereg.blocked_item(f"summary.scored_records[{index}].arm_identity_unblinded_hash", "arm_identity_unblinded_hash_unknown", "arm hash must match a preregistered arm"))
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        paired_id = record.get("paired_sample_id")
        if isinstance(paired_id, str):
            by_pair.setdefault(paired_id, []).append(record)
    for paired_id, pair_records in by_pair.items():
        by_arm: dict[str, list[dict[str, Any]]] = {}
        for record in pair_records:
            arm_digest = record.get("arm_identity_unblinded_hash")
            if isinstance(arm_digest, str):
                by_arm.setdefault(arm_digest, []).append(record)
        for required_hash in (arm_hash("full_gotra"), arm_hash("ksana_real_research")):
            if required_hash not in by_arm:
                blockers.append(prereg.blocked_item(f"summary.scored_records.{paired_id}", "paired_required_candidate_arm_missing", "paired sample must include both candidate arms"))
        identity_by_arm: dict[str, tuple[Any, ...]] = {}
        for arm_digest, arm_records in by_arm.items():
            tuples = {_identity_tuple(record) for record in arm_records}
            if len(tuples) > 1:
                blockers.append(prereg.blocked_item(f"summary.scored_records.{paired_id}.{arm_digest}", "paired_identity_inconsistent_within_arm", "scorer records for same arm must share identity fields"))
            if tuples:
                identity_by_arm[arm_digest] = next(iter(tuples))
        candidate_tuples = [identity_by_arm.get(arm_hash(arm)) for arm in CANDIDATE_ARMS]
        if all(candidate_tuples) and len(set(candidate_tuples)) > 1:
            blockers.append(prereg.blocked_item(f"summary.scored_records.{paired_id}", "paired_identity_mismatch_across_candidate_arms", "candidate arms must share matched identity fields"))
        reference = next((value for value in candidate_tuples if value is not None), None)
        if reference is not None and DIRECT_HASH in identity_by_arm and identity_by_arm[DIRECT_HASH] != reference:
            blockers.append(prereg.blocked_item(f"summary.scored_records.{paired_id}.{DIRECT_HASH}", "paired_identity_mismatch_diagnostic_arm", "diagnostic arm must share matched identity fields when present"))
    return blockers


def _identity_tuple(record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in MATCHED_IDENTITY_FIELDS)


def scorer_reliability_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    policy = summary.get("scorer_reliability")
    if not isinstance(policy, dict):
        blockers.append(prereg.blocked_item("summary.scorer_reliability", "scorer_reliability_not_object", "scorer reliability policy is required"))
        return blockers
    minimum = policy.get("minimum_scorers_per_record")
    if minimum != 2:
        blockers.append(prereg.blocked_item("summary.scorer_reliability.minimum_scorers_per_record", "minimum_scorers_per_record_not_two", "minimum scorers per record must be 2"))
    groups: dict[tuple[Any, ...], set[str]] = {}
    for record in summary.get("scored_records") or []:
        if not isinstance(record, dict):
            continue
        group_key = _scored_unit_key(record)
        scorer = record.get("scorer_id")
        if isinstance(scorer, str):
            groups.setdefault(group_key, set()).add(scorer)
    for group_key, scorers in groups.items():
        if len(scorers) < 2:
            blockers.append(prereg.blocked_item(f"summary.scored_records.{group_key[0]}", "scorer_count_below_minimum", "at least two scorers per scored record are required"))
    return blockers


def _scored_unit_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("paired_sample_id"),
        record.get("ticker"),
        record.get("decision_date"),
        record.get("horizon"),
        record.get("probe_variant_id"),
        record.get("prompt_hash"),
        record.get("input_hash"),
        record.get("visible_data_boundary"),
        record.get("rubric_version"),
        record.get("arm_identity_blinded"),
        record.get("arm_identity_unblinded_hash"),
        record.get("source_run_id"),
        record.get("source_summary_sha256"),
        record.get("source_artifact_sha256"),
        record.get("source_stage_metadata_sha256"),
    )


def direct_boundary_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(prereg.blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_PREFIX + "_interpretation_mismatch", "direct_llm interpretation must remain parametric-memory control"))
    if summary.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(prereg.blocked_item(f"summary.{DIRECT_CLEAN_BASELINE_KEY}", DIRECT_PREFIX + "_clean_baseline_not_false", "direct_llm cannot be a clean baseline"))
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path):
            continue
        for match in prereg.DIRECT_UNSAFE_RE.finditer(text):
            role_start = _direct_role_start(match)
            if not prereg.claim_scan.is_negated(text, match.start() + role_start):
                blockers.append(prereg.blocked_item(path, DIRECT_PREFIX + "_unsafe_role_wording", "direct_llm cannot be clean/no-future/no-memory or primary comparator"))
    return blockers


def _direct_role_start(match: re.Match[str]) -> int:
    role_match = re.search(r"clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline", match.group(0), re.IGNORECASE)
    return role_match.start() if role_match else 0


def comparator_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    policy = summary.get("clean_comparator_policy")
    if not isinstance(policy, dict):
        return [prereg.blocked_item("summary.clean_comparator_policy", "clean_comparator_policy_not_object", "clean comparator policy must be object")]
    if policy.get("direct_llm_diagnostic_only") is not True:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.direct_llm_diagnostic_only", "direct_diagnostic_only_not_true", "direct control must be diagnostic only"))
    if policy.get("required_non_direct_comparator") is not True:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.required_non_direct_comparator", "required_non_direct_comparator_not_true", "non-direct comparator is required"))
    clean_hashes = policy.get("clean_comparator_hashes")
    if not isinstance(clean_hashes, list) or not clean_hashes:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.clean_comparator_hashes", "non_direct_clean_comparator_missing", "a non-direct comparator hash is required"))
    else:
        hash_set = {str(item) for item in clean_hashes}
        allowed_clean = set(CLEAN_COMPARATOR_HASHES.values())
        if hash_set == {DIRECT_HASH}:
            blockers.append(prereg.blocked_item("summary.clean_comparator_policy.clean_comparator_hashes", "only_clean_comparator_is_parametric_control", "direct_llm cannot be the only clean comparator"))
        elif not hash_set.intersection(allowed_clean):
            blockers.append(prereg.blocked_item("summary.clean_comparator_policy.clean_comparator_hashes", "non_direct_clean_comparator_missing", "clean comparator set must include a preregistered non-direct comparator"))
    return blockers


def path_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for key_hint, candidate in prereg.recursive_paths(summary):
        if candidate == "/tmp" or candidate.startswith("/tmp/"):
            continue
        if prereg.claim_scan.forbidden_path(candidate):
            blockers.append(prereg.blocked_item(candidate, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
        elif key_hint.startswith("raw") or "transcript" in key_hint:
            if not prereg.under_tmp(candidate):
                blockers.append(prereg.blocked_item(candidate, "raw_reference_not_tmp", "raw-like or transcript paths must stay under /tmp"))
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path):
            continue
        for match in RAW_CONTENT_RE.finditer(text):
            if not prereg.claim_scan.is_negated(text, match.start()):
                blockers.append(prereg.blocked_item(path, "repo_raw_or_full_transcript_reference", "repo-facing fields cannot contain raw output or full transcript text"))
    return blockers


def effective_n_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    policy = summary.get("effective_n_policy")
    if isinstance(policy, dict):
        if policy.get("raw_count_used_as_independent_n") is not False:
            blockers.append(prereg.blocked_item("summary.effective_n_policy.raw_count_used_as_independent_n", "raw_count_used_as_independent_n", "raw count cannot be independent N"))
        if policy.get("effective_n_field") != "effective_independent_pair_count":
            blockers.append(prereg.blocked_item("summary.effective_n_policy.effective_n_field", "effective_n_field_invalid", "effective-N field must be explicit"))
    else:
        blockers.append(prereg.blocked_item("summary.effective_n_policy", "effective_n_policy_not_object", "effective-N policy must be object"))
    counts = summary.get("work_unit_counts")
    if isinstance(counts, dict):
        if counts.get("raw_count_used_as_independent_n") is not False:
            blockers.append(prereg.blocked_item("summary.work_unit_counts.raw_count_used_as_independent_n", "raw_count_used_as_independent_n", "raw count cannot be independent N"))
        if counts.get("effective_independent_pair_count_source") == "raw_count":
            blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count_source", "effective_n_source_is_raw_count", "effective-N source cannot be raw count"))
    else:
        blockers.append(prereg.blocked_item("summary.work_unit_counts", "work_unit_counts_not_object", "work unit counts must be object"))
    return blockers


def eligibility_all_true(summary: dict[str, Any]) -> bool:
    flags = summary.get("statistical_eligibility")
    return isinstance(flags, dict) and all(flags.get(key) is True for key in ELIGIBILITY_FLAGS)


def effect_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    eligible = eligibility_all_true(summary)
    effect_summary = summary.get("effect_summary")
    if not isinstance(effect_summary, dict):
        blockers.append(prereg.blocked_item("summary.effect_summary", "effect_summary_not_object", "effect summary must be object"))
        return blockers
    if not eligible and (effect_summary.get("emitted") is True or effect_summary.get("values") is not None):
        blockers.append(prereg.blocked_item("summary.effect_summary", "effect_summary_emitted_before_eligibility", "effect fields are forbidden before eligibility"))
    if not eligible:
        for path, key, value in prereg.recursive_key_values(summary, path="summary"):
            if key in FORBIDDEN_EFFECT_KEYS and value is not None and "forbidden_before_eligibility" not in path:
                blockers.append(prereg.blocked_item(path, f"{key}_before_eligibility", f"{key} is forbidden before eligibility"))
    return blockers


def claim_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path):
            continue
        for match in prereg.CLAIM_BOUNDARY_RE.finditer(text):
            if not prereg.claim_scan.is_negated(text, match.start()):
                blockers.append(prereg.blocked_item(path, "claim_boundary_forbidden_wording", "claim text exceeds v3.8S local readiness boundary"))
    return blockers


def _metadata_list_path(path: str) -> bool:
    return any(
        marker in path
        for marker in (
            ".cannot_say",
            ".non_claims",
            ".forbidden_before_eligibility",
            ".blocked_items",
            ".blocker_reasons",
            ".run_root",
            ".summary_path",
            ".manifest_path",
            ".raw_paths",
            ".repo_raw_artifacts",
        )
    )


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(schema_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    records = summary.get("scored_records")
    if isinstance(records, list):
        for index, record in enumerate(records):
            if isinstance(record, dict):
                blockers.extend(record_schema_blockers(record, index))
    blockers.extend(blind_scoring_blockers(summary))
    blockers.extend(paired_identity_blockers(summary))
    blockers.extend(scorer_reliability_blockers(summary))
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(comparator_blockers(summary))
    blockers.extend(path_blockers(summary))
    blockers.extend(effective_n_blockers(summary))
    blockers.extend(effect_blockers(summary))
    if prereg.contains_secret(summary):
        blockers.append(prereg.blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_is_schema_rule(item) for item in blockers) else "clean"
    summary["paired_identity_status"] = "blocked" if any(_rule_has(item, ("paired", "identity", "arm_hash")) for item in blockers) else "clean"
    summary["blind_scoring_status"] = "blocked" if any(_rule_has(item, ("blind", "scorer_facing", "leaks_raw_arm")) for item in blockers) else "clean"
    summary["scorer_reliability_status"] = "blocked" if any(_rule_has(item, ("scorer_count", "scorer_reliability", "minimum_scorers")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "provider", "codex", "formal", "actual_30d", "superiority", "calls", "token")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "repo_raw", "transcript", "secret")) for item in blockers) else "clean"
    summary["raw_boundary_status"] = "blocked" if any(_rule_has(item, ("raw_reference", "raw_output_boundary")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim_boundary",)) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control", "direct_diagnostic")) for item in blockers) else "clean"
    summary["comparator_boundary_status"] = "blocked" if any(_rule_has(item, ("comparator", "non_direct_clean", "parametric_control")) for item in blockers) else "clean"
    summary["effective_n_status"] = "blocked" if any(_rule_has(item, ("effective_n", "raw_count")) for item in blockers) else "blocked_expected_before_eligibility"
    summary["statistical_eligibility_status"] = "blocked" if any(_rule_has(item, ("eligibility", "p_value", "effect_", "confidence", "bootstrap", "hac")) for item in blockers) else "blocked_expected_before_eligibility"


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def _is_schema_rule(item: dict[str, Any]) -> bool:
    rule = str(item.get("rule_id") or "")
    schema_tokens = (
        "summary_schema",
        "schema_id",
        "script_version",
        "evidence_layer",
        "validation_id_invalid",
        "created_at_utc_invalid",
        "scored_records_missing_or_empty",
        "scored_records_not_objects",
        "scored_record_missing_field",
        "rubric_sha256_missing_or_invalid",
        "rubric_lock_status_invalid",
        "rubric_version_mismatch",
        "record_rubric_version_mismatch",
        "score_range_invalid",
        "dimension_weights_mismatch",
        "score_schema_valid_not_true",
        "decision_date_invalid",
        "visible_data_boundary_invalid",
        "scoring_timestamp_utc_invalid",
        "invalid_64_hex",
        "dimension_scores",
        "dimension_rationales",
        "dimension_score_invalid_range_or_step",
        "composite_score",
        "raw_output_sha256_without_path",
        "raw_output_sha256_invalid_64_hex",
    )
    return any(token in rule for token in schema_tokens)


def choose_status(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any(_is_schema_rule(item) for item in blockers):
        return STATUS_BLOCKED_SCHEMA
    if any("actual_30d" in reason or "superiority" in reason or "provider" in reason or "codex" in reason or "formal" in reason or "calls" in reason or "token" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any(DIRECT_PREFIX in reason or "direct_control" in reason or "direct_diagnostic" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("comparator" in reason or "parametric_control" in reason or "non_direct_clean" in reason for reason in reasons):
        return STATUS_BLOCKED_COMPARATOR_BOUNDARY
    if any("blind" in reason or "scorer_facing" in reason or "leaks_raw_arm" in reason for reason in reasons):
        return STATUS_BLOCKED_BLIND_SCORING
    if any("paired" in reason or "identity" in reason or "arm_hash" in reason for reason in reasons):
        return STATUS_BLOCKED_IDENTITY
    if any("scorer_count" in reason or "scorer_reliability" in reason or "minimum_scorers" in reason for reason in reasons):
        return STATUS_BLOCKED_SCORER_RELIABILITY
    if any("raw_reference" in reason or "raw_output_boundary" in reason for reason in reasons):
        return STATUS_BLOCKED_RAW_BOUNDARY
    if any("forbidden_artifact" in reason or "repo_raw" in reason or "transcript" in reason or "secret" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("raw_count" in reason or "effective_n" in reason for reason in reasons):
        return STATUS_BLOCKED_EFFECTIVE_N
    if any("eligibility" in reason or "p_value" in reason or "effect_" in reason or "confidence" in reason or "bootstrap" in reason or "hac" in reason for reason in reasons):
        return STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    if any("claim_boundary" in reason for reason in reasons):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    return STATUS_BLOCKED_SCHEMA


def load_summary_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if prereg.claim_scan.forbidden_path(prereg.normalize_path(path)):
        return {}, [prereg.blocked_item(path, "fixture_path_forbidden", "summary fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [prereg.blocked_item(path, "fixture_missing", "summary fixture does not exist")]
    except json.JSONDecodeError:
        return {}, [prereg.blocked_item(path, "fixture_invalid_json", "summary fixture is not valid JSON")]
    if not isinstance(payload, dict):
        return {}, [prereg.blocked_item(path, "fixture_not_object", "summary fixture must be a JSON object")]
    return payload, []


def fixture_identity_blockers(payload: dict[str, Any], *, config: ScoredRecordConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "validation_id": config.validation_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(prereg.blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: ScoredRecordConfig, run_root: Path) -> None:
    summary["validation_id"] = config.validation_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: ScoredRecordConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = dict(payload) if payload else base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["evaluation_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_default_summary(config: ScoredRecordConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["evaluation_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: ScoredRecordConfig) -> dict[str, Any]:
    run_root = config.output_dir / config.validation_id
    run_id_blockers = validate_run_id(config.validation_id)
    if run_id_blockers:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
        finalize_blockers(summary, run_id_blockers)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = STATUS_BLOCKED_SCHEMA
        summary["evaluation_status"] = STATUS_BLOCKED_SCHEMA
        return summary
    if not prereg.under_tmp(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [prereg.blocked_item(config.output_dir, "output_dir_not_tmp", "output_dir must be under /tmp")]
        status = choose_status(blockers)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = status
        summary["evaluation_status"] = status
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        blockers = [prereg.blocked_item(run_root, "run_id_exists", "validation_id already exists; use --allow-overwrite")]
        summary["rubric_anchored_reasoning_quality_verdict_status"] = STATUS_RUN_ID_EXISTS
        summary["evaluation_status"] = STATUS_RUN_ID_EXISTS
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    if config.summary_fixture is not None:
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
    summary["validation_sha256"] = validation_digest(summary)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "validation_id": summary.get("validation_id"),
        "rubric_anchored_reasoning_quality_verdict_status": summary.get(
            "rubric_anchored_reasoning_quality_verdict_status"
        ),
        "summary_path": str(summary_path),
        "summary_sha256": prereg.sha256_file(summary_path),
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": summary.get("rubric_sha256"),
        "scored_record_schema_id": SCORED_RECORD_SCHEMA_ID,
        "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
        "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "repo_raw_artifacts": [],
        "evidence_layer": EVIDENCE_LAYER,
        "created_at_utc": utc_now_iso(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8s_rubric_reasoning_scored_records"))
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ScoredRecordConfig:
    return ScoredRecordConfig(
        validation_id=str(args.validation_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
    )


def main(argv: list[str] | None = None) -> int:
    summary = build_summary(config_from_args(parse_args(argv)))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("rubric_anchored_reasoning_quality_verdict_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
