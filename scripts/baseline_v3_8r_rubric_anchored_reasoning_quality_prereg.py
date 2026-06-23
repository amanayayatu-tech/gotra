#!/usr/bin/env python3
"""GOTRA v3.8R rubric-anchored reasoning-quality prereg validator."""

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
from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as packet_canary  # noqa: E402
from scripts import baseline_v3_8j_cognitive_lift_rubric_prereg_schema as rubric  # noqa: E402


SUMMARY_SCHEMA = "gotra.v3_8r.rubric_anchored_reasoning_quality_prereg_summary.v1"
MANIFEST_SCHEMA = "gotra.v3_8r.rubric_anchored_reasoning_quality_prereg_manifest.v1"
PREREG_SCHEMA_ID = "gotra.v3_8r.rubric_anchored_reasoning_quality_prereg.v1"
RUN_ID_PREFIX = "gotra_v3_8r_rubric_reasoning_quality_"
RUN_ID_RE = re.compile(rf"^{RUN_ID_PREFIX}[0-9TZ_-]+$")
SCRIPT_VERSION = "v3.8r-20260622"
EVIDENCE_LAYER = "local_checks_rubric_anchored_reasoning_quality_prereg_schema"
BASELINE_REPO_HEAD = "0cf31c9f1c8c36353edc98c6a455a8cab60202c6"
RUBRIC_VERSION = rubric.SCHEMA_VERSION
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
RAW_OUTPUT_BOUNDARY = "/tmp only"

STATUS_READY = "RUBRIC_ANCHORED_REASONING_QUALITY_PREREG_READY"
STATUS_BLOCKED_PREREG = "BLOCKED_PREREG"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_RUBRIC_LOCK = "BLOCKED_RUBRIC_LOCK"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_COMPARATOR_BOUNDARY = "BLOCKED_COMPARATOR_BOUNDARY"
STATUS_BLOCKED_PROVIDER_AUTHORIZATION = "BLOCKED_PROVIDER_AUTHORIZATION"
STATUS_BLOCKED_USAGE_METADATA = "BLOCKED_USAGE_METADATA"
STATUS_BLOCKED_RAW_BOUNDARY = "BLOCKED_RAW_BOUNDARY"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_EFFECTIVE_N = "BLOCKED_EFFECTIVE_N"
STATUS_BLOCKED_STATISTICAL_ELIGIBILITY = "BLOCKED_STATISTICAL_ELIGIBILITY"
STATUS_RUN_ID_EXISTS = "RUBRIC_ANCHORED_REASONING_QUALITY_PREREG_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_PREREG,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_RUBRIC_LOCK,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_BLOCKED_COMPARATOR_BOUNDARY,
    STATUS_BLOCKED_PROVIDER_AUTHORIZATION,
    STATUS_BLOCKED_USAGE_METADATA,
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
SOURCE_PRS = tuple(range(66, 78))
SECRET_RE = packet_canary.SECRET_RE
RUNTIME_FALSE_FLAGS = (
    "provider_or_backend_called",
    "provider_or_backend_called_for_prereg",
    "provider_canary_executed",
    "provider_canary_executed_for_prereg",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "actual_30d_verdict_executed",
)
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "schema_id",
    "schema_version",
    "script_version",
    "preregistration_id",
    "created_at_utc",
    "baseline_repo_head",
    "source_prs",
    "rubric_version",
    "rubric_sha256",
    "source_artifact_sha256",
    "probe_rule_sha256",
    "rubric_lock_status",
    "scoring_mode",
    "actual_30d_readiness_status",
    "cognitive_lift_superiority_verdict_status",
    "rubric_anchored_reasoning_quality_verdict_status",
    DIRECT_INTERPRETATION_KEY,
    DIRECT_CLEAN_BASELINE_KEY,
    "raw_output_boundary",
    "no_raw_repo",
    "provider_or_backend_called_for_prereg",
    "provider_canary_executed_for_prereg",
    "codex_cli_new_call",
    "formal_lite_entered",
    "universe_definition",
    "selection",
    "work_unit",
    "probe_rules",
    "provider_execution_policy",
    "primary_comparison",
    "clean_comparator_policy",
    "scorer_reliability",
    "effective_n_policy",
    "statistical_eligibility",
    "effect_fields_allowed_before_eligibility",
    "forbidden_before_eligibility",
    "effect_summary",
    "work_unit_counts",
    "can_say",
    "cannot_say",
    "non_claims",
}
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
CLAIM_BOUNDARY_RE = re.compile(
    r"\b(?:market\s+edge|public\s+science|science\s+proof|public\s+proof|trading\s+advice|"
    r"investment\s+advice|trading\s+recommendation|investment\s+recommendation|"
    r"winner|proved|confirmed|established|outperformed)\b|P\s*(?:&|&amp;)\s*L",
    re.IGNORECASE,
)
DIRECT_UNSAFE_RE = re.compile(
    r"(?:direct_llm|direct_llm_parametric_memory_control).{0,100}"
    r"(?:clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline)",
    re.IGNORECASE,
)
RAW_CONTENT_RE = re.compile(r"\b(?:full transcript|raw transcript|raw output|provider transcript)\b", re.IGNORECASE)
RAW_PATH_RE = re.compile(r"(?:^|[/. _-])raw(?:[/. _-]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class PreregConfig:
    preregistration_id: str
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
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError(f"preregistration_id must match {RUN_ID_RE.pattern!r}")


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


def is_numeric_zero(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def contains_secret(value: Any) -> bool:
    return bool(SECRET_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)))


