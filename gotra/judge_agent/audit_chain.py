"""Append-only audit event hash chain utilities for Judge/Gate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


AUDIT_CHAIN_SCHEMA_VERSION = "gotra.audit_event_chain.v1"
GENESIS_PREV_EVENT_HASH: str | None = None
ACTIVE_STATUSES = {"active", "strong", "active_strong"}
STRONG_STATUSES = {"strong", "active_strong"}


class AuditChainError(ValueError):
    """Raised when an audit event would violate the local audit contract."""


@dataclass(frozen=True)
class AuditChainVerification:
    """Structured verification result for one JSONL audit stream."""

    path: str
    ok: bool
    event_count: int
    verified_event_count: int
    legacy_unverified_count: int
    violation_count: int
    violations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "event_count": self.event_count,
            "verified_event_count": self.verified_event_count,
            "legacy_unverified_count": self.legacy_unverified_count,
            "violation_count": self.violation_count,
            "violations": self.violations,
        }


def canonical_event_json(event: dict[str, Any]) -> str:
    """Return canonical JSON used for event hashing.

    `event_hash` is excluded by definition so the hash can be recomputed after
    persistence. Whitespace and field ordering do not affect the digest.
    """

    payload = {key: value for key, value in event.items() if key != "event_hash"}
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def compute_event_hash(event: dict[str, Any]) -> str:
    """Compute a stable SHA-256 digest for one audit event."""

    return hashlib.sha256(canonical_event_json(event).encode("utf-8")).hexdigest()


def read_audit_events(path: str | Path) -> list[dict[str, Any]]:
    """Read JSONL audit events. Malformed rows are left to the verifier."""

    input_path = Path(path)
    if not input_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def append_audit_event(path: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    """Append one event with `prev_event_hash` and `event_hash` fields."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = latest_event_hash(output_path)
    record = dict(event)
    record.setdefault("audit_chain_schema_version", AUDIT_CHAIN_SCHEMA_VERSION)
    record.setdefault(
        "event_timestamp_utc",
        datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    record["prev_event_hash"] = prev_hash
    record["event_hash"] = compute_event_hash(record)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def latest_event_hash(path: str | Path) -> str | None:
    """Return the last verified event hash in a stream, ignoring legacy rows."""

    input_path = Path(path)
    if not input_path.exists():
        return GENESIS_PREV_EVENT_HASH
    latest: str | None = GENESIS_PREV_EVENT_HASH
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            latest = GENESIS_PREV_EVENT_HASH
            continue
        event_hash = record.get("event_hash")
        latest = str(event_hash) if event_hash else GENESIS_PREV_EVENT_HASH
    return latest


def verify_audit_chain(path: str | Path) -> AuditChainVerification:
    """Verify event hash integrity and prev pointers for one JSONL stream."""

    input_path = Path(path)
    violations: list[dict[str, Any]] = []
    event_count = 0
    verified_count = 0
    legacy_count = 0
    seen_hashes: set[str] = set()
    previous_hash: str | None = GENESIS_PREV_EVENT_HASH
    if not input_path.exists():
        return AuditChainVerification(
            path=str(input_path),
            ok=True,
            event_count=0,
            verified_event_count=0,
            legacy_unverified_count=0,
            violation_count=0,
            violations=[],
        )

    for line_number, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        event_count += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            violations.append(
                {
                    "code": "invalid_json",
                    "line": line_number,
                    "message": f"invalid JSON: {exc}",
                }
            )
            previous_hash = GENESIS_PREV_EVENT_HASH
            continue
        event_hash = record.get("event_hash")
        if not event_hash:
            legacy_count += 1
            previous_hash = GENESIS_PREV_EVENT_HASH
            continue
        event_hash_text = str(event_hash)
        expected_hash = compute_event_hash(record)
        if event_hash_text != expected_hash:
            violations.append(
                {
                    "code": "invalid_hash",
                    "line": line_number,
                    "event_hash": event_hash_text,
                    "expected_event_hash": expected_hash,
                }
            )
        if event_hash_text in seen_hashes:
            violations.append(
                {
                    "code": "duplicate_event_hash",
                    "line": line_number,
                    "event_hash": event_hash_text,
                }
            )
        seen_hashes.add(event_hash_text)
        prev_hash = record.get("prev_event_hash")
        if prev_hash != previous_hash:
            violations.append(
                {
                    "code": "broken_prev_event_hash",
                    "line": line_number,
                    "prev_event_hash": prev_hash,
                    "expected_prev_event_hash": previous_hash,
                }
            )
        verified_count += 1
        previous_hash = event_hash_text

    return AuditChainVerification(
        path=str(input_path),
        ok=not violations,
        event_count=event_count,
        verified_event_count=verified_count,
        legacy_unverified_count=legacy_count,
        violation_count=len(violations),
        violations=violations,
    )


def build_knowledge_transition_event(
    *,
    audit_actor: str,
    gate_id: str,
    decision: str,
    confidence: float,
    reason_code: str | None,
    knowledge_flag: str,
    knowledge_id: str,
    previous_status: str,
    new_status: str,
    run_id: str = "",
    prediction_id: str | None = None,
    feedback_ref: str | None = None,
    source_provenance_ids: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a validated knowledge transition event without writing it."""

    event = {
        "event_type": "knowledge_transition",
        "audit_actor": audit_actor,
        "run_id": run_id,
        "gate_id": gate_id,
        "decision": decision,
        "confidence": confidence,
        "reason_code": reason_code,
        "knowledge_flag": knowledge_flag,
        "knowledge_id": knowledge_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "prediction_id": prediction_id,
        "feedback_ref": feedback_ref,
        "source_provenance_ids": source_provenance_ids or {},
        "transition_audit_status": "audited",
    }
    validate_knowledge_transition_event(event)
    return event


def append_knowledge_transition_event(path: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    """Validate and append a knowledge transition audit event."""

    validate_knowledge_transition_event(event)
    return append_audit_event(path, event)


def validate_knowledge_transition_event(event: dict[str, Any]) -> None:
    """Reject transitions that would bypass the human-gate audit boundary."""

    required = (
        "event_type",
        "audit_actor",
        "gate_id",
        "decision",
        "knowledge_id",
        "previous_status",
        "new_status",
    )
    missing = [field for field in required if not event.get(field)]
    if missing:
        raise AuditChainError("missing_required_transition_provenance: " + ",".join(missing))
    if event.get("event_type") != "knowledge_transition":
        raise AuditChainError("invalid_transition_event_type")
    decision = str(event.get("decision") or "")
    knowledge_flag = str(event.get("knowledge_flag") or "")
    new_status = str(event.get("new_status") or "")
    if decision in {"reject", "defer"} and new_status in ACTIVE_STATUSES:
        raise AuditChainError("non_approving_decision_cannot_activate_knowledge")
    if knowledge_flag == "quarantine_candidate" and new_status in ACTIVE_STATUSES:
        raise AuditChainError("quarantine_candidate_cannot_activate_knowledge")
    if knowledge_flag == "strong_candidate" and new_status in STRONG_STATUSES:
        raise AuditChainError("strong_candidate_requires_human_gate")
    if new_status in ACTIVE_STATUSES and not (
        event.get("prediction_id")
        or event.get("feedback_ref")
        or event.get("source_provenance_ids")
    ):
        raise AuditChainError("active_transition_requires_source_provenance")
