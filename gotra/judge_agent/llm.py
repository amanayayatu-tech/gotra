"""Judge Agent LLM client factory."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

from chairman.llm.narrative_generator import CodexCliClient

from gotra.judge_agent.judge_agent import AUDIT_ACTOR


def build_judge_client() -> CodexCliClient:
    """Build the Judge Agent Codex CLI client with a read-only clean profile."""

    load_dotenv()
    os.environ["CODEX_PROVIDER_REASONING_EFFORT"] = os.getenv(
        "JUDGE_CODEX_REASONING_EFFORT", "xhigh"
    )
    os.environ.setdefault("CODEX_PROVIDER_SANDBOX", "read-only")
    os.environ.setdefault("CODEX_PROVIDER_CLEAN", "1")
    return CodexCliClient(model=os.getenv("JUDGE_LLM_MODEL", "gpt-5.5"))


class CompletionClient(Protocol):
    """LLM client interface used by CodexJudgeProvider."""

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        timeout_seconds: int,
        temperature: float,
    ) -> str:
        """Return model text."""


class CodexJudgeProvider:
    """Decision provider that asks Codex CLI for strict Judge JSON."""

    def __init__(
        self,
        *,
        client: CompletionClient | None = None,
        prompt_dir: str | Path | None = None,
    ) -> None:
        self.client = client or build_judge_client()
        self.prompt_dir = Path(prompt_dir) if prompt_dir else Path(__file__).with_name("prompts")

    def __call__(self, context: dict[str, Any]) -> str:
        gate_type = str(context.get("gate_type") or "").lower()
        prompt_name = "risk_gate.md" if gate_type == "risk" else "meaning_gate.md"
        system_prompt = (self.prompt_dir / prompt_name).read_text(encoding="utf-8")
        user_prompt = json.dumps(context, ensure_ascii=False, sort_keys=True, indent=2)
        return self.client.complete(
            system_prompt=system_prompt,
            user_prompt=(
                "Evaluate this Alaya gate context and return strict JSON only. "
                f"The audit_actor must be {AUDIT_ACTOR}.\n\n{user_prompt}"
            ),
            max_tokens=900,
            timeout_seconds=180,
            temperature=0.0,
        )
