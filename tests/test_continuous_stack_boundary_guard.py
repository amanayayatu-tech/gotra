from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6ae_continuous_stack_boundary_guard as guard


def test_clean_manifest_is_clean_without_provider_or_v3_7(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/good.md",
                "text": (
                    "engineering/local only; historical/internal only; "
                    "not OOS/science/public/trading claim; not investment advice; "
                    "v3_7_allowed=false; "
                    "direct_llm_parametric_memory_control is not a clean no-future baseline."
                ),
            }
        ],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_CLEAN
    assert summary["ready_for_human_merge_review"] is True
    assert summary["auto_merge_executed"] is False
    assert summary["v3_7_allowed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_clean_stack_snapshot_fixture_is_clean(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, [{"path": "docs/good.md", "text": "engineering/local only; v3_7_allowed=false."}])
    snapshot = _write_snapshot(tmp_path, _clean_snapshot())

    summary = guard.run_guard(_config(tmp_path, manifest=manifest, snapshot=snapshot, pr_range="36-37"))

    assert summary["stack_guard_status"] == guard.STATUS_CLEAN
    assert summary["checked_pr_count"] == 2
    assert summary["ready_for_human_merge_review"] is True


def test_forbidden_file_path_blocks_before_read(tmp_path: Path) -> None:
    forbidden = tmp_path / "data" / "backtest" / "runs" / "raw.json"

    summary = guard.run_guard(_config(tmp_path, files=[forbidden]))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"
    assert summary["forbidden_path_count"] == 1


def test_forbidden_manifest_path_blocks_without_reading(tmp_path: Path) -> None:
    forbidden = tmp_path / "data" / "backtest" / "runs" / "manifest.json"

    summary = guard.run_guard(_config(tmp_path, manifest=forbidden))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"


def test_forbidden_snapshot_path_blocks_before_reading(tmp_path: Path) -> None:
    forbidden = tmp_path / "data" / "backtest" / "runs" / "snapshot.json"

    summary = guard.run_guard(_config(tmp_path, snapshot=forbidden, pr_range="36"))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"
    assert summary["snapshot_sha256"] == ""
    assert any("forbidden_snapshot_path" in reason for reason in summary["blocker_reasons"])


def test_oos_public_trading_overclaim_blocks_claim_boundary(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/bad.md", "text": "This is OOS evidence, public proof, and trading advice."}],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"
    assert summary["evidence_overclaim_count"] >= 1


def test_safe_v3_7_sanitization_preserves_other_claims(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/mixed_bad.md",
                "text": "v3.7 not allowed; direct_llm is clean no-future baseline; OOS proof",
            }
        ],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_DIRECT_LLM
    assert summary["direct_llm_boundary_status"] == "blocked"
    assert summary["claim_boundary_status"] == "blocked"


def test_positive_v3_7_and_30d_verdict_claims_block_maturity_gate(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/bad_v37.md",
                "text": "v3.7 allowed: true\nv3.7 verdict ready\n30D forward-live verdict pass",
            }
        ],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_status"] == "blocked"
    assert summary["maturity_gate_bypass_count"] >= 3


def test_spelled_out_30d_verdict_in_snapshot_is_maturity_block(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["body"] = "thirty-day forward-live verdict pass"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = guard.run_guard(_config(tmp_path, snapshot=snapshot, pr_range="36-37"))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_status"] == "blocked"
    assert any("thirty_day_forward_live_verdict" in reason for reason in summary["blocker_reasons"])


def test_explicit_false_v3_7_boundary_lines_are_clean(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/v37_false.md",
                "text": "v3.7 allowed: false\nv3_7_allowed=false\nv3.7 not allowed",
            }
        ],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_CLEAN
    assert summary["maturity_gate_status"] == "clean"


