#!/usr/bin/env python3
"""GOTRA v3.6AC stacked PR human merge-readiness packet."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from scripts import baseline_v3_6aa_stack_evidence_boundary_audit as stack_audit
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan


SUMMARY_SCHEMA = "gotra.baseline_v3_6ac.stack_merge_readiness_packet_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ac.stack_merge_readiness_packet_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ac_stack_merge_readiness_packet_"
SCRIPT_VERSION = "v3.6ac-20260621"

STATUS_READY = "HUMAN_MERGE_PACKET_READY"
STATUS_BLOCKED_CI = "BLOCKED_CI"
STATUS_BLOCKED_REVIEW = "BLOCKED_REVIEW"
STATUS_BLOCKED_TOPOLOGY = "BLOCKED_TOPOLOGY"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_CONFLICT = "BLOCKED_CONFLICT"
STATUS_DATA_NOT_MATURED_MONITOR_ONLY = "DATA_NOT_MATURED_MONITOR_ONLY"
STATUS_BLOCKED_RUN_ID_EXISTS = "BLOCKED_RUN_ID_EXISTS"

CONFLICT_CLEAN = "CLEAN"
CONFLICT_BLOCKED = "BLOCKED_CONFLICT"
CONFLICT_UNKNOWN = "UNKNOWN_REQUIRES_HUMAN"

DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
NEXT_30D_CHECK_AFTER = stack_audit.NEXT_30D_CHECK_AFTER
NEXT_SHORT_HORIZON_CHECK_AFTER = stack_audit.NEXT_SHORT_HORIZON_CHECK_AFTER


@dataclass(frozen=True)
class PacketConfig:
    packet_run_id: str
    snapshot: Path
    output_dir: Path
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
        raise ValueError(f"packet_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("packet_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_snapshot(path: Path) -> dict[str, Any]:
    return stack_audit.load_snapshot(path)


def expected_merge_order(prs: list[dict[str, Any]]) -> list[str]:
    return [
        f"#{stack_audit.pr_number(pr)} {stack_audit.pr_base(pr)} -> {stack_audit.pr_head(pr)}"
        for pr in prs
    ]


def status_from_failures(clean_label: str, failures: list[str]) -> str:
    return clean_label if not failures else "blocked"


def flattened_status_checks(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    if not isinstance(raw, dict):
        return []
    contexts = raw.get("contexts", raw.get("nodes", []))
    if isinstance(contexts, dict):
        contexts = contexts.get("nodes", [])
    if not isinstance(contexts, list):
        return []
    return [entry for entry in contexts if isinstance(entry, dict)]


def normalize_pr_for_packet(pr: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(pr)
    normalized["statusCheckRollup"] = flattened_status_checks(
        pr.get("statusCheckRollup", pr.get("checks", []))
    )
    return normalized


def normalize_prs_for_packet(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_pr_for_packet(pr) for pr in prs]


def check_draft_prs(prs: list[dict[str, Any]]) -> list[str]:
    return [
        f"stack_topology:draft_pr:pr_{stack_audit.pr_number(pr)}"
        for pr in prs
        if bool(pr.get("isDraft", pr.get("is_draft", False)))
    ]


def claim_boundary_scan(snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> tuple[str, list[str], int]:
    docs = stack_audit.evidence_documents(snapshot, prs)
    sources = [
        claim_scan.ScanSource(
            path=doc.get("path", ""),
            text=doc.get("text", ""),
            origin="stack_merge_packet",
        )
        for doc in docs
    ]
    result = claim_scan.scan_sources(sources)
    failures = (
        result["maturity_gate"]
        + result["short_horizon_as_30d"]
        + result["direct_llm"]
        + result["overclaim"]
    )
    reasons = [
        f"claim_boundary:{item['path']}:{item['line_number']}:{item['rule_id']}"
        for item in failures
    ]
    return ("clean" if not failures else "blocked", reasons, len(failures))


def snapshot_conflict_status(snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> tuple[str, list[str]]:
    raw_status = str(
        snapshot.get("conflict_dry_run_status")
        or snapshot.get("conflict_status")
        or ""
    ).upper()
    reasons = merge_state_conflict_reasons(prs)
    if reasons:
        return CONFLICT_BLOCKED, reasons
    if raw_status:
        if raw_status in {"CLEAN", "NO_CONFLICT", "PASS"}:
            return CONFLICT_CLEAN, []
        if raw_status in {"UNKNOWN", "UNKNOWN_REQUIRES_HUMAN", "NOT_RUN"}:
            return CONFLICT_UNKNOWN, ["conflict_dry_run:unknown_requires_human"]
        return CONFLICT_BLOCKED, [f"conflict_dry_run:{raw_status.lower()}"]
    for pr in prs:
        status = str(pr.get("conflict_dry_run_status") or pr.get("conflict_status") or "").upper()
        if status in {"BLOCKED_CONFLICT", "CONFLICT", "FAILED"}:
            reasons.append(f"conflict_dry_run:pr_{stack_audit.pr_number(pr)}:{status.lower()}")
        elif status in {"UNKNOWN", "UNKNOWN_REQUIRES_HUMAN", "NOT_RUN"}:
            reasons.append(
                f"conflict_dry_run:pr_{stack_audit.pr_number(pr)}:unknown_requires_human"
            )
    if any("unknown_requires_human" in reason for reason in reasons):
        return CONFLICT_UNKNOWN, reasons
    if reasons:
        return CONFLICT_BLOCKED, reasons
    return CONFLICT_CLEAN, []


def merge_state_conflict_reasons(prs: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for pr in prs:
        status = str(pr.get("mergeStateStatus") or pr.get("merge_state_status") or "").upper()
        if status and status != "CLEAN":
            reasons.append(
                "conflict_dry_run:"
                f"pr_{stack_audit.pr_number(pr)}:merge_state_status:{status.lower()}"
            )
    return reasons


def merge_tree_output_has_conflict(output: str) -> bool:
    lowered = output.lower()
    conflict_markers = (
        "<<<<<<<",
        "changed in both",
        "removed in local",
        "removed in remote",
        "deleted in local",
        "deleted in remote",
        "added in both",
    )
    return any(marker in lowered for marker in conflict_markers)


def local_conflict_dry_run(config: PacketConfig) -> tuple[str, list[str]]:
    if not config.repo_root or not config.stack_heads:
        return CONFLICT_UNKNOWN, ["conflict_dry_run:local_not_requested"]
    heads = (config.expected_root_base, *config.stack_heads)
    reasons: list[str] = []
    for previous, current in zip(heads, heads[1:], strict=False):
        try:
            base = subprocess.run(
                ["git", "-C", str(config.repo_root), "merge-base", previous, current],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            tree = subprocess.run(
                ["git", "-C", str(config.repo_root), "merge-tree", base, previous, current],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            reasons.append(f"conflict_dry_run:unknown:{previous}->{current}:{exc.returncode}")
            continue
        if merge_tree_output_has_conflict(tree.stdout):
            reasons.append(f"conflict_dry_run:conflict:{previous}->{current}")
    if any(reason.startswith("conflict_dry_run:conflict") for reason in reasons):
        return CONFLICT_BLOCKED, reasons
    if reasons:
        return CONFLICT_UNKNOWN, reasons
    return CONFLICT_CLEAN, []


def conflict_dry_run(config: PacketConfig, snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> tuple[str, list[str]]:
    fixture_status, fixture_reasons = snapshot_conflict_status(snapshot, prs)
    if fixture_reasons or fixture_status != CONFLICT_CLEAN:
        return fixture_status, fixture_reasons
    if config.repo_root or config.stack_heads:
        return local_conflict_dry_run(config)
    return fixture_status, fixture_reasons


def maturity_boundary(snapshot: dict[str, Any]) -> tuple[str, list[str]]:
    status = str(
        snapshot.get("readiness_status")
        or snapshot.get("actual_readiness_status")
        or snapshot.get("maturity_status")
        or "DATA_NOT_MATURED"
    )
    if status == "READY_FOR_FORWARD_LIVE_VERDICT":
        return "READY_FOR_FORWARD_LIVE_VERDICT", []
    return STATUS_DATA_NOT_MATURED_MONITOR_ONLY, [
        f"maturity_boundary:{status}:v3_7_allowed=false"
    ]


def choose_packet_status(
    *,
    topology_failures: list[str],
    ci_failures: list[str],
    review_failures: list[str],
    artifact_failures: list[str],
    claim_failures: list[str],
    conflict_status: str,
    conflict_reasons: list[str],
) -> str:
    if topology_failures:
        return STATUS_BLOCKED_TOPOLOGY
    if ci_failures:
        return STATUS_BLOCKED_CI
    if review_failures:
        return STATUS_BLOCKED_REVIEW
    if artifact_failures:
        return STATUS_BLOCKED_ARTIFACT
    if claim_failures:
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    if conflict_status != CONFLICT_CLEAN or conflict_reasons:
        return STATUS_BLOCKED_CONFLICT
    return STATUS_READY


def base_summary(config: PacketConfig, *, run_root: Path, snapshot_sha: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "packet_run_id": config.packet_run_id,
        "packet_run_root": str(run_root),
        "packet_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "snapshot_path": str(config.snapshot),
        "snapshot_sha256": snapshot_sha,
        "open_pr_count": 0,
        "expected_merge_order": [],
        "stack_topology_status": "unknown",
        "ci_status": "unknown",
        "review_status": "unknown",
        "artifact_boundary_status": "unknown",
        "claim_boundary_status": "unknown",
        "conflict_dry_run_status": CONFLICT_UNKNOWN,
        "maturity_boundary_status": STATUS_DATA_NOT_MATURED_MONITOR_ONLY,
        "human_merge_readiness_status": STATUS_READY,
        "ready_for_human_merge": False,
        "auto_merge_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "next_30d_check_after": config.next_30d_check_after,
        "next_short_horizon_check_after": config.next_short_horizon_check_after,
        "evidence_layer": "engineering_human_merge_readiness_packet",
        "blocking_reasons": [],
        "warnings": [],
        "changed_file_count": 0,
        "changed_files": [],
        "ci_success_count": 0,
        "active_p1_p2_count": 0,
        "artifact_boundary_violation_count": 0,
        "claim_boundary_violation_count": 0,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
            "not_auto_merge": True,
        },
    }


def blocked_run_id_summary(config: PacketConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, snapshot_sha="")
    summary.update(
        {
            "human_merge_readiness_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocking_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def build_packet(config: PacketConfig) -> dict[str, Any]:
    validate_run_id(config.packet_run_id)
    run_root = config.output_dir / config.packet_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    snapshot = load_snapshot(config.snapshot)
    snapshot_sha = sha256_file(config.snapshot)
    prs = normalize_prs_for_packet(stack_audit.pr_list(snapshot))
    topology_status, topology_failures = stack_audit.check_stack_topology(
        prs,
        expected_root_base=config.expected_root_base,
    )
    draft_failures = check_draft_prs(prs)
    if draft_failures:
        topology_status = "blocked"
        topology_failures.extend(draft_failures)
    ci_success_count, ci_failures = stack_audit.check_ci(prs)
    active_p1_p2, nonblocking_reviews, review_failures = stack_audit.check_reviews(prs)
    paths = stack_audit.changed_paths(snapshot, prs)
    artifact_count, artifact_failures = stack_audit.check_artifact_boundary(paths)
    claim_status, claim_failures, claim_count = claim_boundary_scan(snapshot, prs)
    conflict_status, conflict_reasons = conflict_dry_run(config, snapshot, prs)
    maturity_status, maturity_notes = maturity_boundary(snapshot)
    packet_status = choose_packet_status(
        topology_failures=topology_failures,
        ci_failures=ci_failures,
        review_failures=review_failures,
        artifact_failures=artifact_failures,
        claim_failures=claim_failures,
        conflict_status=conflict_status,
        conflict_reasons=conflict_reasons,
    )
    blocking_reasons = (
        topology_failures
        + ci_failures
        + review_failures
        + artifact_failures
        + claim_failures
        + conflict_reasons
    )
    warnings = maturity_notes
    if conflict_status == CONFLICT_UNKNOWN:
        warnings.extend(conflict_reasons)

    summary = base_summary(config, run_root=run_root, snapshot_sha=snapshot_sha)
    summary.update(
        {
            "open_pr_count": len(prs),
            "expected_merge_order": expected_merge_order(prs),
            "stack_topology_status": topology_status,
            "ci_status": status_from_failures("clean", ci_failures),
            "review_status": status_from_failures("clean", review_failures),
            "artifact_boundary_status": status_from_failures("clean", artifact_failures),
            "claim_boundary_status": claim_status,
            "conflict_dry_run_status": conflict_status,
            "maturity_boundary_status": maturity_status,
            "human_merge_readiness_status": packet_status,
            "ready_for_human_merge": packet_status == STATUS_READY,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "changed_file_count": len(paths),
            "changed_files": paths,
            "ci_success_count": ci_success_count,
            "active_p1_p2_count": active_p1_p2,
            "unresolved_nonblocking_review_count": nonblocking_reviews,
            "artifact_boundary_violation_count": artifact_count,
            "claim_boundary_violation_count": claim_count,
            "pull_requests": [
                {
                    "number": stack_audit.pr_number(pr),
                    "title": str(pr.get("title") or ""),
                    "head": stack_audit.pr_head(pr),
                    "base": stack_audit.pr_base(pr),
                    "head_sha": str(pr.get("headRefOid") or pr.get("head_sha") or ""),
                    "is_draft": bool(pr.get("isDraft", pr.get("is_draft", False))),
                    "merge_state_status": str(pr.get("mergeStateStatus") or ""),
                }
                for pr in prs
            ],
        }
    )
    write_outputs(config=config, run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def human_packet_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# GOTRA v3.6AC Human Merge-Readiness Packet",
        "",
        f"- Status: `{summary['human_merge_readiness_status']}`",
        f"- Ready for human merge review/order: `{str(summary['ready_for_human_merge']).lower()}`",
        "- Auto merge executed: `false`",
        f"- v3.7 allowed: `{str(summary['v3_7_allowed']).lower()}`",
        f"- Evidence layer: `{summary['evidence_layer']}`",
        f"- Next 30D check after: `{summary['next_30d_check_after']}`",
        "",
        "## Expected Merge Order",
        "",
    ]
    lines.extend(f"- {entry}" for entry in summary["expected_merge_order"])
    if summary["blocking_reasons"]:
        lines.extend(["", "## Blocking Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in summary["blocking_reasons"])
    if summary["warnings"]:
        lines.extend(["", "## Boundary Notes", ""])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "This packet is engineering/local merge-readiness evidence only. It is not an",
            "OOS/science/public/trading claim and does not authorize v3.7.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(*, config: PacketConfig, run_root: Path, summary: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "packet_run_id": config.packet_run_id,
        "script_version": SCRIPT_VERSION,
        "summary_path": str(run_root / "summary.json"),
        "packet_path": str(run_root / "packet.md"),
        "snapshot_path": str(config.snapshot),
        "human_merge_readiness_status": summary["human_merge_readiness_status"],
        "auto_merge_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root / "packet.md").write_text(human_packet_markdown(summary), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-run-id", default=default_run_id())
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ac_stack_merge_readiness_packet/runs"),
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


def config_from_args(args: argparse.Namespace) -> PacketConfig:
    return PacketConfig(
        packet_run_id=str(args.packet_run_id),
        snapshot=args.snapshot,
        output_dir=args.output_dir,
        expected_root_base=str(args.expected_root_base),
        repo_root=args.repo_root,
        stack_heads=tuple(str(head) for head in (args.stack_heads or ())),
        next_30d_check_after=str(args.next_30d_check_after),
        next_short_horizon_check_after=str(args.next_short_horizon_check_after),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_packet(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI reports structured failures where possible.
        print(f"stack merge-readiness packet failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("human_merge_readiness_status") == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
