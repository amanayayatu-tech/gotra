#!/usr/bin/env python3
"""GOTRA v3.6AD actual live stacked PR readiness snapshot."""

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
from scripts import baseline_v3_6ac_stack_merge_readiness_packet as merge_packet


SUMMARY_SCHEMA = "gotra.baseline_v3_6ad.live_stack_readiness_snapshot_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ad.live_stack_readiness_snapshot_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ad_live_stack_readiness_snapshot_"
SCRIPT_VERSION = "v3.6ad-20260621"

STATUS_READY = "LIVE_STACK_SNAPSHOT_READY"
STATUS_BLOCKED_CI = "BLOCKED_CI"
STATUS_BLOCKED_REVIEW = "BLOCKED_REVIEW"
STATUS_BLOCKED_TOPOLOGY = "BLOCKED_TOPOLOGY"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_CONFLICT = "BLOCKED_CONFLICT"
STATUS_INCOMPLETE = "SNAPSHOT_INCOMPLETE"
STATUS_BLOCKED_RUN_ID_EXISTS = "LIVE_STACK_SNAPSHOT_BLOCKED_RUN_ID_EXISTS"

SOURCE_FIXTURE = "fixture"
SOURCE_GH_LIVE = "gh_live_snapshot"

NEXT_30D_CHECK_AFTER = merge_packet.NEXT_30D_CHECK_AFTER
NEXT_SHORT_HORIZON_CHECK_AFTER = merge_packet.NEXT_SHORT_HORIZON_CHECK_AFTER
DIRECT_LLM_INTERPRETATION = merge_packet.DIRECT_LLM_INTERPRETATION


