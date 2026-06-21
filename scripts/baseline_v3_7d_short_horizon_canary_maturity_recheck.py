#!/usr/bin/env python3
"""GOTRA v3.7D short-horizon canary maturity recheck."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd

from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import parse_date
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan
from scripts import baseline_v3_6y_short_horizon_first_capture as capture_v36y
from scripts import baseline_v3_four_arm as v3


SUMMARY_SCHEMA = "gotra.baseline_v3_7d.short_horizon_canary_maturity_recheck_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7d.short_horizon_canary_maturity_recheck_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_7d_short_horizon_canary_maturity_recheck_"
SCRIPT_VERSION = "v3.7d-20260622"
EVIDENCE_LAYER = "short_horizon_forward_live_canary_engineering"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
DEFAULT_OUTCOME_WINDOW_DAYS = 7

STATUS_READY = "SHORT_HORIZON_READY"
STATUS_NOT_MATURED = "SHORT_HORIZON_NOT_MATURED"
STATUS_BLOCKED_DATA = "BLOCKED_DATA"
STATUS_BLOCKED_FUTURE_DATA = "BLOCKED_FUTURE_DATA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_RUN_ID_EXISTS = "SHORT_HORIZON_RECHECK_BLOCKED_RUN_ID_EXISTS"

OUTCOME_STATUS_RESOLVED = "RESOLVED"
OUTCOME_STATUS_NOT_MATURED = "NOT_MATURED"
OUTCOME_STATUS_BLOCKED_DATA = "BLOCKED_DATA"

CLI_SUCCESS_STATUSES = {STATUS_READY, STATUS_NOT_MATURED}
VALID_DIRECTIONS = {"long", "avoid", "neutral"}
CLAIM_TEXT_FIELDS = (
    "summary",
    "claim",
    "claims",
    "notes",
    "narrative",
    "rationale",
    "reasoning",
    "statement",
    "verdict",
    "winner",
    "non_claims",
)


@dataclass(frozen=True)
class RecheckConfig:
    recheck_run_id: str
    source_summary: Path
    expected_source_summary_sha256: str
    expected_source_artifact_sha256: str
    expected_run_id: str
    output_dir: Path
    as_of_timestamp_utc: datetime
    price_dir: Path
    source_artifact: Path | None = None
    outcome_window_days: int = DEFAULT_OUTCOME_WINDOW_DAYS
    allow_overwrite: bool = False


@dataclass(frozen=True)
class SourceBundle:
    summary: dict[str, Any]
    summary_sha256: str
    artifact: dict[str, Any]
    artifact_path: Path
    artifact_sha256: str
    identity: dict[str, Any]


class RecheckError(Exception):
    def __init__(self, status: str, rule_id: str, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.rule_id = rule_id
        self.reason = reason


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"recheck_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("recheck_run_id may contain only letters, numbers, '_' and '-'")


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


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "json_read_error", str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "json_decode_error", str(exc)) from exc
    if not isinstance(payload, dict):
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "malformed_json_root", f"expected JSON object: {path}")
    return payload


def blocker(path: Path | str, rule_id: str, reason: str) -> dict[str, str]:
    return {"path": normalize_path(path), "rule_id": rule_id, "reason": reason}


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def bool_false(value: Any) -> bool:
    return isinstance(value, bool) and value is False


def bool_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(value, int):
        return value > 0
    return False


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple, set)):
            text = str(value).strip()
            if text:
                return text
    return ""


def nested_value(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def validate_config(config: RecheckConfig) -> None:
    validate_run_id(config.recheck_run_id)
    if not config.expected_run_id.strip():
        raise ValueError("expected_run_id is required")
    if not config.expected_source_summary_sha256.strip():
        raise ValueError("expected_source_summary_sha256 is required")
    if not config.expected_source_artifact_sha256.strip():
        raise ValueError("expected_source_artifact_sha256 is required")
    if config.outcome_window_days < 0:
        raise ValueError("outcome_window_days must be >= 0")


def resolve_optional_path(path_value: str, *, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path


def discover_artifact_path(summary: dict[str, Any], config: RecheckConfig) -> Path:
    if config.source_artifact is not None:
        return config.source_artifact
    candidates = [
        first_non_empty(summary.get("source_artifact_path")),
        first_non_empty(summary.get("source_capture_artifact")),
        first_non_empty(summary.get("capture_artifact_path")),
        first_non_empty(nested_value(summary, "provenance", "source_artifact_path")),
    ]
    ledger = summary.get("maturity_ledger")
    if isinstance(ledger, list) and ledger and isinstance(ledger[0], dict):
        candidates.extend(
            [
                first_non_empty(ledger[0].get("source_artifact_path")),
                first_non_empty(ledger[0].get("capture_artifact_path")),
            ]
        )
    for candidate in candidates:
        if candidate:
            return resolve_optional_path(candidate, base_dir=config.source_summary.parent)

    run_root = Path(str(summary.get("run_root") or "")).expanduser()
    if run_root.exists():
        matches = sorted(path for path in (run_root / "captures").glob("**/*.json") if path.is_file())
        hash_matches = [path for path in matches if sha256_file(path) == config.expected_source_artifact_sha256]
        if len(hash_matches) == 1:
            return hash_matches[0]
        if len(matches) == 1:
            return matches[0]
    raise RecheckError(STATUS_BLOCKED_PROVENANCE, "missing_source_artifact_path", "source artifact path not found")


def recursive_text_sources(value: Any, *, path: str) -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    if isinstance(value, str):
        sources.append(claim_scan.ScanSource(path=path, text=value, origin="short_horizon_canary"))
    elif isinstance(value, dict):
        for key, item in sorted(value.items()):
            sources.extend(recursive_text_sources(item, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            sources.extend(recursive_text_sources(item, path=f"{path}[{index}]"))
    return sources


def claim_sources(payload: dict[str, Any], *, path: str) -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    for field in CLAIM_TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            sources.append(claim_scan.ScanSource(path=f"{path}:{field}", text=value, origin="short_horizon_canary"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    sources.append(
                        claim_scan.ScanSource(
                            path=f"{path}:{field}[{index}]",
                            text=item,
                            origin="short_horizon_canary",
                        )
                    )
    decision = payload.get("decision")
    if isinstance(decision, (dict, list)):
        sources.extend(recursive_text_sources(decision, path=f"{path}:decision"))
    return sources


def claim_blockers(*, summary: dict[str, Any], artifact: dict[str, Any], summary_path: Path, artifact_path: Path) -> list[dict[str, Any]]:
    scan = claim_scan.scan_sources(
        claim_sources(summary, path=normalize_path(summary_path))
        + claim_sources(artifact, path=normalize_path(artifact_path))
    )
    return (
        scan["overclaim"]
        + scan["direct_llm"]
        + scan["maturity_gate"]
        + scan["short_horizon_as_30d"]
    )


def validate_source_summary_success(summary: dict[str, Any]) -> None:
    if summary.get("schema") != capture_v36y.SUMMARY_SCHEMA:
        raise RecheckError(
            STATUS_BLOCKED_SCHEMA,
            "source_summary_schema_mismatch",
            "source summary is not the expected v3.6Y short-horizon capture summary schema",
        )
    if summary.get("status") != capture_v36y.STATUS_PASS:
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_summary_not_pass",
            f"source summary status is not pass: {summary.get('status')}",
        )
    if int_value(summary.get("actual_capture_artifacts")) != 1:
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_summary_capture_count_not_one",
            "source summary must contain exactly one capture artifact",
        )
    if int_value(summary.get("future_data_violation_count")) not in {0}:
        raise RecheckError(
            STATUS_BLOCKED_FUTURE_DATA,
            "source_summary_future_data_violation",
            "source summary future_data_violation_count must be explicitly zero",
        )
    if int_value(summary.get("deterministic_reference_future_data_violations")) not in {0}:
        raise RecheckError(
            STATUS_BLOCKED_FUTURE_DATA,
            "source_summary_reference_future_data_violation",
            "source summary deterministic_reference_future_data_violations must be explicitly zero",
        )
    if summary.get("formal_lite_entered") is not False:
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_summary_formal_lite_entered",
            "source summary unexpectedly entered formal-lite",
        )
    if summary.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_summary_direct_llm_interpretation_missing",
            "source summary missing direct_llm_parametric_memory_control caveat",
        )


def source_maturity_ledger_row(summary: dict[str, Any]) -> dict[str, Any]:
    ledger = summary.get("maturity_ledger")
    if not isinstance(ledger, list) or len(ledger) != 1:
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_summary_maturity_ledger_not_one",
            "source summary maturity_ledger must contain exactly one row",
        )
    row = ledger[0]
    if not isinstance(row, dict):
        raise RecheckError(
            STATUS_BLOCKED_SCHEMA,
            "source_summary_maturity_ledger_row_malformed",
            "source summary maturity_ledger row must be an object",
        )
    required = [
        "source_decision_id",
        "ticker",
        "decision_date_local",
        "horizon_days",
        "horizon_end_date",
    ]
    missing = [field for field in required if not first_non_empty(row.get(field))]
    if missing:
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_summary_maturity_ledger_missing_fields",
            ",".join(missing),
        )
    return row


def compare_identity_field(*, field: str, artifact_value: Any, ledger_value: Any) -> None:
    if str(artifact_value) != str(ledger_value):
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_artifact_identity_mismatch",
            f"source artifact {field} mismatch against maturity_ledger: artifact={artifact_value!r} ledger={ledger_value!r}",
        )


def validate_summary_artifact_binding(*, summary: dict[str, Any], artifact: dict[str, Any]) -> None:
    ledger_row = source_maturity_ledger_row(summary)
    compare_identity_field(
        field="source_decision_id",
        artifact_value=artifact.get("source_decision_id"),
        ledger_value=ledger_row.get("source_decision_id"),
    )
    compare_identity_field(
        field="ticker",
        artifact_value=artifact.get("ticker"),
        ledger_value=ledger_row.get("ticker"),
    )
    compare_identity_field(
        field="decision_date_local",
        artifact_value=first_non_empty(artifact.get("decision_date_local"), artifact.get("decision_date")),
        ledger_value=ledger_row.get("decision_date_local"),
    )
    compare_identity_field(
        field="horizon_days",
        artifact_value=int_value(artifact.get("horizon_days")),
        ledger_value=int_value(ledger_row.get("horizon_days")),
    )
    compare_identity_field(
        field="horizon_end_date",
        artifact_value=artifact.get("horizon_end_date"),
        ledger_value=ledger_row.get("horizon_end_date"),
    )
    for optional_field in ("arm", "input_layer"):
        ledger_value = ledger_row.get(optional_field)
        if first_non_empty(ledger_value):
            compare_identity_field(
                field=optional_field,
                artifact_value=artifact.get(optional_field),
                ledger_value=ledger_value,
            )


def same_resolved_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve(strict=False) == right.expanduser().resolve(strict=False)


def validate_source_artifact_path_binding(*, summary: dict[str, Any], summary_path: Path, artifact_path: Path) -> None:
    path_values = [
        first_non_empty(summary.get("source_artifact_path")),
        first_non_empty(summary.get("source_capture_artifact")),
        first_non_empty(summary.get("capture_artifact_path")),
        first_non_empty(nested_value(summary, "provenance", "source_artifact_path")),
    ]
    expected_paths = [
        resolve_optional_path(value, base_dir=summary_path.parent)
        for value in path_values
        if value
    ]
    if expected_paths and not any(same_resolved_path(path, artifact_path) for path in expected_paths):
        raise RecheckError(
            STATUS_BLOCKED_PROVENANCE,
            "source_artifact_path_mismatch",
            "source artifact path does not match the verified source summary",
        )


def validate_source_future_data_guard(*, summary: dict[str, Any], artifact: dict[str, Any], identity: dict[str, Any]) -> None:
    if bool_true(summary.get("future_data_violation")) or bool_true(artifact.get("future_data_violation")):
        raise RecheckError(
            STATUS_BLOCKED_FUTURE_DATA,
            "source_future_data_violation",
            "source summary/artifact reports future_data_violation",
        )
    decision_date_text = first_non_empty(
        identity.get("decision_date"),
        artifact.get("decision_date_local"),
        artifact.get("decision_date"),
    )
    if not decision_date_text:
        capture_timestamp = first_non_empty(identity.get("capture_timestamp"), artifact.get("capture_timestamp"))
        if capture_timestamp:
            decision_date_text = parse_timestamp(capture_timestamp).date().isoformat()
    if not decision_date_text:
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "missing_decision_date", "missing decision/capture allowed date")
    try:
        latest_visible = parse_date(str(identity["latest_visible_price_date"]))
        allowed_date = parse_date(str(decision_date_text))
    except ValueError as exc:
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "invalid_source_price_visibility_date", str(exc)) from exc
    if latest_visible > allowed_date:
        raise RecheckError(
            STATUS_BLOCKED_FUTURE_DATA,
            "source_future_visible_price_date",
            "source latest_visible_price_date is after the decision/capture allowed date",
        )


def load_source_bundle(config: RecheckConfig) -> SourceBundle:
    summary_path_text = normalize_path(config.source_summary)
    if claim_scan.forbidden_path(summary_path_text):
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "forbidden_source_summary_path", "source summary path is forbidden")
    if not config.source_summary.exists():
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "source_summary_not_found", "source summary not found")
    summary_sha = sha256_file(config.source_summary)
    if summary_sha != config.expected_source_summary_sha256:
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "source_summary_sha256_mismatch", "source summary sha256 mismatch")
    summary = load_json_object(config.source_summary)
    source_run_id = first_non_empty(summary.get("run_id"), summary.get("source_run_id"))
    if source_run_id != config.expected_run_id:
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "source_run_id_mismatch", "source run id mismatch")
    validate_source_summary_success(summary)

    artifact_path = discover_artifact_path(summary, config)
    artifact_path_text = normalize_path(artifact_path)
    if claim_scan.forbidden_path(artifact_path_text):
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "forbidden_source_artifact_path", "source artifact path is forbidden")
    if not artifact_path.exists():
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "source_artifact_not_found", "source artifact not found")
    artifact_sha = sha256_file(artifact_path)
    if artifact_sha != config.expected_source_artifact_sha256:
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "source_artifact_sha256_mismatch", "source artifact sha256 mismatch")
    artifact = load_json_object(artifact_path)
    validate_source_artifact_path_binding(
        summary=summary,
        summary_path=config.source_summary,
        artifact_path=artifact_path,
    )
    validate_summary_artifact_binding(summary=summary, artifact=artifact)
    blockers = claim_blockers(
        summary=summary,
        artifact=artifact,
        summary_path=config.source_summary,
        artifact_path=artifact_path,
    )
    if blockers:
        first = blockers[0]
        raise RecheckError(STATUS_BLOCKED_OVERCLAIM, str(first["rule_id"]), str(first["reason"]))
    identity = source_identity(summary=summary, artifact=artifact, artifact_path=artifact_path)
    if identity["source_run_id"] != config.expected_run_id:
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "source_artifact_run_id_mismatch", "source artifact run id mismatch")
    validate_source_future_data_guard(summary=summary, artifact=artifact, identity=identity)
    return SourceBundle(
        summary=summary,
        summary_sha256=summary_sha,
        artifact=artifact,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha,
        identity=identity,
    )


def source_identity(*, summary: dict[str, Any], artifact: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    source_run_id = first_non_empty(artifact.get("run_id"), artifact.get("source_run_id"), summary.get("run_id"), summary.get("source_run_id"))
    horizon_days = int_value(first_non_empty(artifact.get("horizon_days"), summary.get("horizon_days")))
    horizon_text = first_non_empty(artifact.get("horizon"), summary.get("horizon"))
    if horizon_days is None and horizon_text.endswith("D"):
        horizon_days = int_value(horizon_text[:-1])
    if horizon_days is None:
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "missing_horizon_days", "missing or invalid horizon_days")
    horizon = horizon_text or f"{horizon_days}D"
    identity = {
        "source_run_id": source_run_id,
        "source_decision_id": first_non_empty(artifact.get("source_decision_id"), summary.get("source_decision_id")),
        "source_artifact_path": str(artifact_path),
        "ticker": first_non_empty(artifact.get("ticker"), summary.get("ticker")),
        "capture_timestamp": first_non_empty(artifact.get("capture_timestamp"), artifact.get("decision_timestamp_utc"), summary.get("capture_timestamp")),
        "decision_date": first_non_empty(artifact.get("decision_date"), artifact.get("decision_date_local"), summary.get("decision_date")),
        "latest_visible_price_date": first_non_empty(artifact.get("latest_visible_price_date"), summary.get("latest_visible_price_date")),
        "horizon": horizon,
        "horizon_days": horizon_days,
        "horizon_end_date": first_non_empty(artifact.get("horizon_end_date"), summary.get("horizon_end_date")),
        "prompt_hash": first_non_empty(artifact.get("prompt_hash"), artifact.get("source_prompt_identity_hash"), summary.get("prompt_hash")),
        "parsed_decision_hash": first_non_empty(artifact.get("parsed_decision_hash"), summary.get("parsed_decision_hash")),
        "backend": first_non_empty(artifact.get("backend"), summary.get("backend")),
        "codex_cli_version": first_non_empty(artifact.get("codex_cli_version"), summary.get("codex_cli_version")),
        "model": first_non_empty(artifact.get("model"), summary.get("model")),
        "reasoning": first_non_empty(artifact.get("reasoning"), summary.get("reasoning")),
    }
    required = [
        "source_run_id",
        "source_decision_id",
        "ticker",
        "capture_timestamp",
        "horizon_end_date",
        "prompt_hash",
        "parsed_decision_hash",
    ]
    missing = [field for field in required if not identity[field]]
    if missing:
        raise RecheckError(STATUS_BLOCKED_PROVENANCE, "missing_source_identity", ",".join(missing))
    try:
        parse_date(str(identity["horizon_end_date"]))
    except ValueError as exc:
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "invalid_horizon_end_date", str(exc)) from exc
    if not identity["latest_visible_price_date"]:
        identity["latest_visible_price_date"] = identity["decision_date"]
    if not identity["latest_visible_price_date"]:
        raise RecheckError(STATUS_BLOCKED_SCHEMA, "missing_latest_visible_price_date", "missing decision/latest visible price date")
    return identity


def daily_close_available_cutoff(as_of_timestamp_utc: datetime) -> date:
    return as_of_timestamp_utc.astimezone(UTC).date() - timedelta(days=1)


def available_after_timestamp(horizon_end_date: date) -> datetime:
    return datetime.combine(horizon_end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)


def price_on_or_before(*, ticker: str, target_date: date, price_dir: Path, as_of_timestamp_utc: datetime) -> tuple[date, float, str]:
    cutoff = daily_close_available_cutoff(as_of_timestamp_utc)
    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    visible = frame.loc[dates <= target_date]
    if visible.empty:
        raise LookupError(f"missing decision price for {ticker} on/before {target_date}")
    row = visible.iloc[-1]
    return parse_date(str(row["date"])), float(row["adj_close"]), str(price_dir / f"{ticker}.csv")


def outcome_price_in_window(
    *,
    ticker: str,
    horizon_end_date: date,
    price_dir: Path,
    as_of_timestamp_utc: datetime,
    outcome_window_days: int,
) -> tuple[date, float, str] | None:
    allowed_end = horizon_end_date + timedelta(days=outcome_window_days)
    cutoff = min(daily_close_available_cutoff(as_of_timestamp_utc), allowed_end)
    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    candidates = frame.loc[(dates >= horizon_end_date) & (dates <= cutoff)]
    if candidates.empty:
        return None
    row = candidates.iloc[0]
    return parse_date(str(row["date"])), float(row["adj_close"]), str(price_dir / f"{ticker}.csv")


def empty_outcome_fields() -> dict[str, Any]:
    return {
        "decision_price": None,
        "decision_price_date": "",
        "outcome_price": None,
        "outcome_price_date": "",
        "actual_change_pct": None,
        "actual_direction": "",
    }


def base_summary(
    *,
    config: RecheckConfig,
    run_root: Path,
    status: str,
    bundle: SourceBundle | None = None,
    blocker_reasons: list[str] | None = None,
) -> dict[str, Any]:
    identity = bundle.identity if bundle else {}
    horizon_end_date = str(identity.get("horizon_end_date") or "")
    next_check_after = ""
    if horizon_end_date:
        try:
            next_check_after = available_after_timestamp(parse_date(horizon_end_date)).isoformat().replace("+00:00", "Z")
        except ValueError:
            next_check_after = ""
    summary = {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "recheck_run_id": config.recheck_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "source_run_id": str(identity.get("source_run_id") or config.expected_run_id),
        "source_summary_path": str(config.source_summary),
        "source_summary_sha256": bundle.summary_sha256 if bundle else "",
        "expected_source_summary_sha256": config.expected_source_summary_sha256,
        "source_artifact_path": str(identity.get("source_artifact_path") or config.source_artifact or ""),
        "source_artifact_sha256": bundle.artifact_sha256 if bundle else "",
        "expected_source_artifact_sha256": config.expected_source_artifact_sha256,
        "source_decision_id": str(identity.get("source_decision_id") or ""),
        "capture_timestamp": str(identity.get("capture_timestamp") or ""),
        "horizon": str(identity.get("horizon") or ""),
        "horizon_days": identity.get("horizon_days"),
        "horizon_end_date": horizon_end_date,
        "prompt_hash": str(identity.get("prompt_hash") or ""),
        "parsed_decision_hash": str(identity.get("parsed_decision_hash") or ""),
        "maturity_status": status,
        "outcome_status": "",
        "resolved_count": 0,
        "scored_count": 0,
        "readiness_status": status,
        "next_check_after": next_check_after,
        "blocker_reasons": blocker_reasons or [],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a 30D forward-live verdict",
            "short-horizon canary does not authorize v3.7",
        ],
    }
    summary.update(empty_outcome_fields())
    return summary


def blocked_summary(
    *,
    config: RecheckConfig,
    run_root: Path,
    status: str,
    reason: str,
    bundle: SourceBundle | None = None,
) -> dict[str, Any]:
    summary = base_summary(
        config=config,
        run_root=run_root,
        status=status,
        bundle=bundle,
        blocker_reasons=[reason],
    )
    if status == STATUS_BLOCKED_DATA:
        summary["outcome_status"] = OUTCOME_STATUS_BLOCKED_DATA
        summary["readiness_status"] = STATUS_BLOCKED_DATA
    return summary


def recheck_status_for(config: RecheckConfig, bundle: SourceBundle) -> dict[str, Any]:
    identity = bundle.identity
    horizon_end = parse_date(str(identity["horizon_end_date"]))
    available_after = available_after_timestamp(horizon_end)
    run_root = config.output_dir / config.recheck_run_id
    if config.as_of_timestamp_utc < available_after:
        summary = base_summary(config=config, run_root=run_root, status=STATUS_NOT_MATURED, bundle=bundle)
        summary.update(
            {
                "outcome_status": OUTCOME_STATUS_NOT_MATURED,
                "readiness_status": STATUS_NOT_MATURED,
                "blocker_reasons": ["daily_close_not_available"],
            }
        )
        return summary

    ticker = str(identity["ticker"])
    latest_visible = parse_date(str(identity["latest_visible_price_date"]))
    try:
        decision_price_date, decision_price, decision_price_source = price_on_or_before(
            ticker=ticker,
            target_date=latest_visible,
            price_dir=config.price_dir,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
        )
        outcome = outcome_price_in_window(
            ticker=ticker,
            horizon_end_date=horizon_end,
            price_dir=config.price_dir,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
            outcome_window_days=config.outcome_window_days,
        )
    except (FileNotFoundError, LookupError, ValueError, KeyError) as exc:
        return blocked_summary(
            config=config,
            run_root=run_root,
            status=STATUS_BLOCKED_DATA,
            reason=v3.redact_error(str(exc)),
            bundle=bundle,
        )
    if outcome is None:
        return blocked_summary(
            config=config,
            run_root=run_root,
            status=STATUS_BLOCKED_DATA,
            reason="outcome_price_unavailable",
            bundle=bundle,
        )
    outcome_price_date, outcome_price, outcome_price_source = outcome
    actual_change_pct = v3.change_pct(decision_price, outcome_price)
    actual_direction = v3.actual_direction(actual_change_pct)
    if actual_direction not in VALID_DIRECTIONS:
        return blocked_summary(
            config=config,
            run_root=run_root,
            status=STATUS_BLOCKED_DATA,
            reason=f"invalid_actual_direction:{actual_direction}",
            bundle=bundle,
        )
    summary = base_summary(config=config, run_root=run_root, status=STATUS_READY, bundle=bundle)
    summary.update(
        {
            "maturity_status": STATUS_READY,
            "outcome_status": OUTCOME_STATUS_RESOLVED,
            "decision_price": decision_price,
            "decision_price_date": decision_price_date.isoformat(),
            "decision_price_source": decision_price_source,
            "outcome_price": outcome_price,
            "outcome_price_date": outcome_price_date.isoformat(),
            "outcome_price_source": outcome_price_source,
            "actual_change_pct": actual_change_pct,
            "actual_direction": actual_direction,
            "resolved_count": 1,
            "scored_count": 1,
            "readiness_status": STATUS_READY,
            "blocker_reasons": [],
        }
    )
    return summary


def write_outputs(config: RecheckConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "recheck_run_id": config.recheck_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "source_summary_path": str(config.source_summary),
        "source_summary_sha256": summary.get("source_summary_sha256", ""),
        "source_artifact_path": summary.get("source_artifact_path", ""),
        "source_artifact_sha256": summary.get("source_artifact_sha256", ""),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def run_recheck(config: RecheckConfig) -> dict[str, Any]:
    validate_config(config)
    run_root = config.output_dir / config.recheck_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = blocked_summary(
            config=config,
            run_root=run_root,
            status=STATUS_BLOCKED_RUN_ID_EXISTS,
            reason="output_run_id_exists",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    try:
        bundle = load_source_bundle(config)
        summary = recheck_status_for(config, bundle)
    except RecheckError as exc:
        summary = blocked_summary(
            config=config,
            run_root=run_root,
            status=exc.status,
            reason=exc.rule_id,
        )
        summary["blocker_details"] = [exc.reason]
    write_outputs(config, summary, run_root=run_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recheck-run-id", default=default_run_id())
    parser.add_argument("--source-summary", type=Path, required=True)
    parser.add_argument("--expected-source-summary-sha256", required=True)
    parser.add_argument("--expected-source-artifact-sha256", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--source-artifact", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7d_short_horizon_canary_maturity_recheck/runs"))
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--outcome-window-days", type=int, default=DEFAULT_OUTCOME_WINDOW_DAYS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RecheckConfig:
    return RecheckConfig(
        recheck_run_id=str(args.recheck_run_id),
        source_summary=args.source_summary,
        expected_source_summary_sha256=str(args.expected_source_summary_sha256),
        expected_source_artifact_sha256=str(args.expected_source_artifact_sha256),
        expected_run_id=str(args.expected_run_id),
        source_artifact=args.source_artifact,
        output_dir=args.output_dir,
        as_of_timestamp_utc=parse_timestamp(str(args.as_of_timestamp_utc or "")),
        price_dir=args.price_dir,
        outcome_window_days=int(args.outcome_window_days),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_recheck(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should surface structured failure where possible.
        print(f"short-horizon canary recheck failed: {v3.redact_error(str(exc))}", file=sys.stderr)
        return 2
    return 0 if summary.get("maturity_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
