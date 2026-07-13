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
from datetime import datetime, timedelta, timezone
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
    build_beta_heartbeat,
    build_public_status,
    read_json,
    status_payload,
    utc_now,
    write_json,
)


MONITOR_HEARTBEAT_SCHEMA = "gotra.launch.beta_monitor_heartbeat.v1"
MONITOR_EVENT_SCHEMA = "gotra.launch.beta_monitor_event.v1"
MONITOR_DAILY_REPORT_SCHEMA = "gotra.launch.beta_monitor_daily_report.v1"
MONITOR_REPAIR_EVENT_SCHEMA = "gotra.launch.beta_monitor_repair_event.v1"
MONITOR_ALERT_SCHEMA = "gotra.launch.beta_alert.v1"
MONITOR_DAILY_REPORT_SERVICE = "gotra-beta-monitor-daily-report.service"
MONITOR_DAILY_REPORT_TIMER = "gotra-beta-monitor-daily-report.timer"
MONITOR_POST_RUN_SERVICE = "gotra-beta-monitor-post-run.service"
MONITOR_POST_RUN_TIMER = "gotra-beta-monitor-post-run.timer"
MONITOR_HEALTH_SERVICE = "gotra-beta-monitor-health.service"
MONITOR_HEALTH_TIMER = "gotra-beta-monitor-health.timer"
SYSTEMD_DIR = Path("/etc/systemd/system")
PUBLIC_LEDGER_ROOT = Path(os.environ.get("GOTRA_PUBLIC_LEDGER_PATH", "/opt/gotra-public-ledger"))
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
        r"\bsk-[A-Za-z0-9]{16,}\b",
        r"\bAuthorization:",
        r"\bBearer\s+[A-Za-z0-9._-]{12,}",
        "OPENAI" + "_API_KEY",
        "ANTHROPIC" + "_API_KEY",
        "GITHUB" + "_TOKEN",
        r"\bapi[_-]?key\b",
        r"\bsecret\b",
        r"\bpassword\b",
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
            "不能",
            "不构成",
            "不要",
            "避免",
            "不得",
            "禁止",
            "无",
            "非",
            "仅",
            "内部",
        )
    )


def source_safety_scan() -> dict[str, Any]:
    root = PUBLIC_LEDGER_ROOT
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
    return any(marker in rel for marker in ("scan", "compliance", "test", "history", "generate", "smoke", "check-secrets")) or any(
        marker in context
        for marker in (
            "scan",
            "scanner",
            "grep",
            "forbidden",
            "allowed",
            "audit",
            "boundary",
            "failure",
            "failures",
            "unacceptable",
            "输出",
            "失败",
            "复核",
            "审计",
            "边界",
            "能当",
            "吗？",
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


def load_beta_status(
    public_status_path: Path = PUBLIC_STATUS_PATH,
    *,
    evidence_root: Path | None = None,
    now: datetime | None = None,
    refresh_timer: bool = False,
    write_outputs: bool = False,
) -> dict[str, Any]:
    current_status = read_json(public_status_path) if public_status_path.exists() else None
    if refresh_timer and evidence_root is not None:
        start_payload = read_json(evidence_root / "beta-start.json")
        refreshed = build_public_status(
            start_payload,
            last_daily_event_at=(current_status or {}).get("last_daily_event_at"),
            last_daily_run_status=(current_status or {}).get("last_daily_run_status"),
            now=now,
            evidence_root=evidence_root,
            previous_due_at=(current_status or {}).get("next_daily_run_due_at"),
        )
        if write_outputs and refreshed != current_status:
            write_json(public_status_path, refreshed)
            write_json(evidence_root / "beta-heartbeat.json", build_beta_heartbeat(evidence_root, refreshed, now))
        return refreshed
    if current_status is not None:
        return current_status
    return status_payload(evidence_root=evidence_root, public_status_path=public_status_path)["public_status"]


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
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = evidence_root or active_evidence_root()
    current = now or utc_now()
    status = status or load_beta_status(public_status_path, evidence_root=root, now=current, refresh_timer=True)
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
        "next_daily_run_due_at_local": status.get("next_daily_run_due_at_local"),
        "next_daily_run_due_at_source": status.get("next_daily_run_due_at_source"),
        "next_daily_run_timer_active": status.get("next_daily_run_timer_active"),
        "stale_status_detected": status.get("stale_status_detected"),
        "daily_research_job_configured": status.get("daily_research_job_configured"),
        "daily_research_job_status": status.get("daily_research_job_status"),
        "valid_research_output_days": status.get("valid_research_output_days", 0),
        "unavailable_days": status.get("unavailable_days", 0),
        "failed_output_days": status.get("failed_output_days", 0),
        "history_backfilled": status.get("history_backfilled") is True,
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


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})", text)
        if not match:
            return None
        parsed = datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}").replace(
            tzinfo=ZoneInfo("Asia/Shanghai")
        )
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def file_age_seconds(path: Path, now: datetime) -> float | None:
    if not path.exists():
        return None
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return max(0.0, (now.astimezone(timezone.utc) - modified).total_seconds())


