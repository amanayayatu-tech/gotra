"""Public research packet adapter for GOTRA/ksana boundaries.

The adapter is intentionally local and deterministic. It normalizes committed
fixtures or exported research artifacts into the shape consumed by the v3
harness while making schema drift, future data, and identity mismatches
auditable instead of silently falling back to internal ksana assumptions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from gotra.backtest.protocol import parse_date


KSANA_PUBLIC_ADAPTER_SCHEMA = "gotra.ksana_public_research_adapter.v1"
SUPPORTED_RESEARCH_PACKET_SCHEMAS = {
    "gotra.ksana_public_research_packet.v1",
    "gotra.baseline_v3.research_artifact.v1",
    "gotra.baseline_v3_1.research_artifact.v1",
}
PUBLIC_SOURCE_KINDS = {"real", "unverified", "synthetic", "deterministic", "reference"}
HARNESS_RESEARCH_SOURCE_KINDS = {"real", "unverified", "synthetic"}
REQUIRED_PUBLIC_RESEARCH_FIELDS = {
    "ticker",
    "source_name",
    "source_url_or_id",
    "publish_timestamp",
    "availability_date",
    "source_kind",
    "retrieval_method",
    "evidence_ref",
    "summary",
}
FORBIDDEN_PUBLIC_RESEARCH_FIELDS = {
    "actual_change_pct",
    "future_return",
    "outcome",
    "realized_after_decision",
    "window_end_price",
    "future_price",
}
KSANA_REAL_RESEARCH_IDENTITY_VALUES = {
    "ksana_real_research",
    "real_ksana_research",
    "ksana_research",
}


def adapt_ksana_public_research_artifacts(
    artifacts: Iterable[Mapping[str, Any]],
    *,
    decision_date: date,
    ticker: str,
    horizon_days: int = 30,
    input_layer: str = "richer_research_packet",
    source_artifact_path: Path | None = None,
    fixture_id: str = "",
) -> dict[str, Any]:
    """Normalize research artifacts and return structured adapter diagnostics."""

    accepted: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    skipped_ticker_count = 0
    legacy_unverified_count = 0
    rejected_schema = 0
    rejected_future = 0
    rejected_identity = 0

    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            issues.append(_issue("schema_type_mismatch", index=index))
            rejected_schema += 1
            continue

        artifact_ticker = str(artifact.get("ticker") or "")
        if artifact_ticker not in {ticker, "*"}:
            skipped_ticker_count += 1
            continue

        schema_status = _schema_issue(artifact, index=index)
        if schema_status:
            issues.append(schema_status)
            rejected_schema += 1
            continue

        missing = sorted(REQUIRED_PUBLIC_RESEARCH_FIELDS - set(artifact))
        type_errors = _required_string_type_errors(artifact)
        source_kind = str(artifact.get("source_kind") or "").strip()
        if missing or type_errors:
            issues.append(
                _issue(
                    "missing_or_invalid_required_field",
                    artifact=artifact,
                    index=index,
                    fields=missing + type_errors,
                )
            )
            rejected_schema += 1
            continue
        if source_kind not in PUBLIC_SOURCE_KINDS:
            issues.append(
                _issue(
                    "untrusted_source_kind",
                    artifact=artifact,
                    index=index,
                    source_kind=source_kind,
                )
            )
            rejected_schema += 1
            continue
        if _identity_issue(artifact, source_kind=source_kind):
            issues.append(
                _issue(
                    "artifact_identity_mismatch",
                    artifact=artifact,
                    index=index,
                    source_kind=source_kind,
                )
            )
            rejected_identity += 1
            continue
        if source_kind not in HARNESS_RESEARCH_SOURCE_KINDS:
            issues.append(
                _issue(
                    "source_kind_not_ksana_research",
                    artifact=artifact,
                    index=index,
                    source_kind=source_kind,
                )
            )
            rejected_identity += 1
            continue

        future_fields = _future_data_issues(artifact, decision_date=decision_date)
        if future_fields:
            issues.append(
                _issue(
                    "future_data_metadata_leak",
                    artifact=artifact,
                    index=index,
                    fields=future_fields,
                )
            )
            rejected_future += 1
            continue

        schema_value = str(artifact.get("schema") or artifact.get("schema_version") or "")
        legacy_unverified = not schema_value
        if legacy_unverified:
            legacy_unverified_count += 1
        accepted.append(
            normalize_ksana_public_research_artifact(
                artifact,
                decision_date=decision_date,
                horizon_days=horizon_days,
                input_layer=input_layer,
                source_artifact_path=source_artifact_path,
                fixture_id=fixture_id,
                legacy_unverified=legacy_unverified,
            )
        )

    return {
        "accepted_artifacts": accepted,
        "adapter_schema": KSANA_PUBLIC_ADAPTER_SCHEMA,
        "ksana_public_adapter_issue_count": len(issues),
        "ksana_public_adapter_issues": issues,
        "rejected_research_artifact_count": rejected_schema + rejected_future + rejected_identity,
        "rejected_research_future_data_count": rejected_future,
        "rejected_research_schema_count": rejected_schema,
        "rejected_research_identity_count": rejected_identity,
        "legacy_unverified_research_artifact_count": legacy_unverified_count,
        "skipped_research_ticker_count": skipped_ticker_count,
    }


def normalize_ksana_public_research_artifact(
    artifact: Mapping[str, Any],
    *,
    decision_date: date,
    horizon_days: int,
    input_layer: str,
    source_artifact_path: Path | None = None,
    fixture_id: str = "",
    legacy_unverified: bool = False,
) -> dict[str, Any]:
    """Return the v3 harness-compatible research artifact shape."""

    source_url_or_id = str(artifact["source_url_or_id"])
    source_path = str(source_artifact_path) if source_artifact_path else ""
    source_kind = str(artifact["source_kind"])
    summary = str(artifact["summary"])
    return {
        "adapter_schema": KSANA_PUBLIC_ADAPTER_SCHEMA,
        "adapter_validation_status": "VALID_LEGACY_UNVERIFIED"
        if legacy_unverified
        else "VALID",
        "name": str(artifact["evidence_ref"]),
        "kind": "research_artifact",
        "source": source_url_or_id,
        "source_kind": source_kind,
        "source_family": str(artifact.get("source_family") or ""),
        "availability_date": str(artifact["availability_date"]),
        "latest_visible_price_date": str(artifact.get("latest_visible_price_date") or ""),
        "captured_at": str(artifact.get("captured_at") or artifact["publish_timestamp"]),
        "summary": summary,
        "text": str(artifact.get("text") or summary),
        "ticker": str(artifact["ticker"]),
        "decision_date": decision_date.isoformat(),
        "horizon_days": int(horizon_days),
        "input_layer": input_layer,
        "source_name": str(artifact["source_name"]),
        "source_url_or_id": source_url_or_id,
        "source_url": str(artifact.get("source_url") or source_url_or_id),
        "source_id": str(artifact.get("source_id") or source_url_or_id),
        "source_run_id": str(artifact.get("source_run_id") or ""),
        "source_artifact_path": source_path,
        "source_artifact_hash": sha256_file(source_artifact_path) if source_artifact_path else "",
        "source_fixture_id": fixture_id,
        "publish_timestamp": str(artifact["publish_timestamp"]),
        "retrieval_method": str(artifact["retrieval_method"]),
        "evidence_ref": str(artifact["evidence_ref"]),
        "decision_date_scope": artifact.get("decision_date_scope"),
        "decision_date_max": artifact.get("decision_date_max"),
        "provenance_hash": str(artifact.get("provenance_hash") or stable_artifact_hash(artifact)),
        "adapter_legacy_unverified": legacy_unverified,
        "citations": _list_field(artifact.get("citations")),
        "evidence": _list_field(artifact.get("evidence")),
        "claims": _list_field(artifact.get("claims")),
        "features": artifact.get("features") if isinstance(artifact.get("features"), dict) else {},
    }


def stable_artifact_hash(artifact: Mapping[str, Any]) -> str:
    """Compute a stable hash for one source artifact mapping."""

    payload = json.dumps(
        dict(artifact),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_issue(artifact: Mapping[str, Any], *, index: int) -> dict[str, Any] | None:
    schema = str(artifact.get("schema") or artifact.get("schema_version") or "")
    if schema and schema not in SUPPORTED_RESEARCH_PACKET_SCHEMAS:
        return _issue("unknown_schema_version", artifact=artifact, index=index, schema=schema)
    return None


def _required_string_type_errors(artifact: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_PUBLIC_RESEARCH_FIELDS:
        value = artifact.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(field)
    return sorted(errors)


def _future_data_issues(artifact: Mapping[str, Any], *, decision_date: date) -> list[str]:
    issues = sorted(FORBIDDEN_PUBLIC_RESEARCH_FIELDS & set(artifact))
    for field in (
        "availability_date",
        "publish_timestamp",
        "captured_at",
        "decision_date_max",
        "latest_visible_price_date",
    ):
        value = artifact.get(field)
        parsed = _date_value(value)
        if parsed is not None and parsed > decision_date:
            issues.append(field)
    return issues


def _date_value(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text or ":" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return parse_date(text)
    except ValueError:
        return None


def _identity_issue(artifact: Mapping[str, Any], *, source_kind: str) -> bool:
    if source_kind in {"real", "unverified"}:
        return False
    for field in (
        "artifact_identity",
        "artifact_kind",
        "artifact_role",
        "research_role",
        "arm",
        "input_role",
    ):
        value = str(artifact.get(field) or "").strip().lower()
        if value in KSANA_REAL_RESEARCH_IDENTITY_VALUES:
            return True
    return False


def _list_field(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _issue(
    code: str,
    *,
    artifact: Mapping[str, Any] | None = None,
    index: int,
    fields: list[str] | None = None,
    source_kind: str = "",
    schema: str = "",
) -> dict[str, Any]:
    return {
        "code": code,
        "index": index,
        "evidence_ref": str((artifact or {}).get("evidence_ref") or ""),
        "ticker": str((artifact or {}).get("ticker") or ""),
        "source_kind": source_kind or str((artifact or {}).get("source_kind") or ""),
        "schema": schema or str((artifact or {}).get("schema") or (artifact or {}).get("schema_version") or ""),
        "fields": fields or [],
    }
