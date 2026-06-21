#!/usr/bin/env python3
"""GOTRA v3.6AK live stack merge-readiness snapshot."""

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

from scripts import baseline_v3_6ah_live_stack_refresh as live_refresh  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_6ak.live_stack_merge_readiness_snapshot.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ak.live_stack_merge_readiness_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ak_live_stack_merge_readiness_snapshot_"
SCRIPT_VERSION = "v3.6ak-20260621"
EVIDENCE_LAYER = "engineering/local stack audit only"

STATUS_READY = "STACK_READY_FOR_USER_MERGE_REVIEW"
STATUS_MERGED_TO_MAIN = "STACK_MERGED_TO_MAIN"
STATUS_BLOCKED_CI = "STACK_BLOCKED_CI"
STATUS_BLOCKED_REVIEW = "STACK_BLOCKED_REVIEW"
STATUS_BLOCKED_TOPOLOGY = "STACK_BLOCKED_TOPOLOGY"
STATUS_BLOCKED_CONFLICT = "STACK_BLOCKED_CONFLICT"
STATUS_BLOCKED_ARTIFACT = "STACK_BLOCKED_ARTIFACT"
STATUS_BLOCKED_CLAIM_BOUNDARY = "STACK_BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_MATURITY_GATE = "STACK_BLOCKED_MATURITY_GATE"
STATUS_BLOCKED_DIRECT_LLM = "STACK_BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_CI_PREFLIGHT = "STACK_BLOCKED_CI_PREFLIGHT"
STATUS_BLOCKED_PROVIDER_BOUNDARY = "STACK_BLOCKED_PROVIDER_BOUNDARY"
STATUS_INCOMPLETE = "STACK_SNAPSHOT_INCOMPLETE"
STATUS_BLOCKED_RUN_ID_EXISTS = "STACK_SNAPSHOT_BLOCKED_RUN_ID_EXISTS"

NEXT_30D_CHECK_AFTER = live_refresh.NEXT_30D_CHECK_AFTER
NEXT_SHORT_HORIZON_CHECK_AFTER = live_refresh.NEXT_SHORT_HORIZON_CHECK_AFTER
DIRECT_LLM_INTERPRETATION = live_refresh.DIRECT_LLM_INTERPRETATION
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"

UNDERLYING_STATUS_MAP = {
    live_refresh.STATUS_READY: STATUS_READY,
    live_refresh.STATUS_BLOCKED_CI: STATUS_BLOCKED_CI,
    live_refresh.STATUS_BLOCKED_REVIEW: STATUS_BLOCKED_REVIEW,
    live_refresh.STATUS_BLOCKED_TOPOLOGY: STATUS_BLOCKED_TOPOLOGY,
    live_refresh.STATUS_BLOCKED_CONFLICT: STATUS_BLOCKED_CONFLICT,
    live_refresh.STATUS_BLOCKED_ARTIFACT: STATUS_BLOCKED_ARTIFACT,
    live_refresh.STATUS_BLOCKED_CLAIM_BOUNDARY: STATUS_BLOCKED_CLAIM_BOUNDARY,
    live_refresh.STATUS_BLOCKED_MATURITY_GATE: STATUS_BLOCKED_MATURITY_GATE,
    live_refresh.STATUS_BLOCKED_DIRECT_LLM: STATUS_BLOCKED_DIRECT_LLM,
    live_refresh.STATUS_BLOCKED_CI_PREFLIGHT: STATUS_BLOCKED_CI_PREFLIGHT,
    live_refresh.STATUS_INCOMPLETE: STATUS_INCOMPLETE,
}


@dataclass(frozen=True)
class SnapshotConfig:
    snapshot_run_id: str
    output_dir: Path
    snapshot: Path | None = None
    use_gh: bool = False
    repo: str = "amanayayatu-tech/gotra"
    pr_range: str = "36-51"
    expected_root_base: str = "main"
    repo_root: Path | None = None
    next_30d_check_after: str = NEXT_30D_CHECK_AFTER
    next_short_horizon_check_after: str = NEXT_SHORT_HORIZON_CHECK_AFTER
    actual_30d_readiness_status: str = ACTUAL_30D_READINESS_STATUS
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"snapshot_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("snapshot_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def underlying_run_id(snapshot_run_id: str) -> str:
    suffix = snapshot_run_id.removeprefix(RUN_ID_PREFIX)
    return f"{live_refresh.RUN_ID_PREFIX}v3_6ak_{suffix}"


