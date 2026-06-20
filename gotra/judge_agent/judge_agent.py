"""Judge Agent for resolving low-risk Alaya human gates through audited APIs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from gotra.judge_agent.alaya_client import AlayaClient


AUDIT_ACTOR = "judge_agent/codex"
MAX_REASONING_CHARS = 300
PROVENANCE_SCHEMA_VERSION = "gotra.judge.decision_provenance.v1"


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
    provenance: dict[str, Any] | None = None


class JudgeAgent:
    """Build Judge context, validate strict JSON, and route gate decisions."""

    def __init__(
        self,
        *,
        alaya_client: AlayaClient,
        decision_provider: DecisionProvider,
        data_dir: str | Path = "engine/ksana/data",
        provenance_log_path: str | Path | None = None,
    ) -> None:
        self.alaya_client = alaya_client
        self.decision_provider = decision_provider
        self.data_dir = Path(data_dir)
        self.provenance_log_path = Path(provenance_log_path) if provenance_log_path else None

    def judge_gate(self, gate_id: str, *, apply: bool = True) -> JudgeRunResult:
        """Evaluate one gate and optionally route approve/reject through Alaya."""

        gate = self.alaya_client.get_human_gate(gate_id)
        context = self.build_context(gate)
        if context["gate_type"] == "risk" and context["quarantine_list"].get("missing"):
            return self._result(
                gate_id=gate_id,
                gate=gate,
                context=context,
                decision=JudgeDecision(
                    decision="defer",
                    confidence=1.0,
                    reasoning="缺少 Alaya quarantine_list 同步，风险闸门暂停自动处理。",
                    knowledge_flag="watch",
                    audit_actor=AUDIT_ACTOR,
                ),
                routed_action="none",
                apply=apply,
                alaya_write_attempted=False,
            )
        decision = parse_judge_decision(self.decision_provider(context))
        if not apply or decision.decision == "defer":
            return self._result(
                gate_id=gate_id,
                gate=gate,
                context=context,
                decision=decision,
                routed_action="none",
                apply=apply,
                alaya_write_attempted=False,
            )
        if decision.decision == "approve":
            try:
                response = self.alaya_client.approve_gate(gate_id, rationale=decision.reasoning)
            except Exception as exc:
                self._result(
                    gate_id=gate_id,
                    gate=gate,
                    context=context,
                    decision=decision,
                    routed_action="approve_gate",
                    apply=apply,
                    alaya_write_attempted=True,
                    routed_action_status="failed",
                    alaya_write_error=exc,
                )
                raise
            return self._result(
                gate_id=gate_id,
                gate=gate,
                context=context,
                decision=decision,
                routed_action="approve_gate",
                response=response,
                apply=apply,
                alaya_write_attempted=True,
                routed_action_status="succeeded",
            )
        try:
            response = self.alaya_client.reject_gate(
                gate_id,
                rationale=decision.reasoning,
                reason_code=decision.reason_code or "risk_too_high",
            )
        except Exception as exc:
            self._result(
                gate_id=gate_id,
                gate=gate,
                context=context,
                decision=decision,
                routed_action="reject_gate",
                apply=apply,
                alaya_write_attempted=True,
                routed_action_status="failed",
                alaya_write_error=exc,
            )
            raise
        return self._result(
            gate_id=gate_id,
            gate=gate,
            context=context,
            decision=decision,
            routed_action="reject_gate",
            response=response,
            apply=apply,
            alaya_write_attempted=True,
            routed_action_status="succeeded",
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
            "gate_id": str(gate.get("id") or ""),
            "project_id": project_id,
            "run_id": run_id,
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
                "reason_code_examples": [
                    "calibrated_accept",
                    "risk_or_future_source_leak",
                    "duplicate_or_noise",
                    "insufficient_or_uncertain",
                    "low_value_or_low_quality",
                    "strong_conflict",
                    "methodology_disagreement",
                    "factual_error",
                    "needs_human_review",
                ],
                "rubric_dimensions": [
                    "methodology_disagreement_vs_factual_error",
                    "evidence_provenance_and_traceability",
                    "future_source_leak_or_decision_date_boundary",
                    "conflict_with_existing_strong_knowledge",
                    "duplicate_noise_or_low_incremental_value",
                    "insufficient_evidence_or_defer_conditions",
                    "likely_clean_outcome_feedback_substrate",
                ],
                "strong_candidate_policy": "report flag only; never auto-promote strong knowledge",
            },
        }

    def _result(
        self,
        *,
        gate_id: str,
        gate: dict[str, Any],
        context: dict[str, Any],
        decision: JudgeDecision,
        routed_action: str,
        apply: bool,
        alaya_write_attempted: bool,
        response: dict[str, Any] | None = None,
        routed_action_status: str = "not_attempted",
        alaya_write_error: Exception | None = None,
    ) -> JudgeRunResult:
        provenance = build_decision_provenance(
            gate_id=gate_id,
            gate=gate,
            context=context,
            decision=decision,
            apply=apply,
            routed_action=routed_action,
            alaya_write_attempted=alaya_write_attempted,
            routed_action_status=routed_action_status,
            alaya_write_error=alaya_write_error,
        )
        if self.provenance_log_path is not None:
            append_decision_provenance(self.provenance_log_path, provenance)
        return JudgeRunResult(
            gate_id=gate_id,
            decision=decision,
            routed_action=routed_action,
            response=response,
            provenance=provenance,
        )


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


def build_decision_provenance(
    *,
    gate_id: str,
    gate: dict[str, Any],
    context: dict[str, Any],
    decision: JudgeDecision,
    apply: bool,
    routed_action: str,
    alaya_write_attempted: bool,
    routed_action_status: str = "not_attempted",
    alaya_write_error: Exception | None = None,
) -> dict[str, Any]:
    """Build one append-only Judge decision provenance record without raw model output."""

    payload = _decode_jsonish(gate.get("payload"))
    decision_payload = decision.model_dump()
    context_fingerprint = {
        "gate_id": gate_id,
        "project_id": context.get("project_id") or payload.get("projectId") or payload.get("project_id"),
        "run_id": context.get("run_id") or payload.get("run_id") or payload.get("runId") or gate.get("cycleId"),
        "ticker": context.get("ticker"),
        "gate_type": context.get("gate_type"),
        "prompt_text": context.get("prompt_text"),
        "active_knowledge_count": len(context.get("existing_knowledge", {}).get("active", [])),
        "strong_knowledge_count": len(context.get("existing_knowledge", {}).get("strong", [])),
        "historical_accuracy_count": len(context.get("historical_accuracy") or []),
        "fwg_recommendation_count": len(context.get("fwg_recommendations") or []),
        "red_team_finding_count": len(context.get("red_team_findings") or []),
    }
    return {
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "run_id": str(context_fingerprint["run_id"] or ""),
        "gate_id": gate_id,
        "decision": decision.decision,
        "confidence": decision.confidence,
        "reason_code": decision.reason_code,
        "knowledge_flag": decision.knowledge_flag,
        "audit_actor": decision.audit_actor,
        "knowledge_id": _first_text(payload, gate, keys=("knowledge_id", "knowledgeId", "knowledge_ref", "knowledgeRef")),
        "prediction_id": _first_text(payload, gate, keys=("prediction_id", "predictionId")),
        "feedback_ref": _first_text(payload, gate, keys=("feedback_ref", "feedbackRef")),
        "apply": apply,
        "dry_run": not apply,
        "routed_action": routed_action,
        "routed_action_status": routed_action_status,
        "alaya_write_attempted": alaya_write_attempted,
        "alaya_write_error_class": type(alaya_write_error).__name__ if alaya_write_error else None,
        "alaya_write_error_message": sanitize_error_message(alaya_write_error),
        "decision_timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "input_hash": stable_json_hash(context_fingerprint),
        "decision_hash": stable_json_hash(decision_payload),
        "gate_payload_hash": stable_json_hash(payload),
    }


def sanitize_error_message(exc: Exception | None) -> str | None:
    if exc is None:
        return None
    message = str(exc).replace("\n", " ")
    redaction_patterns = (
        (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
        (re.compile(r"(?i)\bAuthorization\s*:\s*[^;,\s]+(?:\s+[^;,\s]+)?"), "Authorization: [REDACTED]"),
        (
            re.compile(r"(?i)\b(api[_-]?key|apiKey|token|access[_-]?token)\s*=\s*[^\s,;&]+"),
            lambda match: f"{match.group(1)}=[REDACTED]",
        ),
        (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "sk-[REDACTED]"),
    )
    for pattern, replacement in redaction_patterns:
        message = pattern.sub(replacement, message)
    return message[:300]


def append_decision_provenance(path: str | Path, record: dict[str, Any]) -> None:
    """Append one Judge decision provenance JSONL record."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_decision_provenance(path: str | Path) -> list[dict[str, Any]]:
    """Read Judge decision provenance JSONL records."""

    input_path = Path(path)
    if not input_path.exists():
        return []
    return [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def find_provenance_by_feedback_ref(path: str | Path, feedback_ref: str) -> dict[str, Any] | None:
    """Resolve one feedback_ref back to the Judge provenance record that produced it."""

    for record in read_decision_provenance(path):
        if str(record.get("feedback_ref") or "") == feedback_ref:
            return record
    return None


def stable_json_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for structured audit metadata."""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _first_text(*containers: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for container in containers:
        for key in keys:
            value = container.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
    return None


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
