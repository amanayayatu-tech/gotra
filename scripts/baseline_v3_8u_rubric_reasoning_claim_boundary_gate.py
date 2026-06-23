#!/usr/bin/env python3
"""GOTRA v3.8U rubric reasoning claim-boundary and conclusion gate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
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
from scripts import baseline_v3_8t_rubric_reasoning_effective_n_preflight as preflight  # noqa: E402


SUMMARY_SCHEMA = "gotra.v3_8u.rubric_reasoning_claim_boundary_gate_summary.v1"
MANIFEST_SCHEMA = "gotra.v3_8u.rubric_reasoning_claim_boundary_gate_manifest.v1"
RUN_ID_PREFIX = "gotra_v3_8u_rubric_reasoning_claim_boundary_gate_"
RUN_ID_RE = re.compile(rf"^{RUN_ID_PREFIX}[0-9TZ_-]+$")
SCRIPT_VERSION = "v3.8u-20260622"
EVIDENCE_LAYER = "local_checks_rubric_reasoning_claim_boundary_conclusion_gate"
RUBRIC_VERSION = rubric.SCHEMA_VERSION
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
RAW_OUTPUT_BOUNDARY = "/tmp only"

STATUS_READY = "RUBRIC_ANCHORED_REASONING_QUALITY_ELIGIBILITY_READY"
STATUS_PREREG_READY = "RUBRIC_ANCHORED_REASONING_QUALITY_PREREG_READY"
STATUS_EVALUATION_READY = "RUBRIC_ANCHORED_REASONING_QUALITY_EVALUATION_READY"
STATUS_BOUNDED_VERDICT = "RUBRIC_ANCHORED_REASONING_QUALITY_BOUNDED_VERDICT_READY"
STATUS_INCONCLUSIVE = "RUBRIC_ANCHORED_REASONING_QUALITY_INCONCLUSIVE"
STATUS_NON_CONTROLLER_CONCLUSION_READY = (
    "RUBRIC_ANCHORED_REASONING_QUALITY_CONCLUSION_TEMPLATE_READY"
)
STATUS_BLOCKED_PREREG = "BLOCKED_PREREG"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_IDENTITY = "BLOCKED_IDENTITY"
STATUS_BLOCKED_RUBRIC_LOCK = "BLOCKED_RUBRIC_LOCK"
STATUS_BLOCKED_BLIND_SCORING = "BLOCKED_BLIND_SCORING"
STATUS_BLOCKED_SCORER_RELIABILITY = "BLOCKED_SCORER_RELIABILITY"
STATUS_BLOCKED_EFFECTIVE_N = "BLOCKED_EFFECTIVE_N"
STATUS_BLOCKED_STATISTICAL_ELIGIBILITY = "BLOCKED_STATISTICAL_ELIGIBILITY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_COMPARATOR_BOUNDARY = "BLOCKED_COMPARATOR_BOUNDARY"
STATUS_BLOCKED_PROVIDER_AUTHORIZATION = "BLOCKED_PROVIDER_AUTHORIZATION"
STATUS_BLOCKED_USAGE_METADATA = "BLOCKED_USAGE_METADATA"
STATUS_BLOCKED_RAW_BOUNDARY = "BLOCKED_RAW_BOUNDARY"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_COST_CAP = "BLOCKED_COST_CAP"

CONTROLLER_ALLOWED_STATUSES = {
    STATUS_PREREG_READY,
    STATUS_EVALUATION_READY,
    STATUS_READY,
    STATUS_BOUNDED_VERDICT,
    STATUS_INCONCLUSIVE,
    STATUS_BLOCKED_PREREG,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_IDENTITY,
    STATUS_BLOCKED_RUBRIC_LOCK,
    STATUS_BLOCKED_BLIND_SCORING,
    STATUS_BLOCKED_SCORER_RELIABILITY,
    STATUS_BLOCKED_EFFECTIVE_N,
    STATUS_BLOCKED_STATISTICAL_ELIGIBILITY,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_BLOCKED_COMPARATOR_BOUNDARY,
    STATUS_BLOCKED_PROVIDER_AUTHORIZATION,
    STATUS_BLOCKED_USAGE_METADATA,
    STATUS_BLOCKED_RAW_BOUNDARY,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_COST_CAP,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

CANDIDATE_ARMS = ("full_gotra", "ksana_real_research")
CLEAN_COMPARATORS = (
    "deterministic_price_only",
    "simple_statistical_reference",
    "preregistered_non_direct_control",
)
RUNTIME_FALSE_FLAGS = (
    "provider_or_backend_called",
    "provider_or_backend_called_for_claim_gate",
    "provider_canary_executed",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "actual_30d_verdict_executed",
)
ELIGIBILITY_FLAGS = preflight.ELIGIBILITY_FLAGS
REQUIRED_CONCLUSION_TEMPLATE_KEYS = {
    "local_fixture_schema_tooling_readiness",
    "future_provider_authorized_scored_run",
    "provider_scored_inconclusive_if_gates_fail",
    "bounded_rubric_anchored_reasoning_quality_conclusion",
    "actual_30d_never_from_this_gate",
}
REQUIRED_EVIDENCE_LAYERS = (
    "local_checks",
    "smoke_evidence",
    "long_run_formal_acceptance",
    "science_public_claim",
)
REQUIRED_NON_CLAIMS = {
    "not_market_edge_verdict",
    "not_realized_pnl_verdict",
    "not_actual_30d_verdict",
    "not_forward_live_outcome_superiority",
    "not_public_science_proof",
    "not_trading_or_investment_advice",
    "not_superiority_over_direct_llm_as_clean_baseline",
    "direct_llm_is_parametric_memory_control_only",
}
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "schema_id",
    "script_version",
    "gate_id",
    "created_at_utc",
    "evidence_layer",
    "evidence_layers",
    "rubric_version",
    "rubric_sha256",
    "rubric_lock_status",
    "actual_30d_readiness_status",
    "cognitive_lift_superiority_verdict_status",
    "rubric_anchored_reasoning_quality_verdict_status",
    "conclusion_template_ready",
    "claim_boundary_gate_ready",
    "claim_boundary_gate_status",
    DIRECT_INTERPRETATION_KEY,
    DIRECT_CLEAN_BASELINE_KEY,
    "raw_output_boundary",
    "no_raw_repo",
    "provider_or_backend_called",
    "provider_or_backend_called_for_claim_gate",
    "provider_canary_executed",
    "codex_cli_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "real_calls_count",
    "token_usage_total",
    "usage_metadata_available",
    "clean_comparator_policy",
    "bounded_verdict_preconditions",
    "statistical_eligibility",
    "claim_boundary_flags",
    "can_say",
    "cannot_say",
    "non_claims",
    "allowed_conclusion_text",
    "conclusion_templates",
    "effect_summary",
}

DIRECT_UNSAFE_RE = re.compile(
    r"(?:direct_llm|direct_llm_parametric_memory_control).{0,120}"
    r"(?:clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline|"
    r"sole clean comparator|only clean comparator)",
    re.IGNORECASE,
)
DIRECT_UNSAFE_ROLE_RE = re.compile(
    r"\b(?:clean|no[-_ ]future|no[-_ ]memory|primary comparator|primary baseline|"
    r"sole clean comparator|only clean comparator)\b",
    re.IGNORECASE,
)
CLAIM_BOUNDARY_RE = re.compile(
    r"\b(?:market\s+edge|public\s+science|science\s+proof|public\s+proof|public\s+claim|"
    r"trading\s+signal|trading\s+advice|investment\s+advice|trading\s+recommendation|"
    r"investment\s+recommendation|investment\s+guidance|trading\s+guidance|"
    r"winner|proved|confirmed|established|outperformed|superiority|clean\s+baseline|"
    r"no[-_ ]future(?:/|[-_ ]| )no[-_ ]memory\s+baseline|"
    r"30D\s+actual\s+verdict\s+ready|actual\s+30D\s+verdict\s+ready|"
    r"realized\s+P\s*(?:&|&amp;)\s*L|P\s*(?:&|&amp;)\s*L)\b|"
    r"已证明.{0,30}(?:认知增强优越性|market\s+edge|市场优势)|"
    r"可用于.{0,12}(?:交易|投资建议)|公共科学证明|公开科学证明",
    re.IGNORECASE,
)
BOUNDED_VERDICT_TEXT_RE = re.compile(
    r"\b(?:bounded[-_ ]verdict|bounded\s+(?:rubric[-_ ]anchored\s+)?"
    r"(?:reasoning[-_ ]quality\s+)?verdict|"
    r"RUBRIC_ANCHORED_REASONING_QUALITY_BOUNDED_VERDICT_READY)\b",
    re.IGNORECASE,
)
RAW_CONTENT_RE = re.compile(
    r"\b(?:full transcript|raw transcript|raw output|provider transcript|raw provider output)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClaimBoundaryGateConfig:
    gate_id: str
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
        return [prereg.blocked_item("summary.gate_id", "gate_id_invalid", "gate_id has invalid shape")]
    return []


def is_iso_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def synthetic_hash(label: str) -> str:
    return prereg.stable_sha256_json({"v3_8u_fixture": label})


def clean_comparator_policy() -> dict[str, Any]:
    return {
        "direct_llm_diagnostic_only": True,
        "required_non_direct_comparator": True,
        "allowed_clean_references": list(CLEAN_COMPARATORS),
        "selected_clean_references": ["deterministic_price_only"],
        "direct_llm_interpretation": DIRECT_INTERPRETATION,
        "direct_llm_role": "diagnostic_only_not_claim_comparator",
    }


def bounded_verdict_preconditions() -> dict[str, bool]:
    return {
        "provider_scored_evidence_ready": False,
        "usage_metadata_available": False,
        "effective_n_ready": False,
        "scorer_reliability_ready": False,
        "clustered_statistical_eligibility_ready": False,
        "claim_boundary_fan_in_ready": False,
        "non_direct_comparator_ready": True,
        "raw_artifact_boundary_clean": True,
    }


def statistical_eligibility() -> dict[str, bool]:
    return {flag: False for flag in ELIGIBILITY_FLAGS}


def claim_boundary_flags() -> dict[str, bool]:
    return {
        "claim_boundary_clean": True,
        "direct_llm_boundary_clean": True,
        "comparator_boundary_clean": True,
        "raw_artifact_boundary_clean": True,
        "runtime_boundary_clean": True,
        "artifact_boundary_clean": True,
    }


def evidence_layers() -> dict[str, dict[str, Any]]:
    return {
        "local_checks": {
            "status": "ready",
            "allowed": "schema, fixture, tooling, and claim-boundary readiness",
        },
        "smoke_evidence": {
            "status": "not_run",
            "allowed": "optional future provider-authorized scored-run smoke only",
        },
        "long_run_formal_acceptance": {
            "status": "not_entered",
            "allowed": "requires provider-scored evidence, reliability, effective-N, and cluster gates",
        },
        "science_public_claim": {
            "status": "not_allowed",
            "allowed": "none",
        },
    }


def conclusion_templates() -> dict[str, dict[str, Any]]:
    return {
        "local_fixture_schema_tooling_readiness": {
            "evidence_layer": "local_checks",
            "template": (
                "当前证据支持 GOTRA rubric-anchored reasoning-quality evaluation 的 "
                "prereg/schema/tooling readiness。尚未满足 effective-N、scorer reliability、"
                "clustered statistical eligibility 和 claim-boundary fan-in 条件, 因此不得输出 "
                "bounded reasoning-quality verdict。原 cognitive_lift_superiority_verdict_status "
                "仍为 NOT_YET_VERDICT_READY, actual_30d_readiness_status 仍为 DATA_NOT_MATURED。"
            ),
        },
        "future_provider_authorized_scored_run": {
            "evidence_layer": "smoke_evidence",
            "template": (
                "后续如经单独授权, 可运行 provider-authorized scored run; raw output 仍须 "
                "/tmp only, 并记录 usage/provenance/hash metadata。"
            ),
        },
        "provider_scored_inconclusive_if_gates_fail": {
            "evidence_layer": "long_run_formal_acceptance",
            "template": (
                "若真实 token 路径完成但 effective-N、scorer reliability、clustered eligibility "
                "或 claim boundary 任一失败, 结论只能是 "
                "RUBRIC_ANCHORED_REASONING_QUALITY_INCONCLUSIVE。"
            ),
        },
        "bounded_rubric_anchored_reasoning_quality_conclusion": {
            "permitted_only_if": sorted(bounded_verdict_preconditions()),
            "template": (
                "只有在 provider scored evidence、usage metadata、effective-N、scorer reliability、"
                "clustered statistical eligibility、non-direct comparator 和 claim-boundary fan-in "
                "全部满足后, 才可以输出 bounded rubric-anchored reasoning-quality conclusion。"
            ),
        },
        "actual_30d_never_from_this_gate": {
            "evidence_layer": "science_public_claim",
            "template": (
                "本 gate 永不输出 actual 30D cognitive-lift superiority verdict, market edge, "
                "public science proof, trading recommendation, or investment advice."
            ),
        },
    }


def base_summary(
    config: ClaimBoundaryGateConfig,
    *,
    run_root: Path,
    status: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "schema_id": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "gate_id": config.gate_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "created_at_utc": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "evidence_layers": evidence_layers(),
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": prereg.rubric_lock_digest(),
        "rubric_lock_status": "LOCKED_AT_T0",
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "rubric_anchored_reasoning_quality_verdict_status": status,
        "conclusion_template_ready": True,
        "claim_boundary_gate_ready": True,
        "claim_boundary_gate_status": status,
        "status_normalization": {
            "non_controller_status_observed": None,
            "normalized_to": None,
            "contract": "controller_pack_allowed_statuses_only_for_top_level_verdict_status",
        },
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "no_raw_repo": True,
        "repo_raw_artifacts": [],
        "raw_paths": [],
        "provider_or_backend_called": False,
        "provider_or_backend_called_for_claim_gate": False,
        "provider_canary_executed": False,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_verdict_executed": False,
        "real_calls_count": 0,
        "token_usage_total": 0,
        "usage_metadata_available": False,
        "clean_comparator_policy": clean_comparator_policy(),
        "bounded_verdict_preconditions": bounded_verdict_preconditions(),
        "statistical_eligibility": statistical_eligibility(),
        "claim_boundary_flags": claim_boundary_flags(),
        "effect_summary": {"emitted": False, "values": None},
        "can_say": [
            "v3.8U local fixture/schema/tooling claim-boundary gate is ready",
            "local checks show paired identity, locked rubric, direct_llm_parametric_memory_control boundary, "
            "raw-output boundary, and claim-boundary guards are executable",
        ],
        "cannot_say": [
            "not_bounded_reasoning_quality_verdict",
            "not_actual_30d_verdict",
            "not_forward_live_outcome_superiority",
            "not_realized_pnl_verdict",
            "not_public_science_proof",
            "not_trading_or_investment_advice",
            "not_superiority_over_direct_llm_as_clean_baseline",
        ],
        "non_claims": sorted(REQUIRED_NON_CLAIMS),
        "allowed_conclusion_text": [
            (
                "当前证据支持 GOTRA rubric-anchored reasoning-quality evaluation 的 "
                "prereg/schema/tooling readiness。尚未满足 effective-N、scorer reliability、"
                "clustered statistical eligibility 和 claim-boundary fan-in 条件, 因此不得输出 "
                "bounded reasoning-quality verdict。原 cognitive_lift_superiority_verdict_status "
                "仍为 NOT_YET_VERDICT_READY, actual_30d_readiness_status 仍为 DATA_NOT_MATURED。"
            ),
            (
                "本地 fixture/schema 验证显示 paired identity、locked rubric、"
                "direct_llm_parametric_memory_control boundary、raw-output boundary 和 "
                "claim-boundary 守门可执行。该证据层级为 local checks / engineering readiness, "
                "不构成真实 reasoning-quality superiority, 也不构成 30D outcome verdict。"
            ),
        ],
        "conclusion_templates": conclusion_templates(),
        "schema_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        "raw_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "comparator_boundary_status": "clean",
        "bounded_verdict_boundary_status": "clean",
        "blocker_reasons": [],
        "blocked_items": [],
    }
    summary["claim_boundary_gate_sha256"] = gate_digest(summary)
    return summary


def gate_digest(summary: dict[str, Any]) -> str:
    return prereg.stable_sha256_json(
        {
            "schema": summary.get("schema"),
            "script_version": summary.get("script_version"),
            "evidence_layer": summary.get("evidence_layer"),
            "evidence_layers": summary.get("evidence_layers"),
            "rubric_version": summary.get("rubric_version"),
            "rubric_sha256": summary.get("rubric_sha256"),
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "cognitive_lift_superiority_verdict_status": summary.get(
                "cognitive_lift_superiority_verdict_status"
            ),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "clean_comparator_policy": summary.get("clean_comparator_policy"),
            "bounded_verdict_preconditions": summary.get("bounded_verdict_preconditions"),
            "statistical_eligibility": summary.get("statistical_eligibility"),
            "claim_boundary_flags": summary.get("claim_boundary_flags"),
            "can_say": summary.get("can_say"),
            "cannot_say": summary.get("cannot_say"),
            "non_claims": summary.get("non_claims"),
            "allowed_conclusion_text": summary.get("allowed_conclusion_text"),
            "conclusion_templates": summary.get("conclusion_templates"),
        }
    )


def schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = validate_run_id(str(summary.get("gate_id") or ""))
    if summary.get("schema") != SUMMARY_SCHEMA:
        blockers.append(
            prereg.blocked_item("summary.schema", "summary_schema_mismatch", "schema must match v3.8U")
        )
    if summary.get("schema_id") != SUMMARY_SCHEMA:
        blockers.append(
            prereg.blocked_item(
                "summary.schema_id",
                "summary_schema_id_mismatch",
                "schema_id must match v3.8U",
            )
        )
    if summary.get("script_version") != SCRIPT_VERSION:
        blockers.append(
            prereg.blocked_item(
                "summary.script_version",
                "script_version_mismatch",
                "script version mismatch",
            )
        )
    if summary.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(
            prereg.blocked_item(
                "summary.evidence_layer",
                "evidence_layer_mismatch",
                "v3.8U is local checks only",
            )
        )
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(
        prereg.blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required")
        for key in missing
    )
    status = str(summary.get("rubric_anchored_reasoning_quality_verdict_status") or "")
    if status == STATUS_BOUNDED_VERDICT:
        blockers.append(
            prereg.blocked_item(
                "summary.rubric_anchored_reasoning_quality_verdict_status",
                "bounded_verdict_status_without_provider_scored_evidence",
                "v3.8U cannot emit bounded verdict without provider-scored evidence and fan-in gates",
            )
        )
    elif status == STATUS_NON_CONTROLLER_CONCLUSION_READY:
        _record_status_normalization(summary, status)
    elif status not in CONTROLLER_ALLOWED_STATUSES:
        blockers.append(
            prereg.blocked_item(
                "summary.rubric_anchored_reasoning_quality_verdict_status",
                "invalid_controller_pack_status",
                "top-level status must be controller-pack allowed",
            )
        )
    if not is_iso_utc(summary.get("created_at_utc")):
        blockers.append(
            prereg.blocked_item(
                "summary.created_at_utc",
                "created_at_utc_invalid",
                "created_at_utc must end in Z",
            )
        )
    if summary.get("rubric_version") != RUBRIC_VERSION:
        blockers.append(
            prereg.blocked_item(
                "summary.rubric_version",
                "rubric_version_mismatch",
                "rubric version must match v3.8J",
            )
        )
    if not prereg.is_hex(summary.get("rubric_sha256"), 64):
        blockers.append(
            prereg.blocked_item(
                "summary.rubric_sha256",
                "rubric_sha256_missing_or_invalid",
                "rubric hash must be 64 hex",
            )
        )
    if summary.get("rubric_lock_status") != "LOCKED_AT_T0":
        blockers.append(
            prereg.blocked_item(
                "summary.rubric_lock_status",
                "rubric_lock_status_invalid",
                "rubric must remain locked",
            )
        )
    for key in ("can_say", "cannot_say", "non_claims"):
        value = summary.get(key)
        if not isinstance(value, list) or not value or not all(_non_empty_string(item) for item in value):
            blockers.append(
                prereg.blocked_item(
                    f"summary.{key}",
                    f"{key}_invalid",
                    f"{key} must be a non-empty string list",
                )
            )
    non_claims = summary.get("non_claims")
    if isinstance(non_claims, list):
        missing_non_claims = sorted(REQUIRED_NON_CLAIMS - {str(item) for item in non_claims})
        blockers.extend(
            prereg.blocked_item(
                f"summary.non_claims.{item}",
                "required_non_claim_missing",
                f"{item} must be preserved",
            )
            for item in missing_non_claims
        )
    blockers.extend(evidence_layer_schema_blockers(summary))
    blockers.extend(conclusion_template_schema_blockers(summary))
    return blockers


def _record_status_normalization(summary: dict[str, Any], observed: str) -> None:
    status_normalization = summary.setdefault("status_normalization", {})
    if isinstance(status_normalization, dict):
        status_normalization["non_controller_status_observed"] = observed
        status_normalization["normalized_to"] = STATUS_READY
    summary["conclusion_template_ready"] = True


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evidence_layer_schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    layers = summary.get("evidence_layers")
    if not isinstance(layers, dict):
        return [
            prereg.blocked_item(
                "summary.evidence_layers",
                "evidence_layers_not_object",
                "evidence layers must be explicit",
            )
        ]
    blockers: list[dict[str, Any]] = []
    missing = [layer for layer in REQUIRED_EVIDENCE_LAYERS if layer not in layers]
    blockers.extend(
        prereg.blocked_item(
            f"summary.evidence_layers.{layer}",
            "evidence_layer_missing",
            f"{layer} must be explicit",
        )
        for layer in missing
    )
    science_layer = layers.get("science_public_claim")
    if isinstance(science_layer, dict) and science_layer.get("status") != "not_allowed":
        blockers.append(
            prereg.blocked_item(
                "summary.evidence_layers.science_public_claim.status",
                "science_public_claim_layer_not_blocked",
                "science/public claim layer must remain not_allowed",
            )
        )
    return blockers


def conclusion_template_schema_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    templates = summary.get("conclusion_templates")
    if not isinstance(templates, dict):
        return [
            prereg.blocked_item(
                "summary.conclusion_templates",
                "conclusion_templates_not_object",
                "conclusion templates must be explicit",
            )
        ]
    blockers: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_CONCLUSION_TEMPLATE_KEYS - set(templates))
    blockers.extend(
        prereg.blocked_item(
            f"summary.conclusion_templates.{key}",
            "conclusion_template_missing",
            f"{key} template is required",
        )
        for key in missing
    )
    for key, template in templates.items():
        path = f"summary.conclusion_templates.{key}"
        if not isinstance(template, dict):
            blockers.append(
                prereg.blocked_item(path, "conclusion_template_not_object", "template must be object")
            )
            continue
        if not _non_empty_string(template.get("template")):
            blockers.append(
                prereg.blocked_item(
                    f"{path}.template",
                    "conclusion_template_text_missing",
                    "template text is required",
                )
            )
    bounded = templates.get("bounded_rubric_anchored_reasoning_quality_conclusion")
    if isinstance(bounded, dict):
        permitted = bounded.get("permitted_only_if")
        expected = sorted(bounded_verdict_preconditions())
        if permitted != expected:
            blockers.append(
                prereg.blocked_item(
                    "summary.conclusion_templates.bounded_rubric_anchored_reasoning_quality_conclusion."
                    "permitted_only_if",
                    "bounded_template_preconditions_missing",
                    "bounded template must list every required precondition",
                )
            )
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in RUNTIME_FALSE_FLAGS:
        if flag not in summary:
            blockers.append(
                prereg.blocked_item(f"summary.{flag}", f"{flag}_missing", f"{flag} must be present")
            )
        elif summary.get(flag) is not False:
            blockers.append(
                prereg.blocked_item(
                    f"summary.{flag}",
                    f"{flag}_not_false",
                    f"{flag} must remain false in v3.8U",
                )
            )
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(
            prereg.blocked_item(
                "summary.actual_30d_readiness_status",
                "actual_30d_readiness_status_invalid",
                "actual 30D readiness must remain DATA_NOT_MATURED",
            )
        )
    if summary.get("cognitive_lift_superiority_verdict_status") != SUPERIORITY_STATUS:
        blockers.append(
            prereg.blocked_item(
                "summary.cognitive_lift_superiority_verdict_status",
                "cognitive_lift_superiority_status_invalid",
                "cognitive-lift superiority status must remain not ready",
            )
        )
    if summary.get("raw_output_boundary") != RAW_OUTPUT_BOUNDARY:
        blockers.append(
            prereg.blocked_item(
                "summary.raw_output_boundary",
                "raw_output_boundary_invalid",
                "raw output boundary must be /tmp only",
            )
        )
    if summary.get("no_raw_repo") is not True:
        blockers.append(
            prereg.blocked_item(
                "summary.no_raw_repo",
                "no_raw_repo_not_true",
                "repo-facing fields must not include raw payloads",
            )
        )
    for key in ("real_calls_count", "token_usage_total"):
        if not prereg.is_numeric_zero(summary.get(key)):
            blockers.append(
                prereg.blocked_item(
                    f"summary.{key}",
                    f"{key}_not_numeric_zero",
                    f"{key} must be integer zero",
                )
            )
    if summary.get("usage_metadata_available") is not False:
        blockers.append(
            prereg.blocked_item(
                "summary.usage_metadata_available",
                "usage_metadata_available_not_false",
                "no provider-scored run occurred in v3.8U",
            )
        )
    return blockers


def direct_boundary_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(
            prereg.blocked_item(
                f"summary.{DIRECT_INTERPRETATION_KEY}",
                DIRECT_PREFIX + "_interpretation_mismatch",
                "direct_llm interpretation must remain parametric-memory control",
            )
        )
    if summary.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(
            prereg.blocked_item(
                f"summary.{DIRECT_CLEAN_BASELINE_KEY}",
                DIRECT_PREFIX + "_clean_baseline_not_false",
                "direct_llm cannot be a clean baseline",
            )
        )
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path):
            continue
        if _direct_without_parametric_label(text):
            blockers.append(
                prereg.blocked_item(
                    path,
                    DIRECT_PREFIX + "_without_parametric_memory_control",
                    "direct_llm references must use direct_llm_parametric_memory_control",
                )
            )
        for match in DIRECT_UNSAFE_RE.finditer(text):
            role_match = DIRECT_UNSAFE_ROLE_RE.search(match.group(0))
            role_start = match.start() + role_match.start() if role_match else match.start()
            if not _is_negated(text, role_start):
                blockers.append(
                    prereg.blocked_item(
                        path,
                        DIRECT_PREFIX + "_unsafe_role_wording",
                        "direct_llm cannot be clean/no-future/no-memory or primary comparator",
                    )
                )
    return blockers


def _direct_without_parametric_label(text: str) -> bool:
    for match in re.finditer(r"\bdirect_llm\b", text, re.IGNORECASE):
        boundary_window = text[match.start() : match.end() + 32].lower()
        if re.match(r"direct_llm(?:[_ -]?boundary|[_ -]?boundary[_ -]?status)\b", boundary_window):
            continue
        window = text[match.start() : match.start() + len(DIRECT_INTERPRETATION)]
        if window != DIRECT_INTERPRETATION:
            return True
    return False


def comparator_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    policy = summary.get("clean_comparator_policy")
    if not isinstance(policy, dict):
        return [
            prereg.blocked_item(
                "summary.clean_comparator_policy",
                "clean_comparator_policy_not_object",
                "clean comparator policy must be object",
            )
        ]
    blockers: list[dict[str, Any]] = []
    if policy.get("direct_llm_diagnostic_only") is not True:
        blockers.append(
            prereg.blocked_item(
                "summary.clean_comparator_policy.direct_llm_diagnostic_only",
                "direct_diagnostic_only_not_true",
                "direct control must be diagnostic only",
            )
        )
    if policy.get("required_non_direct_comparator") is not True:
        blockers.append(
            prereg.blocked_item(
                "summary.clean_comparator_policy.required_non_direct_comparator",
                "required_non_direct_comparator_not_true",
                "non-direct comparator is required",
            )
        )
    selected = policy.get("selected_clean_references")
    if not isinstance(selected, list) or not selected:
        blockers.append(
            prereg.blocked_item(
                "summary.clean_comparator_policy.selected_clean_references",
                "non_direct_clean_comparator_missing",
                "selected clean references must include a non-direct comparator",
            )
        )
    else:
        selected_set = {str(item) for item in selected}
        if selected_set == {DIRECT_INTERPRETATION}:
            blockers.append(
                prereg.blocked_item(
                    "summary.clean_comparator_policy.selected_clean_references",
                    "only_clean_comparator_is_parametric_control",
                    "direct_llm cannot be the only clean comparator",
                )
            )
        if DIRECT_INTERPRETATION in selected_set:
            blockers.append(
                prereg.blocked_item(
                    "summary.clean_comparator_policy.selected_clean_references",
                    "direct_llm_selected_as_clean_comparator",
                    "direct_llm cannot be selected as a clean comparator",
                )
            )
        if not selected_set.intersection(CLEAN_COMPARATORS):
            blockers.append(
                prereg.blocked_item(
                    "summary.clean_comparator_policy.selected_clean_references",
                    "non_direct_clean_comparator_missing",
                    "selected clean references need a preregistered non-direct comparator",
                )
            )
    return blockers


def bounded_verdict_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    status = str(summary.get("rubric_anchored_reasoning_quality_verdict_status") or "")
    effect_summary = summary.get("effect_summary")
    bounded_claim_requested = status == STATUS_BOUNDED_VERDICT
    if isinstance(effect_summary, dict):
        bounded_claim_requested = bounded_claim_requested or effect_summary.get("status") == STATUS_BOUNDED_VERDICT
        bounded_claim_requested = bounded_claim_requested or effect_summary.get("emitted") is True
        bounded_claim_requested = bounded_claim_requested or effect_summary.get("values") is not None
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path) or _conditional_template_path(path):
            continue
        for match in BOUNDED_VERDICT_TEXT_RE.finditer(text):
            if not _is_negated(text, match.start()):
                bounded_claim_requested = True
                blockers.append(
                    prereg.blocked_item(
                        path,
                        "bounded_verdict_wording_without_preconditions",
                        "bounded verdict wording is not allowed in current v3.8U conclusion fields",
                    )
                )
    preconditions = summary.get("bounded_verdict_preconditions")
    preconditions_ready = isinstance(preconditions, dict) and all(preconditions.get(key) is True for key in preconditions)
    if bounded_claim_requested and not preconditions_ready:
        blockers.append(
            prereg.blocked_item(
                "summary.bounded_verdict_preconditions",
                "bounded_verdict_preconditions_not_met",
                "bounded verdict requires provider-scored evidence, usage metadata, effective-N, "
                "scorer reliability, cluster, comparator, raw, and claim gates",
            )
        )
        if not isinstance(preconditions, dict) or preconditions.get("provider_scored_evidence_ready") is not True:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_verdict_preconditions.provider_scored_evidence_ready",
                    "provider_scored_evidence_missing_for_bounded_verdict",
                    "bounded verdict requires provider-scored evidence",
                )
            )
        if not isinstance(preconditions, dict) or preconditions.get("usage_metadata_available") is not True:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_verdict_preconditions.usage_metadata_available",
                    "usage_metadata_missing_for_bounded_verdict",
                    "bounded verdict requires usage metadata",
                )
            )
        if not isinstance(preconditions, dict) or preconditions.get("effective_n_ready") is not True:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_verdict_preconditions.effective_n_ready",
                    "effective_n_missing_for_bounded_verdict",
                    "bounded verdict requires effective-N readiness",
                )
            )
        if not isinstance(preconditions, dict) or preconditions.get("scorer_reliability_ready") is not True:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_verdict_preconditions.scorer_reliability_ready",
                    "scorer_reliability_missing_for_bounded_verdict",
                    "bounded verdict requires scorer reliability",
                )
            )
        if (
            not isinstance(preconditions, dict)
            or preconditions.get("clustered_statistical_eligibility_ready") is not True
        ):
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_verdict_preconditions.clustered_statistical_eligibility_ready",
                    "clustered_statistical_eligibility_missing_for_bounded_verdict",
                    "bounded verdict requires clustered statistical eligibility",
                )
            )
        if not isinstance(preconditions, dict) or preconditions.get("claim_boundary_fan_in_ready") is not True:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_verdict_preconditions.claim_boundary_fan_in_ready",
                    "claim_boundary_fan_in_missing_for_bounded_verdict",
                    "bounded verdict requires claim-boundary fan-in",
                )
            )
    return blockers


def claim_boundary_flag_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    flags = summary.get("claim_boundary_flags")
    if not isinstance(flags, dict):
        return [
            prereg.blocked_item(
                "summary.claim_boundary_flags",
                "claim_boundary_flags_not_object",
                "claim boundary flags must be object",
            )
        ]
    blockers: list[dict[str, Any]] = []
    for flag, ready in flags.items():
        if ready is not True:
            blockers.append(
                prereg.blocked_item(
                    f"summary.claim_boundary_flags.{flag}",
                    f"{flag}_false",
                    "v3.8U claim-boundary flags must be true for readiness",
                )
            )
    return blockers


def path_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for key_hint, candidate in prereg.recursive_paths(summary):
        if candidate == "/tmp" or candidate.startswith("/tmp/"):
            continue
        if prereg.claim_scan.forbidden_path(candidate):
            blockers.append(
                prereg.blocked_item(
                    candidate,
                    "forbidden_artifact_reference",
                    "forbidden/raw artifact path reference",
                )
            )
        elif key_hint.startswith("raw") or "transcript" in key_hint:
            if not prereg.under_tmp(candidate):
                blockers.append(
                    prereg.blocked_item(
                        candidate,
                        "raw_reference_not_tmp",
                        "raw-like or transcript paths must stay under /tmp",
                    )
                )
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path) or _conditional_template_path(path):
            continue
        for match in RAW_CONTENT_RE.finditer(text):
            if not _is_negated(text, match.start()):
                blockers.append(
                    prereg.blocked_item(
                        path,
                        "repo_raw_or_full_transcript_reference",
                        "repo-facing fields cannot contain raw output or full transcript text",
                    )
                )
    return blockers


def claim_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if _metadata_list_path(path) or _conditional_template_path(path):
            continue
        for match in CLAIM_BOUNDARY_RE.finditer(text):
            if not _is_negated(text, match.start()):
                blockers.append(
                    prereg.blocked_item(
                        path,
                        "claim_boundary_forbidden_wording",
                        "claim text exceeds v3.8U local readiness boundary",
                    )
                )
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
            ".status_normalization",
            ".run_root",
            ".summary_path",
            ".manifest_path",
            ".raw_paths",
            ".repo_raw_artifacts",
        )
    )


def _conditional_template_path(path: str) -> bool:
    return (
        ".conclusion_templates.future_provider_authorized_scored_run" in path
        or ".conclusion_templates.bounded_rubric_anchored_reasoning_quality_conclusion" in path
        or ".conclusion_templates.actual_30d_never_from_this_gate" in path
        or ".conclusion_templates.provider_scored_inconclusive_if_gates_fail" in path
    )


def _is_negated(text: str, position: int) -> bool:
    if prereg.claim_scan.is_negated(text, position):
        return True
    lowered = text.lower()
    clause_start = 0
    for separator in (".", ";", "\n", "。", "；"):
        idx = lowered.rfind(separator, 0, position)
        if idx >= 0:
            clause_start = max(clause_start, idx + len(separator))
    for separator in (" but ", " however ", " yet ", "但", "但是", "然而"):
        idx = lowered.rfind(separator, 0, position)
        if idx >= 0:
            clause_start = max(clause_start, idx + len(separator))
    prefix = lowered[clause_start:position]
    return bool(
        re.search(
            r"\b(?:not|no|never|without|false|forbidden|blocked|remain(?:s)? not|"
            r"not ready|not allowed|cannot|must not|do not)\b",
            prefix,
        )
        or re.search(r"(?:不构成|不得|不能|不可|尚未|仍为|永不|不是|非|禁止)", prefix)
    )


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(schema_blockers(summary))
    blockers.extend(runtime_blockers(summary))
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(comparator_blockers(summary))
    blockers.extend(claim_boundary_flag_blockers(summary))
    blockers.extend(bounded_verdict_blockers(summary))
    blockers.extend(path_blockers(summary))
    if prereg.contains_secret(summary):
        blockers.append(
            prereg.blocked_item("summary", "secret_material_detected", "summary contains secret-like material")
        )
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    has_blockers = bool(blockers)
    summary["conclusion_template_ready"] = not has_blockers
    summary["claim_boundary_gate_ready"] = not has_blockers
    summary["schema_status"] = "blocked" if any(_is_schema_rule(item) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = (
        "blocked"
        if any(
            _rule_has(item, ("runtime", "provider", "codex", "formal", "actual_30d", "calls", "token"))
            for item in blockers
        )
        else "clean"
    )
    summary["artifact_boundary_status"] = (
        "blocked"
        if any(_rule_has(item, ("forbidden_artifact", "repo_raw", "transcript", "secret")) for item in blockers)
        else "clean"
    )
    summary["raw_boundary_status"] = (
        "blocked"
        if any(_rule_has(item, ("raw_reference", "raw_output_boundary")) for item in blockers)
        else "clean"
    )
    summary["claim_boundary_status"] = (
        "blocked"
        if any(
            _rule_has(
                item,
                (
                    "claim_boundary",
                    "bounded_verdict",
                    "public",
                    "market",
                    "trading",
                    "investment",
                ),
            )
            for item in blockers
        )
        else "clean"
    )
    summary[DIRECT_PREFIX + "_boundary_status"] = (
        "blocked"
        if any(_rule_has(item, (DIRECT_PREFIX, "direct_control", "direct_diagnostic")) for item in blockers)
        else "clean"
    )
    summary["comparator_boundary_status"] = (
        "blocked"
        if any(_rule_has(item, ("comparator", "non_direct_clean", "parametric_control")) for item in blockers)
        else "clean"
    )
    summary["bounded_verdict_boundary_status"] = (
        "blocked" if any(_rule_has(item, ("bounded_verdict", "provider_scored", "usage_metadata")) for item in blockers) else "clean"
    )


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def _is_schema_rule(item: dict[str, Any]) -> bool:
    rule = str(item.get("rule_id") or "")
    schema_tokens = (
        "summary_schema",
        "schema_id",
        "script_version",
        "gate_id_invalid",
        "created_at_utc_invalid",
        "summary_missing_field",
        "_invalid",
        "_missing",
        "not_object",
        "evidence_layer",
        "conclusion_template",
        "required_non_claim_missing",
        "rubric_sha256_missing_or_invalid",
        "rubric_lock_status_invalid",
        "rubric_version_mismatch",
        "invalid_controller_pack_status",
    )
    return any(token in rule for token in schema_tokens)


def choose_status(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any("actual_30d" in reason or "v3_7" in reason or "provider_or_backend" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("codex" in reason or "formal" in reason or "calls" in reason or "token" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("comparator" in reason or "parametric_control" in reason or "non_direct_clean" in reason for reason in reasons):
        return STATUS_BLOCKED_COMPARATOR_BOUNDARY
    if any(DIRECT_PREFIX in reason or "direct_control" in reason or "direct_diagnostic" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("raw_reference" in reason or "raw_output_boundary" in reason for reason in reasons):
        return STATUS_BLOCKED_RAW_BOUNDARY
    if any("forbidden_artifact" in reason or "repo_raw" in reason or "transcript" in reason or "secret" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any(
        "claim_boundary" in reason
        or "bounded_verdict" in reason
        or "provider_scored" in reason
        or "usage_metadata_missing_for_bounded_verdict" in reason
        or "public" in reason
        for reason in reasons
    ):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if any("scorer_reliability" in reason for reason in reasons):
        return STATUS_BLOCKED_SCORER_RELIABILITY
    if any("effective_n" in reason for reason in reasons):
        return STATUS_BLOCKED_EFFECTIVE_N
    if any("eligibility" in reason for reason in reasons):
        return STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    if any(_is_schema_rule(item) for item in blockers):
        return STATUS_BLOCKED_SCHEMA
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
        return {}, [prereg.blocked_item(path, "fixture_not_object", "summary fixture must be JSON object")]
    return payload, []


def fixture_identity_blockers(
    payload: dict[str, Any],
    *,
    config: ClaimBoundaryGateConfig,
    run_root: Path,
) -> list[dict[str, Any]]:
    expected = {
        "gate_id": config.gate_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(
                prereg.blocked_item(
                    f"summary.{key}",
                    f"{key}_identity_mismatch",
                    f"{key} must come from CLI/config",
                )
            )
    return blockers


def restore_config_identity(
    summary: dict[str, Any],
    *,
    config: ClaimBoundaryGateConfig,
    run_root: Path,
) -> None:
    summary["gate_id"] = config.gate_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: ClaimBoundaryGateConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = dict(payload) if payload else base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["claim_boundary_gate_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_default_summary(config: ClaimBoundaryGateConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    status = choose_status(blockers)
    summary["rubric_anchored_reasoning_quality_verdict_status"] = status
    summary["claim_boundary_gate_status"] = status
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: ClaimBoundaryGateConfig) -> dict[str, Any]:
    run_root = config.output_dir / config.gate_id
    run_id_blockers = validate_run_id(config.gate_id)
    if run_id_blockers:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_SCHEMA)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = STATUS_BLOCKED_SCHEMA
        summary["claim_boundary_gate_status"] = STATUS_BLOCKED_SCHEMA
        finalize_blockers(summary, run_id_blockers)
        return summary
    if not prereg.under_tmp(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [prereg.blocked_item(config.output_dir, "output_dir_not_tmp", "output_dir must be under /tmp")]
        status = choose_status(blockers)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = status
        summary["claim_boundary_gate_status"] = status
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [prereg.blocked_item(run_root, "run_id_exists", "gate_id already exists; use --allow-overwrite")]
        status = choose_status(blockers)
        summary["rubric_anchored_reasoning_quality_verdict_status"] = status
        summary["claim_boundary_gate_status"] = status
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
    summary["claim_boundary_gate_sha256"] = gate_digest(summary)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "gate_id": summary.get("gate_id"),
        "rubric_anchored_reasoning_quality_verdict_status": summary.get(
            "rubric_anchored_reasoning_quality_verdict_status"
        ),
        "claim_boundary_gate_status": summary.get("claim_boundary_gate_status"),
        "conclusion_template_ready": summary.get("conclusion_template_ready"),
        "claim_boundary_gate_ready": summary.get("claim_boundary_gate_ready"),
        "summary_path": str(summary_path),
        "summary_sha256": prereg.sha256_file(summary_path),
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": summary.get("rubric_sha256"),
        "cognitive_lift_superiority_verdict_status": summary.get(
            "cognitive_lift_superiority_verdict_status"
        ),
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
    parser.add_argument("--gate-id", default=default_run_id())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_8u_rubric_reasoning_claim_boundary_gate"),
    )
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ClaimBoundaryGateConfig:
    return ClaimBoundaryGateConfig(
        gate_id=str(args.gate_id),
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
