import os

from chairman.llm.narrative_generator import CodexCliClient

from gotra.judge_agent.llm import build_judge_client


def test_build_judge_client_defaults_to_read_only_clean_codex(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_PROVIDER_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_SANDBOX", raising=False)
    monkeypatch.delenv("CODEX_PROVIDER_CLEAN", raising=False)
    monkeypatch.delenv("JUDGE_CODEX_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("JUDGE_LLM_MODEL", raising=False)

    client = build_judge_client()

    assert isinstance(client, CodexCliClient)
    assert client.model == "gpt-5.5"
    assert client.project_root.name == "gotra"
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
