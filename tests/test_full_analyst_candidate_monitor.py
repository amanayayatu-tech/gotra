import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import full_analyst_candidate_monitor as monitor


def write_status(tmp_path: Path, *, heartbeat_at: datetime, public_scan: str = "ok", readback: str = "verified") -> Path:
    path = tmp_path / "status_full_analyst_evening_hk.json"
    path.write_text(
        json.dumps(
            {
                "run_id": "full_analyst_evening_hk_candidate_test",
                "run_status": "completed",
                "last_heartbeat_utc": monitor.isoformat(heartbeat_at),
                "latest_public_report_file": "full_analyst_evening_hk_2026-06-30.md",
                "public_scan_status": public_scan,
                "alaya_readback_status": readback,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_monitor_reports_healthy_candidate(monkeypatch, tmp_path: Path) -> None:
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    write_status(tmp_path, heartbeat_at=now - timedelta(seconds=90))

    def fake_systemctl(unit: str) -> dict[str, str]:
        if unit.endswith(".timer"):
            return {"ActiveState": "active", "UnitFileState": "enabled", "NextElapseUSecRealtime": "Tue 2026-06-30 19:30:00 CST"}
        return {"ActiveState": "inactive", "Result": "success", "ExecMainStartTimestamp": "Tue 2026-06-30 15:25:55 CST"}

    monkeypatch.setattr(monitor, "systemctl_show", fake_systemctl)

    payload = monitor.build_monitor(
        static_dir=tmp_path,
        timer="gotra-full-analyst-evening-hk-candidate.timer",
        service="gotra-full-analyst-evening-hk-candidate.service",
        now=now,
        heartbeat_stale_seconds=600,
        artifact_stale_seconds=3600,
    )

    assert payload["overall_status"] == "healthy"
    assert payload["verdict"] == "PRODUCTION_CANARY_MONITOR_HEALTHY"
    assert payload["checks"]["timer"] == "ok"
    assert payload["checks"]["public_scan"] == "ok"
    assert payload["latest_run"]["run_id"] == "full_analyst_evening_hk_candidate_test"
    assert payload["links"]["status_json"] == "/reports/status_full_analyst_evening_hk.json"
    assert payload["rollback"]["mode"] == "manual_ssh_runbook"
    assert payload["rollback"]["affects_daily_timers"] is False


def test_monitor_marks_stale_heartbeat_as_degraded(monkeypatch, tmp_path: Path) -> None:
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    write_status(tmp_path, heartbeat_at=now - timedelta(minutes=30))
    monkeypatch.setattr(
        monitor,
        "systemctl_show",
        lambda unit: {"ActiveState": "active", "UnitFileState": "enabled"} if unit.endswith(".timer") else {"ActiveState": "inactive", "Result": "success"},
    )

    payload = monitor.build_monitor(
        static_dir=tmp_path,
        timer="candidate.timer",
        service="candidate.service",
        now=now,
        heartbeat_stale_seconds=600,
        artifact_stale_seconds=3600,
    )

    assert payload["overall_status"] == "degraded"
    assert payload["checks"]["heartbeat"] == "stale"
    assert payload["latest_run"]["heartbeat_stale"] is True
    assert "heartbeat_stale" in payload["status_codes"]


def test_monitor_marks_public_scan_failure_as_failed(monkeypatch, tmp_path: Path) -> None:
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    write_status(tmp_path, heartbeat_at=now, public_scan="failed")
    monkeypatch.setattr(
        monitor,
        "systemctl_show",
        lambda unit: {"ActiveState": "active", "UnitFileState": "enabled"} if unit.endswith(".timer") else {"ActiveState": "inactive", "Result": "success"},
    )

    payload = monitor.build_monitor(
        static_dir=tmp_path,
        timer="candidate.timer",
        service="candidate.service",
        now=now,
        heartbeat_stale_seconds=600,
        artifact_stale_seconds=3600,
    )

    assert payload["overall_status"] == "failed"
    assert payload["checks"]["public_scan"] == "fail"
    assert payload["verdict"] == "PRODUCTION_CANARY_MONITOR_FAILED"
    assert "public_scan_failed" in payload["status_codes"]