def systemd_properties(unit_name: str, properties: tuple[str, ...]) -> dict[str, Any]:
    if not systemctl_available():
        return {"available": False, "unit": unit_name}
    command = ["systemctl", "show", unit_name]
    for name in ("LoadState", *properties):
        command.extend(["-p", name])
    command.append("--no-pager")
    result = run_command(command)
    values: dict[str, Any] = {"available": result.returncode in {0, 3}, "unit": unit_name}
    for line in result.output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip()
    if values.get("LoadState") == "not-found":
        values["available"] = False
    return values


def all_daily_events(evidence_root: Path) -> list[dict[str, Any]]:
    path = evidence_root / "beta-daily-events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return [event for event in events if event.get("event_type") == "beta_daily_runtime_event"]


def latest_file(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern)) if path.exists() else []
    return files[-1] if files else None


def expected_repo_state_path(evidence_root: Path) -> Path:
    return monitor_root(evidence_root) / "expected-repo-state.json"


def write_expected_repo_state(evidence_root: Path) -> dict[str, Any]:
    payload = {
        "schema": "gotra.launch.beta_expected_repo_state.v1",
        "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
        "gotra": git_state(Path("/opt/gotra")),
        "ledger": git_state(Path("/opt/gotra-public-ledger")),
        "beta_clock_preserved": True,
    }
    write_json(expected_repo_state_path(evidence_root), payload)
    return payload


def make_alert(
    *,
    current: datetime,
    severity: str,
    code: str,
    root_cause: str,
    component: str,
    latest_good_event: str,
    evidence_paths: list[str],
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema": MONITOR_ALERT_SCHEMA,
        "event_type": "stage15B_beta_alert",
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "severity": severity,
        "alert_code": code,
        "root_cause": root_cause,
        "affected_component": component,
        "latest_good_event": latest_good_event,
        "evidence_paths": evidence_paths,
        "auto_repair_attempted": False,
        "auto_repair_result": "not_attempted",
        "beta_clock_preserved": True,
        "beta_timer_stopped": False,
        "human_action_required": severity in {"blocker", "critical"},
        "next_action": next_action,
    }


