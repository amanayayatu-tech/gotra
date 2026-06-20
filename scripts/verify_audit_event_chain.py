#!/usr/bin/env python3
"""Verify GOTRA Judge/Gate audit event JSONL hash chains."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from gotra.judge_agent.audit_chain import verify_audit_chain


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="audit event JSONL path")
    args = parser.parse_args(argv)

    summary = verify_audit_chain(args.path).to_dict()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
