"""Stage 15B public beta runtime helpers.

This module starts and monitors the 30-day beta clock. It does not fabricate
research output, enable paid access, or claim launch readiness.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gotra.beta_readiness import load_beta_universe


PUBLIC_BETA_STATUS_SCHEMA = "gotra.public_beta.status.v1"
BETA_START_SCHEMA = "gotra.launch.beta_start.v1"
BETA_HEARTBEAT_SCHEMA = "gotra.launch.beta_heartbeat.v1"
BETA_DAILY_EVENT_SCHEMA = "gotra.launch.beta_daily_event.v1"
DEFAULT_EVIDENCE_PARENT = Path("/tmp/gotra-launch-roadmap-evidence")
ACTIVE_POINTER_PATH = DEFAULT_EVIDENCE_PARENT / "stage15B-beta-active-path.txt"
PUBLIC_STATUS_PATH = Path("/var/www/gotra-public-ledger/reports/beta_status.json")
SERVICE_NAME = "gotra-stage15b-beta.service"
TIMER_NAME = "gotra-stage15b-beta.timer"
SERVICE_PATH = Path("/etc/systemd/system") / SERVICE_NAME
TIMER_PATH = Path("/etc/systemd/system") / TIMER_NAME
REQUIRED_DAYS = 30
REMAINING_REVIEW_ITEMS = [
    "Full Analyst public sample withheld pending fresh real v4 canary",
    "Backend/private external Alaya client references remain P1 before formal/paid readiness",
    "npm audit 17 moderate dev-only/transitive vulnerabilities remain review items",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def default_evidence_root(now: datetime | None = None) -> Path:
    value = now or utc_now()
    stamp = value.strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_EVIDENCE_PARENT / f"stage15B-30d-beta-runtime-{stamp}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def boundary() -> dict[str, bool]:
    return {
        "not_30d_complete": True,
        "not_launch_ready": True,
        "not_paid_ready": True,
        "not_investment_advice": True,
        "not_trading_signal": True,
        "no_target_price": True,
        "no_position_sizing": True,
        "no_return_promise": True,
        "no_performance_proof": True,
        "no_science_public_proof": True,
        "alaya_internal_only": True,
    }


def elapsed_days(started_at: str, *, now: datetime | None = None) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    current = now or utc_now()
    return max(0, int((current - start).total_seconds() // 86400))


def next_daily_run_due_at(now: datetime | None = None) -> str:
    current = now or utc_now()
    candidate = current.replace(hour=18, minute=30, second=0, microsecond=0)
    if candidate <= current:
        candidate = candidate + timedelta(days=1)
    return candidate.isoformat().replace("+00:00", "Z")


def ensure_runtime_dirs(evidence_root: Path) -> None:
    for child in ("daily-runs", "weekly-reports", "production-smoke-start", "screenshots-start", "systemd"):
        (evidence_root / child).mkdir(parents=True, exist_ok=True)


def build_systemd_units(evidence_root: Path, *, script_path: Path | None = None) -> dict[str, str]:
    script = script_path or Path(__file__).resolve().parents[1] / "scripts" / "gotra_beta_runtime.py"
    python = Path(os.environ.get("GOTRA_PYTHON", "/opt/gotra/.venv/bin/python"))
    log_path = evidence_root / "beta-runtime-systemd.log"
    service = f"""[Unit]
Description=GOTRA Stage 15B public beta daily event writer
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/gotra
Environment=PYTHONUNBUFFERED=1
ExecStart={python} {script} run-once
StandardOutput=append:{log_path}
StandardError=append:{log_path}
"""
    timer = """[Unit]
Description=Run GOTRA Stage 15B public beta daily event writer

[Timer]
OnCalendar=*-*-* 18:30:00
Persistent=true
Unit=gotra-stage15b-beta.service