def rubric_lock_digest() -> str:
    return stable_sha256_json(
        {
            "rubric_version": RUBRIC_VERSION,
            "dimensions": list(rubric.DIMENSIONS),
            "score_range": {"min": 0, "max": 5, "step": 0.5},
            "dimension_weights": dimension_weights(),
            "direct_llm_interpretation": DIRECT_INTERPRETATION,
            "direct_llm_clean_baseline": False,
        }
    )


def source_artifact_digest() -> str:
    return stable_sha256_json(
        {
            "baseline_repo_head": BASELINE_REPO_HEAD,
            "source_prs": list(SOURCE_PRS),
            "universe_definition": universe_definition(),
            "selection_seed": "gotra_v3_8r_seed_20260622",
            "selection_algorithm_version": "rubric_reasoning_quality_seeded_v1",
            "ticker_count": 100,
        }
    )


def selected_tickers_digest() -> str:
    return stable_sha256_json(
        {
            "selection_seed": "gotra_v3_8r_seed_20260622",
            "ticker_count": 100,
            "selection_algorithm_version": "rubric_reasoning_quality_seeded_v1",
        }
    )


def probe_rule_digest() -> str:
    payload = probe_rules(include_digest=False)
    return stable_sha256_json(payload)


def dimension_weights() -> dict[str, float]:
    return {dimension: 0.125 for dimension in rubric.DIMENSIONS}


def universe_definition() -> dict[str, Any]:
    return {
        "markets": ["US", "HK"],
        "inclusion_rules": {
            "liquidity_minimum": "PREREGISTERED",
            "market_cap_buckets": "PREREGISTERED",
            "sector_balance_policy": "PREREGISTERED",
        },
        "exclusion_rules": [
            "insufficient_history",
            "suspended_or_untradable",
            "missing_visible_data_boundary",
        ],
    }


def selection_lock() -> dict[str, Any]:
    digest = source_artifact_digest()
    return {
        "ticker_count": 100,
        "selection_seed": "gotra_v3_8r_seed_20260622",
        "selection_algorithm_version": "rubric_reasoning_quality_seeded_v1",
        "selected_tickers_sha256": selected_tickers_digest(),
        "source_artifact_sha256": digest,
        "locked_at_T0": True,
        "post_hoc_selection_allowed": False,
    }


def work_unit_definition() -> dict[str, Any]:
    return {
        "unit_key": ["ticker", "decision_date", "arm_identity", "probe_variant_id"],
        "arms": {
            "allowed": list(ALLOWED_ARMS),
            "direct_llm_role": "diagnostic_only_not_claim_comparator",
        },
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
        "provenance_fields": [
            "source_run_id",
            "source_summary_sha256",
            "source_artifact_sha256",
            "source_stage_metadata_sha256",
        ],
    }


def probe_rules(*, include_digest: bool = True) -> dict[str, Any]:
    payload = {
        "baseline_probe_required": True,
        "allowed_probe_types": [
            "baseline",
            "counterfactual_mask_research_context",
            "ticker_swap_control",
            "visible_data_boundary_trim",
            "prompt_variant_stability",
        ],
        "post_hoc_probe_addition_allowed": False,
        "no_silent_caps": True,
    }
    if include_digest:
        payload["probe_rule_sha256"] = probe_rule_digest()
    return payload


