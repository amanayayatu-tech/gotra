"""Judge Agent for resolving low-risk Alaya human gates through audited APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from gotra.judge_agent.alaya_client import AlayaClient


AUDIT_ACTOR = "judge_agent/codex"
MAX_REASONING_CHARS = 300


class DecisionProvider(Protocol):
    """Callable model/provider used by JudgeAgent."""

    def __call__(self, context: dict[str, Any]) -> str | dict[str, Any]:
        """Return a strict JSON decision or equivalent dict."""


class JudgeDecision(BaseModel):
    """Strict JSON decision emitted by the Judge Agent."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    knowledge_flag: str
    audit_actor: str = AUDIT_ACTOR
    reason_code: str | None = None

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        if value not in {"approve", "reject", "defer"}:
            raise ValueError("decision must be approve, reject, or defer")
        return value

    @field_validator("knowledge_flag")
    @classmethod
    def validate_knowledge_flag(cls, value: str) -> str:
        allowed = {"none", "watch", "strong_candidate", "quarantine_candidate"}
        if value not in allowed:
            raise ValueError(f"knowledge_flag must be one of {sorted(allowed)}")
        return value

    @field_validator("audit_actor")
    @classmethod
    def validate_actor(cls, value: str) -> str:
        if value != AUDIT_ACTOR:
            raise ValueError(f"audit_actor must be {AUDIT_ACTOR}")
        return value

    @field_validator("reasoning")
    @classmethod
    def validate_reasoning(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning is required")
        if len(value) > MAX_REASONING_CHARS:
            raise ValueError("reasoning must be <= 300 chars")
        cjk_chars = sum(1 for char in value if "\u4e00" <= char <= "\u9fff")
        ascii_letters = sum(1 for char in value if char.isascii() and char.isalpha())
        if cjk_chars == 0 or ascii_letters > cjk_chars * 4:
            raise ValueError("reasoning must be Simplified Chinese")
        return value


@dataclass(frozen=True)
class JudgeRunResult:
    """Result for one gate evaluation."""

    gate_id: str
    decision: JudgeDecision
    routed_action: str
    response: dict[str, Any] | None = None


class JudgeAgent:
    """Build Judge context, validate strict JSON, and route gate decisions."""

    def __init__(
        self,
        *,
        alaya_client: AlayaClient,
        decision_provider: DecisionProvider,
        data_dir: str | Path = "engine/ksana/data",
    ) -> None:
        self.alaya_client = alaya_client
        self.decision_provider = decision_provider
        self.data_dir = Path(data_dir)

    def judge_gate(self, gate_id: str, *, apply: bool = True) -> JudgeRunResult:
        """Evaluate one gate and optionally route approve/reject through Alaya."""

        gate = self.alaya_client.get_human_gate(gate_id)
        context = self.build_context(gate)
        if context["gate_type"] == "risk" and context["quarantine_list"].get("missing"):
            return JudgeRunResult(
                gate_id=gate_id,
                decision=JudgeDecision(
                    decision="defer",
                    confidence=1.0,
                    reasoning="缺少 Alaya quarantine_list 同步，风险闸门暂停自动处理。",
                    knowledge_flag="watch",
                    audit_actor=AUDIT_ACTOR,
                ),
                routed_action="none",
            )
        decision = parse_judge_decision(self.decision_provider(context))
        if not apply or decision.decision == "defer":
            return JudgeRunResult(gate_id=gate_id, decision=decision, routed_action="none")
        if decision.decision == "approve":
            response = self.alaya_client.approve_gate(gate_id, rationale=decision.reasoning)
            return JudgeRunResult(
                gate_id=gate_id,
                decision=decision,
                routed_action="approve_gate",
                response=response,
            )
        response = self.alaya_client.reject_gate(
            gate_id,
            rationale=decision.reasoning,
            reason_code=decision.reason_code or "risk_too_high",
        )
        return JudgeRunResult(
            gate_id=gate_id,
            decision=decision,
            routed_action="reject_gate",
            response=response,
        )

    def build_context(self, gate: dict[str, Any]) -> dict[str, Any]:
        """Build the Phase B Judge context from Alaya SoR and local ksana artifacts."""

        payload = _decode_jsonish(gate.get("payload"))
        project_id = str(
            gate.get("projectId")
            or payload.get("projectId")
            or payload.get("project_id")
            or ""
        )
        run_id = str(payload.get("run_id") or payload.get("runId") or gate.get("cycleId") or "")
        ticker = str(payload.get("ticker") or payload.get("symbol") or "")
        gate_type = str(gate.get("type") or payload.get("gate_type") or "")
        prompt_text = str(
            payload.get("prompt_text")
            or payload.get("promptText")
            or payload.get("question")
            or gate.get("title")
            or ""
        )
        existing_knowledge = {
            "active": self.alaya_client.list_knowledge(project_id, status="active")
            if project_id
            else [],
            "strong": self.alaya_client.list_knowledge(project_id, status="strong")
            if project_id
            else [],
        }
        return {
            "gate": gate,
            "ticker": ticker,
            "gate_type": gate_type,
            "prompt_text": prompt_text,
            "existing_knowledge": existing_knowledge,
            "fwg_recommendations": load_fwg_recommendations(self.data_dir, run_id=run_id, ticker=ticker),
            "red_team_findings": load_red_team_findings(self.data_dir, run_id=run_id, ticker=ticker),
            "historical_accuracy": self.alaya_client.list_predictions(project_id) if project_id else [],
            "quarantine_list": load_quarantine_list(self.data_dir),
            "output_contract": {
                "decision": "approve|reject|defer",
                "confidence": "0..1",
                "reasoning": "Simplified Chinese, <=300 chars; distinguish methodology disagreement vs potential error",
                "knowledge_flag": "none|watch|strong_candidate|quarantine_candidate",
                "audit_actor": AUDIT_ACTOR,
            },
        }


def parse_judge_decision(value: str | dict[str, Any]) -> JudgeDecision:
    """Parse and validate the strict Judge JSON contract."""

    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Judge provider returned invalid JSON: {exc}") from exc
    else:
        payload = value
    try:
        return JudgeDecision.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Judge provider returned invalid decision: {exc}") from exc


def load_fwg_recommendations(data_dir: str | Path, *, run_id: str, ticker: str) -> list[dict[str, Any]]:
    """Load local F/W/G recommendations at the same run/ticker grain when present."""

    root = Path(data_dir)
    candidates: list[dict[str, Any]] = []
    for path in sorted((root / "recommendations").glob("**/*")):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        data = _read_structured(path)
        if not isinstance(data, dict):
            continue
        haystack = json.dumps(data, ensure_ascii=False)
        if run_id and run_id not in haystack and run_id not in str(path):
            continue
        if ticker and ticker not in haystack and ticker not in str(path):
            continue
        candidates.append({"path": str(path), "data": data})
    return candidates


def load_red_team_findings(data_dir: str | Path, *, run_id: str, ticker: str) -> list[dict[str, Any]]:
    """Load red-team artifacts relevant to the same run/ticker when present."""

    root = Path(data_dir)
    findings: list[dict[str, Any]] = []
    for path in sorted((root / "red_team_audits").glob("**/*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if run_id and run_id not in text and run_id not in str(path):
            continue
        if ticker and ticker not in text and ticker not in str(path):
            continue
        findings.append({"path": str(path), "excerpt": text[:2000]})
    return findings


def load_quarantine_list(data_dir: str | Path) -> dict[str, Any]:
    """Load synced Alaya knowledge filter/quarantine state if present."""

    root = Path(data_dir)
    for path in (
        root / "quarantine_list.yaml",
        root / "knowledge_store" / "quarantine_list.yaml",
        root / "knowledge_filter" / "quarantine_list.yaml",
    ):
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {"items": data}
    return {"items": [], "missing": True}


def _read_structured(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _decode_jsonish(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
