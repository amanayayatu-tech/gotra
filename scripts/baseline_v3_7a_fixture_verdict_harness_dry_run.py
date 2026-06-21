#!/usr/bin/env python3
"""GOTRA v3.7A fixture-only verdict harness dry-run."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7a.fixture_verdict_harness_dry_run_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7a.fixture_verdict_harness_dry_run_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_7a_fixture_verdict_harness_dry_run_"
SCRIPT_VERSION = "v3.7a-20260621"
EVIDENCE_LAYER = "engineering/local v3.7 fixture-only harness dry-run"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_7_FIXTURE_HARNESS_READY"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
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

DETERMINISTIC_KINDS = {
    "deterministic_reference",
    "deterministic_price_only",
    "price_only_reference",
}
FULL_GOTRA_KINDS = {"full_gotra"}
CLAIM_TEXT_FIELDS = (
    "summary",
    "claim",
    "claims",
    "notes",
    "rationale",
    "statement",
    "verdict",
    "verdict_claim",
    "winner",
    "winner_claim",
)


@dataclass(frozen=True)
class FixtureHarnessConfig:
    harness_run_id: str
    output_dir: Path
    fixtures: tuple[Path, ...] = ()
    fixture_manifest: Path | None = None
    allow_overwrite: bool = False


@dataclass(frozen=True)
class FixtureRecord:
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
        raise ValueError(f"harness_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("harness_run_id may contain only letters, numbers, '_' and '-'")


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


def load_fixture_manifest(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        return [], [blocker(path, "malformed_manifest_root", "fixture manifest must be a JSON object")]
    raw = payload.get("fixtures", payload.get("artifacts", []))
    if not isinstance(raw, list):
        return [], [
            blocker(
                path,
                "malformed_manifest_fixtures",
                "fixture manifest fixtures/artifacts must be a list",
            )
        ]
    records: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            blockers.append(
                blocker(
                    path,
                    "malformed_manifest_fixture_entry",
                    f"fixture manifest entry {index} must be an object",
                )
            )
            continue
        if "payload" in entry:
            payload_entry = entry.get("payload")
            if not isinstance(payload_entry, dict):
                blockers.append(
                    blocker(
                        path,
                        "malformed_manifest_payload",
                        f"fixture manifest entry {index} payload must be an object",
                    )
                )
                continue
            record = dict(payload_entry)
            if entry.get("path") and not record.get("fixture_path"):
                record["fixture_path"] = str(entry["path"])
            records.append(record)
            continue
        if entry.get("path") and set(entry).issubset({"path", "filename"}):
            fixture_path = Path(str(entry.get("path") or entry.get("filename") or ""))
            if not fixture_path.is_absolute():
                fixture_path = path.parent / fixture_path
            records_from_path, path_blockers = load_fixture_file(fixture_path)
            records.extend(records_from_path)
            blockers.extend(path_blockers)
            continue
        records.append(dict(entry))
    return records, blockers


def load_fixture_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized = normalize_path(path)
    if claim_scan.forbidden_path(normalized):
        return [], [blocker(normalized, "forbidden_fixture_path", "fixture path is forbidden")]
    payload = load_json(path)
    if isinstance(payload, list):
        records = []
        blockers = []
        for index, entry in enumerate(payload):
            if isinstance(entry, dict):
                record = dict(entry)
                record.setdefault("fixture_path", normalized)
                records.append(record)
            else:
                blockers.append(
                    blocker(
                        normalized,
                        "malformed_fixture_row",
                        f"fixture row {index} must be an object",
                    )
                )
        return records, blockers
    if isinstance(payload, dict) and isinstance(payload.get("fixtures"), list):
        records = []
        blockers = []
        for index, entry in enumerate(payload["fixtures"]):
            if isinstance(entry, dict):
                record = dict(entry)
                record.setdefault("fixture_path", normalized)
                records.append(record)
            else:
                blockers.append(
                    blocker(
                        normalized,
                        "malformed_fixture_row",
                        f"fixture row {index} must be an object",
                    )
                )
        return records, blockers
    if isinstance(payload, dict):
        record = dict(payload)
        record.setdefault("fixture_path", normalized)
        return [record], []
    return [], [blocker(normalized, "malformed_fixture_root", "fixture JSON must be an object or list")]


def collect_fixture_payloads(
    config: FixtureHarnessConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if config.fixture_manifest:
        manifest_path = normalize_path(config.fixture_manifest)
        if claim_scan.forbidden_path(manifest_path):
            blockers.append(blocker(manifest_path, "forbidden_manifest_path", "manifest path is forbidden"))
        else:
            manifest_records, manifest_blockers = load_fixture_manifest(config.fixture_manifest)
            records.extend(manifest_records)
            blockers.extend(manifest_blockers)
    for path in config.fixtures:
        loaded, path_blockers = load_fixture_file(path)
        records.extend(loaded)
        blockers.extend(path_blockers)
    return records, blockers


def blocker(path: Path | str, rule_id: str, reason: str) -> dict[str, Any]:
    return {
        "path": normalize_path(path),
        "rule_id": rule_id,
        "reason": reason,
    }


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


def canonical_kind(payload: dict[str, Any]) -> str:
    raw_kind = str(payload.get("fixture_kind") or payload.get("kind") or payload.get("arm") or "")
    raw_kind = raw_kind.strip().lower()
    if raw_kind in DETERMINISTIC_KINDS:
        return "deterministic"
    if raw_kind in FULL_GOTRA_KINDS:
        return "full_gotra"
    return ""


def pair_key(payload: dict[str, Any]) -> tuple[str, str, int] | None:
    ticker = payload.get("ticker")
    decision_date = payload.get("decision_date")
    horizon_days = int_value(payload.get("horizon_days"))
    if not non_empty_string(ticker) or not non_empty_string(decision_date) or horizon_days is None:
        return None
    try:
        date.fromisoformat(str(decision_date))
    except ValueError:
        return None
    if horizon_days <= 0:
        return None
    return str(ticker).upper(), str(decision_date), horizon_days


def source_hash(payload: dict[str, Any]) -> str:
    return str(
        payload.get("source_hash")
        or payload.get("source_artifact_sha256")
        or payload.get("source_artifact_hash")
        or ""
    ).strip()


def provenance_source_hash(provenance: dict[str, Any]) -> str:
    return str(
        provenance.get("source_hash")
        or provenance.get("source_artifact_sha256")
        or provenance.get("source_artifact_hash")
        or ""
    ).strip()


def future_data_blocked(payload: dict[str, Any]) -> bool:
    if payload.get("future_data_violation") is True:
        return True
    if payload.get("source_future_data_violation") is True:
        return True
    raw_count = payload.get("future_data_violation_count", 0)
    try:
        return int(raw_count or 0) > 0
    except (TypeError, ValueError):
        return True


def claim_source_texts(path: str, payload: dict[str, Any]) -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    for field in CLAIM_TEXT_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if isinstance(value, str):
            text = value
        elif isinstance(value, list):
            text = "\n".join(str(item) for item in value if isinstance(item, str))
        else:
            text = ""
        if text:
            sources.append(
                claim_scan.ScanSource(
                    path=f"{path}#{field}",
                    text=text,
                    origin="fixture_field",
                )
            )
    return sources


def winner_or_verdict_claim_present(payload: dict[str, Any]) -> bool:
    if payload.get("winner_emitted") is True:
        return True
    for field in ("winner", "winner_claim", "verdict", "verdict_claim"):
        if field not in payload:
            continue
        value = payload[field]
        if value in (False, None, "", [], {}):
            continue
        if isinstance(value, str) and value.strip().lower() in {"none", "not_emitted", "not emitted"}:
            continue
        return True
    return False


def validate_fixture_payload(
    payload: dict[str, Any],
) -> tuple[FixtureRecord | None, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    path = str(payload.get("fixture_path") or payload.get("source_artifact_path") or "inline_fixture")
    schema_blockers: list[dict[str, Any]] = []
    provenance_blockers: list[dict[str, Any]] = []
    future_blockers: list[dict[str, Any]] = []
    overclaim_blockers: list[dict[str, Any]] = []

    kind = canonical_kind(payload)
    if not kind:
        schema_blockers.append(blocker(path, "unknown_fixture_kind", "fixture kind must be deterministic_reference or full_gotra"))
    key = pair_key(payload)
    if key is None:
        schema_blockers.append(blocker(path, "invalid_pair_key", "ticker, decision_date, and positive horizon_days are required"))

    if winner_or_verdict_claim_present(payload):
        overclaim_blockers.append(
            blocker(path, "winner_or_verdict_claim_present", "fixture-only harness cannot emit winner or verdict claim")
        )

    claim_result = claim_scan.scan_sources(claim_source_texts(path, payload))
    for category in ("overclaim", "direct_llm", "maturity_gate", "short_horizon_as_30d"):
        for item in claim_result[category]:
            overclaim_blockers.append(
                blocker(
                    item.get("path", path),
                    str(item.get("rule_id") or category),
                    str(item.get("reason") or "claim boundary violation"),
                )
            )

    if future_data_blocked(payload):
        future_blockers.append(blocker(path, "future_data_violation", "fixture declares future-data violation"))

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        provenance_blockers.append(blocker(path, "missing_provenance", "fixture provenance object is required"))
        provenance = {}

    top_source_run_id = str(payload.get("source_run_id") or "").strip()
    provenance_source_run_id = str(provenance.get("source_run_id") or "").strip()
    if not top_source_run_id:
        provenance_blockers.append(blocker(path, "missing_source_run_id", "source_run_id is required"))
    if not provenance_source_run_id:
        provenance_blockers.append(blocker(path, "missing_provenance_source_run_id", "provenance.source_run_id is required"))
    if top_source_run_id and provenance_source_run_id and top_source_run_id != provenance_source_run_id:
        provenance_blockers.append(blocker(path, "source_run_id_mismatch", "source_run_id must match provenance.source_run_id"))

    top_hash = source_hash(payload)
    provenance_hash = provenance_source_hash(provenance)
    if not top_hash:
        provenance_blockers.append(blocker(path, "missing_source_hash", "source hash is required"))
    if not provenance_hash:
        provenance_blockers.append(blocker(path, "missing_provenance_source_hash", "provenance source hash is required"))
    if top_hash and provenance_hash and top_hash != provenance_hash:
        provenance_blockers.append(blocker(path, "source_hash_mismatch", "source hash must match provenance source hash"))

    for field_path in (
        payload.get("source_artifact_path"),
        payload.get("fixture_path"),
        provenance.get("source_artifact_path"),
    ):
        if non_empty_string(field_path) and claim_scan.forbidden_path(str(field_path)):
            provenance_blockers.append(
                blocker(
                    str(field_path),
                    "forbidden_source_artifact_path",
                    "source artifact path is forbidden for fixture-only harness",
                )
            )

    if schema_blockers or key is None or not kind:
        return None, schema_blockers, provenance_blockers, future_blockers, overclaim_blockers
    return (
        FixtureRecord(path=normalize_path(path), payload=payload, key=key, kind=kind),
        schema_blockers,
        provenance_blockers,
        future_blockers,
        overclaim_blockers,
    )


def duplicate_key_count(records: list[FixtureRecord], kind: str) -> int:
    seen: dict[tuple[str, str, int], int] = {}
    for record in records:
        if record.kind != kind:
            continue
        seen[record.key] = seen.get(record.key, 0) + 1
    return sum(1 for count in seen.values() if count > 1)


def paired_clean_count(records: list[FixtureRecord]) -> int:
    deterministic_keys = {record.key for record in records if record.kind == "deterministic"}
    full_keys = {record.key for record in records if record.kind == "full_gotra"}
    return len(deterministic_keys & full_keys)


def unpaired_count(records: list[FixtureRecord]) -> int:
    deterministic_keys = {record.key for record in records if record.kind == "deterministic"}
    full_keys = {record.key for record in records if record.kind == "full_gotra"}
    paired = deterministic_keys & full_keys
    return sum(1 for record in records if record.key not in paired)


def status_for_summary(summary: dict[str, Any]) -> str:
    if summary["overclaim_blocker_count"]:
        return STATUS_BLOCKED_OVERCLAIM
    if summary["schema_blocker_count"]:
        return STATUS_BLOCKED_SCHEMA
    if summary["future_data_violation_count"]:
        return STATUS_BLOCKED_FUTURE_DATA
    if summary["provenance_blocker_count"]:
        return STATUS_BLOCKED_PROVENANCE
    if summary["input_fixture_count"] == 0:
        return STATUS_DATA_INSUFFICIENT
    if (
        summary["deterministic_fixture_count"] == 0
        or summary["full_gotra_fixture_count"] == 0
        or summary["duplicate_pair_count"] > 0
        or summary["unpaired_fixture_count"] > 0
        or summary["paired_clean_count"] == 0
    ):
        return STATUS_BLOCKED_PAIRING
    return STATUS_READY


def base_summary(config: FixtureHarnessConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "harness_run_id": config.harness_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "harness_status": STATUS_DATA_INSUFFICIENT,
        "evidence_layer": EVIDENCE_LAYER,
        "input_fixture_count": 0,
        "fixture_pair_count": 0,
        "deterministic_fixture_count": 0,
        "full_gotra_fixture_count": 0,
        "paired_clean_count": 0,
        "duplicate_pair_count": 0,
        "unpaired_fixture_count": 0,
        "future_data_violation_count": 0,
        "provenance_blocker_count": 0,
        "schema_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "blocker_reasons": [],
        "blocked_items": [],
        "winner_emitted": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_allowed": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "non_claims": [
            "not an actual 30D forward-live verdict",
            "not OOS evidence",
            "not science/public proof",
            "not trading or investment advice",
            "no deterministic/full_gotra/ksana winner emitted",
            "does not bypass the 2026-07-21 30D maturity gate",
        ],
    }


def build_summary(config: FixtureHarnessConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    raw_payloads, collection_blockers = collect_fixture_payloads(config)
    valid_records: list[FixtureRecord] = []
    blocked_items = list(collection_blockers)
    for payload in raw_payloads:
        if not isinstance(payload, dict):
            blocked_items.append(blocker("inline_fixture", "malformed_fixture_row", "fixture row must be an object"))
            continue
        record, schema_blockers, provenance_blockers, future_blockers, overclaim_blockers = validate_fixture_payload(payload)
        blocked_items.extend(schema_blockers)
        blocked_items.extend(provenance_blockers)
        blocked_items.extend(future_blockers)
        blocked_items.extend(overclaim_blockers)
        if record is not None:
            valid_records.append(record)

    deterministic_count = sum(1 for record in valid_records if record.kind == "deterministic")
    full_count = sum(1 for record in valid_records if record.kind == "full_gotra")
    duplicate_count = duplicate_key_count(valid_records, "deterministic") + duplicate_key_count(
        valid_records,
        "full_gotra",
    )
    paired_count = paired_clean_count(valid_records)
    unpaired = unpaired_count(valid_records)

    summary.update(
        {
            "input_fixture_count": len(raw_payloads),
            "fixture_pair_count": paired_count,
            "deterministic_fixture_count": deterministic_count,
            "full_gotra_fixture_count": full_count,
            "paired_clean_count": paired_count,
            "duplicate_pair_count": duplicate_count,
            "unpaired_fixture_count": unpaired,
            "future_data_violation_count": sum(
                1 for item in blocked_items if item.get("rule_id") == "future_data_violation"
            ),
            "provenance_blocker_count": sum(
                1
                for item in blocked_items
                if str(item.get("rule_id") or "").startswith(
                    (
                        "missing_",
                        "source_",
                        "forbidden_source",
                        "forbidden_fixture_path",
                        "forbidden_manifest_path",
                    )
                )
            ),
            "schema_blocker_count": sum(
                1
                for item in blocked_items
                if str(item.get("rule_id") or "").startswith(
                    ("malformed_", "unknown_fixture_kind", "invalid_pair_key")
                )
            ),
            "overclaim_blocker_count": sum(
                1
                for item in blocked_items
                if str(item.get("rule_id") or "")
                in {
                    "winner_or_verdict_claim_present",
                    "oos_science_public_trading_claim",
                    "provider_runtime_as_public_claim",
                    "direct_llm_without_parametric_memory_control",
                    "direct_llm_clean_no_future_baseline",
                    "v3_7_allowed_true",
                    "v3_7_verdict_allowed",
                    "v3_7_plain_allowed",
                    "thirty_day_forward_live_verdict",
                    "short_horizon_as_30d_verdict",
                }
            ),
            "blocked_items": blocked_items,
        }
    )
    summary["harness_status"] = status_for_summary(summary)
    if summary["harness_status"] == STATUS_BLOCKED_PAIRING:
        reasons = []
        if deterministic_count == 0:
            reasons.append("missing_deterministic_fixture")
        if full_count == 0:
            reasons.append("missing_full_gotra_fixture")
        if duplicate_count:
            reasons.append("duplicate_pair_key")
        if unpaired:
            reasons.append("unpaired_fixture_rows")
        if paired_count == 0:
            reasons.append("no_clean_fixture_pairs")
        summary["blocker_reasons"] = sorted(set(reasons))
    else:
        summary["blocker_reasons"] = sorted(
            {
                str(item.get("rule_id") or "")
                for item in blocked_items
                if str(item.get("rule_id") or "")
            }
        )
    return summary


def write_outputs(config: FixtureHarnessConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "harness_run_id": config.harness_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "harness_status": summary["harness_status"],
        "fixtures": [normalize_path(path) for path in config.fixtures],
        "fixture_manifest": normalize_path(config.fixture_manifest),
        "winner_emitted": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def blocked_run_id_summary(config: FixtureHarnessConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "harness_status": STATUS_BLOCKED_SCHEMA,
            "schema_blocker_count": 1,
            "blocker_reasons": ["output_run_id_exists"],
            "blocked_items": [
                blocker(run_root, "output_run_id_exists", "output run id exists")
            ],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_harness(config: FixtureHarnessConfig) -> dict[str, Any]:
    validate_run_id(config.harness_run_id)
    run_root = config.output_dir / config.harness_run_id
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
    parser.add_argument("--harness-run-id", default=default_run_id())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_7a_fixture_verdict_harness_dry_run/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> FixtureHarnessConfig:
    return FixtureHarnessConfig(
        harness_run_id=str(args.harness_run_id),
        output_dir=args.output_dir,
        fixtures=tuple(args.fixture or ()),
        fixture_manifest=args.fixture_manifest,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_harness(config_from_args(parse_args(argv)))
    return 1 if summary.get("harness_status") in BLOCKED_STATUSES else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
