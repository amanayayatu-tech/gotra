#!/usr/bin/env python3
"""GOTRA v3.7K ksana packet v2 front-half optimization validator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
from scripts import baseline_v3_6ai_ksana_cognitive_lift_audit as lift_audit  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7k.ksana_packet_v2_front_half_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7k.ksana_packet_v2_front_half_manifest.v1"
PACKET_SCHEMA = "gotra.ksana.research_packet.v2.front_half_fixture.v1"
RUN_ID_PREFIX = "baseline_v3_7k_ksana_packet_v2_front_half_"
SCRIPT_VERSION = "v3.7k-20260621"
EVIDENCE_LAYER = "engineering/local ksana packet v2 front-half optimization fixture-only"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY"
STATUS_LOW_INFORMATION_GAIN = "LOW_INFORMATION_GAIN"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"

NON_BLOCKING_STATUSES = {STATUS_READY, STATUS_LOW_INFORMATION_GAIN, STATUS_DATA_INSUFFICIENT}
BLOCKED_STATUSES = {STATUS_BLOCKED_SCHEMA, STATUS_BLOCKED_PROVENANCE, STATUS_BLOCKED_OVERCLAIM}

REQUIRED_PACKET_FIELDS = {
    "source_run_id",
    "source_artifact_path",
    "ticker",
    "decision_date",
    "research_mode",
    "ranked_hypotheses",
    "why_it_matters",
    "confidence",
    "falsification_triggers",
    "expected_observable_evidence",
    "counterfactuals",
    "disagreement_with_price_only",
    "evidence_gaps",
    "uncertainty_decomposition",
    "non_claims",
    "evidence_layer",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
}
REQUIRED_HYPOTHESIS_FIELDS = {
    "rank",
    "hypothesis",
    "confidence",
    "why_it_matters",
    "falsification_triggers",
    "expected_observable_evidence",
}
PROVENANCE_REQUIRED_FIELDS = {"source_run_id", "source_artifact_path"}
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
GENERIC_CAUTION_PATTERNS = lift_audit.GENERIC_CAUTION_PATTERNS


@dataclass(frozen=True)
class PacketV2Config:
    validator_run_id: str
    output_dir: Path
    packet_manifest: Path | None = None
    packet_artifacts: tuple[Path, ...] = ()
    baseline_manifest: Path | None = None
    baseline_artifacts: tuple[Path, ...] = ()
    allow_overwrite: bool = False


@dataclass(frozen=True)
class PacketArtifact:
    path: str
    payload: dict[str, Any]
    origin: str


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


def normalize_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    return claim_scan.normalize_scan_path(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def make_blocker(path: str | Path, rule_id: str, reason: str) -> dict[str, Any]:
    return {"path": normalize_path(path), "rule_id": rule_id, "reason": reason}


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def non_empty_mapping(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def list_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def artifacts_from_payload(payload: Any, *, path: str, origin: str) -> list[PacketArtifact]:
    if isinstance(payload, dict) and isinstance(payload.get("artifacts"), list):
        return [
            PacketArtifact(path=f"{path}#{index}", payload=dict(item), origin=origin)
            for index, item in enumerate(payload["artifacts"])
            if isinstance(item, dict)
        ]
    if isinstance(payload, dict) and isinstance(payload.get("packets"), list):
        return [
            PacketArtifact(path=f"{path}#{index}", payload=dict(item), origin=origin)
            for index, item in enumerate(payload["packets"])
            if isinstance(item, dict)
        ]
    if isinstance(payload, list):
        return [
            PacketArtifact(path=f"{path}#{index}", payload=dict(item), origin=origin)
            for index, item in enumerate(payload)
            if isinstance(item, dict)
        ]
    if isinstance(payload, dict):
        return [PacketArtifact(path=path, payload=dict(payload), origin=origin)]
    return []


def artifact_from_manifest_entry(entry: Any) -> list[PacketArtifact]:
    if not isinstance(entry, dict):
        return []
    path = normalize_path(str(entry.get("path") or entry.get("source_artifact_path") or ""))
    if "payload" in entry and isinstance(entry["payload"], dict):
        return [PacketArtifact(path=path or "manifest_payload", payload=dict(entry["payload"]), origin="manifest")]
    if path:
        if claim_scan.forbidden_path(path):
            return [
                PacketArtifact(
                    path=path,
                    payload={"_schema_error": "forbidden_artifact_path"},
                    origin="manifest_path",
                )
            ]
        file_path = (REPO_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)
        return artifacts_from_payload(load_json(file_path), path=path, origin="manifest_path")
    return []


def collect_artifacts(
    *,
    manifest: Path | None,
    artifacts: tuple[Path, ...],
) -> tuple[list[PacketArtifact], list[dict[str, Any]]]:
    collected: list[PacketArtifact] = []
    load_errors: list[dict[str, Any]] = []
    if manifest:
        manifest_path = normalize_path(manifest)
        if claim_scan.forbidden_path(manifest_path):
            load_errors.append(make_blocker(manifest_path, "forbidden_artifact_path", "manifest path is forbidden"))
        else:
            manifest_payload = load_json(manifest)
            if not isinstance(manifest_payload, dict):
                load_errors.append(make_blocker(manifest_path, "malformed_manifest_root", "manifest must be a JSON object"))
            else:
                entries = manifest_payload.get("artifacts", manifest_payload.get("packets", []))
                if not isinstance(entries, list):
                    load_errors.append(make_blocker(manifest_path, "malformed_manifest_artifacts", "manifest artifacts/packets must be a list"))
                    entries = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        load_errors.append(make_blocker(manifest_path, "malformed_manifest_artifact_entry", "manifest entry must be an object"))
                        continue
                    try:
                        collected.extend(artifact_from_manifest_entry(entry))
                    except (OSError, json.JSONDecodeError, ValueError) as exc:
                        load_errors.append(make_blocker(manifest_path, "artifact_load_error", str(exc)))
    for path in artifacts:
        normalized = normalize_path(path)
        if claim_scan.forbidden_path(normalized):
            load_errors.append(make_blocker(normalized, "forbidden_artifact_path", "input path is forbidden"))
            continue
        try:
            collected.extend(artifacts_from_payload(load_json(path), path=normalized, origin="file"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            load_errors.append(make_blocker(normalized, "artifact_load_error", str(exc)))
    return collected, load_errors


def ranked_hypotheses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("ranked_hypotheses")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    raw_legacy = payload.get("hypotheses")
    if isinstance(raw_legacy, list):
        return [dict(item) for item in raw_legacy if isinstance(item, dict)]
    return []


def claim_text_sources_from_value(
    *,
    artifact: PacketArtifact,
    field_path: str,
    value: Any,
) -> list[claim_scan.ScanSource]:
    if isinstance(value, str):
        return [claim_scan.ScanSource(path=f"{artifact.path}:{field_path}", text=value, origin=artifact.origin)]
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


def claim_scan_sources_for_artifact(artifact: PacketArtifact) -> list[claim_scan.ScanSource]:
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
    for key in ("ranked_hypotheses", "hypotheses", "counterfactuals", "evidence_gaps", "claims"):
        value = payload.get(key)
        if value:
            fields.append(json.dumps(value, ensure_ascii=False, default=str))
    return "\n".join(fields)


def generic_caution_count(payload: dict[str, Any]) -> int:
    text = text_for_caution_scan(payload).lower()
    return sum(len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in GENERIC_CAUTION_PATTERNS)


def validate_schema(artifact: PacketArtifact) -> list[dict[str, Any]]:
    payload = artifact.payload
    if payload.get("_schema_error"):
        return [make_blocker(artifact.path, str(payload["_schema_error"]), "artifact cannot be validated")]
    missing = sorted(REQUIRED_PACKET_FIELDS - set(payload))
    type_errors: list[str] = []

    if payload.get("schema") not in (None, PACKET_SCHEMA):
        type_errors.append("schema")
    if not is_non_empty_string(payload.get("source_run_id")):
        type_errors.append("source_run_id")
    if not is_non_empty_string(payload.get("source_artifact_path")):
        type_errors.append("source_artifact_path")
    if not is_non_empty_string(payload.get("ticker")):
        type_errors.append("ticker")
    if not is_non_empty_string(payload.get("decision_date")):
        type_errors.append("decision_date")
    else:
        try:
            date.fromisoformat(str(payload["decision_date"]))
        except ValueError:
            type_errors.append("decision_date")
    if not is_non_empty_string(payload.get("research_mode")):
        type_errors.append("research_mode")
    if not is_non_empty_string(payload.get("why_it_matters")):
        type_errors.append("why_it_matters")
    if "confidence" in payload and (not is_number(payload["confidence"]) or not 0 <= float(payload["confidence"]) <= 1):
        type_errors.append("confidence")

    if "ranked_hypotheses" in payload and not isinstance(payload["ranked_hypotheses"], list):
        type_errors.append("ranked_hypotheses")
    if "ranked_hypotheses" in payload and isinstance(payload["ranked_hypotheses"], list):
        if not payload["ranked_hypotheses"]:
            type_errors.append("ranked_hypotheses")
        for index, item in enumerate(payload["ranked_hypotheses"]):
            if not isinstance(item, dict):
                type_errors.append(f"ranked_hypotheses[{index}]")

    for key in (
        "falsification_triggers",
        "expected_observable_evidence",
        "counterfactuals",
        "evidence_gaps",
    ):
        if key in payload and not non_empty_list(payload[key]):
            type_errors.append(key)
    if "disagreement_with_price_only" in payload and not non_empty_list(payload["disagreement_with_price_only"]):
        type_errors.append("disagreement_with_price_only")
    if "uncertainty_decomposition" in payload and not (
        non_empty_mapping(payload["uncertainty_decomposition"]) or non_empty_list(payload["uncertainty_decomposition"])
    ):
        type_errors.append("uncertainty_decomposition")
    if "non_claims" in payload and not (non_empty_list(payload["non_claims"]) or non_empty_mapping(payload["non_claims"])):
        type_errors.append("non_claims")
    for key in ("provider_or_backend_called", "codex_cli_new_call", "formal_lite_entered"):
        if key in payload and payload[key] is not False:
            type_errors.append(key)

    hypothesis_missing: list[str] = []
    for index, item in enumerate(ranked_hypotheses(payload)):
        missing_keys = sorted(REQUIRED_HYPOTHESIS_FIELDS - set(item))
        if missing_keys:
            hypothesis_missing.append(f"ranked_hypotheses[{index}]:{','.join(missing_keys)}")
        if "rank" in item and not is_number(item["rank"]):
            type_errors.append(f"ranked_hypotheses[{index}].rank")
        if "confidence" in item:
            confidence = item["confidence"]
            if not is_number(confidence) or not 0 <= float(confidence) <= 1:
                type_errors.append(f"ranked_hypotheses[{index}].confidence")
        if "why_it_matters" in item and not isinstance(item["why_it_matters"], str):
            type_errors.append(f"ranked_hypotheses[{index}].why_it_matters")
        for key in ("falsification_triggers", "expected_observable_evidence"):
            if key in item and not non_empty_list(item[key]):
                type_errors.append(f"ranked_hypotheses[{index}].{key}")
    failures = missing + sorted(set(type_errors)) + hypothesis_missing
    if failures:
        return [
            make_blocker(
                artifact.path,
                "missing_or_invalid_packet_v2_schema_field",
                ",".join(failures),
            )
        ]
    return []


def validate_provenance(artifact: PacketArtifact) -> list[dict[str, Any]]:
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
    forbidden_paths = []
    for key in ("source_artifact_path",):
        top_path = str(payload.get(key) or "")
        provenance_path = str(provenance.get(key) or "")
        if top_path and claim_scan.forbidden_path(top_path):
            forbidden_paths.append(key)
        if provenance_path and claim_scan.forbidden_path(provenance_path):
            forbidden_paths.append(f"provenance.{key}")
    failures = missing + mismatches + empty_top_level
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


def scan_overclaim(artifacts: list[PacketArtifact]) -> list[dict[str, Any]]:
    sources = [source for artifact in artifacts for source in claim_scan_sources_for_artifact(artifact)]
    scan = claim_scan.scan_sources(sources)
    return scan["overclaim"] + scan["direct_llm"] + scan["maturity_gate"] + scan["short_horizon_as_30d"]


def nested_list_count(payload: dict[str, Any], key: str, hypotheses: list[dict[str, Any]]) -> int:
    total = list_count(payload.get(key))
    total += sum(list_count(item.get(key)) for item in hypotheses)
    return total


def metrics_for_artifacts(artifacts: list[PacketArtifact]) -> dict[str, Any]:
    hypothesis_count = 0
    ranked_hypothesis_count = 0
    counterfactual_count = 0
    falsifiable_trigger_count = 0
    explicit_disagreement_count = 0
    evidence_gap_count = 0
    uncertainty_decomposition_count = 0
    generic_caution_phrase_count = 0
    source_run_id = ""
    source_artifact_path = ""
    for artifact in artifacts:
        payload = artifact.payload
        source_run_id = source_run_id or str(payload.get("source_run_id") or "")
        source_artifact_path = source_artifact_path or str(payload.get("source_artifact_path") or "")
        hypotheses = ranked_hypotheses(payload)
        hypothesis_count += len(hypotheses)
        ranked_hypothesis_count += sum(1 for item in hypotheses if item.get("rank") is not None)
        counterfactual_count += nested_list_count(payload, "counterfactuals", hypotheses)
        falsifiable_trigger_count += nested_list_count(payload, "falsification_triggers", hypotheses)
        explicit_disagreement_count += list_count(payload.get("disagreement_with_price_only"))
        evidence_gap_count += list_count(payload.get("evidence_gaps"))
        uncertainty_decomposition_count += list_count(payload.get("uncertainty_decomposition"))
        generic_caution_phrase_count += generic_caution_count(payload)
    return {
        "input_artifact_count": len(artifacts),
        "source_run_id": source_run_id,
        "source_artifact_path": source_artifact_path,
        "hypothesis_count": hypothesis_count,
        "ranked_hypothesis_count": ranked_hypothesis_count,
        "counterfactual_count": counterfactual_count,
        "falsifiable_trigger_count": falsifiable_trigger_count,
        "explicit_disagreement_count": explicit_disagreement_count,
        "evidence_gap_count": evidence_gap_count,
        "uncertainty_decomposition_count": uncertainty_decomposition_count,
        "price_only_disagreement_signal": explicit_disagreement_count > 0,
        "generic_caution_phrase_count": generic_caution_phrase_count,
    }


def information_gain_score(metrics: dict[str, Any]) -> int:
    return (
        int(metrics["ranked_hypothesis_count"])
        + int(metrics["counterfactual_count"])
        + int(metrics["falsifiable_trigger_count"])
        + int(metrics["explicit_disagreement_count"])
        + int(metrics["evidence_gap_count"])
        + int(metrics["uncertainty_decomposition_count"])
        - int(metrics["generic_caution_phrase_count"])
    )


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
    return STATUS_READY


def choose_status(
    *,
    metrics: dict[str, Any],
    schema_failures: list[dict[str, Any]],
    provenance_failures: list[dict[str, Any]],
    overclaim_failures: list[dict[str, Any]],
    load_errors: list[dict[str, Any]],
) -> str:
    if load_errors or schema_failures:
        return STATUS_BLOCKED_SCHEMA
    if provenance_failures:
        return STATUS_BLOCKED_PROVENANCE
    if overclaim_failures:
        return STATUS_BLOCKED_OVERCLAIM
    return information_gain_status(metrics)


def base_summary(config: PacketV2Config, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "validator_run_id": config.validator_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "validator_status": STATUS_DATA_INSUFFICIENT,
        "packet_schema_valid": False,
        "source_run_id": "",
        "source_artifact_path": "",
        "input_artifact_count": 0,
        "baseline_artifact_count": 0,
        "hypothesis_count": 0,
        "ranked_hypothesis_count": 0,
        "counterfactual_count": 0,
        "falsifiable_trigger_count": 0,
        "explicit_disagreement_count": 0,
        "evidence_gap_count": 0,
        "uncertainty_decomposition_count": 0,
        "price_only_disagreement_signal": False,
        "generic_caution_phrase_count": 0,
        "baseline_information_gain_score": 0,
        "candidate_information_gain_score": 0,
        "information_gain_delta": 0,
        "overclaim_blocker_count": 0,
        "schema_blocker_count": 0,
        "provenance_blocker_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_allowed": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "blocker_reasons": [],
        "blocked_items": [],
        "non_claims": {
            "not_provider_run": True,
            "not_30d_forward_live_verdict": True,
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_gotra_ksana_alaya_superiority_conclusion": True,
        },
    }


def build_summary(config: PacketV2Config, *, run_root: Path) -> dict[str, Any]:
    packet_artifacts, packet_load_errors = collect_artifacts(
        manifest=config.packet_manifest,
        artifacts=config.packet_artifacts,
    )
    baseline_artifacts, baseline_load_errors = collect_artifacts(
        manifest=config.baseline_manifest,
        artifacts=config.baseline_artifacts,
    )
    metrics = metrics_for_artifacts(packet_artifacts)
    baseline_metrics = metrics_for_artifacts(baseline_artifacts)
    schema_failures = [failure for artifact in packet_artifacts for failure in validate_schema(artifact)]
    provenance_failures = [failure for artifact in packet_artifacts for failure in validate_provenance(artifact)]
    overclaim_failures = scan_overclaim(packet_artifacts + baseline_artifacts)
    load_errors = packet_load_errors + baseline_load_errors
    status = choose_status(
        metrics=metrics,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        overclaim_failures=overclaim_failures,
        load_errors=load_errors,
    )
    blockers = load_errors + schema_failures + provenance_failures + overclaim_failures
    summary = base_summary(config, run_root=run_root)
    summary.update(metrics)
    candidate_score = information_gain_score(metrics)
    baseline_score = information_gain_score(baseline_metrics)
    summary.update(
        {
            "validator_status": status,
            "packet_schema_valid": status in {STATUS_READY, STATUS_LOW_INFORMATION_GAIN},
            "baseline_artifact_count": int(baseline_metrics["input_artifact_count"]),
            "baseline_information_gain_score": baseline_score,
            "candidate_information_gain_score": candidate_score,
            "information_gain_delta": candidate_score - baseline_score,
            "overclaim_blocker_count": len(overclaim_failures),
            "schema_blocker_count": len(load_errors) + len(schema_failures),
            "provenance_blocker_count": len(provenance_failures),
            "blocker_reasons": [str(item.get("rule_id") or "") for item in blockers],
            "blocked_items": blockers,
        }
    )
    return summary


def write_outputs(config: PacketV2Config, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
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
        "summary_digest_target": "summary.json final payload",
        "packet_manifest": normalize_path(config.packet_manifest),
        "baseline_manifest": normalize_path(config.baseline_manifest),
        "packet_artifacts": [normalize_path(path) for path in config.packet_artifacts],
        "baseline_artifacts": [normalize_path(path) for path in config.baseline_artifacts],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def blocked_run_id_summary(config: PacketV2Config, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "validator_status": STATUS_BLOCKED_SCHEMA,
            "schema_blocker_count": 1,
            "blocker_reasons": ["output_run_id_exists"],
            "blocked_items": [make_blocker(run_root, "output_run_id_exists", "output run id exists")],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_validator(config: PacketV2Config) -> dict[str, Any]:
    validate_run_id(config.validator_run_id)
    run_root = config.output_dir / config.validator_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    summary = build_summary(config, run_root=run_root)
    write_outputs(config, summary, run_root=run_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-manifest", type=Path, default=None)
    parser.add_argument("--packet-artifact", action="append", type=Path, default=[])
    parser.add_argument("--baseline-manifest", type=Path, default=None)
    parser.add_argument("--baseline-artifact", action="append", type=Path, default=[])
    parser.add_argument("--validator-run-id", default=default_run_id())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_7k_ksana_packet_v2_front_half/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PacketV2Config:
    return PacketV2Config(
        validator_run_id=str(args.validator_run_id),
        output_dir=args.output_dir,
        packet_manifest=args.packet_manifest,
        packet_artifacts=tuple(args.packet_artifact or ()),
        baseline_manifest=args.baseline_manifest,
        baseline_artifacts=tuple(args.baseline_artifact or ()),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_validator(config_from_args(parse_args(argv)))
    return 0 if summary["validator_status"] in NON_BLOCKING_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
