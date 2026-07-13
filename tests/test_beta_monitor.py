from __future__ import annotations

import json
from datetime import datetime, timezone

import gotra.beta_monitor as beta_monitor
import gotra.beta_runtime as beta_runtime
from gotra.beta_monitor import (
    build_monitor_systemd_units,
    daily_report,
    health_check,
    post_run_check,
)
from gotra.beta_runtime import start_beta_runtime


def _passing_production() -> dict[str, object]:
    return {
        "routes": [
            {"url": "https://gotra.me/", "ok": True, "status": 200},
            {"url": "https://gotra.me/beta", "ok": True, "status": 200},
            {"url": "https://gotra.me/today/", "ok": True, "status": 200},
            {"url": "https://gotra.me/track-record", "ok": True, "status": 200},
            {"url": "https://gotra.me/monthly-reports", "ok": True, "status": 200},
            {"url": "https://gotra.me/reports/latest/", "ok": True, "status": 200},
            {"url": "https://gotra.me/reports/full-analyst/", "ok": True, "status": 200},
            {"url": "https://gotra.me/reports/beta_status.json", "ok": True, "status": 200},
        ],
        "http_ok": True,
        "beta_page_visible": True,
        "raw_accidental_landing_count": 0,
        "object_object_count": 0,
        "python_dict_count": 0,
        "traceback_count": 0,
        "unrendered_json_or_md_count": 0,
        "forbidden_direct_advice": 0,
        "forbidden_secret_raw_provider_leak": 0,
        "forbidden_external_alaya_public_implication": 0,
        "verdict": "pass",
    }


def _fake_fetch(url: str, **_: object) -> dict[str, object]:
    return {"url": url, "ok": True, "status": 200, "body_sample": "{}"}


def _prepare_runtime(tmp_path, monkeypatch):
    active_pointer = tmp_path / "active-path.txt"
    evidence_root = tmp_path / "stage15B-runtime"
    public_status = tmp_path / "beta_status.json"
    monkeypatch.setattr(beta_runtime, "ACTIVE_POINTER_PATH", active_pointer)
    monkeypatch.setattr(beta_runtime, "ENABLEMENT_PATH", tmp_path / "missing-enablement.json")
    monkeypatch.setattr(
        beta_runtime,
        "read_next_systemd_timer_due",
        lambda unit=beta_runtime.TIMER_NAME: {"available": False, "unit": unit},
    )
    monkeypatch.setattr(beta_monitor, "MAIN_HEARTBEAT_PATH", tmp_path / "roadmap-heartbeat.json")
    monkeypatch.setattr(beta_monitor, "MAIN_EVENTS_PATH", tmp_path / "roadmap-events.jsonl")
    monkeypatch.setattr(beta_monitor, "MAIN_SUMMARY_PATH", tmp_path / "roadmap-summary.md")
    start_beta_runtime(
        evidence_root=evidence_root,
        public_status_path=public_status,
        install_scheduler=False,
        now=datetime(2026, 7, 6, 4, 18, 1, tzinfo=timezone.utc),
    )
    active_pointer.write_text(str(evidence_root) + "\n", encoding="utf-8")
    monkeypatch.setattr(beta_monitor, "production_smoke", _passing_production)
    monkeypatch.setattr(beta_monitor, "fetch_url", _fake_fetch)
    return evidence_root, public_status


def test_health_check_uses_reviewed_runtime_enablement_without_counting_output(tmp_path, monkeypatch):
    evidence_root, public_status = _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        beta_monitor,
        "daily_research_job_readiness",
        lambda: {"daily_job_configured": True, "daily_job_status": "configured"},
    )

    result = health_check(
        evidence_root=evidence_root,
        public_status_path=public_status,
        now=datetime(2026, 7, 6, 5, 0, 0, tzinfo=timezone.utc),
    )

    heartbeat = result["heartbeat"]
    assert heartbeat["daily_research_job_configured"] is True
    assert heartbeat["valid_research_output_days"] == 0
    assert heartbeat["unavailable_days"] == 0
    assert all(alert["alert_code"] != "DAILY_RESEARCH_JOB_NOT_READY" for alert in result["alerts"])


