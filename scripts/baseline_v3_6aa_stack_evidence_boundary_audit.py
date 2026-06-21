#!/usr/bin/env python3
"""GOTRA v3.6AA stacked PR / evidence boundary audit."""

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


SUMMARY_SCHEMA = "gotra.baseline_v3_6aa.stack_evidence_boundary_audit_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6aa.stack_evidence_boundary_audit_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6aa_stack_evidence_boundary_audit_"
SCRIPT_VERSION = "v3.6aa-20260621"

STATUS_CLEAN = "STACK_AUDIT_CLEAN"
STATUS_BLOCKED_CI = "STACK_AUDIT_BLOCKED_CI"
STATUS_BLOCKED_REVIEW = "STACK_AUDIT_BLOCKED_REVIEW"
STATUS_BLOCKED_TOPOLOGY = "STACK_AUDIT_BLOCKED_TOPOLOGY"
STATUS_BLOCKED_ARTIFACT = "STACK_AUDIT_BLOCKED_ARTIFACT"
STATUS_BLOCKED_OVERCLAIM = "STACK_AUDIT_BLOCKED_OVERCLAIM"
STATUS_DATA_NOT_MATURED = "STACK_AUDIT_DATA_NOT_MATURED"
STATUS_BLOCKED_RUN_ID_EXISTS = "STACK_AUDIT_BLOCKED_RUN_ID_EXISTS"

DIRECT_LLM_INTERPRETATION = "direct_llm_parametric_memory_control"
NEXT_30D_CHECK_AFTER = "2026-07-21T00:00:00Z"
NEXT_SHORT_HORIZON_CHECK_AFTER = "2026-06-23T00:00:00Z"

BLOCKING_STATUS_PRIORITY = (
    STATUS_BLOCKED_TOPOLOGY,
    STATUS_BLOCKED_CI,
    STATUS_BLOCKED_REVIEW,
    STATUS_BLOCKED_ARTIFACT,
    STATUS_BLOCKED_OVERCLAIM,
)

FORBIDDEN_PATH_PATTERNS = (
    r"^data/backtest/runs/",
    r"^data/paper_trading/",
    r"(^|/)\.env",
    r"\.(sqlite|sqlite3|db)$",
    r"\.(bundle|tar|tgz|tar\.gz|zip)$",
    r"(^|/)(raw_outputs?|provider_raw|transcripts?)(/|$)",
    r"STAGE8|STAGE9|Stage8|Stage9",
)

OVERCLAIM_PATTERNS = (
    r"\bOOS\s+(pass|proof|accepted|validated)\b",
    r"\bscience/public\s+proof\b",
    r"\bpublic\s+proof\b",
    r"\btrading\s+(recommendation|advice)\b",
    r"\binvestment\s+(recommendation|advice)\b",
    r"\bprovider/formal-lite\s+acceptance\b",
    r"\b30D\s+forward-live\s+verdict\s+(allowed|ready|pass)\b",
)


@dataclass(frozen=True)
class AuditConfig:
    audit_run_id: str
    snapshot: Path
    output_dir: Path
    expected_root_base: str = "main"
    next_30d_check_after: str = NEXT_30D_CHECK_AFTER
    next_short_horizon_check_after: str = NEXT_SHORT_HORIZON_CHECK_AFTER
    allow_overwrite: bool = False


def parse_timestamp(value: str | None = None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"audit_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("audit_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"pull_requests": payload}
    if not isinstance(payload, dict):
        raise ValueError("snapshot must be a JSON object or PR list")
    return payload


