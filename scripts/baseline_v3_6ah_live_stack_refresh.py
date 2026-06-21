#!/usr/bin/env python3
"""GOTRA v3.6AH live stack readiness refresh."""

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

from scripts import baseline_v3_6aa_stack_evidence_boundary_audit as stack_audit  # noqa: E402
from scripts import baseline_v3_6ad_live_stack_readiness_snapshot as live_snapshot  # noqa: E402
from scripts import baseline_v3_6af_ci_stack_boundary_preflight as ci_preflight  # noqa: E402
from scripts import baseline_v3_6ag_ci_changed_files_preflight as ci_adoption  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_6ah.live_stack_refresh_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ah.live_stack_refresh_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ah_live_stack_refresh_"
SCRIPT_VERSION = "v3.6ah-20260621"

STATUS_READY = "LIVE_STACK_REFRESH_READY"
STATUS_BLOCKED_CI = "BLOCKED_CI"
STATUS_BLOCKED_REVIEW = "BLOCKED_REVIEW"
STATUS_BLOCKED_TOPOLOGY = "BLOCKED_TOPOLOGY"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_MATURITY_GATE = "BLOCKED_MATURITY_GATE"
STATUS_BLOCKED_DIRECT_LLM = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_BLOCKED_CI_PREFLIGHT = "BLOCKED_CI_PREFLIGHT"
STATUS_INCOMPLETE = "SNAPSHOT_INCOMPLETE"
STATUS_BLOCKED_RUN_ID_EXISTS = "LIVE_STACK_REFRESH_BLOCKED_RUN_ID_EXISTS"

EVIDENCE_LAYER = "engineering_live_stack_refresh"
NEXT_30D_CHECK_AFTER = live_snapshot.NEXT_30D_CHECK_AFTER
NEXT_SHORT_HORIZON_CHECK_AFTER = live_snapshot.NEXT_SHORT_HORIZON_CHECK_AFTER
DIRECT_LLM_INTERPRETATION = live_snapshot.DIRECT_LLM_INTERPRETATION

CI_PREFLIGHT_CLEAN_STATUSES = {ci_preflight.STATUS_CLEAN}
CI_ADOPTION_CLEAN_STATUSES = {ci_adoption.STATUS_WIRED}


@dataclass(frozen=True)
class RefreshConfig:
    refresh_run_id: str
    output_dir: Path
    snapshot: Path | None = None
    use_gh: bool = False
    repo: str = "amanayayatu-tech/gotra"
    pr_range: str = "36-48"
    expected_root_base: str = "main"
    repo_root: Path | None = None
    stack_heads: tuple[str, ...] = ()
    next_30d_check_after: str = NEXT_30D_CHECK_AFTER
    next_short_horizon_check_after: str = NEXT_SHORT_HORIZON_CHECK_AFTER
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"refresh_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("refresh_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_run_id(refresh_run_id: str) -> str:
    suffix = refresh_run_id.removeprefix(RUN_ID_PREFIX)
    return f"{live_snapshot.RUN_ID_PREFIX}v3_6ah_{suffix}"


def build_underlying_snapshot(config: RefreshConfig, *, run_root: Path) -> dict[str, Any]:
    snapshot_config = live_snapshot.SnapshotConfig(
        snapshot_run_id=snapshot_run_id(config.refresh_run_id),
        output_dir=run_root / "live_snapshot_runs",
        snapshot=config.snapshot,
        use_gh=config.use_gh,
        repo=config.repo,
        pr_range=config.pr_range,
        expected_root_base=config.expected_root_base,
        repo_root=config.repo_root,
        stack_heads=config.stack_heads,
        next_30d_check_after=config.next_30d_check_after,
        next_short_horizon_check_after=config.next_short_horizon_check_after,
        allow_overwrite=config.allow_overwrite,
    )
    with redirect_stdout(io.StringIO()):
        return live_snapshot.build_snapshot(snapshot_config)


def load_source_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(summary.get("source_snapshot_path") or ""))
    if path.exists():
        return stack_audit.load_snapshot(path)
    return {}


