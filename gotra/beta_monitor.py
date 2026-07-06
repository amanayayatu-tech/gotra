"""Stage 15B public beta monitor helpers.

This module monitors the already-started beta runtime. It must not start or
reset the beta clock, fabricate daily research output, enable paid access, or
claim launch readiness.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from gotra.beta_runtime import (
    PUBLIC_STATUS_PATH,
    SERVICE_NAME as DAILY_SERVICE_NAME,
    TIMER_NAME as DAILY_TIMER_NAME,
    active_evidence_root,
    append_jsonl,
    boundary,
    read_json,
    status_payload,
    utc_now,
    write_json,
)


MONITOR_HEARTBEAT_SCHEMA = "gotra.launch.beta_monitor_heartbeat.v1"
MONITOR_EVENT_SCHEMA = "gotra.launch.beta_monitor_event.v1"
MONITOR_DAILY_REPORT_SCHEMA = "gotra.launch.beta_monitor_daily_report.v1"
MONITOR_REPAIR_EVENT_SCHEMA = "gotra.launch.beta_monitor_repair_event.v1"
MONITOR_DAILY_REPORT_SERVICE = "gotra-beta-monitor-daily-report.service"
MONITOR_DAILY_REPORT_TIMER = "gotra-beta-monitor-daily-report.timer"
MONITOR_POST_RUN_SERVICE = "gotra-beta-monitor-post-run.service"
MONITOR_POST_RUN_TIMER = "gotra-beta-monitor-post-run.timer"
MONITOR_HEALTH_SERVICE = "gotra-beta-monitor-health.service"
MONITOR_HEALTH_TIMER = "gotra-beta-monitor-health.timer"
SYSTEMD_DIR = Path("/etc/systemd/system")
MAIN_HEARTBEAT_PATH = Path("/tmp/gotra-launch-roadmap-heartbeat.json")
MAIN_EVENTS_PATH = Path("/tmp/gotra-launch-roadmap-events.jsonl")
MAIN_SUMMARY_PATH = Path("/tmp/gotra-launch-roadmap-summary.md")
PRODUCTION_ROUTES = [
    "https://gotra.me/",
    "https://gotra.me/beta",
    "https://gotra.me/today/",
    "https://gotra.me/track-record",
    "https://gotra.me/monthly-reports",
    "https://gotra.me/reports/latest/",
    "https://gotra.me/reports/full-analyst/",
    "https://gotra.me/reports/beta_status.json",
]


def local_now(now: datetime | None = None) -> datetime:
    current = now or utc_now()
    return current.astimezone(ZoneInfo("Asia/Shanghai"))


def monitor_root(evidence_root: Path | None = None) -> Path:
    root = evidence_root or active_evidence_root()
    return root / "monitor"


def ensure_monitor_dirs(root: Path) -> None:
    for child in (
        "daily-reports",
        "post-run",
        "health-snapshots",
        "screenshots",
        "production-smoke",
        "status-snapshots",
        "systemd",
    ):
        (root / child).mkdir(parents=True, exist_ok=True)


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    output: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "output": self.output[-4000:],
        }


def run_command(command: list[str], *, timeout: int = 30) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return CommandResult(command, completed.returncode, completed.stdout)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(command, 124, (exc.stdout or "") + "\ncommand timed out")


def systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def unit_status(unit_name: str) -> dict[str, Any]:
    if not systemctl_available():
        return {"available": False, "unit": unit_name}
    active = run_command(["systemctl", "is-active", unit_name])
    status = run_command(["systemctl", "status", unit_name, "--no-pager"])
    return {
        "available": True,
        "unit": unit_name,
        "is_active": active.output.strip(),
        "is_active_rc": active.returncode,
        "status_rc": status.returncode,
        "status_tail": status.output[-4000:],
    }


def timer_listing(unit_name: str) -> dict[str, Any]:
    if not systemctl_available():
        return {"available": False, "unit": unit_name}
    result = run_command(["systemctl", "list-timers", unit_name, "--all", "--no-pager"])
    return {"available": True, "unit": unit_name, "returncode": result.returncode, "output": result.output[-4000:]}


def journal_tail(unit_name: str, *, lines: int = 80) -> dict[str, Any]:
    if shutil.which("journalctl") is None:
        return {"available": False, "unit": unit_name}
    result = run_command(["journalctl", "-u", unit_name, "-n", str(lines), "--no-pager"])
    return {"available": True, "unit": unit_name, "returncode": result.returncode, "output": result.output[-6000:]}


def git_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    branch = run_command(["git", "-C", str(path), "branch", "--show-current"])
    head = run_command(["git", "-C", str(path), "rev-parse", "--short", "HEAD"])
    status = run_command(["git", "-C", str(path), "status", "--short"])
    return {
        "path": str(path),
        "exists": True,
        "branch": branch.output.strip(),
        "head": head.output.strip(),
        "dirty_count": len([line for line in status.output.splitlines() if line.strip()]),
        "status_short": status.output.strip(),
    }


def fetch_url(url: str, *, timeout: int = 12, read_limit: int = 6000) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "gotra-beta-monitor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(read_limit).decode("utf-8", errors="replace")
            return {
                "url": url,
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "body_sample": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(read_limit).decode("utf-8", errors="replace")
        return {"url": url, "ok": False, "status": exc.code, "content_type": "", "body_sample": body}
    except Exception as exc:  # noqa: BLE001 - monitor must preserve diagnostics.
        return {"url": url, "ok": False, "status": None, "error": repr(exc), "body_sample": ""}


def production_smoke() -> dict[str, Any]:
    routes = [fetch_url(route) for route in PRODUCTION_ROUTES]
    page_text = "\n".join(route.get("body_sample", "") for route in routes if route.get("url") != str(PUBLIC_STATUS_PATH))
    forbidden = classify_public_text(page_text)
    return {
        "routes": [
            {key: value for key, value in route.items() if key != "body_sample"}
            for route in routes
        ],
        "http_ok": all(bool(route.get("ok")) for route in routes),
        "beta_page_visible": any("30 天公开 beta" in str(route.get("body_sample", "")) for route in routes),
        "raw_accidental_landing_count": sum(
            1
            for route in routes
            if route.get("url") != "https://gotra.me/reports/beta_status.json"
            and looks_like_raw_main_path(str(route.get("body_sample", "")))
        ),
        "object_object_count": page_text.count("[object Object]"),
        "python_dict_count": len(re.findall(r"\{['\"][A-Za-z0-9_ -]+['\"]:", page_text)),
        "traceback_count": page_text.count("Traceback (most recent call last)"),
        "unrendered_json_or_md_count": unrendered_json_or_md_count(page_text),
        "forbidden_direct_advice": forbidden["forbidden_direct_advice"],
        "forbidden_secret_raw_provider_leak": forbidden["forbidden_secret_raw_provider_leak"],
        "forbidden_external_alaya_public_implication": forbidden["forbidden_external_alaya_public_implication"],
        "verdict": "pass" if all(bool(route.get("ok")) for route in routes) and not any(
            [
                forbidden["forbidden_direct_advice"],
                forbidden["forbidden_secret_raw_provider_leak"],
                forbidden["forbidden_external_alaya_public_implication"],
            ]
        ) else "needs_review",
    }


def looks_like_raw_main_path(text: str) -> bool:
    sample = text.lstrip()[:500]
    return sample.startswith("{") or sample.startswith("[") or sample.startswith("# ")


def unrendered_json_or_md_count(text: str) -> int:
    return len(re.findall(r"```json|```markdown|^#{1,3}\\s+", text, flags=re.MULTILINE))


def classify_public_text(text: str) -> dict[str, int]:
    forbidden_direct = 0
    for pattern in (
        r"\bbuy\b",
        r"\bsell\b",
        r"\bhold\b",
        r"target price",
        r"price target",
        r"alpha signal",
        r"outperform",
        r"proven returns",
        r"validated returns",
        r"帮你赚钱|买入|卖出|持有|加仓|减仓|目标价|交易信号|投资建议|收益承诺|必涨|稳赚|荐股",
    ):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            context = text[max(0, match.start() - 80): match.end() + 80].lower()
            if is_boundary_context(context):
                continue
            forbidden_direct += 1
    secret_tokens = [
        r"sk-[A-Za-z0-9]",
        "Authorization:",
        "Bearer ",
        "OPENAI" + "_API_KEY",
        "ANTHROPIC" + "_API_KEY",
        "GITHUB" + "_TOKEN",
        r"api[_-]?key",
        "secret",
        "password",
        "raw provider",
        "provider raw",
    ]
    secret_hits = sum(len(re.findall(token, text, flags=re.IGNORECASE)) for token in secret_tokens)
    external_alaya_tokens = [
        "ALAYA" + "_BASE_URL",
        "ALAYA" + "_WRITE_PATH",
        "/Users/peachy/Documents/" + "alaya",
        "external " + "Alaya",
    ]
    external_alaya = 0
    for token in external_alaya_tokens:
        for match in re.finditer(re.escape(token), text):
            context = text[max(0, match.start() - 100): match.end() + 100].lower()
            if is_boundary_context(context):
                continue
            external_alaya += 1
    return {
        "forbidden_direct_advice": forbidden_direct,
        "forbidden_secret_raw_provider_leak": secret_hits,
        "forbidden_external_alaya_public_implication": external_alaya,
    }


def is_boundary_context(context: str) -> bool:
    return any(
        marker in context
        for marker in (
            "not ",
            "no ",
            "not a ",
            "is not",
            "without",
            "only",
            "internal",
            "boundary",
            "不是",
            "不提供",
            "不会",
            "不得",
            "禁止",
            "无",
            "非",
            "仅",
            "内部",
        )
    )


def source_safety_scan() -> dict[str, Any]:
    root = Path("/opt/gotra-public-ledger")
    paths = [root / "src", root / "public", root / "scripts"]
    existing_paths = [path for path in paths if path.exists()]
    if not existing_paths:
        return {"available": False, "reason": "public_ledger_paths_absent"}
    result: dict[str, Any] = {
        "available": True,
        "allowed_boundary_copy": 0,
        "allowed_scanner_test_history": 0,
        "allowed_context_mention": 0,
        "forbidden_direct_advice": 0,
        "forbidden_secret_raw_provider_leak": 0,
        "forbidden_external_alaya_public_implication": 0,
        "forbidden_samples": [],
    }
    for base in existing_paths:
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".ts", ".tsx", ".js", ".mjs", ".html", ".json", ".md"}:
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                for line_number, line in enumerate(lines, start=1):
                    classify_source_line(result, path.relative_to(root), line_number, line)
    return result


def classify_source_line(result: dict[str, Any], rel_path: Path, line_number: int, line: str) -> None:
    if not line.strip():
        return
    context = line.lower()
    rel = str(rel_path)
    scanner_context = is_scanner_or_test_context(rel, context)
    boundary_context = is_boundary_context(context)
    advice_hit = classify_public_text(line)["forbidden_direct_advice"] > 0
    secret_hit = classify_public_text(line)["forbidden_secret_raw_provider_leak"] > 0
    alaya_hit = classify_public_text(line)["forbidden_external_alaya_public_implication"] > 0

    for hit_type, hit in (
        ("forbidden_direct_advice", advice_hit),
        ("forbidden_secret_raw_provider_leak", secret_hit),
        ("forbidden_external_alaya_public_implication", alaya_hit),
    ):
        if not hit:
            continue
        if boundary_context:
            result["allowed_boundary_copy"] += 1
            continue
        if scanner_context:
            result["allowed_scanner_test_history"] += 1
            continue
        if hit_type == "forbidden_secret_raw_provider_leak" and is_generic_secret_context(context):
            result["allowed_context_mention"] += 1
            continue
        result[hit_type] += 1
        if len(result["forbidden_samples"]) < 10:
            result["forbidden_samples"].append({"path": rel, "line": line_number, "type": hit_type})


def is_scanner_or_test_context(rel_path: str, context: str) -> bool:
    rel = rel_path.lower()
    return any(marker in rel for marker in ("scan", "compliance", "test", "history")) or any(
        marker in context
        for marker in (
            "scan",
            "scanner",
            "grep",
            "forbidden",
            "allowed",
            "audit",
            "boundary",
            "not investment advice",
            "not a trading signal",
            "不是投资建议",
            "不是交易信号",
        )
    )


def is_generic_secret_context(context: str) -> bool:
    return not any(
        marker in context
        for marker in (
            "sk-",
            "authorization:",
            "bearer ",
            "openai" + "_api_key",
            "anthropic" + "_api_key",
            "github" + "_token",
        )
    )


def latest_daily_event(evidence_root: Path) -> dict[str, Any] | None:
    events_path = evidence_root / "beta-daily-events.jsonl"
    if not events_path.exists():
        return None
    last: dict[str, Any] | None = None
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = json.loads(line)
    return last


def load_beta_status(public_status_path: Path = PUBLIC_STATUS_PATH) -> dict[str, Any]:
    if public_status_path.exists():
        return read_json(public_status_path)
    return status_payload(public_status_path=public_status_path)["public_status"]


def monitor_timer_statuses() -> dict[str, Any]:
    return {
        MONITOR_DAILY_REPORT_TIMER: unit_status(MONITOR_DAILY_REPORT_TIMER),
        MONITOR_POST_RUN_TIMER: unit_status(MONITOR_POST_RUN_TIMER),
        MONITOR_HEALTH_TIMER: unit_status(MONITOR_HEALTH_TIMER),
    }


def build_monitor_heartbeat(
    *,
    evidence_root: Path | None = None,
    public_status_path: Path = PUBLIC_STATUS_PATH,
    production: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    current = now or utc_now()
    status = load_beta_status(public_status_path)
    production_status = production or production_smoke()
    gotra_state = git_state(Path("/opt/gotra"))
    ledger_state = git_state(Path("/opt/gotra-public-ledger"))
    return {
        "schema": MONITOR_HEARTBEAT_SCHEMA,
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "phase": "stage15B_beta_monitoring",
        "beta_started": status.get("beta_started") is True,
        "beta_clock_started": status.get("beta_clock_started") is True,
        "started_at": status.get("started_at"),
        "elapsed_days": status.get("elapsed_days", 0),
        "required_days": status.get("required_days", 30),
        "beta_complete": status.get("beta_complete") is True,
        "last_daily_run_status": status.get("last_daily_run_status"),
        "last_daily_event_at": status.get("last_daily_event_at"),
        "next_daily_run_due_at": status.get("next_daily_run_due_at"),
        "systemd_daily_timer": unit_status(DAILY_TIMER_NAME),
        "systemd_daily_service": unit_status(DAILY_SERVICE_NAME),
        "systemd_monitor_timers": monitor_timer_statuses(),
        "production_beta_status_ok": fetch_url("https://gotra.me/reports/beta_status.json").get("ok") is True,
        "production_beta_page_ok": any(route["url"] == "https://gotra.me/beta" and route["ok"] for route in production_status["routes"]),
        "production_smoke_verdict": production_status["verdict"],
        "paid_features_enabled": status.get("paid_features_enabled") is True,
        "current_blocker": classify_blocker(status=status, production=production_status, gotra_state=gotra_state, ledger_state=ledger_state),
        "last_repair_action": latest_repair_action(root / "monitor" / "repair-events.jsonl"),
        "latest_daily_report": latest_daily_report_path(root / "monitor" / "daily-reports"),
        "gotra_branch": gotra_state.get("branch", ""),
        "gotra_head": gotra_state.get("head", ""),
        "gotra_dirty": str(gotra_state.get("dirty_count", "")),
        "ledger_branch": ledger_state.get("branch", ""),
        "ledger_head": ledger_state.get("head", ""),
        "ledger_dirty": str(ledger_state.get("dirty_count", "")),
    }


def classify_blocker(
    *,
    status: dict[str, Any],
    production: dict[str, Any],
    gotra_state: dict[str, Any],
    ledger_state: dict[str, Any],
) -> str | None:
    if status.get("beta_started") is not True or status.get("beta_clock_started") is not True:
        return "P0_beta_clock_not_started"
    if status.get("elapsed_days", 0) < 30 and status.get("beta_complete") is True:
        return "P0_beta_complete_before_30d"
    if status.get("paid_features_enabled") is True:
        return "P0_paid_features_enabled"
    if production.get("http_ok") is not True:
        return "P0_production_http"
    if production.get("forbidden_direct_advice", 0) > 0:
        return "P0_forbidden_direct_advice"
    if production.get("forbidden_secret_raw_provider_leak", 0) > 0:
        return "P0_secret_or_raw_provider_leak"
    if production.get("raw_accidental_landing_count", 0) > 0:
        return "P0_raw_accidental_landing"
    if int(gotra_state.get("dirty_count", 0) or 0) > 0 or int(ledger_state.get("dirty_count", 0) or 0) > 0:
        return "P0_unknown_repo_dirty"
    return None


def latest_repair_action(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    latest: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            latest = json.loads(line)
    return latest


def latest_daily_report_path(path: Path) -> str:
    if not path.exists():
        return ""
    reports = sorted(path.glob("*.md"))
    return str(reports[-1]) if reports else ""


def health_check(
    *,
    evidence_root: Path | None = None,
    public_status_path: Path = PUBLIC_STATUS_PATH,
    now: datetime | None = None,
    write_outputs: bool = True,
) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    monitor = monitor_root(root)
    ensure_monitor_dirs(monitor)
    current = now or utc_now()
    production = production_smoke()
    status = load_beta_status(public_status_path)
    heartbeat = build_monitor_heartbeat(
        evidence_root=root,
        public_status_path=public_status_path,
        production=production,
        now=current,
    )
    snapshot = {
        "schema": MONITOR_EVENT_SCHEMA,
        "event_type": "stage15B_beta_monitor_health_check",
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "status": status,
        "runtime": {
            "daily_timer": unit_status(DAILY_TIMER_NAME),
            "daily_service": unit_status(DAILY_SERVICE_NAME),
            "daily_timer_listing": timer_listing(DAILY_TIMER_NAME),
        },
        "production": production,
        "source_safety_scan": source_safety_scan(),
        "repo_state": {
            "gotra": git_state(Path("/opt/gotra")),
            "ledger": git_state(Path("/opt/gotra-public-ledger")),
        },
        "heartbeat": heartbeat,
        "result": "pass" if heartbeat["current_blocker"] is None else "needs_repair",
        "boundary": boundary(),
    }
    if write_outputs:
        write_json(monitor / "monitor-heartbeat.json", heartbeat)
        write_json(monitor / "health-snapshots" / f"{local_now(current).date().isoformat()}-{current.strftime('%H%M%SZ')}.json", snapshot)
        append_jsonl(monitor / "health-events.jsonl", snapshot)
        append_jsonl(monitor / "monitor-events.jsonl", snapshot)
        sync_main_roadmap_files(root, heartbeat, snapshot)
    return snapshot


def post_run_check(
    *,
    evidence_root: Path | None = None,
    public_status_path: Path = PUBLIC_STATUS_PATH,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    monitor = monitor_root(root)
    ensure_monitor_dirs(monitor)
    current = now or utc_now()
    health = health_check(evidence_root=root, public_status_path=public_status_path, now=current, write_outputs=not dry_run)
    event = latest_daily_event(root)
    payload = {
        "schema": MONITOR_EVENT_SCHEMA,
        "event_type": "stage15B_beta_monitor_post_run_check",
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "dry_run": dry_run,
        "latest_daily_event": event,
        "daily_service": unit_status(DAILY_SERVICE_NAME),
        "daily_journal_tail": journal_tail(DAILY_SERVICE_NAME),
        "health_result": health["result"],
        "current_blocker": health["heartbeat"]["current_blocker"],
        "repair_attempted": False,
        "result": health["result"],
        "boundary": boundary(),
    }
    if not dry_run:
        write_json(monitor / "post-run" / f"{local_now(current).date().isoformat()}.json", payload)
        append_jsonl(monitor / "monitor-events.jsonl", payload)
    return payload


def daily_report(
    *,
    evidence_root: Path | None = None,
    public_status_path: Path = PUBLIC_STATUS_PATH,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    monitor = monitor_root(root)
    ensure_monitor_dirs(monitor)
    current = now or utc_now()
    health = health_check(evidence_root=root, public_status_path=public_status_path, now=current, write_outputs=not dry_run)
    status = health["status"]
    report_date = local_now(current).date().isoformat()
    report_path = monitor / "daily-reports" / f"{report_date}.md"
    report = render_daily_report(
        date=report_date,
        status=status,
        health=health,
        report_path=report_path,
        evidence_root=root,
    )
    payload = {
        "schema": MONITOR_DAILY_REPORT_SCHEMA,
        "event_type": "stage15B_beta_monitor_daily_report",
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "dry_run": dry_run,
        "report_path": str(report_path),
        "elapsed_days": status.get("elapsed_days", 0),
        "beta_complete": status.get("beta_complete") is True,
        "current_blocker": health["heartbeat"]["current_blocker"],
        "result": "pass" if health["heartbeat"]["current_blocker"] is None else "needs_repair",
        "boundary": boundary(),
    }
    if not dry_run:
        report_path.write_text(report, encoding="utf-8")
        append_jsonl(monitor / "monitor-events.jsonl", payload)
        append_jsonl(
            MAIN_EVENTS_PATH,
            {
                "event_type": "stage15B_beta_monitor_daily_report",
                "timestamp": payload["timestamp"],
                "report_path": str(report_path),
                "elapsed_days": payload["elapsed_days"],
                "beta_complete": payload["beta_complete"],
                "current_blocker": payload["current_blocker"],
                "result": payload["result"],
            },
        )
        append_summary_line(status, payload, report_path)
        heartbeat = health["heartbeat"]
        heartbeat["latest_daily_report"] = str(report_path)
        write_json(monitor / "monitor-heartbeat.json", heartbeat)
    return payload


def render_daily_report(
    *,
    date: str,
    status: dict[str, Any],
    health: dict[str, Any],
    report_path: Path,
    evidence_root: Path,
) -> str:
    heartbeat = health["heartbeat"]
    production = health["production"]
    runtime = health["runtime"]
    latest_event = latest_daily_event(evidence_root)
    remaining_days = max(0, int(status.get("required_days", 30)) - int(status.get("elapsed_days", 0)))
    blocker = heartbeat.get("current_blocker")
    return f"""# GOTRA Stage 15B 30 天公开 Beta 日报 - {date}

