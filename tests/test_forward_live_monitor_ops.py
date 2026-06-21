from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness_v36
from scripts import baseline_v3_6s_actual_maturity_monitor as monitor_v36s
from scripts import baseline_v3_6t_forward_live_monitor_ops as ops


def test_ops_reports_data_insufficient_without_monitor_summaries(tmp_path: Path) -> None:
    input_root = tmp_path / "empty"
    input_root.mkdir()
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_no_summaries",
    )

    summary = ops.run_ops(config)

    assert summary["status"] == ops.STATUS_DATA_INSUFFICIENT
    assert summary["monitor_run_count"] == 0
    assert summary["latest_monitor_run_id"] == ""
    assert summary["next_action_recommendation"] == ops.RECOMMEND_FIX_BLOCKER
    assert summary["v3_7_verdict_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False


def test_ops_waits_until_next_check_for_latest_data_not_matured(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_wait",
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
        next_check_after="2026-07-21T00:00:00Z",
        as_of="2026-06-21T00:00:00Z",
        not_matured_count=8,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_wait",
        as_of="2026-06-21T03:00:00Z",
    )

    summary = ops.run_ops(config)

    assert summary["status"] == monitor_v36s.STATUS_DATA_NOT_MATURED
    assert summary["latest_status"] == monitor_v36s.STATUS_DATA_NOT_MATURED
    assert summary["not_matured_count"] == 8
    assert summary["next_action_recommendation"] == ops.RECOMMEND_WAIT_UNTIL_NEXT_CHECK
    assert summary["latest_next_check_after"] == "2026-07-21T00:00:00Z"


def test_ops_recheck_now_allowed_after_next_check_time(tmp_path: Path) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_due",
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
        next_check_after="2026-07-21T00:00:00Z",
        as_of="2026-06-21T00:00:00Z",
        not_matured_count=8,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_due",
        as_of="2026-07-21T00:00:00Z",
    )

    summary = ops.run_ops(config)

    assert summary["next_action_recommendation"] == ops.RECOMMEND_RECHECK_NOW_ALLOWED
    assert summary["v3_7_verdict_allowed"] is False


def test_ops_honors_data_not_matured_before_stale_ready_status(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_not_matured_ready",
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
        next_check_after="2026-07-21T00:00:00Z",
        as_of="2026-06-21T00:00:00Z",
        readiness_status=readiness_v36.STATUS_READY,
        next_stage_planning_allowed=False,
        not_matured_count=8,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_not_matured_ready",
        as_of="2026-06-21T03:00:00Z",
    )

    summary = ops.run_ops(config)

    assert summary["status"] == monitor_v36s.STATUS_DATA_NOT_MATURED
    assert summary["readiness_status"] == readiness_v36.STATUS_READY
    assert summary["next_action_recommendation"] == ops.RECOMMEND_WAIT_UNTIL_NEXT_CHECK
    assert summary["v3_7_verdict_allowed"] is False


def test_ops_recommends_fix_blocker_for_latest_blocked_data(tmp_path: Path) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_blocked",
        status=monitor_v36s.STATUS_BLOCKED_DATA,
        as_of="2026-07-21T00:00:00Z",
        blocked_data_count=2,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_blocked",
    )

    summary = ops.run_ops(config)

    assert summary["status"] == monitor_v36s.STATUS_BLOCKED_DATA
    assert summary["blocked_data_count"] == 2
    assert summary["next_action_recommendation"] == ops.RECOMMEND_FIX_BLOCKER
    assert summary["v3_7_verdict_allowed"] is False


def test_ops_blocks_resolver_path_without_ready_readiness(tmp_path: Path) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_missing_readiness",
        status=monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE,
        as_of="2026-07-21T00:00:00Z",
        readiness_status=monitor_v36s.READINESS_NOT_RUN,
        resolver_path_eligible=True,
        matured_candidate_count=3,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_missing_readiness",
    )

    summary = ops.run_ops(config)

    assert summary["status"] == monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE
    assert summary["readiness_status"] == monitor_v36s.READINESS_NOT_RUN
    assert summary["next_action_recommendation"] == ops.RECOMMEND_FIX_BLOCKER
    assert summary["v3_7_verdict_allowed"] is False


