from __future__ import annotations

import json
from datetime import datetime, timezone

from gotra.beta_runtime import (
    build_systemd_units,
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
    heartbeat = write_heartbeat(evidence_root=evidence_root, public_status_path=public_status)
    assert heartbeat["phase"] == "beta_in_progress_real_time_wait"
    assert heartbeat["beta_complete"] is False
    assert heartbeat["boundary"]["no_performance_proof"] is True

    status = status_payload(evidence_root=evidence_root, public_status_path=public_status)
    assert status["beta_started"] is True
    assert status["public_status"]["last_daily_run_status"] == "unavailable_no_live_daily_research_job_configured"


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


def test_systemd_unit_definition_is_recoverable(tmp_path):
    units = build_systemd_units(tmp_path)

    assert "gotra-stage15b-beta.service" in units["timer"]
    assert "scripts/gotra_beta_runtime.py run-once" in units["service"]
    assert "StandardOutput=append:" in units["service"]