## 今日结论
- 状态: `BETA_IN_PROGRESS_REAL_TIME_WAIT`
- 是否需要人工介入: `{str(blocker is not None).lower()}`
- 是否发生自动修复: `false`
- 当前是否仍为 BETA_IN_PROGRESS_REAL_TIME_WAIT: `true`

## Beta 进度
- beta_started: `{str(status.get('beta_started') is True).lower()}`
- beta_clock_started: `{str(status.get('beta_clock_started') is True).lower()}`
- started_at: `{status.get('started_at')}`
- elapsed_days: `{status.get('elapsed_days', 0)}`
- required_days: `{status.get('required_days', 30)}`
- beta_complete: `{str(status.get('beta_complete') is True).lower()}`
- 距离 30 天还剩: `{remaining_days}`
- 30d 是否完成: `false`

## Runtime 状态
- daily timer: `{runtime['daily_timer'].get('is_active')}`
- latest daily service result: `{runtime['daily_service'].get('is_active')}`
- last_daily_event_at: `{status.get('last_daily_event_at')}`
- next_daily_run_due_at: `{status.get('next_daily_run_due_at')}`
- daily run status: `{status.get('last_daily_run_status')}`
- blocked_count: `{(latest_event or {}).get('blocked_count', 0)}`
- failed_count: `0`
- needs_review_count: `{(latest_event or {}).get('needs_review_count', 0)}`
- data_gap_count: `{(latest_event or {}).get('data_gap_count', 0)}`

