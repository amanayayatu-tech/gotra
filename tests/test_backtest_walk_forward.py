from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from gotra.backtest.audit import audit_step
from gotra.backtest.budget import TokenBudget
from gotra.backtest.compare_runs import direction_agreement
from gotra.backtest.protocol import TickerSpec, decision_dates
from gotra.backtest.walk_forward import (
    CodexCliUsageClient,
    CodexDecisionProvider,
    DecisionCache,
    ProviderError,
    BacktestConfig,
    _codex_jsonl_usage,
    _last_agent_message_from_codex_jsonl,
    run_backtest,
)
import gotra.backtest.walk_forward as walk_forward


def test_decision_dates_start_after_initial_window() -> None:
    dates = decision_dates(
        start=date(2016, 1, 1),
        end=date(2017, 7, 1),
        step_months=3,
    )

    assert dates == (
        date(2017, 1, 1),
        date(2017, 4, 1),
        date(2017, 7, 1),
    )


def test_audit_step_rejects_future_decision_input() -> None:
    violations = audit_step(
        {
            "decision_date": "2020-01-01",
            "outcome_as_of": "2020-02-03",
            "future_data_allowed": False,
            "provider_network_enabled": False,
            "audit_actor": "backtest/walk_forward",
            "decision_inputs": [
                {
                    "name": "bad_news",
                    "availability_date": "2020-01-02",
                    "source": "fixture",
                }
            ],
            "outcome_inputs": [
                {
                    "name": "outcome_price",
                    "availability_date": "2020-02-03",
                    "source": "fixture",
                }
            ],
        }
    )

    assert [violation.code for violation in violations] == ["decision_input_future"]


def test_sampled_backtest_writes_steps_audit_summary_and_report(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=560)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="sampled_test",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 4, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=10_000,
        )
    )

    run_root = tmp_path / "runs" / "sampled_test"
    baseline_steps = sorted((run_root / "baseline").glob("step_*.json"))
    alaya_steps = sorted((run_root / "alaya").glob("step_*.json"))

    assert summary["audit"]["ok"] is True
    assert summary["audit"]["steps_checked"] == 4
    assert summary["metrics"]["scored_steps"] == 4
    assert summary["metrics"]["paired_steps"] == 2
    assert baseline_steps
    assert alaya_steps
    assert (run_root / "event_log.jsonl").exists()
    assert (run_root / "system_health.json").exists()
    assert (run_root / "quality_summary.json").exists()
    assert (tmp_path / "REPORT_backtest.md").exists()
    assert (tmp_path / "REPORT_backtest_mse.svg").exists()
    system_health = json.loads((run_root / "system_health.json").read_text(encoding="utf-8"))
    assert system_health["status"] == "ok"
    assert system_health["token_budget"]["max_tokens"] == 10_000
    quality_summary = json.loads((run_root / "quality_summary.json").read_text(encoding="utf-8"))
    assert quality_summary["overall_status"] in {"pass", "low_coverage"}

    step = json.loads(alaya_steps[0].read_text(encoding="utf-8"))
    assert step["future_data_allowed"] is False
    assert step["provider_network_enabled"] is False
    assert step["audit_actor"] == "backtest/walk_forward"
    assert all(item["availability_date"] <= step["decision_date"] for item in step["decision_inputs"])


def test_backtest_pauses_when_token_budget_is_exceeded(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "MSFT", start="2016-01-01", days=470)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="budget_test",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),),
            token_budget=1,
        )
    )

    assert summary["paused"] is True
    assert "token budget exceeded" in summary["pause_reason"].lower()
    assert summary["system_health"]["status"] == "paused"
    assert summary["system_health"]["alerts"] == [summary["pause_reason"]]
    assert summary["token_budget"]["spent_tokens"] == 0
    assert summary["audit"]["ok"] is True
    assert summary["audit"]["steps_checked"] == 0
    assert summary["audit"]["event_rows_checked"] == 0
    run_root = tmp_path / "runs" / "budget_test"
    assert (run_root / "summary.json").exists()
    assert (run_root / "system_health.json").exists()
    assert not (run_root / "event_log.jsonl").exists()


