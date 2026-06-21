from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts import baseline_v3_6ag_ci_changed_files_preflight as adoption
from scripts import baseline_v3_6af_ci_stack_boundary_preflight as preflight


def test_changed_file_helper_clean_fixture_is_wired_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "docs/historical_stage8.md", "This historical tracked file is not changed.")
    _commit_all(repo, "base")
    base = _head(repo)
    _write(
        repo,
        "docs/good.md",
        "engineering/local only; v3_7_allowed=false; direct_llm_parametric_memory_control is not a clean no-future baseline.",
    )
    _commit_all(repo, "head")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["ci_integration_status"] == adoption.STATUS_WIRED
    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 1
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_allowed"] is False


def test_helper_scans_only_changed_files_not_historical_tree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "docs/STAGE8_historical.md", "Tracked historical path should not be scanned.")
    _write(repo, "docs/good.md", "engineering/local only; v3_7_allowed=false.")
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, "docs/good.md", "engineering/local only; v3_7_allowed=false; updated.")
    _commit_all(repo, "head")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base, allow_overwrite=False))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 1


def test_helper_uses_merge_base_pr_delta_not_base_tip_diff(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "docs/historical_bad.md", "This is OOS evidence and public proof.")
    _write(repo, "docs/base.md", "engineering/local only; v3_7_allowed=false.")
    _commit_all(repo, "root")
    root_branch = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    subprocess.run(["git", "-C", str(repo), "checkout", "--quiet", "-b", "feature"], check=True)
    _write(repo, "docs/pr_only.md", "engineering/local only; v3_7_allowed=false.")
    _commit_all(repo, "feature")
    head = _head(repo)
    subprocess.run(["git", "-C", str(repo), "checkout", "--quiet", root_branch], check=True)
    (repo / "docs" / "historical_bad.md").unlink()
    _commit_all(repo, "base deletes historical")
    base_tip = _head(repo)
    subprocess.run(["git", "-C", str(repo), "checkout", "--quiet", "feature"], check=True)

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base_tip, head_sha=head))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 1


def test_deleted_changed_file_is_skipped(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "docs/old.md", "v3.7 verdict ready")
    _commit_all(repo, "base")
    base = _head(repo)
    (repo / "docs" / "old.md").unlink()
    _commit_all(repo, "delete")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 0
    assert summary["skipped_deleted_count"] == 1


def test_gitlink_changed_file_is_skipped(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "update-index",
            "--add",
            "--cacheinfo",
            "160000,0123456789012345678901234567890123456789,engine/ksana",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "gitlink"], check=True)

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 0
    assert summary["skipped_gitlink_count"] == 1


def test_non_file_changed_entry_is_skipped(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    os.symlink("missing-target", repo / "broken_link.md")
    subprocess.run(["git", "-C", str(repo), "add", "broken_link.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "broken symlink"], check=True)

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 0
    assert summary["skipped_non_file_count"] == 1


def test_symlink_with_existing_target_is_skipped_without_scanning_target(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, "docs/target.md", "This is OOS evidence and public proof.")
    os.symlink("target.md", repo / "docs" / "link.md")
    subprocess.run(["git", "-C", str(repo), "add", "docs/link.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "symlink"], check=True)

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 0
    assert summary["skipped_non_file_count"] == 1


def test_changed_forbidden_artifact_path_blocks_nonzero(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, "data/backtest/runs/raw.json", "This content must not be needed for blocking.")
    _commit_all(repo, "forbidden")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"


def test_tracked_env_example_placeholder_is_allowed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, ".env.example", "OPENAI_API_KEY=your-key-here\n")
    _commit_all(repo, "env example")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 1


def test_tracked_env_example_with_secret_like_value_blocks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    secret_like = "sk-" + "1234567890abcdefghijklmnop"
    _write(repo, ".env.example", f"OPENAI_API_KEY={secret_like}\n")
    _commit_all(repo, "env example secret")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"
    assert any("secret_like_value" in reason for reason in summary["blocker_reasons"])


def test_real_env_file_still_blocks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, ".env", "OPENAI_API_KEY=placeholder\n")
    _commit_all(repo, "real env")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"


def test_changed_oos_public_overclaim_blocks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, "docs/bad.md", "This is OOS evidence and public proof.")
    _commit_all(repo, "overclaim")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_test_fixture_overclaim_text_is_not_scanned_as_claim_boundary(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, "tests/test_fixture.py", "BAD = 'This is OOS evidence and public proof.'\n")
    _commit_all(repo, "test fixture")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["claim_boundary_status"] == "clean"
    assert summary["changed_file_count"] == 1
    assert summary["scanned_file_count"] == 1


def test_changed_v3_7_verdict_blocks_maturity_gate(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(repo, "docs/bad.md", "v3.7 verdict ready\n30D forward-live verdict pass")
    _commit_all(repo, "maturity")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_status"] == "blocked"


def test_changed_safe_v3_7_and_direct_llm_caveat_is_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_all(repo, "base")
    base = _head(repo)
    _write(
        repo,
        "docs/good.md",
        "v3_7_allowed=false; direct_llm_parametric_memory_control is not a clean no-future baseline.",
    )
    _commit_all(repo, "good")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base))

    assert summary["preflight_status"] == preflight.STATUS_CLEAN
    assert summary["direct_llm_boundary_status"] == "clean"
    assert summary["maturity_gate_status"] == "clean"


def test_workflow_contains_safe_pull_request_step() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8",
    )

    assert "GOTRA changed-file boundary preflight" in workflow
    assert "github.event_name == 'pull_request'" in workflow
    assert "baseline_v3_6ag_ci_changed_files_preflight.py" in workflow
    assert "--base-sha \"$BASE_SHA\"" in workflow
    assert "--head-sha \"$HEAD_SHA\"" in workflow


def test_duplicate_run_id_does_not_overwrite_existing_outputs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "docs/good.md", "engineering/local only; v3_7_allowed=false.")
    _commit_all(repo, "base")
    base = _head(repo)
    run_root = tmp_path / "runs" / "baseline_v3_6ag_ci_changed_files_preflight_unit"
    run_root.mkdir(parents=True)
    sentinel = run_root / "summary.json"
    sentinel.write_text("sentinel\n", encoding="utf-8")

    summary = adoption.run_adoption(_config(tmp_path, repo, base_sha=base, allow_overwrite=False))

    assert summary["preflight_status"] == preflight.STATUS_FAIL
    assert summary["blocker_reasons"] == ["output_run_id_exists"]
    assert sentinel.read_text(encoding="utf-8") == "sentinel\n"


def _config(
    tmp_path: Path,
    repo: Path,
    *,
    base_sha: str,
    head_sha: str = "HEAD",
    allow_overwrite: bool = True,
) -> adoption.AdoptionConfig:
    return adoption.AdoptionConfig(
        ci_adoption_run_id="baseline_v3_6ag_ci_changed_files_preflight_unit",
        output_root=tmp_path / "runs",
        repo_root=repo,
        base_sha=base_sha,
        head_sha=head_sha,
        allow_overwrite=allow_overwrite,
        workflow_wired=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    return repo


def _write(repo: Path, relative_path: str, text: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "--allow-empty", "-m", message], check=True)


def _head(repo: Path) -> str:
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
