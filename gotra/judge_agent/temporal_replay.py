"""Offline temporal replay and calibration for GOTRA Judge policies."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gotra.judge_agent.judge_agent import stable_json_hash


REPLAY_SCHEMA_VERSION = "gotra.judge.temporal_replay.v1"
POLICY_CURRENT = "judge_vn_current"
POLICY_CANDIDATE = "judge_vn1_calibrated_candidate"
TERMINAL_PASS = "REPLAY_CALIBRATION_PASS"
TERMINAL_INCONCLUSIVE = "REPLAY_CALIBRATION_INCONCLUSIVE"
TERMINAL_FUTURE_LEAK = "REPLAY_CALIBRATION_FAIL_FUTURE_LEAK"

FORBIDDEN_VISIBLE_FIELD_NAMES = {
    "actual_return_after_decision",
    "expected_decision",
    "future_return",
    "label",
    "labels",
    "outcome",
    "post_horizon",
    "realized_after_decision",
    "risk_outcome",
    "scoring_labels",
    "should_defer",
    "valuable_evidence",
    "would_create_independent_feedback",
}
LABEL_FIELDS = {
    "expected_decision",
    "risk_outcome",
    "valuable_evidence",
    "should_defer",
    "would_create_independent_feedback",
}
DECISIONS = {"approve", "reject", "defer"}


@dataclass(frozen=True)
class ReplayCase:
    """One decision-time Judge replay fixture."""

    case_id: str
    gate_type: str
    decision_date: str
    available_at: str
    visible: dict[str, Any]
    labels: dict[str, Any]


@dataclass(frozen=True)
class ReplayDecision:
    """A deterministic replay policy decision."""

    decision: str
    confidence: float
    reason_code: str
    knowledge_flag: str = "none"


def load_replay_cases(path: str | Path) -> list[ReplayCase]:
    """Load replay fixtures from JSON without network, provider, or env access."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list):
        raise ValueError("temporal replay fixture must be a list or {'cases': [...]}")
    cases = [_parse_case(item, index=index) for index, item in enumerate(raw_cases)]
    duplicate_ids = _duplicates(case.case_id for case in cases)
    if duplicate_ids:
        raise ValueError(f"duplicate replay case_id values: {sorted(duplicate_ids)}")
    return cases


def run_temporal_replay(cases: Sequence[ReplayCase]) -> dict[str, Any]:
    """Run current and candidate offline Judge policies and return metrics/verdict."""

    future_input_violation_count = sum(audit_future_input(case)["future_input_violation_count"] for case in cases)
    policy_results = {
        POLICY_CURRENT: evaluate_policy(cases, policy_name=POLICY_CURRENT),
        POLICY_CANDIDATE: evaluate_policy(cases, policy_name=POLICY_CANDIDATE),
    }
    verdict = classify_replay(
        current=policy_results[POLICY_CURRENT]["metrics"],
        candidate=policy_results[POLICY_CANDIDATE]["metrics"],
        future_input_violation_count=future_input_violation_count,
    )
    return {
        "replay_schema_version": REPLAY_SCHEMA_VERSION,
        "case_count": len(cases),
        "future_input_violation_count": future_input_violation_count,
        "policy_results": policy_results,
        "verdict": verdict,
    }


def evaluate_policy(cases: Sequence[ReplayCase], *, policy_name: str) -> dict[str, Any]:
    """Evaluate one deterministic replay policy on frozen cases."""

    rows = []
    for case in cases:
        decision = decide_case(case, policy_name=policy_name)
        expected = _label_decision(case.labels, "expected_decision")
        correct = decision.decision == expected
        rows.append(
            {
                "case_id": case.case_id,
                "policy": policy_name,
                "decision": decision.decision,
                "confidence": decision.confidence,
                "reason_code": decision.reason_code,
                "expected_decision": expected,
                "correct": correct,
                "risk_outcome": _label_text(case.labels, "risk_outcome"),
                "valuable_evidence": _label_bool(case.labels, "valuable_evidence"),
                "should_defer": _label_bool(case.labels, "should_defer"),
                "would_create_independent_feedback": _label_bool(
                    case.labels,
                    "would_create_independent_feedback",
                ),
                "visible_input_hash": stable_json_hash(case.visible),
            }
        )
    return {"policy": policy_name, "rows": rows, "metrics": compute_metrics(rows)}


def decide_case(case: ReplayCase, *, policy_name: str) -> ReplayDecision:
    if policy_name == POLICY_CURRENT:
        return judge_vn_current(case.visible)
    if policy_name == POLICY_CANDIDATE:
        return judge_vn1_calibrated_candidate(case.visible)
    raise ValueError(f"unknown replay policy: {policy_name}")


