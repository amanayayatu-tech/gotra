#!/usr/bin/env python3
"""GOTRA v3.7J short-horizon report template/schema validator."""

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
from scripts import baseline_v3_7h_claim_boundary_regression as claim_regression  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7j.short_horizon_report_template_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7j.short_horizon_report_template_manifest.v1"
REPORT_SCHEMA_VERSION = "gotra.baseline_v3_7j.short_horizon_report.v1"
RUN_ID_PREFIX = "baseline_v3_7j_short_horizon_report_template_"
SCRIPT_VERSION = "v3.7j-20260622"
EVIDENCE_LAYER = "short_horizon_forward_live_canary_engineering"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "SHORT_HORIZON_REPORT_TEMPLATE_READY"
STATUS_NOT_MATURED = "SHORT_HORIZON_NOT_MATURED"
STATUS_BLOCKED_DATA = "BLOCKED_DATA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_RUN_ID_EXISTS = "SHORT_HORIZON_REPORT_TEMPLATE_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY, STATUS_NOT_MATURED}
HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
ALLOWED_HORIZONS = {"1D", "3D", "5D", "NEXT_CLOSE", "NEXT-CLOSE", "NEXT_CLOSE"}
VALID_DIRECTIONS = {"long", "avoid", "neutral"}
READY_MATURITY_STATUSES = {"SHORT_HORIZON_READY", STATUS_READY, "READY", "RESOLVED"}
NOT_MATURED_STATUSES = {STATUS_NOT_MATURED, "NOT_MATURED", "DATA_NOT_MATURED"}
BLOCKED_DATA_STATUSES = {STATUS_BLOCKED_DATA, "DATA_MISSING", "PRICE_MISSING"}
REQUIRED_FIELDS = (
    "report_schema_version",
    "source_run_id",
    "source_summary_sha256",
    "source_artifact_path",
    "source_artifact_sha256",
    "capture_timestamp",
    "horizon",
    "horizon_end_date",
    "maturity_status",
    "outcome_status",
    "decision_price",
    "outcome_price",
    "actual_change_pct",
    "actual_direction",
    "resolved_count",
    "scored_count",
    "readiness_status",
    "next_check_after",
    "blocker_reasons",
    "evidence_layer",
    "actual_30d_readiness_status",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "direct_llm_interpretation",
    "non_claims",
)
REQUIRED_FALSE_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
)
BOUNDARY_CRITICAL_FIELDS = (
    "source_run_id",
    "source_summary_sha256",
    "source_artifact_path",
    "source_artifact_sha256",
    "horizon",
    "maturity_status",
    "outcome_status",
    "evidence_layer",
    "actual_30d_readiness_status",
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "provider_or_backend_called",
    "codex_cli_new_call",
    "formal_lite_entered",
    "direct_llm_interpretation",
)


@dataclass(frozen=True)
class ReportConfig:
    template_run_id: str
    report: Path
    output_dir: Path
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"template_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("template_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def normalize_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    return claim_scan.normalize_scan_path(path)


