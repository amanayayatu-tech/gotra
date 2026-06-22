#!/usr/bin/env python3
"""GOTRA v3.8 ksana_real_research comparison prereg/schema validator."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_8.ksana_comparison_prereg_schema_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_8.ksana_comparison_prereg_schema_manifest.v1"
PREREG_SCHEMA_VERSION = "gotra.baseline_v3_8.ksana_comparison_prereg.v1"
RUN_ID_PREFIX = "baseline_v3_8_ksana_comparison_prereg_schema_"
SCRIPT_VERSION = "v3.8-20260622"
EVIDENCE_LAYER = "engineering_internal_v3_8_ksana_comparison_prereg_schema"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_8_KSANA_COMPARISON_PREREG_SCHEMA_READY"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_DATA_NOT_MATURED = "DATA_NOT_MATURED"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_RUN_ID_EXISTS = "V3_8_KSANA_COMPARISON_PREREG_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}
HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
REQUIRED_ARMS = {"ksana_real_research", "full_gotra"}
OPTIONAL_DIRECT_LLM = "direct_llm_parametric_memory_control"
FORBIDDEN_DIRECT_LLM_ROLES = {"primary", "primary_comparator", "baseline", "clean_baseline", "treatment"}
REQUIRED_FALSE_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
REQUIRED_FIELDS = (
    "comparison_id",
    "prereg_id",
    "schema_version",
    "arms",
    "paired_design",
    "actual_30d_readiness_status",
    "actual_30d_next_check_after",
    "evidence_layer",
    "non_claims",
    "direct_llm_interpretation",
)
BOUNDARY_CRITICAL_FIELDS = (
    "comparison_id",
    "prereg_id",
    "schema_version",
    "arms",
    "paired_design",
    "actual_30d_readiness_status",
    "actual_30d_next_check_after",
    "direct_llm_interpretation",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "evidence_layer",
)


@dataclass(frozen=True)
class PreregConfig:
    validator_run_id: str
    fixture: Path
    output_dir: Path
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"validator_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("validator_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value.strip()))


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "forbidden_fixture_path", "fixture path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [blocked_item(path, "fixture_read_error", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [blocked_item(path, "fixture_json_decode_error", str(exc))]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "fixture_root_not_object", "fixture must be a JSON object")]
    return payload, []


def arm_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("arms")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def arm_id(entry: dict[str, Any]) -> str:
    return str(entry.get("arm_id") or entry.get("name") or "").strip()


def provenance_arms(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    provenance = payload.get("provenance")
    raw = provenance.get("arms") if isinstance(provenance, dict) else {}
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items() if isinstance(value, dict)}
    return {}


def schema_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for field in REQUIRED_FIELDS:
        if field not in payload:
            blockers.append(blocked_item("fixture", f"missing_{field}", f"{field} is required"))
    if blockers:
        return blockers
    if payload.get("schema_version") != PREREG_SCHEMA_VERSION:
        blockers.append(blocked_item("fixture", "schema_version_mismatch", f"schema_version must be {PREREG_SCHEMA_VERSION}"))
    if payload.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("fixture", "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if payload.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocked_item("fixture", "actual_30d_readiness_status_not_data_not_matured", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if payload.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("fixture", "actual_30d_next_check_after_mismatch", "next_check_after must remain 2026-07-21T00:00:00Z"))
    if payload.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        blockers.append(blocked_item("fixture", "direct_llm_interpretation_mismatch", "direct_llm_interpretation must be direct_llm_parametric_memory_control"))
    for field in ("comparison_id", "prereg_id"):
        if not is_non_empty_string(payload.get(field)):
            blockers.append(blocked_item("fixture", f"{field}_invalid", f"{field} must be a non-empty string"))

    raw_arms = payload.get("arms")
    arms = arm_entries(payload)
    if not isinstance(raw_arms, list):
        blockers.append(blocked_item("fixture.arms", "arms_not_list", "arms must be a list"))
    elif len(arms) != len(raw_arms):
        blockers.append(blocked_item("fixture.arms", "arm_entry_not_object", "all arm entries must be objects"))
    arm_ids = {arm_id(entry) for entry in arms}
    if not REQUIRED_ARMS.issubset(arm_ids):
        blockers.append(blocked_item("fixture.arms", "required_arms_missing", "arms must include ksana_real_research and full_gotra"))
    comparison_arms = arm_ids - {OPTIONAL_DIRECT_LLM}
    if comparison_arms != REQUIRED_ARMS:
        blockers.append(blocked_item("fixture.arms", "unexpected_primary_comparison_arms", "primary comparison arms must be exactly ksana_real_research and full_gotra"))
    for index, entry in enumerate(arms):
        current_id = arm_id(entry)
        if not current_id:
            blockers.append(blocked_item(f"fixture.arms[{index}]", "arm_id_missing", "arm_id is required"))
        if current_id == "direct_llm" or str(entry.get("role") or "").strip().lower() in FORBIDDEN_DIRECT_LLM_ROLES:
            blockers.append(blocked_item(f"fixture.arms[{index}]", "direct_llm_as_primary_or_clean_baseline", "direct_llm cannot be a primary comparator or clean baseline"))
        if current_id == OPTIONAL_DIRECT_LLM and str(entry.get("role") or "").strip().lower() not in {"historical_diagnostic", "diagnostic_control", "metadata_only"}:
            blockers.append(blocked_item(f"fixture.arms[{index}]", "direct_llm_role_not_diagnostic", "direct_llm_parametric_memory_control must be diagnostic metadata only"))

    paired = payload.get("paired_design")
    if not isinstance(paired, dict):
        blockers.append(blocked_item("fixture.paired_design", "paired_design_missing", "paired_design object is required"))
    else:
        keys = paired.get("pairing_keys")
        if not isinstance(keys, list) or not {"ticker", "decision_date", "horizon"}.issubset({str(item) for item in keys}):
            blockers.append(blocked_item("fixture.paired_design", "pairing_keys_invalid", "pairing_keys must include ticker, decision_date, horizon"))
    return blockers


def runtime_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in REQUIRED_FALSE_FLAGS:
        if flag not in payload:
            blockers.append(blocked_item("fixture", f"missing_{flag}", f"{flag} must be explicitly present and false"))
        elif payload.get(flag) is not False:
            blockers.append(blocked_item("fixture", f"{flag}_not_false", f"{flag} must be false"))
    return blockers


def artifact_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = claim_regression.path_blockers(payload, path="fixture")
    for entry in arm_entries(payload):
        path = str(entry.get("source_artifact_path") or "")
        if path and claim_scan.forbidden_path(path):
            blockers.append(blocked_item(path, "forbidden_source_artifact_path", "source artifact path violates artifact boundary"))
    return blockers


def provenance_blockers(payload: dict[str, Any], *, fixture_path: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    provenance = provenance_arms(payload)
    if not provenance:
        blockers.append(blocked_item("fixture.provenance", "provenance_arms_missing", "provenance.arms is required"))
    for index, entry in enumerate(arm_entries(payload)):
        current_id = arm_id(entry)
        if current_id == OPTIONAL_DIRECT_LLM:
            continue
        entry_path = f"fixture.arms[{index}]"
        for field in ("source_run_id", "source_artifact_path", "source_summary_sha256", "source_artifact_sha256", "generated_at"):
            if not is_non_empty_string(entry.get(field)):
                blockers.append(blocked_item(entry_path, f"{field}_missing", f"{field} is required for {current_id}"))
        if entry.get("source_summary_sha256") and not is_hash(entry.get("source_summary_sha256")):
            blockers.append(blocked_item(entry_path, "source_summary_sha256_invalid", "source_summary_sha256 must be sha256 hex"))
        if entry.get("source_artifact_sha256") and not is_hash(entry.get("source_artifact_sha256")):
            blockers.append(blocked_item(entry_path, "source_artifact_sha256_invalid", "source_artifact_sha256 must be sha256 hex"))
        if entry.get("generated_at") and parse_generated_at(entry.get("generated_at")) is None:
            blockers.append(blocked_item(entry_path, "generated_at_invalid", "generated_at must be ISO-8601"))
        prov = provenance.get(current_id, {})
        if prov:
            for field in ("source_run_id", "source_artifact_path", "source_summary_sha256"):
                if prov.get(field) != entry.get(field):
                    blockers.append(blocked_item(f"fixture.provenance.arms.{current_id}", f"{field}_mismatch", f"provenance {field} must match arm"))
        if is_non_empty_string(entry.get("source_artifact_path")) and is_hash(entry.get("source_artifact_sha256")):
            candidate = Path(str(entry["source_artifact_path"])).expanduser()
            if not candidate.is_absolute():
                candidate = (fixture_path.parent / candidate).resolve()
            if candidate.exists() and candidate.is_file():
                actual = sha256_file(candidate)
                if actual != str(entry["source_artifact_sha256"]).lower():
                    blockers.append(blocked_item(candidate, "source_artifact_sha256_mismatch", "source artifact hash does not match file bytes"))
    return blockers


def claim_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = claim_regression.claim_blockers(payload, path="fixture")
    for entry in arm_entries(payload):
        current_id = arm_id(entry)
        role = str(entry.get("role") or "").lower()
        if "direct_llm" in current_id and current_id != OPTIONAL_DIRECT_LLM:
            blockers.append(blocked_item("fixture.arms", "direct_llm_without_parametric_memory_control", "direct_llm must be direct_llm_parametric_memory_control"))
        if current_id == OPTIONAL_DIRECT_LLM and any(term in role for term in ("clean", "baseline", "primary")):
            blockers.append(blocked_item("fixture.arms", "direct_llm_clean_or_primary_role", "direct_llm_parametric_memory_control cannot be a clean baseline or primary comparator"))
    return blockers


def choose_status(
    *,
    schema: list[dict[str, Any]],
    runtime: list[dict[str, Any]],
    artifact: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    overclaim: list[dict[str, Any]],
) -> str:
    if schema:
        return STATUS_BLOCKED_SCHEMA
    if runtime:
        return STATUS_BLOCKED_RUNTIME_BOUNDARY
    if artifact:
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if provenance:
        return STATUS_BLOCKED_PROVENANCE
    if overclaim:
        return STATUS_BLOCKED_OVERCLAIM
    return STATUS_READY


def digest_payload(payload: dict[str, Any], status: str, blocker_reasons: list[str]) -> dict[str, Any]:
    return {
        "schema": PREREG_SCHEMA_VERSION,
        "boundary_fields": {field: payload.get(field) for field in BOUNDARY_CRITICAL_FIELDS},
        "status": status,
        "blocker_reasons": blocker_reasons,
    }


def base_summary(config: PreregConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "validator_run_id": config.validator_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "validator_status": status,
        "validation_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "comparison_id": "",
        "prereg_id": "",
        "schema_version": PREREG_SCHEMA_VERSION,
        "arm_count": 0,
        "primary_comparison_arms": [],
        "has_direct_llm_parametric_memory_control_metadata": False,
        "paired_key_count": 0,
        "source_artifact_path_count": 0,
        "source_summary_hash_count": 0,
        "source_artifact_hash_count": 0,
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "schema_boundary_status": "clean",
        "provenance_boundary_status": "clean",
        "schema_blocker_count": 0,
        "runtime_blocker_count": 0,
        "artifact_blocker_count": 0,
        "provenance_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "blocker_reasons": [],
        "blocked_items": [],
        "prereg_content_sha256": "",
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "non_claims": {
            "not_provider_run": True,
            "not_actual_comparison_verdict": True,
            "not_oos_science_public_proof": True,
            "not_trading_or_investment_advice": True,
        },
    }


def build_summary(config: PreregConfig) -> dict[str, Any]:
    validate_run_id(config.validator_run_id)
    run_root = config.output_dir / config.validator_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["schema_blocker_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        summary["blocked_items"] = [blocked_item(run_root, "output_run_id_exists", "output run id exists")]
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    payload, load_blockers = load_fixture(config.fixture)
    schema = load_blockers + (schema_blockers(payload) if payload else [])
    runtime = runtime_blockers(payload) if payload else []
    artifact = artifact_blockers(payload) if payload else []
    provenance = provenance_blockers(payload, fixture_path=config.fixture) if payload else []
    overclaim = claim_blockers(payload) if payload else []
    status = choose_status(schema=schema, runtime=runtime, artifact=artifact, provenance=provenance, overclaim=overclaim)
    blocked_items = schema + runtime + artifact + provenance + overclaim
    blocker_reasons = [str(item["rule_id"]) for item in blocked_items]
    run_root.mkdir(parents=True, exist_ok=True)
    arms = arm_entries(payload) if payload else []
    arm_ids = [arm_id(entry) for entry in arms if arm_id(entry)]
    paired = payload.get("paired_design", {}) if payload else {}
    pairing_keys = paired.get("pairing_keys", []) if isinstance(paired, dict) else []
    summary = base_summary(config, run_root=run_root, status=status)
    summary.update(
        {
            "validator_status": status,
            "comparison_id": str(payload.get("comparison_id") or ""),
            "prereg_id": str(payload.get("prereg_id") or ""),
            "schema_version": str(payload.get("schema_version") or PREREG_SCHEMA_VERSION),
            "arm_count": len(arms),
            "primary_comparison_arms": sorted([arm for arm in arm_ids if arm != OPTIONAL_DIRECT_LLM]),
            "has_direct_llm_parametric_memory_control_metadata": OPTIONAL_DIRECT_LLM in arm_ids,
            "paired_key_count": len(pairing_keys) if isinstance(pairing_keys, list) else 0,
            "source_artifact_path_count": sum(1 for entry in arms if is_non_empty_string(entry.get("source_artifact_path"))),
            "source_summary_hash_count": sum(1 for entry in arms if is_hash(entry.get("source_summary_sha256"))),
            "source_artifact_hash_count": sum(1 for entry in arms if is_hash(entry.get("source_artifact_sha256"))),
            "artifact_boundary_status": "blocked" if artifact else "clean",
            "claim_boundary_status": "blocked" if overclaim else "clean",
            "runtime_boundary_status": "blocked" if runtime else "clean",
            "schema_boundary_status": "blocked" if schema else "clean",
            "provenance_boundary_status": "blocked" if provenance else "clean",
            "schema_blocker_count": len(schema),
            "runtime_blocker_count": len(runtime),
            "artifact_blocker_count": len(artifact),
            "provenance_blocker_count": len(provenance),
            "overclaim_blocker_count": len(overclaim),
            "blocker_reasons": blocker_reasons,
            "blocked_items": blocked_items[:100],
            "prereg_content_sha256": stable_sha256_json(digest_payload(payload, status, blocker_reasons)),
            "provider_or_backend_called": bool(payload.get("provider_or_backend_called")) if payload else False,
            "codex_cli_new_call": bool(payload.get("codex_cli_new_call")) if payload else False,
            "formal_lite_entered": bool(payload.get("formal_lite_entered")) if payload else False,
            "v3_7_actual_verdict_executable": bool(payload.get("v3_7_actual_verdict_executable")) if payload else False,
            "v3_7_actual_verdict_executed": bool(payload.get("v3_7_actual_verdict_executed")) if payload else False,
            "actual_30d_readiness_status": str(payload.get("actual_30d_readiness_status") or ACTUAL_30D_READINESS_STATUS),
            "actual_30d_next_check_after": str(payload.get("actual_30d_next_check_after") or ACTUAL_30D_NEXT_CHECK_AFTER),
            "direct_llm_interpretation": str(payload.get("direct_llm_interpretation") or DIRECT_LLM_INTERPRETATION),
        }
    )
    write_outputs(config, summary, run_root=run_root)
    return summary


def write_outputs(config: PreregConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "validator_run_id": config.validator_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "prereg_content_sha256": summary.get("prereg_content_sha256"),
        "validator_status": summary.get("validator_status"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator-run-id", default=default_run_id())
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_8_ksana_comparison_prereg_schema/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PreregConfig:
    return PreregConfig(
        validator_run_id=str(args.validator_run_id),
        fixture=args.fixture,
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed with redacted stderr.
        print(f"v3.8 ksana comparison prereg schema validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("validator_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
