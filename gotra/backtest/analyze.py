"""Rebuild Phase BT summaries from local run artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from gotra.backtest.audit import AuditViolation, audit_run
from gotra.backtest.statistics import summarize_steps


QualityStatus = str
QUALITY_STATUSES = {"pass", "fail", "low_coverage", "na"}
EVENT_LOG_ONLY_AUDIT_CODES = {"event_actor", "event_log_missing", "event_log_json"}
MIN_PAIRED_COVERAGE = 0.95


@dataclass(frozen=True)
class EventRows:
    rows: list[dict[str, Any]]
    invalid_rows: int = 0
    exists: bool = False


def analyze_run(
    run_root: str | Path,
    *,
    write: bool = True,
    min_paired_coverage: float = MIN_PAIRED_COVERAGE,
) -> dict[str, Any]:
    """Analyze a run directory without calling providers or network services."""

    root = Path(run_root)
    if not root.exists():
        raise FileNotFoundError(f"run root not found: {root}")

    existing_summary = _read_json(root / "summary.json")
    existing_health = _read_json(root / "system_health.json")
    steps = load_steps(root)
    events = read_events(root / "event_log.jsonl")
    audit = audit_run(root)
    metrics = summarize_steps(steps)
    provider_errors = _provider_error_count(steps)
    token_budget = _token_budget(existing_summary, existing_health, steps)
    provider_abort_reason = _provider_abort_reason(existing_summary, existing_health)
    budget_error = str(
        token_budget.get("over_budget_error")
        or ("token budget exceeded" if token_budget.get("over_budget") else "")
    )
    system_health = _system_health(
        existing=existing_health,
        audit_ok=audit.ok,
        provider_errors=provider_errors,
        provider_abort_reason=provider_abort_reason,
        budget_error=budget_error,
        token_budget=token_budget,
        steps=steps,
    )
    summary = _summary(
        existing=existing_summary,
        root=root,
        steps=steps,
        audit=audit.to_dict(),
        metrics=metrics,
        provider_errors=provider_errors,
        system_health=system_health,
        token_budget=token_budget,
        events=events,
    )
    quality_summary = build_quality_summary(
        run_root=root,
        steps=steps,
        audit_violations=audit.violations,
        audit=audit.to_dict(),
        metrics=metrics,
        provider_errors=provider_errors,
        provider_abort_reason=provider_abort_reason,
        token_budget=token_budget,
        events=events,
        min_paired_coverage=min_paired_coverage,
    )
    summary["quality_summary_path"] = str(root / "quality_summary.json")

    if write:
        _write_json(root / "system_health.json", system_health)
        _write_json(root / "summary.json", summary)
        _write_json(root / "quality_summary.json", quality_summary)
    return {"summary": summary, "quality_summary": quality_summary}


def load_steps(run_root: str | Path) -> list[dict[str, Any]]:
    root = Path(run_root)
    steps: list[dict[str, Any]] = []
    for step_path in sorted(root.glob("*/step_*.json")):
        if step_path.parent.name not in {"baseline", "alaya"}:
            continue
        step = _read_json(step_path)
        if not step:
            continue
        step["_artifact_path"] = str(step_path)
        steps.append(step)
    return sorted(
        steps,
        key=lambda item: (
            int(item.get("step") or 0),
            str(item.get("decision_date") or item.get("date") or ""),
            str(item.get("ticker") or ""),
            str(item.get("arm") or ""),
        ),
    )


def read_events(path: str | Path) -> EventRows:
    event_path = Path(path)
    rows: list[dict[str, Any]] = []
    invalid_rows = 0
    if not event_path.exists():
        return EventRows(rows=rows, invalid_rows=0, exists=False)
    for line in event_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid_rows += 1
            continue
        if isinstance(event, dict):
            rows.append(event)
        else:
            invalid_rows += 1
    return EventRows(rows=rows, invalid_rows=invalid_rows, exists=True)


def build_quality_summary(
    *,
    run_root: Path,
    steps: list[dict[str, Any]],
    audit_violations: list[AuditViolation],
    audit: dict[str, Any],
    metrics: dict[str, Any],
    provider_errors: int,
    provider_abort_reason: str,
    token_budget: dict[str, Any],
    events: EventRows,
    min_paired_coverage: float = MIN_PAIRED_COVERAGE,
) -> dict[str, Any]:
    compare = _baseline_compare(run_root)
    event_actor_violations = [
        violation for violation in audit_violations if violation.code == "event_actor"
    ]
    event_log_missing = any(violation.code == "event_log_missing" for violation in audit_violations)
    future_leak_violations = [
        violation
        for violation in audit_violations
        if violation.code not in EVENT_LOG_ONLY_AUDIT_CODES
    ]
    provider_abort = bool(provider_abort_reason)
    over_budget = bool(token_budget.get("over_budget"))
    arms = {str(step.get("arm")) for step in steps}
    paired_steps = int(metrics.get("paired_steps") or 0)
    latency = _latency_observation(events.rows)

    rows = [
        _row(
            "future_leak_audit",
            _future_leak_status(steps=steps, violations=future_leak_violations),
            passed=False if future_leak_violations else (True if steps else None),
            observed={
                "steps_checked": audit.get("steps_checked"),
                "violations": [violation.__dict__ for violation in future_leak_violations],
            },
        ),
        _row(
            "steps_written",
            "pass" if steps else "fail",
            passed=bool(steps),
            observed={"steps_written": len(steps)},
        ),
        _row(
            "provider_errors",
            "pass" if provider_errors == 0 else "fail",
            passed=provider_errors == 0,
            observed={"provider_errors": provider_errors},
        ),
        _row(
            "provider_abort",
            "pass" if not provider_abort else "fail",
            passed=not provider_abort,
            observed={"provider_abort_reason": provider_abort_reason},
        ),
        _row(
            "token_budget",
            "pass" if not over_budget else "fail",
            passed=not over_budget,
            observed=token_budget,
        ),
        _row(
            "event_log_actor",
            _event_log_actor_status(
                events=events,
                steps=steps,
                event_actor_violations=event_actor_violations,
                event_log_missing=event_log_missing,
            ),
            passed=_event_log_actor_passed(
                events=events,
                steps=steps,
                event_actor_violations=event_actor_violations,
                event_log_missing=event_log_missing,
            ),
            observed={
                "event_rows": len(events.rows),
                "invalid_event_rows": events.invalid_rows,
                "event_actor_violations": [violation.__dict__ for violation in event_actor_violations],
                "event_log_missing": event_log_missing,
            },
        ),
        _row(
            "baseline_replay_agreement",
            _compare_status(compare),
            passed=compare.get("passed") if compare else None,
            observed=compare or {"reason": "compare artifact unavailable"},
        ),
        _row(
            "paired_step_coverage",
            _paired_status(
                arms=arms,
                paired_steps=paired_steps,
                scored_steps=int(metrics.get("scored_steps") or 0),
                min_paired_coverage=min_paired_coverage,
            ),
            passed=_paired_passed(
                arms=arms,
                paired_steps=paired_steps,
                scored_steps=int(metrics.get("scored_steps") or 0),
                min_paired_coverage=min_paired_coverage,
            ),
            observed={
                "arms": sorted(arms),
                "paired_steps": paired_steps,
                "scored_steps": int(metrics.get("scored_steps") or 0),
                "coverage": _paired_coverage(
                    paired_steps=paired_steps,
                    scored_steps=int(metrics.get("scored_steps") or 0),
                ),
                "min_paired_coverage": min_paired_coverage,
            },
        ),
        _row(
            "latency_observed",
            "pass" if latency else "na",
            passed=True if latency else None,
            observed=latency or {"reason": "event timestamps unavailable"},
        ),
    ]
    return {
        "schema": "gotra.bt.quality_summary.v1",
        "run_id": run_root.name,
        "generated_at": datetime.now().astimezone().isoformat(),
        "sources": {
            "steps": "<run_root>/{baseline,alaya}/step_*.json",
            "events": "event_log.jsonl",
            "system_health": "system_health.json",
            "compare": "compare*.json when present",
        },
        "status_values": sorted(QUALITY_STATUSES),
        "rows": rows,
        "overall_status": _overall_status(rows),
        "blocking_failed": any(row["status"] == "fail" for row in rows if row["blocking"]),
    }


def _summary(
    *,
    existing: dict[str, Any],
    root: Path,
    steps: list[dict[str, Any]],
    audit: dict[str, Any],
    metrics: dict[str, Any],
    provider_errors: int,
    system_health: dict[str, Any],
    token_budget: dict[str, Any],
    events: EventRows,
) -> dict[str, Any]:
    first_step = steps[0] if steps else {}
    summary = dict(existing)
    summary.update(
        {
            "run_id": existing.get("run_id") or root.name,
            "mode": existing.get("mode") or first_step.get("run_mode"),
            "provider": existing.get("provider") or first_step.get("provider"),
            "steps_written": len(steps),
            "arms": sorted({str(step.get("arm")) for step in steps if step.get("arm")}),
            "tickers": sorted({str(step.get("ticker")) for step in steps if step.get("ticker")}),
            "provider_errors": provider_errors,
            "token_budget": token_budget,
            "system_health": system_health,
            "audit": audit,
            "metrics": metrics,
            "event_log": {
                "rows": len(events.rows),
                "invalid_rows": events.invalid_rows,
                "source": "event_log.jsonl" if events.exists else "missing",
            },
            "analysis_rebuilt_from_artifacts": True,
        }
    )
    return summary


def _system_health(
    *,
    existing: dict[str, Any],
    audit_ok: bool,
    provider_errors: int,
    provider_abort_reason: str,
    budget_error: str,
    token_budget: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    health = dict(existing)
    status = str(health.get("status") or "ok")
    alerts = list(health.get("alerts") or [])
    if budget_error:
        status = "paused"
        alerts.append(budget_error)
    elif provider_abort_reason:
        status = "aborted_provider_unhealthy"
        alerts.append(provider_abort_reason)
    elif not audit_ok or provider_errors:
        status = "failed"
        if not audit_ok:
            alerts.append("future-function audit failed")
        if provider_errors:
            alerts.append(f"provider_error steps: {provider_errors}")
    health.update(
        {
            "status": status,
            "paused": bool(budget_error),
            "pause_reason": str(health.get("pause_reason") or budget_error),
            "aborted_provider_unhealthy": bool(provider_abort_reason),
            "provider_abort_reason": provider_abort_reason,
            "alerts": sorted(set(str(alert) for alert in alerts if alert)),
            "provider_errors": provider_errors,
            "sampled_validation_only": bool(
                health.get("sampled_validation_only")
                or any(step.get("run_mode") == "sampled" or step.get("provider") == "heuristic" for step in steps)
            ),
            "token_budget": token_budget,
        }
    )
    return health


def _token_budget(
    existing_summary: dict[str, Any],
    existing_health: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    existing = existing_health.get("token_budget") or existing_summary.get("token_budget")
    if isinstance(existing, dict):
        return dict(existing)
    cache_hits = sum(1 for step in steps if step.get("cache_hit") is True)
    cache_misses = sum(1 for step in steps if step.get("cache_hit") is False)
    spent_tokens = sum(int(step.get("estimated_tokens") or 0) for step in steps if not step.get("cache_hit"))
    return {
        "max_tokens": None,
        "spent_tokens": spent_tokens,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "over_budget": False,
        "over_budget_error": "",
        "source": "reconstructed_from_steps",
    }


def _provider_abort_reason(existing_summary: dict[str, Any], existing_health: dict[str, Any]) -> str:
    reason = str(
        existing_summary.get("provider_abort_reason")
        or existing_health.get("provider_abort_reason")
        or ""
    )
    if reason:
        return reason
    if existing_summary.get("aborted_provider_unhealthy") or existing_health.get(
        "aborted_provider_unhealthy"
    ):
        return "aborted_provider_unhealthy"
    return ""


def _provider_error_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "provider_error"
        or step.get("error_type") == "provider_error"
        or bool(step.get("provider_error"))
    )


def _baseline_compare(run_root: Path) -> dict[str, Any]:
    candidates = sorted(run_root.glob("compare*.json")) + sorted(run_root.glob("*compare*.json"))
    for path in candidates:
        payload = _read_json(path)
        if payload:
            payload = dict(payload)
            payload["source"] = str(path)
            return payload
    return {}


def _compare_status(compare: dict[str, Any]) -> QualityStatus:
    if not compare:
        return "na"
    if compare.get("passed") is True:
        return "pass"
    return "fail"


def _future_leak_status(
    *,
    steps: list[dict[str, Any]],
    violations: list[AuditViolation],
) -> QualityStatus:
    if not steps:
        return "na"
    return "fail" if violations else "pass"


def _event_log_actor_status(
    *,
    events: EventRows,
    steps: list[dict[str, Any]],
    event_actor_violations: list[AuditViolation],
    event_log_missing: bool,
) -> QualityStatus:
    if events.invalid_rows or event_actor_violations:
        return "fail"
    if event_log_missing or (steps and not events.rows):
        return "low_coverage"
    if not steps and not events.rows:
        return "na"
    return "pass"


def _event_log_actor_passed(
    *,
    events: EventRows,
    steps: list[dict[str, Any]],
    event_actor_violations: list[AuditViolation],
    event_log_missing: bool,
) -> bool | None:
    status = _event_log_actor_status(
        events=events,
        steps=steps,
        event_actor_violations=event_actor_violations,
        event_log_missing=event_log_missing,
    )
    if status == "pass":
        return True
    if status == "fail":
        return False
    return None


def _paired_status(
    *,
    arms: set[str],
    paired_steps: int,
    scored_steps: int,
    min_paired_coverage: float,
) -> QualityStatus:
    if not {"baseline", "alaya"}.issubset(arms):
        return "na"
    coverage = _paired_coverage(paired_steps=paired_steps, scored_steps=scored_steps)
    return "pass" if coverage is not None and coverage >= min_paired_coverage else "low_coverage"


def _paired_passed(
    *,
    arms: set[str],
    paired_steps: int,
    scored_steps: int,
    min_paired_coverage: float,
) -> bool | None:
    status = _paired_status(
        arms=arms,
        paired_steps=paired_steps,
        scored_steps=scored_steps,
        min_paired_coverage=min_paired_coverage,
    )
    if status == "na":
        return None
    return status == "pass"


def _paired_coverage(*, paired_steps: int, scored_steps: int) -> float | None:
    if scored_steps <= 0:
        return None
    return round((2 * paired_steps) / scored_steps, 6)


def _latency_observation(events: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = []
    for event in events:
        for key in ("elapsed_ms", "latency_ms", "provider_latency_ms", "duration_ms"):
            value = event.get(key)
            if isinstance(value, int | float) and value >= 0:
                latencies.append(float(value))
                break
    if not latencies:
        return {}
    return {
        "event_count": len(events),
        "latency_events": len(latencies),
        "max_ms": round(max(latencies), 3),
        "mean_ms": round(sum(latencies) / len(latencies), 3),
    }


def _row(
    metric: str,
    status: QualityStatus,
    *,
    passed: bool | None,
    observed: dict[str, Any],
    blocking: bool = True,
) -> dict[str, Any]:
    if status not in QUALITY_STATUSES:
        raise ValueError(f"unsupported quality status: {status!r}")
    return {
        "metric": metric,
        "name": metric,
        "status": status,
        "passed": passed,
        "blocking": blocking,
        "observed": observed,
    }


def _overall_status(rows: list[dict[str, Any]]) -> QualityStatus:
    statuses = {str(row["status"]) for row in rows}
    if "fail" in statuses:
        return "fail"
    if "low_coverage" in statuses:
        return "low_coverage"
    if "pass" in statuses:
        return "pass"
    return "na"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a Phase BT run directory.")
    parser.add_argument("--run-root", required=True, help="Path to data/backtest/runs/<run_id>.")
    parser.add_argument("--no-write", action="store_true", help="Print analysis without writing artifacts.")
    parser.add_argument(
        "--min-paired-coverage",
        type=float,
        default=MIN_PAIRED_COVERAGE,
        help="Minimum paired scored-step coverage for the paired_step_coverage row.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_run(
        args.run_root,
        write=not args.no_write,
        min_paired_coverage=args.min_paired_coverage,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    rows = result["quality_summary"]["rows"]
    return 1 if any(row["status"] == "fail" for row in rows if row["blocking"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
