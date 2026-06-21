#!/usr/bin/env python3
"""GOTRA v3.6AJ cognitive-lift fixture comparison harness."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ai_ksana_cognitive_lift_audit as lift_audit  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_6aj.cognitive_lift_fixture_comparison_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6aj.cognitive_lift_fixture_comparison_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6aj_cognitive_lift_fixture_comparison_"
SCRIPT_VERSION = "v3.6aj-20260621"
EVIDENCE_LAYER = "engineering/local cognitive-lift fixture comparison only"
DIRECT_LLM_INTERPRETATION = lift_audit.DIRECT_LLM_INTERPRETATION

STATUS_READY = "COGNITIVE_LIFT_FIXTURE_COMPARISON_READY"
STATUS_IMPROVED = "COGNITIVE_LIFT_FIXTURE_IMPROVED"
STATUS_LOW_BASELINE = "LOW_INFORMATION_GAIN_BASELINE"
STATUS_LOW_CANDIDATE = "LOW_INFORMATION_GAIN_CANDIDATE"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"

NON_BLOCKING_STATUSES = {
    STATUS_READY,
    STATUS_IMPROVED,
    STATUS_LOW_BASELINE,
    STATUS_LOW_CANDIDATE,
    STATUS_DATA_INSUFFICIENT,
}
BLOCKED_STATUS_ORDER = (
    lift_audit.STATUS_BLOCKED_SCHEMA,
    lift_audit.STATUS_BLOCKED_PROVENANCE,
    lift_audit.STATUS_BLOCKED_OVERCLAIM,
)
BLOCKED_STATUS_MAP = {
    lift_audit.STATUS_BLOCKED_SCHEMA: STATUS_BLOCKED_SCHEMA,
    lift_audit.STATUS_BLOCKED_PROVENANCE: STATUS_BLOCKED_PROVENANCE,
    lift_audit.STATUS_BLOCKED_OVERCLAIM: STATUS_BLOCKED_OVERCLAIM,
}
LOW_INFORMATION_GAIN = lift_audit.STATUS_LOW_INFORMATION_GAIN
SUFFICIENT = "SUFFICIENT_FOR_FIXTURE_COMPARISON"
STRUCTURAL_IMPROVEMENT_METRICS = (
    "ranked_hypothesis_count",
    "counterfactual_count",
    "falsifiable_trigger_count",
)


@dataclass(frozen=True)
class ComparisonConfig:
    comparison_run_id: str
    output_dir: Path
    baseline_manifest: Path | None = None
    candidate_manifest: Path | None = None
    baseline_artifacts: tuple[Path, ...] = ()
    candidate_artifacts: tuple[Path, ...] = ()
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"comparison_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("comparison_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    return lift_audit.normalize_path(path)


def side_audit_run_id(comparison_run_id: str, side: str) -> str:
    suffix = comparison_run_id.removeprefix(RUN_ID_PREFIX)
    return f"{lift_audit.RUN_ID_PREFIX}v3_6aj_{side}_{suffix}"


def run_side_audit(
    config: ComparisonConfig,
    *,
    run_root: Path,
    side: str,
) -> dict[str, Any]:
    if side == "baseline":
        manifest = config.baseline_manifest
        artifacts = config.baseline_artifacts
    elif side == "candidate":
        manifest = config.candidate_manifest
        artifacts = config.candidate_artifacts
    else:
        raise ValueError(f"unknown comparison side: {side}")
    audit_config = lift_audit.AuditConfig(
        audit_run_id=side_audit_run_id(config.comparison_run_id, side),
        output_dir=run_root / "side_audit_runs",
        input_artifacts=artifacts,
        manifest=manifest,
        allow_overwrite=True,
    )
    with redirect_stdout(io.StringIO()):
        return lift_audit.run_audit(audit_config)


def int_metric(summary: dict[str, Any], key: str) -> int:
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def delta(candidate: dict[str, Any], baseline: dict[str, Any], key: str) -> int:
    return int_metric(candidate, key) - int_metric(baseline, key)


def structural_improvement_deltas(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, int]:
    return {key: delta(candidate, baseline, key) for key in STRUCTURAL_IMPROVEMENT_METRICS}


def has_positive_structural_improvement(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    deltas = structural_improvement_deltas(baseline, candidate)
    return all(value > 0 for value in deltas.values())


def blocked_status(baseline: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    statuses = {str(baseline.get("overall_status") or ""), str(candidate.get("overall_status") or "")}
    for status in BLOCKED_STATUS_ORDER:
        if status in statuses:
            return BLOCKED_STATUS_MAP[status]
    return None


def comparison_status(baseline: dict[str, Any], candidate: dict[str, Any]) -> str:
    blocked = blocked_status(baseline, candidate)
    if blocked:
        return blocked
    if (
        baseline.get("overall_status") == lift_audit.STATUS_DATA_INSUFFICIENT
        or candidate.get("overall_status") == lift_audit.STATUS_DATA_INSUFFICIENT
    ):
        return STATUS_DATA_INSUFFICIENT
    baseline_info = str(baseline.get("information_gain_status") or "")
    candidate_info = str(candidate.get("information_gain_status") or "")
    if candidate_info == LOW_INFORMATION_GAIN:
        return STATUS_LOW_CANDIDATE
    if (
        baseline_info == LOW_INFORMATION_GAIN
        and candidate_info == SUFFICIENT
        and has_positive_structural_improvement(baseline, candidate)
    ):
        return STATUS_IMPROVED
    if baseline_info == LOW_INFORMATION_GAIN:
        return STATUS_READY
    return STATUS_READY


def blocker_count(summary: dict[str, Any], rule_prefix: str) -> int:
    return sum(
        1
        for item in summary.get("blocked_items", [])
        if isinstance(item, dict) and str(item.get("rule_id") or "").startswith(rule_prefix)
    )


def overclaim_blocker_count(*summaries: dict[str, Any]) -> int:
    return sum(
        sum(
            1
            for item in summary.get("blocked_items", [])
            if isinstance(item, dict)
            and str(item.get("rule_id") or "")
            in {
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
        )
        for summary in summaries
    )


def schema_blocker_count(*summaries: dict[str, Any]) -> int:
    return sum(blocker_count(summary, "missing_or_invalid_required_schema_field") for summary in summaries)


def provenance_blocker_count(*summaries: dict[str, Any]) -> int:
    return sum(
        sum(
            1
            for item in summary.get("blocked_items", [])
            if isinstance(item, dict)
            and str(item.get("rule_id") or "")
            in {"missing_provenance", "missing_or_inconsistent_provenance"}
        )
        for summary in summaries
    )


def base_summary(config: ComparisonConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "comparison_run_id": config.comparison_run_id,
        "comparison_run_root": str(run_root),
        "comparison_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "comparison_status": STATUS_DATA_INSUFFICIENT,
        "baseline_information_gain_status": lift_audit.STATUS_DATA_INSUFFICIENT,
        "candidate_information_gain_status": lift_audit.STATUS_DATA_INSUFFICIENT,
        "baseline_hypothesis_count": 0,
        "candidate_hypothesis_count": 0,
        "baseline_counterfactual_count": 0,
        "candidate_counterfactual_count": 0,
        "baseline_falsifiable_trigger_count": 0,
        "candidate_falsifiable_trigger_count": 0,
        "baseline_evidence_gap_count": 0,
        "candidate_evidence_gap_count": 0,
        "baseline_generic_caution_phrase_count": 0,
        "candidate_generic_caution_phrase_count": 0,
        "delta_ranked_hypothesis_count": 0,
        "delta_counterfactual_count": 0,
        "delta_falsifiable_trigger_count": 0,
        "delta_generic_caution_phrase_count": 0,
        "structural_improvement_required_metric_count": len(STRUCTURAL_IMPROVEMENT_METRICS),
        "positive_structural_delta_count": 0,
        "structural_improvement_met": False,
        "provenance_link_count": 0,
        "overclaim_blocker_count": 0,
        "schema_blocker_count": 0,
        "provenance_blocker_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "blocker_reasons": [],
        "non_claims": {
            "not_30d_forward_live_verdict": True,
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_gotra_ksana_alaya_superiority_conclusion": True,
        },
        "baseline_audit_summary_path": "",
        "candidate_audit_summary_path": "",
    }


def build_summary(
    config: ComparisonConfig,
    *,
    run_root: Path,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    status = comparison_status(baseline, candidate)
    improvement_deltas = structural_improvement_deltas(baseline, candidate)
    positive_structural_delta_count = sum(1 for value in improvement_deltas.values() if value > 0)
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "comparison_status": status,
            "baseline_information_gain_status": baseline.get("information_gain_status"),
            "candidate_information_gain_status": candidate.get("information_gain_status"),
            "baseline_hypothesis_count": int_metric(baseline, "hypothesis_count"),
            "candidate_hypothesis_count": int_metric(candidate, "hypothesis_count"),
            "baseline_counterfactual_count": int_metric(baseline, "counterfactual_count"),
            "candidate_counterfactual_count": int_metric(candidate, "counterfactual_count"),
            "baseline_falsifiable_trigger_count": int_metric(
                baseline, "falsifiable_trigger_count"
            ),
            "candidate_falsifiable_trigger_count": int_metric(
                candidate, "falsifiable_trigger_count"
            ),
            "baseline_evidence_gap_count": int_metric(baseline, "evidence_gap_count"),
            "candidate_evidence_gap_count": int_metric(candidate, "evidence_gap_count"),
            "baseline_generic_caution_phrase_count": int_metric(
                baseline, "generic_caution_phrase_count"
            ),
            "candidate_generic_caution_phrase_count": int_metric(
                candidate, "generic_caution_phrase_count"
            ),
            "delta_ranked_hypothesis_count": delta(
                candidate, baseline, "ranked_hypothesis_count"
            ),
            "delta_counterfactual_count": delta(candidate, baseline, "counterfactual_count"),
            "delta_falsifiable_trigger_count": delta(
                candidate, baseline, "falsifiable_trigger_count"
            ),
            "delta_generic_caution_phrase_count": delta(
                candidate, baseline, "generic_caution_phrase_count"
            ),
            "structural_improvement_required_metrics": sorted(STRUCTURAL_IMPROVEMENT_METRICS),
            "positive_structural_delta_count": positive_structural_delta_count,
            "structural_improvement_met": positive_structural_delta_count
            == len(STRUCTURAL_IMPROVEMENT_METRICS),
            "provenance_link_count": int_metric(baseline, "provenance_link_count")
            + int_metric(candidate, "provenance_link_count"),
            "overclaim_blocker_count": overclaim_blocker_count(baseline, candidate),
            "schema_blocker_count": schema_blocker_count(baseline, candidate),
            "provenance_blocker_count": provenance_blocker_count(baseline, candidate),
            "provider_or_backend_called": bool(
                baseline.get("provider_or_backend_called")
                or candidate.get("provider_or_backend_called")
            ),
            "codex_cli_new_call": bool(
                baseline.get("codex_cli_new_call") or candidate.get("codex_cli_new_call")
            ),
            "formal_lite_entered": bool(
                baseline.get("formal_lite_entered") or candidate.get("formal_lite_entered")
            ),
            "v3_7_allowed": bool(baseline.get("v3_7_allowed") or candidate.get("v3_7_allowed")),
            "baseline_audit_summary_path": str(baseline.get("summary_path") or ""),
            "candidate_audit_summary_path": str(candidate.get("summary_path") or ""),
            "blocker_reasons": sorted(
                {
                    str(item)
                    for item in (baseline.get("blocker_reasons") or [])
                    + (candidate.get("blocker_reasons") or [])
                    if item
                }
            ),
        }
    )
    return summary


def write_outputs(config: ComparisonConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary_sha256 = sha256_file(summary_path)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "comparison_run_id": config.comparison_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": summary_sha256,
        "summary_digest_target": "summary.json final payload",
        "baseline_manifest": normalize_path(config.baseline_manifest),
        "candidate_manifest": normalize_path(config.candidate_manifest),
        "baseline_artifacts": [normalize_path(path) for path in config.baseline_artifacts],
        "candidate_artifacts": [normalize_path(path) for path in config.candidate_artifacts],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def blocked_run_id_summary(config: ComparisonConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "comparison_status": STATUS_BLOCKED_SCHEMA,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_comparison(config: ComparisonConfig) -> dict[str, Any]:
    validate_run_id(config.comparison_run_id)
    run_root = config.output_dir / config.comparison_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    baseline = run_side_audit(config, run_root=run_root, side="baseline")
    candidate = run_side_audit(config, run_root=run_root, side="candidate")
    summary = build_summary(config, run_root=run_root, baseline=baseline, candidate=candidate)
    write_outputs(config, summary, run_root=run_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, default=None)
    parser.add_argument("--candidate-manifest", type=Path, default=None)
    parser.add_argument("--baseline-artifact", action="append", type=Path, default=[])
    parser.add_argument("--candidate-artifact", action="append", type=Path, default=[])
    parser.add_argument(
        "--comparison-run-id",
        default=default_run_id(),
        help=f"Run id, must start with {RUN_ID_PREFIX}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6aj_cognitive_lift_fixture_comparison/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_comparison(
        ComparisonConfig(
            comparison_run_id=args.comparison_run_id,
            output_dir=args.output_dir,
            baseline_manifest=args.baseline_manifest,
            candidate_manifest=args.candidate_manifest,
            baseline_artifacts=tuple(args.baseline_artifact),
            candidate_artifacts=tuple(args.candidate_artifact),
            allow_overwrite=bool(args.allow_overwrite),
        )
    )
    return 0 if summary["comparison_status"] in NON_BLOCKING_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