def run_underlying_refresh(config: SnapshotConfig, *, run_root: Path) -> dict[str, Any]:
    refresh_config = live_refresh.RefreshConfig(
        refresh_run_id=underlying_run_id(config.snapshot_run_id),
        output_dir=run_root / "underlying_v3_6ah_runs",
        snapshot=config.snapshot,
        use_gh=config.use_gh,
        repo=config.repo,
        pr_range=config.pr_range,
        expected_root_base=config.expected_root_base,
        repo_root=config.repo_root,
        next_30d_check_after=config.next_30d_check_after,
        next_short_horizon_check_after=config.next_short_horizon_check_after,
        allow_overwrite=config.allow_overwrite,
    )
    with redirect_stdout(io.StringIO()):
        return live_refresh.run_refresh(refresh_config)


def provider_boundary_status(underlying: dict[str, Any]) -> str:
    if (
        underlying.get("provider_or_backend_called") is False
        and underlying.get("codex_cli_new_call") is False
        and underlying.get("formal_lite_entered") is False
    ):
        return "clean"
    return "blocked"


def merge_commit_oid(pr: dict[str, Any]) -> str:
    raw = pr.get("mergeCommit", pr.get("merge_commit", ""))
    if isinstance(raw, dict):
        return str(raw.get("oid") or raw.get("sha") or "")
    return str(raw or "")


def merged_at(pr: dict[str, Any]) -> str:
    return str(pr.get("mergedAt") or pr.get("merged_at") or "")


def source_pr_records(underlying: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        source_snapshot = live_refresh.load_source_snapshot(underlying)
        return live_refresh.pr_records(source_snapshot)
    except (TypeError, ValueError, OSError, json.JSONDecodeError):
        return []


def merged_pr_records(underlying: dict[str, Any]) -> list[dict[str, Any]]:
    prs = source_pr_records(underlying)
    expected = [int(number) for number in underlying.get("pr_numbers", [])]
    if not prs or not expected:
        return []
    by_number = {int(pr.get("number") or 0): pr for pr in prs}
    merged: list[dict[str, Any]] = []
    for number in expected:
        pr = by_number.get(number)
        if not pr:
            return []
        if str(pr.get("state") or "").upper() != "MERGED":
            return []
        if not merge_commit_oid(pr):
            return []
        merged.append(pr)
    return merged


def merged_stack_evidence(underlying: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "number": int(pr.get("number") or 0),
            "title": str(pr.get("title") or ""),
            "base": str(pr.get("baseRefName") or pr.get("base") or ""),
            "head": str(pr.get("headRefName") or pr.get("head") or ""),
            "head_sha": str(pr.get("headRefOid") or pr.get("head_sha") or ""),
            "state": str(pr.get("state") or ""),
            "merged_at": merged_at(pr),
            "merge_commit": merge_commit_oid(pr),
        }
        for pr in merged_pr_records(underlying)
    ]


def stack_status_from_underlying(underlying: dict[str, Any]) -> str:
    if provider_boundary_status(underlying) != "clean":
        return STATUS_BLOCKED_PROVIDER_BOUNDARY
    if merged_pr_records(underlying):
        return STATUS_MERGED_TO_MAIN
    return UNDERLYING_STATUS_MAP.get(
        str(underlying.get("live_stack_refresh_status") or ""),
        STATUS_INCOMPLETE,
    )


def base_summary(config: SnapshotConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "snapshot_run_id": config.snapshot_run_id,
        "snapshot_run_root": str(run_root),
        "snapshot_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "source_mode": "",
        "repo": config.repo,
        "pr_range": config.pr_range,
        "pr_numbers": [],
        "expected_stack_order": [],
        "base_chain": [],
        "head_shas": {},
        "top_pr_number": 0,
        "top_head_sha": "",
        "ci_all_success": False,
        "merge_state_all_clean": False,
        "merge_state_status_summary": {},
        "unresolved_review_thread_count": 0,
        "active_p1_p2_count": 0,
        "stack_topology_status": "unknown",
        "artifact_boundary_status": "unknown",
        "claim_boundary_status": "unknown",
        "maturity_gate_status": "unknown",
        "direct_llm_boundary_status": "unknown",
        "provider_boundary_status": "unknown",
        "ci_boundary_preflight_status": "unknown",
        "ci_adoption_status": "unknown",
        "underlying_live_stack_refresh_status": "unknown",
        "stack_merge_readiness_status": STATUS_INCOMPLETE,
        "stack_closeout_status": "unknown",
        "merged_pr_count": 0,
        "merge_commit_count": 0,
        "merged_prs": [],
        "main_after_merge_commit": "",
        "stack_already_merged_to_main": False,
        "ready_for_user_merge_review": False,
        "auto_merge_executed": False,
        "auto_merge_executed_by_worker": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "actual_30d_readiness_status": config.actual_30d_readiness_status,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "next_30d_check_after": config.next_30d_check_after,
        "next_short_horizon_check_after": config.next_short_horizon_check_after,
        "evidence_layer": EVIDENCE_LAYER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "underlying_summary_path": "",
        "underlying_summary_sha256": "",
        "summary_digest_target": "manifest.summary_sha256",
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
            "not_auto_merge": True,
            "not_merge_authorization": True,
        },
        "blocker_reasons": [],
        "warnings": [],
    }


