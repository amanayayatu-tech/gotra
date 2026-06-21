from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6aa_stack_evidence_boundary_audit as audit


def test_clean_stacked_pr_fixture_is_clean_and_v3_7_false(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, _clean_snapshot())
    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_CLEAN
    assert summary["open_pr_count"] == 7
    assert summary["stack_topology_status"] == "clean"
    assert summary["ci_success_count"] == 14
    assert summary["active_p1_p2_count"] == 0
    assert summary["artifact_boundary_violation_count"] == 0
    assert summary["evidence_overclaim_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False
    assert summary["next_30d_check_after"] == audit.NEXT_30D_CHECK_AFTER
    assert summary["next_short_horizon_check_after"] == audit.NEXT_SHORT_HORIZON_CHECK_AFTER
    assert summary["direct_llm_interpretation"] == audit.DIRECT_LLM_INTERPRETATION


def test_open_unmerged_pr_stack_does_not_block(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    for pr in payload["pull_requests"]:
        pr["state"] = "OPEN"
        pr["merged"] = False
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_CLEAN


def test_ci_failed_or_pending_blocks_stack(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][2]["statusCheckRollup"][0]["status"] = "IN_PROGRESS"
    payload["pull_requests"][2]["statusCheckRollup"][0]["conclusion"] = ""
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_CI
    assert any(reason.startswith("ci:not_success:pr_38") for reason in summary["blocking_reasons"])


def test_active_p2_review_thread_blocks_stack(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][5]["reviewThreads"] = [
        {
            "isResolved": False,
            "isOutdated": False,
            "comments": [{"body": "![P2 Badge] active blocker"}],
        }
    ]
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_REVIEW
    assert summary["active_p1_p2_count"] == 1
    assert "review:active_P2:pr_41" in summary["blocking_reasons"]


def test_base_topology_break_blocks_stack(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][4]["baseRefName"] = "main"
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_TOPOLOGY
    assert any("pr_40" in reason for reason in summary["blocking_reasons"])


def test_forbidden_artifact_path_blocks_stack(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["pull_requests"][0]["changed_files"].append("data/backtest/runs/raw.json")
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_ARTIFACT
    assert summary["artifact_boundary_violation_count"] == 1
    assert "data/backtest/runs/raw.json" in summary["blocking_reasons"][0]


def test_evidence_overclaim_blocks_stack(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["evidence_documents"].append(
        {
            "path": "docs/bad.md",
            "text": "This is an OOS pass and trading recommendation.",
        }
    )
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_OVERCLAIM
    assert summary["evidence_overclaim_count"] >= 1


def test_direct_llm_without_parametric_memory_caveat_blocks_stack(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["evidence_documents"].append(
        {
            "path": "docs/direct_bad.md",
            "text": "direct_llm is the clean baseline.",
        }
    )
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_OVERCLAIM
    assert any("direct_llm_without_parametric_caveat" in reason for reason in summary["blocking_reasons"])


def test_short_horizon_ready_does_not_authorize_v3_7(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["evidence_documents"].append(
        {
            "path": "docs/short_ready.md",
            "text": (
                "SHORT_HORIZON_READY only; "
                "direct_llm_parametric_memory_control; not OOS."
            ),
        }
    )
    snapshot = _write_snapshot(tmp_path, payload)

    summary = audit.audit_snapshot(_config(tmp_path, snapshot))

    assert summary["overall_status"] == audit.STATUS_CLEAN
    assert summary["v3_7_allowed"] is False


def test_cli_returns_nonzero_for_blocked_fixture(tmp_path: Path) -> None:
    payload = _clean_snapshot()
    payload["changed_files"].append("data/paper_trading/decision.json")
    snapshot = _write_snapshot(tmp_path, payload)

    rc = audit.main(
        [
            "--audit-run-id",
            "baseline_v3_6aa_stack_evidence_boundary_audit_cli_blocked",
            "--snapshot",
            str(snapshot),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert rc == 1


def _config(tmp_path: Path, snapshot: Path) -> audit.AuditConfig:
    return audit.AuditConfig(
        audit_run_id="baseline_v3_6aa_stack_evidence_boundary_audit_unit",
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
    ]
    return {
        "schema": "gotra.test.stack_snapshot.v1",
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
            }
            for number, title, base, head in branches
        ],
        "changed_files": ["docs/GOTRA_V3_6AA_STACK_AUDIT_RESULT_20260621.md"],
        "evidence_documents": [
            {
                "path": "docs/good.md",
                "text": (
                    "engineering/local only; not OOS; not science/public proof; "
                    "not trading or investment advice; "
                    "direct_llm_parametric_memory_control; v3.7 allowed false."
                ),
            }
        ],
    }
