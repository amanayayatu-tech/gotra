from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

from business_agents._common.knowledge_store import ingest_filled_result
from business_agents._common.perplexity_results import (
    collect_perplexity_context,
    load_result_status,
    sync_signal_file_perplexity_status,
)
from chairman.models import ResearchSignal
from gotra.perplexity_executor import DEFAULT_CONCURRENCY_LIMIT, PerplexityExecutor
from gotra.perplexity_executor.pplx_client import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    PerplexityApiClient,
)


class MockPerplexityClient:
    def __init__(self, answer_text: str = "mock answer", *, fail: Exception | None = None) -> None:
        self.answer_text = answer_text
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def complete(self, prompt_text: str, *, model: str) -> str:
        self.calls.append((prompt_text, model))
        if self.fail:
            raise self.fail
        return self.answer_text


class CountingClient:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def complete(self, prompt_text: str, *, model: str) -> str:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return f"# Result\n\n{prompt_text}\n\n- closed question: yes"


def test_executor_writes_ksana_consumable_filled_result(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    prompt_text = "Research META AI ad conversion catalysts and cite current evidence."
    prompt_id = "PR-TEST-1"
    signal_id = "SIG-TEST-1"
    write_prompt(data_dir, prompt_id, signal_id, prompt_text)
    signal_path = write_signal(data_dir, signal_id, prompt_id)

    answer = "\n".join(
        [
            "# META AI ad stack update",
            "",
            "Research date: 2026-06-14",
            "Event date: 2026-06-13",
            "Confidence: medium",
            "",
            "- META reported stronger conversion from AI ad tools.",
            "- The open question about advertiser adoption is now closed.",
            "- Source: https://example.com/meta-ai-ads",
        ]
    )
    client = MockPerplexityClient(answer)

    results = PerplexityExecutor(data_dir=data_dir, client=client).run()

    assert [result.status for result in results] == ["filled"]
    assert client.calls == [(prompt_text, "sonar-deep-research")]
    result_path = data_dir / "perplexity_results" / f"{prompt_id}_filled.yaml"
    assert result_path.exists()
    result_payload = read_yaml(result_path)
    assert result_payload["prompt_id"] == prompt_id
    assert result_payload["related_signal_id"] == signal_id
    assert result_payload["status"] == "filled"
    assert result_payload["source"] == "perplexity"
    assert result_payload["model"] == "sonar-deep-research"
    assert result_payload["prompt_text"] == prompt_text
    assert result_payload["answer_text"] == answer

    status = load_result_status(
        data_dir,
        {
            "prompt_id": prompt_id,
            "related_signal_id": signal_id,
            "prompt_text_for_match": prompt_text,
        },
    )
    assert status["status"] == "filled"
    assert status["source"] == "perplexity"

    signal = ResearchSignal.model_validate(read_yaml(signal_path)["research_signal"])
    context = collect_perplexity_context(data_dir, signal)
    assert context.filled_prompt_ids == [prompt_id]
    assert context.pending_prompt_ids == []
    assert "META AI ad stack update" in context.yaml_text

    entry = ingest_filled_result(data_dir, prompt_id)
    assert entry is not None
    assert entry.prompt_id == prompt_id
    assert entry.related_signal_id == signal_id

    changed = sync_signal_file_perplexity_status(data_dir, prompt_id)
    assert changed == [signal_path]
    synced = read_yaml(signal_path)["research_signal"]["perplexity_research"]
    assert synced["prompts_filled_back"] == [prompt_id]
    assert synced["prompts_pending"] == []
    assert synced["coverage_ratio"] == 1.0


def test_executor_failure_does_not_write_filled_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    prompt_id = "PR-FAIL-1"
    prompt_text = "Research MSFT AI cloud risk."
    write_prompt(data_dir, prompt_id, "SIG-FAIL-1", prompt_text)
    client = MockPerplexityClient(fail=TimeoutError("timed out"))

    results = PerplexityExecutor(data_dir=data_dir, client=client).run()

    assert results[0].status == "failed"
    assert "timed out" in str(results[0].error)
    assert client.calls == [(prompt_text, "sonar-deep-research")]
    assert not (data_dir / "perplexity_results" / f"{prompt_id}_filled.yaml").exists()
    assert load_result_status(data_dir, prompt_id)["status"] == "pending"


def test_executor_without_api_key_keeps_prompt_pending(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    prompt_id = "PR-NOKEY-1"
    write_prompt(data_dir, prompt_id, "SIG-NOKEY-1", "Research GOOG AI search risk.")
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    results = PerplexityExecutor(data_dir=data_dir).run()

    assert results[0].status == "failed"
    assert "missing PPLX_API_KEY or PERPLEXITY_API_KEY" in str(results[0].error)
    assert not (data_dir / "perplexity_results" / f"{prompt_id}_filled.yaml").exists()
    assert load_result_status(data_dir, prompt_id)["status"] == "pending"


def test_executor_validates_prompt_before_client_call(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    prompt_dir = data_dir / "pull_requests"
    prompt_dir.mkdir(parents=True)
    write_yaml(prompt_dir / "PR-BAD.yaml", {"prompt": {"prompt_text": "missing id"}})
    client = MockPerplexityClient()

    with pytest.raises(Exception):
        PerplexityExecutor(data_dir=data_dir, client=client).run()

    assert client.calls == []
    assert not (data_dir / "perplexity_results").exists()


def test_executor_enforces_default_concurrency_limit(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    for index in range(5):
        write_prompt(
            data_dir,
            f"PR-CONC-{index}",
            f"SIG-CONC-{index}",
            f"Research NVDA concurrency case {index}.",
        )
    client = CountingClient()

    results = PerplexityExecutor(data_dir=data_dir, client=client).run()

    assert len(results) == 5
    assert all(result.status == "filled" for result in results)
    assert client.max_active == DEFAULT_CONCURRENCY_LIMIT


def test_api_client_defaults_match_phase_contract() -> None:
    client = PerplexityApiClient()

    assert client.timeout_seconds == DEFAULT_TIMEOUT_SECONDS == 120.0
    assert client.max_attempts == DEFAULT_MAX_ATTEMPTS == 3
    assert DEFAULT_MODEL == "sonar-deep-research"


def write_prompt(data_dir: Path, prompt_id: str, signal_id: str, prompt_text: str) -> Path:
    path = data_dir / "pull_requests" / f"{prompt_id}.yaml"
    write_yaml(
        path,
        {
            "prompt": {
                "prompt_id": prompt_id,
                "related_signal_id": signal_id,
                "priority": "P1",
                "prompt_text": prompt_text,
                "research_question_set": {"questions": [prompt_text]},
            }
        },
    )
    return path


def write_signal(data_dir: Path, signal_id: str, prompt_id: str) -> Path:
    path = data_dir / "research_signals" / f"{signal_id}.yaml"
    write_yaml(
        path,
        {
            "research_signal": {
                "research_signal_id": signal_id,
                "signal_type": "event",
                "research_stage": "deep_research",
                "signal_summary": "META AI ad catalyst requires outside research.",
                "candidate_targets": [
                    {
                        "ticker": "META",
                        "market": "US",
                        "company_name": "Meta Platforms",
                    }
                ],
                "routing_recommendation": {"action": "run_or_update_perplexity_research"},
                "perplexity_research": {
                    "prompts_requested": [prompt_id],
                    "prompts_pending": [prompt_id],
                    "prompts_filled_back": [],
                },
            }
        },
    )
    return path


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
