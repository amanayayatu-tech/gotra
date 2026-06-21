from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import baseline_v3_6ak_live_stack_merge_readiness_snapshot as snapshot


def test_clean_stack_36_to_51_is_ready_for_user_merge_review(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, _clean_snapshot())

    summary = snapshot.run_snapshot(_config(tmp_path, path))

    assert summary["stack_merge_readiness_status"] == snapshot.STATUS_READY
    assert summary["ready_for_user_merge_review"] is True
    assert summary["auto_merge_executed"] is False
    assert summary["v3_7_allowed"] is False
    assert summary["actual_30d_readiness_status"] == snapshot.ACTUAL_30D_READINESS_STATUS
    assert summary["pr_numbers"] == list(range(36, 52))
    assert summary["top_pr_number"] == 51
    assert summary["top_head_sha"] == "sha-51"
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_active_p2_blocks_user_merge_review(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][-1]["reviewThreads"] = [
        {"isResolved": False, "isOutdated": False, "comments": [{"body": "P2: blocker"}]}
    ]
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.run_snapshot(_config(tmp_path, path, suffix="p2"))

    assert summary["stack_merge_readiness_status"] == snapshot.STATUS_BLOCKED_REVIEW
    assert summary["ready_for_user_merge_review"] is False
    assert summary["active_p1_p2_count"] == 1


def test_merged_stack_36_to_51_is_closeout_not_merge_review(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, _merged_snapshot(), suffix="merged")

    summary = snapshot.run_snapshot(_config(tmp_path, path, suffix="merged"))

    assert summary["stack_merge_readiness_status"] == snapshot.STATUS_MERGED_TO_MAIN
    assert summary["stack_closeout_status"] == "merged_to_main"
    assert summary["stack_topology_status"] == "merged_to_main"
    assert summary["maturity_gate_status"] == snapshot.ACTUAL_30D_READINESS_STATUS
    assert summary["ci_boundary_preflight_status"] == "post_merge_not_applicable"
    assert summary["ci_adoption_status"] == "post_merge_not_applicable"
    assert summary["stack_already_merged_to_main"] is True
    assert summary["ready_for_user_merge_review"] is False
    assert summary["auto_merge_executed"] is False
    assert summary["auto_merge_executed_by_worker"] is False
    assert summary["merged_pr_count"] == 16
    assert summary["merge_commit_count"] == 16
    assert summary["main_after_merge_commit"] == "merge-51"
    assert summary["merged_prs"][0]["number"] == 36
    assert summary["merged_prs"][-1]["number"] == 51
    assert summary["blocker_reasons"] == []
    assert summary["actual_30d_readiness_status"] == snapshot.ACTUAL_30D_READINESS_STATUS
    assert summary["v3_7_allowed"] is False


def test_forbidden_artifact_path_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["files"] = {"nodes": [{"path": "data/backtest/runs/raw.json"}]}
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.run_snapshot(_config(tmp_path, path, suffix="artifact"))

    assert summary["stack_merge_readiness_status"] == snapshot.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, _clean_snapshot())

    summary = snapshot.run_snapshot(_config(tmp_path, path, suffix="digest"))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(Path(summary["summary_path"]))
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def _config(tmp_path: Path, path: Path, *, suffix: str = "unit") -> snapshot.SnapshotConfig:
    return snapshot.SnapshotConfig(
        snapshot_run_id=f"{snapshot.RUN_ID_PREFIX}{suffix}",
        output_dir=tmp_path / f"runs_{suffix}",
        snapshot=path,
    )


def _write_snapshot(tmp_path: Path, payload: dict[str, object], *, suffix: str = "unit") -> Path:
    path = tmp_path / f"snapshot_{suffix}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_snapshot() -> dict[str, object]:
    branches = [
        (36, "Add actual forward-live maturity monitor", "main", "codex/gotra-v3-6s-actual-maturity-monitor-20260621"),
        (37, "Add forward-live maturity monitor operations ledger", "codex/gotra-v3-6s-actual-maturity-monitor-20260621", "codex/gotra-v3-6t-forward-live-monitor-ops-20260621"),
        (38, "Add parallel fast-feedback routes", "codex/gotra-v3-6t-forward-live-monitor-ops-20260621", "codex/gotra-v3-6u-v-parallel-feedback-routes-20260621"),
        (39, "Add evidence package decision dashboard", "codex/gotra-v3-6u-v-parallel-feedback-routes-20260621", "codex/gotra-v3-6x-evidence-package-dashboard-20260621"),
        (40, "Add short-horizon first-capture canary", "codex/gotra-v3-6x-evidence-package-dashboard-20260621", "codex/gotra-v3-6y-short-horizon-first-capture-20260621"),
        (41, "Add short-horizon outcome recheck", "codex/gotra-v3-6y-short-horizon-first-capture-20260621", "codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621"),
        (42, "Add stack evidence boundary audit", "codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621", "codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621"),
        (43, "Add evidence claim boundary scanner", "codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621", "codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621"),
        (44, "Add stack merge-readiness packet", "codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621", "codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621"),
        (45, "Add live stack readiness snapshot", "codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621", "codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621"),
        (46, "Add continuous stack boundary guard", "codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621", "codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621"),
        (47, "Add CI stack boundary preflight", "codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621", "codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621"),
        (48, "Wire CI boundary preflight workflow", "codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621", "codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621"),
        (49, "Refresh live stack readiness", "codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621", "codex/gotra-v3-6ah-live-stack-refresh-20260621"),
        (50, "Add ksana cognitive-lift audit", "codex/gotra-v3-6ah-live-stack-refresh-20260621", "codex/gotra-v3-6ai-ksana-cognitive-lift-audit-20260621"),
        (51, "Add cognitive-lift fixture comparison", "codex/gotra-v3-6ai-ksana-cognitive-lift-audit-20260621", "codex/gotra-v3-6aj-cognitive-lift-fixture-comparison-20260621"),
    ]
    return {
        "schema": "gotra.test.live_stack_merge_readiness.v1",
        "repo": "amanayayatu-tech/gotra",
        "conflict_dry_run_status": "CLEAN",
        "readiness_status": "DATA_NOT_MATURED",
        "pull_requests": [
            {
                "number": number,
                "title": title,
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
                "changed_files": [
                    f"docs/GOTRA_V3_6_{number}_RESULT.md",
                    f"scripts/baseline_v3_6_{number}.py",
                ],
                "body": (
                    "engineering/local only; no OOS/science/public/trading claim is made; "
                    "direct_llm_parametric_memory_control is not a clean no-future baseline; "
                    "v3_7_allowed=false."
                ),
            }
            for number, title, base, head in branches
        ],
    }


def _merged_snapshot() -> dict[str, object]:
    payload = json.loads(json.dumps(_clean_snapshot()))
    for pr in payload["pull_requests"]:
        number = int(pr["number"])
        pr["baseRefName"] = "main"
        pr["state"] = "MERGED"
        pr["mergeStateStatus"] = ""
        pr["mergedAt"] = f"2026-06-21T12:{number - 6:02d}:00Z"
        pr["mergeCommit"] = {"oid": f"merge-{number}"}
    return payload
