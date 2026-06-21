from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import baseline_v3_6af_ci_stack_boundary_preflight as preflight


def test_tracked_only_clean_fixture_is_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(
        repo,
        "docs/good.md",
        (
            "engineering/local only; not OOS/science/public/trading claim; "
            "v3_7_allowed=false; "
            "direct_llm_parametric_memory_control is not a clean no-future baseline."
        ),
    )

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=("docs/",)))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["scanned_tracked_file_count"] == 1
    assert summary["skipped_untracked_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_untracked_forbidden_file_is_skipped_in_tracked_only_mode(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "docs/good.md", "engineering/local only; v3.7 allowed: false.")
    forbidden = repo / "data" / "backtest" / "runs" / "raw.json"
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_text("This is OOS evidence and v3.7 verdict ready.", encoding="utf-8")

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=(".",)))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["scanned_tracked_file_count"] == 1
    assert summary["skipped_untracked_count"] == 1
    assert summary["artifact_boundary_status"] == "clean"


def test_tracked_forbidden_path_blocks_without_content_scan(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "data/backtest/runs/raw.json", "benign text would still be forbidden")

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=(".",)))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"
    assert any("data/backtest/runs/raw.json" in reason for reason in summary["blocker_reasons"])


def test_forbidden_manifest_path_blocks_before_reading(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    manifest = repo / "data" / "backtest" / "runs" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("not json; should not be read", encoding="utf-8")

    summary = preflight.run_preflight(
        _config(tmp_path, repo, manifest=manifest, pathspecs=("docs/",)),
    )

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"
    assert any("forbidden_manifest_path" in reason for reason in summary["blocker_reasons"])


def test_manifest_forbidden_entry_blocks_artifact(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    manifest = _write_manifest(
        repo,
        [{"path": "data/backtest/runs/summary.md", "text": "engineering/local only"}],
    )

    summary = preflight.run_preflight(_config(tmp_path, repo, manifest=manifest, pathspecs=()))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"


def test_tracked_oos_evidence_blocks_claim_boundary(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "docs/bad.md", "This is OOS evidence and public proof.")

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=("docs/",)))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_tracked_v3_7_verdict_blocks_maturity_gate(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "docs/bad.md", "v3.7 verdict ready\n30D forward-live verdict pass")

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=("docs/",)))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_status"] == "blocked"


def test_safe_false_v3_7_boundary_is_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "docs/good.md", "v3.7 allowed: false\nv3_7_allowed=false\nv3.7 not allowed")

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=("docs/",)))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["maturity_gate_status"] == "clean"


def test_unmarked_direct_llm_clean_baseline_blocks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "docs/direct_bad.md", "direct_llm is clean no-future baseline.")

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=("docs/",)))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_DIRECT_LLM
    assert summary["direct_llm_boundary_status"] == "blocked"


def test_direct_llm_parametric_memory_control_caveat_is_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(
        repo,
        "docs/direct_good.md",
        "direct_llm_parametric_memory_control is not a clean no-future baseline.",
    )

    summary = preflight.run_preflight(_config(tmp_path, repo, pathspecs=("docs/",)))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["direct_llm_boundary_status"] == "clean"


def test_wrapper_blocked_status_exits_nonzero(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _track(repo, "docs/bad.md", "v3.7 verdict ready")

    exit_code = preflight.main(
        [
            "--preflight-run-id",
            "baseline_v3_6af_ci_stack_boundary_preflight_cli",
            "--repo-root",
            str(repo),
            "--pathspec",
            "docs/",
            "--output-root",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 1


def _config(
    tmp_path: Path,
    repo: Path,
    *,
    pathspecs: tuple[str, ...] = ("docs/",),
    manifest: Path | None = None,
    snapshot: Path | None = None,
) -> preflight.PreflightConfig:
    return preflight.PreflightConfig(
        preflight_run_id="baseline_v3_6af_ci_stack_boundary_preflight_unit",
        output_root=tmp_path / "runs",
        repo_root=repo,
        pathspecs=pathspecs,
        manifest=manifest,
        snapshot=snapshot,
        allow_overwrite=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    return repo


def _track(repo: Path, relative_path: str, text: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", relative_path], check=True)
    return path


def _write_manifest(repo: Path, files: list[dict[str, str]]) -> Path:
    path = repo / "manifest.json"
    path.write_text(json.dumps({"files": files}, indent=2), encoding="utf-8")
    return path