@dataclass(frozen=True)
class SnapshotConfig:
    snapshot_run_id: str
    output_dir: Path
    snapshot: Path | None = None
    use_gh: bool = False
    repo: str = "amanayayatu-tech/gotra"
    pr_range: str = "36-44"
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
        raise ValueError(f"snapshot_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("snapshot_run_id may contain only letters, numbers, '_' and '-'")


def parse_pr_range(value: str) -> list[int]:
    raw = value.strip()
    if not raw:
        raise ValueError("pr_range cannot be empty")
    if "," in raw:
        numbers = [int(part.strip()) for part in raw.split(",") if part.strip()]
    elif "-" in raw:
        start_raw, end_raw = raw.split("-", maxsplit=1)
        start = int(start_raw.strip())
        end = int(end_raw.strip())
        if end < start:
            raise ValueError("pr_range end must be >= start")
        numbers = list(range(start, end + 1))
    else:
        numbers = [int(raw)]
    if not numbers or any(number <= 0 for number in numbers):
        raise ValueError("pr_range must contain positive PR numbers")
    return numbers


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source_snapshot(
    config: SnapshotConfig,
    *,
    run_root: Path,
) -> tuple[dict[str, Any], str, str, str]:
    if config.snapshot and config.use_gh:
        raise ValueError("choose either --snapshot or --use-gh, not both")
    if config.snapshot:
        snapshot = stack_audit.load_snapshot(config.snapshot)
        return snapshot, str(config.snapshot), sha256_file(config.snapshot), SOURCE_FIXTURE
    if config.use_gh:
        snapshot = fetch_gh_snapshot(repo=config.repo, numbers=parse_pr_range(config.pr_range))
        source_path = run_root / "gh_live_snapshot.json"
        source_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return snapshot, str(source_path), sha256_file(source_path), SOURCE_GH_LIVE
    raise ValueError("either --snapshot or --use-gh is required")


def fetch_gh_snapshot(*, repo: str, numbers: list[int]) -> dict[str, Any]:
    owner, name = parse_repo(repo)
    query = gh_query(owner=owner, name=name, numbers=numbers)
    completed = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    repository = payload.get("data", {}).get("repository", {})
    prs: list[dict[str, Any]] = []
    missing: list[int] = []
    for number in numbers:
        entry = repository.get(f"pr{number}")
        if entry is None:
            missing.append(number)
            continue
        prs.append(entry)
    return {
        "schema": "gotra.baseline_v3_6ad.gh_live_stack_snapshot_source.v1",
        "repo": repo,
        "pr_numbers": numbers,
        "missing_pr_numbers": missing,
        "pull_requests": prs,
        "readiness_status": "DATA_NOT_MATURED",
        "snapshot_created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
    }


def parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.strip().split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repo must use owner/name format")
    return parts[0], parts[1]


def gh_query(*, owner: str, name: str, numbers: list[int]) -> str:
    owner_json = json.dumps(owner)
    name_json = json.dumps(name)
    fields = """
      number
      title
      body
      baseRefName
      headRefName
      headRefOid
      isDraft
      mergeStateStatus
      state
      statusCheckRollup {
        contexts(first: 100) {
          nodes {
            __typename
            ... on CheckRun {
              name
              status
              conclusion
            }
            ... on StatusContext {
              context
              state
            }
          }
        }
      }
      reviewThreads(first: 100) {
        nodes {
          isResolved
          isOutdated
          comments(first: 20) {
            nodes {
              body
            }
          }
        }
      }
      files(first: 100) {
        nodes {
          path
        }
      }
    """
    aliases = "\n".join(
        f"pr{number}: pullRequest(number: {number}) {{{fields}}}" for number in numbers
    )
    return f"query {{ repository(owner: {owner_json}, name: {name_json}) {{ {aliases} }} }}"


def normalize_pr_for_snapshot(pr: dict[str, Any]) -> dict[str, Any]:
    normalized = merge_packet.normalize_pr_for_packet(pr)
    checks: list[dict[str, Any]] = []
    for check in normalized.get("statusCheckRollup", []):
        if not isinstance(check, dict):
            continue
        if check.get("__typename") == "StatusContext":
            state = str(check.get("state") or "").upper()
            checks.append(
                {
                    "name": str(check.get("context") or "status"),
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS" if state == "SUCCESS" else state,
                }
            )
            continue
        checks.append(check)
    normalized["statusCheckRollup"] = checks
    return normalized


def normalize_prs_for_snapshot(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_pr_for_snapshot(pr) for pr in prs]


def base_chain(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "number": stack_audit.pr_number(pr),
            "base": stack_audit.pr_base(pr),
            "head": stack_audit.pr_head(pr),
        }
        for pr in prs
    ]


def head_shas(prs: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(stack_audit.pr_number(pr)): str(pr.get("headRefOid") or pr.get("head_sha") or "")
        for pr in prs
    }