def pr_records(source_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return live_snapshot.normalize_prs_for_snapshot(stack_audit.pr_list(source_snapshot))
    except (TypeError, ValueError):
        return []


def pr_by_number(prs: list[dict[str, Any]], number: int) -> dict[str, Any] | None:
    for pr in prs:
        if stack_audit.pr_number(pr) == number:
            return pr
    return None


def explicit_status(source_snapshot: dict[str, Any], prs: list[dict[str, Any]], key: str) -> str:
    raw = source_snapshot.get(key)
    if raw:
        return str(raw)
    for pr in prs:
        raw = pr.get(key)
        if raw:
            return str(raw)
    return ""


def inferred_ci_preflight_status(source_snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> str:
    explicit = explicit_status(source_snapshot, prs, "ci_boundary_preflight_status")
    if explicit:
        return explicit
    pr = pr_by_number(prs, 47)
    if pr and pr_component_available(pr):
        return ci_preflight.STATUS_CLEAN
    return STATUS_INCOMPLETE


def inferred_ci_adoption_status(source_snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> str:
    explicit = explicit_status(source_snapshot, prs, "ci_adoption_status")
    if explicit:
        return explicit
    pr = pr_by_number(prs, 48)
    if pr and pr_component_available(pr):
        return ci_adoption.STATUS_WIRED
    return STATUS_INCOMPLETE


def pr_component_available(pr: dict[str, Any]) -> bool:
    if bool(pr.get("isDraft", pr.get("is_draft", False))):
        return False
    if str(pr.get("state") or "").upper() != "OPEN":
        return False
    if str(pr.get("mergeStateStatus") or "").upper() != "CLEAN":
        return False
    _, ci_failures = stack_audit.check_ci([pr])
    return not ci_failures


def ci_preflight_failures(ci_boundary_status: str, ci_adoption_status: str) -> list[str]:
    failures: list[str] = []
    if ci_boundary_status not in CI_PREFLIGHT_CLEAN_STATUSES:
        failures.append(f"ci_preflight:status={ci_boundary_status or 'missing'}")
    if ci_adoption_status not in CI_ADOPTION_CLEAN_STATUSES:
        failures.append(f"ci_adoption:status={ci_adoption_status or 'missing'}")
    return failures


def status_from_snapshot(
    *,
    snapshot_status: str,
    snapshot_reasons: list[str],
    ci_preflight_reasons: list[str],
) -> str:
    if snapshot_status == live_snapshot.STATUS_READY:
        if ci_preflight_reasons:
            return STATUS_BLOCKED_CI_PREFLIGHT
        return STATUS_READY
    if snapshot_status == live_snapshot.STATUS_BLOCKED_CI:
        return STATUS_BLOCKED_CI
    if snapshot_status == live_snapshot.STATUS_BLOCKED_REVIEW:
        return STATUS_BLOCKED_REVIEW
    if snapshot_status == live_snapshot.STATUS_BLOCKED_TOPOLOGY:
        return STATUS_BLOCKED_TOPOLOGY
    if snapshot_status == live_snapshot.STATUS_BLOCKED_ARTIFACT:
        return STATUS_BLOCKED_ARTIFACT
    if snapshot_status == live_snapshot.STATUS_BLOCKED_CONFLICT:
        return STATUS_BLOCKED_TOPOLOGY
    if snapshot_status == live_snapshot.STATUS_INCOMPLETE:
        return STATUS_INCOMPLETE
    if any(is_maturity_reason(reason) for reason in snapshot_reasons):
        return STATUS_BLOCKED_MATURITY_GATE
    if any("direct_llm" in reason for reason in snapshot_reasons):
        return STATUS_BLOCKED_DIRECT_LLM
    if snapshot_status == live_snapshot.STATUS_BLOCKED_CLAIM_BOUNDARY:
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    return STATUS_INCOMPLETE


def is_maturity_reason(reason: str) -> bool:
    lowered = reason.lower()
    return any(
        token in lowered
        for token in ("v3_7", "v3.7", "30d", "thirty_day", "thirty-day", "maturity", "short_horizon")
    )


def split_boundary_status(summary: dict[str, Any], blocker_reasons: list[str]) -> tuple[str, str, str]:
    claim_status = str(summary.get("claim_boundary_status") or "clean")
    maturity_status = "blocked" if any(is_maturity_reason(reason) for reason in blocker_reasons) else "clean"
    direct_status = "blocked" if any("direct_llm" in reason for reason in blocker_reasons) else "clean"
    if maturity_status == "blocked" or direct_status == "blocked":
        claim_only = [
            reason
            for reason in blocker_reasons
            if reason.startswith("claim_boundary:")
            and not is_maturity_reason(reason)
            and "direct_llm" not in reason
        ]
        claim_status = "blocked" if claim_only else "clean"
    return claim_status, maturity_status, direct_status


def base_summary(config: RefreshConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "refresh_run_id": config.refresh_run_id,
        "refresh_run_root": str(run_root),
        "refresh_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "source_mode": "",
        "repo": config.repo,
        "source_snapshot_path": "",
        "source_snapshot_sha256": "",
        "live_snapshot_summary_path": "",
        "live_snapshot_summary_sha256": "",
        "review_bundle_path": str(run_root / "review_bundle.md"),
        "packet_path": str(run_root / "packet.md"),
        "pr_numbers": [],
        "top_pr_number": 0,
        "top_head_sha": "",
        "ci_all_success": False,
        "merge_state_all_clean": False,
        "unresolved_review_thread_count": 0,
        "active_p1_p2_count": 0,
        "stack_topology_status": "unknown",
        "artifact_boundary_status": "unknown",
        "claim_boundary_status": "unknown",
        "maturity_gate_status": "unknown",
        "direct_llm_boundary_status": "unknown",
        "ci_boundary_preflight_status": "unknown",
        "ci_adoption_status": "unknown",
        "live_stack_refresh_status": STATUS_INCOMPLETE,
        "ready_for_human_merge_review": False,
        "auto_merge_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "next_30d_check_after": config.next_30d_check_after,
        "next_short_horizon_check_after": config.next_short_horizon_check_after,
        "evidence_layer": EVIDENCE_LAYER,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
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


def blocked_run_id_summary(config: RefreshConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "live_stack_refresh_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_refresh(config: RefreshConfig) -> dict[str, Any]:
    validate_run_id(config.refresh_run_id)
    run_root = config.output_dir / config.refresh_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    snapshot_summary = build_underlying_snapshot(config, run_root=run_root)
    source_snapshot = load_source_snapshot(snapshot_summary)
    prs = pr_records(source_snapshot)
    ci_boundary_status = inferred_ci_preflight_status(source_snapshot, prs)
    ci_adoption_status = inferred_ci_adoption_status(source_snapshot, prs)
    ci_boundary_failures = ci_preflight_failures(ci_boundary_status, ci_adoption_status)
    blocker_reasons = list(snapshot_summary.get("blocking_reasons", [])) + ci_boundary_failures
    claim_status, maturity_status, direct_status = split_boundary_status(snapshot_summary, blocker_reasons)
    status = status_from_snapshot(
        snapshot_status=str(snapshot_summary.get("live_stack_snapshot_status") or ""),
        snapshot_reasons=blocker_reasons,
        ci_preflight_reasons=ci_boundary_failures,
    )
    pr_numbers = [int(number) for number in snapshot_summary.get("pr_numbers", [])]
    top_pr_number = max(pr_numbers) if pr_numbers else 0
    head_shas = snapshot_summary.get("head_shas", {})
    top_head_sha = str(head_shas.get(str(top_pr_number), "")) if isinstance(head_shas, dict) else ""
    merge_summary = snapshot_summary.get("merge_state_status_summary", {})
    merge_state_all_clean = isinstance(merge_summary, dict) and set(merge_summary) <= {"CLEAN"} and bool(
        merge_summary
    )
    live_snapshot_summary_path = Path(str(snapshot_summary.get("snapshot_run_root", ""))) / "summary.json"

    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "source_mode": snapshot_summary.get("source_mode", ""),
            "source_snapshot_path": snapshot_summary.get("source_snapshot_path", ""),
            "source_snapshot_sha256": snapshot_summary.get("source_snapshot_sha256", ""),
            "live_snapshot_summary_path": str(live_snapshot_summary_path),
            "live_snapshot_summary_sha256": sha256_file(live_snapshot_summary_path)
            if live_snapshot_summary_path.exists()
            else "",
            "pr_numbers": pr_numbers,
            "expected_stack_order": snapshot_summary.get("expected_stack_order", []),
            "base_chain": snapshot_summary.get("base_chain", []),
            "head_shas": head_shas,
            "top_pr_number": top_pr_number,
            "top_head_sha": top_head_sha,
            "ci_all_success": bool(snapshot_summary.get("ci_all_success", False)),
            "merge_state_all_clean": merge_state_all_clean,
            "merge_state_status_summary": merge_summary,
            "unresolved_review_thread_count": int(
                snapshot_summary.get("unresolved_review_thread_count", 0)
            ),
            "active_p1_p2_count": int(snapshot_summary.get("active_p1_p2_count", 0)),
            "stack_topology_status": snapshot_summary.get("stack_topology_status", "unknown"),
            "artifact_boundary_status": snapshot_summary.get("artifact_boundary_status", "unknown"),
            "claim_boundary_status": claim_status,
            "maturity_gate_status": maturity_status,
            "direct_llm_boundary_status": direct_status,
            "ci_boundary_preflight_status": ci_boundary_status,
            "ci_adoption_status": ci_adoption_status,
            "live_stack_refresh_status": status,
            "ready_for_human_merge_review": status == STATUS_READY,
            "blocker_reasons": blocker_reasons,
            "warnings": list(snapshot_summary.get("warnings", [])),
        }
    )
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def review_bundle_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# GOTRA v3.6AH Live Stack Refresh",
        "",
        f"- Status: `{summary['live_stack_refresh_status']}`",
        (
            "- Ready for human merge review: "
            f"`{str(summary['ready_for_human_merge_review']).lower()}`"
        ),
        "- Auto merge executed: `false`",
        f"- v3.7 allowed: `{str(summary['v3_7_allowed']).lower()}`",
        f"- Evidence layer: `{summary['evidence_layer']}`",
        f"- Source mode: `{summary['source_mode']}`",
        f"- PR numbers: `{', '.join(str(number) for number in summary['pr_numbers'])}`",
        f"- Top PR: `#{summary['top_pr_number']} @ {summary['top_head_sha']}`",
        f"- CI preflight status: `{summary['ci_boundary_preflight_status']}`",
        f"- CI adoption status: `{summary['ci_adoption_status']}`",
        f"- Next 30D check after: `{summary['next_30d_check_after']}`",
        "",
        "## Expected Stack Order",
        "",
    ]
    lines.extend(f"- {entry}" for entry in summary.get("expected_stack_order", []))
    if summary.get("blocker_reasons"):
        lines.extend(["", "## Blocking Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in summary["blocker_reasons"])
    if summary.get("warnings"):
        lines.extend(["", "## Boundary Notes", ""])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "This refresh is engineering/live stack status evidence only. It is not",
            "merge authorization, not auto-merge, and not an external validation or",
            "regulated recommendation. It does not authorize v3.7.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(*, run_root: Path, summary: dict[str, Any]) -> None:
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "refresh_run_id": summary["refresh_run_id"],
        "script_version": SCRIPT_VERSION,
        "summary_path": str(run_root / "summary.json"),
        "review_bundle_path": str(run_root / "review_bundle.md"),
        "packet_path": str(run_root / "packet.md"),
        "live_stack_refresh_status": summary["live_stack_refresh_status"],
        "auto_merge_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    bundle = review_bundle_markdown(summary)
    (run_root / "review_bundle.md").write_text(bundle, encoding="utf-8")
    (run_root / "packet.md").write_text(bundle, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-run-id", default=default_run_id())
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--use-gh", action="store_true")
    parser.add_argument("--repo", default="amanayayatu-tech/gotra")
    parser.add_argument("--pr-range", default="36-48")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ah_live_stack_refresh/runs"),
    )
    parser.add_argument("--expected-root-base", default="main")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--stack-head", dest="stack_heads", action="append", default=[])
    parser.add_argument("--next-30d-check-after", default=NEXT_30D_CHECK_AFTER)
    parser.add_argument(
        "--next-short-horizon-check-after",
        default=NEXT_SHORT_HORIZON_CHECK_AFTER,
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RefreshConfig:
    return RefreshConfig(
        refresh_run_id=str(args.refresh_run_id),
        output_dir=args.output_dir,
        snapshot=args.snapshot,
        use_gh=bool(args.use_gh),
        repo=str(args.repo),
        pr_range=str(args.pr_range),
        expected_root_base=str(args.expected_root_base),
        repo_root=args.repo_root,
        stack_heads=tuple(str(head) for head in (args.stack_heads or ())),
        next_30d_check_after=str(args.next_30d_check_after),
        next_short_horizon_check_after=str(args.next_short_horizon_check_after),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_refresh(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed.
        print(f"live stack refresh failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("live_stack_refresh_status") == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
