"""Auto-quarantine unsafe Alaya knowledge after prediction outcomes are available."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


DEFAULT_ERROR_THRESHOLD = 0.15
RETURN_REVERSAL_THRESHOLD = 0.05
DEFAULT_ACTOR = "judge_agent/codex"

LONG_DIRECTIONS = {"long", "buy"}
SHORT_DIRECTIONS = {"short", "sell", "avoid"}
RESOLVED_STATUSES = {
    "closed",
    "completed",
    "evaluated",
    "observed",
    "outcome_observed",
    "resolved",
    "settled",
}
SOURCE_REF_KEYS = ("source_pr_id", "sourcePrId", "source_ref", "sourceRef")
SOURCE_REF_CONTAINER_KEYS = ("payload", "metadata", "source", "prediction", "knowledge")
KNOWLEDGE_ID_KEYS = ("id", "knowledge_id", "knowledgeId", "entry_id", "entryId")
PREDICTION_ID_KEYS = ("id", "prediction_id", "predictionId")
DIRECTION_KEYS = ("direction", "side", "stance", "recommendation", "action", "call", "position")
STATUS_KEYS = ("status", "state", "predictionStatus", "lifecycleStatus")
OBSERVED_RETURN_KEYS = (
    "observed_return",
    "observedReturn",
    "actual_return",
    "actualReturn",
    "realized_return",
    "realizedReturn",
    "realisedReturn",
    "outcome_return",
    "outcomeReturn",
    "price_return",
    "priceReturn",
)
ERROR_METRIC_KEYS = {
    "predictionError": ("predictionError", "prediction_error"),
    "worstClaimError": ("worstClaimError", "worst_claim_error"),
    "price_error": ("price_error", "priceError"),
}
LOOKUP_CONTAINER_KEYS = (
    "payload",
    "metadata",
    "prediction",
    "outcome",
    "outcomeSnapshot",
    "observation",
    "metrics",
    "errors",
    "claim",
)


class AlayaAutoQuarantineClient(Protocol):
    """Small Alaya API abstraction required by auto-quarantine."""

    def list_resolved_predictions(self) -> Sequence[Mapping[str, Any]]:
        """Return predictions whose outcome snapshots or prediction errors are available."""

    def list_knowledge(self, *, source_refs: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        """Return Alaya knowledge items that may match source_refs."""

    def quarantine_knowledge(
        self,
        knowledge_id: str,
        *,
        reason: str,
        actor: str,
    ) -> Mapping[str, Any] | None:
        """Quarantine one Alaya knowledge item through the Alaya API."""


class HttpAlayaAutoQuarantineClient:
    """HTTP-backed Alaya client for production orchestration."""

    def __init__(
        self,
        *,
        base_url: str,
        project_id: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def list_resolved_predictions(self) -> Sequence[Mapping[str, Any]]:
        if not self.project_id:
            raise ValueError("project_id is required to list Alaya predictions")
        data = self._request("GET", f"/api/projects/{self.project_id}/predictions")
        return [item for item in _unwrap_items(data, ("predictions", "items", "data"))]

    def list_knowledge(self, *, source_refs: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        del source_refs
        params = {"projectId": self.project_id} if self.project_id else None
        data = self._request("GET", "/api/knowledge", params=params)
        return [item for item in _unwrap_items(data, ("knowledge", "items", "data"))]

    def quarantine_knowledge(
        self,
        knowledge_id: str,
        *,
        reason: str,
        actor: str,
    ) -> Mapping[str, Any] | None:
        return self._request(
            "POST",
            f"/api/knowledge/{knowledge_id}/quarantine",
            json_payload={"actor": actor, "reason": reason},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any] | list[Any] | None:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            json=json_payload,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()


@dataclass(frozen=True)
class PredictionTrigger:
    """Reason one resolved prediction makes its source knowledge unsafe."""

    prediction_id: str
    source_ref: str
    reasons: tuple[str, ...]


@dataclass
class QuarantinedKnowledge:
    """Knowledge item quarantined through Alaya."""

    knowledge_id: str
    source_ref: str
    prediction_ids: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)

    def add_trigger(self, trigger: PredictionTrigger) -> None:
        self.prediction_ids.add(trigger.prediction_id)
        for reason in trigger.reasons:
            if reason not in self.reasons:
                self.reasons.append(reason)

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "source_ref": self.source_ref,
            "prediction_ids": sorted(self.prediction_ids),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AutoQuarantineResult:
    """Result of one auto-quarantine pass."""

    report_path: Path
    quarantined: tuple[QuarantinedKnowledge, ...]
    resolved_prediction_count: int
    matched_knowledge_count: int
    error_threshold: float


def run_auto_quarantine(
    client: AlayaAutoQuarantineClient,
    *,
    data_dir: str | Path = "data",
    report_dir: str | Path | None = None,
    error_threshold: float | None = None,
    actor: str = DEFAULT_ACTOR,
    now: datetime | None = None,
) -> AutoQuarantineResult:
    """Quarantine Alaya knowledge contradicted by resolved prediction outcomes."""

    threshold = error_threshold if error_threshold is not None else read_error_threshold()
    generated_at = now or datetime.now(UTC)
    predictions = [
        prediction
        for prediction in client.list_resolved_predictions()
        if is_resolved_prediction(prediction)
    ]
    triggers = find_prediction_triggers(predictions, error_threshold=threshold)
    source_refs = sorted({trigger.source_ref for trigger in triggers})
    knowledge_items = client.list_knowledge(source_refs=source_refs) if source_refs else []
    candidates = match_quarantine_candidates(triggers, knowledge_items)

    for candidate in candidates:
        client.quarantine_knowledge(
            candidate.knowledge_id,
            reason="; ".join(candidate.reasons),
            actor=actor,
        )

    output_dir = Path(report_dir) if report_dir is not None else Path(data_dir) / "judge_reports"
    report_path = write_report(
        output_dir,
        generated_at=generated_at,
        error_threshold=threshold,
        resolved_prediction_count=len(predictions),
        matched_knowledge_count=len(knowledge_items),
        quarantined=candidates,
    )
    return AutoQuarantineResult(
        report_path=report_path,
        quarantined=tuple(candidates),
        resolved_prediction_count=len(predictions),
        matched_knowledge_count=len(knowledge_items),
        error_threshold=threshold,
    )


def find_prediction_triggers(
    predictions: Iterable[Mapping[str, Any]],
    *,
    error_threshold: float,
) -> list[PredictionTrigger]:
    """Find resolved predictions that should quarantine their source knowledge."""

    triggers: list[PredictionTrigger] = []
    for prediction in predictions:
        source_refs = sorted(extract_source_refs(prediction))
        if not source_refs:
            continue
        reasons = quarantine_reasons(prediction, error_threshold=error_threshold)
        if not reasons:
            continue
        prediction_id = extract_string_value(prediction, PREDICTION_ID_KEYS) or "unknown"
        for source_ref in source_refs:
            triggers.append(
                PredictionTrigger(
                    prediction_id=prediction_id,
                    source_ref=source_ref,
                    reasons=tuple(reasons),
                )
            )
    return triggers


def match_quarantine_candidates(
    triggers: Sequence[PredictionTrigger],
    knowledge_items: Iterable[Mapping[str, Any]],
) -> list[QuarantinedKnowledge]:
    """Match triggered prediction source refs to Alaya knowledge items."""

    triggers_by_ref: dict[str, list[PredictionTrigger]] = {}
    for trigger in triggers:
        triggers_by_ref.setdefault(trigger.source_ref, []).append(trigger)

    candidates: dict[str, QuarantinedKnowledge] = {}
    for item in knowledge_items:
        knowledge_id = extract_string_value(item, KNOWLEDGE_ID_KEYS)
        if not knowledge_id or is_already_quarantined(item):
            continue
        matching_refs = sorted(extract_source_refs(item).intersection(triggers_by_ref))
        for source_ref in matching_refs:
            candidate = candidates.setdefault(
                knowledge_id,
                QuarantinedKnowledge(knowledge_id=knowledge_id, source_ref=source_ref),
            )
            for trigger in triggers_by_ref[source_ref]:
                candidate.add_trigger(trigger)

    return sorted(candidates.values(), key=lambda candidate: candidate.knowledge_id)


def quarantine_reasons(
    prediction: Mapping[str, Any],
    *,
    error_threshold: float,
) -> list[str]:
    """Return quarantine reasons for one resolved prediction."""

    reasons: list[str] = []
    direction = extract_direction(prediction)
    observed_return = extract_observed_return(prediction)
    if direction in LONG_DIRECTIONS and observed_return is not None:
        if observed_return <= -RETURN_REVERSAL_THRESHOLD:
            reasons.append(
                "long/buy observed_return "
                f"{format_percent(observed_return)} <= -{format_percent(RETURN_REVERSAL_THRESHOLD)}"
            )
    if direction in SHORT_DIRECTIONS and observed_return is not None:
        if observed_return >= RETURN_REVERSAL_THRESHOLD:
            reasons.append(
                "short/sell/avoid observed_return "
                f"{format_percent(observed_return)} >= {format_percent(RETURN_REVERSAL_THRESHOLD)}"
            )

    for metric_name, metric_value in extract_error_metrics(prediction).items():
        if abs(metric_value) > error_threshold:
            reasons.append(
                f"{metric_name} abs({format_percent(metric_value)}) "
                f"> {format_percent(error_threshold)}"
            )
    return reasons


def is_resolved_prediction(prediction: Mapping[str, Any]) -> bool:
    """Return whether a prediction has resolved outcome/error data."""

    status = extract_string_value(prediction, STATUS_KEYS)
    if status and status.lower() not in RESOLVED_STATUSES:
        return False
    return extract_observed_return(prediction) is not None or bool(extract_error_metrics(prediction))


def is_already_quarantined(item: Mapping[str, Any]) -> bool:
    status = extract_string_value(item, ("status", "state"))
    return bool(status and status.lower() == "quarantined")


def extract_source_refs(item: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in SOURCE_REF_KEYS:
        if key in item:
            refs.update(flatten_source_ref(item[key]))
    for key in SOURCE_REF_CONTAINER_KEYS:
        nested = item.get(key)
        if isinstance(nested, Mapping):
            refs.update(extract_source_refs(nested))
    return refs


def flatten_source_ref(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        stripped = value.strip()
        return {stripped} if stripped else set()
    if isinstance(value, int | float):
        return {str(value)}
    if isinstance(value, Mapping):
        refs: set[str] = set()
        for key in (*SOURCE_REF_KEYS, "pr_id", "prId", "id", "ref"):
            if key in value:
                refs.update(flatten_source_ref(value[key]))
        return refs
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        refs: set[str] = set()
        for item in value:
            refs.update(flatten_source_ref(item))
        return refs
    return set()


def extract_direction(prediction: Mapping[str, Any]) -> str | None:
    value = extract_string_value(prediction, DIRECTION_KEYS)
    if not value:
        return None
    normalized = value.lower()
    for direction in LONG_DIRECTIONS:
        if direction in normalized:
            return direction
    for direction in SHORT_DIRECTIONS:
        if direction in normalized:
            return direction
    return None


def extract_observed_return(prediction: Mapping[str, Any]) -> float | None:
    value = lookup_nested_value(prediction, OBSERVED_RETURN_KEYS)
    return coerce_ratio(value, normalize_percent_numeric=True)


def extract_error_metrics(prediction: Mapping[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for canonical_name, keys in ERROR_METRIC_KEYS.items():
        value = lookup_nested_value(prediction, keys)
        ratio = coerce_ratio(value, normalize_percent_numeric=False)
        if ratio is not None:
            metrics[canonical_name] = ratio
    return metrics


def extract_string_value(item: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    value = lookup_nested_value(item, keys)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def lookup_nested_value(item: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    for container_key in LOOKUP_CONTAINER_KEYS:
        nested = item.get(container_key)
        if isinstance(nested, Mapping):
            value = lookup_nested_value(nested, keys)
            if value is not None:
                return value
    return None


def coerce_ratio(value: Any, *, normalize_percent_numeric: bool) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if not stripped:
            return None
        is_percent = stripped.endswith("%")
        if is_percent:
            stripped = stripped[:-1].strip()
        try:
            number = float(stripped)
        except ValueError:
            return None
        if is_percent:
            return number / 100
    else:
        return None

    if normalize_percent_numeric and 1 < abs(number) <= 100:
        return number / 100
    return number


def read_error_threshold() -> float:
    raw_threshold = os.getenv("QUARANTINE_ERROR_THRESHOLD")
    if raw_threshold is None or not raw_threshold.strip():
        return DEFAULT_ERROR_THRESHOLD
    threshold = coerce_ratio(raw_threshold, normalize_percent_numeric=False)
    if threshold is None or threshold < 0:
        raise ValueError("QUARANTINE_ERROR_THRESHOLD must be a non-negative ratio")
    return threshold


def write_report(
    report_dir: Path,
    *,
    generated_at: datetime,
    error_threshold: float,
    resolved_prediction_count: int,
    matched_knowledge_count: int,
    quarantined: Sequence[QuarantinedKnowledge],
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"auto_quarantine_{timestamp}.json"
    payload = {
        "generated_at": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "error_threshold": error_threshold,
        "resolved_prediction_count": resolved_prediction_count,
        "matched_knowledge_count": matched_knowledge_count,
        "quarantined_count": len(quarantined),
        "quarantined": [candidate.to_report_dict() for candidate in quarantined],
    }
    tmp_path = report_path.with_name(f".{report_path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(report_path)
    return report_path


def format_percent(value: float) -> str:
    return f"{value:.2%}"


def _unwrap_items(
    data: Mapping[str, Any] | list[Any] | None,
    keys: Sequence[str],
) -> list[Mapping[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, Mapping)]
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []
