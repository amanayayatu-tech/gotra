#!/usr/bin/env python3
"""GOTRA v3.6AE continuous stack boundary guard / CI-local preflight."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

from scripts import baseline_v3_6aa_stack_evidence_boundary_audit as stack_audit
from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan
from scripts import baseline_v3_6ac_stack_merge_readiness_packet as merge_packet
from scripts import baseline_v3_6ad_live_stack_readiness_snapshot as live_snapshot


SUMMARY_SCHEMA = "gotra.baseline_v3_6ae.continuous_stack_boundary_guard_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ae.continuous_stack_boundary_guard_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ae_continuous_stack_boundary_guard_"
SCRIPT_VERSION = "v3.6ae-20260621"

STATUS_CLEAN = "STACK_BOUNDARY_GUARD_CLEAN"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_MATURITY_GATE = "BLOCKED_MATURITY_GATE"
STATUS_BLOCKED_DIRECT_LLM = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_INCOMPLETE = "SNAPSHOT_INCOMPLETE"
STATUS_BLOCKED_RUN_ID_EXISTS = "STACK_BOUNDARY_GUARD_BLOCKED_RUN_ID_EXISTS"

DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION
NEXT_30D_CHECK_AFTER = merge_packet.NEXT_30D_CHECK_AFTER
NEXT_SHORT_HORIZON_CHECK_AFTER = merge_packet.NEXT_SHORT_HORIZON_CHECK_AFTER


@dataclass(frozen=True)
class GuardConfig:
    guard_run_id: str
    output_dir: Path
    files: tuple[Path, ...] = ()
    manifest: Path | None = None
    snapshot: Path | None = None
    pr_range: str = "36-45"
    expected_root_base: str = "main"
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"guard_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("guard_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitized_source(source: claim_scan.ScanSource) -> claim_scan.ScanSource:
    lines: list[str] = []
    for line in source.text.splitlines():
        if live_snapshot.safe_false_v3_7_line(line.lower()):
            lines.append(neutralize_safe_v3_7_fragments(line))
        else:
            lines.append(line)
    return claim_scan.ScanSource(
        path=source.path,
        text="\n".join(lines),
        origin=source.origin,
    )


def neutralize_safe_v3_7_fragments(line: str) -> str:
    replacements = (
        (
            r"['\"]?\bv3[_ .-]?7[_ .-]?allowed['\"]?\s*[:=]\s*[`'\"]?(?:false|no)\b[`'\"]?",
            "v3_7_allowed=false",
        ),
        (
            r"\bv(?:3[._-]?7|37)\b.{0,40}\ballowed\s*:\s*[`'\"]?(?:false|no)\b[`'\"]?",
            "v3_7_allowed=false",
        ),
        (
            r"\bv(?:3[._-]?7|37)\b.{0,40}\b(?:not\s+allowed|disallowed|forbidden|blocked)\b",
            "v3_7_allowed=false",
        ),
        (
            r"\b(do(?:es)?\s+not|not)\s+(execute|authorize).{0,40}\bv(?:3[._-]?7|37)\b",
            "v3_7_allowed=false",
        ),
    )
    sanitized = line
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized


def text_scan(config: GuardConfig) -> dict[str, Any]:
    scan_config = claim_scan.ScanConfig(
        scan_run_id=f"{claim_scan.RUN_ID_PREFIX}{utc_timestamp_slug()}",
        output_dir=Path("/tmp/gotra_v3_6ae_claim_scan_probe"),
        files=config.files,
        manifest=config.manifest,
    )
    sources, paths = claim_scan.collect_sources(scan_config)
    forbidden_items = [
        claim_scan.make_blocked_item(
            path,
            0,
            "forbidden_artifact_path",
            "path is forbidden artifact input",
        )
        for path in paths
        if claim_scan.forbidden_path(path)
    ]
    safe_sources = [
        sanitized_source(source)
        for source in sources
        if not claim_scan.forbidden_path(source.path)
    ]
    scan_result = claim_scan.scan_sources(safe_sources)
    return {
        "paths": paths,
        "forbidden_items": forbidden_items,
        "overclaims": scan_result["overclaim"],
        "direct_llm": scan_result["direct_llm"],
        "maturity": scan_result["maturity_gate"],
        "short_horizon": scan_result["short_horizon_as_30d"],
        "warnings": scan_result["warnings"],
        "manifest_path": claim_scan.normalize_scan_path(config.manifest) if config.manifest else "",
        "manifest_sha256": (
            sha256_file(config.manifest)
            if config.manifest
            and not claim_scan.forbidden_path(claim_scan.normalize_scan_path(config.manifest))
            else ""
        ),
    }


def snapshot_scan(config: GuardConfig) -> dict[str, Any]:
    if not config.snapshot:
        return {
            "checked_pr_count": 0,
            "paths": [],
            "artifact_failures": [],
            "claim_failures": [],
            "maturity_failures": [],
            "direct_llm_failures": [],
            "incomplete_failures": [],
            "ci_failures": [],
            "review_failures": [],
            "topology_failures": [],
            "conflict_failures": [],
            "snapshot_sha256": "",
        }
    snapshot_path = claim_scan.normalize_scan_path(config.snapshot)
    if claim_scan.forbidden_path(snapshot_path):
        return {
            "checked_pr_count": 0,
            "paths": [snapshot_path],
            "artifact_failures": [f"artifact_boundary:forbidden_snapshot_path:{snapshot_path}"],
            "claim_failures": [],
            "maturity_failures": [],
            "direct_llm_failures": [],
            "incomplete_failures": [],
            "ci_failures": [],
            "review_failures": [],
            "topology_failures": [],
            "conflict_failures": [],
            "snapshot_sha256": "",
        }
    snapshot = stack_audit.load_snapshot(config.snapshot)
    prs = live_snapshot.normalize_prs_for_snapshot(stack_audit.pr_list(snapshot))
    expected_numbers = live_snapshot.parse_pr_range(config.pr_range)
    missing, incomplete, state_failures = live_snapshot.snapshot_completeness_failures(
        expected_numbers=expected_numbers,
        prs=prs,
        snapshot=snapshot,
    )
    topology_status, topology_failures = stack_audit.check_stack_topology(
        prs,
        expected_root_base=config.expected_root_base,
    )
    if state_failures:
        topology_status = "blocked"
        topology_failures.extend(state_failures)
    draft_failures = merge_packet.check_draft_prs(prs)
    if draft_failures:
        topology_status = "blocked"
        topology_failures.extend(draft_failures)
    _ = topology_status
    _, ci_failures = stack_audit.check_ci(prs)
    _, _, review_failures = stack_audit.check_reviews(prs)
    evidence_paths = evidence_document_paths(snapshot, prs)
    evidence_artifact_failures = [
        f"artifact_boundary:forbidden_evidence_document_path:{path}"
        for path in evidence_paths
        if claim_scan.forbidden_path(path)
    ]
    claim_snapshot, claim_prs = snapshot_without_forbidden_evidence_documents(snapshot, prs)
    changed_paths = stack_audit.changed_paths(snapshot, prs)
    paths = changed_paths + evidence_paths
    _, artifact_failures = stack_audit.check_artifact_boundary(changed_paths)
    artifact_failures.extend(evidence_artifact_failures)
    claim_status, claim_failures, _ = live_snapshot.claim_boundary_scan(claim_snapshot, claim_prs)
    _ = claim_status
    conflict_status, conflict_failures = merge_packet.snapshot_conflict_status(snapshot, prs)
    if conflict_status != merge_packet.CONFLICT_CLEAN and not conflict_failures:
        conflict_failures = [f"conflict:{conflict_status}"]
    incomplete_failures = (
        [f"snapshot_incomplete:missing_pr_{number}" for number in missing]
        + [
            f"snapshot_incomplete:changed_files_pagination_incomplete:pr_{number}"
            for number in incomplete
        ]
    )
    maturity_failures = [
        reason
        for reason in claim_failures
        if "v3_7" in reason
        or "30d" in reason.lower()
        or "thirty_day" in reason.lower()
        or "thirty-day" in reason.lower()
        or "maturity" in reason.lower()
        or "short_horizon" in reason
    ]
    direct_llm_failures = [reason for reason in claim_failures if "direct_llm" in reason]
    return {
        "checked_pr_count": len(prs),
        "paths": paths,
        "artifact_failures": artifact_failures,
        "claim_failures": [
            reason
            for reason in claim_failures
            if reason not in maturity_failures and reason not in direct_llm_failures
        ],
        "maturity_failures": maturity_failures,
        "direct_llm_failures": direct_llm_failures,
        "incomplete_failures": incomplete_failures,
        "ci_failures": ci_failures,
        "review_failures": review_failures,
        "topology_failures": topology_failures,
        "conflict_failures": conflict_failures,
        "snapshot_sha256": sha256_file(config.snapshot),
    }


def evidence_document_paths(snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    raw_docs = snapshot.get("evidence_documents", snapshot.get("documents", []))
    if isinstance(raw_docs, list):
        paths.extend(doc.get("path", "") for doc in map(stack_audit.document_entry, raw_docs))
    for pr in prs:
        raw = pr.get("evidence_documents", [])
        if isinstance(raw, list):
            paths.extend(doc.get("path", "") for doc in map(stack_audit.document_entry, raw))
    return sorted({path for path in paths if path})


def snapshot_without_forbidden_evidence_documents(
    snapshot: dict[str, Any],
    prs: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    filtered_snapshot = deepcopy(snapshot)
    for key in ("evidence_documents", "documents"):
        raw = filtered_snapshot.get(key)
        if isinstance(raw, list):
            filtered_snapshot[key] = [
                entry
                for entry in raw
                if not claim_scan.forbidden_path(stack_audit.document_entry(entry).get("path", ""))
            ]
    filtered_prs = []
    for pr in prs:
        filtered = deepcopy(pr)
        raw = filtered.get("evidence_documents", [])
        if isinstance(raw, list):
            filtered["evidence_documents"] = [
                entry
                for entry in raw
                if not claim_scan.forbidden_path(stack_audit.document_entry(entry).get("path", ""))
            ]
        filtered_prs.append(filtered)
    return filtered_snapshot, filtered_prs


def choose_status(
    *,
    artifact_count: int,
    incomplete_count: int,
    maturity_count: int,
    direct_llm_count: int,
    claim_count: int,
    stack_blocker_count: int,
) -> str:
    if artifact_count:
        return STATUS_BLOCKED_ARTIFACT
    if incomplete_count or stack_blocker_count:
        return STATUS_INCOMPLETE
    if maturity_count:
        return STATUS_BLOCKED_MATURITY_GATE
    if direct_llm_count:
        return STATUS_BLOCKED_DIRECT_LLM
    if claim_count:
        return STATUS_BLOCKED_CLAIM_BOUNDARY
    return STATUS_CLEAN


def status_label(blocked: bool) -> str:
    return "blocked" if blocked else "clean"


def base_summary(config: GuardConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "guard_run_id": config.guard_run_id,
        "guard_run_root": str(run_root),
        "guard_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "checked_file_count": 0,
        "checked_pr_count": 0,
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "maturity_gate_status": "clean",
        "direct_llm_boundary_status": "clean",
        "stack_guard_status": STATUS_CLEAN,
        "ready_for_human_merge_review": True,
        "auto_merge_executed": False,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "evidence_layer": "engineering_stack_boundary_guard",
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "next_30d_check_after": NEXT_30D_CHECK_AFTER,
        "next_short_horizon_check_after": NEXT_SHORT_HORIZON_CHECK_AFTER,
        "blocker_reasons": [],
        "blocked_items": [],
        "warnings": [],
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
            "not_auto_merge": True,
        },
    }


def blocked_run_id_summary(config: GuardConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "stack_guard_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "ready_for_human_merge_review": False,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_guard(config: GuardConfig) -> dict[str, Any]:
    validate_run_id(config.guard_run_id)
    run_root = config.output_dir / config.guard_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    text = text_scan(config)
    stack = snapshot_scan(config)
    text_artifacts = text["forbidden_items"]
    maturity_items = text["maturity"] + text["short_horizon"]
    direct_items = text["direct_llm"]
    claim_items = text["overclaims"]
    stack_artifacts = stack["artifact_failures"]
    stack_maturity = stack["maturity_failures"]
    stack_direct = stack["direct_llm_failures"]
    stack_claim = stack["claim_failures"]
    stack_incomplete = stack["incomplete_failures"]
    stack_blockers = (
        stack["ci_failures"]
        + stack["review_failures"]
        + stack["topology_failures"]
        + stack["conflict_failures"]
    )
    artifact_count = len(text_artifacts) + len(stack_artifacts)
    incomplete_count = len(stack_incomplete)
    maturity_count = len(maturity_items) + len(stack_maturity)
    direct_count = len(direct_items) + len(stack_direct)
    claim_count = len(claim_items) + len(stack_claim)
    status = choose_status(
        artifact_count=artifact_count,
        incomplete_count=incomplete_count,
        maturity_count=maturity_count,
        direct_llm_count=direct_count,
        claim_count=claim_count,
        stack_blocker_count=len(stack_blockers),
    )
    blocked_items = text_artifacts + maturity_items + direct_items + claim_items
    blocker_reasons = (
        [f"artifact_boundary:{item['path']}:{item['rule_id']}" for item in text_artifacts]
        + stack_artifacts
        + stack_incomplete
        + stack_blockers
        + [f"maturity_gate:{item['path']}:{item['line_number']}:{item['rule_id']}" for item in maturity_items]
        + stack_maturity
        + [f"direct_llm:{item['path']}:{item['line_number']}:{item['rule_id']}" for item in direct_items]
        + stack_direct
        + [f"claim_boundary:{item['path']}:{item['line_number']}:{item['rule_id']}" for item in claim_items]
        + stack_claim
    )
    summary = base_summary(config, run_root=run_root)
    all_paths = sorted({*text["paths"], *stack["paths"]})
    summary.update(
        {
            "checked_file_count": len(all_paths),
            "checked_pr_count": stack["checked_pr_count"],
            "artifact_boundary_status": status_label(bool(artifact_count)),
            "claim_boundary_status": status_label(bool(claim_count)),
            "maturity_gate_status": status_label(bool(maturity_count)),
            "direct_llm_boundary_status": status_label(bool(direct_count)),
            "stack_guard_status": status,
            "ready_for_human_merge_review": status == STATUS_CLEAN,
            "blocker_reasons": blocker_reasons,
            "blocked_items": blocked_items,
            "warnings": text["warnings"],
            "checked_paths": all_paths,
            "forbidden_path_count": artifact_count,
            "evidence_overclaim_count": claim_count,
            "maturity_gate_bypass_count": maturity_count,
            "direct_llm_mislabel_count": direct_count,
            "snapshot_path": str(config.snapshot) if config.snapshot else "",
            "snapshot_sha256": stack["snapshot_sha256"],
            "manifest_path": text["manifest_path"],
            "manifest_sha256": text["manifest_sha256"],
        }
    )
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def write_outputs(*, run_root: Path, summary: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "guard_run_id": summary["guard_run_id"],
        "script_version": SCRIPT_VERSION,
        "summary_path": str(run_root / "summary.json"),
        "stack_guard_status": summary["stack_guard_status"],
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard-run-id", default=default_run_id())
    parser.add_argument("--file", dest="files", type=Path, action="append", default=[])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--pr-range", default="36-45")
    parser.add_argument("--expected-root-base", default="main")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ae_continuous_stack_boundary_guard/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> GuardConfig:
    return GuardConfig(
        guard_run_id=str(args.guard_run_id),
        output_dir=args.output_dir,
        files=tuple(args.files or ()),
        manifest=args.manifest,
        snapshot=args.snapshot,
        pr_range=str(args.pr_range),
        expected_root_base=str(args.expected_root_base),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_guard(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI preflight should fail closed.
        print(f"continuous stack boundary guard failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("stack_guard_status") == STATUS_CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