def pr_list(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    raw = snapshot.get("pull_requests", snapshot.get("prs", []))
    if not isinstance(raw, list):
        raise ValueError("snapshot pull_requests must be a list")
    prs: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each pull request snapshot entry must be an object")
        prs.append(entry)
    return sorted(prs, key=lambda item: int(item.get("number") or 0))


def pr_number(pr: dict[str, Any]) -> int:
    return int(pr.get("number") or 0)


def pr_head(pr: dict[str, Any]) -> str:
    return str(pr.get("headRefName") or pr.get("head_ref") or pr.get("head") or "")


def pr_base(pr: dict[str, Any]) -> str:
    return str(pr.get("baseRefName") or pr.get("base_ref") or pr.get("base") or "")


def check_stack_topology(
    prs: list[dict[str, Any]],
    *,
    expected_root_base: str,
) -> tuple[str, list[str]]:
    if not prs:
        return "missing", ["stack_topology:no_open_prs"]
    failures: list[str] = []
    previous_head = ""
    for index, pr in enumerate(prs):
        number = pr_number(pr)
        head = pr_head(pr)
        base = pr_base(pr)
        if not head or not base:
            failures.append(f"stack_topology:missing_head_or_base:pr_{number}")
            continue
        if index == 0 and base != expected_root_base:
            failures.append(
                "stack_topology:root_base_mismatch:"
                f"pr_{number}:base={base}:expected={expected_root_base}"
            )
        if index > 0 and base != previous_head:
            failures.append(
                "stack_topology:base_chain_break:"
                f"pr_{number}:base={base}:expected={previous_head}"
            )
        previous_head = head
    return ("clean" if not failures else "blocked", failures)


def check_ci(prs: list[dict[str, Any]]) -> tuple[int, list[str]]:
    success_count = 0
    failures: list[str] = []
    for pr in prs:
        number = pr_number(pr)
        checks = pr.get("statusCheckRollup", pr.get("checks", []))
        if not isinstance(checks, list) or not checks:
            failures.append(f"ci:no_checks:pr_{number}")
            continue
        for check in checks:
            if not isinstance(check, dict):
                failures.append(f"ci:invalid_check_entry:pr_{number}")
                continue
            status = str(check.get("status") or "").upper()
            conclusion = str(check.get("conclusion") or "").upper()
            if status == "COMPLETED" and conclusion == "SUCCESS":
                success_count += 1
                continue
            failures.append(
                "ci:not_success:"
                f"pr_{number}:{check.get('name', 'check')}:{status}:{conclusion}"
            )
    return success_count, failures


def review_priority(thread: dict[str, Any]) -> str:
    explicit = str(thread.get("priority") or thread.get("severity") or "").upper()
    if explicit in {"P1", "P2"}:
        return explicit
    body = " ".join(str(comment.get("body") or "") for comment in review_comments(thread))
    match = re.search(r"\bP([12])\b|P([12]) Badge", body)
    if not match:
        return ""
    return f"P{match.group(1) or match.group(2)}"


def review_comments(thread: dict[str, Any]) -> list[dict[str, Any]]:
    comments = thread.get("comments", [])
    if isinstance(comments, dict):
        comments = comments.get("nodes", [])
    if not isinstance(comments, list):
        return []
    return [comment for comment in comments if isinstance(comment, dict)]


def review_threads(pr: dict[str, Any]) -> list[dict[str, Any]]:
    threads = pr.get("reviewThreads", pr.get("review_threads", []))
    if isinstance(threads, dict):
        threads = threads.get("nodes", [])
    if not isinstance(threads, list):
        return []
    return [thread for thread in threads if isinstance(thread, dict)]


def check_reviews(prs: list[dict[str, Any]]) -> tuple[int, int, list[str]]:
    active_p1_p2 = 0
    nonblocking = 0
    failures: list[str] = []
    for pr in prs:
        number = pr_number(pr)
        explicit = int(pr.get("unresolved_p1_p2_count") or 0)
        if explicit:
            active_p1_p2 += explicit
            failures.append(f"review:active_p1_p2:pr_{number}:count={explicit}")
        for thread in review_threads(pr):
            if thread.get("isResolved") is True or thread.get("isOutdated") is True:
                continue
            priority = review_priority(thread)
            if priority in {"P1", "P2"}:
                active_p1_p2 += 1
                failures.append(f"review:active_{priority}:pr_{number}")
            else:
                nonblocking += 1
    return active_p1_p2, nonblocking, failures


def changed_paths(snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for key in ("changed_files", "changedFiles", "files"):
        raw = snapshot.get(key, [])
        paths.extend(paths_from_collection(raw))
    for pr in prs:
        for key in ("changed_files", "changedFiles", "files"):
            raw = pr.get(key, [])
            paths.extend(paths_from_collection(raw))
    return sorted({path for path in paths if path})


def paths_from_collection(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        paths: list[str] = []
        for entry in raw:
            paths.extend(paths_from_collection(entry))
        return paths
    if isinstance(raw, dict):
        direct = path_from_entry(raw)
        paths = [direct] if direct else []
        for key in ("nodes", "edges"):
            nested = raw.get(key)
            if not isinstance(nested, list):
                continue
            for entry in nested:
                if key == "edges" and isinstance(entry, dict) and "node" in entry:
                    paths.extend(paths_from_collection(entry.get("node")))
                else:
                    paths.extend(paths_from_collection(entry))
        return paths
    return []


def path_from_entry(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("path") or entry.get("filename") or entry.get("name") or "")
    return ""


def check_artifact_boundary(paths: list[str]) -> tuple[int, list[str]]:
    violations: list[str] = []
    for path in paths:
        if any(re.search(pattern, path) for pattern in FORBIDDEN_PATH_PATTERNS):
            violations.append(f"artifact_boundary:forbidden_path:{path}")
    return len(violations), violations


def evidence_documents(snapshot: dict[str, Any], prs: list[dict[str, Any]]) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    raw_docs = snapshot.get("evidence_documents", snapshot.get("documents", []))
    if isinstance(raw_docs, list):
        docs.extend(document_entry(entry) for entry in raw_docs)
    for pr in prs:
        raw = pr.get("evidence_documents", [])
        if isinstance(raw, list):
            docs.extend(document_entry(entry) for entry in raw)
        body = str(pr.get("body") or "")
        if body:
            docs.append({"path": f"pr_{pr_number(pr)}_body", "text": body})
    return [doc for doc in docs if doc.get("text") or doc.get("path")]


def document_entry(entry: Any) -> dict[str, str]:
    if isinstance(entry, str):
        return {"path": "", "text": entry}
    if isinstance(entry, dict):
        return {
            "path": str(entry.get("path") or entry.get("filename") or ""),
            "text": str(entry.get("text") or entry.get("body") or entry.get("content") or ""),
        }
    return {"path": "", "text": ""}


def check_evidence_overclaims(docs: list[dict[str, str]]) -> tuple[int, list[str]]:
    failures: list[str] = []
    for index, doc in enumerate(docs):
        text = doc.get("text", "")
        label = doc.get("path") or f"document_{index}"
        for pattern in OVERCLAIM_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if overclaim_match_is_negated(text, match.start()):
                    continue
                failures.append(f"evidence_overclaim:{label}:{pattern}")
        if "direct_llm" in text and DIRECT_LLM_INTERPRETATION not in text:
            failures.append(f"evidence_overclaim:{label}:direct_llm_without_parametric_caveat")
    return len(failures), failures


def overclaim_match_is_negated(text: str, match_start: int) -> bool:
    prefix_start = max(
        text.rfind(".", 0, match_start),
        text.rfind(";", 0, match_start),
        text.rfind("\n", 0, match_start),
    )
    prefix = text[prefix_start + 1 : match_start].strip().lower()
    return bool(re.search(r"(?:^|\b)(not|no)\b|不是|不得|非", prefix))


def choose_status(blockers: dict[str, list[str]]) -> str:
    for status in BLOCKING_STATUS_PRIORITY:
        if blockers.get(status):
            return status
    return STATUS_CLEAN


def base_summary(config: AuditConfig, *, run_root: Path, snapshot_sha: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "audit_run_id": config.audit_run_id,
        "audit_run_root": str(run_root),
        "audit_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "snapshot_path": str(config.snapshot),
        "snapshot_sha256": snapshot_sha,
        "open_pr_count": 0,
        "stack_topology_status": "unknown",
        "ci_success_count": 0,
        "active_p1_p2_count": 0,
        "unresolved_nonblocking_review_count": 0,
        "artifact_boundary_violation_count": 0,
        "evidence_overclaim_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "next_30d_check_after": config.next_30d_check_after,
        "next_short_horizon_check_after": config.next_short_horizon_check_after,
        "expected_root_base": config.expected_root_base,
        "evidence_layer": "engineering_stack_audit",
        "overall_status": STATUS_CLEAN,
        "blocking_reasons": [],
        "changed_file_count": 0,
        "changed_files": [],
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
        },
    }


def blocked_run_id_summary(config: AuditConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root, snapshot_sha="")
    summary.update(
        {
            "overall_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocking_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def audit_snapshot(config: AuditConfig) -> dict[str, Any]:
    validate_run_id(config.audit_run_id)
    run_root = config.output_dir / config.audit_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    snapshot = load_snapshot(config.snapshot)
    snapshot_sha = sha256_file(config.snapshot)
    prs = pr_list(snapshot)
    topology_status, topology_failures = check_stack_topology(
        prs,
        expected_root_base=config.expected_root_base,
    )
    ci_success_count, ci_failures = check_ci(prs)
    active_p1_p2, nonblocking_reviews, review_failures = check_reviews(prs)
    paths = changed_paths(snapshot, prs)
    artifact_count, artifact_failures = check_artifact_boundary(paths)
    overclaim_count, overclaim_failures = check_evidence_overclaims(
        evidence_documents(snapshot, prs)
    )
    blockers = {
        STATUS_BLOCKED_TOPOLOGY: topology_failures,
        STATUS_BLOCKED_CI: ci_failures,
        STATUS_BLOCKED_REVIEW: review_failures,
        STATUS_BLOCKED_ARTIFACT: artifact_failures,
        STATUS_BLOCKED_OVERCLAIM: overclaim_failures,
    }
    status = choose_status(blockers)
    blocking_reasons = [
        reason
        for status_key in BLOCKING_STATUS_PRIORITY
        for reason in blockers.get(status_key, [])
    ]

    summary = base_summary(config, run_root=run_root, snapshot_sha=snapshot_sha)
    summary.update(
        {
            "open_pr_count": len(prs),
            "stack_topology_status": topology_status,
            "ci_success_count": ci_success_count,
            "active_p1_p2_count": active_p1_p2,
            "unresolved_nonblocking_review_count": nonblocking_reviews,
            "artifact_boundary_violation_count": artifact_count,
            "evidence_overclaim_count": overclaim_count,
            "overall_status": status,
            "blocking_reasons": blocking_reasons,
            "changed_file_count": len(paths),
            "changed_files": paths,
            "pull_requests": [
                {
                    "number": pr_number(pr),
                    "title": str(pr.get("title") or ""),
                    "head": pr_head(pr),
                    "base": pr_base(pr),
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


def write_outputs(*, config: AuditConfig, run_root: Path, summary: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "audit_run_id": config.audit_run_id,
        "script_version": SCRIPT_VERSION,
        "summary_path": str(run_root / "summary.json"),
        "snapshot_path": str(config.snapshot),
        "overall_status": summary["overall_status"],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
    }
    for filename, payload in (("summary.json", summary), ("manifest.json", manifest)):
        (run_root / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-run-id", default=default_run_id())
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6aa_stack_evidence_boundary_audit/runs"),
    )
    parser.add_argument("--next-30d-check-after", default=NEXT_30D_CHECK_AFTER)
    parser.add_argument("--expected-root-base", default="main")
    parser.add_argument(
        "--next-short-horizon-check-after",
        default=NEXT_SHORT_HORIZON_CHECK_AFTER,
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> AuditConfig:
    return AuditConfig(
        audit_run_id=str(args.audit_run_id),
        snapshot=args.snapshot,
        output_dir=args.output_dir,
        expected_root_base=str(args.expected_root_base),
        next_30d_check_after=str(args.next_30d_check_after),
        next_short_horizon_check_after=str(args.next_short_horizon_check_after),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = audit_snapshot(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI reports structured failures where possible.
        print(f"stack evidence boundary audit failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("overall_status") == STATUS_CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