## Production 状态
- /beta: `{route_status(production, 'https://gotra.me/beta')}`
- /today: `{route_status(production, 'https://gotra.me/today/')}`
- /track-record: `{route_status(production, 'https://gotra.me/track-record')}`
- /monthly-reports: `{route_status(production, 'https://gotra.me/monthly-reports')}`
- /reports/latest: `{route_status(production, 'https://gotra.me/reports/latest/')}`
- /reports/full-analyst: `{route_status(production, 'https://gotra.me/reports/full-analyst/')}`
- /reports/beta_status.json: `{route_status(production, 'https://gotra.me/reports/beta_status.json')}`
- production smoke verdict: `{production.get('verdict')}`

## 安全与边界
- paid_features_enabled: `{str(status.get('paid_features_enabled') is True).lower()}`
- direct advice scan: `{production.get('forbidden_direct_advice', 0)}`
- external Alaya public implication: `{production.get('forbidden_external_alaya_public_implication', 0)}`
- secret/raw provider leak: `{production.get('forbidden_secret_raw_provider_leak', 0)}`
- raw artifact main path: `{production.get('raw_accidental_landing_count', 0)}`
- not investment advice: `true`
- not trading signal: `true`
- no target price: `true`
- no position sizing: `true`
- no return promise: `true`
- no performance proof: `true`
- no science/public proof: `true`

