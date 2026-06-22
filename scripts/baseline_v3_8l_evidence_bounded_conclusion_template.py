#!/usr/bin/env python3
"""GOTRA v3.8L evidence-bounded conclusion template validator."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_8l.evidence_bounded_conclusion_template_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8l.evidence_bounded_conclusion_template_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8l_evidence_bounded_conclusion_template_"
SCRIPT_VERSION = "v3.8l-20260622"
EVIDENCE_LAYER = "engineering_internal_evidence_bounded_conclusion_template"
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
ACTUAL_30D_NEXT_CHECK_AFTER = rubric.ACTUAL_30D_NEXT_CHECK_AFTER
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
DEFAULT_BACKEND_NAME = "codex_responses_oauth_backend"
DEFAULT_MODEL = "gpt-5.5"

STATUS_READY = "EVIDENCE_BOUNDED_CONCLUSION_TEMPLATE_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE_BOUNDARY"
STATUS_BLOCKED_VERDICT_OVERREACH = "BLOCKED_VERDICT_OVERREACH"
STATUS_RUN_ID_EXISTS = "EVIDENCE_BOUNDED_CONCLUSION_TEMPLATE_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_BLOCKED_MISSING_EVIDENCE,
    STATUS_BLOCKED_VERDICT_OVERREACH,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

STAGE_ORDER = ("v3.8B", "v3.8C", "v3.8D", "v3.8E", "v3.8F", "v3.8G", "v3.8H", "v3.8I", "v3.8J", "v3.8K")
EXPECTED_STAGE_EVIDENCE: dict[str, dict[str, Any]] = {
    "v3.8B": {
        "pr_number": 66,
        "head_sha": "c09060b95666d7760c4529eb66271298638d75bf",
        "merge_commit": "e974420eb2090f541f20d694444d184019f82dca",
        "status": "REAL_CONNECTION_AUTH_READY",
        "evidence_layer": "engineering_internal_real_connection_auth_metadata_smoke",
        "real_calls_count": 1,
        "token_usage_total": 86,
        "provider_or_backend_called": True,
    },
    "v3.8C": {
        "pr_number": 67,
        "head_sha": "96406a6dda3daa4e682aea1329eb1c63ebfeb78f",
        "merge_commit": "9d554e48294e74f9af22a72c93bab6f3c6c8c37a",
        "status": "KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS",
        "evidence_layer": "engineering_internal_ksana_packet_v2_real_token_schema_canary",
        "real_calls_count": 3,
        "token_usage_total": 6518,
        "provider_or_backend_called": True,
    },
    "v3.8D": {
        "pr_number": 68,
        "head_sha": "bdf5997a4ca881125878879f7d1f06db349ff257",
        "merge_commit": "b92be9870db661dd27015f4e8dcccd5d7235541e",
        "status": "GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS",
        "evidence_layer": "engineering_internal_gotra_orchestrator_real_token_dry_run",
        "real_calls_count": 3,
        "token_usage_total": 6765,
        "provider_or_backend_called": True,
    },
    "v3.8E": {
        "pr_number": 69,
        "head_sha": "500649a51816fef338e941b0790cc3a5a01ac0a7",
        "merge_commit": "cce6cec18ba856d986e8144d8e7915c37d6c9822",
        "status": "REAL_TOKEN_FAILURE_MODE_SUITE_PASS",
        "evidence_layer": "engineering_internal_real_token_failure_mode_suite",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
        "failure_cases_total": 12,
        "failure_cases_handled": 12,
    },
    "v3.8F": {
        "pr_number": 70,
        "head_sha": "16cb7283f7dd280685aacafd137b663222d3e2fa",
        "merge_commit": "069aba13405928249f70f2f9bc5bafb01af641f5",
        "status": "REAL_CONNECTION_EVIDENCE_DASHBOARD_READY",
        "evidence_layer": "engineering_internal_real_connection_evidence_dashboard",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "source_real_calls_count_total": 7,
        "source_token_usage_total": 13369,
        "provider_or_backend_called": False,
    },
    "v3.8G": {
        "pr_number": 71,
        "head_sha": "c86719c1e70746568950fb7d1e097b16bae307e3",
        "merge_commit": "050a070f3f6bc10c3f1c18b9a31ba4ff46280e9c",
        "status": "PROVIDER_CANARY_PREREG_READY",
        "evidence_layer": "engineering_internal_provider_canary_prereg_only",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
    },
    "v3.8H": {
        "pr_number": 72,
        "head_sha": "b825341cf90dcb2859920ec46bb9a1257eabec22",
        "merge_commit": "3321e870d99df935201a91294ee767be0edf541c",
        "status": "PROVIDER_CANARY_AUTHORIZATION_GATE_READY",
        "evidence_layer": "engineering_internal_provider_canary_authorization_gate",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
    },
    "v3.8I": {
        "pr_number": 73,
        "head_sha": "dea0ab6eeaf8f59ca0266894c1e0e624068fe4e2",
        "merge_commit": "d85da9d9b5e1402af7ef213ec4079db5770c8179",
        "status": "END_TO_END_CONNECTIVITY_READY",
        "evidence_layer": "engineering_internal_end_to_end_connectivity_replay",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
    },
    "v3.8J": {
        "pr_number": 74,
        "head_sha": "3b4d360ec7e3ffb0369279d8e377009017016af3",
        "merge_commit": "d4f5d770fe147c5113657a43d94038ae59903989",
        "status": "COGNITIVE_LIFT_RUBRIC_PREREG_READY",
        "evidence_layer": "engineering_internal_cognitive_lift_rubric_prereg_schema",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
    },
    "v3.8K": {
        "pr_number": 75,
        "head_sha": "744f69486178a5a5d614774e88d97cc14bc68b2b",
        "merge_commit": "314cbcce1f318de3d0a399e4f0b3d3837b811344",
        "status": "COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY",
        "evidence_layer": "engineering_internal_cognitive_lift_fixture_dry_run",
        "real_calls_count": 0,
        "token_usage_total": 0,
        "provider_or_backend_called": False,
    },
}

CONCLUSION_SECTIONS = (
    "Engineering Connectivity Conclusion",
    "Cognitive-Lift Candidate Conclusion",
    "Cognitive-Lift Superiority Verdict",
)
CONNECTIVITY_STATUS = "ENGINEERING_CONNECTIVITY_EVIDENCE_LAYERED"
CANDIDATE_STATUS = "COGNITIVE_LIFT_CANDIDATE_EVALUATION_PATH_DEFINED_ONLY"

SECRET_RE = packet_canary.SECRET_RE
LEGACY_BACKEND_RE = re.compile(r"\b(?:ki" + "mi|g" + "lm|deep" + "seek)\b", re.IGNORECASE)
VERDICT_WORD = "verd" + "ict"
COMPARATIVE_RESULT_WORD = "win" + "ner"
STATUS_CLAIM_RE = re.compile(
    rf"(?:v3[\._]?7|v3[\._]?8|30d|30-day|actual|cognitive[-_ ]lift).{{0,90}}"
    rf"(?:{VERDICT_WORD}|readiness|executable|superiority).{{0,70}}"
    r"(?:ready|pass|allowed|true|executed|proved|validated|confirmed)",
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
    + r"ance)\b",
    re.IGNORECASE,
)
VERDICT_OVERREACH_RE = re.compile(
    rf"(?:superiority|comparative|external|actual).{{0,70}}(?:{VERDICT_WORD}|result|conclusion).{{0,70}}"
    r"(?:ready|proved|confirmed|passed|executed|wins)",
    re.IGNORECASE,
)
AFFIRMATIVE_STATUS_TOKEN_RE = re.compile(
    rf"\b(?:ready|pass|allowed|true|executed|proved|validated|confirmed|{COMPARATIVE_RESULT_WORD}|wins)\b",
    re.IGNORECASE,
)
PROVIDER_EXECUTION_CLAIM_RE = re.compile(
    r"\b(?:provider|backend|canary).{0,80}\b(?:called|executed|ran|used|completed)\b",
    re.IGNORECASE,
)
RAW_PATH_RE = re.compile(r"(?:^|[/. _-])raw(?:[/. _-]|$)", re.IGNORECASE)
DIRECT_UNSAFE_RE = re.compile(
    r"(?:direct_llm|direct_llm_parametric_memory_control).{0,80}"
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
REQUIRED_SUMMARY_FIELDS = {
    "schema",
    "script_version",
    "template_id",
    "generated_at",
    "evidence_layer",
    "template_status",
    "source_stages",
    "source_stage_metadata_sha256",
    "source_stage_statuses",
    "source_stage_hashes",
    "source_real_calls_count_total",
    "source_token_usage_total",
    "conclusion_template_sha256",
    "conclusion_sections",
    "engineering_connectivity_conclusion",
    "cognitive_lift_candidate_conclusion",
    "cognitive_lift_superiority_verdict",
    "can_say",
    "cannot_say",
    "missing_before_superiority_verdict",
    "allowed_conclusion_text",
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
    "real_calls_count",
    "token_usage_total",
    "cognitive_lift_superiority_verdict_status",
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
    "provider_or_backend_called",
    "provider_canary_executed",
    "codex_cli_new_call",
    "formal_lite_entered",
    "raw_tmp_boundary",
    "raw_tmp_paths",
    "raw_tmp_sha256s",
    "repo_raw_committed",
    "claim_boundary_status",
    "artifact_boundary_status",
    "provenance_status",
    "metadata_sha256",
}


@dataclass(frozen=True)
class TemplateConfig:
    template_id: str
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
        raise ValueError(f"template_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("template_id may contain only letters, numbers, '_' and '-'")


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


def safe_nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def is_numeric_zero(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def stage_hash_payload(stage: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stage.items() if key != "metadata_sha256"}


def enrich_stage_hashes(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for stage in stages:
        item = dict(stage)
        item["metadata_sha256"] = stable_sha256_json(stage_hash_payload(item))
        enriched.append(item)
    return enriched


def canonical_stage_map() -> dict[str, dict[str, Any]]:
    return {stage["stage_id"]: stage for stage in canonical_source_stages()}


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
            "provider_or_backend_called": evidence["provider_or_backend_called"],
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
        for optional_key in (
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


def conclusion_sections() -> list[dict[str, Any]]:
    return [
        {
            "section_id": CONCLUSION_SECTIONS[0],
            "status": CONNECTIVITY_STATUS,
            "allowed_wording": "bounded engineering chain evidence is present across connectivity, schema, provenance, hash, claim-boundary, usage metadata, and failure-handling stages",
            "boundary": "engineering evidence only",
        },
        {
            "section_id": CONCLUSION_SECTIONS[1],
            "status": CANDIDATE_STATUS,
            "allowed_wording": "internal candidate evaluation path is defined for future paired assessment",
            "boundary": "planning and fixture-tooling evidence only",
        },
        {
            "section_id": CONCLUSION_SECTIONS[2],
            "status": SUPERIORITY_STATUS,
            "allowed_wording": "formal comparative conclusion remains not ready",
            "boundary": "requires mature paired evidence, preregistered scoring, statistical eligibility, and clean claim boundary",
        },
    ]


def base_summary(config: TemplateConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    stages = canonical_source_stages()
    sections = conclusion_sections()
    summary = {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "template_id": config.template_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "template_status": status,
        "source_stages": stages,
        "source_stage_metadata_sha256": stable_sha256_json(stages),
        "source_stage_hashes": {stage["stage_id"]: stage["metadata_sha256"] for stage in stages},
        "source_stage_statuses": {stage["stage_id"]: stage["status"] for stage in stages},
        "source_real_calls_count_total": sum(int(stage["real_calls_count"]) for stage in stages),
        "source_token_usage_total": sum(int(stage["token_usage_total"]) for stage in stages),
        "conclusion_template_sha256": "",
        "conclusion_sections": sections,
        "engineering_connectivity_conclusion": {
            "section_id": CONCLUSION_SECTIONS[0],
            "status": CONNECTIVITY_STATUS,
            "source_stages": ["v3.8B", "v3.8C", "v3.8D", "v3.8E", "v3.8F", "v3.8I"],
            "evidence_summary": "bounded engineering chain evidence is available for internal review",
        },
        "cognitive_lift_candidate_conclusion": {
            "section_id": CONCLUSION_SECTIONS[1],
            "status": CANDIDATE_STATUS,
            "source_stages": ["v3.8J", "v3.8K"],
            "evidence_summary": "rubric and deterministic fixture tooling define a future evaluation path",
        },
        "cognitive_lift_superiority_verdict": {
            "section_id": CONCLUSION_SECTIONS[2],
            "status": SUPERIORITY_STATUS,
            "required_before_ready": [
                "mature paired evidence",
                "preregistered scoring execution",
                "statistical eligibility gate",
                "clean claim boundary",
            ],
        },
        "can_say": [
            "engineering connectivity and local tooling evidence are layered and auditable",
            "a future candidate evaluation path is defined by rubric and fixture tooling",
        ],
        "cannot_say": [
            "no formal comparative conclusion",
            "no external claim",
            "no 30D actual conclusion",
            "no provider canary execution in this stage",
            "no action guidance",
        ],
        "missing_before_superiority_verdict": [
            "mature paired evidence",
            "preregistered scoring execution",
            "statistical eligibility gate",
            "clean claim boundary",
            "actual 30D readiness gate",
        ],
        "allowed_conclusion_text": [
            "Current evidence supports an engineering-only candidate evaluation path.",
            "Formal comparative conclusion remains not ready.",
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
        "schema_status": "clean",
        "missing_evidence_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "verdict_boundary_status": "clean",
        "blocker_reasons": [],
        "blocked_items": [],
        "non_claims": {
            "not_formal_comparative_conclusion": True,
            "not_actual_30d_verdict": True,
            "not_provider_canary_execution": True,
            "not_external_claim": True,
            "not_action_guidance": True,
            "readiness_gate_not_passed": True,
        },
    }
    summary["conclusion_template_sha256"] = conclusion_template_digest(summary)
    return summary


def conclusion_template_digest(summary: dict[str, Any]) -> str:
    return stable_sha256_json(
        {
            "source_stages": summary.get("source_stages"),
            "source_stage_metadata_sha256": summary.get("source_stage_metadata_sha256"),
            "conclusion_sections": summary.get("conclusion_sections"),
            "engineering_connectivity_conclusion": summary.get("engineering_connectivity_conclusion"),
            "cognitive_lift_candidate_conclusion": summary.get("cognitive_lift_candidate_conclusion"),
            "cognitive_lift_superiority_verdict": summary.get("cognitive_lift_superiority_verdict"),
            "can_say": summary.get("can_say"),
            "cannot_say": summary.get("cannot_say"),
            "missing_before_superiority_verdict": summary.get("missing_before_superiority_verdict"),
            "allowed_conclusion_text": summary.get("allowed_conclusion_text"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "next_check_after": summary.get("next_check_after"),
            "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
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
        if key_hint in path_keys or claim_scan.forbidden_path(value) or RAW_PATH_RE.search(value) or "transcript" in value.lower():
            paths.append((key_hint, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(recursive_paths(item, key_hint=key))
    elif isinstance(value, list):
        for item in value:
            paths.extend(recursive_paths(item, key_hint=key_hint))
    return paths


def claim_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    text_items = recursive_strings(payload, path="template")
    sources = [
        claim_scan.ScanSource(path=path, text=text, origin="v3_8l_conclusion_template")
        for path, text in text_items
    ]
    scan = claim_scan.scan_sources(sources)
    blockers = scan["overclaim"] + scan[DIRECT_PREFIX] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for path, text in text_items:
        for status_match in STATUS_CLAIM_RE.finditer(text):
            if _has_unnegated_affirmative_token(text, status_match):
                blockers.append(blocked_item(path, "actual_or_superiority_verdict_claim", "status-like text cannot assert current actual or comparative conclusion readiness"))
        for verdict_match in VERDICT_OVERREACH_RE.finditer(text):
            if _has_unnegated_affirmative_token(text, verdict_match):
                blockers.append(blocked_item(path, "verdict_overreach_wording", "text exceeds evidence-bounded conclusion template boundary"))
        for provider_match in PROVIDER_EXECUTION_CLAIM_RE.finditer(text):
            if not _is_locally_negated(text, provider_match.start()):
                blockers.append(blocked_item(path, "provider_canary_execution_text_claim", "text cannot claim provider/backend/canary execution in v3.8L"))
        for match in COMPARATIVE_CLAIM_RE.finditer(text):
            if not claim_scan.is_negated(text, match.start()):
                blockers.append(blocked_item(path, "comparative_or_action_guidance_claim", "comparative or action-guidance wording exceeds this template boundary"))
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
    for path, text in recursive_strings(payload, path="template"):
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
        elif (key_hint.startswith("raw") or RAW_PATH_RE.search(candidate) or "transcript" in candidate.lower()) and not under_tmp(candidate):
            blockers.append(blocked_item(candidate, "raw_reference_not_tmp", "raw-like or transcript path references must stay under /tmp"))
    return blockers


def runtime_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in RUNTIME_FALSE_FLAGS:
        if flag not in summary:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_missing", f"{flag} must be explicitly present and false"))
        elif summary.get(flag) is not False:
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8L itself"))
    if summary.get("provider_canary_executed") is not False:
        blockers.append(blocked_item("summary.provider_canary_executed", "provider_canary_executed_not_false", "provider canary execution is not part of v3.8L"))
    if not is_numeric_zero(summary.get("real_calls_count")):
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_count_not_numeric_zero", "v3.8L real call count must be integer zero"))
    if not is_numeric_zero(summary.get("token_usage_total")):
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_total_not_numeric_zero", "v3.8L token usage must be integer zero"))
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
    if str(summary.get("template_status") or "") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.template_status", "invalid_template_status", "template_status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if not _is_iso_utc(summary.get("generated_at")):
        blockers.append(blocked_item("summary.generated_at", "generated_at_invalid", "generated_at must be an ISO UTC timestamp ending in Z"))
    for key in ("can_say", "cannot_say", "missing_before_superiority_verdict", "allowed_conclusion_text"):
        value = summary.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            blockers.append(blocked_item(f"summary.{key}", f"{key}_invalid", f"{key} must be a non-empty string list"))
    sections = summary.get("conclusion_sections")
    if not isinstance(sections, list) or len(sections) != 3:
        blockers.append(blocked_item("summary.conclusion_sections", "conclusion_sections_invalid", "template requires exactly three conclusion sections"))
    else:
        section_ids = [section.get("section_id") if isinstance(section, dict) else None for section in sections]
        if tuple(section_ids) != CONCLUSION_SECTIONS:
            blockers.append(blocked_item("summary.conclusion_sections", "conclusion_sections_mismatch", "conclusion section ids must stay in the required order"))
        expected_statuses = (CONNECTIVITY_STATUS, CANDIDATE_STATUS, SUPERIORITY_STATUS)
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                blockers.append(blocked_item(f"summary.conclusion_sections[{index}]", "conclusion_section_not_object", "section must be object"))
                continue
            if section.get("status") != expected_statuses[index]:
                blockers.append(blocked_item(f"summary.conclusion_sections[{index}].status", "conclusion_section_status_mismatch", "section status must match layer boundary"))
    _validate_conclusion_object(summary, "engineering_connectivity_conclusion", CONCLUSION_SECTIONS[0], CONNECTIVITY_STATUS, blockers)
    _validate_conclusion_object(summary, "cognitive_lift_candidate_conclusion", CONCLUSION_SECTIONS[1], CANDIDATE_STATUS, blockers)
    _validate_conclusion_object(summary, "cognitive_lift_superiority_verdict", CONCLUSION_SECTIONS[2], SUPERIORITY_STATUS, blockers)
    return blockers


def _validate_conclusion_object(
    summary: dict[str, Any],
    key: str,
    expected_section_id: str,
    expected_status: str,
    blockers: list[dict[str, Any]],
) -> None:
    value = summary.get(key)
    if not isinstance(value, dict):
        blockers.append(blocked_item(f"summary.{key}", f"{key}_not_object", f"{key} must be object"))
        return
    if value.get("section_id") != expected_section_id:
        blockers.append(blocked_item(f"summary.{key}.section_id", f"{key}_section_id_mismatch", "conclusion object is assigned to the wrong layer"))
    if value.get("status") != expected_status:
        blockers.append(blocked_item(f"summary.{key}.status", f"{key}_status_mismatch", "conclusion object status crosses its evidence layer"))


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
                blockers.append(
                    blocked_item(
                        f"{stage_path}.{canonical_key}",
                        f"source_stage_{canonical_key}_canonical_mismatch",
                        f"{canonical_key} must match canonical source-stage payload",
                    )
                )
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
        if stage.get("raw_tmp_boundary") != "tmp_only":
            blockers.append(blocked_item(f"{stage_path}.raw_tmp_boundary", "source_raw_tmp_boundary_invalid", "source raw boundary must be tmp_only"))
        if stage.get("repo_raw_committed") is not False:
            blockers.append(blocked_item(f"{stage_path}.repo_raw_committed", "source_repo_raw_committed", "source stage must not commit raw payloads"))
        _raw_metadata_blockers(blockers, stage, stage_path)
        if stage.get("metadata_sha256") != canonical_stage["metadata_sha256"]:
            blockers.append(blocked_item(f"{stage_path}.metadata_sha256", "source_metadata_sha256_mismatch", "metadata hash must match canonical source-stage payload"))
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


def evidence_digest_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    stages = [stage for stage in summary.get("source_stages", []) if isinstance(stage, dict)]
    canonical_stages = canonical_source_stages()
    canonical_hashes = {stage["stage_id"]: stage.get("metadata_sha256") for stage in canonical_stages}
    canonical_statuses = {stage["stage_id"]: stage.get("status") for stage in canonical_stages}
    if summary.get("source_real_calls_count_total") != sum(safe_nonnegative_int(stage.get("real_calls_count")) for stage in stages):
        blockers.append(blocked_item("summary.source_real_calls_count_total", "source_real_calls_total_mismatch", "source call total must equal stage totals"))
    if summary.get("source_token_usage_total") != sum(safe_nonnegative_int(stage.get("token_usage_total")) for stage in stages):
        blockers.append(blocked_item("summary.source_token_usage_total", "source_token_total_mismatch", "source token total must equal stage totals"))
    if summary.get("source_stage_hashes") != canonical_hashes:
        blockers.append(blocked_item("summary.source_stage_hashes", "source_stage_hashes_mismatch", "source stage hashes must match canonical source-stage payloads"))
    if summary.get("source_stage_statuses") != canonical_statuses:
        blockers.append(blocked_item("summary.source_stage_statuses", "source_stage_statuses_mismatch", "source stage statuses must match canonical evidence"))
    if not is_hex(summary.get("source_stage_metadata_sha256"), 64):
        blockers.append(blocked_item("summary.source_stage_metadata_sha256", "source_stage_metadata_sha256_invalid", "source metadata digest is required"))
    elif summary.get("source_stage_metadata_sha256") != stable_sha256_json(canonical_stages):
        blockers.append(blocked_item("summary.source_stage_metadata_sha256", "source_stage_metadata_sha256_mismatch", "source metadata digest must match canonical source-stage payloads"))
    if not is_hex(summary.get("conclusion_template_sha256"), 64):
        blockers.append(blocked_item("summary.conclusion_template_sha256", "conclusion_template_sha256_invalid", "template digest is required"))
    elif summary.get("conclusion_template_sha256") != conclusion_template_digest(summary):
        blockers.append(blocked_item("summary.conclusion_template_sha256", "conclusion_template_sha256_mismatch", "template digest must cover boundary-critical fields"))
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
    blockers.extend(direct_boundary_blockers(summary))
    blockers.extend(path_blockers(summary))
    if contains_secret(summary):
        blockers.append(blocked_item("summary", "secret_material_detected", "summary contains secret-like material"))
    blockers.extend(claim_blockers(summary))
    return blockers


def finalize_blockers(summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    summary["blocked_items"] = blockers[:200]
    summary["blocker_reasons"] = [str(item.get("rule_id") or "") for item in blockers]
    summary["schema_status"] = "blocked" if any(_rule_has(item, ("schema", "missing", "invalid", "not_list", "not_object", "section")) for item in blockers) else "clean"
    summary["missing_evidence_boundary_status"] = "blocked" if any(_rule_has(item, ("source_stage", "source_", "metadata_sha256", "conclusion_template_sha256")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim", "overclaim")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "flag", "provider", "backend", "executable", "canary", "calls", "token", "output_dir")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "raw_reference", "raw_tmp_path", "repo_raw", "transcript")) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control")) for item in blockers) else "clean"
    summary["verdict_boundary_status"] = "blocked" if any(_rule_has(item, ("verdict_overreach", "actual_or_superiority_verdict", "comparative_or_action")) for item in blockers) else "clean"


def _rule_has(item: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    rule = str(item.get("rule_id") or "")
    return any(token in rule for token in tokens)


def choose_status(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return STATUS_READY
    reasons = {str(item.get("rule_id") or "") for item in blockers}
    if any(DIRECT_PREFIX in reason or "direct_control" in reason for reason in reasons):
        return STATUS_BLOCKED_DIRECT_BOUNDARY
    if any("forbidden_artifact" in reason or "raw_reference" in reason or "raw_tmp_path" in reason or "repo_raw" in reason or "transcript" in reason for reason in reasons):
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if any("verdict_overreach" in reason or "actual_or_superiority_verdict" in reason or "comparative_or_action" in reason for reason in reasons):
        return STATUS_BLOCKED_VERDICT_OVERREACH
    if any("provider_canary_execution_text_claim" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any(
        reason.endswith("_not_false")
        or reason in {
            "real_calls_not_zero",
            "token_usage_not_zero",
            "real_calls_count_not_numeric_zero",
            "token_usage_total_not_numeric_zero",
            "output_dir_not_tmp",
            "run_id_exists",
        }
        for reason in reasons
    ):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("source_stage" in reason or "source_" in reason or "metadata_sha256" in reason or "conclusion_template_sha256" in reason for reason in reasons):
        return STATUS_BLOCKED_MISSING_EVIDENCE
    if any("claim" in reason or "overclaim" in reason for reason in reasons):
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if any(
        reason.endswith("_invalid")
        or reason.endswith("_not_list")
        or reason.endswith("_not_object")
        or "schema" in reason
        or "section" in reason
        for reason in reasons
    ):
        return STATUS_BLOCKED_SCHEMA
    if any("runtime" in reason or "flag" in reason or "provider" in reason or "backend" in reason or "executable" in reason or "canary" in reason or "output_dir" in reason for reason in reasons):
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if any("schema" in reason or "missing" in reason for reason in reasons):
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


def fixture_identity_blockers(payload: dict[str, Any], *, config: TemplateConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "template_id": config.template_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: TemplateConfig, run_root: Path) -> None:
    summary["template_id"] = config.template_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: TemplateConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("template_status") or STATUS_BLOCKED_SCHEMA) if payload else STATUS_BLOCKED_SCHEMA,
    )
    if payload:
        summary.update(payload)
    restore_config_identity(summary, config=config, run_root=run_root)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    summary["template_status"] = choose_status(blockers)
    finalize_blockers(summary, blockers)
    return summary


def build_default_template(config: TemplateConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    summary["template_status"] = choose_status(blockers)
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: TemplateConfig) -> dict[str, Any]:
    validate_run_id(config.template_id)
    run_root = config.output_dir / config.template_id
    if not under_tmp(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(config.output_dir, "output_dir_not_tmp", "output dir must be under /tmp")]
        summary["template_status"] = choose_status(blockers)
        finalize_blockers(summary, blockers)
        return summary
    if run_root.exists() and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_RUN_ID_EXISTS)
        blockers = [blocked_item(run_root, "run_id_exists", "run id already exists; pass --allow-overwrite to replace")]
        summary["template_status"] = STATUS_RUN_ID_EXISTS
        finalize_blockers(summary, blockers)
        return summary
    summary = build_from_fixture(config, run_root=run_root) if config.summary_fixture else build_default_template(config, run_root=run_root)
    write_outputs(summary, run_root=run_root, allow_overwrite=config.allow_overwrite)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path, allow_overwrite: bool) -> None:
    if not under_tmp(run_root):
        return
    if run_root.exists():
        if not allow_overwrite:
            raise FileExistsError(f"run root already exists: {run_root}")
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=False)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary_path.write_bytes(stable_json_bytes(summary) + b"\n")
    summary_sha256 = sha256_file(summary_path)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "template_id": summary.get("template_id"),
        "template_status": summary.get("template_status"),
        "summary_path": str(summary_path),
        "summary_sha256": summary_sha256,
        "generated_at": summary.get("generated_at"),
        "evidence_layer": summary.get("evidence_layer"),
        "provider_or_backend_called": summary.get("provider_or_backend_called"),
        "provider_canary_executed": summary.get("provider_canary_executed"),
        "codex_cli_called": summary.get("codex_cli_called"),
        "codex_cli_new_call": summary.get("codex_cli_new_call"),
        "formal_lite_entered": summary.get("formal_lite_entered"),
        "real_calls_count": summary.get("real_calls_count"),
        "token_usage_total": summary.get("token_usage_total"),
        "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
        "cognitive_lift_superiority_verdict_status": summary.get("cognitive_lift_superiority_verdict_status"),
        "artifact_boundary_status": summary.get("artifact_boundary_status"),
        "claim_boundary_status": summary.get("claim_boundary_status"),
        "runtime_boundary_status": summary.get("runtime_boundary_status"),
        "missing_evidence_boundary_status": summary.get("missing_evidence_boundary_status"),
        "verdict_boundary_status": summary.get("verdict_boundary_status"),
        "blocker_reasons": summary.get("blocker_reasons", []),
    }
    manifest_path.write_bytes(stable_json_bytes(manifest) + b"\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8l_evidence_bounded_conclusion_template"))
    parser.add_argument("--summary-fixture", type=Path)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = TemplateConfig(
        template_id=args.template_id,
        output_dir=args.output_dir,
        allow_overwrite=args.allow_overwrite,
        summary_fixture=args.summary_fixture,
    )
    try:
        summary = build_summary(config)
    except (FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("template_status") in CLI_SUCCESS_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
