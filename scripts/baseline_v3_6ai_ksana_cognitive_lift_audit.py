#!/usr/bin/env python3
"""GOTRA v3.6AI ksana cognitive-lift deterministic audit."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_6ai.ksana_cognitive_lift_audit_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ai.ksana_cognitive_lift_audit_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ai_ksana_cognitive_lift_audit_"
SCRIPT_VERSION = "v3.6ai-20260621"
EVIDENCE_LAYER = "engineering/local cognitive-lift audit only"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "COGNITIVE_LIFT_READY_FOR_FIXTURE_COMPARISON"
STATUS_LOW_INFORMATION_GAIN = "LOW_INFORMATION_GAIN"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"

NON_BLOCKING_STATUSES = {STATUS_READY, STATUS_LOW_INFORMATION_GAIN, STATUS_DATA_INSUFFICIENT}

REQUIRED_CONTRACT_FIELDS = {
    "source_run_id",
    "source_artifact_path",
    "ticker",
    "decision_date",
    "research_mode",
    "hypotheses",
    "counterfactuals",
    "disagreement_with_price_only",
    "evidence_gaps",
    "uncertainty_decomposition",
    "non_claims",
    "evidence_layer",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "provenance",
}
REQUIRED_HYPOTHESIS_FIELDS = {
    "rank",
    "confidence",
    "why_it_matters",
    "falsification_triggers",
    "expected_observable_evidence",
}
PROVENANCE_REQUIRED_FIELDS = {
    "source_run_id",
    "source_artifact_path",
}
GOTRA_CONSUMED_FIELDS = {
    "adapter_schema",
    "adapter_validation_status",
    "name",
    "kind",
    "source",
    "source_kind",
    "source_family",
    "availability_date",
    "latest_visible_price_date",
    "captured_at",
    "summary",
    "text",
    "ticker",
    "decision_date",
    "horizon_days",
    "input_layer",
    "source_name",
    "source_url_or_id",
    "source_url",
    "source_id",
    "source_run_id",
    "source_artifact_path",
    "source_artifact_hash",
    "source_fixture_id",
    "publish_timestamp",
    "retrieval_method",
    "evidence_ref",
    "decision_date_scope",
    "decision_date_max",
    "provenance_hash",
    "adapter_legacy_unverified",
    "citations",
    "evidence",
    "claims",
    "features",
    "research_artifacts",
    "ksana_research_workflow",
    "alaya_feedback_history",
    "alaya_knowledge_state",
}
GENERIC_CAUTION_PATTERNS = (
    r"\bdo your own research\b",
    r"\bnot investment advice\b",
    r"\buncertain\b",
    r"\buncertainty remains\b",
    r"\blimited information\b",
    r"\bcannot guarantee\b",
    r"\brisk remains\b",
    r"\bcould\b",
    r"\bmay\b",
    r"\bmight\b",
    r"\bno conclusion\b",
    r"\bgeneric caution\b",
)
FUTURE_DATA_METADATA_FIELDS = {
    "future_data_violation",
    "latest_visible_price_date",
    "availability_date",
    "decision_date_scope",
    "decision_date_max",
}
CLAIM_SCAN_SKIP_FIELDS = {
    "schema",
    "source_run_id",
    "source_artifact_path",
    "ticker",
    "decision_date",
    "non_claims",
    "evidence_layer",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "provenance",
}


@dataclass(frozen=True)
class AuditConfig:
    audit_run_id: str
    output_dir: Path
    input_artifacts: tuple[Path, ...] = ()
    manifest: Path | None = None
    allow_overwrite: bool = False


@dataclass(frozen=True)
class AuditArtifact:
    path: str
    payload: dict[str, Any]
    origin: str


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"audit_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("audit_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_path(path: Path | str) -> str:
    raw = str(path).replace("\\", "/")
    if not raw:
        return ""
    try:
        resolved = Path(raw).expanduser().resolve()
    except OSError:
        return raw
    for root in (Path.cwd().resolve(), REPO_ROOT.resolve()):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def artifacts_from_payload(payload: Any, *, path: str, origin: str) -> list[AuditArtifact]:
    if isinstance(payload, dict) and isinstance(payload.get("artifacts"), list):
        return [
            AuditArtifact(path=f"{path}#{index}", payload=dict(item), origin=origin)
            for index, item in enumerate(payload["artifacts"])
            if isinstance(item, dict)
        ]
    if isinstance(payload, list):
        return [
            AuditArtifact(path=f"{path}#{index}", payload=dict(item), origin=origin)
            for index, item in enumerate(payload)
            if isinstance(item, dict)
        ]
    if isinstance(payload, dict):
        return [AuditArtifact(path=path, payload=dict(payload), origin=origin)]
    return []


def artifact_from_manifest_entry(entry: Any) -> list[AuditArtifact]:
    if not isinstance(entry, dict):
        return []
    path = normalize_path(str(entry.get("path") or entry.get("source_artifact_path") or ""))
    if "payload" in entry and isinstance(entry["payload"], dict):
        return [AuditArtifact(path=path or "manifest_payload", payload=dict(entry["payload"]), origin="manifest")]
    if "text" in entry:
        try:
            parsed = json.loads(str(entry["text"]))
        except json.JSONDecodeError:
            parsed = {"text": str(entry["text"]), "source_artifact_path": path}
        return artifacts_from_payload(parsed, path=path or "manifest_text", origin="manifest")
    if path:
        file_path = (REPO_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)
        if claim_scan.forbidden_path(path):
            return [
                AuditArtifact(
                    path=path,
                    payload={"_schema_error": "forbidden_artifact_path"},
                    origin="manifest_path",
                )
            ]
        return artifacts_from_payload(load_json(file_path), path=path, origin="manifest_path")
    return []


def collect_artifacts(config: AuditConfig) -> tuple[list[AuditArtifact], list[dict[str, Any]]]:
    artifacts: list[AuditArtifact] = []
    load_errors: list[dict[str, Any]] = []
    if config.manifest:
        manifest_path = normalize_path(config.manifest)
        if claim_scan.forbidden_path(manifest_path):
            load_errors.append(
                make_blocker(manifest_path, "forbidden_artifact_path", "manifest path is forbidden")
            )
        else:
            manifest = load_json(config.manifest)
            if not isinstance(manifest, dict):
                load_errors.append(
                    make_blocker(
                        manifest_path,
                        "malformed_manifest_root",
                        "manifest must be a JSON object",
                    )
                )
            else:
                entries = manifest.get("artifacts", [])
                if not isinstance(entries, list):
                    load_errors.append(
                        make_blocker(
                            manifest_path,
                            "malformed_manifest_artifacts",
                            "manifest artifacts must be a list",
                        )
                    )
                    entries = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        load_errors.append(
                            make_blocker(
                                manifest_path,
                                "malformed_manifest_artifact_entry",
                                "manifest artifact entry must be an object",
                            )
                        )
                        continue
                    try:
                        artifacts.extend(artifact_from_manifest_entry(entry))
                    except (OSError, json.JSONDecodeError, ValueError) as exc:
                        load_errors.append(
                            make_blocker(
                                normalize_path(str(entry.get("path", "")))
                                if isinstance(entry, dict)
                                else "",
                                "artifact_load_error",
                                str(exc),
                            )
                        )
    for path in config.input_artifacts:
        normalized = normalize_path(path)
        if claim_scan.forbidden_path(normalized):
            load_errors.append(
                make_blocker(normalized, "forbidden_artifact_path", "input path is forbidden")
            )
            continue
        try:
            artifacts.extend(artifacts_from_payload(load_json(path), path=normalized, origin="file"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            load_errors.append(make_blocker(normalized, "artifact_load_error", str(exc)))
    return artifacts, load_errors


def make_blocker(path: str, rule_id: str, reason: str) -> dict[str, Any]:
    return {"path": path, "rule_id": rule_id, "reason": reason}


def list_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, str) and value.strip():
        return 1
    return 0


def iter_hypotheses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("hypotheses")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    return []


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def nested_list_count(payload: dict[str, Any], key: str, hypotheses: list[dict[str, Any]]) -> int:
    total = list_count(payload.get(key))
    total += sum(list_count(item.get(key)) for item in hypotheses)
    return total


def claim_text_sources_from_value(
    *,
    artifact: AuditArtifact,
    field_path: str,
    value: Any,
) -> list[claim_scan.ScanSource]:
    if isinstance(value, str):
        return [
            claim_scan.ScanSource(
                path=f"{artifact.path}:{field_path}",
                text=value,
                origin=artifact.origin,
            )
        ]
    if isinstance(value, list):
        sources: list[claim_scan.ScanSource] = []
        for index, item in enumerate(value):
            sources.extend(
                claim_text_sources_from_value(
                    artifact=artifact,
                    field_path=f"{field_path}[{index}]",
                    value=item,
                )
            )
        return sources
    if isinstance(value, dict):
        sources = []
        for key, item in value.items():
            if str(key) in CLAIM_SCAN_SKIP_FIELDS:
                continue
            sources.extend(
                claim_text_sources_from_value(
                    artifact=artifact,
                    field_path=f"{field_path}.{key}",
                    value=item,
                )
            )
        return sources
    return []


def claim_scan_sources_for_artifact(artifact: AuditArtifact) -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    for key, value in artifact.payload.items():
        if key in CLAIM_SCAN_SKIP_FIELDS:
            continue
        sources.extend(
            claim_text_sources_from_value(artifact=artifact, field_path=key, value=value)
        )
    return sources


def text_for_caution_scan(payload: dict[str, Any]) -> str:
    fields: list[str] = []
    for key in ("summary", "text", "why_it_matters", "research_mode"):
        value = payload.get(key)
        if isinstance(value, str):
            fields.append(value)
    for key in ("hypotheses", "counterfactuals", "evidence_gaps", "claims"):
        value = payload.get(key)
        if value:
            fields.append(json.dumps(value, ensure_ascii=False, default=str))
    return "\n".join(fields)


def generic_caution_count(payload: dict[str, Any]) -> int:
    text = text_for_caution_scan(payload).lower()
    return sum(len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in GENERIC_CAUTION_PATTERNS)


def validate_schema(artifact: AuditArtifact) -> list[dict[str, Any]]:
    payload = artifact.payload
    if payload.get("_schema_error"):
        return [make_blocker(artifact.path, str(payload["_schema_error"]), "artifact cannot be audited")]
    provenance_fields = {"provenance", "source_run_id", "source_artifact_path"}
    missing = sorted((REQUIRED_CONTRACT_FIELDS - provenance_fields) - set(payload))
    type_errors: list[str] = []
    if "hypotheses" in payload and not isinstance(payload["hypotheses"], list):
        type_errors.append("hypotheses")
    if "hypotheses" in payload and isinstance(payload["hypotheses"], list):
        for index, item in enumerate(payload["hypotheses"]):
            if not isinstance(item, dict):
                type_errors.append(f"hypotheses[{index}]")
    if "disagreement_with_price_only" in payload and not isinstance(
        payload["disagreement_with_price_only"], (list, dict)
    ):
        type_errors.append("disagreement_with_price_only")
    for key in (
        "counterfactuals",
        "evidence_gaps",
        "non_claims",
    ):
        if key in payload and not isinstance(payload[key], (list, dict)):
            type_errors.append(key)
    if "uncertainty_decomposition" in payload and not isinstance(
        payload["uncertainty_decomposition"], (dict, list)
    ):
        type_errors.append("uncertainty_decomposition")
    for key in ("provider_or_backend_called", "codex_cli_new_call", "formal_lite_entered"):
        if key in payload and payload[key] is not False:
            type_errors.append(key)
    hypothesis_missing = []
    for index, item in enumerate(iter_hypotheses(payload)):
        missing_keys = sorted(REQUIRED_HYPOTHESIS_FIELDS - set(item))
        if missing_keys:
            hypothesis_missing.append(f"hypotheses[{index}]:{','.join(missing_keys)}")
        if "rank" in item and not is_number(item["rank"]):
            type_errors.append(f"hypotheses[{index}].rank")
        if "confidence" in item:
            confidence = item["confidence"]
            if not is_number(confidence) or not 0 <= float(confidence) <= 1:
                type_errors.append(f"hypotheses[{index}].confidence")
        if "why_it_matters" in item and not isinstance(item["why_it_matters"], str):
            type_errors.append(f"hypotheses[{index}].why_it_matters")
        for key in ("falsification_triggers", "expected_observable_evidence"):
            if key in item and not isinstance(item[key], list):
                type_errors.append(f"hypotheses[{index}].{key}")
        if "counterfactuals" in item and not isinstance(item["counterfactuals"], list):
            type_errors.append(f"hypotheses[{index}].counterfactuals")
    failures = missing + sorted(set(type_errors)) + hypothesis_missing
    if failures:
        return [
            make_blocker(
                artifact.path,
                "missing_or_invalid_required_schema_field",
                ",".join(failures),
            )
        ]
    return []


def validate_provenance(artifact: AuditArtifact) -> list[dict[str, Any]]:
    payload = artifact.payload
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return [make_blocker(artifact.path, "missing_provenance", "provenance must be an object")]
    missing = sorted(PROVENANCE_REQUIRED_FIELDS - set(provenance))
    mismatches = [
        key
        for key in PROVENANCE_REQUIRED_FIELDS
        if key in provenance and str(provenance.get(key) or "") != str(payload.get(key) or "")
    ]
    empty_top_level = [
        key for key in PROVENANCE_REQUIRED_FIELDS if not str(payload.get(key) or "").strip()
    ]
    failures = missing + mismatches + empty_top_level
    forbidden_paths = []
    for key in ("source_artifact_path",):
        top_path = str(payload.get(key) or "")
        provenance_path = str(provenance.get(key) or "") if isinstance(provenance, dict) else ""
        if top_path and claim_scan.forbidden_path(top_path):
            forbidden_paths.append(key)
        if provenance_path and claim_scan.forbidden_path(provenance_path):
            forbidden_paths.append(f"provenance.{key}")
    if failures:
        return [
            make_blocker(
                artifact.path,
                "missing_or_inconsistent_provenance",
                ",".join(sorted(set(failures))),
            )
        ]
    if forbidden_paths:
        return [
            make_blocker(
                artifact.path,
                "forbidden_source_artifact_path",
                ",".join(sorted(set(forbidden_paths))),
            )
        ]
    return []


def scan_overclaim(artifacts: list[AuditArtifact]) -> list[dict[str, Any]]:
    sources = [source for artifact in artifacts for source in claim_scan_sources_for_artifact(artifact)]
    scan = claim_scan.scan_sources(sources)
    return (
        scan["overclaim"]
        + scan["direct_llm"]
        + scan["maturity_gate"]
        + scan["short_horizon_as_30d"]
    )


def count_future_data_metadata(payload: dict[str, Any]) -> int:
    count = sum(1 for key in FUTURE_DATA_METADATA_FIELDS if key in payload)
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        count += sum(1 for key in FUTURE_DATA_METADATA_FIELDS if key in provenance)
    return count


def metrics_for_artifacts(artifacts: list[AuditArtifact]) -> dict[str, Any]:
    source_path_count = 0
    gotra_used_fields: set[str] = set()
    gotra_ignored_fields: set[str] = set()
    hypothesis_count = 0
    ranked_hypothesis_count = 0
    counterfactual_count = 0
    falsifiable_trigger_count = 0
    explicit_disagreement_count = 0
    evidence_gap_count = 0
    uncertainty_decomposition_count = 0
    generic_caution_phrase_count = 0
    provenance_link_count = 0
    future_data_metadata_count = 0

    for artifact in artifacts:
        payload = artifact.payload
        if str(payload.get("source_artifact_path") or "").strip():
            source_path_count += 1
        gotra_used_fields.update(set(payload) & GOTRA_CONSUMED_FIELDS)
        gotra_ignored_fields.update(set(payload) - GOTRA_CONSUMED_FIELDS)
        hypotheses = iter_hypotheses(payload)
        hypothesis_count += len(hypotheses)
        ranked_hypothesis_count += sum(1 for item in hypotheses if item.get("rank") is not None)
        counterfactual_count += nested_list_count(payload, "counterfactuals", hypotheses)
        falsifiable_trigger_count += nested_list_count(payload, "falsification_triggers", hypotheses)
        explicit_disagreement_count += list_count(payload.get("disagreement_with_price_only"))
        evidence_gap_count += list_count(payload.get("evidence_gaps"))
        uncertainty_decomposition_count += list_count(payload.get("uncertainty_decomposition"))
        generic_caution_phrase_count += generic_caution_count(payload)
        if not validate_provenance(artifact):
            provenance_link_count += 1
        future_data_metadata_count += count_future_data_metadata(payload)

    return {
        "input_artifact_count": len(artifacts),
        "source_artifact_path_count": source_path_count,
        "gotra_used_field_count": len(gotra_used_fields),
        "gotra_ignored_field_count": len(gotra_ignored_fields),
        "gotra_used_fields": sorted(gotra_used_fields),
        "gotra_ignored_fields": sorted(gotra_ignored_fields),
        "hypothesis_count": hypothesis_count,
        "ranked_hypothesis_count": ranked_hypothesis_count,
        "counterfactual_count": counterfactual_count,
        "falsifiable_trigger_count": falsifiable_trigger_count,
        "explicit_disagreement_count": explicit_disagreement_count,
        "evidence_gap_count": evidence_gap_count,
        "uncertainty_decomposition_count": uncertainty_decomposition_count,
        "price_only_disagreement_signal": explicit_disagreement_count > 0,
        "generic_caution_phrase_count": generic_caution_phrase_count,
        "provenance_link_count": provenance_link_count,
        "future_data_metadata_count": future_data_metadata_count,
    }


def information_gain_status(metrics: dict[str, Any]) -> str:
    if int(metrics["input_artifact_count"]) == 0:
        return STATUS_DATA_INSUFFICIENT
    if (
        int(metrics["hypothesis_count"]) < 1
        or int(metrics["ranked_hypothesis_count"]) < 1
        or int(metrics["counterfactual_count"]) < 1
        or int(metrics["falsifiable_trigger_count"]) < 1
        or int(metrics["explicit_disagreement_count"]) < 1
        or int(metrics["evidence_gap_count"]) < 1
        or int(metrics["uncertainty_decomposition_count"]) < 1
    ):
        return STATUS_LOW_INFORMATION_GAIN
    if int(metrics["generic_caution_phrase_count"]) > (
        int(metrics["hypothesis_count"]) + int(metrics["counterfactual_count"])
    ):
        return STATUS_LOW_INFORMATION_GAIN
    return "SUFFICIENT_FOR_FIXTURE_COMPARISON"


def base_summary(config: AuditConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "audit_run_id": config.audit_run_id,
        "audit_run_root": str(run_root),
        "audit_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "source_chain": {
            "source_artifact_path": "ksana/public research artifact fixture or export",
            "public_adapter_path": "gotra/ksana_public_adapter.py::adapt_ksana_public_research_artifacts",
            "gotra_consumed_path": (
                "scripts/baseline_v3_four_arm.py::filter_external_research_artifacts -> "
                "research_artifact_filter_result -> build_prompt_payload -> render_provider_prompt"
            ),
        },
        "input_artifact_count": 0,
        "source_artifact_path_count": 0,
        "gotra_used_field_count": 0,
        "gotra_ignored_field_count": 0,
        "gotra_used_fields": [],
        "gotra_ignored_fields": [],
        "hypothesis_count": 0,
        "ranked_hypothesis_count": 0,
        "counterfactual_count": 0,
        "falsifiable_trigger_count": 0,
        "explicit_disagreement_count": 0,
        "evidence_gap_count": 0,
        "uncertainty_decomposition_count": 0,
        "price_only_disagreement_signal": False,
        "generic_caution_phrase_count": 0,
        "provenance_link_count": 0,
        "future_data_metadata_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "information_gain_status": STATUS_DATA_INSUFFICIENT,
        "cognitive_lift_status": STATUS_DATA_INSUFFICIENT,
        "overall_status": STATUS_DATA_INSUFFICIENT,
        "blocker_reasons": [],
        "blocked_items": [],
        "non_claims": {
            "not_30d_forward_live_verdict": True,
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_gotra_ksana_alaya_superiority_conclusion": True,
        },
    }


def choose_status(
    *,
    metrics: dict[str, Any],
    schema_failures: list[dict[str, Any]],
    provenance_failures: list[dict[str, Any]],
    overclaim_failures: list[dict[str, Any]],
    load_errors: list[dict[str, Any]],
) -> tuple[str, str]:
    if load_errors or schema_failures:
        return STATUS_BLOCKED_SCHEMA, STATUS_BLOCKED_SCHEMA
    if provenance_failures:
        return STATUS_BLOCKED_PROVENANCE, STATUS_BLOCKED_PROVENANCE
    if overclaim_failures:
        return STATUS_BLOCKED_OVERCLAIM, STATUS_BLOCKED_OVERCLAIM
    info_status = information_gain_status(metrics)
    if info_status == "SUFFICIENT_FOR_FIXTURE_COMPARISON":
        return info_status, STATUS_READY
    return info_status, info_status


def write_outputs(config: AuditConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary_sha256 = sha256_file(summary_path)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "audit_run_id": config.audit_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": summary_sha256,
        "summary_digest_target": "summary.json final payload",
        "input_artifacts": [normalize_path(path) for path in config.input_artifacts],
        "manifest": normalize_path(config.manifest) if config.manifest else "",
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def run_audit(config: AuditConfig) -> dict[str, Any]:
    validate_run_id(config.audit_run_id)
    run_root = config.output_dir / config.audit_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root)
        summary.update(
            {
                "overall_status": STATUS_BLOCKED_SCHEMA,
                "cognitive_lift_status": STATUS_BLOCKED_SCHEMA,
                "information_gain_status": STATUS_BLOCKED_SCHEMA,
                "blocker_reasons": ["output_run_id_exists"],
                "blocked_items": [
                    make_blocker(str(run_root), "output_run_id_exists", "output run id exists")
                ],
            }
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    artifacts, load_errors = collect_artifacts(config)
    metrics = metrics_for_artifacts(artifacts)
    schema_failures = [failure for artifact in artifacts for failure in validate_schema(artifact)]
    provenance_failures = [
        failure for artifact in artifacts for failure in validate_provenance(artifact)
    ]
    overclaim_failures = scan_overclaim(artifacts)
    info_status, cognitive_status = choose_status(
        metrics=metrics,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        overclaim_failures=overclaim_failures,
        load_errors=load_errors,
    )
    blockers = load_errors + schema_failures + provenance_failures + overclaim_failures
    summary = base_summary(config, run_root=run_root)
    summary.update(metrics)
    summary.update(
        {
            "information_gain_status": info_status,
            "cognitive_lift_status": cognitive_status,
            "overall_status": cognitive_status,
            "blocker_reasons": [str(item.get("rule_id") or "") for item in blockers],
            "blocked_items": blockers,
        }
    )
    write_outputs(config, summary, run_root=run_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-artifact", action="append", type=Path, default=[])
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--audit-run-id",
        default=default_run_id(),
        help=f"Run id, must start with {RUN_ID_PREFIX}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ai_ksana_cognitive_lift_audit/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_audit(
        AuditConfig(
            audit_run_id=args.audit_run_id,
            output_dir=args.output_dir,
            input_artifacts=tuple(args.input_artifact),
            manifest=args.manifest,
            allow_overwrite=bool(args.allow_overwrite),
        )
    )
    return 0 if summary["overall_status"] in NON_BLOCKING_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