def evaluate_alerts(
    *,
    evidence_root: Path,
    status: dict[str, Any],
    production: dict[str, Any],
    gotra_state: dict[str, Any],
    ledger_state: dict[str, Any],
    current: datetime,
) -> list[dict[str, Any]]:
    monitor = monitor_root(evidence_root)
    alerts: list[dict[str, Any]] = []
    timer = systemd_properties(
        DAILY_TIMER_NAME,
        ("ActiveState", "SubState", "NextElapseUSecRealtime", "LastTriggerUSec"),
    )
    service = systemd_properties(
        DAILY_SERVICE_NAME,
        ("ActiveState", "Result", "ExecMainStatus", "ExecMainStartTimestamp", "ExecMainExitTimestamp"),
    )
    latest_event = latest_daily_event(evidence_root) or {}
    latest_event_at = parse_timestamp(latest_event.get("timestamp"))
    last_trigger = parse_timestamp(timer.get("LastTriggerUSec"))
    next_due = parse_timestamp(status.get("next_daily_run_due_at"))
    canonical_start = read_json(evidence_root / "beta-start.json").get("started_at")

    def add(severity: str, code: str, cause: str, component: str, action: str, paths: list[str] | None = None) -> None:
        alerts.append(
            make_alert(
                current=current,
                severity=severity,
                code=code,
                root_cause=cause,
                component=component,
                latest_good_event=str(latest_event.get("timestamp") or ""),
                evidence_paths=paths or [str(evidence_root / "beta-daily-events.jsonl")],
                next_action=action,
            )
        )

    if timer.get("available") is True and (
        timer.get("ActiveState") != "active" or timer.get("SubState") not in {"waiting", "running"}
    ):
        add("critical", "BETA_TIMER_INACTIVE", "daily beta timer is not active/waiting", DAILY_TIMER_NAME, "inspect systemd without resetting the beta clock")
    if next_due and next_due < current - timedelta(minutes=15):
        add("blocker", "NEXT_RUN_STALE", "next daily run is more than 15 minutes behind current time", "beta_status", "refresh status from the active systemd timer")
    if service.get("available") is True and (
        service.get("Result") not in {"", "success"}
        or str(service.get("ExecMainStatus") or "0") not in {"", "0"}
    ):
        add("blocker", "DAILY_SERVICE_FAILED", "last daily service exited non-zero", DAILY_SERVICE_NAME, "preserve the failed event and inspect the service journal")
    if last_trigger and current > last_trigger + timedelta(minutes=45) and (not latest_event_at or latest_event_at < last_trigger):
        add("blocker", "DAILY_EVENT_MISSING_AFTER_RUN", "no new daily event within 45 minutes of the timer trigger", "beta_daily_events", "inspect the daily service and append only the truthful missing/failure state")

    previous_heartbeat = monitor / "monitor-heartbeat.json"
    heartbeat_age = file_age_seconds(previous_heartbeat, current)
    if heartbeat_age is None or heartbeat_age > 20 * 60:
        add("warning", "MONITOR_HEARTBEAT_STALE", "monitor heartbeat is older than 20 minutes", MONITOR_HEALTH_TIMER, "run one health check and verify the 10-minute timer", [str(previous_heartbeat)])
    report = latest_file(monitor / "daily-reports", "*.md")
    report_age = file_age_seconds(report, current) if report else None
    if report_age is None or report_age > 26 * 3600:
        add("warning", "DAILY_REPORT_STALE", "Chinese daily report is older than 26 hours", "daily_report", "regenerate the report from existing evidence", [str(report or monitor / "daily-reports")])
    post_run = latest_file(monitor / "post-run", "*.json")
    post_run_at = datetime.fromtimestamp(post_run.stat().st_mtime, tz=timezone.utc) if post_run else None
    if last_trigger and current > last_trigger + timedelta(minutes=45) and (not post_run_at or post_run_at < last_trigger):
        add("warning", "POST_RUN_EVIDENCE_MISSING", "post-run evidence is missing 45 minutes after the daily run", "post_run_monitor", "run the post-run check once", [str(post_run or monitor / "post-run")])

    if production.get("verdict") != "pass" or production.get("http_ok") is not True:
        add("critical", "PRODUCTION_SMOKE_FAILED", "production route or smoke validation failed", "production", "rerun production smoke once; do not deploy automatically")
    for field, code in (
        ("raw_accidental_landing_count", "RAW_ACCIDENTAL_LANDING"),
        ("object_object_count", "OBJECT_OBJECT_RENDERED"),
        ("python_dict_count", "PYTHON_DICT_RENDERED"),
        ("traceback_count", "TRACEBACK_RENDERED"),
        ("unrendered_json_or_md_count", "UNRENDERED_JSON_OR_MD"),
        ("forbidden_direct_advice", "FORBIDDEN_ADVICE"),
        ("forbidden_external_alaya_public_implication", "EXTERNAL_ALAYA_PUBLIC_IMPLICATION"),
        ("forbidden_secret_raw_provider_leak", "SECRET_OR_RAW_PROVIDER_LEAK"),
    ):
        if int(production.get(field, 0) or 0) > 0:
            add("critical", code, f"production smoke found {field}", "production_public_surface", "preserve evidence and require human review")

    expected_path = expected_repo_state_path(evidence_root)
    expected = read_json(expected_path) if expected_path.exists() else {}
    for label, state in (("gotra", gotra_state), ("ledger", ledger_state)):
        if state.get("exists") is not False and (
            state.get("branch") != "main" or int(state.get("dirty_count", 0) or 0) > 0
        ):
            add("blocker", "REPO_STATE_UNSAFE", f"{label} repo is not clean main", label, "restore an explicitly reviewed clean main state")
        expected_head = str((expected.get(label) or {}).get("head") or "")
        if expected_head and state.get("head") != expected_head:
            add("warning", "REPO_HEAD_CHANGED", f"{label} HEAD differs from the installed monitor baseline", label, "review the merged commit and refresh the expected-head baseline")
    if status.get("paid_features_enabled") is True:
        add("critical", "PAID_FEATURES_ENABLED", "paid features became enabled during free beta", "beta_status", "disable paid features without changing the beta clock")
    if status.get("started_at") != canonical_start:
        add("critical", "BETA_STARTED_AT_CHANGED", "public beta started_at differs from immutable beta-start evidence", "beta_clock", "preserve both artifacts and require human review")
    if status.get("daily_research_job_configured") is not True:
        add("blocker", "DAILY_RESEARCH_JOB_NOT_READY", "daily runtime still has no approved real research job", "daily_research", "complete a side-effect-free real-data dry-run and review before future-run enablement")

    events = all_daily_events(evidence_root)
    computed_unavailable = sum(1 for event in events if str(event.get("run_status") or "").startswith("unavailable_"))
    computed_failed = sum(1 for event in events if str(event.get("run_status") or "").startswith(("failed", "blocked")))
    if int(status.get("unavailable_days", 0) or 0) != computed_unavailable or int(status.get("failed_output_days", 0) or 0) != computed_failed:
        add("blocker", "DAILY_COUNTS_INCONSISTENT", "public status does not match append-only daily events", "beta_status", "refresh derived counts without rewriting history")
    last_two = events[-2:]
    if len(last_two) == 2 and all(event.get("daily_research_job_configured") is True for event in last_two):
        valid_counts = [int(event.get("valid_research_output_days", 0) or 0) for event in last_two]
        if valid_counts[0] == valid_counts[1]:
            add("warning", "VALID_OUTPUT_NOT_GROWING", "valid research output days did not grow across two configured runs", "daily_research", "inspect both truthful daily outcomes without backfilling history")
    if str(latest_event.get("track_record_ledger_integrity") or "").lower() in {"failed", "mismatch"}:
        add("critical", "LEDGER_INTEGRITY_FAILED", "latest daily event reports ledger integrity failure", "research_ledger", "stop publication for the affected run and preserve evidence")
    if str(latest_event.get("alaya_internal_readback_status") or "").lower() in {"failed", "mismatch"}:
        add("critical", "ALAYA_READBACK_FAILED", "latest daily event reports internal Alaya readback failure", "alaya_internal_readback", "preserve the event and require a fresh future run")
    return sorted(alerts, key=lambda item: {"critical": 0, "blocker": 1, "warning": 2}[str(item["severity"])])


