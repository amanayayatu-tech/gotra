"""Compare Phase BT run outputs for replay consistency checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gotra.backtest.walk_forward import Arm


def direction_agreement(
    *,
    reference_run: Path,
    candidate_run: Path,
    arm: Arm = "baseline",
) -> dict[str, Any]:
    reference = _load_scored_steps(reference_run / arm)
    candidate = _load_scored_steps(candidate_run / arm)
    same = 0
    mismatches: list[dict[str, Any]] = []
    for key, reference_step in sorted(reference.items()):
        candidate_step = candidate.get(key)
        if candidate_step is None:
            mismatches.append(
                {
                    "ticker": key[0],
                    "decision_date": key[1],
                    "reference_direction": reference_step.get("decision_direction"),
                    "candidate_direction": None,
                    "reason": "missing_candidate_step",
                }
            )
            continue
        reference_direction = reference_step.get("decision_direction")
        candidate_direction = candidate_step.get("decision_direction")
        if reference_direction == candidate_direction:
            same += 1
        else:
            mismatches.append(
                {
                    "ticker": key[0],
                    "decision_date": key[1],
                    "reference_direction": reference_direction,
                    "candidate_direction": candidate_direction,
                    "reason": "direction_mismatch",
                }
            )
    total = len(reference)
    return {
        "arm": arm,
        "reference_run": str(reference_run),
        "candidate_run": str(candidate_run),
        "same": same,
        "total": total,
        "rate": same / total if total else None,
        "mismatches": mismatches,
    }


def _load_scored_steps(arm_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    steps: dict[tuple[str, str], dict[str, Any]] = {}
    for step_path in sorted(arm_dir.glob("step_*.json")):
        step = json.loads(step_path.read_text(encoding="utf-8"))
        if step.get("status") != "scored":
            continue
        key = (str(step.get("ticker")), str(step.get("decision_date")))
        steps[key] = step
    return steps


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Phase BT replay directions.")
    parser.add_argument("--reference-run", required=True)
    parser.add_argument("--candidate-run", required=True)
    parser.add_argument("--arm", choices=["baseline", "alaya"], default="baseline")
    parser.add_argument("--threshold", type=float, default=0.95)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = direction_agreement(
        reference_run=Path(args.reference_run),
        candidate_run=Path(args.candidate_run),
        arm=args.arm,
    )
    result["threshold"] = args.threshold
    rate = result["rate"]
    result["passed"] = rate is not None and rate >= args.threshold
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
