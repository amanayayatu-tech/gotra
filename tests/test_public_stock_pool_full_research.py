from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.public_stock_pool_full_research import (
    BOUNDARY_LINES,
    MODE,
    RunConfig,
    RunnerResult,
    run,
)


ITEM = {
    "symbol": "0068",
    "exchange": "HKEX",
    "provider_ticker": "0068.HK",
    "source": "test",
    "source_date": "2026-06-29",
    "purpose": "test",
    "boundary": "research information only",
}


def valid_payload(symbol: str = "0068", exchange: str = "HKEX") -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "exchange": exchange,
            "as_of_date": "2026-06-29",
            "research_summary": "Public-safe business and market context only.",
            "key_updates": ["Review current public filings and major news."],
            "price_context": "Public price context should be verified from market data.",
            "risk_factors": ["Information may be incomplete or stale."],
            "watch_items": ["Verify primary sources before operational use."],
            "boundary": list(BOUNDARY_LINES),
            "source_notes": ["Generated as a runtime smoke artifact."],
            "status": "ok",
        }
    )


class SequenceRunner:
    def __init__(self, responses: list[RunnerResult]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del prompt_text, timeout_seconds
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def make_config(tmp_path: Path, *, retries: int = 0, resume: bool = False) -> RunConfig:
    return RunConfig(
        run_id="test_run",
        mode=MODE,
        output_dir=tmp_path / "public",
        private_audit_root=tmp_path / "private",
        as_of_date=date(2026, 6, 29),
        trading_date=date(2026, 6, 26),
        universe_url="http://127.0.0.1:3000/api/research-universe",
        max_concurrency=1,
        continue_on_failure=True,
        llm_runner="codex-cli",
        model="gpt-5.5",
        reasoning_effort="high",
        per_symbol_timeout_seconds=30,
        retries=retries,
        resume=resume,
        codex_bin="codex",
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def public_text(root: Path) -> str:
    chunks: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def test_retry_invalid_json_then_success_keeps_raw_out_of_public_outputs(tmp_path: Path) -> None:
    runner = SequenceRunner(
        [
            RunnerResult(True, text="not json raw_provider_response prompt completion messages sk-test"),
            RunnerResult(True, text=valid_payload()),
        ]
    )

    exit_code = run(make_config(tmp_path, retries=1), universe_items=[ITEM], runner=runner)

    assert exit_code == 0
    status = read_json(tmp_path / "public" / "status.json")
    assert status["ok"] is True
    assert status["success_count"] == 1
    assert status["trading_date"] == "2026-06-26"
    assert status["total_attempts"] == 2
    assert status["invalid_json_count"] == 1
    per_symbol = read_json(tmp_path / "public" / "per_symbol_status.json")
    assert per_symbol["items"][0]["attempts"] == 2
    text = public_text(tmp_path / "public")
    assert "not json raw_provider_response" not in text
    assert '"prompt_text"' not in text
    assert '"completion"' not in text
    assert '"messages"' not in text


def test_failed_symbols_records_invalid_json_without_raw_output(tmp_path: Path) -> None:
    runner = SequenceRunner([RunnerResult(True, text="not json raw output")])

    exit_code = run(make_config(tmp_path, retries=0), universe_items=[ITEM], runner=runner)

    assert exit_code == 2
    status = read_json(tmp_path / "public" / "status.json")
    assert status["ok"] is False
    assert status["failed_count"] == 1
    assert status["failed_symbols"][0]["reason"] == "invalid_json"
    assert "not json raw output" not in public_text(tmp_path / "public")


def test_private_audit_contains_prompt_but_not_raw_stdout_stderr_and_uses_private_modes(tmp_path: Path) -> None:
    runner = SequenceRunner([RunnerResult(True, text=valid_payload(), stdout_bytes=12, stderr_bytes=34)])

    exit_code = run(make_config(tmp_path), universe_items=[ITEM], runner=runner)

    assert exit_code == 0
    audit_dir = tmp_path / "private" / "test_run"
    attempt_path = next((audit_dir / "attempts").glob("HKEX_0068_attempt_1_*.json"))
    assert oct(audit_dir.stat().st_mode & 0o777) == "0o700"
    assert oct(attempt_path.stat().st_mode & 0o777) == "0o600"
    attempt = read_json(attempt_path)
    assert attempt["attempt_id"].startswith("HKEX_0068_attempt_1_")
    assert "prompt_text" in attempt
    assert attempt["stdout_bytes"] == 12
    assert attempt["stderr_bytes"] == 34
    assert "stdout" not in attempt
    assert "stderr" not in attempt
    assert "raw_provider_response" not in attempt


def test_status_records_audit_policy_and_does_not_write_public_latest(tmp_path: Path) -> None:
    runner = SequenceRunner([RunnerResult(True, text=valid_payload())])

    exit_code = run(make_config(tmp_path), universe_items=[ITEM], runner=runner)

    assert exit_code == 0
    status = read_json(tmp_path / "public" / "status.json")
    assert status["run_id"] == "test_run"
    assert status["private_audit_path"].endswith("/private/test_run")
    assert status["prompt_template_version"]
    assert status["public_latest_written"] is False
    assert status["audit_artifact_policy"]["web_root_copy"] is False