def test_direct_llm_clean_baseline_blocks_direct_boundary(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/direct_bad.md", "text": "direct_llm is clean no-future baseline."}],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_DIRECT_LLM
    assert summary["direct_llm_boundary_status"] == "blocked"


def test_direct_llm_parametric_memory_control_caveat_is_clean(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/direct_good.md",
                "text": "direct_llm_parametric_memory_control is not a clean no-future baseline.",
            }
        ],
    )

    summary = guard.run_guard(_config(tmp_path, manifest=manifest))

    assert summary["stack_guard_status"] == guard.STATUS_CLEAN
    assert summary["direct_llm_boundary_status"] == "clean"


def test_snapshot_evidence_document_forbidden_path_blocks_without_claim_scan(
    tmp_path: Path,
) -> None:
    payload = _clean_snapshot()
    payload["evidence_documents"] = [
        {
            "path": "data/backtest/runs/evidence.md",
            "text": "This is OOS proof and v3.7 verdict ready.",
        }
    ]
    payload["pull_requests"][0]["evidence_documents"] = [
        {
            "path": "data/backtest/runs/pr_evidence.md",
            "text": "direct_llm is clean no-future baseline.",
        }
    ]
    snapshot = _write_snapshot(tmp_path, payload)

    summary = guard.run_guard(_config(tmp_path, snapshot=snapshot, pr_range="36-37"))

    assert summary["stack_guard_status"] == guard.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"
    assert summary["forbidden_path_count"] == 2
    assert summary["evidence_overclaim_count"] == 0
    assert summary["maturity_gate_bypass_count"] == 0
    assert summary["direct_llm_mislabel_count"] == 0


def test_missing_pr_in_requested_range_is_snapshot_incomplete(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, {"pull_requests": [_clean_pr(36, "main", "branch-36")]})

    summary = guard.run_guard(_config(tmp_path, snapshot=snapshot, pr_range="36-37"))

    assert summary["stack_guard_status"] == guard.STATUS_INCOMPLETE
    assert summary["ready_for_human_merge_review"] is False
    assert any("missing_pr_37" in reason for reason in summary["blocker_reasons"])


def test_blocked_status_exits_nonzero(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/bad.md", "text": "v3.7 verdict ready"}],
    )

    exit_code = guard.main(
        [
            "--guard-run-id",
            "baseline_v3_6ae_continuous_stack_boundary_guard_cli",
            "--manifest",
            str(manifest),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 1


def _config(
    tmp_path: Path,
    *,
    manifest: Path | None = None,
    snapshot: Path | None = None,
    files: list[Path] | None = None,
    pr_range: str = "36-45",
) -> guard.GuardConfig:
    return guard.GuardConfig(
        guard_run_id="baseline_v3_6ae_continuous_stack_boundary_guard_unit",
        output_dir=tmp_path / "runs",
        files=tuple(files or ()),
        manifest=manifest,
        snapshot=snapshot,
        pr_range=pr_range,
    )


def _write_manifest(tmp_path: Path, files: list[dict[str, str]]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"files": files}, indent=2), encoding="utf-8")
    return path


def _write_snapshot(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _clean_snapshot() -> dict[str, object]:
    return {
        "schema": "gotra.test.v3_6ae_stack_boundary_snapshot.v1",
        "pull_requests": [
            _clean_pr(36, "main", "branch-36"),
            _clean_pr(37, "branch-36", "branch-37"),
        ],
    }


def _clean_pr(number: int, base: str, head: str) -> dict[str, object]:
    return {
        "number": number,
        "title": f"PR {number}",
        "baseRefName": base,
        "headRefName": head,
        "headRefOid": f"sha-{number}",
        "isDraft": False,
        "mergeStateStatus": "CLEAN",
        "state": "OPEN",
        "statusCheckRollup": [
            {"name": "Python checks", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"name": "Python checks", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ],
        "reviewThreads": [],
        "files": [{"path": f"docs/pr_{number}.md"}],
        "body": (
            "engineering/local only; not OOS/science/public/trading claim; "
            "v3_7_allowed=false; direct_llm_parametric_memory_control."
        ),
    }
