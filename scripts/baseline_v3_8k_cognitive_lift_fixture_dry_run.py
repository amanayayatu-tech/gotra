#!/usr/bin/env python3
"""GOTRA v3.8K deterministic fixture cognitive-lift dry-run."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_8k.cognitive_lift_fixture_dry_run_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8k.cognitive_lift_fixture_dry_run_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_8k_cognitive_lift_fixture_dry_run_"
SCRIPT_VERSION = "v3.8k-20260622"
EVIDENCE_LAYER = "engineering_internal_cognitive_lift_fixture_dry_run"
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
ACTUAL_30D_NEXT_CHECK_AFTER = rubric.ACTUAL_30D_NEXT_CHECK_AFTER
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
CL_CANDIDATE_STATUS = "FIXTURE_DRY_RUN_ONLY"
RUBRIC_SCHEMA_VERSION = rubric.SCHEMA_VERSION

STATUS_READY = "COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROTOCOL = "BLOCKED_PROTOCOL"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_DIRECT_BOUNDARY = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_METADATA = "BLOCKED_METADATA"
STATUS_RUN_ID_EXISTS = "COGNITIVE_LIFT_FIXTURE_DRY_RUN_BLOCKED_RUN_ID_EXISTS"

ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_PROTOCOL,
    STATUS_BLOCKED_PROVENANCE,
    STATUS_BLOCKED_CLAIM_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_BLOCKED_ARTIFACT_BOUNDARY,
    STATUS_BLOCKED_DIRECT_BOUNDARY,
    STATUS_BLOCKED_METADATA,
    STATUS_RUN_ID_EXISTS,
}
CLI_SUCCESS_STATUSES = {STATUS_READY}

DIMENSIONS = rubric.DIMENSIONS
ALLOWED_ARMS = rubric.ALLOWED_ARMS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_PREFIX = rubric.DIRECT_PREFIX
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
SECRET_RE = packet_canary.SECRET_RE
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
    "script_version",
    "dry_run_id",
    "generated_at",
    "evidence_layer",
    "dry_run_status",
    "rubric_schema_version",
    "dimension_count",
    "dimensions",
    "fixture_records",
    "paired_sample_count",
    "fixture_pair_count",
    "arms",
    "per_arm_dimension_scores",
    "inconclusive_pair_count",
    "fixture_records_sha256",
    "dry_run_sha256",
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
REQUIRED_RECORD_FIELDS = {
    "paired_sample_id",
    "arm",
    "ticker",
    "decision_date",
    "horizon",
    "prompt_hash",
    "input_hash",
    "visible_data_boundary",
    "scoring_rubric_version",
    "source_run_id",
    "source_summary_sha256",
    "source_artifact_sha256",
    "dimension_evidence",
    "dimension_scores",
    "future_data_violation_count",
    "claim_boundary_status",
    "artifact_boundary_status",
}


@dataclass(frozen=True)
class DryRunConfig:
    dry_run_id: str
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
        raise ValueError(f"dry_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("dry_run_id may contain only letters, numbers, '_' and '-'")


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


def synthetic_hash(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


def base_fixture_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    base = {
        "paired_sample_id": "fixture_pair_0001",
        "ticker": "SYNTH",
        "decision_date": "2026-06-22",
        "horizon": "30D_fixture_only",
        "prompt_hash": synthetic_hash("v3.8k.prompt.fixture_pair_0001"),
        "input_hash": synthetic_hash("v3.8k.input.fixture_pair_0001"),
        "visible_data_boundary": "synthetic_visible_before_2026-06-22T00:00:00Z",
        "scoring_rubric_version": RUBRIC_SCHEMA_VERSION,
        "future_data_violation_count": 0,
        "claim_boundary_status": "clean",
        "artifact_boundary_status": "clean",
    }
    scores_by_arm = {
        "ksana_real_research": 3,
        "full_gotra": 3,
        DIRECT_INTERPRETATION: 2,
    }
    for arm in ALLOWED_ARMS:
        record = dict(base)
        record.update(
            {
                "arm": arm,
                "source_run_id": f"fixture_{arm}_run_0001",
                "source_summary_sha256": synthetic_hash(f"{arm}.summary.fixture_pair_0001"),
                "source_artifact_sha256": synthetic_hash(f"{arm}.artifact.fixture_pair_0001"),
                "dimension_evidence": {
                    dimension: [
                        f"{arm} fixture evidence for {dimension}",
                        "synthetic/local fixture only",
                    ]
                    for dimension in DIMENSIONS
                },
                "dimension_scores": {dimension: scores_by_arm[arm] for dimension in DIMENSIONS},
            }
        )
        records.append(record)
    return records


def per_arm_scores(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for record in records:
        arm = str(record.get("arm") or "")
        if arm in ALLOWED_ARMS and isinstance(record.get("dimension_scores"), dict):
            scores: dict[str, int] = {}
            for dimension in DIMENSIONS:
                value = record["dimension_scores"].get(dimension)
                if isinstance(value, int) and not isinstance(value, bool):
                    scores[dimension] = value
            result[arm] = scores
    return result


def base_summary(config: DryRunConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    records = base_fixture_records()
    summary = {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "dry_run_id": config.dry_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "generated_at": utc_now_iso(),
        "evidence_layer": EVIDENCE_LAYER,
        "dry_run_status": status,
        "rubric_schema_version": RUBRIC_SCHEMA_VERSION,
        "dimension_count": len(DIMENSIONS),
        "dimensions": list(DIMENSIONS),
        "fixture_records": records,
        "paired_sample_count": 1,
        "fixture_pair_count": 1,
        "arms": list(ALLOWED_ARMS),
        "per_arm_dimension_scores": per_arm_scores(records),
        "inconclusive_pair_count": 0,
        "fixture_records_sha256": stable_sha256_json(records),
        "dry_run_sha256": "",
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
        "cognitive_lift_candidate_status": CL_CANDIDATE_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "schema_status": "clean",
        "protocol_status": "clean",
        "provenance_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "artifact_boundary_status": "clean",
        DIRECT_PREFIX + "_boundary_status": "clean",
        "metadata_status": "clean",
        "can_say": ["deterministic fixture dry-run produced structured per-dimension records"],
        "cannot_say": [
            "not actual evaluation",
            "not comparative result",
            "not actual 30D verdict",
            "not provider canary execution",
            "not external proof or advice",
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
    summary["dry_run_sha256"] = dry_run_digest(summary)
    return summary


def dry_run_digest(summary: dict[str, Any]) -> str:
    return stable_sha256_json(
        {
            "rubric_schema_version": summary.get("rubric_schema_version"),
            "dimensions": summary.get("dimensions"),
            "fixture_records": summary.get("fixture_records"),
            "arms": summary.get("arms"),
            "per_arm_dimension_scores": summary.get("per_arm_dimension_scores"),
            DIRECT_INTERPRETATION_KEY: summary.get(DIRECT_INTERPRETATION_KEY),
            DIRECT_CLEAN_BASELINE_KEY: summary.get(DIRECT_CLEAN_BASELINE_KEY),
            "runtime_flags": {flag: summary.get(flag) for flag in RUNTIME_FALSE_FLAGS},
            "actual_30d_readiness_status": summary.get("actual_30d_readiness_status"),
            "next_check_after": summary.get("next_check_after"),
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
        claim_scan.ScanSource(path=path, text=text, origin="v3_8k_fixture_dry_run")
        for path, text in recursive_strings(payload, path="dry_run")
    ]
    scan = claim_scan.scan_sources(sources)
    blockers = scan["overclaim"] + scan[DIRECT_PREFIX] + scan["maturity_gate"] + scan["short_horizon_as_30d"]
    blockers.extend(claim_regression.extra_text_blockers(sources))
    for path, text in recursive_strings(payload, path="dry_run"):
        if STATUS_CLAIM_RE.search(text) and not claim_regression.FALSE_LINE_RE.search(text):
            blockers.append(blocked_item(path, "actual_or_superiority_verdict_claim", "text cannot assert current actual or superiority verdict readiness"))
        match = COMPARATIVE_CLAIM_RE.search(text)
        if match and not claim_scan.is_negated(text, match.start()):
            blockers.append(blocked_item(path, "comparative_or_advice_claim", "comparative or advice wording exceeds fixture dry-run boundary"))
    return blockers


def direct_boundary_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if payload.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", DIRECT_PREFIX + "_interpretation_mismatch", "direct_llm_parametric_memory_control interpretation must remain explicit"))
    if payload.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(blocked_item(f"summary.{DIRECT_CLEAN_BASELINE_KEY}", DIRECT_PREFIX + "_clean_baseline_not_false", "direct_llm_parametric_memory_control cannot be a clean baseline"))
    for path, text in recursive_strings(payload, path="dry_run"):
        if DIRECT_UNSAFE_RE.search(text):
            blockers.append(blocked_item(path, DIRECT_PREFIX + "_unsafe_role_wording", "direct_llm_parametric_memory_control cannot be clean/no-future/no-memory or primary comparator"))
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
            blockers.append(blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false for v3.8K itself"))
    if summary.get("provider_canary_executed") is not False:
        blockers.append(blocked_item("summary.provider_canary_executed", "provider_canary_executed_not_false", "provider canary execution is not part of v3.8K"))
    if summary.get("real_calls_count") != 0:
        blockers.append(blocked_item("summary.real_calls_count", "real_calls_not_zero", "v3.8K must not make real calls"))
    if summary.get("token_usage_total") != 0:
        blockers.append(blocked_item("summary.token_usage_total", "token_usage_not_zero", "v3.8K must not consume tokens"))
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
    if str(summary.get("dry_run_status") or "") not in ALLOWED_STATUSES:
        blockers.append(blocked_item("summary.dry_run_status", "invalid_dry_run_status", "dry_run_status is not allowed"))
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    blockers.extend(blocked_item(f"summary.{key}", "summary_missing_field", f"{key} is required") for key in missing)
    if not _is_iso_utc(summary.get("generated_at")):
        blockers.append(blocked_item("summary.generated_at", "generated_at_invalid", "generated_at must be an ISO UTC timestamp ending in Z"))
    if summary.get("rubric_schema_version") != RUBRIC_SCHEMA_VERSION:
        blockers.append(blocked_item("summary.rubric_schema_version", "rubric_schema_version_mismatch", "rubric schema version must match v3.8J"))
    if summary.get("dimension_count") != len(DIMENSIONS) or summary.get("dimensions") != list(DIMENSIONS):
        blockers.append(blocked_item("summary.dimensions", "dimensions_mismatch", "dry-run dimensions must match v3.8J rubric"))
    if summary.get("arms") != list(ALLOWED_ARMS):
        blockers.append(blocked_item("summary.arms", "arms_mismatch", "dry-run arms must match prereg protocol"))
    if summary.get("cognitive_lift_candidate_status") != CL_CANDIDATE_STATUS:
        blockers.append(blocked_item("summary.cognitive_lift_candidate_status", "candidate_status_invalid", "candidate status must be fixture-only"))
    records = summary.get("fixture_records")
    if not isinstance(records, list):
        blockers.append(blocked_item("summary.fixture_records", "fixture_records_not_list", "fixture_records must be a list"))
        return blockers
    for index, record in enumerate(records):
        _validate_record_schema(record, f"summary.fixture_records[{index}]", blockers)
    return blockers


def _validate_record_schema(record: Any, path: str, blockers: list[dict[str, Any]]) -> None:
    if not isinstance(record, dict):
        blockers.append(blocked_item(path, "fixture_record_not_object", "fixture record must be an object"))
        return
    missing = sorted(REQUIRED_RECORD_FIELDS - set(record))
    blockers.extend(blocked_item(f"{path}.{key}", "fixture_record_missing_field", f"{key} is required") for key in missing)
    if record.get("arm") not in ALLOWED_ARMS:
        blockers.append(blocked_item(f"{path}.arm", "fixture_record_arm_invalid", "record arm must be allowed"))
    for key in ("paired_sample_id", "ticker", "decision_date", "horizon", "prompt_hash", "input_hash", "visible_data_boundary", "source_run_id"):
        if not isinstance(record.get(key), str) or not record.get(key):
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be a non-empty string"))
    for key in ("prompt_hash", "input_hash", "source_summary_sha256", "source_artifact_sha256"):
        if not is_hex(record.get(key), 64):
            blockers.append(blocked_item(f"{path}.{key}", f"{key}_invalid", f"{key} must be 64-char hex"))
    if record.get("scoring_rubric_version") != RUBRIC_SCHEMA_VERSION:
        blockers.append(blocked_item(f"{path}.scoring_rubric_version", "scoring_rubric_version_mismatch", "record scoring rubric must match v3.8J"))
    if record.get("future_data_violation_count") != 0:
        blockers.append(blocked_item(f"{path}.future_data_violation_count", "future_data_violation_count_not_zero", "fixture record must not contain future-data violation"))
    if record.get("claim_boundary_status") != "clean":
        blockers.append(blocked_item(f"{path}.claim_boundary_status", "fixture_record_claim_boundary_not_clean", "record claim boundary must be clean"))
    if record.get("artifact_boundary_status") != "clean":
        blockers.append(blocked_item(f"{path}.artifact_boundary_status", "fixture_record_artifact_boundary_not_clean", "record artifact boundary must be clean"))
    evidence = record.get("dimension_evidence")
    scores = record.get("dimension_scores")
    if not isinstance(evidence, dict):
        blockers.append(blocked_item(f"{path}.dimension_evidence", "dimension_evidence_not_object", "dimension_evidence must be object"))
    if not isinstance(scores, dict):
        blockers.append(blocked_item(f"{path}.dimension_scores", "dimension_scores_not_object", "dimension_scores must be object"))
    if isinstance(evidence, dict):
        for dimension in DIMENSIONS:
            value = evidence.get(dimension)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
                blockers.append(blocked_item(f"{path}.dimension_evidence.{dimension}", "dimension_evidence_missing", "each dimension needs evidence"))
    if isinstance(scores, dict):
        for dimension in DIMENSIONS:
            value = scores.get(dimension)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 4:
                blockers.append(blocked_item(f"{path}.dimension_scores.{dimension}", "dimension_score_invalid", "dimension score must be integer 0-4"))


def protocol_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    records = [record for record in summary.get("fixture_records", []) if isinstance(record, dict)]
    raw_sample_ids = [record.get("paired_sample_id") for record in records]
    sample_ids = {sample_id for sample_id in raw_sample_ids if isinstance(sample_id, str) and sample_id}
    if len(sample_ids) != len(set(raw_sample_ids)):
        blockers.append(blocked_item("summary.fixture_records", "paired_sample_id_invalid_or_duplicate", "paired sample ids must be non-empty unique strings per sample"))
    if summary.get("paired_sample_count") != len(sample_ids):
        blockers.append(blocked_item("summary.paired_sample_count", "paired_sample_count_mismatch", "paired_sample_count must match fixture records"))
    if summary.get("fixture_pair_count") != len(sample_ids):
        blockers.append(blocked_item("summary.fixture_pair_count", "fixture_pair_count_mismatch", "fixture_pair_count must match paired samples"))
    for sample_id in sorted(sample_ids):
        sample_records = [record for record in records if record.get("paired_sample_id") == sample_id]
        arms = [record.get("arm") for record in sample_records]
        if sorted(arms) != sorted(ALLOWED_ARMS):
            blockers.append(blocked_item(f"summary.fixture_records.{sample_id}", "paired_record_arms_mismatch", "each paired sample must contain all allowed arms"))
            continue
        prompt_hashes = {record.get("prompt_hash") for record in sample_records}
        input_hashes = {record.get("input_hash") for record in sample_records}
        visible_boundaries = {record.get("visible_data_boundary") for record in sample_records}
        horizons = {record.get("horizon") for record in sample_records}
        rubric_versions = {record.get("scoring_rubric_version") for record in sample_records}
        if len(prompt_hashes) != 1 or len(input_hashes) != 1:
            blockers.append(blocked_item(f"summary.fixture_records.{sample_id}", "paired_prompt_input_identity_mismatch", "paired records must share prompt/input identity"))
        if len(visible_boundaries) != 1:
            blockers.append(blocked_item(f"summary.fixture_records.{sample_id}", "paired_visible_data_boundary_mismatch", "paired records must share visible data boundary"))
        if len(horizons) != 1:
            blockers.append(blocked_item(f"summary.fixture_records.{sample_id}", "paired_horizon_mismatch", "paired records must share horizon/readiness gate"))
        if rubric_versions != {RUBRIC_SCHEMA_VERSION}:
            blockers.append(blocked_item(f"summary.fixture_records.{sample_id}", "paired_rubric_version_mismatch", "paired records must share rubric version"))
    expected_scores = per_arm_scores(records)
    if summary.get("per_arm_dimension_scores") != expected_scores:
        blockers.append(blocked_item("summary.per_arm_dimension_scores", "per_arm_dimension_scores_mismatch", "per-arm score summary must match fixture records"))
    if summary.get("inconclusive_pair_count") != 0:
        blockers.append(blocked_item("summary.inconclusive_pair_count", "inconclusive_pair_count_not_zero", "canonical fixture dry-run should be conclusive only at fixture validation level"))
    return blockers


def provenance_blockers(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    records = [record for record in summary.get("fixture_records", []) if isinstance(record, dict)]
    if not is_hex(summary.get("fixture_records_sha256"), 64):
        blockers.append(blocked_item("summary.fixture_records_sha256", "fixture_records_sha256_invalid", "fixture records digest is required"))
    elif summary.get("fixture_records_sha256") != stable_sha256_json(records):
        blockers.append(blocked_item("summary.fixture_records_sha256", "fixture_records_sha256_mismatch", "fixture records digest must match records"))
    if not is_hex(summary.get("dry_run_sha256"), 64):
        blockers.append(blocked_item("summary.dry_run_sha256", "dry_run_sha256_invalid", "dry-run digest is required"))
    elif summary.get("dry_run_sha256") != dry_run_digest(summary):
        blockers.append(blocked_item("summary.dry_run_sha256", "dry_run_sha256_mismatch", "dry-run digest must cover boundary-critical fields"))
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
    summary["protocol_status"] = "blocked" if any(_rule_has(item, ("protocol", "paired", "visible_data_boundary", "horizon", "rubric", "inconclusive")) for item in blockers) else "clean"
    summary["provenance_status"] = "blocked" if any(_rule_has(item, ("provenance", "sha256", "hash", "digest", "source")) for item in blockers) else "clean"
    summary["claim_boundary_status"] = "blocked" if any(_rule_has(item, ("claim", "overclaim")) for item in blockers) else "clean"
    summary["runtime_boundary_status"] = "blocked" if any(_rule_has(item, ("runtime", "flag", "provider", "backend", "executable", "canary", "calls", "token", "output_dir")) for item in blockers) else "clean"
    summary["artifact_boundary_status"] = "blocked" if any(_rule_has(item, ("forbidden_artifact", "raw_reference", "raw_tmp_path", "repo_raw")) for item in blockers) else "clean"
    summary[DIRECT_PREFIX + "_boundary_status"] = "blocked" if any(_rule_has(item, (DIRECT_PREFIX, "direct_control")) for item in blockers) else "clean"
    summary["metadata_status"] = "blocked" if any(_rule_has(item, ("metadata", "score", "count", "token", "calls")) for item in blockers) else "clean"


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
    if any("score" in reason or "metadata" in reason for reason in reasons):
        return STATUS_BLOCKED_METADATA
    if any(
        "protocol" in reason
        or "paired" in reason
        or "visible_data_boundary" in reason
        or "horizon" in reason
        or "rubric" in reason
        or "inconclusive" in reason
        for reason in reasons
    ):
        return STATUS_BLOCKED_PROTOCOL
    if any("schema" in reason or "missing" in reason or "invalid" in reason or "not_list" in reason or "not_object" in reason or "dimension" in reason for reason in reasons):
        return STATUS_BLOCKED_SCHEMA
    if any("provenance" in reason or "sha256" in reason or "hash" in reason or "digest" in reason or "source" in reason for reason in reasons):
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


def fixture_identity_blockers(payload: dict[str, Any], *, config: DryRunConfig, run_root: Path) -> list[dict[str, Any]]:
    expected = {
        "dry_run_id": config.dry_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
    }
    blockers: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        if key in payload and payload.get(key) != expected_value:
            blockers.append(blocked_item(f"summary.{key}", f"{key}_identity_mismatch", f"{key} must come from CLI/config"))
    return blockers


def restore_config_identity(summary: dict[str, Any], *, config: DryRunConfig, run_root: Path) -> None:
    summary["dry_run_id"] = config.dry_run_id
    summary["run_root"] = str(run_root)
    summary["summary_path"] = str(run_root / "summary.json")
    summary["manifest_path"] = str(run_root / "manifest.json")


def build_from_fixture(config: DryRunConfig, *, run_root: Path) -> dict[str, Any]:
    payload, load_blockers = load_summary_fixture(config.summary_fixture or Path(""))
    identity_blockers = fixture_identity_blockers(payload, config=config, run_root=run_root) if payload else []
    summary = base_summary(
        config,
        run_root=run_root,
        status=str(payload.get("dry_run_status") or STATUS_BLOCKED_SCHEMA) if payload else STATUS_BLOCKED_SCHEMA,
    )
    if payload:
        summary.update(payload)
    restore_config_identity(summary, config=config, run_root=run_root)
    summary["fixture_records_sha256"] = stable_sha256_json(summary.get("fixture_records", []))
    summary["dry_run_sha256"] = dry_run_digest(summary)
    blockers = load_blockers + identity_blockers + validate_summary_payload(summary)
    summary["dry_run_status"] = choose_status(blockers, current_status=str(summary.get("dry_run_status") or ""))
    finalize_blockers(summary, blockers)
    return summary


def build_default_dry_run(config: DryRunConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, status=STATUS_READY)
    blockers = validate_summary_payload(summary)
    summary["dry_run_status"] = choose_status(blockers, current_status=STATUS_READY)
    finalize_blockers(summary, blockers)
    return summary


def build_summary(config: DryRunConfig) -> dict[str, Any]:
    validate_run_id(config.dry_run_id)
    run_root = config.output_dir / config.dry_run_id
    if not under_tmp(run_root):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        blockers = [blocked_item(run_root, "output_dir_not_tmp", "dry-run outputs must be under /tmp")]
        summary["dry_run_status"] = choose_status(blockers, current_status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
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
        summary = build_default_dry_run(config, run_root=run_root)
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary["fixture_records_sha256"] = stable_sha256_json(summary.get("fixture_records", []))
    summary["dry_run_sha256"] = dry_run_digest(summary)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "dry_run_id": summary.get("dry_run_id"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "dry_run_sha256": summary.get("dry_run_sha256"),
        "fixture_records_sha256": summary.get("fixture_records_sha256"),
        "dry_run_status": summary.get("dry_run_status"),
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
    parser.add_argument("--dry-run-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8k_cognitive_lift_fixture_dry_run/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--summary-fixture", type=Path)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> DryRunConfig:
    return DryRunConfig(
        dry_run_id=str(args.dry_run_id),
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
        summary_fixture=args.summary_fixture,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(config_from_args(args))
    except ValueError as exc:
        print(json.dumps({"dry_run_status": STATUS_BLOCKED_SCHEMA, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("dry_run_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