def test_health_check_writes_monitor_heartbeat_without_completing_beta(tmp_path, monkeypatch):
    evidence_root, public_status = _prepare_runtime(tmp_path, monkeypatch)

    result = health_check(
        evidence_root=evidence_root,
        public_status_path=public_status,
        now=datetime(2026, 7, 6, 5, 0, 0, tzinfo=timezone.utc),
    )

    heartbeat = json.loads((evidence_root / "monitor" / "monitor-heartbeat.json").read_text())
    assert result["result"] == "needs_repair"
    assert heartbeat["phase"] == "stage15B_beta_monitoring"
    assert heartbeat["beta_started"] is True
    assert heartbeat["beta_clock_started"] is True
    assert heartbeat["beta_complete"] is False
    assert heartbeat["paid_features_enabled"] is False
    assert heartbeat["current_blocker"] == "DAILY_RESEARCH_JOB_NOT_READY"
    assert heartbeat["alert_count"] >= 1
    assert heartbeat["next_daily_run_due_at"] == "2026-07-06T10:30:00Z"
    assert "fallback_schedule" in heartbeat["next_daily_run_due_at_source"]
    assert heartbeat["daily_research_job_configured"] is False
    assert heartbeat["valid_research_output_days"] == 0
    assert heartbeat["unavailable_days"] == 0
    assert heartbeat["failed_output_days"] == 0
    current_alert = json.loads((evidence_root / "monitor" / "current-alert.json").read_text())
    assert current_alert["alert_code"] == "DAILY_RESEARCH_JOB_NOT_READY"
    assert current_alert["beta_clock_preserved"] is True
    assert current_alert["beta_timer_stopped"] is False
    persisted_alerts = [
        json.loads(line)
        for line in (evidence_root / "monitor" / "alerts.jsonl").read_text().splitlines()
    ]
    assert {alert["alert_code"] for alert in persisted_alerts} >= {
        "DAILY_RESEARCH_JOB_NOT_READY",
        "MONITOR_HEARTBEAT_STALE",
    }
    assert (evidence_root / "monitor" / "monitor-events.jsonl").exists()


def test_daily_report_dry_run_preserves_beta_in_progress_boundary(tmp_path, monkeypatch):
    evidence_root, public_status = _prepare_runtime(tmp_path, monkeypatch)

    payload = daily_report(
        evidence_root=evidence_root,
        public_status_path=public_status,
        dry_run=True,
        now=datetime(2026, 7, 6, 5, 30, 0, tzinfo=timezone.utc),
    )

    assert payload["dry_run"] is True
    assert payload["elapsed_days"] == 0
    assert payload["beta_complete"] is False
    assert "daily-reports/2026-07-06.md" in payload["report_path"]
    assert not (evidence_root / "monitor" / "daily-reports" / "2026-07-06.md").exists()


def test_daily_report_writes_chinese_report_and_summary(tmp_path, monkeypatch):
    evidence_root, public_status = _prepare_runtime(tmp_path, monkeypatch)

    payload = daily_report(
        evidence_root=evidence_root,
        public_status_path=public_status,
        now=datetime(2026, 7, 6, 6, 0, 0, tzinfo=timezone.utc),
    )

    report_path = evidence_root / "monitor" / "daily-reports" / "2026-07-06.md"
    report = report_path.read_text(encoding="utf-8")
    assert payload["result"] == "needs_repair"
    assert "# GOTRA Stage 15B 30 天公开 Beta 日报 - 2026-07-06" in report
    assert "BETA_IN_PROGRESS_REAL_TIME_WAIT" in report
    assert "next_daily_run_due_at_source" in report
    assert "daily research job configured: `false`" in report
    assert "valid_research_output_days: `0`" in report
    assert "unavailable_days: `0`" in report
    assert "failed_output_days: `0`" in report
    assert "`blocker` `DAILY_RESEARCH_JOB_NOT_READY`" in report
    assert "这不是 30d beta complete" in report
    assert "不是投资建议" in report
    summary = (tmp_path / "roadmap-summary.md").read_text(encoding="utf-8")
    assert "Stage 15B daily monitor:" in summary
    assert "elapsed_days=0/30" in summary


def test_post_run_check_dry_run_does_not_write_daily_output(tmp_path, monkeypatch):
    evidence_root, public_status = _prepare_runtime(tmp_path, monkeypatch)

    payload = post_run_check(
        evidence_root=evidence_root,
        public_status_path=public_status,
        dry_run=True,
        now=datetime(2026, 7, 6, 10, 50, 0, tzinfo=timezone.utc),
    )

    assert payload["dry_run"] is True
    assert payload["result"] == "needs_repair"
    assert payload["repair_attempted"] is False
    assert not (evidence_root / "monitor" / "post-run" / "2026-07-06.json").exists()


def test_monitor_systemd_units_define_three_monitor_timers(tmp_path):
    units = build_monitor_systemd_units(tmp_path)

    assert "daily-report" in units[beta_monitor.MONITOR_DAILY_REPORT_SERVICE]
    assert "OnCalendar=*-*-* 09:30:00" in units[beta_monitor.MONITOR_DAILY_REPORT_TIMER]
    assert "post-run-check" in units[beta_monitor.MONITOR_POST_RUN_SERVICE]
    assert "OnCalendar=*-*-* 18:50:00" in units[beta_monitor.MONITOR_POST_RUN_TIMER]
    assert "health-check" in units[beta_monitor.MONITOR_HEALTH_SERVICE]
    assert "OnCalendar=*:0/10" in units[beta_monitor.MONITOR_HEALTH_TIMER]
