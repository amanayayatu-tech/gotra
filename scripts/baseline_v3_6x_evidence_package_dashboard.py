#!/usr/bin/env python3
"""GOTRA v3.6X evidence package / decision dashboard builder."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SUMMARY_SCHEMA = "gotra.baseline_v3_6x.evidence_package_dashboard_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6x.evidence_package_dashboard_manifest.v1"
PACKAGE_RUN_ID_PREFIX = "baseline_v3_6x_evidence_package_dashboard_"
SCRIPT_VERSION = "v3.6x-20260621"

STATUS_READY = "EVIDENCE_PACKAGE_READY"
STATUS_BLOCKED_RUN_ID_EXISTS = "EVIDENCE_PACKAGE_BLOCKED_RUN_ID_EXISTS"
STATUS_BLOCKED_SOURCE_DOCS = "EVIDENCE_PACKAGE_BLOCKED_SOURCE_DOCS"

DIRECT_LLM_INTERPRETATION = "direct_llm_parametric_memory_control"
THIRTY_DAY_MATURITY_STATUS = "DATA_NOT_MATURED"
NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"


@dataclass(frozen=True)
class SourceDocConfig:
    doc_id: str
    path: Path
    required_snippets: tuple[str, ...] = ()


@dataclass(frozen=True)
class DashboardConfig:
    package_run_id: str
    output_dir: Path
    source_docs: tuple[SourceDocConfig, ...]
    allow_overwrite: bool = False


DEFAULT_SOURCE_DOCS = (
    SourceDocConfig(
        doc_id="v3_6s_actual_maturity_monitor_result",
        path=Path("docs/GOTRA_V3_6S_ACTUAL_MATURITY_MONITOR_RESULT_20260621.md"),
        required_snippets=(
            "DATA_NOT_MATURED",
            "2026-07-21T00:00:00Z",
            DIRECT_LLM_INTERPRETATION,
            "Provider/backend called: `false`",
            "Codex CLI called: `false`",
            "Formal-lite entered: `false`",
        ),
    ),
    SourceDocConfig(
        doc_id="v3_6t_monitor_ops_result",
        path=Path("docs/GOTRA_V3_6T_FORWARD_LIVE_MONITOR_OPS_RESULT_20260621.md"),
        required_snippets=(
            "DATA_NOT_MATURED",
            "WAIT_UNTIL_NEXT_CHECK",
            "v3.7 verdict allowed: `false`",
            DIRECT_LLM_INTERPRETATION,
        ),
    ),
    SourceDocConfig(
        doc_id="v3_6u_historical_internal_verdict",
        path=Path("docs/GOTRA_V3_6U_HISTORICAL_INTERNAL_LARGE_REGRESSION_VERDICT_20260621.md"),
        required_snippets=(
            "FULL_GOTRA_BETTER",
            "mse_ci_excludes_zero_positive",
            "historical/internal",
            DIRECT_LLM_INTERPRETATION,
        ),
    ),
    SourceDocConfig(
        doc_id="v3_6v_short_horizon_prereg",
        path=Path("docs/GOTRA_V3_6V_SHORT_HORIZON_FORWARD_LIVE_COHORT_PREREG_20260621.md"),
        required_snippets=(
            "SHORT_HORIZON_COHORT_PLAN_READY",
            "equivalent to 30D outcomes",
            "gpt-5.5",
            "high",
            DIRECT_LLM_INTERPRETATION,
        ),
    ),
)


def parse_timestamp(value: str | None = None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def utc_timestamp_slug(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{PACKAGE_RUN_ID_PREFIX}{utc_timestamp_slug(now or datetime.now(UTC))}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(PACKAGE_RUN_ID_PREFIX):
        raise ValueError(f"package_run_id must start with {PACKAGE_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("package_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def source_doc_summary(doc: SourceDocConfig) -> dict[str, Any]:
    path = doc.path
    exists = path.exists()
    text = path.read_text(encoding="utf-8") if exists else ""
    missing_snippets = [snippet for snippet in doc.required_snippets if snippet not in text]
    return {
        "doc_id": doc.doc_id,
        "path": str(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists else "",
        "required_snippet_count": len(doc.required_snippets),
        "missing_required_snippets": missing_snippets,
        "missing_required_snippet_count": len(missing_snippets),
    }


def can_say() -> list[str]:
    return [
        "engineering/local monitor and readiness chain exists",
        "historical/internal offline MSE-specific deterministic_price_only vs full_gotra result exists",
        "30D actual forward-live outcomes are not mature",
        "short-horizon experiment family/preregistration exists as a separate path",
        "open stacked PRs can be clean without being merged",
    ]


def cannot_say() -> list[str]:
    return [
        "OOS pass",
        "science/public proof",
        "trading or investment recommendation",
        "30D forward-live verdict",
        "ksana/full_gotra H2 winner",
        "provider/formal-lite acceptance",
        "direct_llm as a clean no-future baseline",
    ]


def base_summary(config: DashboardConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "package_run_id": config.package_run_id,
        "run_root": str(run_root),
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "script_version": SCRIPT_VERSION,
        "status": STATUS_BLOCKED_SOURCE_DOCS,
        "evidence_layer": "engineering/local packaging plus historical/internal summary only",
        "source_document_count": len(config.source_docs),
        "source_document_missing_count": 0,
        "source_document_required_snippet_missing_count": 0,
        "source_documents": [],
        "thirty_day_forward_live_maturity_status": THIRTY_DAY_MATURITY_STATUS,
        "next_check_after": NEXT_CHECK_AFTER,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "historical_internal_verdict": {
            "primary_comparison": "deterministic_price_only_baseline_vs_full_gotra",
            "status": "FULL_GOTRA_BETTER",
            "criterion": "mse_loss_diff_det_minus_full",
            "reason": "mse_ci_excludes_zero_positive",
            "scope": "historical_internal_mse_specific_only",
            "not_forward_live": True,
            "not_oos": True,
            "not_science_public_or_trading": True,
        },
        "short_horizon_status": {
            "family": "v3.6v_short_horizon_forward_live",
            "status": "SHORT_HORIZON_COHORT_PLAN_READY",
            "separate_from_30d": True,
            "not_equivalent_to_30d": True,
            "real_capture_performed_by_this_package": False,
            "earliest_short_horizon_maturity_availability": "2026-06-23T00:00:00Z",
        },
        "open_pr_stack": [
            {
                "number": 36,
                "title": "Add actual forward-live maturity monitor",
                "head": "365a52a87cb0e1dbed39a3323ffb8bf4de2fd511",
                "status": "open_clean_ci_success_p2_resolved_or_outdated",
            },
            {
                "number": 37,
                "title": "Add forward-live maturity monitor operations ledger",
                "head": "56fe015b8a033878f9ad5378fe83a04e221448af",
                "status": "open_clean_ci_success_p2_resolved_or_outdated",
            },
            {
                "number": 38,
                "title": "Add parallel fast-feedback routes",
                "head": "dd3760a3ef5f326178cb19dc43c48d1d8c886da0",
                "status": "open_clean_ci_success_p2_resolved_or_outdated",
            },
        ],
        "active_blockers": ["none_currently_detected"],
        "next_permitted_actions": [
            "continue_monitor",
            "short_horizon_capture_or_maturity_recheck_only_if_separately_authorized",
            "do_not_execute_v3_7_until_real_ready",
        ],
        "can_say": can_say(),
        "cannot_say": cannot_say(),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
            "not_provider_formal_lite_acceptance": True,
        },
    }


def blocked_run_id_summary(config: DashboardConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "active_blockers": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_dashboard(config: DashboardConfig) -> dict[str, Any]:
    validate_run_id(config.package_run_id)
    run_root = config.output_dir / config.package_run_id
    if run_root.exists() and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)

    source_documents = [source_doc_summary(doc) for doc in config.source_docs]
    missing_count = sum(1 for doc in source_documents if not doc["exists"])
    missing_snippet_count = sum(
        int(doc["missing_required_snippet_count"]) for doc in source_documents
    )

    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "status": STATUS_READY
            if missing_count == 0 and missing_snippet_count == 0
            else STATUS_BLOCKED_SOURCE_DOCS,
            "source_document_missing_count": missing_count,
            "source_document_required_snippet_missing_count": missing_snippet_count,
            "source_documents": source_documents,
            "active_blockers": ["none_currently_detected"]
            if missing_count == 0 and missing_snippet_count == 0
            else ["source_document_missing_or_missing_required_boundary"],
        }
    )

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "package_run_id": config.package_run_id,
        "script_version": SCRIPT_VERSION,
        "created_at_utc": summary["generated_at_utc"],
        "summary_path": str(run_root / "summary.json"),
        "source_document_paths": [str(doc.path) for doc in config.source_docs],
    }
    atomic_write_json(run_root / "summary.json", summary)
    atomic_write_json(run_root / "manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_source_doc_arg(value: str) -> SourceDocConfig:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--source-doc must be doc_id=path")
    doc_id, path = value.split("=", 1)
    doc_id = doc_id.strip()
    if not doc_id:
        raise argparse.ArgumentTypeError("source doc_id must not be empty")
    return SourceDocConfig(doc_id=doc_id, path=Path(path))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-run-id", default=default_run_id())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6x_evidence_package_dashboard/runs"),
    )
    parser.add_argument(
        "--source-doc",
        action="append",
        type=parse_source_doc_arg,
        help="Optional source doc override in doc_id=path form. May be repeated.",
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_docs = tuple(args.source_doc) if args.source_doc else DEFAULT_SOURCE_DOCS
    config = DashboardConfig(
        package_run_id=args.package_run_id,
        output_dir=args.output_dir,
        source_docs=source_docs,
        allow_overwrite=args.allow_overwrite,
    )
    try:
        summary = run_dashboard(config)
    except Exception as exc:
        print(f"evidence package dashboard failed: {exc}", file=sys.stderr)
        return 2
    if summary["status"] == STATUS_READY:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