[Install]
WantedBy=timers.target
"""
    return {"service": service, "timer": timer, "log_path": str(log_path)}


def write_systemd_definition(evidence_root: Path) -> dict[str, Any]:
    units = build_systemd_units(evidence_root)
    systemd_dir = evidence_root / "systemd"
    service_copy = systemd_dir / SERVICE_NAME
    timer_copy = systemd_dir / TIMER_NAME
    service_copy.write_text(units["service"], encoding="utf-8")
    timer_copy.write_text(units["timer"], encoding="utf-8")
    return {
        "service_name": SERVICE_NAME,
        "timer_name": TIMER_NAME,
        "service_path": str(SERVICE_PATH),
        "timer_path": str(TIMER_PATH),
        "service_template": str(service_copy),
        "timer_template": str(timer_copy),
        "start_command": "systemctl enable --now gotra-stage15b-beta.timer",
        "status_command": "systemctl status gotra-stage15b-beta.timer --no-pager",
        "disable_command": "systemctl disable --now gotra-stage15b-beta.timer",
        "log_path": units["log_path"],
        "next_run_time": "daily at 18:30 server local time",
        "failure_behavior": "systemd records failure; runtime preserves beta evidence and keeps no-fabrication status",
        "evidence_write_path": str(evidence_root),
    }


def install_systemd_timer(evidence_root: Path) -> dict[str, Any]:
    if shutil.which("systemctl") is None:
        raise RuntimeError("systemd_unavailable")
    definition = write_systemd_definition(evidence_root)
    systemd_dir = evidence_root / "systemd"
    SERVICE_PATH.write_text((systemd_dir / SERVICE_NAME).read_text(encoding="utf-8"), encoding="utf-8")
    TIMER_PATH.write_text((systemd_dir / TIMER_NAME).read_text(encoding="utf-8"), encoding="utf-8")
    commands = [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "--now", TIMER_NAME],
    ]
    results = []
    for command in commands:
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        results.append({"command": command, "returncode": completed.returncode, "output": completed.stdout[-2000:]})
        if completed.returncode != 0:
            raise RuntimeError(f"systemd_command_failed:{' '.join(command)}:{completed.stdout[-400:]}")
    definition["installed"] = True
    definition["install_results"] = results
    return definition


def systemd_status() -> dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"available": False}
    result = subprocess.run(
        ["systemctl", "is-active", TIMER_NAME],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    list_result = subprocess.run(
        ["systemctl", "list-timers", TIMER_NAME, "--no-pager", "--all"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "available": True,
        "timer_name": TIMER_NAME,
        "is_active_rc": result.returncode,
        "is_active": result.stdout.strip(),
        "list_timers": list_result.stdout[-4000:],
    }


def runtime_contract(evidence_root: Path, public_status_path: Path) -> dict[str, Any]:
    return {
        "schema": "gotra.launch.beta_runtime_contract.v1",
        "stage": "15B_30d_public_beta_runtime",
        "documented_start_command": "/opt/gotra/.venv/bin/python scripts/gotra_beta_runtime.py start --day0",
        "documented_status_command": "/opt/gotra/.venv/bin/python scripts/gotra_beta_runtime.py status",
        "documented_stop_disable_command": "/opt/gotra/.venv/bin/python scripts/gotra_beta_runtime.py disable",
        "daily_event_writer": "/opt/gotra/.venv/bin/python scripts/gotra_beta_runtime.py run-once",
        "heartbeat_writer": "/opt/gotra/.venv/bin/python scripts/gotra_beta_runtime.py write-heartbeat",
        "public_beta_status_artifact": str(public_status_path),
        "active_pointer": str(ACTIVE_POINTER_PATH),
        "evidence_root": str(evidence_root),
        "scheduler": write_systemd_definition(evidence_root),
        "no_fabrication": True,
        "paid_features_enabled": False,
        "boundary": boundary(),
    }


def build_public_status(
    start_payload: dict[str, Any],
    *,
    last_daily_event_at: str | None = None,
    last_daily_run_status: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    started_at = str(start_payload["started_at"])
    days = elapsed_days(started_at, now=now)
    return {
        "schema": PUBLIC_BETA_STATUS_SCHEMA,
        "beta_started": True,
        "beta_clock_started": True,
        "started_at": started_at,
        "elapsed_days": days,
        "required_days": REQUIRED_DAYS,
        "beta_complete": days >= REQUIRED_DAYS,
        "paid_features_enabled": False,
        "free_beta": True,
        "last_daily_event_at": last_daily_event_at or start_payload.get("last_daily_event_at") or started_at,
        "last_daily_run_status": last_daily_run_status or start_payload.get("last_daily_run_status") or "day0_started_no_daily_research_run_yet",
        "next_daily_run_due_at": next_daily_run_due_at(now=now),
        "no_fabrication": True,
        "not_launch_ready": True,
        "not_paid_ready": True,
        "not_investment_advice": True,
        "not_trading_signal": True,
        "remaining_review_items": REMAINING_REVIEW_ITEMS,
        "boundary": boundary(),
    }


def beta_summary_markdown(status: dict[str, Any]) -> str:
    return f"""# GOTRA Stage 15B 30d Public Beta Runtime