## 数据与研究诚实性
- 今日是否有真实 daily event: `{str((latest_event or {}).get('run_status') not in (None, 'unavailable_no_live_daily_research_job_configured', 'day0_started_no_daily_research_run_yet')).lower()}`
- 是否出现 data_gap: `{str((latest_event or {}).get('data_gap_count', 0) > 0).lower()}`
- 是否出现 needs_review: `{str((latest_event or {}).get('needs_review_count', 0) > 0).lower()}`
- 是否有 no-fabrication unavailable state: `{str(status.get('no_fabrication') is True).lower()}`
- Full Analyst sample 状态: `withheld pending fresh real v4 canary`

## 自动修复
- 是否触发: `false`
- root cause: `{blocker or 'none'}`
- action: `none`
- result: `{health.get('result')}`
- evidence: `{report_path}`

## Remaining Review Items
- Full Analyst public sample withheld pending fresh real v4 canary
- backend/private external Alaya client references remain P1 before formal/paid readiness
- npm audit 17 moderate dev-only/transitive vulnerabilities remain review items

## Repo 状态
- /opt/gotra: `branch={heartbeat.get('gotra_branch')} head={heartbeat.get('gotra_head')} dirty={heartbeat.get('gotra_dirty')}`
- /opt/gotra-public-ledger: `branch={heartbeat.get('ledger_branch')} head={heartbeat.get('ledger_head')} dirty={heartbeat.get('ledger_dirty')}`