def judge_vn_current(visible: Mapping[str, Any]) -> ReplayDecision:
    """Thin legacy replay approximation; not a production Judge provider."""

    signals = _signals(visible)
    if signals["risk_score"] >= 0.9:
        return ReplayDecision("reject", 0.78, "risk_too_high", "quarantine_candidate")
    if signals["duplicate_score"] >= 0.85:
        return ReplayDecision("reject", 0.74, "duplicate_or_noise", "watch")
    if signals["uncertainty_score"] >= 0.85 or signals["evidence_count"] <= 0:
        return ReplayDecision("defer", 0.68, "insufficient_evidence", "watch")
    return ReplayDecision("approve", 0.76, "thin_accept", _knowledge_flag(signals))


def judge_vn1_calibrated_candidate(visible: Mapping[str, Any]) -> ReplayDecision:
    """Structured/calibrated replay policy; not wired into production prompts."""

    signals = _signals(visible)
    if signals["future_source_leak_risk"] or signals["risk_score"] >= 0.74:
        return ReplayDecision("reject", 0.88, "risk_or_future_source_leak", "quarantine_candidate")
    if signals["duplicate_score"] >= 0.7:
        return ReplayDecision("reject", 0.82, "duplicate_or_noise", "watch")
    if signals["evidence_count"] <= 0 or signals["uncertainty_score"] >= 0.65:
        return ReplayDecision("defer", 0.78, "insufficient_or_uncertain", "watch")
    if signals["source_quality"] == "low" or signals["value_score"] < 0.35:
        return ReplayDecision("reject", 0.77, "low_value_or_low_quality", "watch")
    if signals["source_quality"] == "unverified" and signals["value_score"] < 0.75:
        return ReplayDecision("defer", 0.72, "unverified_needs_review", "watch")
    confidence = min(0.92, max(0.66, 0.62 + signals["value_score"] * 0.25 - signals["risk_score"] * 0.1))
    return ReplayDecision("approve", round(confidence, 4), "calibrated_accept", _knowledge_flag(signals))


