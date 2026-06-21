#!/usr/bin/env python3
"""GOTRA v3.7C bootstrap/HAC eligibility preflight."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_7c.bootstrap_hac_eligibility_preflight_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7c.bootstrap_hac_eligibility_preflight_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_7c_bootstrap_hac_eligibility_preflight_"
SCRIPT_VERSION = "v3.7c-20260621"
EVIDENCE_LAYER = "engineering/local v3.7 bootstrap HAC eligibility preflight"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE_COUNT"
STATUS_INSUFFICIENT_CLUSTER = "INSUFFICIENT_CLUSTER_COVERAGE"
STATUS_INSUFFICIENT_DATE = "INSUFFICIENT_DATE_COVERAGE"
STATUS_INSUFFICIENT_TICKER = "INSUFFICIENT_TICKER_COVERAGE"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_FUTURE_DATA = "BLOCKED_FUTURE_DATA"
STATUS_BLOCKED_PAIRING = "BLOCKED_PAIRING"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"

BLOCKED_STATUSES = {
    STATUS_BLOCKED_SCHEMA,
    STATUS_BLOCKED_PROVENANCE,
    STATUS_BLOCKED_FUTURE_DATA,
    STATUS_BLOCKED_PAIRING,
    STATUS_BLOCKED_OVERCLAIM,
}

DETERMINISTIC_KINDS = {"deterministic_reference", "deterministic_price_only", "price_only_reference"}
FULL_GOTRA_KINDS = {"full_gotra"}
HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
DEFAULT_MIN_SAMPLE_COUNT = 4
DEFAULT_MIN_PAIRED_CLEAN_COUNT = 4
DEFAULT_MIN_TICKER_CLUSTERS = 2
DEFAULT_MIN_DATE_CLUSTERS = 2
DEFAULT_MIN_DATE_COVERAGE = 2
DEFAULT_MIN_TICKER_COVERAGE = 2

CLAIM_TEXT_FIELDS = (
    "summary",
    "claim",
    "claims",
    "notes",
    "narrative",
    "verdict",
    "verdict_claim",
    "winner",
    "winner_claim",
    "p_value",
    "pvalue",
    "ci",
    "confidence_interval",
)
DISALLOWED_ESTIMATE_FIELDS = {
    "winner",
    "winner_claim",
    "verdict",
    "verdict_claim",
    "p_value",
    "pvalue",
    "ci",
    "confidence_interval",
    "bootstrap_estimate",
    "hac_estimate",
}
NONNEGATIVE_COUNT_FIELDS = {
    "future_data_violation_count",
    "provenance_blocker_count",
    "pairing_blocker_count",
    "schema_blocker_count",
    "overclaim_blocker_count",
}


@dataclass(frozen=True)
class PreflightConfig:
    preflight_run_id: str
    output_dir: Path
    fixtures: tuple[Path, ...] = ()
    fixture_manifest: Path | None = None
    min_sample_count: int = DEFAULT_MIN_SAMPLE_COUNT
    min_paired_clean_count: int = DEFAULT_MIN_PAIRED_CLEAN_COUNT
    min_ticker_clusters: int = DEFAULT_MIN_TICKER_CLUSTERS
    min_date_clusters: int = DEFAULT_MIN_DATE_CLUSTERS
    min_date_coverage: int = DEFAULT_MIN_DATE_COVERAGE
    min_ticker_coverage: int = DEFAULT_MIN_TICKER_COVERAGE
    allow_overwrite: bool = False


@dataclass(frozen=True)
class FixtureRow:
    path: str
    payload: dict[str, Any]
    key: tuple[str, str, int]
    kind: str


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"preflight_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("preflight_run_id may contain only letters, numbers, '_' and '-'")


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


def blocker(path: Path | str, rule_id: str, reason: str) -> dict[str, Any]:
    return {"path": normalize_path(path), "rule_id": rule_id, "reason": reason}


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def valid_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value.strip()))


def canonical_kind(payload: dict[str, Any]) -> str:
    raw = str(payload.get("fixture_kind") or payload.get("kind") or payload.get("arm") or "")
    raw = raw.strip().lower()
    if raw in DETERMINISTIC_KINDS:
        return "deterministic_reference"
    if raw in FULL_GOTRA_KINDS:
        return "full_gotra"
    return raw


def key_from_payload(payload: dict[str, Any]) -> tuple[str, str, int] | None:
    ticker = str(payload.get("ticker") or "").strip()
    decision_date = str(payload.get("decision_date") or "").strip()
    horizon_days = int_value(payload.get("horizon_days"))
    if not ticker or not decision_date or horizon_days is None:
        return None
    return ticker, decision_date, horizon_days


def payload_entries(payload: Any, *, path: str, origin: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if isinstance(payload, dict) and isinstance(payload.get("fixtures"), list):
        raw_rows = payload["fixtures"]
    elif isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        raw_rows = payload["rows"]
    elif isinstance(payload, dict) and isinstance(payload.get("artifacts"), list):
        raw_rows = payload["artifacts"]
    elif isinstance(payload, list):
        raw_rows = payload
    elif isinstance(payload, dict):
        raw_rows = [payload]
    else:
        return [], [blocker(path, "malformed_fixture_root", "fixture JSON must be an object or list")]

    for index, entry in enumerate(raw_rows):
        row_path = f"{path}#{index}" if len(raw_rows) > 1 else path
        if not isinstance(entry, dict):
            blockers.append(blocker(row_path, "malformed_fixture_row", "fixture row must be an object"))
            continue
        if "payload" in entry:
            payload_entry = entry.get("payload")
            entry_path = normalize_path(str(entry.get("path") or row_path))
            if entry_path and claim_scan.forbidden_path(entry_path):
                blockers.append(blocker(entry_path, "forbidden_fixture_path", "embedded fixture path is forbidden"))
                continue
            if not isinstance(payload_entry, dict):
                blockers.append(blocker(entry_path or row_path, "malformed_fixture_payload", "payload must be an object"))
                continue
            row = dict(payload_entry)
            row.setdefault("fixture_path", entry_path or row_path)
            rows.append(row)
            continue
        row = dict(entry)
        row.setdefault("fixture_path", row_path)
        rows.append(row)
    return rows, blockers


def load_fixture_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized = normalize_path(path)
    if claim_scan.forbidden_path(normalized):
        return [], [blocker(normalized, "forbidden_fixture_path", "fixture path is forbidden")]
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [], [blocker(normalized, "fixture_load_error", str(exc))]
    return payload_entries(payload, path=normalized, origin="file")


def load_manifest(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized = normalize_path(path)
    if claim_scan.forbidden_path(normalized):
        return [], [blocker(normalized, "forbidden_manifest_path", "manifest path is forbidden")]
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [], [blocker(normalized, "manifest_load_error", str(exc))]
    if not isinstance(payload, dict):
        return [], [blocker(normalized, "malformed_manifest_root", "manifest must be a JSON object")]
    raw = payload.get("fixtures", payload.get("rows", payload.get("artifacts", [])))
    if not isinstance(raw, list):
        return [], [blocker(normalized, "malformed_manifest_rows", "manifest fixtures/rows must be a list")]
    return payload_entries(raw, path=normalized, origin="manifest")


def collect_payloads(config: PreflightConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if config.fixture_manifest:
        manifest_rows, manifest_blockers = load_manifest(config.fixture_manifest)
        rows.extend(manifest_rows)
        blockers.extend(manifest_blockers)
    for path in config.fixtures:
        file_rows, file_blockers = load_fixture_file(path)
        rows.extend(file_rows)
        blockers.extend(file_blockers)
    return rows, blockers


def validate_schema(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    failures: list[str] = []
    key = key_from_payload(payload)
    if key is None:
        failures.append("ticker/decision_date/horizon_days")
    else:
        _ticker, decision_date, horizon_days = key
        try:
            date.fromisoformat(decision_date)
        except ValueError:
            failures.append("decision_date")
        if horizon_days <= 0:
            failures.append("horizon_days")

    kind = canonical_kind(payload)
    if kind not in {"deterministic_reference", "full_gotra"}:
        failures.append("kind")
    if payload.get("outcome_status") not in {"RESOLVED", "SCORED"}:
        failures.append("outcome_status")
    if payload.get("evidence_layer") != EVIDENCE_LAYER:
        failures.append("evidence_layer")
    for flag in ("provider_or_backend_called", "codex_cli_called", "formal_lite_entered"):
        if payload.get(flag) is not False:
            failures.append(flag)
    for field in ("actual_change_pct", "decision_price", "outcome_price"):
        value = payload.get(field)
        if value is not None and isinstance(value, bool):
            failures.append(field)
        elif value is not None and not isinstance(value, (int, float)):
            failures.append(field)
    for field in NONNEGATIVE_COUNT_FIELDS:
        if field in payload:
            value = int_value(payload.get(field))
            if value is None or value < 0:
                failures.append(field)

    if failures:
        return [blocker(path, "missing_or_invalid_fixture_schema_field", ",".join(sorted(set(failures))))]
    return []


def provenance_values(payload: dict[str, Any]) -> dict[str, str]:
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    return {
        "source_run_id": str(payload.get("source_run_id") or provenance.get("source_run_id") or ""),
        "source_artifact_path": str(
            payload.get("source_artifact_path") or provenance.get("source_artifact_path") or ""
        ),
        "source_artifact_sha256": str(
            payload.get("source_artifact_sha256")
            or payload.get("source_hash")
            or provenance.get("source_artifact_sha256")
            or provenance.get("source_hash")
            or ""
        ),
    }


def validate_provenance(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return [blocker(path, "missing_provenance", "provenance must be an object")]

    values = provenance_values(payload)
    failures = [key for key, value in values.items() if not value.strip()]
    mismatches = []
    for key in ("source_run_id", "source_artifact_path", "source_artifact_sha256"):
        top_value = payload.get(key)
        provenance_value = provenance.get(key) or provenance.get("source_hash")
        if top_value is not None and provenance_value is not None and str(top_value) != str(provenance_value):
            mismatches.append(key)
    if not valid_hash(values["source_artifact_sha256"]):
        failures.append("source_artifact_sha256")
    if values["source_artifact_path"] and claim_scan.forbidden_path(values["source_artifact_path"]):
        failures.append("source_artifact_path_forbidden")
    local_path = Path(values["source_artifact_path"]).expanduser()
    if local_path.exists() and local_path.is_file():
        if sha256_file(local_path) != values["source_artifact_sha256"].lower():
            failures.append("source_artifact_sha256_mismatch")
    failures.extend(mismatches)
    if failures:
        return [blocker(path, "missing_or_invalid_provenance", ",".join(sorted(set(failures))))]
    return []


def future_data_blockers(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    count = int_value(payload.get("future_data_violation_count"))
    if payload.get("future_data_violation") is True or (count is not None and count > 0):
        return [blocker(path, "future_data_violation", "future-data violation count must be zero")]
    if count is not None and count < 0:
        return [blocker(path, "invalid_future_data_violation_count", "future-data count cannot be negative")]
    return []


def claim_sources_for_payload(payload: dict[str, Any], path: str) -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    for field in CLAIM_TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            sources.append(claim_scan.ScanSource(path=f"{path}:{field}", text=value, origin="fixture"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    sources.append(
                        claim_scan.ScanSource(
                            path=f"{path}:{field}[{index}]",
                            text=item,
                            origin="fixture",
                        )
                    )
    return sources


def overclaim_blockers(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if payload.get("winner_emitted") is True:
        blockers.append(blocker(path, "winner_emitted_not_allowed", "winner emission is not allowed"))
    for field in DISALLOWED_ESTIMATE_FIELDS:
        if field in payload and payload.get(field) not in (None, "", False, [], {}):
            blockers.append(blocker(path, f"{field}_not_allowed", "verdict estimate fields are not allowed"))
    scan = claim_scan.scan_sources(claim_sources_for_payload(payload, path))
    blockers.extend(scan["overclaim"])
    blockers.extend(scan["direct_llm"])
    blockers.extend(scan["maturity_gate"])
    blockers.extend(scan["short_horizon_as_30d"])
    return blockers


def to_fixture_row(payload: dict[str, Any], path: str) -> FixtureRow | None:
    key = key_from_payload(payload)
    kind = canonical_kind(payload)
    if key is None or kind not in {"deterministic_reference", "full_gotra"}:
        return None
    return FixtureRow(path=path, payload=payload, key=key, kind=kind)


def pairing_metrics(rows: list[FixtureRow]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deterministic: dict[tuple[str, str, int], FixtureRow] = {}
    full: dict[tuple[str, str, int], FixtureRow] = {}
    pairing_blockers: list[dict[str, Any]] = []
    duplicate_pair_count = 0

    for row in rows:
        target = deterministic if row.kind == "deterministic_reference" else full
        if row.key in target:
            duplicate_pair_count += 1
            pairing_blockers.append(
                blocker(row.path, "duplicate_pair_key", f"duplicate {row.kind} key {row.key!r}")
            )
            continue
        target[row.key] = row

    deterministic_keys = set(deterministic)
    full_keys = set(full)
    paired_keys = sorted(deterministic_keys & full_keys)
    for key in sorted((deterministic_keys | full_keys) - set(paired_keys)):
        reason = "missing_full_gotra_pair" if key in deterministic_keys else "missing_deterministic_reference_pair"
        source_row = deterministic.get(key) or full.get(key)
        source_path = source_row.path if source_row else "unknown"
        pairing_blockers.append(blocker(source_path, reason, f"unpaired key {key!r}"))

    tickers = {key[0] for key in paired_keys}
    dates = {key[1] for key in paired_keys}
    union_key_count = len(deterministic_keys | full_keys)
    paired_clean_count = len(paired_keys)
    ratio = paired_clean_count / union_key_count if union_key_count else 0.0
    metrics = {
        "sample_count": paired_clean_count,
        "paired_clean_count": paired_clean_count,
        "ticker_cluster_count": len(tickers),
        "date_cluster_count": len(dates),
        "date_coverage_count": len(dates),
        "ticker_coverage_count": len(tickers),
        "deterministic_reference_available_count": len(deterministic),
        "full_gotra_available_count": len(full),
        "paired_coverage_ratio": ratio,
        "duplicate_pair_count": duplicate_pair_count,
    }
    return metrics, pairing_blockers


def base_summary(config: PreflightConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "preflight_run_id": config.preflight_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "preflight_status": STATUS_DATA_INSUFFICIENT,
        "sample_count": 0,
        "paired_clean_count": 0,
        "ticker_cluster_count": 0,
        "date_cluster_count": 0,
        "date_coverage_count": 0,
        "ticker_coverage_count": 0,
        "deterministic_reference_available_count": 0,
        "full_gotra_available_count": 0,
        "paired_coverage_ratio": 0.0,
        "bootstrap_eligible": False,
        "hac_eligible": False,
        "cluster_eligible": False,
        "future_data_violation_count": 0,
        "provenance_blocker_count": 0,
        "pairing_blocker_count": 0,
        "schema_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "winner_emitted": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "blocker_reasons": [],
        "blocked_items": [],
        "non_claims": {
            "not_actual_30d_verdict": True,
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "no_winner_pvalue_or_ci": True,
        },
    }


def choose_status(summary: dict[str, Any], config: PreflightConfig) -> str:
    if summary["schema_blocker_count"]:
        return STATUS_BLOCKED_SCHEMA
    if summary["provenance_blocker_count"]:
        return STATUS_BLOCKED_PROVENANCE
    if summary["future_data_violation_count"]:
        return STATUS_BLOCKED_FUTURE_DATA
    if summary["overclaim_blocker_count"]:
        return STATUS_BLOCKED_OVERCLAIM
    if summary["pairing_blocker_count"]:
        return STATUS_BLOCKED_PAIRING
    if summary["sample_count"] == 0:
        return STATUS_DATA_INSUFFICIENT
    if summary["sample_count"] < config.min_sample_count:
        return STATUS_INSUFFICIENT_SAMPLE
    if not summary["cluster_eligible"]:
        return STATUS_INSUFFICIENT_CLUSTER
    if summary["date_coverage_count"] < config.min_date_coverage:
        return STATUS_INSUFFICIENT_DATE
    if summary["ticker_coverage_count"] < config.min_ticker_coverage:
        return STATUS_INSUFFICIENT_TICKER
    return STATUS_READY


def build_summary(config: PreflightConfig, *, run_root: Path) -> dict[str, Any]:
    payloads, load_blockers = collect_payloads(config)
    schema_blockers: list[dict[str, Any]] = list(load_blockers)
    provenance_blockers: list[dict[str, Any]] = []
    future_blockers: list[dict[str, Any]] = []
    overclaim_blockers_list: list[dict[str, Any]] = []
    rows: list[FixtureRow] = []

    for index, payload in enumerate(payloads):
        path = normalize_path(str(payload.get("fixture_path") or f"manifest_payload#{index}"))
        schema_blockers.extend(validate_schema(payload, path))
        provenance_blockers.extend(validate_provenance(payload, path))
        future_blockers.extend(future_data_blockers(payload, path))
        overclaim_blockers_list.extend(overclaim_blockers(payload, path))
        row = to_fixture_row(payload, path)
        if row:
            rows.append(row)

    pairing_summary, pairing_blockers = pairing_metrics(rows)
    summary = base_summary(config, run_root=run_root)
    summary.update(pairing_summary)
    future_data_violation_count = len(future_blockers)
    bootstrap_eligible = (
        int(summary["sample_count"]) >= config.min_sample_count
        and int(summary["paired_clean_count"]) >= config.min_paired_clean_count
    )
    cluster_eligible = (
        int(summary["ticker_cluster_count"]) >= config.min_ticker_clusters
        and int(summary["date_cluster_count"]) >= config.min_date_clusters
    )
    hac_eligible = bootstrap_eligible and int(summary["date_cluster_count"]) >= config.min_date_clusters
    blockers = schema_blockers + provenance_blockers + future_blockers + overclaim_blockers_list + pairing_blockers
    summary.update(
        {
            "bootstrap_eligible": bootstrap_eligible,
            "hac_eligible": hac_eligible,
            "cluster_eligible": cluster_eligible,
            "future_data_violation_count": future_data_violation_count,
            "provenance_blocker_count": len(provenance_blockers),
            "pairing_blocker_count": len(pairing_blockers),
            "schema_blocker_count": len(schema_blockers),
            "overclaim_blocker_count": len(overclaim_blockers_list),
            "blocker_reasons": [str(item.get("rule_id") or "") for item in blockers],
            "blocked_items": blockers,
        }
    )
    summary["preflight_status"] = choose_status(summary, config)
    return summary


def write_outputs(config: PreflightConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "preflight_run_id": config.preflight_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "fixture_manifest": normalize_path(config.fixture_manifest),
        "fixtures": [normalize_path(path) for path in config.fixtures],
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def blocked_run_id_summary(config: PreflightConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "preflight_status": STATUS_BLOCKED_SCHEMA,
            "schema_blocker_count": 1,
            "blocker_reasons": ["output_run_id_exists"],
            "blocked_items": [blocker(run_root, "output_run_id_exists", "output run id exists")],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_preflight(config: PreflightConfig) -> dict[str, Any]:
    validate_run_id(config.preflight_run_id)
    run_root = config.output_dir / config.preflight_run_id
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
    parser.add_argument("--fixture", action="append", type=Path, default=[])
    parser.add_argument("--fixture-manifest", type=Path, default=None)
    parser.add_argument("--preflight-run-id", default=default_run_id())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_7c_bootstrap_hac_eligibility_preflight/runs"),
    )
    parser.add_argument("--min-sample-count", type=int, default=DEFAULT_MIN_SAMPLE_COUNT)
    parser.add_argument("--min-paired-clean-count", type=int, default=DEFAULT_MIN_PAIRED_CLEAN_COUNT)
    parser.add_argument("--min-ticker-clusters", type=int, default=DEFAULT_MIN_TICKER_CLUSTERS)
    parser.add_argument("--min-date-clusters", type=int, default=DEFAULT_MIN_DATE_CLUSTERS)
    parser.add_argument("--min-date-coverage", type=int, default=DEFAULT_MIN_DATE_COVERAGE)
    parser.add_argument("--min-ticker-coverage", type=int, default=DEFAULT_MIN_TICKER_COVERAGE)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PreflightConfig:
    return PreflightConfig(
        preflight_run_id=str(args.preflight_run_id),
        output_dir=args.output_dir,
        fixtures=tuple(args.fixture or ()),
        fixture_manifest=args.fixture_manifest,
        min_sample_count=int(args.min_sample_count),
        min_paired_clean_count=int(args.min_paired_clean_count),
        min_ticker_clusters=int(args.min_ticker_clusters),
        min_date_clusters=int(args.min_date_clusters),
        min_date_coverage=int(args.min_date_coverage),
        min_ticker_coverage=int(args.min_ticker_coverage),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_preflight(config_from_args(parse_args(argv)))
    return 2 if summary["preflight_status"] in BLOCKED_STATUSES else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
