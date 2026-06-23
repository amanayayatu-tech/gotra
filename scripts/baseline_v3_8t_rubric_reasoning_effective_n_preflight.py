#!/usr/bin/env python3
"""GOTRA v3.8T rubric reasoning effective-N eligibility preflight."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
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


SUMMARY_SCHEMA = "gotra.v3_8t.rubric_reasoning_effective_n_preflight_summary.v1"
MANIFEST_SCHEMA = "gotra.v3_8t.rubric_reasoning_effective_n_preflight_manifest.v1"
RUN_ID_PREFIX = "gotra_v3_8t_rubric_reasoning_effective_n_preflight_"
RUN_ID_RE = re.compile(rf"^{RUN_ID_PREFIX}[0-9TZ_-]+$")
SCRIPT_VERSION = "v3.8t-20260622"
EVIDENCE_LAYER = "local_checks_rubric_reasoning_effective_n_clustered_eligibility_preflight"
RUBRIC_VERSION = rubric.SCHEMA_VERSION
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
RAW_OUTPUT_BOUNDARY = "/tmp only"

STATUS_READY = "RUBRIC_ANCHORED_REASONING_QUALITY_ELIGIBILITY_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_IDENTITY = "BLOCKED_IDENTITY"
STATUS_BLOCKED_SCORER_RELIABILITY = "BLOCKED_SCORER_RELIABILITY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_COMPARATOR_BOUNDARY = "BLOCKED_COMPARATOR_BOUNDARY"
STATUS_BLOCKED_RAW_BOUNDARY = "BLOCKED_RAW_BOUNDARY"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_EFFECTIVE_N = "BLOCKED_EFFECTIVE_N"
STATUS_BLOCKED_STATISTICAL_ELIGIBILITY = "BLOCKED_STATISTICAL_ELIGIBILITY"
STATUS_RUN_ID_EXISTS = "RUBRIC_ANCHORED_REASONING_QUALITY_ELIGIBILITY_BLOCKED_RUN_ID_EXISTS"
STATUS_BOUNDED_VERDICT = "RUBRIC_ANCHORED_REASONING_QUALITY_BOUNDED_VERDICT_READY"
STATUS_INCONCLUSIVE = "RUBRIC_ANCHORED_REASONING_QUALITY_INCONCLUSIVE"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_IDENTITY,
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

CANDIDATE_ARMS = ("full_gotra", "ksana_real_research")
CLEAN_COMPARATORS = (
    "deterministic_price_only",
    "simple_statistical_reference",
    "preregistered_non_direct_control",
)
CLEAN_PAIRED_UNIT_GROUPING_KEY = (
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
CLUSTERING_DIMENSIONS = ("ticker", "decision_date", "probe_family")
EFFECTIVE_N_ESTIMATORS = (
    "cluster_bootstrap",
    "block_bootstrap_by_decision_date",
    "sensitivity_analysis_by_ticker_cluster",
)
PREREG_MINIMUM_EFFECTIVE_N = 30
DEFAULT_CLEAN_PAIR_COUNT = 36
DEFAULT_EFFECTIVE_INDEPENDENT_PAIR_COUNT = 30
RUNTIME_FALSE_FLAGS = (
    "provider_or_backend_called",
    "provider_or_backend_called_for_preflight",
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
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "schema_id",
    "script_version",
    "preflight_id",
    "created_at_utc",
    "evidence_layer",
    "rubric_version",
    "rubric_sha256",
    "rubric_lock_status",
    "actual_30d_readiness_status",
    "cognitive_lift_superiority_verdict_status",
    "rubric_anchored_reasoning_quality_verdict_status",
    DIRECT_INTERPRETATION_KEY,
    DIRECT_CLEAN_BASELINE_KEY,
    "raw_output_boundary",
    "no_raw_repo",
    "provider_or_backend_called",
    "provider_or_backend_called_for_preflight",
    "provider_canary_executed",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "real_calls_count",
    "token_usage_total",
    "clean_paired_unit_policy",
    "clean_comparator_policy",
    "scorer_reliability",
    "clean_paired_units",
    "work_unit_counts",
    "effective_n_policy",
    "statistical_eligibility",
    "effect_fields_allowed_before_eligibility",
    "forbidden_before_eligibility",
    "effect_summary",
    "can_say",
    "cannot_say",
    "non_claims",
}
CLAIM_BOUNDARY_RE = re.compile(
    r"\b(?:market\s+edge|public\s+science|science\s+proof|public\s+proof|public\s+claim|"
    r"trading|trading\s+advice|investment\s+advice|trading\s+recommendation|"
    r"investment\s+recommendation|winner|proved|confirmed|established|outperformed|"
    r"bounded\s+(?:rubric[- ]anchored\s+)?(?:reasoning[- ]quality\s+)?verdict)\b|"
    r"RUBRIC_ANCHORED_REASONING_QUALITY_BOUNDED_VERDICT_READY|P\s*(?:&|&amp;)\s*L",
    re.IGNORECASE,
)
RAW_CONTENT_RE = re.compile(r"\b(?:full transcript|raw transcript|raw output|provider transcript)\b", re.IGNORECASE)


@dataclass(frozen=True)
class EffectiveNPreflightConfig:
    preflight_id: str
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
        return [prereg.blocked_item("summary.preflight_id", "preflight_id_invalid", "preflight_id has invalid shape")]
    return []


def synthetic_hash(label: str) -> str:
    return prereg.stable_sha256_json({"v3_8t_fixture": label})


def clean_paired_unit_policy() -> dict[str, Any]:
    return {
        "grouping_key": list(CLEAN_PAIRED_UNIT_GROUPING_KEY),
        "required_candidate_arms": list(CANDIDATE_ARMS),
        "diagnostic_arm_optional": [DIRECT_INTERPRETATION],
        "required_clean_reference": {"one_of": list(CLEAN_COMPARATORS)},
    }


def clean_comparator_policy() -> dict[str, Any]:
    return {
        "direct_llm_diagnostic_only": True,
        "required_non_direct_comparator": True,
        "allowed_clean_references": list(CLEAN_COMPARATORS),
        "selected_clean_references": ["deterministic_price_only"],
        "direct_llm_interpretation": DIRECT_INTERPRETATION,
        "direct_llm_role": "diagnostic_only_not_claim_comparator",
    }


def scorer_reliability_policy() -> dict[str, Any]:
    return {
        "minimum_scorers_per_record": 2,
        "reliability_metric": ["intraclass_correlation", "kendall_tau_rank_stability"],
        "reliability_minimum": "PREREGISTERED",
        "scorer_reliability_ready": True,
        "blocked_status_if_failed": STATUS_BLOCKED_SCORER_RELIABILITY,
    }


def effective_n_policy() -> dict[str, Any]:
    return {
        "raw_unit_count_field": "clean_paired_unit_count",
        "effective_n_field": "effective_independent_pair_count",
        "clustering_dimensions": list(CLUSTERING_DIMENSIONS),
        "minimum_effective_n": PREREG_MINIMUM_EFFECTIVE_N,
        "effective_n_estimator": list(EFFECTIVE_N_ESTIMATORS),
        "raw_count_used_as_independent_n": False,
        "blocked_status_if_failed": STATUS_BLOCKED_EFFECTIVE_N,
    }


def statistical_eligibility() -> dict[str, bool]:
    return {flag: True for flag in ELIGIBILITY_FLAGS}


def default_clean_paired_units(count: int = DEFAULT_CLEAN_PAIR_COUNT) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    start_date = datetime(2026, 2, 3, tzinfo=UTC)
    tickers = ("AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL")
    probe_families = ("baseline", "counterfactual_mask", "boundary_trim")
    for index in range(count):
        ticker = tickers[index % len(tickers)]
        decision_date = (start_date + timedelta(days=index)).strftime("%Y-%m-%d")
        probe_family = probe_families[index % len(probe_families)]
        probe_variant_id = f"{probe_family}_v{index % 2}"
        units.append(
            {
                "paired_sample_id": f"pair-{index + 1:04d}",
                "ticker": ticker,
                "decision_date": decision_date,
                "horizon": "30d",
                "probe_variant_id": probe_variant_id,
                "probe_family": probe_family,
                "prompt_hash": synthetic_hash(f"prompt:{index}"),
                "input_hash": synthetic_hash(f"input:{index}"),
                "visible_data_boundary": decision_date,
                "rubric_version": RUBRIC_VERSION,
                "candidate_arms": list(CANDIDATE_ARMS),
                "diagnostic_arms": [DIRECT_INTERPRETATION],
                "clean_reference_arm": "deterministic_price_only",
                "cluster_key": {
                    "ticker": ticker,
                    "decision_date": decision_date,
                    "probe_family": probe_family,
                },
                "scorer_count_by_arm": {
                    "full_gotra": 2,
                    "ksana_real_research": 2,
                    "direct_llm_parametric_memory_control": 2,
                },
                "raw_paths": [],
            }
        )
    return units


def base_summary(config: EffectiveNPreflightConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    units = default_clean_paired_units()
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "schema_id": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "preflight_id": config.preflight_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "created_at_utc": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": prereg.rubric_lock_digest(),
        "rubric_lock_status": "LOCKED_AT_T0",
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "rubric_anchored_reasoning_quality_verdict_status": status,
        "eligibility_preflight_status": status,
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "no_raw_repo": True,
        "repo_raw_artifacts": [],
        "raw_paths": [],
        "provider_or_backend_called": False,
        "provider_or_backend_called_for_preflight": False,
        "provider_canary_executed": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_verdict_executed": False,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "usage_metadata_available": False,
        "clean_paired_unit_policy": clean_paired_unit_policy(),
        "clean_comparator_policy": clean_comparator_policy(),
        "scorer_reliability": scorer_reliability_policy(),
        "clean_paired_units": units,
        "work_unit_counts": {
            "clean_paired_unit_count": len(units),
            "effective_independent_pair_count": DEFAULT_EFFECTIVE_INDEPENDENT_PAIR_COUNT,
            "effective_independent_pair_count_source": "cluster_bootstrap",
            "raw_count_used_as_independent_n": False,
            "ticker_cluster_count": len({unit["ticker"] for unit in units}),
            "decision_date_cluster_count": len({unit["decision_date"] for unit in units}),
            "probe_family_cluster_count": len({unit["probe_family"] for unit in units}),
        },
        "effective_n_policy": effective_n_policy(),
        "statistical_eligibility": statistical_eligibility(),
        "effect_fields_allowed_before_eligibility": False,
        "forbidden_before_eligibility": sorted(FORBIDDEN_EFFECT_KEYS),
        "effect_summary": {"emitted": False, "values": None},
        "can_say": ["v3.8T effective-N and clustered statistical eligibility local preflight is ready"],
        "cannot_say": [
            "not_bounded_reasoning_quality_verdict",
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
        "scorer_reliability_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "raw_boundary_status": "clean",
        "claim_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "comparator_boundary_status": "clean",
        "effective_n_status": "clean",
        "statistical_eligibility_status": "clean",
        "blocker_reasons": [],
        "blocked_items": [],
    }
    summary["preflight_sha256"] = preflight_digest(summary)
    return summary


def preflight_digest(summary: dict[str, Any]) -> str:
    return prereg.stable_sha256_json(
        {
            "schema": summary.get("schema"),
            "script_version": summary.get("script_version"),
            "rubric_version": summary.get("rubric_version"),
            "rubric_sha256": summary.get("rubric_sha256"),
            "clean_paired_unit_policy": summary.get("clean_paired_unit_policy"),
            "clean_comparator_policy": summary.get("clean_comparator_policy"),
            "scorer_reliability": summary.get("scorer_reliability"),
            "work_unit_counts": summary.get("work_unit_counts"),
            "effective_n_policy": summary.get("effective_n_policy"),
            "statistical_eligibility": summary.get("statistical_eligibility"),
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


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = validate_run_id(str(summary.get("preflight_id") or ""))
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(prereg.blocked_item("summary.schema", "summary_schema_mismatch", "schema must match v3.8T"))
    if summary.get("schema_id") != SUMMARY_SCHEMA:
        blockers.append(prereg.blocked_item("summary.schema_id", "summary_schema_id_mismatch", "schema_id must match v3.8T"))
    if summary.get("script_version") != SCRIPT_VERSION:
        blockers.append(prereg.blocked_item("summary.script_version", "script_version_mismatch", "script version mismatch"))
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(prereg.blocked_item("summary.evidence_layer", "evidence_layer_mismatch", "v3.8T is local checks only"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(prereg.blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    status = str(summary.get("rubric_anchored_reasoning_quality_verdict_status") or "")
    if status == STATUS_BOUNDED_VERDICT or "BOUNDED_VERDICT" in status or "PUBLIC" in status or "SCIENCE" in status:
        blockers.append(
            prereg.blocked_item(
                "summary.rubric_anchored_reasoning_quality_verdict_status",
                "bounded_or_public_verdict_status_not_allowed_at_preflight",
                "v3.8T may emit eligibility readiness only, not bounded/public verdict status",
            )
        )
    elif status not in ALLOWED_STATUSES:
        blockers.append(prereg.blocked_item("summary.rubric_anchored_reasoning_quality_verdict_status", "invalid_status", "status is not allowed"))
    if not is_iso_utc(summary.get("created_at_utc")):
        blockers.append(prereg.blocked_item("summary.created_at_utc", "created_at_utc_invalid", "created_at_utc must end in Z"))
    if summary.get("rubric_version") != RUBRIC_VERSION:
        blockers.append(prereg.blocked_item("summary.rubric_version", "rubric_version_mismatch", "rubric version must match v3.8J"))
    if not prereg.is_hex(summary.get("rubric_sha256"), 64):
        blockers.append(prereg.blocked_item("summary.rubric_sha256", "rubric_sha256_missing_or_invalid", "rubric hash must be 64 hex"))
    if summary.get("rubric_lock_status") != "LOCKED_AT_T0":
        blockers.append(prereg.blocked_item("summary.rubric_lock_status", "rubric_lock_status_invalid", "rubric must remain locked"))
    if summary.get("effect_fields_allowed_before_eligibility") is not False:
        blockers.append(prereg.blocked_item("summary.effect_fields_allowed_before_eligibility", "effect_fields_allowed_before_eligibility_not_false", "effect fields are blocked before eligibility"))
    if summary.get("forbidden_before_eligibility") != sorted(FORBIDDEN_EFFECT_KEYS):
        blockers.append(prereg.blocked_item("summary.forbidden_before_eligibility", "forbidden_before_eligibility_mismatch", "forbidden effect fields must be locked"))
    for key in ("can_say", "cannot_say", "non_claims"):
        value = summary.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            blockers.append(prereg.blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))
    units = summary.get("clean_paired_units")
    if not isinstance(units, list) or not units:
        blockers.append(prereg.blocked_item("summary.clean_paired_units", "clean_paired_units_missing_or_empty", "clean paired units are required"))
    elif not all(isinstance(unit, dict) for unit in units):
        blockers.append(prereg.blocked_item("summary.clean_paired_units", "clean_paired_units_not_objects", "each clean paired unit must be an object"))
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


def clean_paired_unit_policy_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    policy = summary.get("clean_paired_unit_policy")
    if not isinstance(policy, dict):
        return [prereg.blocked_item("summary.clean_paired_unit_policy", "clean_paired_unit_policy_not_object", "clean paired unit policy must be an object")]
    blockers: list[dict[str, Any]] = []
    if policy.get("grouping_key") != list(CLEAN_PAIRED_UNIT_GROUPING_KEY):
        blockers.append(prereg.blocked_item("summary.clean_paired_unit_policy.grouping_key", "clean_paired_unit_grouping_key_mismatch", "clean paired unit grouping key must match prereg section 6.1"))
    if policy.get("required_candidate_arms") != list(CANDIDATE_ARMS):
        blockers.append(prereg.blocked_item("summary.clean_paired_unit_policy.required_candidate_arms", "required_candidate_arms_mismatch", "required candidate arms must be full_gotra and ksana_real_research"))
    if policy.get("diagnostic_arm_optional") != [DIRECT_INTERPRETATION]:
        blockers.append(prereg.blocked_item("summary.clean_paired_unit_policy.diagnostic_arm_optional", "diagnostic_arm_optional_mismatch", "direct_llm parametric control must remain optional diagnostic arm"))
    required_reference = policy.get("required_clean_reference")
    if not isinstance(required_reference, dict) or set(required_reference.get("one_of") or []) != set(CLEAN_COMPARATORS):
        blockers.append(prereg.blocked_item("summary.clean_paired_unit_policy.required_clean_reference", "required_clean_reference_mismatch", "clean reference must be one of the preregistered non-direct controls"))
    return blockers


def clean_paired_unit_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    units = summary.get("clean_paired_units")
    if not isinstance(units, list):
        return blockers
    for index, unit in enumerate(units):
        if not isinstance(unit, dict):
            continue
        path = f"summary.clean_paired_units[{index}]"
        for field in CLEAN_PAIRED_UNIT_GROUPING_KEY:
            if not isinstance(unit.get(field), str) or not str(unit.get(field)).strip():
                blockers.append(prereg.blocked_item(f"{path}.{field}", f"{field}_missing_or_invalid", f"{field} is required in clean paired unit grouping key"))
        candidate_arms = unit.get("candidate_arms")
        if not isinstance(candidate_arms, list) or not set(CANDIDATE_ARMS).issubset(set(candidate_arms)):
            blockers.append(prereg.blocked_item(f"{path}.candidate_arms", "paired_required_candidate_arm_missing", "clean paired unit must include full_gotra and ksana_real_research"))
        if isinstance(candidate_arms, list) and DIRECT_INTERPRETATION in candidate_arms:
            blockers.append(prereg.blocked_item(f"{path}.candidate_arms", "direct_llm_in_candidate_arms", "direct_llm must not be a candidate arm"))
        diagnostic_arms = unit.get("diagnostic_arms")
        if diagnostic_arms is not None and diagnostic_arms != [DIRECT_INTERPRETATION]:
            blockers.append(prereg.blocked_item(f"{path}.diagnostic_arms", "diagnostic_arms_invalid", "only direct_llm_parametric_memory_control is allowed as optional diagnostic arm"))
        clean_reference = unit.get("clean_reference_arm")
        if clean_reference == DIRECT_INTERPRETATION:
            blockers.append(prereg.blocked_item(f"{path}.clean_reference_arm", "only_clean_comparator_is_parametric_control", "direct_llm cannot be the only clean reference"))
        elif clean_reference not in CLEAN_COMPARATORS:
            blockers.append(prereg.blocked_item(f"{path}.clean_reference_arm", "non_direct_clean_comparator_missing", "clean paired unit requires a preregistered non-direct clean reference"))
        probe_family = unit.get("probe_family")
        if not isinstance(probe_family, str) or not probe_family.strip():
            blockers.append(prereg.blocked_item(f"{path}.probe_family", "cluster_dimension_probe_family_missing", "probe_family cluster dimension is required"))
        cluster_key = unit.get("cluster_key")
        if not isinstance(cluster_key, dict) or any(cluster_key.get(dimension) != unit.get(dimension) for dimension in CLUSTERING_DIMENSIONS):
            blockers.append(prereg.blocked_item(f"{path}.cluster_key", "cluster_key_dimension_mismatch", "cluster key must contain ticker, decision_date, and probe_family"))
        scorer_counts = unit.get("scorer_count_by_arm")
        if isinstance(scorer_counts, dict):
            for arm in CANDIDATE_ARMS:
                if not isinstance(scorer_counts.get(arm), int) or scorer_counts.get(arm) < 2:
                    blockers.append(prereg.blocked_item(f"{path}.scorer_count_by_arm.{arm}", "scorer_count_below_minimum", "each candidate arm needs at least two scorers"))
        raw_paths = unit.get("raw_paths", [])
        if not isinstance(raw_paths, list):
            blockers.append(prereg.blocked_item(f"{path}.raw_paths", "raw_paths_not_list", "raw paths must be a list"))
        else:
            for raw_path in raw_paths:
                if not isinstance(raw_path, str) or not prereg.under_tmp(raw_path):
                    blockers.append(prereg.blocked_item(f"{path}.raw_paths", "raw_reference_not_tmp", "raw paths must stay under /tmp"))
    return blockers


def clean_comparator_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    policy = summary.get("clean_comparator_policy")
    if not isinstance(policy, dict):
        return [prereg.blocked_item("summary.clean_comparator_policy", "clean_comparator_policy_not_object", "clean comparator policy must be object")]
    blockers: list[dict[str, Any]] = []
    if policy.get("direct_llm_diagnostic_only") is not True:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.direct_llm_diagnostic_only", "direct_diagnostic_only_not_true", "direct control must be diagnostic only"))
    if policy.get("required_non_direct_comparator") is not True:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.required_non_direct_comparator", "required_non_direct_comparator_not_true", "non-direct comparator is required"))
    if policy.get("direct_llm_interpretation") != DIRECT_INTERPRETATION:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.direct_llm_interpretation", "direct_llm_interpretation_mismatch", "direct_llm interpretation must remain parametric-memory control"))
    if policy.get("direct_llm_role") != "diagnostic_only_not_claim_comparator":
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.direct_llm_role", "direct_control_role_mismatch", "direct control must remain diagnostic only"))
    selected = policy.get("selected_clean_references")
    if not isinstance(selected, list) or not selected:
        blockers.append(prereg.blocked_item("summary.clean_comparator_policy.selected_clean_references", "non_direct_clean_comparator_missing", "a non-direct comparator is required"))
    else:
        selected_set = {str(item) for item in selected}
        if selected_set == {DIRECT_INTERPRETATION}:
            blockers.append(prereg.blocked_item("summary.clean_comparator_policy.selected_clean_references", "only_clean_comparator_is_parametric_control", "direct_llm cannot be the only clean comparator"))
        if DIRECT_INTERPRETATION in selected_set:
            blockers.append(prereg.blocked_item("summary.clean_comparator_policy.selected_clean_references", "direct_llm_selected_as_clean_comparator", "direct_llm cannot be selected as a clean comparator"))
        if not selected_set.intersection(CLEAN_COMPARATORS):
            blockers.append(prereg.blocked_item("summary.clean_comparator_policy.selected_clean_references", "non_direct_clean_comparator_missing", "selected clean references must include a preregistered non-direct comparator"))
    return blockers


def scorer_reliability_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    policy = summary.get("scorer_reliability")
    if not isinstance(policy, dict):
        return [prereg.blocked_item("summary.scorer_reliability", "scorer_reliability_not_object", "scorer reliability policy is required")]
    blockers: list[dict[str, Any]] = []
    if policy.get("minimum_scorers_per_record") != 2:
        blockers.append(prereg.blocked_item("summary.scorer_reliability.minimum_scorers_per_record", "minimum_scorers_per_record_not_two", "minimum scorers per record must be 2"))
    if policy.get("scorer_reliability_ready") is not True:
        blockers.append(prereg.blocked_item("summary.scorer_reliability.scorer_reliability_ready", "scorer_reliability_ready_false", "scorer reliability must be ready before eligibility"))
    return blockers


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


def effective_n_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    policy = summary.get("effective_n_policy")
    counts = summary.get("work_unit_counts")
    if not isinstance(policy, dict):
        blockers.append(prereg.blocked_item("summary.effective_n_policy", "effective_n_policy_not_object", "effective-N policy must be object"))
    else:
        if policy.get("raw_unit_count_field") != "clean_paired_unit_count":
            blockers.append(prereg.blocked_item("summary.effective_n_policy.raw_unit_count_field", "raw_unit_count_field_invalid", "raw count field must be clean_paired_unit_count"))
        if policy.get("effective_n_field") != "effective_independent_pair_count":
            blockers.append(prereg.blocked_item("summary.effective_n_policy.effective_n_field", "effective_n_field_invalid", "effective-N field must be effective_independent_pair_count"))
        if policy.get("clustering_dimensions") != list(CLUSTERING_DIMENSIONS):
            blockers.append(prereg.blocked_item("summary.effective_n_policy.clustering_dimensions", "clustering_dimensions_missing_or_invalid", "clustering dimensions must be ticker, decision_date, probe_family"))
        estimators = policy.get("effective_n_estimator")
        if not isinstance(estimators, list) or not set(EFFECTIVE_N_ESTIMATORS).issubset(set(estimators)):
            blockers.append(prereg.blocked_item("summary.effective_n_policy.effective_n_estimator", "effective_n_estimator_list_missing_or_invalid", "effective-N estimators must include cluster, block, and ticker-cluster sensitivity estimators"))
        minimum = policy.get("minimum_effective_n")
        if not isinstance(minimum, int | float) or isinstance(minimum, bool) or minimum <= 0:
            blockers.append(prereg.blocked_item("summary.effective_n_policy.minimum_effective_n", "minimum_effective_n_invalid", "minimum effective-N must be a preregistered positive number"))
        if policy.get("raw_count_used_as_independent_n") is not False:
            blockers.append(prereg.blocked_item("summary.effective_n_policy.raw_count_used_as_independent_n", "raw_count_used_as_independent_n", "raw count cannot be independent N"))
        if policy.get("blocked_status_if_failed") != STATUS_BLOCKED_EFFECTIVE_N:
            blockers.append(prereg.blocked_item("summary.effective_n_policy.blocked_status_if_failed", "effective_n_blocked_status_invalid", "failed effective-N status must be BLOCKED_EFFECTIVE_N"))
    if not isinstance(counts, dict):
        blockers.append(prereg.blocked_item("summary.work_unit_counts", "work_unit_counts_not_object", "work unit counts must be object"))
        return blockers
    clean_count = counts.get("clean_paired_unit_count")
    effective_count = counts.get("effective_independent_pair_count")
    minimum = policy.get("minimum_effective_n") if isinstance(policy, dict) else PREREG_MINIMUM_EFFECTIVE_N
    if not isinstance(clean_count, int) or isinstance(clean_count, bool) or clean_count <= 0:
        blockers.append(prereg.blocked_item("summary.work_unit_counts.clean_paired_unit_count", "clean_paired_unit_count_invalid", "clean paired unit count must be positive integer"))
    if not isinstance(effective_count, int | float) or isinstance(effective_count, bool):
        blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count", "effective_independent_pair_count_invalid", "effective independent pair count must be numeric"))
    elif isinstance(minimum, int | float) and not isinstance(minimum, bool) and effective_count < minimum:
        blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count", "effective_n_below_preregistered_minimum", "effective-N is below preregistered minimum"))
    if isinstance(clean_count, int) and isinstance(effective_count, int | float):
        if effective_count > clean_count:
            blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count", "effective_n_exceeds_clean_pair_count", "effective-N cannot exceed clean paired unit count"))
        if clean_count > 1 and effective_count == clean_count:
            blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count", "effective_n_equals_raw_clean_pair_count", "raw count must not be accepted as independent N"))
    if counts.get("raw_count_used_as_independent_n") is not False:
        blockers.append(prereg.blocked_item("summary.work_unit_counts.raw_count_used_as_independent_n", "raw_count_used_as_independent_n", "raw count cannot be independent N"))
    if counts.get("effective_independent_pair_count_source") == "raw_count":
        blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count_source", "effective_n_source_is_raw_count", "effective-N source cannot be raw count"))
    elif counts.get("effective_independent_pair_count_source") not in EFFECTIVE_N_ESTIMATORS:
        blockers.append(prereg.blocked_item("summary.work_unit_counts.effective_independent_pair_count_source", "effective_n_source_not_preregistered_estimator", "effective-N source must be a preregistered clustered estimator"))
    for dimension in CLUSTERING_DIMENSIONS:
        count_key = f"{dimension}_cluster_count"
        if not isinstance(counts.get(count_key), int) or counts.get(count_key) <= 0:
            blockers.append(prereg.blocked_item(f"summary.work_unit_counts.{count_key}", "cluster_dimension_count_missing", "each clustering dimension needs a positive cluster count"))
    return blockers


def eligibility_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    flags = summary.get("statistical_eligibility")
    if not isinstance(flags, dict):
        return [prereg.blocked_item("summary.statistical_eligibility", "statistical_eligibility_not_object", "statistical eligibility flags are required")]
    blockers: list[dict[str, Any]] = []
    if set(flags) != set(ELIGIBILITY_FLAGS):
        blockers.append(prereg.blocked_item("summary.statistical_eligibility", "statistical_eligibility_flags_mismatch", "eligibility flags must match prereg section 6.3"))
    for flag in ELIGIBILITY_FLAGS:
        if flags.get(flag) is not True:
            blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "statistical_eligibility_flag_not_true", "all eligibility flags must be true at v3.8T readiness"))
            if flag == "scorer_reliability_ready":
                blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "scorer_reliability_ready_false", "scorer reliability gate must be true"))
            elif flag == "effective_n_ready":
                blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "effective_n_ready_false", "effective-N gate must be true"))
            elif flag == "claim_boundary_clean":
                blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "claim_boundary_clean_false", "claim boundary gate must be clean"))
            elif flag == "direct_llm_boundary_clean":
                blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "direct_llm_boundary_clean_false", "direct_llm boundary gate must be clean"))
            elif flag == "comparator_boundary_clean":
                blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "comparator_boundary_clean_false", "comparator boundary gate must be clean"))
            elif flag == "raw_artifact_boundary_clean":
                blockers.append(prereg.blocked_item(f"summary.statistical_eligibility.{flag}", "raw_artifact_boundary_clean_false", "raw artifact boundary gate must be clean"))
    return blockers


def eligibility_all_true(summary: dict[str, Any]) -> bool:
    flags = summary.get("statistical_eligibility")
    return isinstance(flags, dict) and all(flags.get(flag) is True for flag in ELIGIBILITY_FLAGS)


def effect_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    eligible = eligibility_all_true(summary)
    effect_summary = summary.get("effect_summary")
    if not isinstance(effect_summary, dict):
        return [prereg.blocked_item("summary.effect_summary", "effect_summary_not_object", "effect summary must be object")]
    effect_emitted = effect_summary.get("emitted") is True or effect_summary.get("values") is not None
    if effect_emitted:
        rule_id = "effect_summary_emitted_at_preflight_stage" if eligible else "effect_summary_emitted_before_eligibility"
        blockers.append(prereg.blocked_item("summary.effect_summary", rule_id, "v3.8T may preflight eligibility but must not emit effect fields or bounded verdict"))
    for path, key, value in prereg.recursive_key_values(summary, path="summary"):
        if key in FORBIDDEN_EFFECT_KEYS and value is not None and "forbidden_before_eligibility" not in path:
            rule_id = f"{key}_at_preflight_stage" if eligible else f"{key}_before_eligibility"
            blockers.append(prereg.blocked_item(path, rule_id, f"{key} is forbidden at v3.8T preflight"))
    if isinstance(effect_summary, dict):
        stage_status = effect_summary.get("status")
        if isinstance(stage_status, str) and stage_status in {STATUS_BOUNDED_VERDICT, STATUS_INCONCLUSIVE}:
            blockers.append(prereg.blocked_item("summary.effect_summary.status", "bounded_verdict_status_not_allowed_at_preflight", "v3.8T cannot output bounded verdict or inconclusive verdict status"))
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


def claim_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path):
            continue
        for match in CLAIM_BOUNDARY_RE.finditer(text):
            if not prereg.claim_scan.is_negated(text, match.start()):
                blockers.append(prereg.blocked_item(path, "claim_boundary_forbidden_wording", "claim text exceeds v3.8T local readiness boundary"))
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
    blockers.extend(clean_paired_unit_policy_blockers(summary))
    blockers.extend(clean_paired_unit_blockers(summary))
    blockers.extend(clean_comparator_blockers(summary))
    blockers.extend(scorer_reliability_blockers(summary))
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(effective_n_blockers(summary))
    blockers.extend(eligibility_blockers(summary))
    blockers.extend(effect_blockers(summary))
    blockers.extend(path_blockers(summary))
    if prereg.contains_secret(summary):
        blockers.append(prereg.blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_is_schema_rule(item) for item in blockers) else "clean"
    summary["paired_identity_status"] = "blocked" if any(_rule_has(item, ("paired", "identity", "candidate_arm", "grouping_key")) for item in blockers) else "clean"
    summary["scorer_reliability_status"] = "blocked" if any(_rule_has(item, ("scorer_count", "scorer_reliability", "minimum_scorers")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "provider", "codex", "formal", "actual_30d", "superiority", "calls", "token")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "repo_raw", "transcript", "secret")) for item in blockers) else "clean"
    summary["raw_boundary_status"] = "blocked" if any(_rule_has(item, ("raw_reference", "raw_output_boundary", "raw_artifact_boundary")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim_boundary", "bounded", "public_verdict")) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control", "direct_diagnostic", "direct_llm_boundary")) for item in blockers) else "clean"
    summary["comparator_boundary_status"] = "blocked" if any(_rule_has(item, ("comparator", "non_direct_clean", "parametric_control")) for item in blockers) else "clean"
    summary["effective_n_status"] = "blocked" if any(_rule_has(item, ("effective_n", "raw_count", "cluster_dimension", "cluster_key")) for item in blockers) else "clean"
    summary["statistical_eligibility_status"] = "blocked" if any(_rule_has(item, ("eligibility", "p_value", "effect_", "confidence", "bootstrap", "hac", "winner", "proved", "established", "outperformed")) for item in blockers) else "clean"


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
        "preflight_id_invalid",
        "created_at_utc_invalid",
        "summary_missing_field",
        "rubric_sha256_missing_or_invalid",
        "rubric_lock_status_invalid",
        "rubric_version_mismatch",
        "forbidden_before_eligibility_mismatch",
        "clean_paired_units_missing_or_empty",
        "clean_paired_units_not_objects",
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
    if any("scorer_count" in reason or "scorer_reliability" in reason or "minimum_scorers" in reason for reason in reasons):
        return STATUS_BLOCKED_SCORER_RELIABILITY
    if any("comparator" in reason or "parametric_control" in reason or "non_direct_clean" in reason for reason in reasons):
        return STATUS_BLOCKED_COMPARATOR_BOUNDARY
    if any(DIRECT_PREFIX in reason or "direct_control" in reason or "direct_diagnostic" in reason or "direct_llm_boundary" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("effective_n" in reason or "raw_count" in reason or "cluster_dimension" in reason or "cluster_key" in reason for reason in reasons):
        return STATUS_BLOCKED_EFFECTIVE_N
    if any("raw_reference" in reason or "raw_output_boundary" in reason or "raw_artifact_boundary" in reason for reason in reasons):
        return STATUS_BLOCKED_RAW_BOUNDARY
    if any("forbidden_artifact" in reason or "repo_raw" in reason or "transcript" in reason or "secret" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("claim_boundary" in reason or "bounded" in reason or "public_verdict" in reason for reason in reasons):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if any("paired" in reason or "identity" in reason or "candidate_arm" in reason or "grouping_key" in reason for reason in reasons):
        return STATUS_BLOCKED_IDENTITY
    if any("eligibility" in reason or "p_value" in reason or "effect_" in reason or "confidence" in reason or "bootstrap" in reason or "hac" in reason or "winner" in reason or "proved" in reason or "established" in reason or "outperformed" in reason for reason in reasons):
        return STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
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


def fixture_identity_blockers(payload: dict[str, Any], *, config: EffectiveNPreflightConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "preflight_id": config.preflight_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(prereg.blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: EffectiveNPreflightConfig, run_root: Path) -> None:
    summary["preflight_id"] = config.preflight_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: EffectiveNPreflightConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = dict(payload) if payload else base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["eligibility_preflight_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_default_summary(config: EffectiveNPreflightConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["eligibility_preflight_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: EffectiveNPreflightConfig) -> dict[str, Any]:
    run_root = config.output_dir / config.preflight_id
    run_id_blockers = validate_run_id(config.preflight_id)
    if run_id_blockers:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = STATUS_BLOCKED_SCHEMA
        summary["eligibility_preflight_status"] = STATUS_BLOCKED_SCHEMA
        finalize_blockers(summary, run_id_blockers)
        return summary
    if not prereg.under_tmp(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [prereg.blocked_item(config.output_dir, "output_dir_not_tmp", "output_dir must be under /tmp")]
        status = choose_status(blockers)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = status
        summary["eligibility_preflight_status"] = status
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        blockers = [prereg.blocked_item(run_root, "run_id_exists", "preflight_id already exists; use --allow-overwrite")]
        summary["rubric_anchored_reasoning_quality_verdict_status"] = STATUS_RUN_ID_EXISTS
        summary["eligibility_preflight_status"] = STATUS_RUN_ID_EXISTS
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
    summary["preflight_sha256"] = preflight_digest(summary)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "preflight_id": summary.get("preflight_id"),
        "rubric_anchored_reasoning_quality_verdict_status": summary.get(
            "rubric_anchored_reasoning_quality_verdict_status"
        ),
        "eligibility_preflight_status": summary.get("eligibility_preflight_status"),
        "summary_path": str(summary_path),
        "summary_sha256": prereg.sha256_file(summary_path),
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": summary.get("rubric_sha256"),
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
    parser.add_argument("--preflight-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8t_rubric_reasoning_effective_n_preflight"))
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> EffectiveNPreflightConfig:
    return EffectiveNPreflightConfig(
        preflight_id=str(args.preflight_id),
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
