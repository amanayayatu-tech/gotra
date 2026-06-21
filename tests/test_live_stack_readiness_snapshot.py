from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts import baseline_v3_6ad_live_stack_readiness_snapshot as snapshot


def test_clean_stack_fixture_is_ready_without_v3_7(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, _clean_snapshot())

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["ready_for_human_merge_review"] is True
    assert summary["auto_merge_executed"] is False
    assert summary["v3_7_allowed"] is False
    assert summary["source_mode"] == snapshot.SOURCE_FIXTURE
    assert summary["open_pr_count"] == 10
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_open_unmerged_prs_do_not_block_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    for pr in payload["pull_requests"]:
        pr["state"] = "OPEN"
        pr["merged"] = False
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["ready_for_human_merge_review"] is True


def test_ci_pending_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][2]["statusCheckRollup"][0]["status"] = "IN_PROGRESS"
    payload["pull_requests"][2]["statusCheckRollup"][0]["conclusion"] = ""
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_CI
    assert summary["ready_for_human_merge_review"] is False


def test_active_p2_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][4]["reviewThreads"] = [
        {
            "isResolved": False,
            "isOutdated": False,
            "comments": [{"body": "![P2 Badge] active blocker"}],
        }
    ]
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_REVIEW
    assert summary["active_p1_p2_count"] == 1


def test_draft_pr_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][1]["isDraft"] = True
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_TOPOLOGY
    assert any("draft_pr" in reason for reason in summary["blocking_reasons"])


def test_topology_base_chain_break_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["baseRefName"] = "old-root"
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_TOPOLOGY
    assert any("root_base_mismatch" in reason for reason in summary["blocking_reasons"])


def test_forbidden_changed_path_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["files"] = {
        "nodes": [{"path": "data/backtest/runs/raw.json"}]
    }
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_violation_count"] == 1


def test_claim_boundary_overclaim_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][3]["body"] = "This is an OOS pass."
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_violation_count"] >= 1


def test_cannot_say_body_boundary_list_does_not_block(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][3]["body"] = "\n".join(
        [
            "## Cannot say",
            "",
            "- OOS pass.",
            "- Science/public proof.",
            "- Trading recommendation.",
            "- `direct_llm` as a clean no-future baseline.",
            "",
            "v3.7 allowed: `false`.",
        ]
    )
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["claim_boundary_status"] == "clean"


def test_canary_non_claim_boundary_line_does_not_block(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][4]["body"] = (
        "Added v3.6Y prereg/result doc with canary metadata and non-claim boundaries."
    )
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["claim_boundary_status"] == "clean"


@pytest.mark.parametrize(
    "body",
    [
        "v3_7_allowed=true (was false before)",
        "v3.7 is allowed, not false anymore",
    ],
)
def test_positive_v3_7_claim_with_false_word_still_blocks(
    tmp_path: Path,
    body: str,
) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][4]["body"] = body
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_violation_count"] >= 1


@pytest.mark.parametrize(
    "body",
    [
        "v3.7 allowed: false",
        "v3_7_allowed=false",
        "v3.7 verdict allowed: false",
        "v3.7 30D verdict allowed: false",
        "v3.7 not allowed",
    ],
)
def test_unambiguous_false_v3_7_boundary_lines_are_clean(
    tmp_path: Path,
    body: str,
) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][4]["body"] = body
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["claim_boundary_status"] == "clean"


def test_dirty_merge_state_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][2]["mergeStateStatus"] = "DIRTY"
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_CONFLICT
    assert summary["conflict_dry_run_status"] == snapshot.merge_packet.CONFLICT_BLOCKED
    assert any("merge_state_status:dirty" in reason for reason in summary["blocking_reasons"])


