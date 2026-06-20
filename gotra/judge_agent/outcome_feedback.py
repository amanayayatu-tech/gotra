"""Outcome-derived feedback artifact production for GOTRA v3 harnesses."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from gotra.judge_agent.auto_quarantine import (
    PREDICTION_ID_KEYS,
    extract_observed_return,
    extract_string_value,
    is_resolved_prediction,
    lookup_nested_value,
)
from gotra.judge_agent.judge_agent import stable_json_hash


PRODUCER_SCHEMA_VERSION = "gotra.outcome_feedback.v1"
FEEDBACK_SOURCE_KINDS = {"outcome_feedback", "realized_error_feedback"}
FORBIDDEN_FEEDBACK_ARTIFACT_FIELDS = {
    "current_actual_return",
    "current_step_output",
    "future_return",
    "outcome_after_current_decision",
    "realized_after_current_decision",
    "same_date_future_outcome",
}

TICKER_KEYS = ("ticker", "symbol", "asset", "asset_symbol")
INPUT_LAYER_KEYS = ("input_layer", "inputLayer")
RUN_ID_KEYS = ("source_run_id", "sourceRunId", "run_id", "runId", "cycleId")
STEP_ID_KEYS = ("source_step_id", "sourceStepId", "step_id", "stepId")
DECISION_DATE_KEYS = ("source_decision_date", "decision_date", "decisionDate", "as_of_date", "asOfDate")
HORIZON_END_KEYS = (
    "source_horizon_end_date",
    "horizon_end_date",
    "horizonEndDate",
    "window_end_date",
    "windowEndDate",
)
AVAILABILITY_KEYS = (
    "availability_date",
    "outcome_availability_date",
    "outcomeAvailabilityDate",
    "observed_at",
    "observedAt",
    "resolved_at",
    "resolvedAt",
)
PRIOR_PREDICTION_KEYS = (
    "prior_prediction",
    "priorPrediction",
    "expected_change_pct",
    "expectedChangePct",
    "expected_return",
    "expectedReturn",
)
ERROR_KEYS = ("error", "realized_error", "realizedError", "prediction_error", "predictionError")
MSE_KEYS = ("mse", "squared_error", "squaredError")
SOURCE_KIND_KEYS = ("feedback_source_kind", "feedbackSourceKind", "source_kind", "sourceKind")
SOURCE_GATE_KEYS = ("source_gate_id", "sourceGateId", "gate_id", "gateId")
SOURCE_KNOWLEDGE_KEYS = ("source_knowledge_id", "sourceKnowledgeId", "knowledge_id", "knowledgeId")
JUDGE_HASH_KEYS = ("judge_decision_hash", "judgeDecisionHash", "decision_hash", "decisionHash")
JUDGE_PROVENANCE_KEYS = ("judge_provenance_ref", "judgeProvenanceRef", "provenance_ref", "provenanceRef")


class ResolvedPredictionClient(Protocol):
    """Read-only adapter for resolved prediction records."""

    def list_resolved_predictions(self) -> Sequence[Mapping[str, Any]]:
        """Return prediction records with observed outcomes when available."""


@dataclass(frozen=True)
class OutcomeFeedbackGenerationResult:
    """Generated feedback artifacts and production diagnostics."""

    artifacts: tuple[dict[str, Any], ...]
    diagnostics: dict[str, int | str]
    skipped: tuple[dict[str, str], ...] = field(default_factory=tuple)


def generate_outcome_feedback_from_client(
    client: ResolvedPredictionClient,
    *,
    current_run_id: str = "",
    generated_at: datetime | None = None,
) -> OutcomeFeedbackGenerationResult:
    """Generate outcome feedback artifacts from a read-only prediction client."""

    return generate_outcome_feedback_artifacts(
        client.list_resolved_predictions(),
        current_run_id=current_run_id,
        generated_at=generated_at,
    )


def generate_outcome_feedback_artifacts(
    predictions: Iterable[Mapping[str, Any]],
    *,
    current_run_id: str = "",
    generated_at: datetime | None = None,
) -> OutcomeFeedbackGenerationResult:
    """Generate v3-compatible true-independent feedback artifacts from resolved predictions."""

    generated_at = generated_at or datetime.now(UTC)
    artifacts: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    diagnostics: dict[str, int | str] = {
        "producer_schema_version": PRODUCER_SCHEMA_VERSION,
        "input_prediction_count": 0,
        "generated_artifact_count": 0,
        "rejected_prediction_count": 0,
        "rejected_unresolved_count": 0,
        "rejected_schema_count": 0,
        "rejected_nonfinite_count": 0,
        "rejected_inconsistent_numeric_count": 0,
        "rejected_future_data_count": 0,
        "rejected_current_run_count": 0,
        "rejected_duplicate_count": 0,
    }

    for prediction in predictions:
        diagnostics["input_prediction_count"] = int(diagnostics["input_prediction_count"]) + 1
        if not is_resolved_prediction(prediction):
            _reject(skipped, diagnostics, prediction, "unresolved", "rejected_unresolved_count")
            continue
        try:
            artifact = outcome_feedback_artifact_for_prediction(
                prediction,
                current_run_id=current_run_id,
                generated_at=generated_at,
            )
        except OutcomeFeedbackRejection as rejection:
            _reject(skipped, diagnostics, prediction, rejection.reason, rejection.counter)
            continue
        feedback_ref = str(artifact["feedback_ref"])
        if feedback_ref in seen_refs:
            _reject(skipped, diagnostics, prediction, "duplicate_feedback_ref", "rejected_duplicate_count")
            continue
        seen_refs.add(feedback_ref)
        artifacts.append(artifact)

    diagnostics["generated_artifact_count"] = len(artifacts)
    diagnostics["rejected_prediction_count"] = int(diagnostics["input_prediction_count"]) - len(artifacts)
    return OutcomeFeedbackGenerationResult(
        artifacts=tuple(artifacts),
        diagnostics=diagnostics,
        skipped=tuple(skipped),
    )


def outcome_feedback_artifact_for_prediction(
    prediction: Mapping[str, Any],
    *,
    current_run_id: str = "",
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert one resolved prediction into one strict v3 feedback artifact."""

    forbidden = sorted(FORBIDDEN_FEEDBACK_ARTIFACT_FIELDS.intersection(prediction.keys()))
    if forbidden:
        raise OutcomeFeedbackRejection("forbidden_future_field", "rejected_future_data_count")

    generated_at = generated_at or datetime.now(UTC)
    prediction_id = _required_text(prediction, PREDICTION_ID_KEYS, "prediction_id")
    ticker = _required_text(prediction, TICKER_KEYS, "ticker")
    input_layer = _optional_text(prediction, INPUT_LAYER_KEYS) or "*"
    source_run_id = _required_text(prediction, RUN_ID_KEYS, "source_run_id")
    if current_run_id and source_run_id == current_run_id:
        raise OutcomeFeedbackRejection("source_run_id_matches_current_run_id", "rejected_current_run_count")
    source_step_id = _optional_text(prediction, STEP_ID_KEYS) or prediction_id
    source_decision_date = _required_date(prediction, DECISION_DATE_KEYS, "source_decision_date")
    source_horizon_end_date = _required_date(prediction, HORIZON_END_KEYS, "source_horizon_end_date")
    availability_date = _required_date(prediction, AVAILABILITY_KEYS, "availability_date")
    if source_decision_date >= source_horizon_end_date or availability_date < source_horizon_end_date:
        raise OutcomeFeedbackRejection("invalid_feedback_temporal_order", "rejected_future_data_count")

    actual_return = _finite_number(extract_observed_return(prediction), "actual_return")
    prior_prediction = _finite_number(
        lookup_nested_value(prediction, PRIOR_PREDICTION_KEYS),
        "prior_prediction",
    )
    error = actual_return - prior_prediction
    supplied_error = lookup_nested_value(prediction, ERROR_KEYS)
    if supplied_error is not None and abs(_finite_number(supplied_error, "error") - error) > 1e-6:
        raise OutcomeFeedbackRejection("inconsistent_error", "rejected_inconsistent_numeric_count")
    mse = error * error
    supplied_mse = lookup_nested_value(prediction, MSE_KEYS)
    if supplied_mse is not None and abs(_finite_number(supplied_mse, "mse") - mse) > 1e-6:
        raise OutcomeFeedbackRejection("inconsistent_mse", "rejected_inconsistent_numeric_count")

    source_kind = _optional_text(prediction, SOURCE_KIND_KEYS) or "outcome_feedback"
    if source_kind not in FEEDBACK_SOURCE_KINDS:
        raise OutcomeFeedbackRejection("unsupported_feedback_source_kind", "rejected_schema_count")

    feedback_ref = stable_feedback_ref(
        ticker=ticker,
        input_layer=input_layer,
        source_decision_date=source_decision_date,
        prediction_id=prediction_id,
    )
    artifact: dict[str, Any] = {
        "producer_schema_version": PRODUCER_SCHEMA_VERSION,
        "ticker": ticker,
        "input_layer": input_layer,
        "feedback_ref": feedback_ref,
        "feedback_source_kind": source_kind,
        "availability_date": availability_date.isoformat(),
        "source_run_id": source_run_id,
        "source_step_id": source_step_id,
        "source_decision_date": source_decision_date.isoformat(),
        "source_horizon_end_date": source_horizon_end_date.isoformat(),
        "actual_return": round(actual_return, 10),
        "prior_prediction": round(prior_prediction, 10),
        "error": round(error, 10),
        "mse": round(mse, 10),
        "summary": _summary(prediction, ticker=ticker, source_kind=source_kind, error=error),
        "source_prediction_id": prediction_id,
        "source_gate_id": _optional_text(prediction, SOURCE_GATE_KEYS),
        "source_knowledge_id": _optional_text(prediction, SOURCE_KNOWLEDGE_KEYS),
        "judge_provenance_ref": _optional_text(prediction, JUDGE_PROVENANCE_KEYS),
        "judge_decision_hash": _optional_text(prediction, JUDGE_HASH_KEYS),
        "generated_at_utc": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    artifact["provenance_hash"] = stable_json_hash(
        {key: value for key, value in artifact.items() if key not in {"generated_at_utc", "provenance_hash"}}
    )
    return artifact


class OutcomeFeedbackRejection(ValueError):
    """Raised when a prediction cannot safely produce feedback."""

    def __init__(self, reason: str, counter: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.counter = counter


def write_feedback_artifacts_jsonl(
    path: str | Path,
    artifacts: Sequence[Mapping[str, Any]],
    *,
    append: bool = True,
) -> Path:
    """Append generated feedback artifacts to a JSONL file."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "x"
    with output_path.open(mode, encoding="utf-8") as handle:
        for artifact in artifacts:
            handle.write(json.dumps(dict(artifact), ensure_ascii=False, sort_keys=True) + "\n")
    return output_path


def load_predictions_file(path: str | Path) -> list[dict[str, Any]]:
    """Load local prediction records from JSON or JSONL."""

    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("predictions", payload.get("items", []))
    if not isinstance(payload, list):
        raise ValueError("prediction file must be a list or {'predictions': [...]}")
    return [dict(item) for item in payload if isinstance(item, dict)]


def stable_feedback_ref(
    *,
    ticker: str,
    input_layer: str,
    source_decision_date: date,
    prediction_id: str,
) -> str:
    return ":".join(
        [
            "outcome",
            _slug(ticker),
            _slug(input_layer),
            source_decision_date.isoformat(),
            _slug(prediction_id),
        ]
    )


def _reject(
    skipped: list[dict[str, str]],
    diagnostics: dict[str, int | str],
    prediction: Mapping[str, Any],
    reason: str,
    counter: str,
) -> None:
    diagnostics[counter] = int(diagnostics[counter]) + 1
    skipped.append(
        {
            "prediction_id": extract_string_value(prediction, PREDICTION_ID_KEYS) or "",
            "reason": reason,
        }
    )


def _required_text(prediction: Mapping[str, Any], keys: Sequence[str], field_name: str) -> str:
    value = _optional_text(prediction, keys)
    if value is None:
        raise OutcomeFeedbackRejection(f"missing_{field_name}", "rejected_schema_count")
    return value


def _optional_text(prediction: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    value = extract_string_value(prediction, keys)
    return value or None


def _required_date(prediction: Mapping[str, Any], keys: Sequence[str], field_name: str) -> date:
    raw = _optional_text(prediction, keys)
    if raw is None:
        raise OutcomeFeedbackRejection(f"missing_{field_name}", "rejected_schema_count")
    try:
        return _parse_date(raw)
    except ValueError as exc:
        raise OutcomeFeedbackRejection(f"invalid_{field_name}", "rejected_schema_count") from exc


def _parse_date(value: str) -> date:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return date.fromisoformat(value[:10])


def _finite_number(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise OutcomeFeedbackRejection(f"missing_{field_name}", "rejected_schema_count")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OutcomeFeedbackRejection(f"invalid_{field_name}", "rejected_schema_count") from exc
    if not math.isfinite(number):
        raise OutcomeFeedbackRejection(f"nonfinite_{field_name}", "rejected_nonfinite_count")
    return number


def _summary(prediction: Mapping[str, Any], *, ticker: str, source_kind: str, error: float) -> str:
    raw_summary = _optional_text(prediction, ("summary", "rationale", "reasoning"))
    if raw_summary:
        return raw_summary[:500]
    return f"{source_kind} for {ticker}: realized prediction error {error:.6f}."


def _slug(value: str) -> str:
    if value.strip() == "*":
        return "all"
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    return slug.strip("_").lower() or "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GOTRA outcome feedback artifacts locally.")
    parser.add_argument("--predictions-path", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--current-run-id", default="")
    args = parser.parse_args(argv)

    result = generate_outcome_feedback_artifacts(
        load_predictions_file(args.predictions_path),
        current_run_id=args.current_run_id,
    )
    write_feedback_artifacts_jsonl(args.output_jsonl, result.artifacts)
    print(json.dumps(result.diagnostics, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
