#!/usr/bin/env python3
"""GOTRA v3.6AG changed-files CI boundary preflight adoption helper."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402
from scripts import baseline_v3_6af_ci_stack_boundary_preflight as preflight  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_6ag.ci_changed_files_preflight_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ag.changed_files_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ag_ci_changed_files_preflight_"
SCRIPT_VERSION = "v3.6ag-20260621"

STATUS_WIRED = "CI_PREFLIGHT_WIRED"
STATUS_DOCUMENTED_ONLY = "CI_PREFLIGHT_DOCUMENTED_ONLY"
STATUS_BLOCKED_UNSAFE = "BLOCKED_CI_CONFIG_UNSAFE"

EVIDENCE_LAYER = "engineering_ci_boundary_preflight_adoption"
TEXT_SCAN_SUFFIXES = {".md", ".markdown", ".rst", ".txt", ".yaml", ".yml"}
SYMLINK_MODE = "120000"
GITLINK_MODE = "160000"
ENV_EXAMPLE_PATH = ".env.example"
SECRET_LIKE_PATTERNS = (
    ("openai_key", r"sk-[A-Za-z0-9_-]{20,}"),
    ("generic_secret_assignment", r"(?i)\b(api[_-]?key|secret|token|password)\s*=\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
)


@dataclass(frozen=True)
class AdoptionConfig:
    ci_adoption_run_id: str
    output_root: Path
    repo_root: Path = Path.cwd()
    base_sha: str = ""
    head_sha: str = "HEAD"
    base_ref: str = ""
    head_ref: str = ""
    allow_overwrite: bool = False
    workflow_wired: bool = True


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"ci_adoption_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("ci_adoption_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def resolve_ref(config: AdoptionConfig, *, sha: str, ref: str, fallback: str) -> str:
    value = sha or ref or fallback
    if not value:
        raise ValueError("base/head ref is required")
    return value


def changed_files(config: AdoptionConfig) -> list[ChangedFile]:
    base = resolve_ref(config, sha=config.base_sha, ref=config.base_ref, fallback="HEAD~1")
    head = resolve_ref(config, sha=config.head_sha, ref=config.head_ref, fallback="HEAD")
    merge_base = git_output(config.repo_root, ["merge-base", base, head]).strip()
    output = git_output(
        config.repo_root,
        ["diff", "--name-status", "--no-renames", "-z", merge_base, head, "--"],
    )
    tokens = [token for token in output.split("\0") if token]
    files: list[ChangedFile] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        if index + 1 >= len(tokens):
            raise ValueError(f"malformed git diff --name-status output at token {index}")
        path = tokens[index + 1]
        files.append(ChangedFile(path=path, status=status))
        index += 2
    return files


def git_mode(repo_root: Path, path: str) -> str:
    output = git_output(repo_root, ["ls-files", "--stage", "--", path])
    if not output.strip():
        return ""
    return output.split(" ", 1)[0]


def is_env_example(relative_path: str) -> bool:
    return relative_path.replace("\\", "/") == ENV_EXAMPLE_PATH


def has_secret_like_value(text: str) -> bool:
    return any(re.search(pattern, text) for _, pattern in SECRET_LIKE_PATTERNS)


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def should_scan_text(relative_path: str) -> bool:
    if is_env_example(relative_path):
        return True
    path = Path(relative_path)
    if path.parts and path.parts[0] == "tests":
        return False
    if path.suffix.lower() in TEXT_SCAN_SUFFIXES:
        return True
    return False


def manifest_entries(config: AdoptionConfig, changes: list[ChangedFile]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    counts: dict[str, Any] = {
        "skipped_deleted_count": 0,
        "skipped_gitlink_count": 0,
        "skipped_non_file_count": 0,
        "local_blocker_reasons": [],
    }
    for change in changes:
        if change.status.startswith("D"):
            counts["skipped_deleted_count"] += 1
            continue
        mode = git_mode(config.repo_root, change.path)
        if mode == GITLINK_MODE:
            counts["skipped_gitlink_count"] += 1
            continue
        if mode == SYMLINK_MODE:
            counts["skipped_non_file_count"] += 1
            continue
        full_path = config.repo_root / change.path
        if not full_path.is_file() or full_path.is_symlink():
            counts["skipped_non_file_count"] += 1
            continue
        if claim_scan.forbidden_path(change.path) and not is_env_example(change.path):
            entries.append({"path": change.path, "status": change.status})
            continue
        if not should_scan_text(change.path):
            entries.append({"path": change.path, "status": change.status})
            continue
        text = safe_read_text(full_path)
        if is_env_example(change.path) and has_secret_like_value(text):
            counts["local_blocker_reasons"].append(
                f"artifact_boundary:{change.path}:secret_like_value",
            )
        entries.append(
            {
                "path": change.path,
                "status": change.status,
                "text": text,
            }
        )
    return entries, counts


def write_manifest(*, run_root: Path, entries: list[dict[str, Any]]) -> Path:
    manifest_path = run_root / "changed_files_manifest.json"
    payload = {
        "schema": MANIFEST_SCHEMA,
        "files": entries,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def preflight_run_id(adoption_run_id: str) -> str:
    suffix = adoption_run_id.removeprefix(RUN_ID_PREFIX)
    return f"{preflight.RUN_ID_PREFIX}v3_6ag_{suffix}"


def ci_integration_status(*, workflow_wired: bool) -> str:
    return STATUS_WIRED if workflow_wired else STATUS_DOCUMENTED_ONLY


def base_summary(config: AdoptionConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "ci_adoption_run_id": config.ci_adoption_run_id,
        "ci_adoption_run_root": str(run_root),
        "ci_adoption_timestamp_utc": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "repo_root": str(config.repo_root),
        "base_sha": config.base_sha,
        "head_sha": config.head_sha,
        "base_ref": config.base_ref,
        "head_ref": config.head_ref,
        "ci_integration_status": ci_integration_status(workflow_wired=config.workflow_wired),
        "changed_file_count": 0,
        "scanned_file_count": 0,
        "skipped_deleted_count": 0,
        "skipped_gitlink_count": 0,
        "skipped_non_file_count": 0,
        "manifest_path": "",
        "manifest_sha256": "",
        "preflight_summary_path": "",
        "preflight_summary_sha256": "",
        "preflight_status": preflight.STATUS_CLEAN,
        "artifact_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "maturity_gate_status": "clean",
        "direct_llm_boundary_status": "clean",
        "workflow_files_changed": True,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "auto_merge_executed": False,
        "v3_7_allowed": False,
        "evidence_layer": EVIDENCE_LAYER,
        "direct_llm_interpretation": preflight.DIRECT_LLM_INTERPRETATION,
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
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def blocked_summary(
    config: AdoptionConfig,
    *,
    run_root: Path,
    reasons: list[str],
    status: str = STATUS_BLOCKED_UNSAFE,
    write: bool = True,
) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "ci_integration_status": status,
            "preflight_status": preflight.STATUS_FAIL,
            "blocker_reasons": reasons,
        }
    )
    if write:
        write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_adoption(config: AdoptionConfig) -> dict[str, Any]:
    validate_run_id(config.ci_adoption_run_id)
    run_root = config.output_root / config.ci_adoption_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_summary(
            config,
            run_root=run_root,
            reasons=["output_run_id_exists"],
            write=False,
        )
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    try:
        changes = changed_files(config)
        entries, counts = manifest_entries(config, changes)
        manifest_path = write_manifest(run_root=run_root, entries=entries)
        wrapper_run_id = preflight_run_id(config.ci_adoption_run_id)
        wrapper_config = preflight.PreflightConfig(
            preflight_run_id=wrapper_run_id,
            output_root=run_root / "preflight_runs",
            repo_root=config.repo_root,
            pathspecs=(),
            manifest=manifest_path,
            allow_overwrite=config.allow_overwrite,
        )
        with redirect_stdout(io.StringIO()):
            preflight_summary = preflight.run_preflight(wrapper_config)
    except Exception as exc:  # noqa: BLE001 - CI adoption should fail closed.
        return blocked_summary(
            config,
            run_root=run_root,
            reasons=[f"ci_changed_files_preflight_failed:{exc}"],
        )

    preflight_summary_path = Path(str(preflight_summary.get("preflight_run_root", ""))) / "summary.json"
    local_blocker_reasons = list(counts.get("local_blocker_reasons", []))
    preflight_status = preflight_summary.get("preflight_status", preflight.STATUS_FAIL)
    artifact_boundary_status = preflight_summary.get("artifact_boundary_status", "clean")
    if local_blocker_reasons:
        preflight_status = preflight.STATUS_BLOCKED_ARTIFACT
        artifact_boundary_status = "blocked"
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "changed_file_count": len(changes),
            "scanned_file_count": len(entries),
            "skipped_deleted_count": counts["skipped_deleted_count"],
            "skipped_gitlink_count": counts["skipped_gitlink_count"],
            "skipped_non_file_count": counts["skipped_non_file_count"],
            "manifest_path": str(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "preflight_summary_path": str(preflight_summary_path),
            "preflight_summary_sha256": sha256_file(preflight_summary_path)
            if preflight_summary_path.exists()
            else "",
            "preflight_status": preflight_status,
            "artifact_boundary_status": artifact_boundary_status,
            "claim_boundary_status": preflight_summary.get("claim_boundary_status", "clean"),
            "maturity_gate_status": preflight_summary.get("maturity_gate_status", "clean"),
            "direct_llm_boundary_status": preflight_summary.get("direct_llm_boundary_status", "clean"),
            "blocker_reasons": list(preflight_summary.get("blocker_reasons", []))
            + local_blocker_reasons,
        }
    )
    write_outputs(run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ci-adoption-run-id", default=default_run_id())
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="HEAD")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("/tmp/gotra_v3_6ag_ci_changed_files_preflight/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--documented-only", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> AdoptionConfig:
    return AdoptionConfig(
        ci_adoption_run_id=str(args.ci_adoption_run_id),
        output_root=args.output_root,
        repo_root=args.repo_root,
        base_sha=str(args.base_sha),
        head_sha=str(args.head_sha),
        base_ref=str(args.base_ref),
        head_ref=str(args.head_ref),
        allow_overwrite=bool(args.allow_overwrite),
        workflow_wired=not bool(args.documented_only),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_adoption(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed.
        print(f"CI changed-files boundary preflight failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("preflight_status") == preflight.STATUS_CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