def build_summary(
    config: SnapshotConfig,
    *,
    run_root: Path,
    underlying: dict[str, Any],
) -> dict[str, Any]:
    status = stack_status_from_underlying(underlying)
    merged_evidence = merged_stack_evidence(underlying)
    top_pr_number = int(underlying.get("top_pr_number") or 0)
    main_after_merge_commit = ""
    if merged_evidence:
        main_after_merge_commit = str(merged_evidence[-1].get("merge_commit") or "")
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "source_mode": underlying.get("source_mode", ""),
            "pr_numbers": underlying.get("pr_numbers", []),
            "expected_stack_order": underlying.get("expected_stack_order", []),
            "base_chain": underlying.get("base_chain", []),
            "head_shas": underlying.get("head_shas", {}),
            "top_pr_number": top_pr_number,
            "top_head_sha": underlying.get("top_head_sha", ""),
            "ci_all_success": bool(underlying.get("ci_all_success", False)),
            "merge_state_all_clean": bool(underlying.get("merge_state_all_clean", False)),
            "merge_state_status_summary": underlying.get("merge_state_status_summary", {}),
            "unresolved_review_thread_count": int(
                underlying.get("unresolved_review_thread_count", 0)
            ),
            "active_p1_p2_count": int(underlying.get("active_p1_p2_count", 0)),
            "stack_topology_status": underlying.get("stack_topology_status", "unknown"),
            "artifact_boundary_status": underlying.get("artifact_boundary_status", "unknown"),
            "claim_boundary_status": underlying.get("claim_boundary_status", "unknown"),
            "maturity_gate_status": underlying.get("maturity_gate_status", "unknown"),
            "direct_llm_boundary_status": underlying.get("direct_llm_boundary_status", "unknown"),
            "provider_boundary_status": provider_boundary_status(underlying),
            "ci_boundary_preflight_status": underlying.get("ci_boundary_preflight_status", "unknown"),
            "ci_adoption_status": underlying.get("ci_adoption_status", "unknown"),
            "underlying_live_stack_refresh_status": underlying.get("live_stack_refresh_status", ""),
            "stack_merge_readiness_status": status,
            "stack_closeout_status": "merged_to_main" if status == STATUS_MERGED_TO_MAIN else "not_merged",
            "merged_pr_count": len(merged_evidence),
            "merge_commit_count": sum(1 for pr in merged_evidence if pr.get("merge_commit")),
            "merged_prs": merged_evidence,
            "main_after_merge_commit": main_after_merge_commit,
            "stack_already_merged_to_main": status == STATUS_MERGED_TO_MAIN,
            "ready_for_user_merge_review": status == STATUS_READY,
            "provider_or_backend_called": bool(underlying.get("provider_or_backend_called", False)),
            "codex_cli_new_call": bool(underlying.get("codex_cli_new_call", False)),
            "formal_lite_entered": bool(underlying.get("formal_lite_entered", False)),
            "underlying_summary_path": underlying.get("summary_path", "")
            or str(Path(str(underlying.get("refresh_run_root", ""))) / "summary.json"),
            "blocker_reasons": []
            if status == STATUS_MERGED_TO_MAIN
            else list(underlying.get("blocker_reasons", [])),
            "warnings": list(underlying.get("warnings", [])),
        }
    )
    underlying_path = Path(str(summary["underlying_summary_path"]))
    if underlying_path.exists():
        summary["underlying_summary_sha256"] = sha256_file(underlying_path)
    if status == STATUS_MERGED_TO_MAIN:
        summary["stack_topology_status"] = "merged_to_main"
        summary["maturity_gate_status"] = config.actual_30d_readiness_status
        summary["ci_boundary_preflight_status"] = "post_merge_not_applicable"
        summary["ci_adoption_status"] = "post_merge_not_applicable"
    return summary


