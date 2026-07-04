#!/usr/bin/env python3
"""CLI wrapper for GOTRA launch-roadmap operational helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gotra.ops.launch_ops import (
    build_release_bundle,
    heartbeat_payload,
    rollback_dry_run,
    status_summary,
    verify_release_bundle,
    write_heartbeat,
    write_json,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    heartbeat = subcommands.add_parser("heartbeat")
    heartbeat.add_argument("--output", type=Path, required=True)
    heartbeat.add_argument("--run-id", required=True)
    heartbeat.add_argument("--status", required=True)
    heartbeat.add_argument("--current-step", required=True)
    heartbeat.add_argument("--evidence-layer", default="local checks")

    status = subcommands.add_parser("status-summary")
    status.add_argument("--output", type=Path, required=True)
    status.add_argument("--run-id", required=True)
    status.add_argument("--evidence-layer", default="local checks")
    for category in ("frontend", "backend", "data", "release", "review"):
        status.add_argument(f"--{category}-status", default="not_reported")
        status.add_argument(f"--{category}-note", default="")

    bundle = subcommands.add_parser("release-bundle")
    bundle.add_argument("--output-dir", type=Path, required=True)
    bundle.add_argument("--run-id", required=True)
    bundle.add_argument("--public-summary", required=True)
    bundle.add_argument("--evidence", type=Path, action="append", default=[])
    bundle.add_argument("--status-summary", type=Path)

    verify = subcommands.add_parser("verify-bundle")
    verify.add_argument("--bundle-dir", type=Path, required=True)

    rollback = subcommands.add_parser("rollback-dry-run")
    rollback.add_argument("--output", type=Path, required=True)
    rollback.add_argument("--static-dir", type=Path, required=True)
    rollback.add_argument("--backup-dir", type=Path, required=True)
    rollback.add_argument("--route", action="append", default=[])

    return parser.parse_args(argv)


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def category_payload(args: argparse.Namespace, category: str) -> dict[str, str]:
    payload = {"status": getattr(args, f"{category}_status")}
    note = getattr(args, f"{category}_note")
    if note:
        payload["note"] = note
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "heartbeat":
        payload = heartbeat_payload(
            run_id=args.run_id,
            status=args.status,
            current_step=args.current_step,
            evidence_layer=args.evidence_layer,
        )
        write_heartbeat(args.output, payload)
        print_json(payload)
        return 0
    if args.command == "status-summary":
        payload = status_summary(
            run_id=args.run_id,
            evidence_layer=args.evidence_layer,
            frontend=category_payload(args, "frontend"),
            backend=category_payload(args, "backend"),
            data=category_payload(args, "data"),
            release=category_payload(args, "release"),
            review=category_payload(args, "review"),
        )
        write_json(args.output, payload)
        print_json(payload)
        return 0
    if args.command == "release-bundle":
        status = None
        if args.status_summary:
            status = json.loads(args.status_summary.read_text(encoding="utf-8"))
        payload = build_release_bundle(
            output_dir=args.output_dir,
            run_id=args.run_id,
            evidence_paths=args.evidence,
            public_safe_summary=args.public_summary,
            status=status,
        )
        print_json(payload)
        return 0 if payload.get("checksums_verified") else 1
    if args.command == "verify-bundle":
        payload = verify_release_bundle(args.bundle_dir)
        print_json(payload)
        return 0 if payload.get("ok") else 1
    if args.command == "rollback-dry-run":
        payload = rollback_dry_run(
            static_dir=args.static_dir,
            backup_dir=args.backup_dir,
            required_routes=args.route,
        )
        write_json(args.output, payload)
        print_json(payload)
        return 0 if payload.get("status") == "pass" else 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
