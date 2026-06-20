from __future__ import annotations

import json
from pathlib import Path

import pytest

from gotra.judge_agent.audit_chain import (
    AuditChainError,
    append_audit_event,
    append_knowledge_transition_event,
    build_knowledge_transition_event,
    canonical_event_json,
    compute_event_hash,
    verify_audit_chain,
)


def test_append_audit_event_adds_hash_chain_and_verifies(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    first = append_audit_event(path, _gate_event("gate-1", "approve"))
    second = append_audit_event(path, _gate_event("gate-2", "reject"))

    assert first["prev_event_hash"] is None
    assert len(first["event_hash"]) == 64
    assert second["prev_event_hash"] == first["event_hash"]
    assert second["event_hash"] == compute_event_hash(second)
    summary = verify_audit_chain(path).to_dict()
    assert summary["ok"] is True
    assert summary["event_count"] == 2
    assert summary["verified_event_count"] == 2
    assert summary["legacy_unverified_count"] == 0


def test_event_hash_is_canonical_and_excludes_event_hash() -> None:
    event_a = {"b": 2, "a": {"z": 3, "y": 4}, "event_hash": "old"}
    event_b = {"event_hash": "different", "a": {"y": 4, "z": 3}, "b": 2}

    assert canonical_event_json(event_a) == canonical_event_json(event_b)
    assert compute_event_hash(event_a) == compute_event_hash(event_b)


def test_verifier_detects_tampered_event_body(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    append_audit_event(path, _gate_event("gate-1", "approve"))
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    record["decision"] = "reject"
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    summary = verify_audit_chain(path).to_dict()
    assert summary["ok"] is False
    assert summary["violations"][0]["code"] == "invalid_hash"


def test_verifier_detects_reordered_events(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    append_audit_event(path, _gate_event("gate-1", "approve"))
    append_audit_event(path, _gate_event("gate-2", "reject"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")

    summary = verify_audit_chain(path).to_dict()
    assert summary["ok"] is False
    assert any(item["code"] == "broken_prev_event_hash" for item in summary["violations"])


def test_verifier_detects_missing_event_broken_prev_pointer(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    append_audit_event(path, _gate_event("gate-1", "approve"))
    append_audit_event(path, _gate_event("gate-2", "reject"))
    append_audit_event(path, _gate_event("gate-3", "defer"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    summary = verify_audit_chain(path).to_dict()
    assert summary["ok"] is False
    assert any(item["code"] == "broken_prev_event_hash" for item in summary["violations"])


def test_verifier_detects_duplicate_event_hash(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    append_audit_event(path, _gate_event("gate-1", "approve"))
    line = path.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    summary = verify_audit_chain(path).to_dict()
    assert summary["ok"] is False
    assert any(item["code"] == "duplicate_event_hash" for item in summary["violations"])


def test_verifier_reports_legacy_unverified_events(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(json.dumps({"event_type": "legacy", "gate_id": "old"}) + "\n", encoding="utf-8")
    append_audit_event(path, _gate_event("gate-1", "approve"))

    summary = verify_audit_chain(path).to_dict()
    assert summary["ok"] is True
    assert summary["legacy_unverified_count"] == 1
    assert summary["verified_event_count"] == 1


def test_knowledge_transition_event_chains_to_gate_decision(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    decision_event = append_audit_event(path, _gate_event("gate-1", "approve"))
    transition = build_knowledge_transition_event(
        audit_actor="judge_agent/codex",
        gate_id="gate-1",
        decision="approve",
        confidence=0.91,
        reason_code="calibrated_accept",
        knowledge_flag="none",
        knowledge_id="knowledge-1",
        previous_status="candidate",
        new_status="active",
        run_id="RUN-1",
        prediction_id="prediction-1",
        feedback_ref="feedback-1",
        source_provenance_ids={"decision_event_hash": decision_event["event_hash"]},
    )
    transition_event = append_knowledge_transition_event(path, transition)

    assert transition_event["event_type"] == "knowledge_transition"
    assert transition_event["prev_event_hash"] == decision_event["event_hash"]
    assert transition_event["source_provenance_ids"]["decision_event_hash"] == decision_event["event_hash"]
    assert verify_audit_chain(path).ok is True


@pytest.mark.parametrize(
    ("decision", "knowledge_flag", "new_status", "expected_error"),
    [
        ("approve", "strong_candidate", "strong", "strong_candidate_requires_human_gate"),
        ("reject", "none", "active", "non_approving_decision_cannot_activate_knowledge"),
        ("defer", "watch", "active", "non_approving_decision_cannot_activate_knowledge"),
        ("approve", "quarantine_candidate", "active", "quarantine_candidate_cannot_activate_knowledge"),
    ],
)
def test_human_gate_negative_transitions_are_rejected(
    decision: str,
    knowledge_flag: str,
    new_status: str,
    expected_error: str,
) -> None:
    with pytest.raises(AuditChainError, match=expected_error):
        build_knowledge_transition_event(
            audit_actor="judge_agent/codex",
            gate_id="gate-1",
            decision=decision,
            confidence=0.7,
            reason_code="needs_human_review",
            knowledge_flag=knowledge_flag,
            knowledge_id="knowledge-1",
            previous_status="candidate",
            new_status=new_status,
            prediction_id="prediction-1",
        )


def test_active_transition_without_provenance_is_rejected() -> None:
    with pytest.raises(AuditChainError, match="active_transition_requires_source_provenance"):
        build_knowledge_transition_event(
            audit_actor="judge_agent/codex",
            gate_id="gate-1",
            decision="approve",
            confidence=0.7,
            reason_code="calibrated_accept",
            knowledge_flag="none",
            knowledge_id="knowledge-1",
            previous_status="candidate",
            new_status="active",
        )


def test_transition_missing_required_provenance_is_not_audited_pass() -> None:
    with pytest.raises(AuditChainError, match="missing_required_transition_provenance"):
        build_knowledge_transition_event(
            audit_actor="judge_agent/codex",
            gate_id="",
            decision="approve",
            confidence=0.7,
            reason_code="calibrated_accept",
            knowledge_flag="none",
            knowledge_id="knowledge-1",
            previous_status="candidate",
            new_status="watch",
            prediction_id="prediction-1",
        )


def _gate_event(gate_id: str, decision: str) -> dict[str, object]:
    return {
        "event_type": "gate_decision",
        "audit_actor": "judge_agent/codex",
        "run_id": "RUN-1",
        "gate_id": gate_id,
        "decision": decision,
        "confidence": 0.8,
        "reason_code": "calibrated_accept",
        "knowledge_flag": "none",
        "knowledge_id": "knowledge-1",
        "previous_status": "pending",
        "new_status": "approved" if decision == "approve" else "pending",
        "prediction_id": "prediction-1",
        "feedback_ref": "feedback-1",
        "source_provenance_ids": {"source": "fixture"},
        "event_timestamp_utc": "2026-06-21T00:00:00Z",
    }