def blocked_run_id_summary(config: SnapshotConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "stack_merge_readiness_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_snapshot(config: SnapshotConfig) -> dict[str, Any]:
    validate_run_id(config.snapshot_run_id)
    run_root = config.output_dir / config.snapshot_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    underlying = run_underlying_refresh(config, run_root=run_root)
    summary = build_summary(config, run_root=run_root, underlying=underlying)
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def review_bundle_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# GOTRA v3.6AK Live Stack Merge-Readiness Snapshot",
        "",
        f"- Status: `{summary['stack_merge_readiness_status']}`",
        f"- Closeout status: `{summary['stack_closeout_status']}`",
        (
            "- Ready for user merge review: "
            f"`{str(summary['ready_for_user_merge_review']).lower()}`"
        ),
        "- Auto merge executed by worker: `false`",
        f"- v3.7 allowed: `{str(summary['v3_7_allowed']).lower()}`",
        f"- Actual 30D readiness: `{summary['actual_30d_readiness_status']}`",
        f"- Evidence layer: `{summary['evidence_layer']}`",
        f"- Source mode: `{summary['source_mode']}`",
        f"- PR range: `{summary['pr_range']}`",
        f"- PR numbers: `{', '.join(str(number) for number in summary['pr_numbers'])}`",
        f"- Top PR: `#{summary['top_pr_number']} @ {summary['top_head_sha']}`",
        f"- CI all success: `{str(summary['ci_all_success']).lower()}`",
        f"- Merge state all clean: `{str(summary['merge_state_all_clean']).lower()}`",
        f"- Active P1/P2 count: `{summary['active_p1_p2_count']}`",
        f"- Unresolved review thread count: `{summary['unresolved_review_thread_count']}`",
        f"- Artifact boundary: `{summary['artifact_boundary_status']}`",
        f"- Claim boundary: `{summary['claim_boundary_status']}`",
        f"- Maturity gate: `{summary['maturity_gate_status']}`",
        f"- Direct LLM boundary: `{summary['direct_llm_boundary_status']}`",
        f"- Provider boundary: `{summary['provider_boundary_status']}`",
        f"- CI boundary preflight: `{summary['ci_boundary_preflight_status']}`",
        f"- CI adoption: `{summary['ci_adoption_status']}`",
        f"- Merged PR count: `{summary['merged_pr_count']}`",
        f"- Merge commit count: `{summary['merge_commit_count']}`",
        f"- Main after merge commit: `{summary['main_after_merge_commit']}`",
        f"- Next 30D check after: `{summary['next_30d_check_after']}`",
        "",
        "## Expected Stack Order",
        "",
    ]
    lines.extend(f"- {entry}" for entry in summary.get("expected_stack_order", []))
    if summary.get("merged_prs"):
        lines.extend(["", "## Merged PR Evidence", ""])
        lines.extend(
            (
                f"- #{pr['number']} `{pr['head']}` @ `{pr['head_sha']}` -> "
                f"`{pr['merge_commit']}`"
            )
            for pr in summary["merged_prs"]
        )
    if summary.get("blocker_reasons"):
        lines.extend(["", "## Blocking Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in summary["blocker_reasons"])
    lines.extend(
        [
            "",
            "This snapshot is engineering/local stack audit evidence only. It is not",
            "merge authorization, not a worker-executed auto-merge, not a 30D",
            "verdict, and not an OOS/science/public/trading claim.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(*, run_root: Path, summary: dict[str, Any]) -> None:
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    bundle_path = run_root / "review_bundle.md"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["review_bundle_path"] = str(bundle_path)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_sha256 = sha256_file(summary_path)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "snapshot_run_id": summary["snapshot_run_id"],
        "summary_path": str(summary_path),
        "summary_sha256": summary_sha256,
        "summary_digest_target": "summary.json final payload",
        "review_bundle_path": str(bundle_path),
        "stack_merge_readiness_status": summary["stack_merge_readiness_status"],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "auto_merge_executed": False,
        "auto_merge_executed_by_worker": False,
        "v3_7_allowed": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    bundle_path.write_text(review_bundle_markdown(summary), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-run-id", default=default_run_id())
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--use-gh", action="store_true")
    parser.add_argument("--repo", default="amanayayatu-tech/gotra")
    parser.add_argument("--pr-range", default="36-51")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ak_live_stack_merge_readiness_snapshot/runs"),
    )
    parser.add_argument("--expected-root-base", default="main")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--next-30d-check-after", default=NEXT_30D_CHECK_AFTER)
    parser.add_argument("--next-short-horizon-check-after", default=NEXT_SHORT_HORIZON_CHECK_AFTER)
    parser.add_argument("--actual-30d-readiness-status", default=ACTUAL_30D_READINESS_STATUS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> SnapshotConfig:
    return SnapshotConfig(
        snapshot_run_id=str(args.snapshot_run_id),
        output_dir=args.output_dir,
        snapshot=args.snapshot,
        use_gh=bool(args.use_gh),
        repo=str(args.repo),
        pr_range=str(args.pr_range),
        expected_root_base=str(args.expected_root_base),
        repo_root=args.repo_root,
        next_30d_check_after=str(args.next_30d_check_after),
        next_short_horizon_check_after=str(args.next_short_horizon_check_after),
        actual_30d_readiness_status=str(args.actual_30d_readiness_status),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_snapshot(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed.
        print(f"live stack merge-readiness snapshot failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("stack_merge_readiness_status") in {STATUS_READY, STATUS_MERGED_TO_MAIN} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