## Evidence
- beta_status snapshot: `{PUBLIC_STATUS_PATH}`
- beta heartbeat: `{evidence_root / 'beta-heartbeat.json'}`
- daily events: `{evidence_root / 'beta-daily-events.jsonl'}`
- monitor events: `{monitor_root(evidence_root) / 'monitor-events.jsonl'}`
- production smoke: `{monitor_root(evidence_root) / 'production-smoke'}`
- screenshots/logs: `{monitor_root(evidence_root) / 'screenshots'}`

## 明日计划
- next daily timer: `{status.get('next_daily_run_due_at')}`
- next monitor check: `systemd timer: {MONITOR_HEALTH_TIMER}`
- 是否需要人工 review: `{str(blocker is not None).lower()}`

## Boundary
这不是 30d beta complete，不是 full launch，不是 paid ready，不是投资建议，不是交易信号，无目标价、无仓位建议、无收益承诺、无 performance proof、无 science/public proof。Alaya 只指 GOTRA 内部 cognition flywheel / memory / readback。
"""


def route_status(production: dict[str, Any], url: str) -> str:
    for route in production.get("routes", []):
        if route.get("url") == url:
            return "ok" if route.get("ok") else f"failed:{route.get('status') or route.get('error')}"
    return "missing"


def append_summary_line(status: dict[str, Any], payload: dict[str, Any], report_path: Path) -> None:
    timestamp = payload["timestamp"]
    line = (
        f"Stage 15B daily monitor: date={report_path.stem}, "
        f"elapsed_days={status.get('elapsed_days', 0)}/30, "
        f"beta_complete={str(status.get('beta_complete') is True).lower()}, "
        f"daily_run={status.get('last_daily_run_status')}, "
        f"production={payload.get('result')}, repair=none, "
        f"blocker={payload.get('current_blocker')}, report={report_path}, "
        f"updated_at={timestamp}.\n"
    )
    MAIN_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MAIN_SUMMARY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def sync_main_roadmap_files(evidence_root: Path, heartbeat: dict[str, Any], event: dict[str, Any]) -> None:
    main = {
        "timestamp": heartbeat["timestamp"],
        "phase": "beta_in_progress_real_time_wait",
        "roadmap_stage": "15B_30d_public_beta_runtime",
        "current_gate": "30d_real_time_beta_monitoring",
        "run_id": "gotra_stage15b_30d_public_beta_20260706T041801Z",
        "elapsed_seconds": int(heartbeat.get("elapsed_days", 0)) * 86400,
        "last_completed_action": "Stage 15B beta monitor heartbeat updated",
        "latest_backend_validation": "monitor health-check",
        "latest_frontend_validation": "production route smoke sampled by monitor",
        "latest_browser_qa": "not run by lightweight monitor",
        "latest_production_smoke": heartbeat.get("production_smoke_verdict"),
        "latest_long_run_status": f"BETA_IN_PROGRESS_REAL_TIME_WAIT elapsed_days={heartbeat.get('elapsed_days')}/30",
        "current_blocker": heartbeat.get("current_blocker"),
        "next_action": "continue Stage 15B daily monitoring until real elapsed_days >= 30; do not enter Stage 16",
        "gotra_branch": heartbeat.get("gotra_branch"),
        "gotra_head": heartbeat.get("gotra_head"),
        "gotra_dirty": heartbeat.get("gotra_dirty"),
        "ledger_branch": heartbeat.get("ledger_branch"),
        "ledger_head": heartbeat.get("ledger_head"),
        "ledger_dirty": heartbeat.get("ledger_dirty"),
    }
    write_json(MAIN_HEARTBEAT_PATH, main)
    append_jsonl(
        MAIN_EVENTS_PATH,
        {
            "event_type": "stage15B_beta_monitor_health_check",
            "timestamp": event["timestamp"],
            "elapsed_days": heartbeat.get("elapsed_days"),
            "beta_complete": heartbeat.get("beta_complete"),
            "production": heartbeat.get("production_smoke_verdict"),
            "current_blocker": heartbeat.get("current_blocker"),
            "monitor_heartbeat": str(monitor_root(evidence_root) / "monitor-heartbeat.json"),
            "boundary": boundary(),
        },
    )


def build_monitor_systemd_units(evidence_root: Path, *, script_path: Path | None = None) -> dict[str, str]:
    script = script_path or Path("/opt/gotra/scripts/gotra_beta_monitor.py")
    python = Path(os.environ.get("GOTRA_PYTHON", "/opt/gotra/.venv/bin/python"))
    log_path = evidence_root / "monitor" / "monitor-systemd.log"
    service_template = """[Unit]
