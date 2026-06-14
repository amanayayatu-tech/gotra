import os
from pathlib import Path

from chairman.llm.narrative_generator import CodexCliClient

from gotra.judge_agent.llm import CodexJudgeProvider, build_judge_client


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
