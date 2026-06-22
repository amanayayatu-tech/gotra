from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_7i_merge_readiness_watchdog as watchdog


def test_clean_mock_pr_is_ready(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture())

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_READY
    assert summary["ready_for_judge_auto_merge_gate"] is True
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["evidence_layer"] == watchdog.EVIDENCE_LAYER


def test_dirty_merge_state_blocks_conflict(tmp_path: Path) -> None:
    payload = _valid_fixture(merge_state_status="DIRTY")
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_CONFLICT
    assert "merge_state_not_clean" in summary["blocker_reasons"]


def test_ci_fail_pending_or_missing_required_check_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture(
        required_status_checks=["Python checks", "Boundary preflight"],
        status_checks=[
            {"name": "Python checks", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"name": "Lint", "status": "IN_PROGRESS", "conclusion": ""},
        ],
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_CI
    assert "ci_missing_required_check" in summary["blocker_reasons"]
    assert "ci_check_not_success" in summary["blocker_reasons"]


def test_active_p1_p2_review_thread_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture(
        review_threads=[
            {"priority": "P2", "isResolved": False, "isOutdated": False, "body": "P2 active review"},
        ]
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_REVIEW
    assert "active_p1_p2_review_thread" in summary["blocker_reasons"]


def test_resolved_or_outdated_p2_thread_stays_ready(tmp_path: Path) -> None:
    payload = _valid_fixture(
        review_threads=[
            {"priority": "P2", "isResolved": True, "isOutdated": False, "body": "P2 resolved"},
            {"priority": "P1", "isResolved": False, "isOutdated": True, "body": "P1 outdated"},
        ]
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_READY
    assert summary["active_p1_p2_review_thread_count"] == 0


def test_draft_pr_blocks(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture(is_draft=True))

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_DRAFT
    assert "draft_pr" in summary["blocker_reasons"]


def test_forbidden_changed_file_path_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture(changed_files=["scripts/good.py", "data/backtest/runs/raw.json"])
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_changed_file_path" in summary["blocker_reasons"]


def test_runtime_flag_true_or_missing_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_fixture(provider_or_backend_called=True)
    payload.pop("codex_cli_new_call")
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_SCHEMA
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "missing_codex_cli_new_call" in summary["blocker_reasons"]


def test_claim_overreach_in_title_body_or_status_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture(
        title="This PR proves OOS public science evidence",
        body="This is trading advice and a winner proof.",
        merge_readiness_status="actual v3.7 verdict ready",
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_v3_7_actual_verdict_executable_true_with_data_not_matured_blocks(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture(v3_7_actual_verdict_executable=True))

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_SCHEMA
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_direct_llm_without_parametric_label_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture(body="direct_llm is the clean no-future baseline")
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "direct_llm_clean_no_future_baseline" in summary["blocker_reasons"]


def test_malformed_missing_schema_fields_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload.pop("base_sha")
    payload["changed_files"] = "scripts/good.py"
    fixture = _write_fixture(tmp_path, payload)

    summary = watchdog.build_summary(_config(tmp_path, fixture))

    assert summary["watchdog_status"] == watchdog.STATUS_BLOCKED_SCHEMA
    assert "missing_base_sha" in summary["blocker_reasons"]


def test_manifest_digest_and_content_digest_are_stable(tmp_path: Path) -> None:
    payload = _valid_fixture()
    fixture = _write_fixture(tmp_path, payload)
    summary_a = watchdog.build_summary(_config(tmp_path / "a", fixture, "baseline_v3_7i_merge_readiness_watchdog_a"))
    summary_b = watchdog.build_summary(_config(tmp_path / "b", fixture, "baseline_v3_7i_merge_readiness_watchdog_b"))
    manifest = json.loads(Path(summary_a["manifest_path"]).read_text(encoding="utf-8"))

    assert summary_a["watchdog_status"] == watchdog.STATUS_READY
    assert summary_a["watchdog_content_sha256"] == summary_b["watchdog_content_sha256"]
    assert manifest["summary_sha256"] == watchdog.sha256_file(Path(summary_a["summary_path"]))


def test_cli_returns_nonzero_for_blockers(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture(is_draft=True))

    status = watchdog.main(
        [
            "--watchdog-run-id",
            "baseline_v3_7i_merge_readiness_watchdog_cli_blocked",
            "--fixture",
            str(fixture),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def _valid_fixture(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "base_ref": "main",
        "base_sha": "bb9dba1b86b569e80239a2f95bb8cf32bb83bb15",
        "head_ref": "codex/gotra-v3-7i-merge-readiness-watchdog-20260622",
        "head_sha": "1234567890abcdef1234567890abcdef12345678",
        "merge_state_status": "CLEAN",
        "is_draft": False,
        "changed_files": [
            "scripts/baseline_v3_7i_merge_readiness_watchdog.py",
            "tests/test_v3_7i_merge_readiness_watchdog.py",
            "docs/GOTRA_V3_7I_MERGE_READINESS_WATCHDOG_RESULT_20260622.md",
        ],
        "status_checks": [
            {"name": "Python checks", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"name": "Python checks", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ],
        "required_status_checks": ["Python checks"],
        "review_threads": [],
        "title": "Add v3.7 merge-readiness watchdog",
        "body": "engineering/internal merge gate guard only; not OOS; not science; not public; not trading",
        "summary": "Fixture-only watchdog. v3_7_actual_verdict_executable=false.",
        "merge_readiness_status": "ENGINEERING_MERGE_GATE_CLEAN",
        "evidence_layer": watchdog.EVIDENCE_LAYER,
        "actual_30d_readiness_status": watchdog.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": watchdog.ACTUAL_30D_NEXT_CHECK_AFTER,
        "direct_llm_interpretation": watchdog.DIRECT_LLM_INTERPRETATION,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "non_claims": "not actual 30D verdict; not OOS/science/public/trading claim; not investment advice",
    }
    payload.update(updates)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "merge_readiness_watchdog_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(
    tmp_path: Path,
    fixture: Path,
    run_id: str = "baseline_v3_7i_merge_readiness_watchdog_unit",
) -> watchdog.WatchdogConfig:
    return watchdog.WatchdogConfig(
        watchdog_run_id=run_id,
        output_dir=tmp_path / "runs",
        fixture=fixture,
        allow_overwrite=True,
    )