def test_codex_provider_returns_decision_and_bills_real_usage(tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return {
                "content": json.dumps(
                    {
                        "direction": "long",
                        "expected_change_pct": 4.25,
                        "confidence": 0.72,
                        "reasoning": "Momentum is positive.",
                    }
                ),
                "usage": {"total_tokens": 1234},
            }

    client = FakeClient()
    provider = CodexDecisionProvider(client=client)
    budget = TokenBudget(max_tokens=2_000)
    decision = provider.decide(
        ticker="AAPL",
        arm="baseline",
        decision_date=date(2020, 1, 1),
        price_rows=_price_rows(start="2019-01-01", days=370),
        feedback=[],
        cache=DecisionCache(tmp_path / "cache.json"),
        budget=budget,
    )

    assert client.calls == 1
    assert decision.direction == "long"
    assert decision.expected_change_pct == 4.25
    assert decision.estimated_tokens == 1234
    assert decision.token_usage_source == "provider_usage"
    assert budget.snapshot()["spent_tokens"] == 1234


def test_codex_provider_records_actual_usage_overage_after_paid_call(tmp_path: Path) -> None:
    class FakeClient:
        def complete(self, **_kwargs):
            return {
                "content": json.dumps(
                    {
                        "direction": "long",
                        "expected_change_pct": 1.0,
                        "confidence": 0.5,
                        "reasoning": "Valid JSON.",
                    }
                ),
                "usage": {"total_tokens": 2500},
            }

    budget = TokenBudget(max_tokens=2000)
    decision = CodexDecisionProvider(client=FakeClient()).decide(
        ticker="AAPL",
        arm="baseline",
        decision_date=date(2020, 1, 1),
        price_rows=_price_rows(start="2019-01-01", days=370),
        feedback=[],
        cache=DecisionCache(tmp_path / "cache.json"),
        budget=budget,
    )

    assert decision.estimated_tokens == 2500
    assert budget.snapshot()["spent_tokens"] == 2500
    assert budget.snapshot()["over_budget"] is True
    assert "token budget exceeded" in str(budget.snapshot()["over_budget_error"]).lower()
    assert json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))


def test_codex_provider_retries_invalid_json(tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.responses = [
                "not json",
                json.dumps(
                    {
                        "direction": "hold",
                        "expected_change_pct": 0.5,
                        "confidence": 55,
                        "reasoning": "Mixed trend.",
                    }
                ),
            ]

        def complete(self, **_kwargs):
            return self.responses.pop(0)

    provider = CodexDecisionProvider(client=FakeClient(), max_retries=2)
    decision = provider.decide(
        ticker="MSFT",
        arm="baseline",
        decision_date=date(2020, 1, 1),
        price_rows=_price_rows(start="2019-01-01", days=370),
        feedback=[],
        cache=DecisionCache(tmp_path / "cache.json"),
        budget=TokenBudget(max_tokens=100_000),
    )

    assert decision.direction == "watch"
    assert decision.confidence == 0.55
    assert decision.token_usage_source == "estimated"


def test_codex_jsonl_usage_parser_reads_turn_completed_usage() -> None:
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "t"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": '{"direction":"long"}'},
                }
            ),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 18445,
                        "cached_input_tokens": 4992,
                        "output_tokens": 33,
                        "reasoning_output_tokens": 22,
                    },
                }
            ),
        ]
    )

    assert _last_agent_message_from_codex_jsonl(stdout) == '{"direction":"long"}'
    assert _codex_jsonl_usage(stdout) == {
        "input_tokens": 18445,
        "cached_input_tokens": 4992,
        "output_tokens": 33,
        "reasoning_output_tokens": 22,
        "total_tokens": 18478,
    }


