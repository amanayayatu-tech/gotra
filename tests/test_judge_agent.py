from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
import yaml

from gotra.judge_agent.gate_poller import GatePoller, auto_judge_enabled
from gotra.judge_agent.judge_agent import AUDIT_ACTOR, JudgeAgent, parse_judge_decision


class FakeAlayaClient:
    def __init__(self) -> None:
        self.gates: dict[str, dict[str, Any]] = {
            "gate_meaning": {
                "id": "gate_meaning",
                "type": "meaning",
                "cycleId": "RUN-1",
                "title": "Meaning gate for META",
                "status": "pending",
                "payload": {
                    "projectId": "proj_1",
                    "ticker": "META",
                    "run_id": "RUN-1",
                    "prompt_text": "Should META AI ads evidence enter active knowledge?",
                },
            },
            "gate_risk": {
                "id": "gate_risk",
                "type": "risk",
                "cycleId": "RUN-1",
                "title": "Risk gate for META",
                "status": "pending",
                "payload": {
                    "projectId": "proj_1",
                    "ticker": "META",
                    "run_id": "RUN-1",
                    "prompt_text": "Is risk too high?",
                },
            },
        }
        self.knowledge = {
            "active": [{"id": "kb_active", "status": "active", "sourceRef": "PR-1"}],
            "strong": [{"id": "kb_strong", "status": "strong", "sourceRef": "PR-2"}],
        }
        self.predictions = [{"id": "pred_1", "predictionError": 0.04}]
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get_human_gate(self, gate_id: str) -> dict[str, Any]:
        return self.gates[gate_id]

    def list_human_gates(self, **kwargs) -> list[dict[str, Any]]:
        status = kwargs.get("status")
        return [gate for gate in self.gates.values() if not status or gate["status"] == status]

    def approve_gate(self, gate_id: str, *, rationale: str) -> dict[str, Any]:
        self.calls.append(("approve_gate", gate_id, {"rationale": rationale}))
        self.gates[gate_id]["status"] = "approved"
        return {"id": gate_id, "status": "approved", "decision": "approve"}

    def reject_gate(self, gate_id: str, *, rationale: str, reason_code: str = "risk_too_high") -> dict[str, Any]:
        self.calls.append(("reject_gate", gate_id, {"rationale": rationale, "reasonCode": reason_code}))
        self.gates[gate_id]["status"] = "rejected"
        return {"id": gate_id, "status": "rejected", "decision": "reject"}

    def list_knowledge(self, project_id: str, *, status: str) -> list[dict[str, Any]]:
        assert project_id == "proj_1"
        return list(self.knowledge[status])

    def list_predictions(self, project_id: str) -> list[dict[str, Any]]:
        assert project_id == "proj_1"
        return list(self.predictions)


def write_local_context(data_dir: Path) -> None:
    rec_dir = data_dir / "recommendations" / "20260614"
    rec_dir.mkdir(parents=True)
    (rec_dir / "R-FP-META.yaml").write_text(
        yaml.safe_dump({"run_id": "RUN-1", "ticker": "META", "direction": "watch"}),
        encoding="utf-8",
    )
    audit_dir = data_dir / "red_team_audits" / "20260614"
    audit_dir.mkdir(parents=True)
    (audit_dir / "AUDIT-META.md").write_text("RUN-1 META no critical finding", encoding="utf-8")
    (data_dir / "quarantine_list.yaml").write_text(
        yaml.safe_dump({"items": [{"source_pr_id": "PR-old", "status": "quarantined"}]}),
        encoding="utf-8",
    )


def decision_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "decision": "approve",
        "confidence": 0.82,
        "reasoning": "证据链一致，未见潜在错误；这是方法论可接受差异。",
        "knowledge_flag": "none",
        "audit_actor": AUDIT_ACTOR,
    }
    payload.update(overrides)
    return payload


def test_parse_judge_decision_enforces_strict_contract() -> None:
    decision = parse_judge_decision(decision_payload())

    assert decision.decision == "approve"
    assert decision.audit_actor == AUDIT_ACTOR

    with pytest.raises(ValueError):
        parse_judge_decision(decision_payload(audit_actor="human"))
    with pytest.raises(ValueError):
        parse_judge_decision(decision_payload(reasoning="x" * 301))
    with pytest.raises(ValueError):
        parse_judge_decision(decision_payload(reasoning="This is an English reason."))