def blocked_item(path: Path | str, rule_id: str, reason: str, *, line_number: int = 0) -> dict[str, Any]:
    return {
        "path": normalize_path(path),
        "line_number": line_number,
        "rule_id": rule_id,
        "reason": reason,
    }


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value.strip()))


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def number_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_report(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if claim_scan.forbidden_path(normalize_path(path)):
        return {}, [blocked_item(path, "forbidden_report_path", "report path is forbidden")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [blocked_item(path, "report_read_error", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [blocked_item(path, "report_json_decode_error", str(exc))]
    if not isinstance(payload, dict):
        return {}, [blocked_item(path, "report_root_not_object", "report must be a JSON object")]
    return payload, []


def resolve_report_relative(path_value: str, *, report_path: Path) -> Path:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate
    return (report_path.parent / candidate).resolve()


def schema_blockers(report: dict[str, Any], *, report_path: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for field in REQUIRED_FIELDS:
        if field not in report:
            blockers.append(blocked_item("report", f"missing_{field}", f"{field} is required"))
    if blockers:
        return blockers

    if report.get("report_schema_version") != REPORT_SCHEMA_VERSION:
        blockers.append(blocked_item("report", "report_schema_version_mismatch", f"must be {REPORT_SCHEMA_VERSION}"))
    if report.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocked_item("report", "evidence_layer_mismatch", f"must be {EVIDENCE_LAYER}"))
    if report.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(
            blocked_item(
                "report",
                "actual_30d_readiness_status_not_data_not_matured",
                "actual 30D readiness must remain DATA_NOT_MATURED",
            )
        )
    if report.get("actual_30d_next_check_after", ACTUAL_30D_NEXT_CHECK_AFTER) != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocked_item("report", "actual_30d_next_check_after_mismatch", "next check must remain 2026-07-21T00:00:00Z"))
    if report.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        blockers.append(
            blocked_item(
                "report",
                "direct_llm_interpretation_mismatch",
                "direct_llm_interpretation must be direct_llm_parametric_memory_control",
            )
        )
    if not is_non_empty_string(report.get("source_run_id")):
        blockers.append(blocked_item("report", "source_run_id_invalid", "source_run_id must be a non-empty string"))
    if not is_hash(report.get("source_summary_sha256")):
        blockers.append(blocked_item("report", "source_summary_sha256_invalid", "source_summary_sha256 must be a sha256 hex string"))
    if "source_artifact_sha256" in report and report.get("source_artifact_sha256") is not None and not is_hash(report.get("source_artifact_sha256")):
        blockers.append(blocked_item("report", "source_artifact_sha256_invalid", "source_artifact_sha256 must be a sha256 hex string when present"))
    if parse_timestamp(report.get("capture_timestamp")) is None:
        blockers.append(blocked_item("report", "capture_timestamp_invalid", "capture_timestamp must be ISO-8601"))
    if not is_non_empty_string(report.get("horizon_end_date")):
        blockers.append(blocked_item("report", "horizon_end_date_invalid", "horizon_end_date must be present"))
    if not isinstance(report.get("blocker_reasons"), list):
        blockers.append(blocked_item("report", "blocker_reasons_not_list", "blocker_reasons must be a list"))
    if not is_non_empty_string(report.get("non_claims")) and not isinstance(report.get("non_claims"), (list, dict)):
        blockers.append(blocked_item("report", "non_claims_invalid", "non_claims must be structured or non-empty text"))

    horizon = str(report.get("horizon") or "").strip()
    if horizon.upper() not in ALLOWED_HORIZONS:
        blockers.append(blocked_item("report", "horizon_not_short_horizon", "horizon must be 1D/3D/5D/next_close"))
    if horizon.upper() in {"30D", "THIRTY_DAY", "THIRTY-DAY"} or "30" in horizon:
        blockers.append(blocked_item("report", "horizon_30d_not_allowed", "short-horizon report cannot use 30D actual verdict horizon"))

    for field in ("resolved_count", "scored_count"):
        parsed = int_value(report.get(field))
        if parsed is None or parsed < 0:
            blockers.append(blocked_item("report", f"{field}_invalid", f"{field} must be a non-negative integer"))
    direction = report.get("actual_direction")
    if direction is not None and direction != "" and direction not in VALID_DIRECTIONS:
        blockers.append(blocked_item("report", "actual_direction_invalid", "actual_direction must be long/avoid/neutral"))

    artifact_path = report.get("source_artifact_path")
    if is_non_empty_string(artifact_path) and report.get("source_artifact_sha256"):
        path = resolve_report_relative(str(artifact_path), report_path=report_path)
        if path.exists() and path.is_file():
            actual = sha256_file(path)
            if actual != str(report["source_artifact_sha256"]).lower():
                blockers.append(blocked_item(path, "source_artifact_sha256_mismatch", "source artifact hash does not match file bytes"))
    return blockers


def runtime_blockers(report: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in REQUIRED_FALSE_FLAGS:
        if flag not in report:
            blockers.append(blocked_item("report", f"missing_{flag}", f"{flag} must be explicitly present and false"))
        elif report.get(flag) is not False:
            blockers.append(blocked_item("report", f"{flag}_not_false", f"{flag} must be false"))
    return blockers


def provenance_blockers(report: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        blockers.append(blocked_item("report.provenance", "provenance_missing", "provenance object is required"))
    else:
        if provenance.get("source_run_id") != report.get("source_run_id"):
            blockers.append(blocked_item("report.provenance", "source_run_id_mismatch", "provenance source_run_id must match report"))
        if provenance.get("source_summary_sha256") != report.get("source_summary_sha256"):
            blockers.append(blocked_item("report.provenance", "source_summary_sha256_mismatch", "provenance source_summary_sha256 must match report"))
        if provenance.get("source_artifact_path") != report.get("source_artifact_path"):
            blockers.append(blocked_item("report.provenance", "source_artifact_path_mismatch", "provenance source_artifact_path must match report"))
    path = str(report.get("source_artifact_path") or "")
    if not path.strip():
        blockers.append(blocked_item("report", "source_artifact_path_missing", "source_artifact_path is required"))
    elif claim_scan.forbidden_path(path):
        blockers.append(blocked_item(path, "forbidden_source_artifact_path", "source artifact path violates artifact boundary"))
    blockers.extend(claim_regression.path_blockers(report, path="report"))
    return blockers


def claim_blockers(report: dict[str, Any]) -> list[dict[str, Any]]:
    return claim_regression.claim_blockers(report, path="report")


def data_blockers(report: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    maturity = str(report.get("maturity_status") or "").strip().upper()
    outcome = str(report.get("outcome_status") or "").strip().upper()
    if maturity in NOT_MATURED_STATUSES or outcome in NOT_MATURED_STATUSES:
        return blockers
    if maturity in BLOCKED_DATA_STATUSES or outcome in BLOCKED_DATA_STATUSES:
        blockers.append(blocked_item("report", "outcome_data_blocked", "report declares blocked/missing data"))
        return blockers
    if maturity in READY_MATURITY_STATUSES or outcome in {"RESOLVED", "READY"}:
        for field in ("decision_price", "outcome_price", "actual_change_pct"):
            if number_value(report.get(field)) is None:
                blockers.append(blocked_item("report", f"{field}_missing", f"{field} is required for matured/resolved report"))
        if report.get("actual_direction") not in VALID_DIRECTIONS:
            blockers.append(blocked_item("report", "actual_direction_missing", "actual_direction is required for matured/resolved report"))
    return blockers


def digest_payload(report: dict[str, Any], status: str, blocker_reasons: list[str]) -> dict[str, Any]:
    return {
        "report_schema_version": report.get("report_schema_version"),
        "boundary_fields": {field: report.get(field) for field in BOUNDARY_CRITICAL_FIELDS},
        "maturity_status": report.get("maturity_status"),
        "outcome_status": report.get("outcome_status"),
        "readiness_status": report.get("readiness_status"),
        "blocker_reasons": blocker_reasons,
        "status": status,
    }


def choose_status(
    *,
    schema: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    runtime: list[dict[str, Any]],
    overclaim: list[dict[str, Any]],
    data: list[dict[str, Any]],
    report: dict[str, Any],
) -> str:
    if schema or runtime:
        return STATUS_BLOCKED_SCHEMA
    if provenance:
        return STATUS_BLOCKED_PROVENANCE
    if overclaim:
        return STATUS_BLOCKED_OVERCLAIM
    if data:
        return STATUS_BLOCKED_DATA
    maturity = str(report.get("maturity_status") or "").strip().upper()
    outcome = str(report.get("outcome_status") or "").strip().upper()
    if maturity in NOT_MATURED_STATUSES or outcome in NOT_MATURED_STATUSES:
        return STATUS_NOT_MATURED
    if maturity in READY_MATURITY_STATUSES or outcome in {"RESOLVED", "READY"}:
        return STATUS_READY
    return STATUS_DATA_INSUFFICIENT


def base_summary(config: ReportConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "template_run_id": config.template_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "template_status": status,
        "validation_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_run_id": "",
        "source_summary_sha256": "",
        "source_artifact_path": "",
        "source_artifact_sha256": "",
        "horizon": "",
        "horizon_end_date": "",
        "maturity_status": "",
        "outcome_status": "",
        "readiness_status": "",
        "decision_price": None,
        "outcome_price": None,
        "actual_change_pct": None,
        "actual_direction": "",
        "resolved_count": 0,
        "scored_count": 0,
        "next_check_after": "",
        "blocker_reasons": [],
        "blocked_items": [],
        "schema_blocker_count": 0,
        "provenance_blocker_count": 0,
        "data_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "runtime_blocker_count": 0,
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "runtime_boundary_status": "clean",
        "schema_boundary_status": "clean",
        "data_boundary_status": "clean",
        "report_content_sha256": "",
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "non_claims": {
            "not_provider_run": True,
            "not_actual_30d_verdict": True,
            "not_oos_science_public_proof": True,
            "not_trading_or_investment_advice": True,
        },
    }


def build_summary(config: ReportConfig) -> dict[str, Any]:
    validate_run_id(config.template_run_id)
    run_root = config.output_dir / config.template_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["schema_blocker_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        summary["blocked_items"] = [blocked_item(run_root, "output_run_id_exists", "output run id exists")]
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    report, load_blockers = load_report(config.report)
    schema = load_blockers + (schema_blockers(report, report_path=config.report) if report else [])
    runtime = runtime_blockers(report) if report else []
    provenance = provenance_blockers(report) if report else []
    overclaim = claim_blockers(report) if report else []
    data = data_blockers(report) if report else []
    status = choose_status(schema=schema, provenance=provenance, runtime=runtime, overclaim=overclaim, data=data, report=report)
    blocked_items = schema + provenance + runtime + overclaim + data
    blocker_reasons = [str(item["rule_id"]) for item in blocked_items]

    run_root.mkdir(parents=True, exist_ok=True)
    summary = base_summary(config, run_root=run_root, status=status)
    summary.update(
        {
            "template_status": status,
            "source_run_id": str(report.get("source_run_id") or ""),
            "source_summary_sha256": str(report.get("source_summary_sha256") or ""),
            "source_artifact_path": str(report.get("source_artifact_path") or ""),
            "source_artifact_sha256": str(report.get("source_artifact_sha256") or ""),
            "horizon": str(report.get("horizon") or ""),
            "horizon_end_date": str(report.get("horizon_end_date") or ""),
            "maturity_status": str(report.get("maturity_status") or ""),
            "outcome_status": str(report.get("outcome_status") or ""),
            "readiness_status": str(report.get("readiness_status") or ""),
            "decision_price": report.get("decision_price"),
            "outcome_price": report.get("outcome_price"),
            "actual_change_pct": report.get("actual_change_pct"),
            "actual_direction": str(report.get("actual_direction") or ""),
            "resolved_count": int_value(report.get("resolved_count")) or 0,
            "scored_count": int_value(report.get("scored_count")) or 0,
            "next_check_after": str(report.get("next_check_after") or ""),
            "blocker_reasons": blocker_reasons,
            "blocked_items": blocked_items[:100],
            "schema_blocker_count": len(schema),
            "provenance_blocker_count": len(provenance),
            "data_blocker_count": len(data),
            "overclaim_blocker_count": len(overclaim),
            "runtime_blocker_count": len(runtime),
            "artifact_boundary_status": "blocked" if provenance else "clean",
            "claim_boundary_status": "blocked" if overclaim else "clean",
            "runtime_boundary_status": "blocked" if runtime else "clean",
            "schema_boundary_status": "blocked" if schema else "clean",
            "data_boundary_status": "blocked" if data else "clean",
            "report_content_sha256": stable_sha256_json(digest_payload(report, status, blocker_reasons)),
            "provider_or_backend_called": bool(report.get("provider_or_backend_called")) if report else False,
            "codex_cli_new_call": bool(report.get("codex_cli_new_call")) if report else False,
            "formal_lite_entered": bool(report.get("formal_lite_entered")) if report else False,
            "v3_7_actual_verdict_executable": bool(report.get("v3_7_actual_verdict_executable")) if report else False,
            "v3_7_actual_verdict_executed": bool(report.get("v3_7_actual_verdict_executed")) if report else False,
            "actual_30d_readiness_status": str(report.get("actual_30d_readiness_status") or ACTUAL_30D_READINESS_STATUS),
            "actual_30d_next_check_after": str(report.get("actual_30d_next_check_after") or ACTUAL_30D_NEXT_CHECK_AFTER),
            "direct_llm_interpretation": str(report.get("direct_llm_interpretation") or DIRECT_LLM_INTERPRETATION),
        }
    )
    write_outputs(config, summary, run_root=run_root)
    return summary


def write_outputs(config: ReportConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "template_run_id": config.template_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "report_content_sha256": summary.get("report_content_sha256"),
        "template_status": summary.get("template_status"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-run-id", default=default_run_id())
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7j_short_horizon_report_template/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ReportConfig:
    return ReportConfig(
        template_run_id=str(args.template_run_id),
        report=args.report,
        output_dir=args.output_dir,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed with redacted stderr.
        print(f"short-horizon report template validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("template_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
