import os
from pathlib import Path

from chairman.llm.narrative_generator import CodexCliClient

from gotra.judge_agent.llm import CodexJudgeProvider, build_judge_client


PROMPT_DIR = Path("gotra/judge_agent/prompts")
REQUIRED_PROMPT_PHRASES = (
    "strict JSON only",
    "approve|reject|defer",
    "Simplified Chinese",
    "简体中文",
    "方法论分歧",
    "事实错误",
    "evidence provenance",
    "source traceability",
    "Future-source leak",
    "decision-date boundary",
    "existing strong knowledge",
    "Duplicate/noise",
    "Insufficient evidence",
    "feedback substrate",
    "outcome-derived feedback",
    "strong_candidate",
    "Never auto-promote strong knowledge",
    "future outcomes",
    "realized returns",
    "post-horizon",
    "calibrated_accept",
    "risk_or_future_source_leak",
    "duplicate_or_noise",
    "insufficient_or_uncertain",
    "low_value_or_low_quality",
    "strong_conflict",
    "methodology_disagreement",
    "factual_error",
    "needs_human_review",
)


def test_build_judge_client_defaults_to_read_only_clean_codex(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_PROVIDER_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_SANDBOX", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_CLEAN", raising=False)
    monkeypatch.delenv("JUDGE_CODEX_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("JUDGE_LLM_MODEL", raising=False)

    client = build_judge_client()

    assert isinstance(client, CodexCliClient)
    assert client.model == "gpt-5.5"
    assert client.project_root == Path.cwd()
    assert os.environ["CODEX_PROVIDER_REASONING_EFFORT"] == "xhigh"
    assert os.environ["CODEX_PROVIDER_SANDBOX"] == "read-only"
    assert os.environ["CODEX_PROVIDER_CLEAN"] == "1"


def test_build_judge_client_sets_provider_environment(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_PROVIDER_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_SANDBOX", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_CLEAN", raising=False)
    monkeypatch.setenv("JUDGE_CODEX_REASONING_EFFORT", "xhigh")
    monkeypatch.setenv("JUDGE_LLM_MODEL", "gpt-5.5")

    build_judge_client()

    assert os.environ["CODEX_PROVIDER_REASONING_EFFORT"] == "xhigh"
    assert os.environ["CODEX_PROVIDER_SANDBOX"] == "read-only"
    assert os.environ["CODEX_PROVIDER_CLEAN"] == "1"


def test_codex_judge_provider_uses_gate_prompt_and_strict_actor(tmp_path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "risk_gate.md").write_text("risk prompt", encoding="utf-8")
    (prompt_dir / "meaning_gate.md").write_text("meaning prompt", encoding="utf-8")

    class FakeClient:
        def __init__(self) -> None:
            self.kwargs = {}

        def complete(self, **kwargs):
            self.kwargs = kwargs
            return '{"decision":"defer","confidence":0.5,"reasoning":"等待更多证据。","knowledge_flag":"none","audit_actor":"judge_agent/codex"}'

    client = FakeClient()
    provider = CodexJudgeProvider(client=client, prompt_dir=prompt_dir)

    response = provider({"gate_type": "risk", "ticker": "META"})

    assert '"decision":"defer"' in response
    assert client.kwargs["system_prompt"] == "risk prompt"
    assert "judge_agent/codex" in client.kwargs["user_prompt"]
    assert client.kwargs["temperature"] == 0.0


def test_codex_judge_provider_uses_meaning_prompt_for_non_risk_gate(tmp_path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "risk_gate.md").write_text("risk prompt", encoding="utf-8")
    (prompt_dir / "meaning_gate.md").write_text("meaning prompt", encoding="utf-8")

    class FakeClient:
        def __init__(self) -> None:
            self.kwargs = {}

        def complete(self, **kwargs):
            self.kwargs = kwargs
            return '{"decision":"approve","confidence":0.8,"reasoning":"证据可靠，可以通过。","knowledge_flag":"none","audit_actor":"judge_agent/codex"}'

    client = FakeClient()
    provider = CodexJudgeProvider(client=client, prompt_dir=prompt_dir)

    provider({"gate_type": "meaning", "ticker": "META"})

    assert client.kwargs["system_prompt"] == "meaning prompt"
    assert "judge_agent/codex" in client.kwargs["user_prompt"]
    assert client.kwargs["temperature"] == 0.0


def test_judge_prompt_files_include_structured_calibration_contract() -> None:
    for name in ("meaning_gate.md", "risk_gate.md"):
        prompt = (PROMPT_DIR / name).read_text(encoding="utf-8")
        prompt_lower = prompt.lower()
        for phrase in REQUIRED_PROMPT_PHRASES:
            if phrase.isascii():
                assert phrase.lower() in prompt_lower
            else:
                assert phrase in prompt
        assert '"audit_actor": "judge_agent/codex"' in prompt
        assert '"reason_code":' in prompt