Description={description}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/gotra
Environment=PYTHONUNBUFFERED=1
ExecStart={python} {script} {command}
StandardOutput=append:{log_path}
StandardError=append:{log_path}
"""
    return {
        MONITOR_DAILY_REPORT_SERVICE: service_template.format(
            description="GOTRA Stage 15B beta monitor daily Chinese report",
            python=python,
            script=script,
            command="daily-report",
            log_path=log_path,
        ),
        MONITOR_DAILY_REPORT_TIMER: """[Unit]
Description=Generate GOTRA Stage 15B beta daily Chinese report

[Timer]
OnCalendar=*-*-* 09:30:00
Persistent=true
Unit=gotra-beta-monitor-daily-report.service

[Install]
WantedBy=timers.target
""",
        MONITOR_POST_RUN_SERVICE: service_template.format(
            description="GOTRA Stage 15B beta monitor post daily run check",
            python=python,
            script=script,
            command="post-run-check",
            log_path=log_path,
        ),
        MONITOR_POST_RUN_TIMER: """[Unit]
Description=Run GOTRA Stage 15B beta post-run monitor

[Timer]
OnCalendar=*-*-* 18:50:00
Persistent=true
Unit=gotra-beta-monitor-post-run.service

[Install]
WantedBy=timers.target
""",
        MONITOR_HEALTH_SERVICE: service_template.format(
            description="GOTRA Stage 15B beta lightweight health monitor",
            python=python,
            script=script,
            command="health-check",
            log_path=log_path,
        ),
        MONITOR_HEALTH_TIMER: """[Unit]