def test_judge_context_reads_alaya_knowledge_sor_and_local_artifacts(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    write_local_context(data_dir)
    client = FakeAlayaClient()
    seen_context: dict[str, Any] = {}

    def provider(context: dict[str, Any]) -> dict[str, Any]:
        seen_context.update(context)
        return decision_payload()

    result = JudgeAgent(alaya_client=client, decision_provider=provider, data_dir=data_dir).judge_gate(
        "gate_meaning"
    )

    assert result.routed_action == "approve_gate"
    assert client.calls == [("approve_gate", "gate_meaning", {"rationale": result.decision.reasoning})]
    assert seen_context["ticker"] == "META"
    assert seen_context["gate_type"] == "meaning"
    assert seen_context["existing_knowledge"]["active"][0]["id"] == "kb_active"
    assert seen_context["existing_knowledge"]["strong"][0]["id"] == "kb_strong"
    assert seen_context["fwg_recommendations"][0]["path"].endswith("R-FP-META.yaml")
    assert seen_context["red_team_findings"][0]["path"].endswith("AUDIT-META.md")
    assert seen_context["historical_accuracy"] == [{"id": "pred_1", "predictionError": 0.04}]
    assert seen_context["quarantine_list"]["items"][0]["source_pr_id"] == "PR-old"


def test_judge_reject_routes_to_gate_reject_with_reason_code(tmp_path: Path) -> None:
    write_local_context(tmp_path)
    client = FakeAlayaClient()

    def provider(context: dict[str, Any]) -> dict[str, Any]:
        return decision_payload(
            decision="reject",
            confidence=0.91,
            reasoning="潜在错误风险过高，需人工复核。",
            knowledge_flag="quarantine_candidate",
            reason_code="risk_too_high",
        )

    result = JudgeAgent(alaya_client=client, decision_provider=provider, data_dir=tmp_path).judge_gate(
        "gate_risk"
    )

    assert result.routed_action == "reject_gate"
    assert client.calls == [
        (
            "reject_gate",
            "gate_risk",
            {"rationale": "潜在错误风险过高，需人工复核。", "reasonCode": "risk_too_high"},
        )
    ]


def test_risk_gate_defers_when_quarantine_filter_sync_is_missing(tmp_path: Path) -> None:
    client = FakeAlayaClient()
    provider_called = False

    def provider(context: dict[str, Any]) -> dict[str, Any]:
        nonlocal provider_called
        provider_called = True
        return decision_payload(decision="reject")

    result = JudgeAgent(alaya_client=client, decision_provider=provider, data_dir=tmp_path).judge_gate(
        "gate_risk"
    )

    assert result.routed_action == "none"
    assert result.decision.decision == "defer"
    assert "quarantine_list" in result.decision.reasoning
    assert provider_called is False
    assert client.calls == []


def test_strong_candidate_does_not_call_knowledge_approve(tmp_path: Path) -> None:
    client = FakeAlayaClient()

    result = JudgeAgent(
        alaya_client=client,
        decision_provider=lambda context: decision_payload(knowledge_flag="strong_candidate"),
        data_dir=tmp_path,
    ).judge_gate("gate_meaning")

    assert result.routed_action == "approve_gate"
    assert all(call[0] != "approve_knowledge" for call in client.calls)


def test_ci_contract_has_no_automation_strong_promotion_paths() -> None:
    source_root = Path(__file__).resolve().parents[1] / "gotra" / "judge_agent"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.glob("*.py")
        if path.name != "__init__.py"
    )

    assert "/api/knowledge/{knowledge_id}/quarantine" in source
    assert "/api/knowledge/{knowledge_id}/approve" not in source
    assert "/approve" not in source.replace("/api/human-gates/{gate_id}/{action}", "")
    assert "approve_knowledge" not in source
    assert "humanApprovedCount" not in source
    assert '"status": "strong"' not in source


def test_gate_poller_auto_judge_false_exits(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_JUDGE", "false")
    poller = GatePoller(
        judge=object(),  # type: ignore[arg-type]
        alaya_client=object(),  # type: ignore[arg-type]
    )

    assert auto_judge_enabled() is False
    with pytest.raises(SystemExit) as exc:
        poller.run_forever()
    assert exc.value.code == 0


def test_gate_poller_warns_after_five_failures(monkeypatch) -> None:
    client = FakeAlayaClient()
    stream = io.StringIO()

    class FailingJudge:
        def judge_gate(self, gate_id: str, *, apply: bool = True):
            raise RuntimeError(f"fail {gate_id}")

    poller = GatePoller(
        judge=FailingJudge(),  # type: ignore[arg-type]
        alaya_client=client,  # type: ignore[arg-type]
        interval_seconds=0.1,
        stderr=stream,
    )

    for _ in range(5):
        try:
            poller.poll_once()
        except RuntimeError:
            poller.consecutive_failures += 1
            if poller.consecutive_failures >= 5:
                print(f"[judge-poller] {poller.consecutive_failures} consecutive failures", file=stream)

    assert "5 consecutive failures" in stream.getvalue()