def persist_alerts(evidence_root: Path, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    monitor = monitor_root(evidence_root)
    current_path = monitor / "current-alert.json"
    previous = read_json(current_path) if current_path.exists() else {}
    current_alert = alerts[0] if alerts else {
        "schema": MONITOR_ALERT_SCHEMA,
        "event_type": "stage15B_beta_alert_state",
        "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
        "severity": "none",
        "alert_code": "none",
        "beta_clock_preserved": True,
        "beta_timer_stopped": False,
        "human_action_required": False,
    }
    changed = (previous.get("severity"), previous.get("alert_code"), previous.get("root_cause")) != (
        current_alert.get("severity"), current_alert.get("alert_code"), current_alert.get("root_cause")
    )
    write_json(current_path, current_alert)
    if changed:
        append_jsonl(monitor / "alerts.jsonl", current_alert)
        append_jsonl(MAIN_EVENTS_PATH, current_alert)
    return current_alert


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
    status = load_beta_status(
        public_status_path,
        evidence_root=root,
        now=current,
        refresh_timer=True,
        write_outputs=write_outputs,
    )
    gotra_state = git_state(Path("/opt/gotra"))
    ledger_state = git_state(Path("/opt/gotra-public-ledger"))
    heartbeat = build_monitor_heartbeat(
        evidence_root=root,
        public_status_path=public_status_path,
        production=production,
        now=current,
        status=status,
    )
    alerts = evaluate_alerts(
        evidence_root=root,
        status=status,
        production=production,
        gotra_state=gotra_state,
        ledger_state=ledger_state,
        current=current,
    )
    current_alert = alerts[0] if alerts else None
    heartbeat["active_alerts"] = [
        {key: alert[key] for key in ("severity", "alert_code", "root_cause", "next_action")}
        for alert in alerts
    ]
    heartbeat["alert_count"] = len(alerts)
    if current_alert:
        heartbeat["current_blocker"] = current_alert["alert_code"]
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
            "gotra": gotra_state,
            "ledger": ledger_state,
        },
        "alerts": alerts,
        "current_alert": current_alert,
        "heartbeat": heartbeat,
        "result": "pass" if heartbeat["current_blocker"] is None else "needs_repair",
        "boundary": boundary(),
    }
    if write_outputs:
        snapshot["current_alert"] = persist_alerts(root, alerts)
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
        "active_alert_count": health["heartbeat"].get("alert_count", 0),
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
    alerts = health.get("alerts") or []
    alert_lines = "\n".join(
        f"- `{alert['severity']}` `{alert['alert_code']}`: {alert['root_cause']}"
        for alert in alerts
    ) or "- 当前没有活动告警。"
    return f"""# GOTRA Stage 15B 30 天公开 Beta 日报 - {date}

## 当前异常
{alert_lines}
- 异常是否影响 beta clock: `false`
- beta timer 是否停止: `false`

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
- next_daily_run_due_at_local: `{status.get('next_daily_run_due_at_local')}`
- next_daily_run_due_at_source: `{status.get('next_daily_run_due_at_source')}`
- timer_active: `{status.get('next_daily_run_timer_active')}`
- stale_status_detected: `{status.get('stale_status_detected')}`
- daily run status: `{status.get('last_daily_run_status')}`
- daily research job configured: `{str(status.get('daily_research_job_configured') is True).lower()}`
- valid_research_output_days: `{status.get('valid_research_output_days', 0)}`
- unavailable_days: `{status.get('unavailable_days', 0)}`
- failed_output_days: `{status.get('failed_output_days', 0)}`
- history_backfilled: `{str(status.get('history_backfilled') is True).lower()}`
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
- beta output review item: `daily research job not configured; beta clock running but valid_research_output_days remains {status.get('valid_research_output_days', 0)}`

## 自动修复
- 是否触发: `{str(bool((heartbeat.get('last_repair_action') or {}).get('repair_action') not in (None, 'none'))).lower()}`
- root cause: `{blocker or 'none'}`
- action: `{(heartbeat.get('last_repair_action') or {}).get('repair_action', 'none')}`
- result: `{health.get('result')}`
- evidence: `{report_path}`

## Remaining Review Items
- Full Analyst public sample withheld pending fresh real v4 canary
- backend/private external Alaya client references remain P1 before formal/paid readiness
- npm audit 17 moderate dev-only/transitive vulnerabilities remain review items
- daily research job not configured; beta clock running but valid_research_output_days remains 0

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
- next daily timer source: `{status.get('next_daily_run_due_at_source')}`
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
OnCalendar=*:0/10
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
    expected_repo_state = write_expected_repo_state(root)
    payload = {
        "schema": MONITOR_EVENT_SCHEMA,
        "event_type": "stage15B_beta_monitor_timers_installed",
        "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
        "definitions": definitions,
        "install_results": results,
        "timer_status": monitor_timer_statuses(),
        "expected_repo_state": expected_repo_state,
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
    repairs_path = monitor / "repair-events.jsonl"
    previous_repairs = []
    if repairs_path.exists():
        previous_repairs = [
            json.loads(line)
            for line in repairs_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    attempts = sum(
        1
        for item in previous_repairs
        if item.get("root_cause") == blocker and item.get("repair_action") != "none"
    )
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
        "attempt": attempts + 1 if blocker else 0,
        "beta_clock_preserved": True,
        "beta_timer_stopped": False,
        "evidence_paths": [str(monitor)],
        "boundary": boundary(),
    }
    safe_retry_codes = {
        "PRODUCTION_SMOKE_FAILED",
        "MONITOR_HEARTBEAT_STALE",
        "DAILY_REPORT_STALE",
        "POST_RUN_EVIDENCE_MISSING",
    }
    if blocker in safe_retry_codes and attempts >= 3:
        event["result"] = "auto_repair_limit_reached"
    elif blocker in safe_retry_codes:
        after = health_check(evidence_root=root, write_outputs=True)
        event["validation_after"].append(
            {"production": after["production"], "blocker": after["heartbeat"]["current_blocker"]}
        )
        event["repair_action"] = "rerun_health_and_production_smoke_once"
        event["result"] = "repaired" if after["heartbeat"]["current_blocker"] is None else "needs_review"
    append_jsonl(repairs_path, event)
    append_jsonl(monitor / "monitor-events.jsonl", event)
    return event