def test_codex_usage_client_uses_clean_codex_home(monkeypatch, tmp_path: Path) -> None:
    source_home = tmp_path / "source-codex"
    source_home.mkdir()
    (source_home / "auth.json").write_text('{"token":"test"}', encoding="utf-8")
    (source_home / "skills").mkdir()
    (source_home / "skills" / "bad").mkdir()
    calls = []

    class BaseClient:
        model = "gpt-5.5"
        project_root = tmp_path
        codex_binary = "codex"

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        clean_home = Path(kwargs["env"]["CODEX_HOME"])
        assert clean_home != source_home
        assert (clean_home / "auth.json").exists()
        assert not list((clean_home / "skills").iterdir())
        output_path = command[command.index("--output-last-message") + 1]
        Path(output_path).write_text('{"direction":"long"}', encoding="utf-8")
        stdout = "\n".join(
            [
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}),
            ]
        )
        return walk_forward.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setenv("CODEX_HOME", str(source_home))
    monkeypatch.setenv("CODEX_PROVIDER_CLEAN", "1")
    monkeypatch.setenv("CODEX_PROVIDER_SANDBOX", "read-only")
    monkeypatch.setattr(walk_forward.shutil, "which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(walk_forward.subprocess, "run", fake_run)

    result = CodexCliUsageClient(BaseClient()).complete(
        system_prompt="Return JSON.",
        user_prompt="{}",
        max_tokens=20,
        timeout_seconds=10,
        temperature=0,
    )

    command, kwargs = calls[0]
    assert command[command.index("exec") + 1] == "--ignore-user-config"
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert kwargs["env"]["CODEX_HOME"] != str(source_home)
    assert result["usage"]["total_tokens"] == 12


def test_codex_provider_cache_hit_does_not_call_or_bill_again(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return {
                "content": json.dumps(
                    {
                        "direction": "avoid",
                        "expected_change_pct": -3.0,
                        "confidence": 0.61,
                        "reasoning": "Trend is weak.",
                    }
                ),
                "usage": {"total_tokens": 321},
            }

    client = FakeClient()
    provider = CodexDecisionProvider(client=client)
    cache = DecisionCache(tmp_path / "cache.json")
    budget = TokenBudget(max_tokens=10_000)
    kwargs = {
        "ticker": "TSM",
        "arm": "baseline",
        "decision_date": date(2020, 1, 1),
        "price_rows": _price_rows(start="2019-01-01", days=370),
        "feedback": [],
        "cache": cache,
        "budget": budget,
    }

    first = provider.decide(**kwargs)
    monkeypatch.setattr(
        walk_forward,
        "_build_default_codex_client",
        lambda: (_ for _ in ()).throw(AssertionError("cache hit should not build client")),
    )
    second = CodexDecisionProvider().decide(**kwargs)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert client.calls == 1
    assert budget.snapshot()["spent_tokens"] == 321
    assert budget.snapshot()["cache_misses"] == 1
    assert budget.snapshot()["cache_hits"] == 1


def test_cache_namespace_forces_independent_provider_replay(tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self, direction: str) -> None:
            self.direction = direction
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return {
                "content": json.dumps(
                    {
                        "direction": self.direction,
                        "expected_change_pct": 1.0,
                        "confidence": 0.5,
                        "reasoning": "Valid JSON.",
                    }
                ),
                "usage": {"total_tokens": 100},
            }

    cache_path = tmp_path / "cache.json"
    kwargs = {
        "ticker": "AAPL",
        "arm": "baseline",
        "decision_date": date(2020, 1, 1),
        "price_rows": _price_rows(start="2019-01-01", days=370),
        "feedback": [],
    }
    first_client = FakeClient("long")
    second_client = FakeClient("short")

    first = CodexDecisionProvider(client=first_client).decide(
        **kwargs,
        cache=DecisionCache(cache_path),
        budget=TokenBudget(max_tokens=10_000),
    )
    second = CodexDecisionProvider(client=second_client).decide(
        **kwargs,
        cache=DecisionCache(cache_path, namespace="baseline-replay"),
        budget=TokenBudget(max_tokens=10_000),
    )

    assert first.prompt_hash == second.prompt_hash
    assert first.direction == "long"
    assert second.direction == "short"
    assert first.cache_hit is False
    assert second.cache_hit is False
    assert first_client.calls == 1
    assert second_client.calls == 1


def test_backtest_can_run_baseline_arm_only(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="baseline_only",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=10_000,
            arms=("baseline",),
            cache_namespace="baseline-replay",
        )
    )

    run_root = tmp_path / "runs" / "baseline_only"
    assert summary["arms"] == ["baseline"]
    assert summary["cache_namespace"] == "baseline-replay"
    assert summary["steps_written"] == 1
    assert summary["metrics"]["paired_steps"] == 0
    assert len(list((run_root / "baseline").glob("step_*.json"))) == 1
    assert not (run_root / "alaya").exists()


def test_sqlite_ledger_serial_backtest_writes_ledger(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="sqlite_serial",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=10_000,
            ledger="sqlite",
        )
    )

    ledger_path = tmp_path / "runs" / "sqlite_serial" / "run_ledger.sqlite"
    assert summary["ledger"]["backend"] == "sqlite"
    assert ledger_path.exists()
    with sqlite3.connect(ledger_path) as conn:
        assert conn.execute("select count(*) from steps").fetchone()[0] == 2
        assert conn.execute("select count(*) from provider_calls").fetchone()[0] == 2