def merge_state_status_summary(prs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pr in prs:
        status = str(pr.get("mergeStateStatus") or pr.get("merge_state_status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def status_from_failures(clean_label: str, failures: list[str]) -> str:
    return clean_label if not failures else "blocked"


def sanitize_pr_body_for_claim_scan(text: str) -> str:
    lines: list[str] = []
    negative_context = False
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if negative_boundary_heading(lowered):
            negative_context = True
            lines.append("explicit non-claim boundary section")
            continue
        if negative_context and stripped.startswith("#"):
            negative_context = negative_boundary_heading(lowered)
        if negative_context and stripped:
            lines.append("explicit negative boundary item omitted")
            continue
        if "non-claim" in lowered or "non claim" in lowered:
            lines.append("explicit non-claim boundary line")
            continue
        if safe_false_v3_7_line(lowered):
            lines.append("v3_7_allowed=false")
            continue
        if test_coverage_boundary_line(lowered):
            lines.append("engineering test coverage boundary line omitted")
            continue
        lines.append(line)
    return "\n".join(lines)


def negative_boundary_heading(lowered: str) -> bool:
    compact = lowered.lstrip("# ").strip()
    return compact.startswith(
        (
            "cannot say",
            "can't say",
            "cannot claim",
            "do not say",
            "non-claims",
            "non claims",
            "boundary notes",
            "不可说",
            "不能说",
            "不得说",
        )
    )


def safe_false_v3_7_line(lowered: str) -> bool:
    if "v3.7" not in lowered and "v3_7" not in lowered and "v37" not in lowered:
        return False
    return any(
        marker in lowered
        for marker in (
            "false",
            "forbidden",
            "disallowed",
            "blocked",
            "not allowed",
            "do not execute",
            "does not execute",
            "not execute",
        )
    )


def test_coverage_boundary_line(lowered: str) -> bool:
    if not any(marker in lowered for marker in ("test", "tests", "fixture", "coverage")):
        return False
    return any(
        term in lowered
        for term in (
            "overclaim",
            "direct_llm",
            "oos",
            "science",
            "public",
            "trading",
            "v3.7",
            "v3_7",
            "30d",
            "maturity bypass",
        )
    )


def claim_boundary_scan(snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> tuple[str, list[str], int]:
    docs: list[dict[str, str]] = []
    raw_docs = snapshot.get("evidence_documents", snapshot.get("documents", []))
    if isinstance(raw_docs, list):
        docs.extend(stack_audit.document_entry(entry) for entry in raw_docs)
    for pr in prs:
        raw = pr.get("evidence_documents", [])
        if isinstance(raw, list):
            docs.extend(stack_audit.document_entry(entry) for entry in raw)
        body = str(pr.get("body") or "")
        if body:
            docs.append(
                {
                    "path": f"pr_{stack_audit.pr_number(pr)}_body",
                    "text": sanitize_pr_body_for_claim_scan(body),
                }
            )
    sources = [
        claim_scan.ScanSource(
            path=doc.get("path", ""),
            text=doc.get("text", ""),
            origin="live_stack_snapshot",
        )
        for doc in docs
        if doc.get("text") or doc.get("path")
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


def choose_snapshot_status(
    *,
    topology_failures: list[str],
    ci_failures: list[str],
    review_failures: list[str],
    artifact_failures: list[str],
    claim_failures: list[str],
    conflict_status: str,
    conflict_reasons: list[str],
    missing_pr_numbers: list[int],
) -> str:
    if missing_pr_numbers:
        return STATUS_INCOMPLETE
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
    if conflict_status != merge_packet.CONFLICT_CLEAN or conflict_reasons:
        return STATUS_BLOCKED_CONFLICT
    return STATUS_READY


def conflict_dry_run(
    config: SnapshotConfig,
    snapshot: dict[str, Any],
    prs: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    fixture_status, fixture_reasons = merge_packet.snapshot_conflict_status(snapshot, prs)
    if fixture_reasons or fixture_status != merge_packet.CONFLICT_CLEAN:
        return fixture_status, fixture_reasons
    if config.repo_root or config.stack_heads:
        packet_config = merge_packet.PacketConfig(
            packet_run_id="baseline_v3_6ac_stack_merge_readiness_packet_v36ad_probe",
            snapshot=Path("."),
            output_dir=Path("/tmp"),
            expected_root_base=config.expected_root_base,
            repo_root=config.repo_root,
            stack_heads=config.stack_heads,
        )
        return merge_packet.local_conflict_dry_run(packet_config)
    return fixture_status, fixture_reasons


def base_summary(
    config: SnapshotConfig,
    *,
    run_root: Path,
    source_mode: str,
    source_snapshot_path: str,
    source_snapshot_sha: str,
) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "snapshot_run_id": config.snapshot_run_id,
        "snapshot_run_root": str(run_root),
        "snapshot_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "source_mode": source_mode,
        "repo": config.repo,
        "source_snapshot_path": source_snapshot_path,
        "source_snapshot_sha256": source_snapshot_sha,
        "open_pr_count": 0,
        "pr_numbers": [],
        "expected_stack_order": [],
        "base_chain": [],
        "head_shas": {},
        "ci_all_success": False,
        "unresolved_review_thread_count": 0,
        "active_p1_p2_count": 0,
        "stack_topology_status": "unknown",
        "artifact_boundary_status": "unknown",
        "claim_boundary_status": "unknown",
        "merge_packet_status": "unknown",
        "conflict_dry_run_status": merge_packet.CONFLICT_UNKNOWN,
        "merge_state_status_summary": {},
        "live_stack_snapshot_status": STATUS_INCOMPLETE,
        "ready_for_human_merge_review": False,
        "auto_merge_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "next_30d_check_after": config.next_30d_check_after,
        "next_short_horizon_check_after": config.next_short_horizon_check_after,
        "evidence_layer": "engineering_live_stack_readiness_snapshot",
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
            "not_auto_merge": True,
            "not_merge_authorization": True,
        },
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "blocking_reasons": [],
        "warnings": [],
    }


def blocked_run_id_summary(config: SnapshotConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(
        config,
        run_root=run_root,
        source_mode="blocked",
        source_snapshot_path="",
        source_snapshot_sha="",
    )
    summary.update(
        {
            "live_stack_snapshot_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocking_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def build_snapshot(config: SnapshotConfig) -> dict[str, Any]:
    validate_run_id(config.snapshot_run_id)
    run_root = config.output_dir / config.snapshot_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    snapshot, source_path, source_sha, source_mode = load_source_snapshot(
        config,
        run_root=run_root,
    )
    prs = normalize_prs_for_snapshot(stack_audit.pr_list(snapshot))
    missing_pr_numbers = [
        int(number)
        for number in snapshot.get("missing_pr_numbers", [])
        if isinstance(number, int) or str(number).isdigit()
    ]
    topology_status, topology_failures = stack_audit.check_stack_topology(
        prs,
        expected_root_base=config.expected_root_base,
    )
    draft_failures = merge_packet.check_draft_prs(prs)
    if draft_failures:
        topology_status = "blocked"
        topology_failures.extend(draft_failures)
    ci_success_count, ci_failures = stack_audit.check_ci(prs)
    active_p1_p2, nonblocking_reviews, review_failures = stack_audit.check_reviews(prs)
    paths = stack_audit.changed_paths(snapshot, prs)
    artifact_count, artifact_failures = stack_audit.check_artifact_boundary(paths)
    claim_status, claim_failures, claim_count = claim_boundary_scan(snapshot, prs)
    conflict_status, conflict_reasons = conflict_dry_run(config, snapshot, prs)
    maturity_status, maturity_notes = merge_packet.maturity_boundary(snapshot)
    packet_status = merge_packet.choose_packet_status(
        topology_failures=topology_failures,
        ci_failures=ci_failures,
        review_failures=review_failures,
        artifact_failures=artifact_failures,
        claim_failures=claim_failures,
        conflict_status=conflict_status,
        conflict_reasons=conflict_reasons,
    )
    snapshot_status = choose_snapshot_status(
        topology_failures=topology_failures,
        ci_failures=ci_failures,
        review_failures=review_failures,
        artifact_failures=artifact_failures,
        claim_failures=claim_failures,
        conflict_status=conflict_status,
        conflict_reasons=conflict_reasons,
        missing_pr_numbers=missing_pr_numbers,
    )
    blocking_reasons = (
        [f"snapshot_incomplete:missing_pr_{number}" for number in missing_pr_numbers]
        + topology_failures
        + ci_failures
        + review_failures
        + artifact_failures
        + claim_failures
        + conflict_reasons
    )
    warnings = list(maturity_notes)
    if conflict_status == merge_packet.CONFLICT_UNKNOWN:
        warnings.extend(conflict_reasons)

    summary = base_summary(
        config,
        run_root=run_root,
        source_mode=source_mode,
        source_snapshot_path=source_path,
        source_snapshot_sha=source_sha,
    )
    pr_numbers = [stack_audit.pr_number(pr) for pr in prs]
    summary.update(
        {
            "open_pr_count": len(prs),
            "pr_numbers": pr_numbers,
            "expected_stack_order": merge_packet.expected_merge_order(prs),
            "base_chain": base_chain(prs),
            "head_shas": head_shas(prs),
            "ci_all_success": not ci_failures and bool(ci_success_count),
            "ci_success_count": ci_success_count,
            "unresolved_review_thread_count": active_p1_p2 + nonblocking_reviews,
            "active_p1_p2_count": active_p1_p2,
            "unresolved_nonblocking_review_count": nonblocking_reviews,
            "stack_topology_status": topology_status,
            "artifact_boundary_status": status_from_failures("clean", artifact_failures),
            "claim_boundary_status": claim_status,
            "merge_packet_status": packet_status,
            "conflict_dry_run_status": conflict_status,
            "merge_state_status_summary": merge_state_status_summary(prs),
            "live_stack_snapshot_status": snapshot_status,
            "ready_for_human_merge_review": snapshot_status == STATUS_READY,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "changed_file_count": len(paths),
            "changed_files": paths,
            "artifact_boundary_violation_count": artifact_count,
            "claim_boundary_violation_count": claim_count,
            "maturity_boundary_status": maturity_status,
            "missing_pr_numbers": missing_pr_numbers,
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
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def review_bundle_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# GOTRA v3.6AD Live Stack Readiness Snapshot",
        "",
        f"- Status: `{summary['live_stack_snapshot_status']}`",
        (
            "- Ready for human merge review: "
            f"`{str(summary['ready_for_human_merge_review']).lower()}`"
        ),
        "- Auto merge executed: `false`",
        f"- v3.7 allowed: `{str(summary['v3_7_allowed']).lower()}`",
        f"- Evidence layer: `{summary['evidence_layer']}`",
        f"- Source mode: `{summary['source_mode']}`",
        f"- Open PR count: `{summary['open_pr_count']}`",
        f"- PR numbers: `{', '.join(str(number) for number in summary['pr_numbers'])}`",
        f"- Next 30D check after: `{summary['next_30d_check_after']}`",
        f"- Next short-horizon check after: `{summary['next_short_horizon_check_after']}`",
        "",
        "## Expected Stack Order",
        "",
    ]
    lines.extend(f"- {entry}" for entry in summary["expected_stack_order"])
    if summary["blocking_reasons"]:
        lines.extend(["", "## Blocking Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in summary["blocking_reasons"])
    if summary["warnings"]:
        lines.extend(["", "## Boundary Notes", ""])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "This snapshot is engineering/live stack readiness evidence only. It is not",
            "merge authorization, not auto-merge, not an OOS/science/public/trading claim,",
            "and it does not authorize v3.7.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(*, run_root: Path, summary: dict[str, Any]) -> None:
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "snapshot_run_id": summary["snapshot_run_id"],
        "script_version": SCRIPT_VERSION,
        "summary_path": str(run_root / "summary.json"),
        "review_bundle_path": str(run_root / "review_bundle.md"),
        "packet_path": str(run_root / "packet.md"),
        "source_snapshot_path": summary["source_snapshot_path"],
        "live_stack_snapshot_status": summary["live_stack_snapshot_status"],
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
    bundle = review_bundle_markdown(summary)
    (run_root / "review_bundle.md").write_text(bundle, encoding="utf-8")
    (run_root / "packet.md").write_text(bundle, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-run-id", default=default_run_id())
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--use-gh", action="store_true")
    parser.add_argument("--repo", default="amanayayatu-tech/gotra")
    parser.add_argument("--pr-range", default="36-44")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ad_live_stack_readiness_snapshot/runs"),
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
        stack_heads=tuple(str(head) for head in (args.stack_heads or ())),
        next_30d_check_after=str(args.next_30d_check_after),
        next_short_horizon_check_after=str(args.next_short_horizon_check_after),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_snapshot(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI reports structured failures where possible.
        print(f"live stack readiness snapshot failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("live_stack_snapshot_status") == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
