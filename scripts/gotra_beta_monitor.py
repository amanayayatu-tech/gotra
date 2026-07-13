#!/usr/bin/env python3
"""CLI for the GOTRA Stage 15B public beta monitor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gotra.beta_monitor import (  # noqa: E402
    daily_report,
    health_check,
    install_monitor_timers,
    post_run_check,
    repair_if_safe,
    write_monitor_systemd_definitions,
)
from gotra.beta_runtime import PUBLIC_STATUS_PATH, status_payload  # noqa: E402


def emit(payload: object) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GOTRA Stage 15B public beta monitor")
    parser.add_argument("--evidence-root", type=Path, help="Override active beta evidence root")
    parser.add_argument("--public-status-path", type=Path, default=PUBLIC_STATUS_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health-check", help="Run lightweight health check and update monitor heartbeat")
    health.add_argument("--dry-run", action="store_true")

    post_run = sub.add_parser("post-run-check", help="Check the beta daily runtime after the scheduled run")
    post_run.add_argument("--dry-run", action="store_true")

    report = sub.add_parser("daily-report", help="Generate the daily Chinese beta report")
    report.add_argument("--dry-run", action="store_true")

    repair = sub.add_parser("repair", help="Run bounded self-repair for safe P0 conditions")
    repair.add_argument("--if-safe", action="store_true", required=True)

    sub.add_parser("status", help="Print beta runtime status plus monitor heartbeat if present")
    sub.add_parser("write-systemd", help="Write monitor systemd templates into the evidence root only")
    sub.add_parser("install-timers", help="Install and enable monitor systemd timers")

    args = parser.parse_args()
    if args.command == "health-check":
        return emit(
            health_check(
                evidence_root=args.evidence_root,
                public_status_path=args.public_status_path,
                write_outputs=not args.dry_run,
            )
        )
    if args.command == "post-run-check":
        return emit(
            post_run_check(
                evidence_root=args.evidence_root,
                public_status_path=args.public_status_path,
                dry_run=args.dry_run,
            )
        )
    if args.command == "daily-report":
        return emit(
            daily_report(
                evidence_root=args.evidence_root,
                public_status_path=args.public_status_path,
                dry_run=args.dry_run,
            )
        )
    if args.command == "repair":
        return emit(repair_if_safe(evidence_root=args.evidence_root))
    if args.command == "status":
        payload = status_payload(evidence_root=args.evidence_root, public_status_path=args.public_status_path)
        root = Path(payload["evidence_root"])
        monitor_heartbeat = root / "monitor" / "monitor-heartbeat.json"
        payload["monitor_heartbeat_path"] = str(monitor_heartbeat)
        payload["monitor_heartbeat_exists"] = monitor_heartbeat.exists()
        if monitor_heartbeat.exists():
            payload["monitor_heartbeat"] = json.loads(monitor_heartbeat.read_text(encoding="utf-8"))
        return emit(payload)
    if args.command == "write-systemd":
        payload = status_payload(evidence_root=args.evidence_root, public_status_path=args.public_status_path)
        return emit(write_monitor_systemd_definitions(Path(payload["evidence_root"])))
    if args.command == "install-timers":
        return emit(install_monitor_timers(evidence_root=args.evidence_root))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
