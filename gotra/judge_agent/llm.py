"""Judge Agent LLM client factory."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from chairman.llm.narrative_generator import CodexCliClient


def build_judge_client() -> CodexCliClient:
    """Build the Judge Agent Codex CLI client with a read-only clean profile."""

    load_dotenv()
    os.environ["CODEX_PROVIDER_REASONING_EFFORT"] = os.getenv(
        "JUDGE_CODEX_REASONING_EFFORT", "xhigh"
    )
    os.environ.setdefault("CODEX_PROVIDER_SANDBOX", "read-only")
    os.environ.setdefault("CODEX_PROVIDER_CLEAN", "1")
    return CodexCliClient(model=os.getenv("JUDGE_LLM_MODEL", "gpt-5.5"))
