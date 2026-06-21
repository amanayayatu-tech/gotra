from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6ah_live_stack_refresh as refresh


def test_clean_stack_fixture_is_ready_without_v3_7(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, _clean_snapshot())

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_READY
    assert summary["ready_for_human_merge_review"] is True
    assert summary["auto_merge_executed"] is False
    assert summary["v3_7_allowed"] is False
    assert summary["pr_numbers"] == list(range(36, 49))
    assert summary["top_pr_number"] == 48
    assert summary["top_head_sha"] == "sha-48"
    assert summary["ci_boundary_preflight_status"] == refresh.ci_preflight.STATUS_CLEAN
    assert summary["ci_adoption_status"] == refresh.ci_adoption.STATUS_WIRED
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_open_unmerged_prs_do_not_block_refresh(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    for pr in payload["pull_requests"]:
        pr["state"] = "OPEN"
        pr["merged"] = False
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_READY
    assert summary["ready_for_human_merge_review"] is True


def test_active_p2_blocks_refresh(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][12]["reviewThreads"] = [
        {
            "isResolved": False,
            "isOutdated": False,
            "comments": [{"body": "P2: active blocker"}],
        }
    ]
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_REVIEW
    assert summary["active_p1_p2_count"] == 1
    assert summary["ci_adoption_status"] == refresh.ci_adoption.STATUS_WIRED


def test_ci_pending_failed_skipped_cancelled_blocks_refresh(tmp_path: Path) -> None:
    for conclusion in ("", "FAILURE", "SKIPPED", "CANCELLED"):
        payload = _clean_snapshot()
        payload["pull_requests"][2]["statusCheckRollup"][0]["status"] = (
            "IN_PROGRESS" if not conclusion else "COMPLETED"
        )
        payload["pull_requests"][2]["statusCheckRollup"][0]["conclusion"] = conclusion
        path = _write_snapshot(tmp_path, payload, suffix=conclusion or "pending")

        summary = refresh.run_refresh(_config(tmp_path, path, suffix=conclusion or "pending"))

        assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_CI
        assert summary["ready_for_human_merge_review"] is False


def test_draft_pr_blocks_refresh(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][1]["isDraft"] = True
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_TOPOLOGY
    assert any("draft_pr" in reason for reason in summary["blocker_reasons"])


def test_topology_base_chain_break_blocks_refresh(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["baseRefName"] = "old-root"
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_TOPOLOGY
    assert any("root_base_mismatch" in reason for reason in summary["blocker_reasons"])


def test_forbidden_changed_path_blocks_refresh(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["files"] = {
        "nodes": [{"path": "data/backtest/runs/raw.json"}]
    }
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_status"] == "blocked"


def test_overclaim_blocks_claim_boundary(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][3]["body"] = "This is an OOS pass."
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_v3_7_or_30d_verdict_wording_blocks_maturity_gate(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][3]["body"] = "30D forward-live verdict pass."
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_status"] == "blocked"


def test_unmarked_direct_llm_clean_baseline_blocks_direct_boundary(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][3]["body"] = "direct_llm is a clean no-future baseline."
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_DIRECT_LLM
    assert summary["direct_llm_boundary_status"] == "blocked"


def test_ci_preflight_or_adoption_blocked_fixture_blocks_refresh(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["ci_boundary_preflight_status"] = "BLOCKED_CI_PREFLIGHT"
    path = _write_snapshot(tmp_path, payload)

    summary = refresh.run_refresh(_config(tmp_path, path))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_CI_PREFLIGHT
    assert any("ci_preflight" in reason for reason in summary["blocker_reasons"])

    payload = _clean_snapshot()
    payload["ci_adoption_status"] = "BLOCKED_CI_CONFIG_UNSAFE"
    path = _write_snapshot(tmp_path, payload, suffix="adoption")

    summary = refresh.run_refresh(_config(tmp_path, path, suffix="adoption"))

    assert summary["live_stack_refresh_status"] == refresh.STATUS_BLOCKED_CI_PREFLIGHT
    assert any("ci_adoption" in reason for reason in summary["blocker_reasons"])


def _config(tmp_path: Path, path: Path, *, suffix: str = "unit") -> refresh.RefreshConfig:
    safe_suffix = "".join(character for character in suffix.lower() if character.isalnum() or character in "_-")
    return refresh.RefreshConfig(
        refresh_run_id=f"baseline_v3_6ah_live_stack_refresh_{safe_suffix}",
        snapshot=path,
        output_dir=tmp_path / f"runs_{safe_suffix}",
    )


def _write_snapshot(tmp_path: Path, payload: dict[str, object], *, suffix: str = "unit") -> Path:
    path = tmp_path / f"snapshot_{suffix}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _clean_snapshot() -> dict[str, object]:
    branches = [
        (36, "Add actual forward-live maturity monitor", "main", "codex/gotra-v3-6s-actual-maturity-monitor-20260621"),
        (
            37,
            "Add forward-live maturity monitor operations ledger",
            "codex/gotra-v3-6s-actual-maturity-monitor-20260621",
            "codex/gotra-v3-6t-forward-live-monitor-ops-20260621",
        ),
        (
            38,
            "Add parallel fast-feedback routes",
            "codex/gotra-v3-6t-forward-live-monitor-ops-20260621",
            "codex/gotra-v3-6u-v-parallel-feedback-routes-20260621",
        ),
        (
            39,
            "Add evidence package decision dashboard",
            "codex/gotra-v3-6u-v-parallel-feedback-routes-20260621",
            "codex/gotra-v3-6x-evidence-package-dashboard-20260621",
        ),
        (
            40,
            "Add short-horizon first-capture canary",
            "codex/gotra-v3-6x-evidence-package-dashboard-20260621",
            "codex/gotra-v3-6y-short-horizon-first-capture-20260621",
        ),
        (
            41,
            "Add short-horizon outcome recheck",
            "codex/gotra-v3-6y-short-horizon-first-capture-20260621",
            "codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621",
        ),
        (
            42,
            "Add stack evidence boundary audit",
            "codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621",
            "codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621",
        ),
        (
            43,
            "Add evidence claim boundary scanner",
            "codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621",
            "codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621",
        ),
        (
            44,
            "Add stack merge-readiness packet",
            "codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621",
            "codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621",
        ),
        (
            45,
            "Add live stack readiness snapshot",
            "codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621",
            "codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621",
        ),
        (
            46,
            "Add continuous stack boundary guard",
            "codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621",
            "codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621",
        ),
        (
            47,
            "Add CI stack boundary preflight",
            "codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621",
            "codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621",
        ),
        (
            48,
            "Wire CI boundary preflight workflow",
            "codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621",
            "codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621",
        ),
    ]
    return {
        "schema": "gotra.test.live_stack_refresh.v1",
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
                    {
                        "name": "Python checks",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                    {
                        "name": "Python checks",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                ],
                "reviewThreads": [],
                "changed_files": [
                    f"docs/GOTRA_V3_6{number}_RESULT.md",
                    f"scripts/baseline_v3_6{number}.py",
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