Current result: `BETA_IN_PROGRESS_REAL_TIME_WAIT`

- beta_started: `{str(status['beta_started']).lower()}`
- beta_clock_started: `{str(status['beta_clock_started']).lower()}`
- started_at: `{status['started_at']}`
- elapsed_days: `{status['elapsed_days']}`
- required_days: `{status['required_days']}`
- beta_complete: `{str(status['beta_complete']).lower()}`
- paid_features_enabled: `{str(status['paid_features_enabled']).lower()}`
- last_daily_run_status: `{status['last_daily_run_status']}`

This is a 30-day public beta runtime state, not 30d complete, not full launch,
not paid ready, not investment advice, not a trading signal, and not
science/public/performance proof. Alaya is GOTRA internal cognition flywheel /
memory / readback only.
"""


def start_beta_runtime(
    *,
    evidence_root: Path | None = None,
    public_status_path: Path = PUBLIC_STATUS_PATH,
    install_scheduler: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    root = evidence_root or default_evidence_root(current)
    ensure_runtime_dirs(root)
    universe = load_beta_universe()
    started_at = current.isoformat().replace("+00:00", "Z")
    start_payload = {
        "schema": BETA_START_SCHEMA,
        "stage": "15B_30d_public_beta_runtime",
        "beta_started": True,
        "beta_clock_started": True,
        "started_at": started_at,
        "day_0": True,
        "required_elapsed_days": REQUIRED_DAYS,
        "complete": False,
        "universe_count": len(universe["universe"]),
        "not_launch_ready": True,
        "not_paid_ready": True,
        "not_investment_advice": True,
        "not_trading_signal": True,
        "review_result_authorizing_start": "TEAM_REVIEW_APPROVES_WITH_P1_REVIEW_ITEMS_STAGE15B_30D_BETA_START",
        "remaining_review_items": REMAINING_REVIEW_ITEMS,
        "last_daily_event_at": started_at,
        "last_daily_run_status": "day0_started_no_daily_research_run_yet",
        "boundary": boundary(),
    }
    scheduler = write_systemd_definition(root)
    if install_scheduler:
        scheduler = install_systemd_timer(root)

    write_json(root / "beta-start.json", start_payload)
    write_json(root / "runtime-contract.json", runtime_contract(root, public_status_path))
    event = {
        "schema": BETA_DAILY_EVENT_SCHEMA,
        "event_type": "beta_runtime_started",
        "timestamp": started_at,
        "day_index": 0,
        "run_status": "day0_started_no_daily_research_run_yet",
        "publication_count": 0,
        "needs_review_count": 0,
        "data_gap_count": 0,
        "blocked_count": 0,
        "no_fabrication": True,
        "paid_features_enabled": False,
        "boundary": boundary(),
    }
    append_jsonl(root / "beta-daily-events.jsonl", event)
    status = build_public_status(start_payload, now=current)
    write_json(public_status_path, status)
    write_json(root / "beta-heartbeat.json", build_beta_heartbeat(root, status, current))
    (root / "beta-summary.md").write_text(beta_summary_markdown(status), encoding="utf-8")
    (root / "weekly-reports" / "beta-weekly-report-template.md").write_text(weekly_report_template(started_at), encoding="utf-8")
    ACTIVE_POINTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_POINTER_PATH.write_text(str(root) + "\n", encoding="utf-8")
    write_json(root / "scheduler-status.json", {"scheduler": scheduler, "systemd_status": systemd_status()})
    return {"root": str(root), "status": status, "scheduler": scheduler}


def active_evidence_root(pointer_path: Path = ACTIVE_POINTER_PATH) -> Path:
    if not pointer_path.exists():
        raise RuntimeError("beta_runtime_not_started")
    root = Path(pointer_path.read_text(encoding="utf-8").strip())
    if not (root / "beta-start.json").exists():
        raise RuntimeError("beta_runtime_active_pointer_invalid")
    return root


def load_start_payload(evidence_root: Path | None = None) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    return read_json(root / "beta-start.json")


def build_beta_heartbeat(evidence_root: Path, status: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    return {
        "schema": BETA_HEARTBEAT_SCHEMA,
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "phase": "beta_in_progress_real_time_wait",
        "roadmap_stage": "15B_30d_public_beta_runtime",
        "current_gate": "30d_real_time_beta",
        "evidence_root": str(evidence_root),
        "beta_started": True,
        "beta_clock_started": True,
        "started_at": status["started_at"],
        "elapsed_days": status["elapsed_days"],
        "required_days": REQUIRED_DAYS,
        "beta_complete": False,
        "last_daily_run_status": status["last_daily_run_status"],
        "next_daily_run_due_at": status["next_daily_run_due_at"],
        "current_blocker": None,
        "boundary": boundary(),
    }


def write_heartbeat(*, evidence_root: Path | None = None, public_status_path: Path = PUBLIC_STATUS_PATH) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    start_payload = read_json(root / "beta-start.json")
    status = build_public_status(start_payload)
    write_json(public_status_path, status)
    heartbeat = build_beta_heartbeat(root, status)
    write_json(root / "beta-heartbeat.json", heartbeat)
    (root / "beta-summary.md").write_text(beta_summary_markdown(status), encoding="utf-8")
    return heartbeat


def run_once(*, dry_run: bool = False, evidence_root: Path | None = None, public_status_path: Path = PUBLIC_STATUS_PATH) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    start_file = root / "beta-start.json"
    if dry_run and not start_file.exists():
        now = utc_now()
        return {
            "schema": BETA_DAILY_EVENT_SCHEMA,
            "event_type": "beta_daily_runtime_event_dry_run_preview",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "day_index": None,
            "run_status": "beta_not_started_dry_run_preview",
            "publication_count": 0,
            "needs_review_count": 0,
            "data_gap_count": 0,
            "blocked_count": 0,
            "review_due_at_schedule": [1, 7, 30, 90],
            "track_record_ledger_integrity": "not_checked_before_beta_start",
            "public_safety_status": "research_only_boundary_preserved",
            "alaya_internal_readback_status": "not_run_before_beta_start",
            "beta_started": False,
            "beta_clock_started": False,
            "no_fabrication": True,
            "paid_features_enabled": False,
            "notes": "Dry-run preview only. It does not start the beta clock and does not fabricate daily research output.",
            "boundary": boundary(),
        }
    start_payload = read_json(start_file)
    now = utc_now()
    status_text = "unavailable_no_live_daily_research_job_configured"
    event = {
        "schema": BETA_DAILY_EVENT_SCHEMA,
        "event_type": "beta_daily_runtime_event",
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "day_index": elapsed_days(str(start_payload["started_at"]), now=now),
        "run_status": status_text,
        "publication_count": 0,
        "needs_review_count": 0,
        "data_gap_count": 0,
        "blocked_count": 0,
        "review_due_at_schedule": [1, 7, 30, 90],
        "track_record_ledger_integrity": "unavailable_no_live_research_ledger_yet",
        "public_safety_status": "research_only_boundary_preserved",
        "alaya_internal_readback_status": "not_run_for_daily_unavailable_event",
        "no_fabrication": True,
        "paid_features_enabled": False,
        "notes": "Daily research job is not fabricated by the beta runtime. This event preserves no-fabrication state until a real daily run is configured.",
        "boundary": boundary(),
    }
    if dry_run:
        return event
    append_jsonl(root / "beta-daily-events.jsonl", event)
    start_payload["last_daily_event_at"] = event["timestamp"]
    start_payload["last_daily_run_status"] = status_text
    write_json(root / "beta-start.json", start_payload)
    status = build_public_status(start_payload, last_daily_event_at=event["timestamp"], last_daily_run_status=status_text, now=now)
    write_json(public_status_path, status)
    write_json(root / "beta-heartbeat.json", build_beta_heartbeat(root, status, now))
    daily_dir = root / "daily-runs" / now.strftime("%Y-%m-%d")
    daily_dir.mkdir(parents=True, exist_ok=True)
    write_json(daily_dir / "daily-event.json", event)
    (root / "beta-summary.md").write_text(beta_summary_markdown(status), encoding="utf-8")
    return event


def status_payload(*, evidence_root: Path | None = None, public_status_path: Path = PUBLIC_STATUS_PATH) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    start_payload = read_json(root / "beta-start.json")
    status = build_public_status(start_payload)
    public_status = read_json(public_status_path) if public_status_path.exists() else None
    return {
        "stage": "15B_30d_public_beta_runtime",
        "evidence_root": str(root),
        "beta_started": True,
        "beta_clock_started": True,
        "started_at": status["started_at"],
        "elapsed_days": status["elapsed_days"],
        "required_days": REQUIRED_DAYS,
        "beta_complete": False,
        "public_status_path": str(public_status_path),
        "public_status": public_status or status,
        "scheduler": systemd_status(),
        "boundary": boundary(),
    }


def disable_beta_runtime(*, evidence_root: Path | None = None, public_status_path: Path = PUBLIC_STATUS_PATH) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    now = utc_now_iso()
    systemd = {"attempted": False}
    if shutil.which("systemctl"):
        completed = subprocess.run(
            ["systemctl", "disable", "--now", TIMER_NAME],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        systemd = {"attempted": True, "returncode": completed.returncode, "output": completed.stdout[-2000:]}
    event = {
        "schema": BETA_DAILY_EVENT_SCHEMA,
        "event_type": "beta_runtime_disabled",
        "timestamp": now,
        "run_status": "disabled_preserve_evidence",
        "no_fabrication": True,
        "paid_features_enabled": False,
        "boundary": boundary(),
        "systemd": systemd,
    }
    append_jsonl(root / "beta-daily-events.jsonl", event)
    start_payload = read_json(root / "beta-start.json")
    start_payload["last_daily_event_at"] = now
    start_payload["last_daily_run_status"] = "disabled_preserve_evidence"
    write_json(root / "beta-start.json", start_payload)
    status = build_public_status(start_payload, last_daily_event_at=now, last_daily_run_status="disabled_preserve_evidence")
    status["scheduler_disabled"] = True
    write_json(public_status_path, status)
    write_json(root / "beta-heartbeat.json", build_beta_heartbeat(root, status))
    return {"event": event, "status": status}


def weekly_report_template(started_at: str) -> str:
    return f"""# GOTRA Stage 15B Weekly Beta Report

Started at: `{started_at}`

This placeholder must be filled with real beta evidence only:
- daily events present
- publication count
- needs_review count
- data_gap count
- blocked_count
- review coverage
- error/no-fabrication log
- unresolved review items

Boundary: not investment advice, not trading signal, no target price, no
position sizing, no return promise, no performance proof, no science/public
proof, Alaya internal only.
"""