def test_baseline_parallel_backtest_writes_ordered_steps(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)
    _write_prices(tmp_path / "prices", "MSFT", start="2016-01-01", days=470)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="parallel_baseline",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(
                TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
                TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),
            ),
            token_budget=100_000,
            arms=("baseline",),
            ledger="sqlite",
            provider_concurrency=2,
            parallel_mode="baseline",
        )
    )

    run_root = tmp_path / "runs" / "parallel_baseline"
    steps = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_root / "baseline").glob("step_*.json"))
    ]
    assert summary["parallel"]["mode"] == "baseline"
    assert summary["steps_written"] == 2
    assert [step["step"] for step in sorted(steps, key=lambda item: item["step"])] == [1, 2]
    assert summary["audit"]["ok"] is True


def test_parallel_resume_reuses_existing_steps_without_provider_call(tmp_path: Path, monkeypatch) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)
    config = BacktestConfig(
        data_dir=tmp_path,
        run_id="parallel_resume",
        mode="sampled",
        provider="heuristic",
        start=date(2016, 1, 1),
        end=date(2017, 1, 1),
        step_months=3,
        tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
        token_budget=100_000,
        arms=("baseline",),
        ledger="sqlite",
        provider_concurrency=2,
        parallel_mode="baseline",
    )
    first = run_backtest(config)

    class ExplodingProvider:
        network_enabled = False

        def decide(self, **_kwargs):
            raise AssertionError("resume should not call provider")

    monkeypatch.setattr(walk_forward, "_build_provider", lambda _name: ExplodingProvider())
    second = run_backtest(BacktestConfig(**{**config.__dict__, "resume": True}))

    assert first["steps_written"] == second["steps_written"] == 1
    event_rows = (tmp_path / "runs" / "parallel_resume" / "event_log.jsonl").read_text().splitlines()
    assert len(event_rows) == 1


def test_alaya_ticker_chain_parallel_preserves_feedback_order(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=760)
    _write_prices(tmp_path / "prices", "MSFT", start="2016-01-01", days=760)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="parallel_alaya_chain",
            mode="sampled",
            provider="heuristic",
            start=date(2016, 1, 1),
            end=date(2017, 7, 1),
            step_months=3,
            tickers=(
                TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
                TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),
            ),
            token_budget=100_000,
            ledger="sqlite",
            provider_concurrency=2,
            parallel_mode="ticker-chains",
        )
    )

    run_root = tmp_path / "runs" / "parallel_alaya_chain"
    alaya_steps = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_root / "alaya").glob("step_*.json"))
    ]
    later_aapl = next(
        step for step in alaya_steps if step["ticker"] == "AAPL" and step["decision_date"] == "2017-04-01"
    )
    assert summary["steps_written"] == 12
    assert summary["metrics"]["paired_steps"] == 6
    assert any(item["kind"] == "alaya_feedback" for item in later_aapl["decision_inputs"])


