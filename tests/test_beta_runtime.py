from __future__ import annotations

import json
from datetime import datetime, timezone

import gotra.beta_runtime as beta_runtime
from gotra.beta_runtime import (
    build_systemd_units,
    daily_research_job_readiness,
    next_daily_run_metadata,
    run_once,
    start_beta_runtime,
    status_payload,
    write_heartbeat,
)


def test_start_beta_runtime_writes_auditable_day0_contract(tmp_path):
    evidence_root = tmp_path / "stage15B-runtime"
    public_status = tmp_path / "beta_status.json"

    result = start_beta_runtime(
        evidence_root=evidence_root,
        public_status_path=public_status,
        install_scheduler=False,
        now=datetime(2026, 7, 6, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result["status"]["schema"] == "gotra.public_beta.status.v1"
    assert result["status"]["beta_started"] is True
    assert result["status"]["beta_clock_started"] is True
    assert result["status"]["elapsed_days"] == 0
    assert result["status"]["required_days"] == 30
    assert result["status"]["beta_complete"] is False
    assert result["status"]["paid_features_enabled"] is False
    assert result["status"]["free_beta"] is True
    assert result["status"]["no_fabrication"] is True
    assert result["status"]["not_launch_ready"] is True
    assert result["status"]["not_investment_advice"] is True
    assert result["status"]["not_trading_signal"] is True

    assert (evidence_root / "beta-start.json").exists()
    assert (evidence_root / "beta-heartbeat.json").exists()
    assert (evidence_root / "beta-daily-events.jsonl").exists()
    assert (evidence_root / "beta-summary.md").exists()
    assert (evidence_root / "weekly-reports" / "beta-weekly-report-template.md").exists()
    assert (evidence_root / "runtime-contract.json").exists()
    assert public_status.exists()

    contract = json.loads((evidence_root / "runtime-contract.json").read_text())
    assert "scripts/gotra_beta_runtime.py start --day0" in contract["documented_start_command"]
    assert contract["scheduler"]["timer_name"] == "gotra-stage15b-beta.timer"
    assert contract["no_fabrication"] is True


def test_next_daily_run_uses_asia_shanghai_schedule_when_systemd_unavailable(monkeypatch):
    monkeypatch.setattr(
        beta_runtime,
        "read_next_systemd_timer_due",
        lambda unit=beta_runtime.TIMER_NAME: {"available": False, "unit": unit},
    )

    metadata = next_daily_run_metadata(now=datetime(2026, 7, 9, 3, 11, 0, tzinfo=timezone.utc))

    assert metadata["next_daily_run_due_at"] == "2026-07-09T10:30:00Z"
    assert metadata["next_daily_run_due_at_local"].startswith("2026-07-09T18:30:00")
    assert "fallback_schedule" in metadata["next_daily_run_due_at_source"]
    assert metadata["stale_status_detected"] is False


def test_next_daily_run_detects_stale_previous_due(monkeypatch):
    monkeypatch.setattr(
        beta_runtime,
        "read_next_systemd_timer_due",
        lambda unit=beta_runtime.TIMER_NAME: {"available": False, "unit": unit},
    )

    metadata = next_daily_run_metadata(
        now=datetime(2026, 7, 9, 3, 11, 0, tzinfo=timezone.utc),
        previous_due_at="2026-07-08T10:30:00Z",
    )

    assert metadata["next_daily_run_due_at"] == "2026-07-09T10:30:00Z"
    assert metadata["stale_status_detected"] is True


def test_systemd_timer_due_parses_cst_as_asia_shanghai(monkeypatch):
    class Result:
        def __init__(self, returncode: int, stdout: str):
            self.returncode = returncode
            self.stdout = stdout

    def fake_run(command, **_kwargs):
        if command[:2] == ["systemctl", "is-active"]:
            return Result(0, "active\n")
        if command[:2] == ["systemctl", "show"]:
            return Result(0, "Thu 2026-07-09 18:30:00 CST\n")
        raise AssertionError(command)

    monkeypatch.setattr(beta_runtime.shutil, "which", lambda name: "/bin/systemctl" if name == "systemctl" else None)
    monkeypatch.setattr(beta_runtime.subprocess, "run", fake_run)

    metadata = beta_runtime.read_next_systemd_timer_due()

    assert metadata["next_daily_run_due_at"] == "2026-07-09T10:30:00Z"
    assert metadata["next_daily_run_due_at_local"].startswith("2026-07-09T18:30:00")
    assert metadata["next_daily_run_due_at_source"] == "systemd_timer"


def test_run_once_dry_run_and_heartbeat_preserve_no_fabrication(tmp_path):
    evidence_root = tmp_path / "stage15B-runtime"
    public_status = tmp_path / "beta_status.json"
    start_beta_runtime(evidence_root=evidence_root, public_status_path=public_status, install_scheduler=False)

    dry_run = run_once(dry_run=True, evidence_root=evidence_root, public_status_path=public_status)
    assert dry_run["run_status"] == "unavailable_no_live_daily_research_job_configured"
    assert dry_run["no_fabrication"] is True
    assert dry_run["paid_features_enabled"] is False

    event = run_once(evidence_root=evidence_root, public_status_path=public_status)
    assert event["run_status"] == "unavailable_no_live_daily_research_job_configured"
    assert event["daily_research_job_configured"] is False
    assert event["valid_research_output_days"] == 0
    assert event["unavailable_days"] == 1
    assert event["failed_output_days"] == 0
    assert event["history_backfilled"] is False
    heartbeat = write_heartbeat(evidence_root=evidence_root, public_status_path=public_status)
    assert heartbeat["phase"] == "beta_in_progress_real_time_wait"
    assert heartbeat["beta_complete"] is False
    assert heartbeat["daily_research_job_configured"] is False
    assert heartbeat["valid_research_output_days"] == 0
    assert heartbeat["unavailable_days"] == 1
    assert heartbeat["failed_output_days"] == 0
    assert heartbeat["boundary"]["no_performance_proof"] is True

    status = status_payload(evidence_root=evidence_root, public_status_path=public_status)
    assert status["beta_started"] is True
    assert status["public_status"]["last_daily_run_status"] == "unavailable_no_live_daily_research_job_configured"
    assert status["public_status"]["daily_research_job_configured"] is False
    assert status["public_status"]["valid_research_output_days"] == 0
    assert status["public_status"]["unavailable_days"] == 1
    assert status["public_status"]["failed_output_days"] == 0


def test_daily_research_job_readiness_fails_closed_without_side_effect_free_live_pipeline():
    readiness = daily_research_job_readiness()

    assert readiness["daily_job_status"] == "not_ready"
    assert readiness["daily_job_configured"] is False
    assert readiness["safe_to_enable_from_next_run"] is False
    assert readiness["fixture_used"] is False
    assert readiness["public_artifact_written"] is False
    assert readiness["ledger_written"] is False
    assert readiness["history_backfilled"] is False
    assert readiness["missing_conditions"]


def test_run_once_dry_run_before_start_is_preview_only(tmp_path):
    evidence_root = tmp_path / "stage15B-runtime"
    evidence_root.mkdir()
    public_status = tmp_path / "beta_status.json"

    dry_run = run_once(dry_run=True, evidence_root=evidence_root, public_status_path=public_status)

    assert dry_run["run_status"] == "beta_not_started_dry_run_preview"
    assert dry_run["beta_started"] is False
    assert dry_run["beta_clock_started"] is False
    assert dry_run["no_fabrication"] is True
    assert not (evidence_root / "beta-start.json").exists()
    assert not public_status.exists()


def test_non_default_public_status_does_not_activate_global_pointer(tmp_path, monkeypatch):
    active_pointer = tmp_path / "active-path.txt"
    monkeypatch.setattr(beta_runtime, "ACTIVE_POINTER_PATH", active_pointer)
    evidence_root = tmp_path / "stage15B-runtime"
    public_status = tmp_path / "beta_status.json"

    start_beta_runtime(evidence_root=evidence_root, public_status_path=public_status, install_scheduler=False)

    assert public_status.exists()
    assert not active_pointer.exists()


def test_systemd_unit_definition_is_recoverable(tmp_path):
    units = build_systemd_units(tmp_path)

    assert "gotra-stage15b-beta.service" in units["timer"]
    assert "scripts/gotra_beta_runtime.py run-once" in units["service"]
    assert "StandardOutput=append:" in units["service"]