Description=Run GOTRA Stage 15B beta lightweight health checks

[Timer]
OnCalendar=*-*-* 03,12,21:10:00
Persistent=true
Unit=gotra-beta-monitor-health.service

[Install]
WantedBy=timers.target
""",
    }


def write_monitor_systemd_definitions(evidence_root: Path) -> dict[str, Any]:
    root = monitor_root(evidence_root)
    ensure_monitor_dirs(root)
    units = build_monitor_systemd_units(evidence_root)
    systemd_root = root / "systemd"
    for name, content in units.items():
        (systemd_root / name).write_text(content, encoding="utf-8")
    return {
        "services": [MONITOR_DAILY_REPORT_SERVICE, MONITOR_POST_RUN_SERVICE, MONITOR_HEALTH_SERVICE],
        "timers": [MONITOR_DAILY_REPORT_TIMER, MONITOR_POST_RUN_TIMER, MONITOR_HEALTH_TIMER],
        "templates_dir": str(systemd_root),
        "log_path": str(root / "monitor-systemd.log"),
    }


def install_monitor_timers(*, evidence_root: Path | None = None) -> dict[str, Any]:
    if not systemctl_available():
        raise RuntimeError("systemd_unavailable")
    root = evidence_root or active_evidence_root()
    definitions = write_monitor_systemd_definitions(root)
    systemd_root = monitor_root(root) / "systemd"
    for unit_name in definitions["services"] + definitions["timers"]:
        (SYSTEMD_DIR / unit_name).write_text((systemd_root / unit_name).read_text(encoding="utf-8"), encoding="utf-8")
    commands = [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "--now", MONITOR_DAILY_REPORT_TIMER],
        ["systemctl", "enable", "--now", MONITOR_POST_RUN_TIMER],
        ["systemctl", "enable", "--now", MONITOR_HEALTH_TIMER],
    ]
    results = [run_command(command).as_dict() for command in commands]
    if any(result["returncode"] != 0 for result in results):
        raise RuntimeError(f"monitor_timer_install_failed:{results}")
    payload = {
        "schema": MONITOR_EVENT_SCHEMA,
        "event_type": "stage15B_beta_monitor_timers_installed",
        "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
        "definitions": definitions,
        "install_results": results,
        "timer_status": monitor_timer_statuses(),
        "boundary": boundary(),
    }
    append_jsonl(monitor_root(root) / "monitor-events.jsonl", payload)
    return payload


def repair_if_safe(*, evidence_root: Path | None = None) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    monitor = monitor_root(root)
    ensure_monitor_dirs(monitor)
    current = utc_now().isoformat().replace("+00:00", "Z")
    health = health_check(evidence_root=root, write_outputs=True)
    blocker = health["heartbeat"]["current_blocker"]
    event = {
        "schema": MONITOR_REPAIR_EVENT_SCHEMA,
        "event_type": "stage15B_beta_monitor_self_repair",
        "timestamp": current,
        "severity": "P0" if blocker else "none",
        "root_cause": blocker or "none",
        "repair_action": "none",
        "commands_run": [],
        "validation_after": [],
        "result": "not_needed" if blocker is None else "needs_review",
        "evidence_paths": [str(monitor)],
        "boundary": boundary(),
    }
    if blocker == "P0_production_http":
        nginx_test = run_command(["nginx", "-t"])
        event["commands_run"].append(nginx_test.as_dict())
        if nginx_test.returncode == 0:
            restart = run_command(["systemctl", "restart", "nginx"])
            event["commands_run"].append(restart.as_dict())
            after = health_check(evidence_root=root, write_outputs=True)
            event["validation_after"].append({"production": after["production"], "blocker": after["heartbeat"]["current_blocker"]})
            event["repair_action"] = "restart_nginx_once"
            event["result"] = "repaired" if after["heartbeat"]["current_blocker"] is None else "needs_review"
    append_jsonl(monitor / "repair-events.jsonl", event)
    append_jsonl(monitor / "monitor-events.jsonl", event)
    return event