def test_direction_agreement_compares_baseline_replay_runs(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    (reference / "baseline").mkdir(parents=True)
    (candidate / "baseline").mkdir(parents=True)
    _write_step_json(reference / "baseline" / "step_2020-01-01_aapl.json", "AAPL", "2020-01-01", "long")
    _write_step_json(candidate / "baseline" / "step_2020-01-01_aapl.json", "AAPL", "2020-01-01", "long")
    _write_step_json(reference / "baseline" / "step_2020-02-01_msft.json", "MSFT", "2020-02-01", "watch")
    _write_step_json(candidate / "baseline" / "step_2020-02-01_msft.json", "MSFT", "2020-02-01", "avoid")

    result = direction_agreement(reference_run=reference, candidate_run=candidate)

    assert result["same"] == 1
    assert result["total"] == 2
    assert result["rate"] == 0.5
    assert result["mismatches"] == [
        {
            "ticker": "MSFT",
            "decision_date": "2020-02-01",
            "reference_direction": "watch",
            "candidate_direction": "avoid",
            "reason": "direction_mismatch",
        }
    ]


def test_codex_provider_prompt_skeleton_differs_only_by_feedback(tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.user_prompts: list[str] = []
            self.system_prompts: list[str] = []

        def complete(self, **kwargs):
            self.system_prompts.append(kwargs["system_prompt"])
            self.user_prompts.append(kwargs["user_prompt"])
            return json.dumps(
                {
                    "direction": "long",
                    "expected_change_pct": 1.0,
                    "confidence": 0.5,
                    "reasoning": "Valid JSON.",
                }
            )

    client = FakeClient()
    provider = CodexDecisionProvider(client=client)
    price_rows = _price_rows(start="2019-01-01", days=370)
    cache = DecisionCache(tmp_path / "cache.json")
    feedback = [
        {
            "decision_date": "2019-10-01",
            "outcome_availability_date": "2019-11-01",
            "error": -1.2,
        }
    ]

    provider.decide(
        ticker="AAPL",
        arm="baseline",
        decision_date=date(2020, 1, 1),
        price_rows=price_rows,
        feedback=[],
        cache=cache,
        budget=TokenBudget(max_tokens=100_000),
    )
    provider.decide(
        ticker="AAPL",
        arm="alaya",
        decision_date=date(2020, 1, 1),
        price_rows=price_rows,
        feedback=feedback,
        cache=cache,
        budget=TokenBudget(max_tokens=100_000),
    )

    assert client.system_prompts[0] == client.system_prompts[1]
    baseline_payload = json.loads(client.user_prompts[0])
    alaya_payload = json.loads(client.user_prompts[1])
    assert baseline_payload.pop("feedback") == []
    assert alaya_payload.pop("feedback") == feedback
    assert baseline_payload == alaya_payload


def test_codex_cli_provider_is_not_stage3_deterministic() -> None:
    metadata = walk_forward._provider_determinism_metadata(  # noqa: SLF001
        "codex_cli",
        require_stage3_provider=True,
    )

    assert metadata["stage3_acceptance_eligible"] is False
    assert metadata["temperature_control"] == "prompt_guidance_only"
    assert metadata["top_p_control"] is False
    assert metadata["seed_control"] is False
    assert "temperature" in metadata["blocking_reason"]


def test_codex_responses_provider_requires_empirical_repro_flag(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_RESPONSES_MEASURED_REPRO_OK", raising=False)
    metadata = walk_forward._provider_determinism_metadata(  # noqa: SLF001
        "codex_responses",
        require_stage3_provider=True,
    )

    assert metadata["stage3_acceptance_eligible"] is False
    assert metadata["temperature_control"] == "unsupported"
    assert metadata["top_p_control"] is False
    assert metadata["seed_control"] is False
    assert metadata["acceptance_basis"] == "empirically_measured_direction_agreement"
    assert metadata["measured_repro_flag"] == "CODEX_RESPONSES_MEASURED_REPRO_OK"
    assert "does not accept temperature" in metadata["blocking_reason"]
    assert "direction-agreement rate >=95%" in metadata["blocking_reason"]
    assert "temperature" in walk_forward._provider_determinism_error(metadata)  # noqa: SLF001


def test_codex_responses_provider_is_stage3_eligible_when_empirically_flagged(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CODEX_RESPONSES_MEASURED_REPRO_OK", "1")
    metadata = walk_forward._provider_determinism_metadata(  # noqa: SLF001
        "codex_responses",
        require_stage3_provider=True,
    )

    assert metadata["stage3_acceptance_eligible"] is True
    assert metadata["temperature_control"] == "unsupported"
    assert metadata["top_p_control"] is False
    assert metadata["seed_control"] is False
    assert metadata["blocking_reason"] == ""
    assert walk_forward._provider_determinism_error(metadata) == ""  # noqa: SLF001


def test_parse_args_accepts_codex_responses_provider() -> None:
    args = walk_forward.parse_args(["--provider", "codex_responses"])

    assert args.provider == "codex_responses"


def test_require_stage3_provider_allows_codex_responses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CODEX_RESPONSES_MEASURED_REPRO_OK", "true")
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)

    class Stage3EligibleProvider:
        network_enabled = False

        def __init__(self) -> None:
            self.preflight_called = False

        def preflight(self) -> None:
            self.preflight_called = True

        def decide(self, **_kwargs):
            return walk_forward.Decision(
                direction="long",
                expected_change_pct=1.0,
                confidence=0.5,
                reasoning="fixture",
                prompt_hash="abc123",
                estimated_tokens=10,
                token_usage_source="provider_usage",
                cache_hit=False,
            )

    provider = Stage3EligibleProvider()
    monkeypatch.setattr(walk_forward, "_build_provider", lambda _name: provider)

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="stage3_codex_responses_allowed_test",
            mode="sampled",
            provider="codex_responses",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            arms=("baseline",),
            require_stage3_provider=True,
            token_budget=50_000,
        )
    )

    assert provider.preflight_called is True
    assert summary["steps_written"] == 1
    assert summary["provider_errors"] == 0
    assert summary["provider_determinism_error"] == ""
    assert summary["provider_determinism"]["stage3_acceptance_eligible"] is True
    assert summary["system_health"]["status"] == "ok"


def test_require_stage3_provider_blocks_codex_responses_before_preflight_without_flag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("CODEX_RESPONSES_MEASURED_REPRO_OK", raising=False)

    class ProviderThatMustNotRun:
        network_enabled = False

        def preflight(self):
            raise AssertionError("preflight should not run when Stage 3 provider gate blocks")

        def decide(self, **_kwargs):
            raise AssertionError("main loop should not run when Stage 3 provider gate blocks")

    monkeypatch.setattr(walk_forward, "_build_provider", lambda _name: ProviderThatMustNotRun())

    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="stage3_codex_responses_block_test",
            mode="full",
            provider="codex_responses",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=1,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            require_stage3_provider=True,
            token_budget=50_000,
        )
    )

    assert summary["steps_written"] == 0
    assert summary["provider_errors"] == 0
    assert summary["aborted_provider_unhealthy"] is False
    assert summary["provider_health"]["preflight_enabled"] is False
    assert summary["provider_determinism"]["required_for_stage3"] is True
    assert summary["provider_determinism"]["stage3_acceptance_eligible"] is False
    assert summary["provider_determinism"]["temperature_control"] == "unsupported"
    assert "temperature" in summary["provider_determinism_error"]
    assert "direction-agreement rate >=95%" in summary["provider_determinism_error"]
    assert summary["system_health"]["status"] == "blocked_provider_determinism"
    assert summary["system_health"]["provider_determinism_error"] == summary[
        "provider_determinism_error"
    ]
    assert (tmp_path / "runs" / "stage3_codex_responses_block_test" / "summary.json").exists()


