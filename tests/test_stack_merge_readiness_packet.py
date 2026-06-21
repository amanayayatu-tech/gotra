from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6ac_stack_merge_readiness_packet as packet


def test_clean_stack_fixture_is_ready_for_human_merge_without_v3_7(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, _clean_snapshot())

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_READY
    assert summary["ready_for_human_merge"] is True
    assert summary["auto_merge_executed"] is False
    assert summary["v3_7_allowed"] is False
    assert summary["maturity_boundary_status"] == packet.STATUS_DATA_NOT_MATURED_MONITOR_ONLY
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert len(summary["expected_merge_order"]) == 8


def test_open_unmerged_prs_do_not_block_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    for pr in payload["pull_requests"]:
        pr["state"] = "OPEN"
        pr["merged"] = False
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_READY
    assert summary["ready_for_human_merge"] is True


def test_ci_pending_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][2]["statusCheckRollup"][0]["status"] = "IN_PROGRESS"
    payload["pull_requests"][2]["statusCheckRollup"][0]["conclusion"] = ""
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_CI
    assert summary["ready_for_human_merge"] is False


def test_graphql_status_check_rollup_contexts_nodes_are_flattened(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    for pr in payload["pull_requests"]:
        pr["statusCheckRollup"] = {
            "contexts": {
                "nodes": [
                    {
                        "name": "Python checks",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    }
                ]
            }
        }
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_READY
    assert summary["ci_status"] == "clean"
    assert summary["ci_success_count"] == 8


def test_active_p2_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][4]["reviewThreads"] = [
        {
            "isResolved": False,
            "isOutdated": False,
            "comments": [{"body": "![P2 Badge] active blocker"}],
        }
    ]
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_REVIEW
    assert summary["active_p1_p2_count"] == 1


def test_topology_break_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["baseRefName"] = "old-root"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_TOPOLOGY
    assert any("root_base_mismatch" in reason for reason in summary["blocking_reasons"])


def test_draft_pr_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][1]["isDraft"] = True
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_TOPOLOGY
    assert any("draft_pr" in reason for reason in summary["blocking_reasons"])
    assert summary["ready_for_human_merge"] is False


def test_forbidden_artifact_path_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["files"] = {
        "nodes": [{"path": "data/backtest/runs/raw.json"}]
    }
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_violation_count"] == 1


def test_claim_boundary_overclaim_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][3]["body"] = "This is an OOS pass."
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_violation_count"] >= 1


def test_conflict_fixture_blocks_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["conflict_dry_run_status"] = "BLOCKED_CONFLICT"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_CONFLICT
    assert summary["conflict_dry_run_status"] == packet.CONFLICT_BLOCKED


def test_dirty_merge_state_status_blocks_as_conflict(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][2]["mergeStateStatus"] = "DIRTY"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_CONFLICT
    assert summary["conflict_dry_run_status"] == packet.CONFLICT_BLOCKED
    assert any("merge_state_status:dirty" in reason for reason in summary["blocking_reasons"])


def test_merge_tree_delete_modify_output_is_conflict() -> None:
    output = "removed in local\\n  their-version.txt\\n"

    assert packet.merge_tree_output_has_conflict(output) is True
    assert packet.merge_tree_output_has_conflict("merged cleanly") is False


def test_unknown_conflict_requires_human_and_is_not_ready(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["conflict_dry_run_status"] = "UNKNOWN_REQUIRES_HUMAN"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_BLOCKED_CONFLICT
    assert summary["conflict_dry_run_status"] == packet.CONFLICT_UNKNOWN
    assert summary["ready_for_human_merge"] is False


def test_data_not_matured_is_boundary_note_not_merge_blocker(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["readiness_status"] = "DATA_NOT_MATURED"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = packet.build_packet(_config(tmp_path, snapshot))

    assert summary["human_merge_readiness_status"] == packet.STATUS_READY
    assert summary["ready_for_human_merge"] is True
    assert summary["v3_7_allowed"] is False
    assert any("DATA_NOT_MATURED" in warning for warning in summary["warnings"])


def test_cli_returns_nonzero_for_blocked_packet(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["conflict_dry_run_status"] = "CONFLICT"
    snapshot = _write_snapshot(tmp_path, payload)

    rc = packet.main(
        [
            "--packet-run-id",
            "baseline_v3_6ac_stack_merge_readiness_packet_cli_blocked",
            "--snapshot",
            str(snapshot),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert rc == 1


def _config(tmp_path: Path, snapshot: Path) -> packet.PacketConfig:
    return packet.PacketConfig(
        packet_run_id="baseline_v3_6ac_stack_merge_readiness_packet_unit",
        snapshot=snapshot,
        output_dir=tmp_path / "runs",
    )


def _write_snapshot(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "snapshot.json"
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
    ]
    return {
        "schema": "gotra.test.stack_merge_readiness_snapshot.v1",
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
                    "engineering/local only; not OOS/science/public/trading claim; "
                    "direct_llm_parametric_memory_control is not a clean no-future baseline; "
                    "v3_7_allowed=false."
                ),
            }
            for number, title, base, head in branches
        ],
        "changed_files": ["docs/GOTRA_V3_6AC_STACK_MERGE_READINESS_PACKET_RESULT_20260621.md"],
        "evidence_documents": [
            {
                "path": "docs/good.md",
                "text": (
                    "engineering/local only; historical/internal only; "
                    "not OOS/science/public/trading claim; not investment advice; "
                    "direct_llm_parametric_memory_control is not a clean no-future baseline; "
                    "v3_7_allowed=false."
                ),
            }
        ],
    }