def test_ops_ready_status_without_current_planning_flag_does_not_allow_v3_7(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_stale_ready",
        status=monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE,
        as_of="2026-07-21T00:00:00Z",
        readiness_status=readiness_v36.STATUS_READY,
        next_stage_planning_allowed=False,
        resolver_path_eligible=True,
        matured_candidate_count=3,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_stale_ready",
    )

    summary = ops.run_ops(config)

    assert summary["readiness_status"] == readiness_v36.STATUS_READY
    assert summary["next_stage_planning_allowed"] is False
    assert summary["next_action_recommendation"] == ops.RECOMMEND_FIX_BLOCKER
    assert summary["v3_7_verdict_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False


def test_ops_ready_with_current_eligibility_only_allows_planning(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_ready",
        status=monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE,
        as_of="2026-07-21T00:00:00Z",
        readiness_status=readiness_v36.STATUS_READY,
        next_stage_planning_allowed=True,
        resolver_path_eligible=True,
        matured_candidate_count=3,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_ready",
    )

    summary = ops.run_ops(config)

    assert summary["next_action_recommendation"] == ops.RECOMMEND_PLAN_V3_7_ONLY_IF_READY
    assert summary["v3_7_verdict_allowed"] is True
    assert summary["v3_7_verdict_executed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_ops_selects_latest_summary_deterministically_and_counts_history(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "summaries"
    old_path = _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_old",
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
        as_of="2026-06-21T00:00:00Z",
        not_matured_count=10,
    )
    new_path = _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_new",
        status=monitor_v36s.STATUS_BLOCKED_DATA,
        as_of="2026-06-22T00:00:00Z",
        blocked_data_count=1,
    )
    config = _ops_config(
        tmp_path,
        input_root=input_root,
        run_id="baseline_v3_6t_monitor_ops_history",
    )

    summary = ops.run_ops(config)

    assert summary["monitor_run_count"] == 2
    assert summary["ledger_entry_count"] == 2
    assert summary["latest_monitor_run_id"] == "baseline_v3_6s_actual_maturity_monitor_new"
    assert summary["latest_status"] == monitor_v36s.STATUS_BLOCKED_DATA
    assert summary["latest_summary_path"] == str(new_path)
    assert summary["latest_summary_path"] != str(old_path)


def test_ops_cli_returns_nonzero_for_latest_hard_blocked_status(tmp_path: Path) -> None:
    input_root = tmp_path / "summaries"
    _write_monitor_summary(
        input_root,
        run_id="baseline_v3_6s_actual_maturity_monitor_cli_blocked",
        status=monitor_v36s.STATUS_BLOCKED_DATA,
        as_of="2026-07-21T00:00:00Z",
        blocked_data_count=1,
    )

    exit_code = ops.main(
        [
            "--input-root",
            str(input_root),
            "--ops-run-id",
            "baseline_v3_6t_monitor_ops_cli_blocked",
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert exit_code == 1
    summary = json.loads(
        (
            tmp_path
            / "runs"
            / "baseline_v3_6t_monitor_ops_cli_blocked"
            / "summary.json"
        ).read_text(encoding="utf-8")
    )
    assert summary["status"] == monitor_v36s.STATUS_BLOCKED_DATA
    assert summary["next_action_recommendation"] == ops.RECOMMEND_FIX_BLOCKER


def _write_monitor_summary(
    root: Path,
    *,
    run_id: str,
    status: str,
    as_of: str,
    next_check_after: str = "",
    readiness_status: str = monitor_v36s.READINESS_NOT_RUN,
    next_stage_planning_allowed: bool = False,
    resolver_path_eligible: bool = False,
    checked_capture_run_count: int = 1,
    not_matured_count: int = 0,
    matured_candidate_count: int = 0,
    blocked_data_count: int = 0,
    resolved_count: int = 0,
    scored_count: int = 0,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{run_id}.json"
    payload = {
        "schema": monitor_v36s.SUMMARY_SCHEMA,
        "monitor_run_id": run_id,
        "status": status,
        "as_of_timestamp_utc": as_of,
        "completed_at": as_of,
        "next_check_after": next_check_after,
        "checked_capture_run_count": checked_capture_run_count,
        "not_matured_count": not_matured_count,
        "matured_candidate_count": matured_candidate_count,
        "blocked_data_count": blocked_data_count,
        "resolved_count": resolved_count,
        "scored_count": scored_count,
        "readiness_status": readiness_status,
        "next_stage_planning_allowed": next_stage_planning_allowed,
        "resolver_path_eligible": resolver_path_eligible,
        "v3_7_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "blocker_reasons": [],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _ops_config(
    root: Path,
    *,
    input_root: Path,
    run_id: str,
    as_of: str = "2026-06-21T03:00:00Z",
) -> ops.OpsConfig:
    return ops.OpsConfig(
        input_roots=(input_root,),
        ops_run_id=run_id,
        output_dir=root / "runs",
        as_of_timestamp_utc=datetime.fromisoformat(as_of.replace("Z", "+00:00")).astimezone(
            UTC
        ),
    )