def compute_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute deterministic replay calibration and gate-quality metrics."""

    total = len(rows)
    high_risk = [row for row in rows if row["risk_outcome"] == "high_risk"]
    valuable = [row for row in rows if row["valuable_evidence"] is True]
    should_defer = [row for row in rows if row["should_defer"] is True]
    safe_no_defer = [
        row
        for row in rows
        if row["risk_outcome"] == "safe" and row["should_defer"] is False
    ]
    approved_feedback = [
        row
        for row in rows
        if row["decision"] == "approve" and row["would_create_independent_feedback"] is True
    ]
    brier_values = [
        (float(row["confidence"]) - (1.0 if row["correct"] else 0.0)) ** 2
        for row in rows
    ]
    return {
        "case_count": total,
        "decision_accuracy": _rate(rows, lambda row: row["correct"] is True),
        "high_risk_case_count": len(high_risk),
        "high_risk_false_pass_rate": _rate(high_risk, lambda row: row["decision"] == "approve"),
        "valuable_case_count": len(valuable),
        "useful_evidence_false_kill_rate": _rate(valuable, lambda row: row["decision"] == "reject"),
        "should_defer_case_count": len(should_defer),
        "defer_reasonableness_rate": _rate(should_defer, lambda row: row["decision"] == "defer"),
        "safe_non_defer_case_count": len(safe_no_defer),
        "over_defer_rate_on_safe_cases": _rate(safe_no_defer, lambda row: row["decision"] == "defer"),
        "brier_score": round(sum(brier_values) / total, 6) if total else 0.0,
        "calibration_bins": calibration_bins(rows),
        "expected_feedback_substrate_yield": len(approved_feedback),
    }


def calibration_bins(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    bins = [
        ("low", 0.0, 0.7),
        ("mid", 0.7, 0.85),
        ("high", 0.85, 1.0000001),
    ]
    output = []
    for name, lower, upper in bins:
        bucket = [row for row in rows if lower <= float(row["confidence"]) < upper]
        output.append(
            {
                "bin": name,
                "count": len(bucket),
                "mean_confidence": round(
                    sum(float(row["confidence"]) for row in bucket) / len(bucket),
                    6,
                )
                if bucket
                else None,
                "accuracy": _rate(bucket, lambda row: row["correct"] is True),
            }
        )
    return output


def classify_replay(
    *,
    current: Mapping[str, Any],
    candidate: Mapping[str, Any],
    future_input_violation_count: int,
) -> str:
    if future_input_violation_count > 0:
        return TERMINAL_FUTURE_LEAK
    candidate_better_risk = candidate["high_risk_false_pass_rate"] < current["high_risk_false_pass_rate"]
    non_worse_false_kill = (
        candidate["useful_evidence_false_kill_rate"] <= current["useful_evidence_false_kill_rate"]
    )
    non_worse_defer = candidate["defer_reasonableness_rate"] >= current["defer_reasonableness_rate"]
    non_worse_over_defer = candidate["over_defer_rate_on_safe_cases"] <= current["over_defer_rate_on_safe_cases"]
    non_worse_brier = candidate["brier_score"] <= current["brier_score"]
    if (
        candidate_better_risk
        and non_worse_false_kill
        and non_worse_defer
        and non_worse_over_defer
        and non_worse_brier
    ):
        return TERMINAL_PASS
    return TERMINAL_INCONCLUSIVE


def audit_future_input(case: ReplayCase) -> dict[str, Any]:
    violations = sorted(_find_forbidden_visible_keys(case.visible))
    return {
        "case_id": case.case_id,
        "future_input_violation_count": len(violations),
        "future_input_violation_keys": violations,
    }


def visible_context(case: ReplayCase) -> dict[str, Any]:
    """Return the policy-visible context after future-field audit."""

    audit = audit_future_input(case)
    if audit["future_input_violation_count"]:
        raise ValueError(f"future/scoring-only fields visible in {case.case_id}: {audit}")
    return dict(case.visible)


def _parse_case(raw: Any, *, index: int) -> ReplayCase:
    if not isinstance(raw, dict):
        raise ValueError(f"replay case #{index} must be an object")
    visible = raw.get("visible")
    labels = raw.get("labels")
    if not isinstance(visible, dict):
        raise ValueError(f"replay case #{index} missing object visible")
    if not isinstance(labels, dict):
        raise ValueError(f"replay case #{index} missing object labels")
    missing_labels = LABEL_FIELDS - set(labels)
    if missing_labels:
        raise ValueError(f"replay case #{index} missing labels: {sorted(missing_labels)}")
    case = ReplayCase(
        case_id=str(raw.get("case_id") or f"case_{index}"),
        gate_type=str(raw.get("gate_type") or visible.get("gate_type") or ""),
        decision_date=str(raw.get("decision_date") or visible.get("decision_date") or ""),
        available_at=str(raw.get("available_at") or visible.get("available_at") or ""),
        visible=dict(visible),
        labels=dict(labels),
    )
    visible_context(case)
    _label_decision(case.labels, "expected_decision")
    _label_text(case.labels, "risk_outcome", allowed={"high_risk", "safe", "uncertain"})
    for field in ("valuable_evidence", "should_defer", "would_create_independent_feedback"):
        _label_bool(case.labels, field)
    return case


def _signals(visible: Mapping[str, Any]) -> dict[str, Any]:
    raw = visible.get("signals")
    signals = raw if isinstance(raw, Mapping) else {}
    return {
        "risk_score": _bounded_float(signals.get("risk_score"), default=0.5),
        "value_score": _bounded_float(signals.get("value_score"), default=0.5),
        "uncertainty_score": _bounded_float(signals.get("uncertainty_score"), default=0.5),
        "duplicate_score": _bounded_float(signals.get("duplicate_score"), default=0.0),
        "evidence_count": max(0, int(signals.get("evidence_count") or 0)),
        "source_quality": str(signals.get("source_quality") or "unknown"),
        "future_source_leak_risk": bool(signals.get("future_source_leak_risk")),
        "strong_conflict": bool(signals.get("strong_conflict")),
    }


def _knowledge_flag(signals: Mapping[str, Any]) -> str:
    if signals["value_score"] >= 0.86 and signals["risk_score"] <= 0.3:
        return "strong_candidate"
    if signals["risk_score"] >= 0.7:
        return "quarantine_candidate"
    return "none"


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return min(1.0, max(0.0, parsed))


def _rate(rows: Sequence[Mapping[str, Any]], predicate) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if predicate(row)) / len(rows), 6)


def _label_decision(labels: Mapping[str, Any], key: str) -> str:
    value = str(labels.get(key) or "")
    if value not in DECISIONS:
        raise ValueError(f"{key} must be one of {sorted(DECISIONS)}")
    return value


def _label_text(labels: Mapping[str, Any], key: str, *, allowed: set[str] | None = None) -> str:
    value = str(labels.get(key) or "")
    if allowed is not None and value not in allowed:
        raise ValueError(f"{key} must be one of {sorted(allowed)}")
    return value


def _label_bool(labels: Mapping[str, Any], key: str) -> bool:
    value = labels.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _find_forbidden_visible_keys(value: Any, *, prefix: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text in FORBIDDEN_VISIBLE_FIELD_NAMES:
                found.add(path)
            found.update(_find_forbidden_visible_keys(child, prefix=path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(_find_forbidden_visible_keys(child, prefix=f"{prefix}[{index}]"))
    return found


def _duplicates(values: Sequence[str] | Any) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local GOTRA Judge temporal replay.")
    parser.add_argument("--fixture", required=True, help="path to temporal replay JSON fixture")
    args = parser.parse_args(argv)
    summary = run_temporal_replay(load_replay_cases(args.fixture))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