def provider_execution_policy() -> dict[str, Any]:
    return {
        "execution_allowed_without_separate_user_authorization": False,
        "required_authorization_fields": {
            "provider_backend_model": "REQUIRED",
            "provider_family": "REQUIRED",
            "call_cap": "REQUIRED_NUMERIC",
            "token_cap": "REQUIRED_NUMERIC",
            "cost_cap": "REQUIRED_NUMERIC",
            "usage_metadata_required": True,
            "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        },
        "placeholder_caps_executable": False,
        "default_placeholder_status": "NOT_EXECUTABLE_PLACEHOLDER_CAPS",
    }


def primary_comparison() -> dict[str, Any]:
    return {
        "candidates": list(CANDIDATE_ARMS),
        "clean_comparators": list(CLEAN_COMPARATORS),
        "comparator_policy": {
            DIRECT_INTERPRETATION: "diagnostic_only_not_claim_comparator",
            "deterministic_price_only": "allowed_clean_reference_if_preregistered",
            "simple_statistical_reference": "allowed_clean_reference_if_preregistered",
            "preregistered_non_direct_control": "allowed_clean_reference_if_preregistered",
        },
    }


def clean_comparator_policy() -> dict[str, Any]:
    return {
        "direct_llm_diagnostic_only": True,
        "required_non_direct_comparator": True,
        "allowed_clean_references": list(CLEAN_COMPARATORS),
    }


def scorer_reliability() -> dict[str, Any]:
    return {
        "minimum_scorers_per_record": 2,
        "adjudication_required_if_score_delta_gt": 1.0,
        "reliability_metric": ["intraclass_correlation", "kendall_tau_rank_stability"],
        "reliability_minimum": "PREREGISTERED",
        "blocked_status_if_failed": "BLOCKED_SCORER_RELIABILITY",
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


def base_summary(config: PreregConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    source_digest = source_artifact_digest()
    probe_digest = probe_rule_digest()
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "schema_id": PREREG_SCHEMA_ID,
        "schema_version": 1,
        "script_version": SCRIPT_VERSION,
        "preregistration_id": config.preregistration_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "created_at_utc": utc_now_iso(),
        "baseline_repo_head": BASELINE_REPO_HEAD,
        "source_prs": list(SOURCE_PRS),
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": rubric_lock_digest(),
        "source_artifact_sha256": source_digest,
        "probe_rule_sha256": probe_digest,
        "rubric_lock_status": "LOCKED_AT_T0",
        "scoring_mode": "paired_blind_locked_rubric",
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "rubric_anchored_reasoning_quality_verdict_status": status,
        "prereg_status": status,
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "no_raw_repo": True,
        "provider_or_backend_called": False,
        "provider_or_backend_called_for_prereg": False,
        "provider_canary_executed": False,
        "provider_canary_executed_for_prereg": False,
        "provider_execution_status": "NOT_REQUESTED",
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_verdict_executed": False,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "usage_metadata_available": False,
        "raw_paths": [],
        "repo_raw_artifacts": [],
        "universe_definition": universe_definition(),
        "selection": selection_lock(),
        "work_unit": work_unit_definition(),
        "probe_rules": probe_rules(),
        "provider_execution_policy": provider_execution_policy(),
        "primary_comparison": primary_comparison(),
        "clean_comparator_policy": clean_comparator_policy(),
        "score_range": {"min": 0, "max": 5, "step": 0.5},
        "dimension_weights": dimension_weights(),
        "scorer_reliability": scorer_reliability(),
        "effective_n_policy": effective_n_policy(),
        "statistical_eligibility": statistical_eligibility(),
        "effect_fields_allowed_before_eligibility": False,
        "forbidden_before_eligibility": sorted(FORBIDDEN_EFFECT_KEYS),
        "effect_summary": {"emitted": False, "values": None},
        "work_unit_counts": {
            "total_work_units": 0,
            "total_scored_records": 0,
            "clean_paired_unit_count": 0,
            "effective_independent_pair_count": 0,
            "effective_independent_pair_count_source": "not_computed_before_eligibility",
            "raw_count_used_as_independent_n": False,
        },
        "can_say": ["v3.8R prereg/schema local checks are ready for later rubric-anchored scoring work"],
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
        "rubric_lock_status_detail": "clean",
        "prereg_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "raw_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "comparator_boundary_status": "clean",
        "effective_n_status": "blocked_expected_before_eligibility",
        "statistical_eligibility_status": "blocked_expected_before_eligibility",
        "blocker_reasons": [],
        "blocked_items": [],
    }
    summary["preregistration_sha256"] = preregistration_digest(summary)
    return summary


def preregistration_digest(summary: dict[str, Any]) -> str:
    return stable_sha256_json(
        {
            "schema_id": summary.get("schema_id"),
            "schema_version": summary.get("schema_version"),
            "baseline_repo_head": summary.get("baseline_repo_head"),
            "source_prs": summary.get("source_prs"),
            "rubric_version": summary.get("rubric_version"),
            "rubric_sha256": summary.get("rubric_sha256"),
            "source_artifact_sha256": summary.get("source_artifact_sha256"),
            "probe_rule_sha256": summary.get("probe_rule_sha256"),
            "rubric_lock_status": summary.get("rubric_lock_status"),
            "scoring_mode": summary.get("scoring_mode"),
            "universe_definition": summary.get("universe_definition"),
            "selection": summary.get("selection"),
            "work_unit": summary.get("work_unit"),
            "probe_rules": summary.get("probe_rules"),
            "primary_comparison": summary.get("primary_comparison"),
            "clean_comparator_policy": summary.get("clean_comparator_policy"),
            "scorer_reliability": summary.get("scorer_reliability"),
            "effective_n_policy": summary.get("effective_n_policy"),
            "statistical_eligibility": summary.get("statistical_eligibility"),
            "effect_fields_allowed_before_eligibility": summary.get("effect_fields_allowed_before_eligibility"),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "raw_output_boundary": summary.get("raw_output_boundary"),
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


def recursive_paths(value: Any, *, key_hint: str = "") -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    path_keys = {
        "artifact_path",
        "artifact_paths",
        "manifest_path",
        "path",
        "paths",
        "raw_output_tmp_path",
        "raw_output_tmp_paths",
        "raw_path",
        "raw_paths",
        "raw_tmp_path",
        "raw_tmp_paths",
        "source_artifact_path",
        "source_artifact_paths",
        "summary_path",
        "transcript_path",
        "transcript_paths",
    }
    if isinstance(value, str):
        if key_hint in path_keys or claim_scan.forbidden_path(value) or _looks_like_raw_path(value):
            paths.append((key_hint, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(recursive_paths(item, key_hint=key))
    elif isinstance(value, list):
        for item in value:
            paths.extend(recursive_paths(item, key_hint=key_hint))
    return paths


def recursive_key_values(value: Any, *, path: str) -> list[tuple[str, str, Any]]:
    items: list[tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            items.append((item_path, str(key), item))
            items.extend(recursive_key_values(item, path=item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            items.extend(recursive_key_values(item, path=f"{path}[{index}]"))
    return items


def _looks_like_raw_path(value: str) -> bool:
    lowered = value.lower()
    if "transcript" in lowered and ("/" in value or "\\" in value or lowered.endswith((".txt", ".json", ".jsonl", ".log"))):
        return True
    if not RAW_PATH_RE.search(value):
        return False
    if re.search(r"\s", value) and not lowered.endswith((".json", ".jsonl", ".txt", ".md", ".log")):
        return False
    return "/" in value or "\\" in value or lowered.endswith((".json", ".jsonl", ".txt", ".md", ".log"))


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(blocked_item("summary.schema", "summary_schema_mismatch", f"schema must be {SUMMARY_SCHEMA}"))
    if summary.get("schema_id") != PREREG_SCHEMA_ID:
        blockers.append(blocked_item("summary.schema_id", "schema_id_mismatch", f"schema_id must be {PREREG_SCHEMA_ID}"))
    if summary.get("schema_version") != 1:
        blockers.append(blocked_item("summary.schema_version", "schema_version_mismatch", "schema_version must be 1"))
    status = str(summary.get("rubric_anchored_reasoning_quality_verdict_status") or "")
    if status not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.rubric_anchored_reasoning_quality_verdict_status", "invalid_status", "status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if not _is_iso_utc(summary.get("created_at_utc")):
        blockers.append(blocked_item("summary.created_at_utc", "created_at_utc_invalid", "created_at_utc must end in Z"))
    if summary.get("baseline_repo_head") != BASELINE_REPO_HEAD:
        blockers.append(blocked_item("summary.baseline_repo_head", "baseline_repo_head_mismatch", "baseline repo head must remain preregistered"))
    if summary.get("source_prs") != list(SOURCE_PRS):
        blockers.append(blocked_item("summary.source_prs", "source_prs_mismatch", "source PRs must match v3.8 prereg stack"))
    if summary.get("rubric_version") != RUBRIC_VERSION:
        blockers.append(blocked_item("summary.rubric_version", "rubric_version_mismatch", "rubric version must match v3.8J"))
    if summary.get("rubric_lock_status") != "LOCKED_AT_T0":
        blockers.append(blocked_item("summary.rubric_lock_status", "rubric_lock_status_invalid", "rubric must be locked at T0"))
    if summary.get("scoring_mode") != "paired_blind_locked_rubric":
        blockers.append(blocked_item("summary.scoring_mode", "scoring_mode_invalid", "scoring mode must be paired_blind_locked_rubric"))
    if summary.get("effect_fields_allowed_before_eligibility") is not False:
        blockers.append(blocked_item("summary.effect_fields_allowed_before_eligibility", "effect_fields_allowed_before_eligibility_not_false", "effect fields are blocked before eligibility"))
    for key in ("can_say", "cannot_say", "non_claims"):
        value = summary.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            blockers.append(blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))
    return blockers


def digest_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not is_hex(summary.get("rubric_sha256"), 64):
        blockers.append(blocked_item("summary.rubric_sha256", "rubric_sha256_missing_or_invalid", "rubric digest is required"))
    elif summary.get("rubric_sha256") != rubric_lock_digest():
        blockers.append(blocked_item("summary.rubric_sha256", "rubric_sha256_mismatch", "rubric digest must match locked rubric payload"))
    if not is_hex(summary.get("source_artifact_sha256"), 64):
        blockers.append(blocked_item("summary.source_artifact_sha256", "source_artifact_sha256_missing_or_invalid", "source artifact digest is required"))
    selection = summary.get("selection")
    if not isinstance(selection, dict):
        blockers.append(blocked_item("summary.selection", "selection_not_object", "selection must be an object"))
    else:
        if selection.get("source_artifact_sha256") != summary.get("source_artifact_sha256"):
            blockers.append(blocked_item("summary.selection.source_artifact_sha256", "selection_source_artifact_sha256_mismatch", "selection source digest must match top-level source digest"))
        if not is_hex(selection.get("selected_tickers_sha256"), 64):
            blockers.append(blocked_item("summary.selection.selected_tickers_sha256", "selected_tickers_sha256_missing_or_invalid", "selected ticker digest is required"))
        if selection.get("locked_at_T0") is not True:
            blockers.append(blocked_item("summary.selection.locked_at_T0", "selection_not_locked_at_t0", "selection must be locked at T0"))
        if selection.get("post_hoc_selection_allowed") is not False:
            blockers.append(blocked_item("summary.selection.post_hoc_selection_allowed", "post_hoc_selection_allowed_not_false", "post-hoc selection is forbidden"))
    if not is_hex(summary.get("probe_rule_sha256"), 64):
        blockers.append(blocked_item("summary.probe_rule_sha256", "probe_rule_sha256_missing_or_invalid", "probe rule digest is required"))
    probes = summary.get("probe_rules")
    if not isinstance(probes, dict):
        blockers.append(blocked_item("summary.probe_rules", "probe_rules_not_object", "probe rules must be an object"))
    else:
        if probes.get("probe_rule_sha256") != summary.get("probe_rule_sha256"):
            blockers.append(blocked_item("summary.probe_rules.probe_rule_sha256", "probe_rule_sha256_mismatch", "probe digest must match top-level digest"))
        if probes.get("post_hoc_probe_addition_allowed") is not False:
            blockers.append(blocked_item("summary.probe_rules.post_hoc_probe_addition_allowed", "post_hoc_probe_addition_allowed_not_false", "post-hoc probe additions are forbidden"))
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in RUNTIME_FALSE_FLAGS:
        if flag not in summary:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_missing", f"{flag} must be present and false"))
        elif summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8R"))
    if not is_numeric_zero(summary.get("real_calls_count")):
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_not_numeric_zero", "real call count must be integer zero"))
    if not is_numeric_zero(summary.get("token_usage_total")):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_not_numeric_zero", "token usage must be integer zero"))
    if summary.get("provider_execution_status") != "NOT_REQUESTED":
        blockers.append(blocked_item("summary.provider_execution_status", "provider_execution_status_not_requested", "provider execution is not requested in v3.8R"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if summary.get("cognitive_lift_superiority_verdict_status") != SUPERIORITY_STATUS:
        blockers.append(blocked_item("summary.cognitive_lift_superiority_verdict_status", "cognitive_lift_superiority_status_invalid", "cognitive-lift superiority status must remain not ready"))
    if summary.get("raw_output_boundary") != RAW_OUTPUT_BOUNDARY:
        blockers.append(blocked_item("summary.raw_output_boundary", "raw_output_boundary_invalid", "raw output boundary must be /tmp only"))
    if summary.get("no_raw_repo") is not True:
        blockers.append(blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "repo-facing artifacts must not include raw payloads"))
    return blockers


def direct_boundary_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_PREFIX + "_interpretation_mismatch", "direct_llm interpretation must stay parametric-memory control"))
    if summary.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(blocked_item(f"summary.{DIRECT_CLEAN_BASELINE_KEY}", DIRECT_PREFIX + "_clean_baseline_not_false", "direct_llm cannot be a clean baseline"))
    work_unit = summary.get("work_unit")
    if isinstance(work_unit, dict):
        arms = work_unit.get("arms")
        if not isinstance(arms, dict) or arms.get("direct_llm_role") != "diagnostic_only_not_claim_comparator":
            blockers.append(blocked_item("summary.work_unit.arms.direct_llm_role", "direct_control_role_mismatch", "direct control must remain diagnostic-only"))
    comparison = summary.get("primary_comparison")
    if isinstance(comparison, dict):
        policy = comparison.get("comparator_policy")
        if not isinstance(policy, dict) or policy.get(DIRECT_INTERPRETATION) != "diagnostic_only_not_claim_comparator":
            blockers.append(blocked_item("summary.primary_comparison.comparator_policy", "direct_comparator_policy_mismatch", "direct control cannot be claim comparator"))
    for path, text in recursive_strings(summary, path="prereg"):
        if _metadata_list_path(path):
            continue
        for match in DIRECT_UNSAFE_RE.finditer(text):
            role_start = _direct_role_start(match)
            if not claim_scan.is_negated(text, match.start() + role_start):
                blockers.append(blocked_item(path, DIRECT_PREFIX + "_unsafe_role_wording", "direct_llm cannot be clean/no-future/no-memory or primary comparator"))
    return blockers


def _direct_role_start(match: re.Match[str]) -> int:
    role_match = re.search(r"clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline", match.group(0), re.IGNORECASE)
    return role_match.start() if role_match else 0


def comparator_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    comparison = summary.get("primary_comparison")
    policy = summary.get("clean_comparator_policy")
    clean_comparators: list[str] = []
    if isinstance(comparison, dict):
        candidates = comparison.get("candidates")
        if candidates != list(CANDIDATE_ARMS):
            blockers.append(blocked_item("summary.primary_comparison.candidates", "candidate_arms_mismatch", "candidate arms must be full_gotra and ksana_real_research"))
        value = comparison.get("clean_comparators")
        if isinstance(value, list):
            clean_comparators = [str(item) for item in value]
    else:
        blockers.append(blocked_item("summary.primary_comparison", "primary_comparison_not_object", "primary comparison must be object"))
    if not clean_comparators:
        blockers.append(blocked_item("summary.primary_comparison.clean_comparators", "non_direct_clean_comparator_missing", "a preregistered non-direct clean comparator is required"))
    elif DIRECT_INTERPRETATION in clean_comparators and not (set(clean_comparators) - {DIRECT_INTERPRETATION}):
        blockers.append(blocked_item("summary.primary_comparison.clean_comparators", "only_clean_comparator_is_parametric_control", "direct_llm cannot be the only clean comparator"))
    elif not set(clean_comparators).intersection(CLEAN_COMPARATORS):
        blockers.append(blocked_item("summary.primary_comparison.clean_comparators", "non_direct_clean_comparator_missing", "clean comparator set must include a non-direct comparator"))
    if isinstance(policy, dict):
        if policy.get("direct_llm_diagnostic_only") is not True:
            blockers.append(blocked_item("summary.clean_comparator_policy.direct_llm_diagnostic_only", "direct_diagnostic_only_not_true", "direct control must be diagnostic only"))
        if policy.get("required_non_direct_comparator") is not True:
            blockers.append(blocked_item("summary.clean_comparator_policy.required_non_direct_comparator", "required_non_direct_comparator_not_true", "non-direct comparator is required"))
    else:
        blockers.append(blocked_item("summary.clean_comparator_policy", "clean_comparator_policy_not_object", "clean comparator policy must be object"))
    return blockers


def eligibility_all_true(summary: dict[str, Any]) -> bool:
    flags = summary.get("statistical_eligibility")
    return isinstance(flags, dict) and all(flags.get(key) is True for key in ELIGIBILITY_FLAGS)


def effect_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    eligible = eligibility_all_true(summary)
    effect_summary = summary.get("effect_summary")
    if not isinstance(effect_summary, dict):
        blockers.append(blocked_item("summary.effect_summary", "effect_summary_not_object", "effect summary must be object"))
        return blockers
    if not eligible and (effect_summary.get("emitted") is True or effect_summary.get("values") is not None):
        blockers.append(blocked_item("summary.effect_summary", "effect_summary_emitted_before_eligibility", "effect fields are forbidden before eligibility"))
    if not eligible:
        for path, key, value in recursive_key_values(summary, path="summary"):
            if key in FORBIDDEN_EFFECT_KEYS and value is not None and "forbidden_before_eligibility" not in path:
                blockers.append(blocked_item(path, f"{key}_before_eligibility", f"{key} is forbidden before eligibility"))
    return blockers


def effective_n_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    policy = summary.get("effective_n_policy")
    if not isinstance(policy, dict):
        blockers.append(blocked_item("summary.effective_n_policy", "effective_n_policy_not_object", "effective-N policy must be object"))
    else:
        if policy.get("raw_count_used_as_independent_n") is not False:
            blockers.append(blocked_item("summary.effective_n_policy.raw_count_used_as_independent_n", "raw_count_used_as_independent_n", "raw count cannot be independent N"))
        if policy.get("effective_n_field") != "effective_independent_pair_count":
            blockers.append(blocked_item("summary.effective_n_policy.effective_n_field", "effective_n_field_invalid", "effective-N field must be explicit"))
    counts = summary.get("work_unit_counts")
    if isinstance(counts, dict):
        if counts.get("raw_count_used_as_independent_n") is not False:
            blockers.append(blocked_item("summary.work_unit_counts.raw_count_used_as_independent_n", "raw_count_used_as_independent_n", "raw count cannot be independent N"))
        if counts.get("effective_independent_pair_count_source") == "raw_count":
            blockers.append(blocked_item("summary.work_unit_counts.effective_independent_pair_count_source", "effective_n_source_is_raw_count", "effective-N source cannot be raw count"))
    else:
        blockers.append(blocked_item("summary.work_unit_counts", "work_unit_counts_not_object", "work-unit counts must be object"))
    return blockers


def path_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for key_hint, candidate in recursive_paths(summary):
        if candidate.startswith("/tmp/") or candidate == "/tmp":
            continue
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocked_item(candidate, "forbidden_artifact_reference", "forbidden/raw artifact path reference"))
        elif key_hint.startswith("raw") or "transcript" in key_hint or _looks_like_raw_path(candidate):
            if not under_tmp(candidate):
                blockers.append(blocked_item(candidate, "raw_reference_not_tmp", "raw-like or transcript path references must stay under /tmp"))
    for path, text in recursive_strings(summary, path="prereg"):
        for match in RAW_CONTENT_RE.finditer(text):
            if not claim_scan.is_negated(text, match.start()):
                blockers.append(blocked_item(path, "repo_raw_or_full_transcript_reference", "repo-facing fields cannot contain raw output or full transcript text"))
    return blockers


def claim_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path, text in recursive_strings(summary, path="prereg"):
        if _metadata_list_path(path):
            continue
        for match in CLAIM_BOUNDARY_RE.finditer(text):
            if not claim_scan.is_negated(text, match.start()):
                blockers.append(blocked_item(path, "claim_boundary_forbidden_wording", "claim text exceeds local prereg boundary"))
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
    blockers.extend(digest_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(comparator_blockers(summary))
    blockers.extend(effect_blockers(summary))
    blockers.extend(effective_n_blockers(summary))
    blockers.extend(path_blockers(summary))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_rule_has(item, ("schema", "missing", "invalid", "not_object")) for item in blockers) else "clean"
    summary["rubric_lock_status_detail"] = "blocked" if any(_rule_has(item, ("rubric",)) for item in blockers) else "clean"
    summary["prereg_boundary_status"] = "blocked" if any(_rule_has(item, ("source_artifact", "probe_rule", "selection", "post_hoc")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim_boundary",)) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "provider", "codex", "formal", "actual_30d", "superiority", "calls", "token")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "repo_raw", "transcript", "secret")) for item in blockers) else "clean"
    summary["raw_boundary_status"] = "blocked" if any(_rule_has(item, ("raw_reference", "raw_output_boundary")) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control", "direct_comparator", "direct_diagnostic")) for item in blockers) else "clean"
    summary["comparator_boundary_status"] = "blocked" if any(_rule_has(item, ("comparator", "candidate_arms")) for item in blockers) else "clean"
    summary["effective_n_status"] = "blocked" if any(_rule_has(item, ("effective_n", "raw_count")) for item in blockers) else "blocked_expected_before_eligibility"
    summary["statistical_eligibility_status"] = "blocked" if any(_rule_has(item, ("eligibility", "p_value", "effect_", "confidence", "bootstrap", "hac")) for item in blockers) else "blocked_expected_before_eligibility"


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def choose_status(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("rubric_sha256" in reason or "rubric_lock" in reason for reason in reasons):
        return STATUS_BLOCKED_RUBRIC_LOCK
    if any("source_artifact_sha256" in reason or "probe_rule_sha256" in reason for reason in reasons):
        return STATUS_BLOCKED_PREREG
    if any(DIRECT_PREFIX in reason or "direct_control" in reason or "direct_comparator" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("comparator" in reason or "candidate_arms" in reason for reason in reasons):
        return STATUS_BLOCKED_COMPARATOR_BOUNDARY
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
    if any("usage_metadata" in reason for reason in reasons):
        return STATUS_BLOCKED_USAGE_METADATA
    if any("provider" in reason for reason in reasons):
        return STATUS_BLOCKED_PROVIDER_AUTHORIZATION
    if any("codex" in reason or "formal" in reason or "actual_30d" in reason or "superiority" in reason or "calls" in reason or "token" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
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


def fixture_identity_blockers(payload: dict[str, Any], *, config: PreregConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "preregistration_id": config.preregistration_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: PreregConfig, run_root: Path) -> None:
    summary["preregistration_id"] = config.preregistration_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: PreregConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = dict(payload) if payload else base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["prereg_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_default_prereg(config: PreregConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["prereg_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: PreregConfig) -> dict[str, Any]:
    validate_run_id(config.preregistration_id)
    run_root = config.output_dir / config.preregistration_id
    if not under_tmp(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(config.output_dir, "output_dir_not_tmp", "output_dir must be under /tmp")]
        status = choose_status(blockers)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = status
        summary["prereg_status"] = status
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        blockers = [blocked_item(run_root, "run_id_exists", "preregistration_id already exists; use --allow-overwrite")]
        summary["rubric_anchored_reasoning_quality_verdict_status"] = STATUS_RUN_ID_EXISTS
        summary["prereg_status"] = STATUS_RUN_ID_EXISTS
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    if config.summary_fixture is not None:
        summary = build_from_fixture(config, run_root=run_root)
    else:
        summary = build_default_prereg(config, run_root=run_root)
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary["preregistration_sha256"] = preregistration_digest(summary)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "preregistration_id": summary.get("preregistration_id"),
        "rubric_anchored_reasoning_quality_verdict_status": summary.get(
            "rubric_anchored_reasoning_quality_verdict_status"
        ),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "rubric_sha256": summary.get("rubric_sha256"),
        "source_artifact_sha256": summary.get("source_artifact_sha256"),
        "probe_rule_sha256": summary.get("probe_rule_sha256"),
        "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
        "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
        "provider_or_backend_called": False,
        "provider_or_backend_called_for_prereg": False,
        "provider_canary_executed": False,
        "provider_canary_executed_for_prereg": False,
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
    parser.add_argument("--preregistration-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8r_rubric_reasoning_quality_prereg"))
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PreregConfig:
    return PreregConfig(
        preregistration_id=str(args.preregistration_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(config_from_args(args))
    except ValueError as exc:
        print(json.dumps({"prereg_status": STATUS_BLOCKED_SCHEMA, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("rubric_anchored_reasoning_quality_verdict_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
