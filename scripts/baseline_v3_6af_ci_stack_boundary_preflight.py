#!/usr/bin/env python3
"""GOTRA v3.6AF CI/local stack boundary preflight wrapper."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from typing import Any

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan
from scripts import baseline_v3_6ae_continuous_stack_boundary_guard as guard


SUMMARY_SCHEMA = "gotra.baseline_v3_6af.ci_stack_boundary_preflight_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6af.ci_stack_boundary_preflight_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6af_ci_stack_boundary_preflight_"
SCRIPT_VERSION = "v3.6af-20260621"

STATUS_CLEAN = "CI_STACK_BOUNDARY_PREFLIGHT_CLEAN"
STATUS_BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
STATUS_BLOCKED_CLAIM_BOUNDARY = "BLOCKED_CLAIM_BOUNDARY"
STATUS_BLOCKED_MATURITY_GATE = "BLOCKED_MATURITY_GATE"
STATUS_BLOCKED_DIRECT_LLM = "BLOCKED_DIRECT_LLM_BOUNDARY"
STATUS_INCOMPLETE = "SNAPSHOT_INCOMPLETE"
STATUS_FAIL = "PREFLIGHT_FAIL"

DEFAULT_PATHSPECS = ("docs/", "scripts/", "tests/", ".github/")
DIRECT_LLM_INTERPRETATION = guard.DIRECT_LLM_INTERPRETATION


@dataclass(frozen=True)
class PreflightConfig:
    preflight_run_id: str
    output_root: Path
    repo_root: Path = Path.cwd()
    tracked_only: bool = True
    pathspecs: tuple[str, ...] = DEFAULT_PATHSPECS
    manifest: Path | None = None
    snapshot: Path | None = None
    pr_range: str = "36-46"
    expected_root_base: str = "main"
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"preflight_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("preflight_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def guard_run_id(preflight_run_id: str) -> str:
    suffix = preflight_run_id.removeprefix(RUN_ID_PREFIX)
    return f"{guard.RUN_ID_PREFIX}v3_6af_{suffix}"


def normalize_repo_path(path: Path | str, *, repo_root: Path) -> str:
    raw = Path(path).expanduser()
    try:
        resolved = raw.resolve()
    except OSError:
        return claim_scan.normalize_scan_path(str(path))
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return claim_scan.normalize_scan_path(resolved)


def forbidden_repo_path(path: Path | str, *, repo_root: Path) -> bool:
    return claim_scan.forbidden_path(normalize_repo_path(path, repo_root=repo_root))


def git_lines(repo_root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def tracked_paths(config: PreflightConfig) -> list[Path]:
    if not config.tracked_only:
        raise ValueError("v3.6AF currently supports tracked-only scans only")
    args = ["ls-files", "--", *config.pathspecs]
    return [config.repo_root / line for line in git_lines(config.repo_root, args)]


def skipped_untracked_count(config: PreflightConfig) -> int:
    if not config.tracked_only:
        return 0
    args = ["ls-files", "--others", "--exclude-standard", "--", *config.pathspecs]
    return len(git_lines(config.repo_root, args))


def pre_read_artifact_failures(config: PreflightConfig) -> list[str]:
    failures: list[str] = []
    for label, path in (("manifest", config.manifest), ("snapshot", config.snapshot)):
        if path and forbidden_repo_path(path, repo_root=config.repo_root):
            normalized = normalize_repo_path(path, repo_root=config.repo_root)
            failures.append(f"artifact_boundary:forbidden_{label}_path:{normalized}")
    return failures


def status_from_guard(guard_status: str, pre_read_failures: list[str]) -> str:
    if pre_read_failures:
        return STATUS_BLOCKED_ARTIFACT
    mapping = {
        guard.STATUS_CLEAN: STATUS_CLEAN,
        guard.STATUS_BLOCKED_ARTIFACT: STATUS_BLOCKED_ARTIFACT,
        guard.STATUS_BLOCKED_CLAIM_BOUNDARY: STATUS_BLOCKED_CLAIM_BOUNDARY,
        guard.STATUS_BLOCKED_MATURITY_GATE: STATUS_BLOCKED_MATURITY_GATE,
        guard.STATUS_BLOCKED_DIRECT_LLM: STATUS_BLOCKED_DIRECT_LLM,
        guard.STATUS_INCOMPLETE: STATUS_INCOMPLETE,
    }
    return mapping.get(guard_status, STATUS_FAIL)


def base_summary(config: PreflightConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "preflight_run_id": config.preflight_run_id,
        "preflight_run_root": str(run_root),
        "preflight_timestamp_utc": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "repo_root": str(config.repo_root),
        "tracked_only": config.tracked_only,
        "pathspecs": list(config.pathspecs),
        "scanned_tracked_file_count": 0,
        "skipped_untracked_count": 0,
        "checked_pr_count": 0,
        "guard_run_id": "",
        "guard_summary_path": "",
        "guard_summary_sha256": "",
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "maturity_gate_status": "clean",
        "direct_llm_boundary_status": "clean",
        "preflight_status": STATUS_CLEAN,
        "ready_for_human_merge_review": True,
        "auto_merge_executed": False,
        "v3_7_allowed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "evidence_layer": "engineering_ci_stack_boundary_preflight",
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "blocker_reasons": [],
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
            "not_auto_merge": True,
        },
    }


def write_outputs(*, run_root: Path, summary: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "preflight_run_id": summary["preflight_run_id"],
        "script_version": SCRIPT_VERSION,
        "summary_path": str(run_root / "summary.json"),
        "preflight_status": summary["preflight_status"],
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


def fail_summary(
    config: PreflightConfig,
    *,
    run_root: Path,
    blocker_reasons: list[str],
    scanned_tracked_file_count: int = 0,
    skipped_count: int = 0,
    status: str = STATUS_FAIL,
) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    artifact_blocked = status == STATUS_BLOCKED_ARTIFACT
    summary.update(
        {
            "scanned_tracked_file_count": scanned_tracked_file_count,
            "skipped_untracked_count": skipped_count,
            "artifact_boundary_status": "blocked" if artifact_blocked else "clean",
            "preflight_status": status,
            "ready_for_human_merge_review": False,
            "blocker_reasons": blocker_reasons,
        }
    )
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_preflight(config: PreflightConfig) -> dict[str, Any]:
    validate_run_id(config.preflight_run_id)
    run_root = config.output_root / config.preflight_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return fail_summary(
            config,
            run_root=run_root,
            blocker_reasons=["output_run_id_exists"],
            status=STATUS_FAIL,
        )
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    pre_read_failures = pre_read_artifact_failures(config)
    if pre_read_failures:
        return fail_summary(
            config,
            run_root=run_root,
            blocker_reasons=pre_read_failures,
            status=STATUS_BLOCKED_ARTIFACT,
        )

    try:
        files = tracked_paths(config)
        skipped_count = skipped_untracked_count(config)
    except Exception as exc:  # noqa: BLE001 - CI preflight should fail closed.
        return fail_summary(
            config,
            run_root=run_root,
            blocker_reasons=[f"git_tracked_file_collection_failed:{exc}"],
            status=STATUS_FAIL,
        )

    guard_id = guard_run_id(config.preflight_run_id)
    guard_output_dir = run_root / "guard_runs"
    guard_config = guard.GuardConfig(
        guard_run_id=guard_id,
        output_dir=guard_output_dir,
        files=tuple(files),
        manifest=config.manifest,
        snapshot=config.snapshot,
        pr_range=config.pr_range,
        expected_root_base=config.expected_root_base,
        allow_overwrite=config.allow_overwrite,
    )
    try:
        with redirect_stdout(io.StringIO()):
            guard_summary = guard.run_guard(guard_config)
    except Exception as exc:  # noqa: BLE001 - wrapper must surface structured failure.
        return fail_summary(
            config,
            run_root=run_root,
            blocker_reasons=[f"v3_6ae_guard_failed:{exc}"],
            scanned_tracked_file_count=len(files),
            skipped_count=skipped_count,
            status=STATUS_FAIL,
        )

    guard_summary_path = guard_output_dir / guard_id / "summary.json"
    preflight_status = status_from_guard(
        str(guard_summary.get("stack_guard_status", "")),
        pre_read_failures,
    )
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "scanned_tracked_file_count": len(files),
            "skipped_untracked_count": skipped_count,
            "checked_pr_count": int(guard_summary.get("checked_pr_count", 0) or 0),
            "guard_run_id": guard_id,
            "guard_summary_path": str(guard_summary_path),
            "guard_summary_sha256": sha256_file(guard_summary_path)
            if guard_summary_path.exists()
            else "",
            "artifact_boundary_status": guard_summary.get("artifact_boundary_status", "clean"),
            "claim_boundary_status": guard_summary.get("claim_boundary_status", "clean"),
            "maturity_gate_status": guard_summary.get("maturity_gate_status", "clean"),
            "direct_llm_boundary_status": guard_summary.get("direct_llm_boundary_status", "clean"),
            "preflight_status": preflight_status,
            "ready_for_human_merge_review": preflight_status == STATUS_CLEAN,
            "blocker_reasons": list(guard_summary.get("blocker_reasons", [])),
        }
    )
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-run-id", default=default_run_id())
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--tracked-only", action="store_true", default=True)
    parser.add_argument("--pathspec", action="append", default=[])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--pr-range", default="36-46")
    parser.add_argument("--expected-root-base", default="main")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("/tmp/gotra_v3_6af_ci_stack_boundary_preflight/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> PreflightConfig:
    pathspecs = tuple(args.pathspec or DEFAULT_PATHSPECS)
    return PreflightConfig(
        preflight_run_id=str(args.preflight_run_id),
        output_root=args.output_root,
        repo_root=args.repo_root,
        tracked_only=bool(args.tracked_only),
        pathspecs=pathspecs,
        manifest=args.manifest,
        snapshot=args.snapshot,
        pr_range=str(args.pr_range),
        expected_root_base=str(args.expected_root_base),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_preflight(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI preflight should fail closed.
        print(f"CI stack boundary preflight failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("preflight_status") == STATUS_CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