def test_provider_error_steps_are_written_and_counted(tmp_path: Path, monkeypatch) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)

    class FailingProvider:
        network_enabled = False

        def decide(self, **_kwargs):
            raise ProviderError("bad provider json", prompt_hash="abc123", estimated_tokens=99)

    monkeypatch.setattr(walk_forward, "_build_provider", lambda _name: FailingProvider())
    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="provider_error_test",
            mode="sampled",
            provider="codex_cli",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=10_000,
        )
    )

    run_root = tmp_path / "runs" / "provider_error_test"
    step = json.loads(next((run_root / "baseline").glob("step_*.json")).read_text(encoding="utf-8"))
    assert summary["provider_errors"] == 2
    assert summary["system_health"]["status"] == "failed"
    assert summary["audit"]["ok"] is True
    assert step["status"] == "provider_error"
    assert step["step"] == 1
    assert step["date"] == "2017-01-01"
    assert step["error_type"] == "provider_error"
    assert step["provider_error"] == "bad provider json"
    assert step["audit_actor"] == "backtest/walk_forward"


def test_codex_provider_preflight_failure_aborts_before_main_loop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=470)

    class UnhealthyProvider:
        network_enabled = True

        def preflight(self):
            raise ProviderError("failed to load skill invalid YAML")

        def decide(self, **_kwargs):
            raise AssertionError("main loop should not call provider after failed preflight")

    monkeypatch.setattr(walk_forward, "_build_provider", lambda _name: UnhealthyProvider())
    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="preflight_abort_test",
            mode="sampled",
            provider="codex_cli",
            start=date(2016, 1, 1),
            end=date(2017, 1, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=50_000,
        )
    )

    assert summary["steps_written"] == 0
    assert summary["provider_errors"] == 0
    assert summary["aborted_provider_unhealthy"] is True
    assert summary["provider_health"]["preflight_ok"] is False
    assert "failed to load skill" in summary["provider_health"]["preflight_error"]
    assert summary["system_health"]["status"] == "aborted_provider_unhealthy"
    assert (tmp_path / "runs" / "preflight_abort_test" / "summary.json").exists()