def test_conflict_fixture_blocks_snapshot(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["conflict_dry_run_status"] = "BLOCKED_CONFLICT"
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_CONFLICT
    assert summary["ready_for_human_merge_review"] is False


def test_graphql_status_check_rollup_contexts_nodes_are_success(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    for pr in payload["pull_requests"]:
        pr["statusCheckRollup"] = {
            "contexts": {
                "nodes": [
                    {
                        "__typename": "CheckRun",
                        "name": "Python checks",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                    {
                        "__typename": "StatusContext",
                        "context": "legacy-status",
                        "state": "SUCCESS",
                    },
                ]
            }
        }
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["ci_all_success"] is True
    assert summary["ci_success_count"] == 20


def test_data_not_matured_is_boundary_note_not_snapshot_blocker(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["readiness_status"] = "DATA_NOT_MATURED"
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_READY
    assert summary["v3_7_allowed"] is False
    assert any("DATA_NOT_MATURED" in warning for warning in summary["warnings"])


@pytest.mark.parametrize("state", ["CLOSED", "MERGED", ""])
def test_pr_state_must_be_open(tmp_path: Path, state: str) -> None:
    payload = _clean_snapshot()
    if state:
        payload["pull_requests"][3]["state"] = state
    else:
        del payload["pull_requests"][3]["state"]
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_TOPOLOGY
    assert any("pr_state_not_open" in reason for reason in summary["blocking_reasons"])


def test_fixture_missing_requested_pr_range_is_incomplete(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"] = payload["pull_requests"][:1]
    path = _write_snapshot(tmp_path, payload)

    summary = snapshot.build_snapshot(_config(tmp_path, path))

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_INCOMPLETE
    assert summary["ready_for_human_merge_review"] is False
    assert 37 in summary["missing_pr_numbers"]
    assert 45 in summary["missing_pr_numbers"]


def test_live_gh_paginates_changed_files_and_blocks_forbidden_after_first_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    first_page_nodes = [{"path": f"docs/safe_{index}.md"} for index in range(100)]
    second_page_nodes = [{"path": "data/backtest/runs/raw.json"}]
    outputs = [
        _gh_response(
            _gh_pr(
                36,
                files_nodes=first_page_nodes,
                has_next=True,
                end_cursor="cursor-1",
            )
        ),
        _gh_response(
            _gh_pr(
                36,
                files_nodes=second_page_nodes,
                has_next=False,
                end_cursor=None,
            )
        ),
    ]

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(" ".join(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs.pop(0), stderr="")

    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)

    summary = snapshot.build_snapshot(
        snapshot.SnapshotConfig(
            snapshot_run_id="baseline_v3_6ad_live_stack_readiness_snapshot_unit",
            output_dir=tmp_path / "runs",
            use_gh=True,
            repo="amanayayatu-tech/gotra",
            pr_range="36",
        )
    )

    assert len(calls) == 2
    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_violation_count"] == 1


def test_incomplete_live_gh_file_pagination_blocks_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _gh_response(
        _gh_pr(
            36,
            files_nodes=[{"path": "docs/safe.md"}],
            has_next=True,
            end_cursor=None,
        )
    )

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout=response, stderr="")

    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)

    summary = snapshot.build_snapshot(
        snapshot.SnapshotConfig(
            snapshot_run_id="baseline_v3_6ad_live_stack_readiness_snapshot_unit",
            output_dir=tmp_path / "runs",
            use_gh=True,
            repo="amanayayatu-tech/gotra",
            pr_range="36",
        )
    )

    assert summary["live_stack_snapshot_status"] == snapshot.STATUS_INCOMPLETE
    assert summary["ready_for_human_merge_review"] is False
    assert summary["incomplete_pr_numbers"] == [36]


def _config(tmp_path: Path, path: Path) -> snapshot.SnapshotConfig:
    return snapshot.SnapshotConfig(
        snapshot_run_id="baseline_v3_6ad_live_stack_readiness_snapshot_unit",
        snapshot=path,
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
    ]
    return {
        "schema": "gotra.test.live_stack_readiness_snapshot.v1",
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
                    }
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


def _gh_response(pr: dict[str, object] | None) -> str:
    return json.dumps({"data": {"repository": {"pullRequest": pr}}})


def _gh_pr(
    number: int,
    *,
    files_nodes: list[dict[str, str]],
    has_next: bool,
    end_cursor: str | None,
) -> dict[str, object]:
    return {
        "number": number,
        "title": "Add actual forward-live maturity monitor",
        "baseRefName": "main",
        "headRefName": "codex/gotra-v3-6s-actual-maturity-monitor-20260621",
        "headRefOid": "sha-36",
        "isDraft": False,
        "mergeStateStatus": "CLEAN",
        "state": "OPEN",
        "statusCheckRollup": {
            "contexts": {
                "nodes": [
                    {
                        "__typename": "CheckRun",
                        "name": "Python checks",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    }
                ]
            }
        },
        "reviewThreads": {"nodes": []},
        "files": {
            "nodes": files_nodes,
            "pageInfo": {
                "hasNextPage": has_next,
                "endCursor": end_cursor,
            },
        },
        "body": (
            "engineering/local only; not OOS/science/public/trading claim; "
            "direct_llm_parametric_memory_control is not a clean no-future baseline; "
            "v3_7_allowed=false."
        ),
    }
