"""Future-function and audit-log checks for Phase BT outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
from typing import Any

from gotra.backtest.protocol import parse_date


@dataclass(frozen=True)
class AuditViolation:
    code: str
    message: str
    path: str = ""


@dataclass
class AuditResult:
    steps_checked: int = 0
    event_rows_checked: int = 0
    violations: list[AuditViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "steps_checked": self.steps_checked,
            "event_rows_checked": self.event_rows_checked,
            "violations": [violation.__dict__ for violation in self.violations],
        }


def audit_run(run_root: str | Path) -> AuditResult:
    root = Path(run_root)
    result = AuditResult()
    for step_path in sorted(root.glob("*/step_*.json")):
        if step_path.parent.name not in {"alaya", "baseline"}:
            continue
        step = json.loads(step_path.read_text(encoding="utf-8"))
        result.steps_checked += 1
        result.violations.extend(audit_step(step, path=str(step_path)))

    event_log = root / "event_log.jsonl"
    if event_log.exists():
        for line_number, line in enumerate(event_log.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            result.event_rows_checked += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                result.violations.append(
                    AuditViolation("event_log_json", f"invalid JSON: {exc}", f"{event_log}:{line_number}")
                )
                continue
            if event.get("actor") != "backtest/walk_forward":
                result.violations.append(
                    AuditViolation(
                        "event_actor",
                        f"unexpected event actor: {event.get('actor')!r}",
                        f"{event_log}:{line_number}",
                    )
                )
    elif result.steps_checked:
        result.violations.append(AuditViolation("event_log_missing", "event_log.jsonl missing", str(event_log)))
    return result


def audit_step(step: dict[str, Any], *, path: str = "") -> list[AuditViolation]:
    violations: list[AuditViolation] = []
    decision_date = _date_or_violation(step.get("decision_date"), "decision_date", violations, path)
    outcome_as_of = _date_or_violation(step.get("outcome_as_of"), "outcome_as_of", violations, path)

    if step.get("future_data_allowed") is not False:
        violations.append(
            AuditViolation("future_data_allowed", "future_data_allowed must be false", path)
        )
    if step.get("provider_network_enabled") is not False:
        violations.append(
            AuditViolation(
                "provider_network_enabled",
                "BT decision provider must not use network research",
                path,
            )
        )
    if step.get("audit_actor") != "backtest/walk_forward":
        violations.append(
            AuditViolation("audit_actor", f"unexpected audit_actor: {step.get('audit_actor')!r}", path)
        )
    if decision_date is not None:
        for item in step.get("decision_inputs") or []:
            _audit_manifest_item(
                item,
                cutoff=decision_date,
                cutoff_name="decision_date",
                code="decision_input_future",
                path=path,
                violations=violations,
            )
    if outcome_as_of is not None:
        for item in step.get("outcome_inputs") or []:
            _audit_manifest_item(
                item,
                cutoff=outcome_as_of,
                cutoff_name="outcome_as_of",
                code="outcome_input_future",
                path=path,
                violations=violations,
            )
    return violations


def _audit_manifest_item(
    item: dict[str, Any],
    *,
    cutoff: date,
    cutoff_name: str,
    code: str,
    path: str,
    violations: list[AuditViolation],
) -> None:
    availability = _date_or_violation(item.get("availability_date"), "availability_date", violations, path)
    if availability is None:
        return
    if availability > cutoff:
        violations.append(
            AuditViolation(
                code,
                f"{item.get('name') or item.get('source')} availability_date={availability} "
                f"is after {cutoff_name}={cutoff}",
                path,
            )
        )


def _date_or_violation(
    value: Any,
    field_name: str,
    violations: list[AuditViolation],
    path: str,
) -> date | None:
    try:
        return parse_date(str(value))
    except (TypeError, ValueError):
        violations.append(AuditViolation("invalid_date", f"invalid {field_name}: {value!r}", path))
        return None
