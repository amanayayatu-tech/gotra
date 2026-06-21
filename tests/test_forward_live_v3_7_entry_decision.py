from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness_v36
from scripts import baseline_v3_6s_actual_maturity_monitor as monitor_v36s
from scripts import baseline_v3_7_forward_live_entry_decision as entry_v37


def test_data_not_matured_blocks_verdict_but_allows_harness_prep(
    tmp_path: Path,
) -> None:
    source = _write_monitor_summary(
        tmp_path,
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
        readiness_status=monitor_v36s.READINESS_NOT_RUN,
        checked_capture_run_count=4,
        matured_candidate_count=0,
        resolved_count=0,
        scored_count=0,
        next_check_after="2026-07-21T00:00:00Z",
        blocker_reasons=["capture_horizons_not_matured", "readiness_not_ready"],
    )
    summary = entry_v37.run_entry_decision(_config(tmp_path, source))

    assert summary["status"] == entry_v37.STATUS_BLOCKED_BY_ACTUAL_READINESS
    assert summary["readiness_status"] == monitor_v36s.STATUS_DATA_NOT_MATURED
    assert summary["checked_capture_run_count"] == 4
    assert summary["matured_candidate_count"] == 0
    assert summary["resolved_count"] == 0
    assert summary["scored_count"] == 0
    assert summary["paired_clean_count"] == 0
    assert summary["full_gotra_available_count"] == 0
    assert summary["deterministic_reference_available_count"] == 0
    assert summary["next_check_after"] == "2026-07-21T00:00:00Z"
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["v3_7_verdict_harness_prep_allowed"] is True
    assert summary["v3_7_verdict_executed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_current_ready_summary_allows_separate_verdict_stage_planning(
    tmp_path: Path,
) -> None:
    source = _write_monitor_summary(
        tmp_path,
        status=monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE,
        readiness_status=readiness_v36.STATUS_READY,
        next_stage_planning_allowed=True,
        resolver_path_eligible=True,
        matured_candidate_count=8,
        resolved_count=8,
        scored_count=8,
        paired_clean_count=8,
        full_gotra_available_count=8,
        deterministic_reference_available_count=8,
    )

    summary = entry_v37.run_entry_decision(_config(tmp_path, source))

    assert summary["status"] == entry_v37.STATUS_READY_FOR_VERDICT_WORKFLOW
    assert summary["readiness_status"] == readiness_v36.STATUS_READY
    assert summary["v3_7_actual_verdict_executable"] is True
    assert summary["v3_7_verdict_executed"] is False
    assert summary["next_action"] == entry_v37.ACTION_EXECUTE_SEPARATE_VERDICT_STAGE


def test_ready_status_without_current_planning_flag_stays_blocked(
    tmp_path: Path,
) -> None:
    source = _write_monitor_summary(
        tmp_path,
        status=monitor_v36s.STATUS_RESOLVER_PATH_ELIGIBLE,
        readiness_status=readiness_v36.STATUS_READY,
        next_stage_planning_allowed=False,
        resolver_path_eligible=True,
        blocker_reasons=["current_monitor_not_resolver_path_eligible"],
    )

    summary = entry_v37.run_entry_decision(_config(tmp_path, source))

    assert summary["status"] == entry_v37.STATUS_BLOCKED_BY_ACTUAL_READINESS
    assert summary["readiness_status"] == readiness_v36.STATUS_READY
    assert summary["v3_7_actual_verdict_executable"] is False
    assert "current_monitor_not_resolver_path_eligible" in summary["blocker_reasons"]


def test_malformed_source_summary_blocks_provenance(tmp_path: Path) -> None:
    source = tmp_path / "bad_summary.json"
    source.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")

    summary = entry_v37.run_entry_decision(_config(tmp_path, source))

    assert summary["status"] == entry_v37.STATUS_BLOCKED_PROVENANCE
    assert "source_summary_schema_mismatch" in summary["blocker_reasons"]
    assert "source_monitor_run_id_missing" in summary["blocker_reasons"]


def test_source_summary_hash_mismatch_blocks_provenance(tmp_path: Path) -> None:
    source = _write_monitor_summary(
        tmp_path,
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
    )

    summary = entry_v37.run_entry_decision(
        _config(tmp_path, source, source_sha256="0" * 64)
    )

    assert summary["status"] == entry_v37.STATUS_BLOCKED_PROVENANCE
    assert "source_summary_sha256_mismatch" in summary["blocker_reasons"]


def test_runtime_boundary_flags_block_entry_decision(tmp_path: Path) -> None:
    source = _write_monitor_summary(
        tmp_path,
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
        provider_or_backend_called=True,
    )

    summary = entry_v37.run_entry_decision(_config(tmp_path, source))

    assert summary["status"] == entry_v37.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert summary["provider_or_backend_called"] is True
    assert "provider_or_backend_called" in summary["blocker_reasons"]
    assert summary["v3_7_actual_verdict_executable"] is False


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    source = _write_monitor_summary(
        tmp_path,
        status=monitor_v36s.STATUS_DATA_NOT_MATURED,
    )
    config = _config(tmp_path, source)

    entry_v37.run_entry_decision(config)

    run_root = config.output_dir / config.entry_run_id
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary_sha256"] == entry_v37.sha256_file(run_root / "summary.json")


def _write_monitor_summary(
    root: Path,
    *,
    status: str,
    readiness_status: str = monitor_v36s.READINESS_NOT_RUN,
    checked_capture_run_count: int = 1,
    matured_candidate_count: int = 0,
    resolved_count: int = 0,
    scored_count: int = 0,
    paired_clean_count: int = 0,
    full_gotra_available_count: int = 0,
    deterministic_reference_available_count: int = 0,
    next_stage_planning_allowed: bool = False,
    resolver_path_eligible: bool = False,
    next_check_after: str = "",
    blocker_reasons: list[str] | None = None,
    provider_or_backend_called: bool = False,
) -> Path:
    path = root / "source_summary.json"
    payload = {
        "schema": monitor_v36s.SUMMARY_SCHEMA,
        "monitor_run_id": "baseline_v3_6s_actual_maturity_monitor_fixture",
        "status": status,
        "readiness_status": readiness_status,
        "checked_capture_run_count": checked_capture_run_count,
        "matured_candidate_count": matured_candidate_count,
        "resolved_count": resolved_count,
        "scored_count": scored_count,
        "paired_clean_count": paired_clean_count,
        "full_gotra_available_count": full_gotra_available_count,
        "deterministic_reference_available_count": deterministic_reference_available_count,
        "next_stage_planning_allowed": next_stage_planning_allowed,
        "resolver_path_eligible": resolver_path_eligible,
        "next_check_after": next_check_after,
        "blocker_reasons": blocker_reasons or [],
        "provider_or_backend_called": provider_or_backend_called,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "v3_7_verdict_executed": False,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(
    root: Path,
    source: Path,
    *,
    source_sha256: str = "",
) -> entry_v37.EntryDecisionConfig:
    return entry_v37.EntryDecisionConfig(
        readiness_summary_path=source,
        readiness_summary_sha256=source_sha256,
        entry_run_id="baseline_v3_7_forward_live_entry_decision_fixture",
        output_dir=root / "runs",
        as_of_timestamp_utc=datetime(2026, 6, 21, 13, 26, 8, tzinfo=UTC),
        allow_overwrite=True,
    )