def test_codex_provider_error_fuse_aborts_after_consecutive_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL", start="2016-01-01", days=760)

    class FailingProvider:
        network_enabled = True

        def preflight(self):
            return None

        def decide(self, **_kwargs):
            raise ProviderError("provider quota exhausted")

    monkeypatch.setattr(walk_forward, "_build_provider", lambda _name: FailingProvider())
    summary = run_backtest(
        BacktestConfig(
            data_dir=tmp_path,
            run_id="provider_fuse_test",
            mode="sampled",
            provider="codex_cli",
            start=date(2016, 1, 1),
            end=date(2017, 10, 1),
            step_months=3,
            tickers=(TickerSpec("AAPL", "Apple", date(1980, 12, 12)),),
            token_budget=50_000,
        )
    )

    assert summary["steps_written"] == 8
    assert summary["provider_errors"] == 8
    assert summary["aborted_provider_unhealthy"] is True
    assert "8 consecutive provider_error" in summary["provider_abort_reason"]
    assert summary["system_health"]["status"] == "aborted_provider_unhealthy"


def _write_prices(price_dir: Path, ticker: str, *, start: str, days: int) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    start_date = date.fromisoformat(start)
    rows = []
    price = 100.0
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        price += 0.05 + (offset % 11) * 0.01
        rows.append(
            {
                "date": current.isoformat(),
                "ticker": ticker,
                "adj_close": round(price, 4),
                "source_url": "fixture",
                "evidence_unverified": False,
            }
        )
    pd.DataFrame(rows).to_csv(price_dir / f"{ticker}.csv", index=False)


def _price_rows(*, start: str, days: int) -> pd.DataFrame:
    start_date = date.fromisoformat(start)
    rows = []
    price = 100.0
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        price += 0.05 + (offset % 7) * 0.02
        rows.append(
            {
                "date": current.isoformat(),
                "ticker": "TEST",
                "adj_close": round(price, 4),
                "source_url": "fixture",
                "evidence_unverified": False,
            }
        )
    return pd.DataFrame(rows)


def _write_step_json(path: Path, ticker: str, decision_date: str, direction: str) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "scored",
                "ticker": ticker,
                "decision_date": decision_date,
                "decision_direction": direction,
            }
        ),
        encoding="utf-8",
    )
