#!/usr/bin/env python3
"""CLI for the GOTRA Stage 15B 30-day public beta runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gotra.beta_runtime import (
    PUBLIC_STATUS_PATH,
    disable_beta_runtime,
    run_once,
    start_beta_runtime,
    status_payload,
    write_heartbeat,
)


def emit(payload: object) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GOTRA Stage 15B public beta runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Initialize runtime directories without starting the beta clock")
    init_p.add_argument("--evidence-root", type=Path, required=True)

    run_p = sub.add_parser("run-once", help="Write one daily beta event, or preview it with --dry-run")
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--evidence-root", type=Path)
    run_p.add_argument("--public-status-path", type=Path, default=PUBLIC_STATUS_PATH)

    start_p = sub.add_parser("start", help="Start the Stage 15B beta clock from day 0")
    start_p.add_argument("--day0", action="store_true", help="Required explicit confirmation that this starts day 0")
    start_p.add_argument("--evidence-root", type=Path)
    start_p.add_argument("--public-status-path", type=Path, default=PUBLIC_STATUS_PATH)
    start_p.add_argument("--no-install-systemd", action="store_true", help="For tests only; do not use for production start")

    status_p = sub.add_parser("status", help="Print current beta runtime status")
    status_p.add_argument("--evidence-root", type=Path)
    status_p.add_argument("--public-status-path", type=Path, default=PUBLIC_STATUS_PATH)

    heartbeat_p = sub.add_parser("write-heartbeat", help="Refresh beta heartbeat and public status")
    heartbeat_p.add_argument("--evidence-root", type=Path)
    heartbeat_p.add_argument("--public-status-path", type=Path, default=PUBLIC_STATUS_PATH)

    disable_p = sub.add_parser("disable", help="Disable scheduler and preserve beta evidence")
    disable_p.add_argument("--evidence-root", type=Path)
    disable_p.add_argument("--public-status-path", type=Path, default=PUBLIC_STATUS_PATH)

    args = parser.parse_args()
    if args.command == "init":
        from gotra.beta_runtime import ensure_runtime_dirs, runtime_contract, write_json

        ensure_runtime_dirs(args.evidence_root)
        write_json(args.evidence_root / "runtime-contract.json", runtime_contract(args.evidence_root, PUBLIC_STATUS_PATH))
        return emit({"result": "initialized", "evidence_root": str(args.evidence_root)})
    if args.command == "run-once":
        return emit(run_once(dry_run=args.dry_run, evidence_root=args.evidence_root, public_status_path=args.public_status_path))
    if args.command == "start":
        if not args.day0:
            parser.error("start requires --day0")
        return emit(
            start_beta_runtime(
                evidence_root=args.evidence_root,
                public_status_path=args.public_status_path,
                install_scheduler=not args.no_install_systemd,
            )
        )
    if args.command == "status":
        return emit(status_payload(evidence_root=args.evidence_root, public_status_path=args.public_status_path))
    if args.command == "write-heartbeat":
        return emit(write_heartbeat(evidence_root=args.evidence_root, public_status_path=args.public_status_path))
    if args.command == "disable":
        return emit(disable_beta_runtime(evidence_root=args.evidence_root, public_status_path=args.public_status_path))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
