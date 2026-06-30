"""Write a public-safe monitor status for the full-analyst candidate timer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CANDIDATE_TIMER = "gotra-full-analyst-evening-hk-candidate.timer"
CANDIDATE_SERVICE = "gotra-full-analyst-evening-hk-candidate.service"
STATIC_REPORT_DIR = Path("/var/www/gotra-public-ledger/reports")
STATUS_FILE = "status_full_analyst_evening_hk.json"
MONITOR_FILE = "status_full_analyst_monitor.json"
HEARTBEAT_STALE_SECONDS = 10 * 60
ARTIFACT_STALE_SECONDS = 36 * 60 * 60
ROLLBACK_RUNBOOK_PATH = "ops/runbooks/full_analyst_candidate_rollback.md"
ROLLBACK_RUNBOOK_URL = "https://github.com/amanayayatu-tech/gotra/blob/main/ops/runbooks/full_analyst_candidate_rollback.md"
BOUNDARY = [
    "production canary",
    "not investment advice",
    "not trading signal",
    "not performance proof",
    "not science/public proof",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor GOTRA full-analyst candidate public-safe status.")
    parser.add_argument("--static-dir", type=Path, default=STATIC_REPORT_DIR)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--timer", default=CANDIDATE_TIMER)
    parser.add_argument("--service", default=CANDIDATE_SERVICE)
    parser.add_argument("--heartbeat-stale-seconds", type=int, default=HEARTBEAT_STALE_SECONDS)
    parser.add_argument("--artifact-stale-seconds", type=int, default=ARTIFACT_STALE_SECONDS)
    parser.add_argument("--now", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(UTC)
    output = args.output or args.static_dir / MONITOR_FILE
    monitor = build_monitor(
        static_dir=args.static_dir,
        timer=args.timer,
        service=args.service,
        now=now,
        heartbeat_stale_seconds=max(60, int(args.heartbeat_stale_seconds)),
        artifact_stale_seconds=max(60, int(args.artifact_stale_seconds)),
    )
    write_json_atomic(output, monitor)
    print(json.dumps(monitor, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if monitor["overall_status"] != "failed" else 2


def build_monitor(
    *,
    static_dir: Path,
    timer: str,
    service: str,
    now: datetime,
    heartbeat_stale_seconds: int,
    artifact_stale_seconds: int,
) -> dict[str, Any]:
    status_path = static_dir / STATUS_FILE
    status = read_json(status_path)
    timer_props = systemctl_show(timer)
    service_props = systemctl_show(service)
    latest_run = latest_run_status(
        status=status,
        status_path=status_path,
        now=now,
        heartbeat_stale_seconds=heartbeat_stale_seconds,
        artifact_stale_seconds=artifact_stale_seconds,
    )
    checks = monitor_checks(
        timer_props=timer_props,
        service_props=service_props,
        status=status,
        latest_run=latest_run,
    )
    overall = overall_status(checks)
    codes = status_codes(status=status, checks=checks, latest_run=latest_run)
    return {
        "schema": "gotra.full_analyst.candidate_monitor.v1",
        "generated_at": isoformat(now),
        "overall_status": overall,
        "verdict": {
            "healthy": "PRODUCTION_CANARY_MONITOR_HEALTHY",
            "degraded": "PRODUCTION_CANARY_MONITOR_DEGRADED",
            "failed": "PRODUCTION_CANARY_MONITOR_FAILED",
            "unknown": "PRODUCTION_CANARY_MONITOR_UNKNOWN",
        }[overall],
        "candidate": {
            "timer": timer,
            "service": service,
            "timer_active": timer_props.get("ActiveState") == "active",
            "timer_enabled": timer_props.get("UnitFileState") == "enabled",
            "timer_state": timer_props.get("ActiveState") or "unknown",
            "service_state": service_props.get("ActiveState") or "unknown",
            "service_result": service_props.get("Result") or "unknown",
            "last_run_at": normalize_systemd_timestamp(service_props.get("ExecMainStartTimestamp")),
            "next_run_at": normalize_systemd_timestamp(timer_props.get("NextElapseUSecRealtime")),
            "rollback_mode": "manual_ssh_runbook",
        },
        "latest_run": latest_run,
        "checks": checks,
        "status_codes": codes,
        "links": {
            "status_json": f"/reports/{STATUS_FILE}",
            "report_markdown": f"/reports/{str(status.get('latest_public_report_file') or status.get('report_file') or '').strip() or 'full_analyst_evening_hk_YYYY-MM-DD.md'}",
            "rollback_runbook": ROLLBACK_RUNBOOK_URL,
        },
        "rollback": {
            "mode": "manual_ssh_runbook",
            "runbook_path": ROLLBACK_RUNBOOK_PATH,
            "runbook_url": ROLLBACK_RUNBOOK_URL,
            "candidate_only": True,
            "affects_daily_timers": False,
            "deletes_historical_reports": False,
        },
        "limitations": list(BOUNDARY),
    }


def systemctl_show(unit: str) -> dict[str, str]:
    command = [
        "systemctl",
        "show",
        unit,
        "-p",
        "ActiveState",
        "-p",
        "SubState",
        "-p",
        "Result",
        "-p",
        "UnitFileState",
        "-p",
        "ExecMainStartTimestamp",
        "-p",
        "NextElapseUSecRealtime",
        "--no-pager",
    ]
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=10)
    except Exception:
        return {}
    if result.returncode not in (0, 3):
        return {}
    props: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            props[key] = value.strip()
    return props


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def latest_run_status(
    *,
    status: dict[str, Any],
    status_path: Path,
    now: datetime,
    heartbeat_stale_seconds: int,
    artifact_stale_seconds: int,
) -> dict[str, Any]:
    run_status = optional_string(status.get("run_status") or status.get("status")) or "unknown"
    heartbeat_at = parse_iso(str(status.get("last_heartbeat_utc") or ""))
    artifact_updated_at = file_mtime(status_path)
    heartbeat_age = age_seconds(now, heartbeat_at)
    artifact_age = age_seconds(now, artifact_updated_at)
    heartbeat_required = is_live_status(run_status)
    return {
        "run_id": optional_string(status.get("run_id")),
        "status": run_status,
        "heartbeat_at": isoformat(heartbeat_at) if heartbeat_at else None,
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_required": heartbeat_required,
        "heartbeat_stale": heartbeat_required and (heartbeat_age is None or heartbeat_age > heartbeat_stale_seconds),
        "artifact_updated_at": isoformat(artifact_updated_at) if artifact_updated_at else None,
        "artifact_age_seconds": artifact_age,
        "artifact_stale": artifact_age is None or artifact_age > artifact_stale_seconds,
    }


def monitor_checks(
    *,
    timer_props: dict[str, str],
    service_props: dict[str, str],
    status: dict[str, Any],
    latest_run: dict[str, Any],
) -> dict[str, str]:
    timer_active = timer_props.get("ActiveState") == "active"
    timer_enabled = timer_props.get("UnitFileState") == "enabled"
    service_state = service_props.get("ActiveState") or "unknown"
    service_result = service_props.get("Result") or "unknown"
    public_scan = str(status.get("public_scan_status") or "").lower()
    alaya_readback = str(status.get("alaya_readback_status") or "").lower()
    heartbeat = heartbeat_check(latest_run)
    return {
        "timer": "ok" if timer_active and timer_enabled else "fail" if timer_props else "unknown",
        "service": "fail" if service_state == "failed" or service_result == "failed" else "ok" if service_props else "unknown",
        "heartbeat": heartbeat,
        "artifact": "missing" if latest_run["artifact_age_seconds"] is None else "stale" if latest_run["artifact_stale"] else "ok",
        "public_scan": "ok" if public_scan == "ok" else "fail" if public_scan == "failed" else "unknown",
        "alaya_readback": "ok" if alaya_readback in {"verified", "not_applicable", "skipped"} else "fail" if alaya_readback in {"failed", "mismatch"} else "unknown",
    }


def overall_status(checks: dict[str, str]) -> str:
    hard_fail = {"timer": {"fail"}, "service": {"fail"}, "public_scan": {"fail"}, "alaya_readback": {"fail"}}
    if any(checks.get(key) in values for key, values in hard_fail.items()):
        return "failed"
    if any(value in {"missing", "stale", "unknown"} for value in checks.values()):
        return "degraded"
    return "healthy"


def status_codes(*, status: dict[str, Any], checks: dict[str, str], latest_run: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    run_status = optional_string(status.get("run_status") or status.get("status")) or "unknown"
    normalized_run_status = normalize_status(run_status)
    supported = {
        "completed",
        "completed_with_review_items",
        "completed_with_allowed_data_gaps",
        "partial",
        "failed",
        "blocked",
        "running",
        "in_progress",
        "processing",
        "starting",
        "started",
        "unknown",
    }
    codes.append(normalized_run_status if normalized_run_status in supported else "unknown")
    if latest_run["heartbeat_stale"]:
        codes.append("heartbeat_stale")
    if latest_run["artifact_stale"]:
        codes.append("artifact_stale")
    if checks.get("service") == "fail":
        codes.append("service_failed")
    if checks.get("timer") == "fail":
        codes.append("timer_inactive")
    if checks.get("public_scan") == "fail":
        codes.append("public_scan_failed")
    if checks.get("alaya_readback") == "fail":
        codes.append("alaya_readback_failed")
    return sorted(set(codes), key=codes.index)


def heartbeat_check(latest_run: dict[str, Any]) -> str:
    if latest_run["heartbeat_required"]:
        return "stale" if latest_run["heartbeat_stale"] else "ok"
    if normalize_status(str(latest_run["status"])) == "unknown":
        return "unknown"
    return "not_required"


def file_mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def parse_iso(value: str) -> datetime | None:
    if not value or value.lower() == "null":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def is_live_status(value: str) -> bool:
    normalized = normalize_status(value)
    live_statuses = {"running", "in_progress", "processing", "starting", "started"}
    return normalized in live_statuses or normalized.startswith(("running_", "in_progress_", "processing_", "starting_"))


def normalize_status(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_systemd_timestamp(value: str | None) -> str | None:
    if not value or value.lower() in {"n/a", "0"}:
        return None
    try:
        parsed = datetime.strptime(value, "%a %Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return value
    return isoformat(parsed.replace(tzinfo=UTC))


def age_seconds(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    return max(0, int((now.astimezone(UTC) - value.astimezone(UTC)).total_seconds()))


def optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def isoformat(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    path.chmod(0o644)


if __name__ == "__main__":
    sys.exit(main())
