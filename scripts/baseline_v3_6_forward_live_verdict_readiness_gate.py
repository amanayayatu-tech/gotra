#!/usr/bin/env python3
"""GOTRA v3.6 forward-live verdict readiness gate."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_matured_outcome_scorer as scorer_v35e
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver
from scripts import baseline_v3_four_arm as v3


SUMMARY_SCHEMA = "gotra.baseline_v3_6.forward_live_verdict_readiness_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6.forward_live_verdict_readiness_manifest.v1"
READINESS_RUN_ID_PREFIX = "baseline_v3_6_forward_live_verdict_readiness_"
READINESS_SCRIPT_VERSION = "v3.6-20260621"

STATUS_READY = "READY_FOR_FORWARD_LIVE_VERDICT"
STATUS_DATA_NOT_MATURED = "DATA_NOT_MATURED"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_INSUFFICIENT_CLUSTER_COVERAGE = "INSUFFICIENT_CLUSTER_COVERAGE"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_FUTURE_DATA = "BLOCKED_FUTURE_DATA"
STATUS_BLOCKED_PAIRING = "BLOCKED_PAIRING"
STATUS_BLOCKED_RUN_ID_EXISTS = "READINESS_BLOCKED_RUN_ID_EXISTS"
STATUS_FAIL = "READINESS_GATE_FAIL"

DEFAULT_PRIMARY_INPUT_LAYER = "richer_research_packet"
DEFAULT_MIN_MATURED_OUTCOMES = 3
DEFAULT_MIN_PAIRED_POINTS = 3
DEFAULT_MIN_CLUSTERS = 2
DEFAULT_MIN_DATES = 2


@dataclass(frozen=True)
class ReadinessConfig:
    input_roots: tuple[Path, ...]
    readiness_run_id: str
    output_dir: Path
    primary_input_layer: str = DEFAULT_PRIMARY_INPUT_LAYER
    min_matured_outcomes: int = DEFAULT_MIN_MATURED_OUTCOMES
    min_paired_points: int = DEFAULT_MIN_PAIRED_POINTS
    min_clusters: int = DEFAULT_MIN_CLUSTERS
    min_dates: int = DEFAULT_MIN_DATES
    allow_overwrite: bool = False


@dataclass(frozen=True)
class DeterministicReference:
    key: tuple[str, str, int]
    path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class CleanFullGotraOutcome:
    key: tuple[str, str, int]
    path: Path
    record: dict[str, Any]
    source_payload: dict[str, Any]


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(READINESS_RUN_ID_PREFIX):
        raise ValueError(f"readiness_run_id must start with {READINESS_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("readiness_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: ReadinessConfig) -> None:
    validate_run_id(config.readiness_run_id)
    if not config.input_roots:
        raise ValueError("at least one input root is required")
    for root in config.input_roots:
        if not root.exists():
            raise FileNotFoundError(f"input root not found: {root}")
    if config.min_matured_outcomes <= 0:
        raise ValueError("min_matured_outcomes must be > 0")
    if config.min_paired_points <= 0:
        raise ValueError("min_paired_points must be > 0")
    if config.min_clusters <= 0:
        raise ValueError("min_clusters must be > 0")
    if config.min_dates <= 0:
        raise ValueError("min_dates must be > 0")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def find_candidate_json_paths(input_roots: tuple[Path, ...]) -> list[Path]:
    paths: set[Path] = set()
    for root in input_roots:
        if root.is_file() and root.suffix.lower() == ".json":
            paths.add(root)
        elif root.is_dir():
            paths.update(root.glob("**/*.json"))
    return sorted(paths)


def outcome_paths_from_candidates(candidates: list[Path]) -> list[Path]:
    paths: set[Path] = set()
    for path in candidates:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == resolver.RESOLVER_SCHEMA:
            paths.add(path)
            continue
        for link in payload.get("provenance_links") or []:
            if not isinstance(link, dict):
                continue
            linked = Path(str(link.get("outcome_artifact_path") or ""))
            if linked.exists():
                paths.add(linked)
    return sorted(paths)


def deterministic_reference_key(payload: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(payload.get("ticker") or ""),
        str(payload.get("decision_date_local") or payload.get("decision_date") or ""),
        int(payload.get("horizon_days") or v3.WINDOW_DAYS),
    )


def outcome_key(record: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(record.get("ticker") or ""),
        str(record.get("decision_date") or ""),
        int(record.get("horizon_days") or v3.WINDOW_DAYS),
    )


def deterministic_reference_identity_reason(payload: dict[str, Any]) -> str:
    if payload.get("schema") != capture_v35a.DETERMINISTIC_CAPTURE_SCHEMA:
        return "deterministic_reference_schema_mismatch"
    if payload.get("baseline") != "deterministic_price_only_baseline":
        return "deterministic_reference_baseline_mismatch"
    if payload.get("provider_or_backend_called") is not False:
        return "deterministic_reference_backend_called"
    if payload.get("llm_used") is not False:
        return "deterministic_reference_llm_used"
    if bool(payload.get("future_data_violation")):
        return "deterministic_reference_future_data_violation"
    if not payload.get("ticker") or not (
        payload.get("decision_date_local") or payload.get("decision_date")
    ):
        return "deterministic_reference_missing_identity"
    return ""


def collect_deterministic_references(
    candidates: list[Path],
) -> tuple[dict[tuple[str, str, int], DeterministicReference], Counter[str]]:
    references: dict[tuple[str, str, int], DeterministicReference] = {}
    failures: Counter[str] = Counter()
    for path in candidates:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") != capture_v35a.DETERMINISTIC_CAPTURE_SCHEMA:
            continue
        reason = deterministic_reference_identity_reason(payload)
        if reason:
            failures[reason] += 1
            continue
        key = deterministic_reference_key(payload)
        if key in references:
            failures["duplicate_deterministic_reference_key"] += 1
            continue
        references[key] = DeterministicReference(key=key, path=path, payload=payload)
    return references, failures


def scorer_summaries(candidates: list[Path]) -> list[tuple[Path, dict[str, Any]]]:
    summaries: list[tuple[Path, dict[str, Any]]] = []
    for path in candidates:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == scorer_v35e.SUMMARY_SCHEMA:
            summaries.append((path, payload))
    return summaries


def scorer_summary_success(summary: dict[str, Any], *, min_matured_outcomes: int) -> bool:
    if summary.get("status") != scorer_v35e.STATUS_SCORED:
        return False
    if int(summary.get("scored_outcome_count") or 0) < min_matured_outcomes:
        return False
    if int(summary.get("future_data_blocker_count") or 0):
        return False
    if int(summary.get("future_data_violation_count") or 0):
        return False
    if int(summary.get("provenance_failure_count") or 0):
        return False
    return True


def scorer_summary_failure_reasons(
    summaries: list[tuple[Path, dict[str, Any]]],
    *,
    min_matured_outcomes: int,
) -> Counter[str]:
    failures: Counter[str] = Counter()
    for _path, summary in summaries:
        status = str(summary.get("status") or "")
        if status != scorer_v35e.STATUS_SCORED:
            failures[f"status:{status or 'missing'}"] += 1
        if int(summary.get("scored_outcome_count") or 0) < min_matured_outcomes:
            failures["scored_outcome_count_below_readiness_minimum"] += 1
        if int(summary.get("future_data_blocker_count") or 0):
            failures["future_data_blocker_count_nonzero"] += 1
        if int(summary.get("future_data_violation_count") or 0):
            failures["future_data_violation_count_nonzero"] += 1
        if int(summary.get("provenance_failure_count") or 0):
            failures["provenance_failure_count_nonzero"] += 1
    return failures


def input_summary_future_data_count(candidates: list[Path]) -> int:
    count = 0
    for path in candidates:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") in {resolver.RESOLVER_SCHEMA, scorer_v35e.SUMMARY_SCHEMA}:
            continue
        value = payload.get("future_data_violation_count")
        if isinstance(value, int | float):
            count += int(value)
        blocker_value = payload.get("future_data_blocker_count")
        if isinstance(blocker_value, int | float):
            count += int(blocker_value)
    return count


def clean_source_payload_for_outcome(
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    source_payload, error = scorer_v35e.load_source_payload(record)
    if error:
        return None, error
    reasons = scorer_v35e.source_future_data_reasons_from_capture(source_payload)
    if reasons:
        return None, "source_capture_future_data_violation:" + ",".join(reasons)
    predicted_direction = scorer_v35e.predicted_direction_from_source(source_payload)
    if predicted_direction not in scorer_v35e.VALID_DIRECTIONS:
        return None, "unknown_predicted_direction"
    return source_payload, ""


def clean_full_gotra_outcome_reason(
    record: dict[str, Any],
    *,
    primary_input_layer: str,
) -> str:
    if record.get("schema") != resolver.RESOLVER_SCHEMA:
        return "outcome_schema_mismatch"
    if record.get("outcome_status") == resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA:
        return "outcome_blocked_source_future_data"
    if bool(record.get("source_future_data_violation")):
        return "outcome_source_future_data_violation"
    if record.get("outcome_status") != resolver.STATUS_RESOLVED:
        return "outcome_not_resolved"
    missing = scorer_v35e.missing_or_invalid_outcome_field_reason(record)
    if missing:
        return "outcome_missing_or_invalid_field:" + missing
    if str(record.get("actual_direction") or "") not in scorer_v35e.VALID_DIRECTIONS:
        return "outcome_unknown_direction"
    if str(record.get("arm") or "") != "full_gotra":
        return "not_full_gotra"
    if str(record.get("input_layer") or "") != primary_input_layer:
        return "full_gotra_input_layer_mismatch"
    if not record.get("scheduler_run_id") or not (record.get("provenance") or {}).get(
        "scheduler_run_id"
    ):
        return "missing_scheduler_provenance"
    if str(record.get("scheduler_run_id")) != str(
        (record.get("provenance") or {}).get("scheduler_run_id")
    ):
        return "scheduler_run_id_mismatch"
    if not record.get("resolver_run_id") or not (record.get("provenance") or {}).get(
        "resolver_run_id"
    ):
        return "missing_resolver_provenance"
    return ""


def collect_clean_full_gotra_outcomes(
    outcome_paths: list[Path],
    *,
    primary_input_layer: str,
) -> tuple[
    dict[tuple[str, str, int], CleanFullGotraOutcome],
    int,
    Counter[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    clean: dict[tuple[str, str, int], CleanFullGotraOutcome] = {}
    matured_count = 0
    failures: Counter[str] = Counter()
    provenance_failures: list[dict[str, Any]] = []
    future_failures: list[dict[str, Any]] = []
    for path in outcome_paths:
        try:
            record = load_json(path)
        except Exception as exc:  # noqa: BLE001 - summary keeps invalid artifact reason.
            failures["invalid_outcome_json"] += 1
            provenance_failures.append(
                {
                    "outcome_artifact": str(path),
                    "reason": "invalid_outcome_json",
                    "error": v3.redact_error(str(exc)),
                }
            )
            continue
        if record.get("schema") != resolver.RESOLVER_SCHEMA:
            continue
        if record.get("outcome_status") == resolver.STATUS_RESOLVED:
            matured_count += 1
        reason = clean_full_gotra_outcome_reason(
            record,
            primary_input_layer=primary_input_layer,
        )
        if reason == "outcome_not_resolved" or reason in {"not_full_gotra", "full_gotra_input_layer_mismatch"}:
            failures[reason] += 1
            continue
        if reason in {"outcome_blocked_source_future_data", "outcome_source_future_data_violation"}:
            failures[reason] += 1
            future_failures.append(
                {
                    "outcome_artifact": str(path),
                    "source_decision_id": str(record.get("source_decision_id") or ""),
                    "reason": reason,
                }
            )
            continue
        if reason:
            failures[reason] += 1
            provenance_failures.append(
                {
                    "outcome_artifact": str(path),
                    "source_decision_id": str(record.get("source_decision_id") or ""),
                    "reason": reason,
                }
            )
            continue
        source_payload, source_error = clean_source_payload_for_outcome(record)
        if source_error:
            if source_error.startswith("source_capture_future_data_violation"):
                failures["source_capture_future_data_violation"] += 1
                future_failures.append(
                    {
                        "outcome_artifact": str(path),
                        "source_decision_id": str(record.get("source_decision_id") or ""),
                        "reason": source_error,
                    }
                )
            else:
                failures[source_error] += 1
                provenance_failures.append(
                    {
                        "outcome_artifact": str(path),
                        "source_decision_id": str(record.get("source_decision_id") or ""),
                        "reason": source_error,
                    }
                )
            continue
        if source_payload is None:
            failures["missing_source_payload"] += 1
            continue
        key = outcome_key(record)
        if key in clean:
            failures["duplicate_full_gotra_key"] += 1
            provenance_failures.append(
                {
                    "outcome_artifact": str(path),
                    "source_decision_id": str(record.get("source_decision_id") or ""),
                    "reason": "duplicate_full_gotra_key",
                }
            )
            continue
        clean[key] = CleanFullGotraOutcome(
            key=key,
            path=path,
            record=record,
            source_payload=source_payload,
        )
    return clean, matured_count, failures, provenance_failures, future_failures


def blocking_reasons_for(
    *,
    status: str,
    matured_outcome_count: int,
    scored_outcome_count: int,
    deterministic_reference_available_count: int,
    full_gotra_available_count: int,
    paired_clean_count: int,
    cluster_count: int,
    date_count: int,
    future_data_violation_count: int,
    provenance_failure_count: int,
    scorer_summary_count: int,
    scorer_summary_success_count: int,
    scorer_summary_failures: Counter[str],
    deterministic_failures: Counter[str],
    outcome_failures: Counter[str],
    min_matured_outcomes: int,
    min_paired_points: int,
    min_clusters: int,
    min_dates: int,
) -> list[str]:
    reasons: list[str] = []
    if future_data_violation_count:
        reasons.append("future_data_violation_detected")
    if provenance_failure_count:
        reasons.append("provenance_failure_detected")
    if scorer_summary_count == 0:
        reasons.append("missing_matured_outcome_scorer_summary")
    elif scorer_summary_success_count == 0:
        reasons.append("missing_successful_matured_outcome_scorer_summary")
    if matured_outcome_count == 0:
        reasons.append("no_resolved_mature_outcomes")
    if scored_outcome_count < min_matured_outcomes:
        reasons.append("scored_outcome_count_below_minimum")
    if deterministic_reference_available_count == 0:
        reasons.append("missing_deterministic_reference")
    if full_gotra_available_count == 0:
        reasons.append("missing_full_gotra_outcomes")
    if paired_clean_count == 0:
        reasons.append("no_clean_deterministic_full_gotra_pairs")
    elif paired_clean_count < min_paired_points:
        reasons.append("paired_clean_count_below_minimum")
    if cluster_count < min_clusters:
        reasons.append("cluster_count_below_minimum")
    if date_count < min_dates:
        reasons.append("date_count_below_minimum")
    for reason, count in sorted(deterministic_failures.items()):
        if count:
            reasons.append(f"deterministic_reference:{reason}")
    for reason, count in sorted(scorer_summary_failures.items()):
        if count:
            reasons.append(f"scorer_summary:{reason}")
    for reason, count in sorted(outcome_failures.items()):
        if count and reason not in {"outcome_not_resolved", "not_full_gotra", "full_gotra_input_layer_mismatch"}:
            reasons.append(f"outcome:{reason}")
    if status == STATUS_READY:
        return []
    return sorted(set(reasons))


def readiness_status(
    *,
    matured_outcome_count: int,
    scored_outcome_count: int,
    deterministic_reference_available_count: int,
    full_gotra_available_count: int,
    paired_clean_count: int,
    cluster_count: int,
    date_count: int,
    future_data_violation_count: int,
    provenance_failure_count: int,
    scorer_summary_success_count: int,
    min_matured_outcomes: int,
    min_paired_points: int,
    min_clusters: int,
    min_dates: int,
) -> str:
    if future_data_violation_count:
        return STATUS_BLOCKED_FUTURE_DATA
    if provenance_failure_count or scorer_summary_success_count == 0:
        return STATUS_BLOCKED_PROVENANCE
    if matured_outcome_count == 0:
        return STATUS_DATA_NOT_MATURED
    if deterministic_reference_available_count == 0 or full_gotra_available_count == 0 or paired_clean_count == 0:
        return STATUS_BLOCKED_PAIRING
    if cluster_count < min_clusters:
        return STATUS_INSUFFICIENT_CLUSTER_COVERAGE
    if (
        scored_outcome_count < min_matured_outcomes
        or paired_clean_count < min_paired_points
        or date_count < min_dates
    ):
        return STATUS_DATA_INSUFFICIENT
    return STATUS_READY


def base_summary(*, config: ReadinessConfig, output_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "readiness_run_id": config.readiness_run_id,
        "readiness_run_root": str(output_root),
        "status": STATUS_FAIL,
        "evidence_layer": "readiness-gate engineering/local validation only",
        "input_roots": [str(path) for path in config.input_roots],
        "matured_outcome_count": 0,
        "scored_outcome_count": 0,
        "ticker_count": 0,
        "cluster_count": 0,
        "date_count": 0,
        "paired_candidate_count": 0,
        "paired_clean_count": 0,
        "deterministic_reference_available_count": 0,
        "full_gotra_available_count": 0,
        "future_data_violation_count": 0,
        "provenance_link_count": 0,
        "provenance_failure_count": 0,
        "bootstrap_eligible": False,
        "hac_eligible": False,
        "blocking_reasons": [],
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not formal-lite",
            "not a forward-live verdict",
            "no full_gotra/deterministic/ksana winner verdict",
        ],
    }


def blocked_run_id_summary(config: ReadinessConfig, output_root: Path) -> dict[str, Any]:
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocking_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_readiness_gate(config: ReadinessConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.readiness_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    candidates = find_candidate_json_paths(config.input_roots)
    references, deterministic_failures = collect_deterministic_references(candidates)
    outcome_paths = outcome_paths_from_candidates(candidates)
    (
        full_outcomes,
        matured_outcome_count,
        outcome_failures,
        provenance_failures,
        future_failures,
    ) = collect_clean_full_gotra_outcomes(
        outcome_paths,
        primary_input_layer=config.primary_input_layer,
    )
    summaries = scorer_summaries(candidates)
    successful_scorer_summaries = [
        (path, summary)
        for path, summary in summaries
        if scorer_summary_success(
            summary,
            min_matured_outcomes=config.min_matured_outcomes,
        )
    ]
    scorer_summary_failures = scorer_summary_failure_reasons(
        summaries,
        min_matured_outcomes=config.min_matured_outcomes,
    )
    scorer_summary_future = sum(
        int(summary.get("future_data_blocker_count") or summary.get("future_data_violation_count") or 0)
        for _path, summary in summaries
    )
    scorer_summary_provenance_failures = sum(
        int(summary.get("provenance_failure_count") or 0) for _path, summary in summaries
    )
    scorer_prerequisite_failure_count = 0 if successful_scorer_summaries else 1
    input_summary_future = input_summary_future_data_count(candidates)
    paired_keys = sorted(set(references) & set(full_outcomes))
    paired_candidate_count = min(len(references), len(full_outcomes))
    paired_clean_count = len(paired_keys)
    paired_clean_records = [full_outcomes[key] for key in paired_keys]
    tickers = {key[0] for key in paired_keys}
    dates = {key[1] for key in paired_keys}
    deterministic_future_failures = deterministic_failures.get(
        "deterministic_reference_future_data_violation",
        0,
    )
    future_data_violation_count = (
        len(future_failures)
        + deterministic_future_failures
        + scorer_summary_future
        + input_summary_future
    )
    provenance_failure_count = (
        len(provenance_failures)
        + scorer_summary_provenance_failures
        + scorer_prerequisite_failure_count
    )
    scored_outcome_count = len(full_outcomes)
    status = readiness_status(
        matured_outcome_count=matured_outcome_count,
        scored_outcome_count=scored_outcome_count,
        deterministic_reference_available_count=len(references),
        full_gotra_available_count=len(full_outcomes),
        paired_clean_count=paired_clean_count,
        cluster_count=len(tickers),
        date_count=len(dates),
        future_data_violation_count=future_data_violation_count,
        provenance_failure_count=provenance_failure_count,
        scorer_summary_success_count=len(successful_scorer_summaries),
        min_matured_outcomes=config.min_matured_outcomes,
        min_paired_points=config.min_paired_points,
        min_clusters=config.min_clusters,
        min_dates=config.min_dates,
    )
    bootstrap_eligible = paired_clean_count >= config.min_paired_points and len(tickers) >= config.min_clusters
    hac_eligible = paired_clean_count >= config.min_paired_points and len(dates) >= config.min_dates
    blocking_reasons = blocking_reasons_for(
        status=status,
        matured_outcome_count=matured_outcome_count,
        scored_outcome_count=scored_outcome_count,
        deterministic_reference_available_count=len(references),
        full_gotra_available_count=len(full_outcomes),
        paired_clean_count=paired_clean_count,
        cluster_count=len(tickers),
        date_count=len(dates),
        future_data_violation_count=future_data_violation_count,
        provenance_failure_count=provenance_failure_count,
        scorer_summary_count=len(summaries),
        scorer_summary_success_count=len(successful_scorer_summaries),
        scorer_summary_failures=scorer_summary_failures,
        deterministic_failures=deterministic_failures,
        outcome_failures=outcome_failures,
        min_matured_outcomes=config.min_matured_outcomes,
        min_paired_points=config.min_paired_points,
        min_clusters=config.min_clusters,
        min_dates=config.min_dates,
    )
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": status,
            "candidate_json_count": len(candidates),
            "outcome_artifact_count": len(outcome_paths),
            "matured_outcome_count": matured_outcome_count,
            "scored_outcome_count": scored_outcome_count,
            "ticker_count": len(tickers),
            "cluster_count": len(tickers),
            "date_count": len(dates),
            "paired_candidate_count": paired_candidate_count,
            "paired_clean_count": paired_clean_count,
            "paired_clean_keys": [
                {"ticker": key[0], "decision_date": key[1], "horizon_days": key[2]}
                for key in paired_keys[:50]
            ],
            "deterministic_reference_available_count": len(references),
            "full_gotra_available_count": len(full_outcomes),
            "future_data_violation_count": future_data_violation_count,
            "future_data_failures": future_failures[:20],
            "deterministic_reference_future_data_violation_count": deterministic_future_failures,
            "input_summary_future_data_violation_count": input_summary_future,
            "scorer_summary_future_data_violation_count": scorer_summary_future,
            "provenance_link_count": len(paired_clean_records),
            "provenance_failure_count": provenance_failure_count,
            "provenance_failures": provenance_failures[:20],
            "scorer_summary_count": len(summaries),
            "scorer_summary_success_count": len(successful_scorer_summaries),
            "scorer_summary_failure_counts": dict(sorted(scorer_summary_failures.items())),
            "scorer_summary_paths": [str(path) for path, _summary in summaries],
            "successful_scorer_summary_paths": [
                str(path) for path, _summary in successful_scorer_summaries
            ],
            "deterministic_reference_failure_counts": dict(sorted(deterministic_failures.items())),
            "outcome_failure_counts": dict(sorted(outcome_failures.items())),
            "bootstrap_eligible": bootstrap_eligible,
            "bootstrap_eligibility_reason": (
                "eligible" if bootstrap_eligible else "requires paired_clean_count and cluster_count minimums"
            ),
            "hac_eligible": hac_eligible,
            "hac_eligibility_reason": (
                "eligible" if hac_eligible else "requires paired_clean_count and date_count minimums"
            ),
            "blocking_reasons": blocking_reasons,
            "primary_input_layer": config.primary_input_layer,
            "min_matured_outcomes": config.min_matured_outcomes,
            "min_paired_points": config.min_paired_points,
            "min_clusters": config.min_clusters,
            "min_dates": config.min_dates,
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
            "readiness_script_version": READINESS_SCRIPT_VERSION,
        }
    )
    manifest = manifest_for(config=config, output_root=output_root, summary=summary)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(
    *,
    config: ReadinessConfig,
    output_root: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "readiness_run_id": config.readiness_run_id,
        "readiness_run_root": str(output_root),
        "input_roots": [str(path) for path in config.input_roots],
        "status": summary["status"],
        "primary_input_layer": config.primary_input_layer,
        "min_matured_outcomes": config.min_matured_outcomes,
        "min_paired_points": config.min_paired_points,
        "min_clusters": config.min_clusters,
        "min_dates": config.min_dates,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "readiness-gate engineering/local validation only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", action="append", type=Path, required=True)
    parser.add_argument("--readiness-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--primary-input-layer", default=DEFAULT_PRIMARY_INPUT_LAYER)
    parser.add_argument("--min-matured-outcomes", type=int, default=DEFAULT_MIN_MATURED_OUTCOMES)
    parser.add_argument("--min-paired-points", type=int, default=DEFAULT_MIN_PAIRED_POINTS)
    parser.add_argument("--min-clusters", type=int, default=DEFAULT_MIN_CLUSTERS)
    parser.add_argument("--min-dates", type=int, default=DEFAULT_MIN_DATES)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ReadinessConfig:
    return ReadinessConfig(
        input_roots=tuple(args.input_root),
        readiness_run_id=str(args.readiness_run_id),
        output_dir=args.output_dir,
        primary_input_layer=str(args.primary_input_layer),
        min_matured_outcomes=int(args.min_matured_outcomes),
        min_paired_points=int(args.min_paired_points),
        min_clusters=int(args.min_clusters),
        min_dates=int(args.min_dates),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_readiness_gate(config_from_args(parse_args(argv)))
    return 0 if str(summary.get("status")) == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
