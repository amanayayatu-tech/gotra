#!/usr/bin/env python3
"""GOTRA v3.5E matured forward-live outcome scorer/report generator."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver
from scripts import baseline_v3_four_arm as v3


SCORER_SCHEMA = "gotra.baseline_v3_5e.matured_outcome_scorer.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3_5e.matured_outcome_scorer_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_5e.matured_outcome_scorer_manifest.v1"
SCORER_RUN_ID_PREFIX = "baseline_v3_5e_matured_outcome_scorer_"
SCORER_SCRIPT_VERSION = "v3.5e-20260621"

STATUS_SCORED = "SCORED_OUTCOMES_AVAILABLE"
STATUS_DATA_NOT_MATURED = "DATA_NOT_MATURED"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_INSUFFICIENT_CLUSTER_COVERAGE = "INSUFFICIENT_CLUSTER_COVERAGE"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_FUTURE_DATA = "BLOCKED_FUTURE_DATA"
STATUS_BLOCKED_RUN_ID_EXISTS = "SCORER_BLOCKED_RUN_ID_EXISTS"
STATUS_FAIL = "SCORER_FAIL"

POLICY_RETURN_NOT_COMPUTED = "POLICY_RETURN_NOT_COMPUTED"
VALID_DIRECTIONS = {"long", "avoid", "neutral"}
DEFAULT_MIN_SCORED_OUTCOMES = 3
DEFAULT_MIN_CLUSTERS = 2

EXCLUDED_NOT_MATURED = "not_matured"
EXCLUDED_BLOCKED_DATA = "blocked_data"
EXCLUDED_BLOCKED_SOURCE_FUTURE_DATA = "blocked_source_future_data"
EXCLUDED_SOURCE_FUTURE_DATA = "source_future_data_violation"
EXCLUDED_PROVENANCE = "provenance_missing"
EXCLUDED_MISSING_OUTCOME_FIELD = "missing_outcome_field"
EXCLUDED_UNKNOWN_ACTUAL_DIRECTION = "unknown_actual_direction"
EXCLUDED_UNKNOWN_PREDICTED_DIRECTION = "unknown_predicted_direction"
EXCLUDED_NON_RESOLVER_ARTIFACT = "non_resolver_artifact"


@dataclass(frozen=True)
class ScorerConfig:
    input_roots: tuple[Path, ...]
    scorer_run_id: str
    output_dir: Path
    min_scored_outcomes: int = DEFAULT_MIN_SCORED_OUTCOMES
    min_clusters: int = DEFAULT_MIN_CLUSTERS
    allow_overwrite: bool = False


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(SCORER_RUN_ID_PREFIX):
        raise ValueError(f"scorer_run_id must start with {SCORER_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("scorer_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: ScorerConfig) -> None:
    validate_run_id(config.scorer_run_id)
    if not config.input_roots:
        raise ValueError("at least one input root is required")
    for root in config.input_roots:
        if not root.exists():
            raise FileNotFoundError(f"input root not found: {root}")
    if config.min_scored_outcomes <= 0:
        raise ValueError("min_scored_outcomes must be > 0")
    if config.min_clusters <= 0:
        raise ValueError("min_clusters must be > 0")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def blocked_run_id_summary(config: ScorerConfig, output_root: Path) -> dict[str, Any]:
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "scorer_run_root": str(output_root),
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_scorer(config: ScorerConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.scorer_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    candidates = find_candidate_json_paths(config.input_roots)
    outcome_paths = resolved_outcome_paths_from_candidates(candidates)
    summary_future_violations = future_data_violations_from_summaries(candidates)
    scored_rows: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    provenance_failures: list[dict[str, Any]] = []
    future_data_failures: list[dict[str, Any]] = []
    future_data_failure_keys: set[str] = set()
    resolved_outcome_count = 0

    for path in outcome_paths:
        try:
            record = load_json(path)
        except Exception as exc:  # noqa: BLE001 - surfaced as provenance-like invalid artifact.
            exclusions[EXCLUDED_NON_RESOLVER_ARTIFACT] += 1
            provenance_failures.append(
                {
                    "outcome_artifact": str(path),
                    "reason": "invalid_json",
                    "error": v3.redact_error(str(exc)),
                }
            )
            continue
        status = str(record.get("outcome_status") or "")
        if record.get("schema") != resolver.RESOLVER_SCHEMA:
            exclusions[EXCLUDED_NON_RESOLVER_ARTIFACT] += 1
            continue
        if status == resolver.STATUS_NOT_MATURED:
            exclusions[EXCLUDED_NOT_MATURED] += 1
            continue
        if status == resolver.STATUS_BLOCKED_DATA:
            exclusions[EXCLUDED_BLOCKED_DATA] += 1
            continue
        if status == resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA:
            exclusions[EXCLUDED_BLOCKED_SOURCE_FUTURE_DATA] += 1
            append_future_data_failure(
                future_data_failures,
                future_data_failure_keys,
                path=path,
                record=record,
                reason=resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA,
            )
            continue
        if status != resolver.STATUS_RESOLVED:
            exclusions[EXCLUDED_NON_RESOLVER_ARTIFACT] += 1
            continue
        resolved_outcome_count += 1
        if bool(record.get("source_future_data_violation")):
            exclusions[EXCLUDED_SOURCE_FUTURE_DATA] += 1
            append_future_data_failure(
                future_data_failures,
                future_data_failure_keys,
                path=path,
                record=record,
                reason=EXCLUDED_SOURCE_FUTURE_DATA,
            )
            continue
        outcome_field_error = missing_or_invalid_outcome_field_reason(record)
        if outcome_field_error:
            exclusions[EXCLUDED_MISSING_OUTCOME_FIELD] += 1
            continue
        actual_direction = str(record["actual_direction"])
        if actual_direction not in VALID_DIRECTIONS:
            exclusions[EXCLUDED_UNKNOWN_ACTUAL_DIRECTION] += 1
            continue
        source_payload, provenance_error = load_source_payload(record)
        if provenance_error is not None:
            exclusions[EXCLUDED_PROVENANCE] += 1
            provenance_failures.append(
                {
                    "outcome_artifact": str(path),
                    "source_decision_id": str(record.get("source_decision_id") or ""),
                    "reason": provenance_error,
                }
            )
            continue
        source_future_reasons = source_future_data_reasons_from_capture(source_payload)
        if source_future_reasons:
            exclusions[EXCLUDED_SOURCE_FUTURE_DATA] += 1
            append_future_data_failure(
                future_data_failures,
                future_data_failure_keys,
                path=path,
                record=record,
                reason="source_capture_future_data_violation",
                source_future_data_violation_reasons=source_future_reasons,
            )
            continue
        predicted_direction = predicted_direction_from_source(source_payload)
        if predicted_direction not in VALID_DIRECTIONS:
            exclusions[EXCLUDED_UNKNOWN_PREDICTED_DIRECTION] += 1
            continue
        actual_change = float(record["actual_change_pct"])
        expected_change = expected_change_from_source(source_payload)
        metric_available = expected_change is not None
        error = expected_change - actual_change if expected_change is not None else None
        scored_rows.append(
            {
                "outcome_artifact": str(path),
                "source_artifact_path": str(
                    (record.get("provenance") or {}).get("source_artifact_path") or ""
                ),
                "source_capture_run_id": str(
                    (record.get("provenance") or {}).get("source_capture_run_id") or ""
                ),
                "source_decision_id": str(record.get("source_decision_id") or ""),
                "ticker": str(record["ticker"]),
                "decision_date": str(record["decision_date"]),
                "horizon_days": int(record["horizon_days"]),
                "arm": str(record.get("arm") or ""),
                "input_layer": str(record.get("input_layer") or ""),
                "predicted_direction": predicted_direction,
                "actual_direction": actual_direction,
                "direction_hit": v3.direction_hit_for(
                    predicted_direction=predicted_direction,
                    actual_change_pct=actual_change,
                ),
                "expected_change_pct": expected_change,
                "actual_change_pct": actual_change,
                "metric_available": metric_available,
                "error": error,
                "absolute_error": abs(error) if error is not None else None,
                "squared_error": error * error if error is not None else None,
            }
        )

    summary = summary_for(
        config=config,
        output_root=output_root,
        candidate_json_count=len(candidates),
        outcome_artifact_count=len(outcome_paths),
        resolved_outcome_count=resolved_outcome_count,
        scored_rows=scored_rows,
        exclusions=exclusions,
        provenance_failures=provenance_failures,
        future_data_failures=future_data_failures,
        summary_future_data_violations=summary_future_violations,
        started_at=started_at,
        completed_at=datetime.now(UTC).replace(microsecond=0),
    )
    manifest = manifest_for(config=config, output_root=output_root)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "scored_outcomes.json").write_text(
        json.dumps(scored_rows, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def find_candidate_json_paths(input_roots: tuple[Path, ...]) -> list[Path]:
    paths: set[Path] = set()
    for root in input_roots:
        if root.is_file() and root.suffix.lower() == ".json":
            paths.add(root)
        elif root.is_dir():
            paths.update(root.glob("**/*.json"))
    return sorted(paths)


def resolved_outcome_paths_from_candidates(candidates: list[Path]) -> list[Path]:
    outcome_paths: set[Path] = set()
    for path in candidates:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == resolver.RESOLVER_SCHEMA:
            outcome_paths.add(path)
            continue
        for link in payload.get("provenance_links") or []:
            if not isinstance(link, dict):
                continue
            outcome_path = Path(str(link.get("outcome_artifact_path") or ""))
            if outcome_path.exists():
                outcome_paths.add(outcome_path)
    return sorted(outcome_paths)


def future_data_violations_from_summaries(candidates: list[Path]) -> int:
    count = 0
    for path in candidates:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == resolver.RESOLVER_SCHEMA:
            continue
        value = payload.get("future_data_violation_count")
        if isinstance(value, int | float) and math.isfinite(float(value)):
            count += int(value)
    return count


def append_future_data_failure(
    failures: list[dict[str, Any]],
    keys: set[str],
    *,
    path: Path,
    record: dict[str, Any],
    reason: str,
    source_future_data_violation_reasons: list[str] | None = None,
) -> None:
    key = future_data_failure_key(path=path, record=record)
    if key in keys:
        return
    keys.add(key)
    failure = {
        "violation_key": key,
        "outcome_artifact": str(path),
        "source_decision_id": str(record.get("source_decision_id") or ""),
        "reason": reason,
    }
    if source_future_data_violation_reasons:
        failure["source_future_data_violation_reasons"] = source_future_data_violation_reasons
    failures.append(failure)


def future_data_failure_key(*, path: Path, record: dict[str, Any]) -> str:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    source_id = str(record.get("source_decision_id") or provenance.get("source_decision_id") or "")
    artifact_ref = str(provenance.get("source_artifact_ref") or "")
    artifact_path = str(provenance.get("source_artifact_path") or "")
    if source_id and (artifact_ref or artifact_path):
        return f"{source_id}|{artifact_ref or artifact_path}"
    if source_id:
        return source_id
    return str(path)


def missing_or_invalid_outcome_field_reason(record: dict[str, Any]) -> str:
    for field in [
        "outcome_price",
        "decision_price",
        "actual_change_pct",
        "actual_direction",
    ]:
        if record.get(field) is None:
            return field
    for field in ["outcome_price", "decision_price", "actual_change_pct"]:
        try:
            value = float(record[field])
        except (TypeError, ValueError):
            return field
        if not math.isfinite(value):
            return field
    return ""


def load_source_payload(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return None, "missing_provenance"
    required = [
        "resolver_run_id",
        "source_capture_run_id",
        "source_decision_id",
        "source_artifact_path",
        "source_artifact_ref",
    ]
    missing = [field for field in required if not provenance.get(field)]
    if missing:
        return None, "missing_provenance_fields:" + ",".join(missing)
    if not record.get("resolver_run_id"):
        return None, "missing_resolver_run_id"
    if str(record.get("resolver_run_id")) != str(provenance.get("resolver_run_id")):
        return None, "resolver_run_id_mismatch"
    if not record.get("source_decision_id"):
        return None, "missing_source_decision_id"
    if str(record.get("source_decision_id")) != str(provenance.get("source_decision_id")):
        return None, "source_decision_id_mismatch"
    source_path = Path(str(provenance["source_artifact_path"]))
    artifact_ref = str(provenance["source_artifact_ref"])
    if not source_path_matches_ref(source_path, artifact_ref):
        return None, "source_artifact_path_ref_mismatch"
    if not source_path.exists():
        return None, "source_artifact_missing"
    try:
        source_payload = load_json(source_path)
    except Exception as exc:  # noqa: BLE001 - surfaced as provenance failure reason.
        return None, "source_artifact_invalid:" + v3.redact_error(str(exc))
    if source_payload.get("schema") != capture_v35a.CAPTURE_SCHEMA:
        return None, "source_artifact_schema_mismatch"
    if str(source_payload.get("run_id") or "") != str(provenance.get("source_capture_run_id")):
        return None, "source_capture_run_id_mismatch"
    expected_source_id = resolver.source_decision_id(source_payload, artifact_ref)
    if str(record.get("source_decision_id")) != expected_source_id:
        return None, "source_decision_id_recomputed_mismatch"
    identity_error = source_identity_mismatch(record, source_payload)
    if identity_error:
        return None, identity_error
    return source_payload, None


def source_path_matches_ref(source_path: Path, artifact_ref: str) -> bool:
    ref_path = Path(artifact_ref)
    if ref_path.is_absolute():
        return source_path == ref_path
    ref_parts = ref_path.parts
    if not ref_parts:
        return False
    source_parts = source_path.parts
    if len(source_parts) < len(ref_parts):
        return False
    return source_parts[-len(ref_parts) :] == ref_parts


def source_identity_mismatch(record: dict[str, Any], source_payload: dict[str, Any]) -> str:
    checks = [
        ("ticker", str(source_payload.get("ticker") or ""), str(record.get("ticker") or "")),
        ("arm", str(source_payload.get("arm") or ""), str(record.get("arm") or "")),
        (
            "input_layer",
            str(source_payload.get("input_layer") or ""),
            str(record.get("input_layer") or ""),
        ),
        (
            "decision_date",
            str(source_payload.get("decision_date_local") or source_payload.get("decision_date") or ""),
            str(record.get("decision_date") or ""),
        ),
        (
            "horizon_days",
            str(source_payload.get("horizon_days") or v3.WINDOW_DAYS),
            str(record.get("horizon_days") or ""),
        ),
    ]
    for field, source_value, record_value in checks:
        if source_value != record_value:
            return f"source_{field}_mismatch"
    return ""


def source_future_data_reasons_from_capture(source_payload: dict[str, Any] | None) -> list[str]:
    if not source_payload:
        return []
    try:
        decision_date = resolver.date_from_capture(
            source_payload,
            "decision_date_local",
            "decision_date",
        )
        latest_visible_date = resolver.date_from_capture(
            source_payload,
            "latest_visible_price_date",
            "decision_date_local",
        )
    except Exception as exc:  # noqa: BLE001 - invalid date provenance is a source guard failure.
        return ["source_future_data_guard_invalid_dates:" + v3.redact_error(str(exc))]
    return resolver.source_future_data_violation_reasons(
        payload=source_payload,
        decision_date=decision_date,
        latest_visible_date=latest_visible_date,
    )


def predicted_direction_from_source(source_payload: dict[str, Any] | None) -> str:
    if not source_payload:
        return ""
    decision = source_payload.get("decision")
    if isinstance(decision, dict):
        return str(decision.get("direction") or "")
    return str(source_payload.get("direction") or "")


def expected_change_from_source(source_payload: dict[str, Any] | None) -> float | None:
    if not source_payload:
        return None
    decision = source_payload.get("decision")
    candidates: list[Any] = []
    if isinstance(decision, dict):
        candidates.append(decision.get("expected_change_pct"))
    candidates.append(source_payload.get("expected_change_pct"))
    for value in candidates:
        if value in (None, ""):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            return numeric
    return None


def summary_for(
    *,
    config: ScorerConfig,
    output_root: Path,
    candidate_json_count: int,
    outcome_artifact_count: int,
    resolved_outcome_count: int,
    scored_rows: list[dict[str, Any]],
    exclusions: Counter[str],
    provenance_failures: list[dict[str, Any]],
    future_data_failures: list[dict[str, Any]],
    summary_future_data_violations: int,
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, Any]:
    scored_count = len(scored_rows)
    tickers = {str(row["ticker"]) for row in scored_rows}
    dates = {str(row["decision_date"]) for row in scored_rows}
    metric_rows = [row for row in scored_rows if row["metric_available"]]
    future_data_violation_count = len(
        {
            str(failure.get("violation_key") or failure.get("outcome_artifact") or "")
            for failure in future_data_failures
        }
    )
    future_data_blocker_count = future_data_violation_count + summary_future_data_violations
    status = scorer_status(
        resolved_outcome_count=resolved_outcome_count,
        scored_count=scored_count,
        ticker_count=len(tickers),
        future_data_violation_count=future_data_blocker_count,
        provenance_failure_count=len(provenance_failures),
        min_scored_outcomes=config.min_scored_outcomes,
        min_clusters=config.min_clusters,
    )
    direction_hit_rate = (
        sum(1 for row in scored_rows if bool(row["direction_hit"])) / scored_count
        if scored_count
        else None
    )
    mae = mean([float(row["absolute_error"]) for row in metric_rows])
    mse = mean([float(row["squared_error"]) for row in metric_rows])
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": status,
            "candidate_json_count": candidate_json_count,
            "outcome_artifact_count": outcome_artifact_count,
            "resolved_outcome_count": resolved_outcome_count,
            "scored_outcome_count": scored_count,
            "excluded_count_by_reason": dict(sorted(exclusions.items())),
            "ticker_count": len(tickers),
            "cluster_count": len(tickers),
            "date_count": len(dates),
            "direction_hit_rate": direction_hit_rate,
            "metric_available_count": len(metric_rows),
            "metric_unavailable_count": scored_count - len(metric_rows),
            "mae": mae,
            "mse": mse,
            "policy_return_status": POLICY_RETURN_NOT_COMPUTED,
            "policy_return_reason": (
                "v3.5E computes descriptive maturity/report metrics only; "
                "policy/reference return is deferred to a later preregistered verdict stage"
            ),
            "provenance_link_count": scored_count,
            "provenance_failure_count": len(provenance_failures),
            "provenance_failures": provenance_failures[:20],
            "future_data_violation_count": future_data_violation_count,
            "input_summary_future_data_violation_count": summary_future_data_violations,
            "future_data_blocker_count": future_data_blocker_count,
            "future_data_failures": future_data_failures[:20],
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
            "scorer_script_version": SCORER_SCRIPT_VERSION,
        }
    )
    return summary


def base_summary(*, config: ScorerConfig, output_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "scorer_run_id": config.scorer_run_id,
        "scorer_run_root": str(output_root),
        "input_roots": [str(path) for path in config.input_roots],
        "status": STATUS_FAIL,
        "evidence_layer": "matured outcome scorer engineering/local validation only",
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "resolved_outcome_count": 0,
        "scored_outcome_count": 0,
        "excluded_count_by_reason": {},
        "ticker_count": 0,
        "cluster_count": 0,
        "date_count": 0,
        "direction_hit_rate": None,
        "metric_available_count": 0,
        "metric_unavailable_count": 0,
        "mae": None,
        "mse": None,
        "policy_return_status": POLICY_RETURN_NOT_COMPUTED,
        "provenance_link_count": 0,
        "future_data_violation_count": 0,
        "input_summary_future_data_violation_count": 0,
        "future_data_blocker_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not formal-lite",
            "no full_gotra/deterministic/ksana winner verdict",
        ],
    }


def scorer_status(
    *,
    resolved_outcome_count: int,
    scored_count: int,
    ticker_count: int,
    future_data_violation_count: int,
    provenance_failure_count: int,
    min_scored_outcomes: int,
    min_clusters: int,
) -> str:
    if future_data_violation_count:
        return STATUS_BLOCKED_FUTURE_DATA
    if provenance_failure_count:
        return STATUS_BLOCKED_PROVENANCE
    if resolved_outcome_count == 0:
        return STATUS_DATA_NOT_MATURED
    if scored_count < min_scored_outcomes:
        return STATUS_DATA_INSUFFICIENT
    if ticker_count < min_clusters:
        return STATUS_INSUFFICIENT_CLUSTER_COVERAGE
    return STATUS_SCORED


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def manifest_for(config: ScorerConfig, output_root: Path) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "scorer_run_id": config.scorer_run_id,
        "scorer_run_root": str(output_root),
        "input_roots": [str(path) for path in config.input_roots],
        "min_scored_outcomes": config.min_scored_outcomes,
        "min_clusters": config.min_clusters,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "matured outcome scorer engineering/local validation only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", action="append", type=Path, required=True)
    parser.add_argument("--scorer-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--min-scored-outcomes", type=int, default=DEFAULT_MIN_SCORED_OUTCOMES)
    parser.add_argument("--min-clusters", type=int, default=DEFAULT_MIN_CLUSTERS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ScorerConfig:
    return ScorerConfig(
        input_roots=tuple(args.input_root),
        scorer_run_id=str(args.scorer_run_id),
        output_dir=args.output_dir,
        min_scored_outcomes=int(args.min_scored_outcomes),
        min_clusters=int(args.min_clusters),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_scorer(config_from_args(parse_args(argv)))
    return 0 if str(summary.get("status")) == STATUS_SCORED else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
