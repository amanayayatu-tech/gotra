import json
import threading
import time
from datetime import date, datetime, timedelta, timezone
from itertools import count
from pathlib import Path

from scripts.public_stock_pool_full_research import RunnerResult
from scripts.public_stock_pool_full_analyst_pipeline import (
    BOUNDARY_LINES,
    LOOP_MODE,
    LOOP_SMOKE_MODE,
    MODE,
    ALAYA_EVENT_SCHEMA,
    ALAYA_EVENT_SCHEMA_V3,
    EXECUTION_MODEL,
    EXECUTION_MODEL_V3,
    FullAnalystConfig,
    GotraInternalAlayaSyncClient,
    METHODOLOGY_VERSION,
    METHODOLOGY_VERSION_V3,
    MockAlayaSyncClient,
    PROMPT_TEMPLATE_VERSION,
    PROMPT_TEMPLATE_VERSION_V3,
    SYMBOL_SCHEMA,
    SYMBOL_SCHEMA_V3,
    assert_public_safe,
    build_prompt,
    config_from_args,
    fixture_v3_agent_output,
    prompt_input_payload,
    parse_args,
    run,
    sanitize_v3_agent_output,
    selected_universe,
    update_loop_public_status,
)


def config(tmp_path: Path, *, symbols: tuple[str, ...] = ("HKEX:0700", "HKEX:9988", "HKEX:0501")) -> FullAnalystConfig:
    return FullAnalystConfig(
        run_id="full_analyst_evening_hk_20260629_v1",
        mode=MODE,
        output_dir=tmp_path / "public",
        private_audit_root=tmp_path / "private",
        static_dir=tmp_path / "static",
        publish_static=True,
        as_of_date=date(2026, 6, 29),
        trading_date=date(2026, 6, 29),
        universe_url="local",
        symbols=symbols,
        llm_runner="fixture",
        alaya_mode="mock",
        max_concurrency=1,
        per_symbol_timeout_seconds=30,
        retries=0,
        codex_bin="codex",
        model="fixture",
        reasoning_effort="low",
        heartbeat_interval_seconds=300,
        loop_duration_seconds=0,
        sample_cadence_seconds=1800,
    )


def universe() -> list[dict[str, str]]:
    return [
        {"exchange": "HKEX", "symbol": "0700", "provider_ticker": "0700.HK"},
        {"exchange": "HKEX", "symbol": "9988", "provider_ticker": "9988.HK"},
        {"exchange": "HKEX", "symbol": "0501", "provider_ticker": "0501.HK"},
    ]


def price_rows() -> dict[str, dict[str, object]]:
    return {
        "HKEX:0700": {
            "ok": True,
            "exchange": "HKEX",
            "symbol": "0700",
            "provider_ticker": "0700.HK",
            "close_date": "2026-06-29",
            "one_session_change_pct": 1.2,
        },
        "HKEX:9988": {
            "ok": True,
            "exchange": "HKEX",
            "symbol": "9988",
            "provider_ticker": "9988.HK",
            "close_date": "2026-06-29",
            "one_session_change_pct": -0.4,
        },
        "HKEX:0501": {
            "ok": False,
            "exchange": "HKEX",
            "symbol": "0501",
            "provider_ticker": "0501.HK",
            "close_date": "2026-06-29",
            "reason": "empty_price_frame",
        },
    }


class StaticRunner:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del prompt_text, timeout_seconds
        return RunnerResult(True, text=json.dumps(self.payload), elapsed_seconds=0.01, returncode=0)


class V3FixtureRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del timeout_seconds
        payload = prompt_input_payload(prompt_text)
        self.calls.append(str(payload["agent_id"]))
        return RunnerResult(True, text=json.dumps(fixture_v3_agent_output(payload)), elapsed_seconds=0.01, returncode=0)


class V3FailingAgentRunner(V3FixtureRunner):
    def __init__(self, failed_agent: str) -> None:
        super().__init__()
        self.failed_agent = failed_agent

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        payload = prompt_input_payload(prompt_text)
        self.calls.append(str(payload["agent_id"]))
        if payload["agent_id"] == self.failed_agent:
            return RunnerResult(False, reason="simulated independent agent failure", elapsed_seconds=0.01, returncode=1)
        return RunnerResult(True, text=json.dumps(fixture_v3_agent_output(payload)), elapsed_seconds=0.01, returncode=0)


class V3OrderingRunner(V3FixtureRunner):
    def __init__(self) -> None:
        super().__init__()
        self.lock = threading.Lock()
        self.started: dict[str, float] = {}
        self.finished: dict[str, float] = {}
        self.order_errors: list[str] = []

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del timeout_seconds
        payload = prompt_input_payload(prompt_text)
        agent_id = str(payload["agent_id"])
        with self.lock:
            self.calls.append(agent_id)
            self.started[agent_id] = time.monotonic()
            if agent_id == "chairman_synthesis":
                missing = [key for key in ("k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view") if key not in self.finished]
                if missing:
                    self.order_errors.append(f"chairman_started_before:{','.join(missing)}")
            if agent_id == "red_team_audit" and "chairman_synthesis" not in self.finished:
                self.order_errors.append("red_team_started_before_chairman")
        if agent_id in {"k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view"}:
            time.sleep(0.05)
        response = fixture_v3_agent_output(payload)
        with self.lock:
            self.finished[agent_id] = time.monotonic()
        return RunnerResult(True, text=json.dumps(response), elapsed_seconds=0.01, returncode=0)


class StatusReadingRunner(StaticRunner):
    def __init__(self, payload: dict[str, object], status_path: Path) -> None:
        super().__init__(payload)
        self.status_path = status_path
        self.public_heartbeats: list[str | None] = []

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        if self.status_path.exists():
            self.public_heartbeats.append(json.loads(self.status_path.read_text()).get("last_heartbeat_utc"))
        else:
            self.public_heartbeats.append(None)
        return super().complete(prompt_text, timeout_seconds=timeout_seconds)


class RecordingAlaya(MockAlayaSyncClient):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def sync(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return super().sync(payload)


class RealSuccessAlaya(RecordingAlaya):
    def sync(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "status": "synced",
            "mode": "real",
            "event_id": "real-event-1",
            "event_hash": "real-hash-1",
            "readback_status": "verified",
            "write_seconds": 0.02,
            "readback_seconds": 0.03,
            "total_seconds": 0.05,
        }


class FailingAlaya(RecordingAlaya):
    def sync(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "status": "failed",
            "mode": "real",
            "reason": "gotra_internal_state_write_failed",
            "readback_status": "skipped",
        }


class ReadbackMismatchAlaya(RecordingAlaya):
    def sync(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "status": "failed",
            "mode": "real",
            "reason": "alaya_readback_mismatch",
            "event_id": "real-event-1",
            "event_hash": "expected-hash",
            "readback_status": "mismatch",
        }


def valid_payload(symbol: str = "0700") -> dict[str, object]:
    return {
        "schema": "gotra.full_analyst.symbol.v1",
        "run_id": "full_analyst_evening_hk_20260629_v1",
        "symbol": symbol,
        "exchange": "HKEX",
        "as_of_date": "2026-06-29",
        "trading_date": "2026-06-29",
        "price_coverage_status": "ok",
        "research_summary": "Public-safe research summary only.",
        "key_updates": ["Public update to verify."],
        "positive_case": ["Positive case to monitor."],
        "negative_case": ["Negative case to monitor."],
        "red_team_review": ["Red-team review rejects trading conclusions."],
        "risk_factors": ["Source freshness risk."],
        "watch_items": ["Next verified public update."],
        "source_notes": ["Public-safe source note."],
        "boundary": list(BOUNDARY_LINES),
    }


def valid_v2_payload(symbol: str = "0700") -> dict[str, object]:
    return {
        "schema": SYMBOL_SCHEMA,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "execution_model": EXECUTION_MODEL,
        "symbol": symbol,
        "exchange": "HKEX",
        "provider_ticker": f"{symbol}.HK",
        "as_of_date": "2026-06-29",
        "price_coverage_status": "ok",
        "research_context": {
            "scope": "Public-source research frame.",
            "source_freshness": "Use verified public updates.",
        },
        "k_deep_research": {
            "summary": "K view maps upstream drivers and source freshness.",
            "evidence_focus": ["public filings", "market structure"],
        },
        "f_partner_view": {"summary": "Constructive case depends on verified demand signals."},
        "w_partner_view": {"summary": "Cautious case highlights valuation and competition pressure."},
        "g_partner_view": {"summary": "Governance view keeps evidence gaps visible."},
        "chairman_synthesis": {"summary": "Integrated research status remains watch."},
        "red_team_audit": {"summary": "Do not turn uncertainty into an action-like answer."},
        "evidence_gaps": ["Source freshness still needs regular review."],
        "watch_conditions": ["Next verified public filing."],
        "research_status": "watch",
        "confidence_boundary": "Bounded by public evidence freshness.",
        "source_notes": ["Public-safe source note."],
        "reader_boundary": "Research content only. This does not constitute investment advice.",
    }


def test_fixture_run_writes_independent_public_and_static_artifacts(tmp_path: Path) -> None:
    cfg = config(tmp_path)

    exit_code = run(cfg, universe_items=universe(), price_rows=price_rows())

    assert exit_code == 0
    report = cfg.output_dir / "full_analyst_evening_hk_2026-06-29.md"
    status_path = cfg.output_dir / "status_full_analyst_evening_hk.json"
    assert report.exists()
    assert status_path.exists()
    assert not (cfg.output_dir / "status.json").exists()
    assert not (cfg.output_dir / "latest.md").exists()
    assert (cfg.static_dir / report.name).exists()
    assert (cfg.static_dir / status_path.name).exists()

    status = json.loads(status_path.read_text())
    assert status["run_status"] == "completed_with_review_items"
    assert status["publish_count"] == 2
    assert status["needs_review_count"] == 1
    assert status["data_gap_count"] == 1
    assert status["max_concurrency"] == 1
    assert "candidate_service" in status
    assert "candidate_timer" in status
    assert status["candidate_service"] is None
    assert status["candidate_timer"] is None
    assert status["symbol_count"] == 3
    assert status["exchange_counts"] == {"HKEX": 3}
    assert status["symbol_hash"]
    assert status["stage_statuses"]["data_fetch"] == "data_gap"
    assert status["stage_statuses"]["judge_gate"] == "needs_review"
    assert status["stage_statuses"]["public_safety_scan"] == "ok"
    assert status["alaya_synced_count"] == 2
    assert status["alaya_write_seconds"] >= 0
    assert status["alaya_readback_seconds"] >= 0
    assert status["alaya_total_seconds"] >= 0
    assert status["provider_model_io_embedded"] is False
    assert status["prompt_template_version"] == PROMPT_TEMPLATE_VERSION
    assert status["symbol_schema"] == SYMBOL_SCHEMA
    assert status["methodology_version"] == METHODOLOGY_VERSION
    assert status["execution_model"] == EXECUTION_MODEL
    assert status["alaya_event_schema"] == ALAYA_EVENT_SCHEMA
    assert "local checks + one-shot runtime smoke" in status["evidence_layer"]
    assert (cfg.private_audit_root / cfg.run_id / "heartbeat.json").exists()
    assert (cfg.private_audit_root / cfg.run_id / "events.jsonl").exists()
    assert (cfg.private_audit_root / cfg.run_id / "cycle_001_summary.json").exists()


def test_all_symbols_config_selects_entire_public_universe() -> None:
    args = parse_args(
        [
            "--mode",
            MODE,
            "--all-symbols",
            "--candidate-service",
            "gotra-full-analyst-evening-hk-candidate.service",
            "--candidate-timer",
            "gotra-full-analyst-evening-hk-candidate.timer",
            "--max-concurrency",
            "3",
        ]
    )

    cfg = config_from_args(args)
    selected = selected_universe(universe(), cfg.symbols)

    assert cfg.all_symbols is True
    assert cfg.symbols == ()
    assert cfg.max_concurrency == 3
    assert cfg.candidate_service == "gotra-full-analyst-evening-hk-candidate.service"
    assert cfg.candidate_timer == "gotra-full-analyst-evening-hk-candidate.timer"
    assert [f"{item['exchange']}:{item['symbol']}" for item in selected] == [
        "HKEX:0700",
        "HKEX:9988",
        "HKEX:0501",
    ]


def test_all_publish_exits_zero_with_real_alaya_readback_verified(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(**{**cfg.__dict__, "alaya_mode": "real"})
    alaya = RealSuccessAlaya()

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=alaya,
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 0
    assert status["run_status"] == "completed"
    assert status["publish_count"] == 1
    assert status["alaya_synced_count"] == 1
    assert status["alaya_readback_verified_count"] == 1
    assert status["alaya_readback_status"] == "verified"
    assert status["alaya_write_seconds"] == 0.02
    assert status["alaya_readback_seconds"] == 0.03
    assert status["alaya_total_seconds"] == 0.05
    assert alaya.calls


def test_real_alaya_uses_gotra_internal_state_hash_chain(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(**{**cfg.__dict__, "alaya_mode": "real"})
    state_path = cfg.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=GotraInternalAlayaSyncClient(
            state_path=state_path,
            actor="test/full_analyst_pipeline",
        ),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    records = [json.loads(line) for line in state_path.read_text().splitlines() if line.strip()]
    event_meta = json.loads(
        (cfg.private_audit_root / cfg.run_id / "alaya_events" / "HKEX_0700.json").read_text()
    )
    assert exit_code == 0
    assert status["alaya_mode"] == "real"
    assert status["alaya_readback_status"] == "verified"
    assert status["alaya_readback_verified_count"] == 1
    assert records[0]["event_type"] == "full_analyst_memory_sync"
    assert records[0]["event_schema"] == ALAYA_EVENT_SCHEMA
    assert records[0]["cognition_flywheel_layer"] == "full_analyst_ksana_4_1_lite"
    assert records[0]["methodology_version"] == METHODOLOGY_VERSION
    assert records[0]["execution_model"] == EXECUTION_MODEL
    assert records[0]["agent_outputs"]["k_deep_research"]
    assert records[0]["public_payload_hash"] == event_meta["public_payload_hash"]
    assert records[0]["event_hash"] == event_meta["event_hash"]


def test_v2_payload_preserves_ksana_sections_and_compatibility_fields(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_v2_payload()),
        alaya_client=RecordingAlaya(),
    )

    symbol_payload = json.loads((cfg.output_dir / "symbols" / "HKEX_0700.json").read_text())
    assert exit_code == 0
    assert symbol_payload["schema"] == SYMBOL_SCHEMA
    assert symbol_payload["prompt_template_version"] == PROMPT_TEMPLATE_VERSION
    assert symbol_payload["methodology_version"] == METHODOLOGY_VERSION
    assert symbol_payload["execution_model"] == EXECUTION_MODEL
    assert symbol_payload["k_deep_research"]["summary"].startswith("K view")
    assert symbol_payload["chairman_synthesis"]["summary"] == "Integrated research status remains watch."
    assert symbol_payload["research_summary"] == "Integrated research status remains watch."
    assert symbol_payload["positive_case"]
    assert symbol_payload["negative_case"]
    assert symbol_payload["red_team_review"]
    assert symbol_payload["evidence_gaps"] == ["Source freshness still needs regular review."]
    assert symbol_payload["watch_conditions"] == ["Next verified public filing."]


def test_v3_fixture_run_writes_independent_agent_schema_and_hashes(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "execution_model": EXECUTION_MODEL_V3,
            "requested_execution_model": EXECUTION_MODEL_V3,
            "agent_concurrency": 4,
            "alaya_mode": "real",
        }
    )
    state_path = cfg.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"
    runner = V3FixtureRunner()

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=runner,
        alaya_client=GotraInternalAlayaSyncClient(state_path=state_path, actor="test/full_analyst_pipeline"),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    symbol_payload = json.loads((cfg.output_dir / "symbols" / "HKEX_0700.json").read_text())
    records = [json.loads(line) for line in state_path.read_text().splitlines() if line.strip()]
    assert exit_code == 0
    assert runner.calls.count("k_deep_research") == 1
    assert runner.calls.count("f_partner_view") == 1
    assert runner.calls.count("w_partner_view") == 1
    assert runner.calls.count("g_partner_view") == 1
    assert runner.calls.count("chairman_synthesis") == 1
    assert runner.calls.count("red_team_audit") == 1
    assert status["prompt_template_version"] == PROMPT_TEMPLATE_VERSION_V3
    assert status["symbol_schema"] == SYMBOL_SCHEMA_V3
    assert status["methodology_version"] == METHODOLOGY_VERSION_V3
    assert status["execution_model"] == EXECUTION_MODEL_V3
    assert status["agent_parallelism"] == 4
    assert status["agent_calls_total"] == 6
    assert status["alaya_event_schema"] == ALAYA_EVENT_SCHEMA_V3
    assert symbol_payload["schema"] == SYMBOL_SCHEMA_V3
    assert symbol_payload["execution_model"] == EXECUTION_MODEL_V3
    assert set(symbol_payload["agent_outputs"]) == {
        "k_deep_research",
        "f_partner_view",
        "w_partner_view",
        "g_partner_view",
        "chairman_synthesis",
        "red_team_audit",
    }
    assert all(symbol_payload["agent_hashes"].values())
    assert symbol_payload["agent_hashes"]["chairman_synthesis"] == symbol_payload["agent_outputs"]["chairman_synthesis"]["output_hash"]
    assert symbol_payload["parallelism"]["kfwg_ran_in_parallel"] is True
    assert symbol_payload["agent_timings"]["total_wall_clock_seconds"] >= 0
    assert records[0]["event_schema"] == ALAYA_EVENT_SCHEMA_V3
    assert records[0]["cognition_flywheel_layer"] == "full_analyst_independent_agents"
    assert records[0]["agent_hashes"] == symbol_payload["agent_hashes"]
    assert records[0]["public_payload_hash"] == symbol_payload["public_payload_hash"]


def test_v3_kfwg_parallel_then_chairman_then_red_team(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "execution_model": EXECUTION_MODEL_V3,
            "requested_execution_model": EXECUTION_MODEL_V3,
            "agent_concurrency": 4,
        }
    )
    runner = V3OrderingRunner()

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=runner,
        alaya_client=RecordingAlaya(),
    )

    assert exit_code == 0
    assert runner.order_errors == []
    kfwg_starts = [runner.started[key] for key in ("k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view")]
    assert max(kfwg_starts) - min(kfwg_starts) < 0.08
    assert runner.started["chairman_synthesis"] >= max(runner.finished[key] for key in ("k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view"))
    assert runner.started["red_team_audit"] >= runner.finished["chairman_synthesis"]


def test_v3_agent_sanitizer_fills_pipeline_owned_metadata(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    payload = {
        "status": "ok",
        "findings": ["Chairman synthesis keeps the research state bounded by evidence freshness."],
        "evidence_gaps": ["Issuer filing refresh is still required."],
        "uncertainties": ["Public context may be stale."],
        "watch_conditions": ["Next verified public filing."],
        "research_status": "watch",
        "confidence_boundary": "Confidence is limited by public evidence freshness.",
    }

    output = sanitize_v3_agent_output(
        payload,
        agent_id="chairman_synthesis",
        item=universe()[0],
        config=cfg,
        input_context_hash="input-hash",
        started_at="2026-07-03T00:00:00Z",
        finished_at="2026-07-03T00:00:01Z",
        duration_seconds=1.0,
    )

    assert output["status"] == "ok"
    assert output["agent_id"] == "chairman_synthesis"
    assert output["schema"] == "gotra.full_analyst.agent_output.v3"
    assert output["symbol"] == "0700"
    assert output["run_id"] == cfg.run_id
    assert output["boundary"] == "research content only; does not constitute investment advice"
    assert output["output_hash"]


def test_v3_agent_failure_blocks_symbol_and_preserves_failure_readback(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "execution_model": EXECUTION_MODEL_V3,
            "requested_execution_model": EXECUTION_MODEL_V3,
            "agent_concurrency": 4,
            "alaya_mode": "real",
        }
    )
    state_path = cfg.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=V3FailingAgentRunner("w_partner_view"),
        alaya_client=GotraInternalAlayaSyncClient(state_path=state_path, actor="test/full_analyst_pipeline"),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    symbol_payload = json.loads((cfg.output_dir / "symbols" / "HKEX_0700.json").read_text())
    records = [json.loads(line) for line in state_path.read_text().splitlines() if line.strip()]
    failures = [json.loads(line) for line in (cfg.private_audit_root / cfg.run_id / "failures.jsonl").read_text().splitlines()]
    assert exit_code == 2
    assert status["blocked_count"] == 1
    assert status["alaya_readback_status"] == "verified"
    assert symbol_payload["agent_outputs"]["w_partner_view"]["status"] == "failed"
    assert symbol_payload["failure_records"][0]["agent_id"] == "w_partner_view"
    assert records[0]["failure_records"][0]["agent_id"] == "w_partner_view"
    assert any(row.get("agent_id") == "w_partner_view" for row in failures)


def test_v3_requested_can_explicitly_fallback_to_v2() -> None:
    args = parse_args(["--mode", MODE, "--v3-independent-agents", "--fallback-to-v2"])

    cfg = config_from_args(args)

    assert cfg.requested_execution_model == EXECUTION_MODEL_V3
    assert cfg.execution_model == EXECUTION_MODEL
    assert cfg.v3_independent_agents is False
    assert cfg.explicit_v2_fallback is True


def test_missing_required_field_becomes_blocked_failure(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    payload = valid_payload()
    payload.pop("red_team_review")

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(payload),
        alaya_client=RecordingAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert status["failed_count"] == 1
    assert status["blocked_count"] == 1
    assert status["alaya_synced_count"] == 0
    assert status["blocked_symbols"][0]["reason"] == "missing_required_fields"


def test_raw_io_field_is_blocked_and_not_synced(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    payload = valid_payload()
    payload["messages"] = [{"role": "assistant", "content": "raw"}]
    alaya = RecordingAlaya()

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(payload),
        alaya_client=alaya,
    )

    text = (cfg.output_dir / "full_analyst_evening_hk_2026-06-29.md").read_text()
    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert alaya.calls == []
    assert "messages" not in text
    assert status["blocked_symbols"][0]["reason"] == "forbidden_raw_io_keys_detected"


def test_investment_advice_like_output_is_blocked(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    payload = valid_payload()
    payload["research_summary"] = "This is a buy recommendation."

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(payload),
        alaya_client=RecordingAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert status["blocked_count"] == 1
    assert "forbidden_public_content_detected" in status["blocked_symbols"][0]["reason"]


def test_negated_advice_disclaimer_does_not_trip_public_scanner() -> None:
    assert_public_safe(
        {
            "summary": (
                "This is not a buy recommendation, not a buy/sell/hold recommendation, "
                "and no target prices are provided. The research note does not provide price targets."
            ),
            "boundary": list(BOUNDARY_LINES),
        }
    )


def test_retry_prompt_names_forbidden_public_trigger_privately(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))

    prompt = build_prompt(
        universe()[0],
        price_rows()["HKEX:0700"],
        cfg,
        attempt=2,
        last_error="forbidden_public_content_detected:target_price",
    )

    assert "Previous failure: forbidden_public_content_detected:target_price" in prompt
    assert "Remove the named public-safety trigger" in prompt


def test_forbidden_public_content_reason_is_public_safe(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    payload = valid_payload()
    payload["research_summary"] = "The output mentions stdout and should be blocked."

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(payload),
        alaya_client=RecordingAlaya(),
    )

    status_path = cfg.output_dir / "status_full_analyst_evening_hk.json"
    report_path = cfg.output_dir / "full_analyst_evening_hk_2026-06-29.md"
    status = json.loads(status_path.read_text())
    public_text = status_path.read_text() + "\n" + report_path.read_text()
    assert exit_code == 2
    assert status["blocked_symbols"][0]["reason"] == "forbidden_public_content_detected"
    assert "stdout" not in public_text


def test_alaya_sync_failure_blocks_run(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(**{**cfg.__dict__, "alaya_mode": "real"})

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=FailingAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert status["run_status"] == "completed_with_blockers"
    assert status["alaya_failed_count"] == 1
    assert status["last_error_category"] == "gotra_internal_state_sync_failed"


def test_alaya_readback_mismatch_blocks_run(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(**{**cfg.__dict__, "alaya_mode": "real"})

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=ReadbackMismatchAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert status["alaya_readback_failed_count"] == 1
    assert status["alaya_readback_status"] == "failed"
    assert status["last_error_category"] == "alaya_readback_mismatch"


def test_artifact_write_failure_exits_two(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg.static_dir.write_text("not a directory", encoding="utf-8")

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=RecordingAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert status["artifact_write_status"] == "failed"
    assert status["last_error_category"] == "artifact_write_failed"


def test_public_scan_failure_exits_two(monkeypatch, tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))

    from scripts import public_stock_pool_full_analyst_pipeline as module

    monkeypatch.setattr(module, "render_markdown", lambda status, results: "stdout leaked into public artifact")

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=RecordingAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    assert exit_code == 2
    assert status["public_scan_status"] == "failed"
    assert status["last_error_category"] == "forbidden_public_content_detected"


def test_loop_smoke_writes_loop_named_public_artifacts(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "mode": LOOP_SMOKE_MODE,
            "output_dir": tmp_path / "loop-public",
            "run_id": "full_analyst_10h_loop_20260629_v1",
        }
    )

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=RecordingAlaya(),
    )

    status_path = cfg.output_dir / "status_full_analyst_loop.json"
    status = json.loads(status_path.read_text())
    assert exit_code == 0
    assert status_path.exists()
    assert (cfg.output_dir / "full_analyst_loop_latest.md").exists()
    assert status["evidence_layer"] == "local checks + short loop smoke + public-safe artifact smoke"


def test_loop_public_status_bootstraps_before_first_cycle_artifact(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700", "HKEX:9988"))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "mode": LOOP_MODE,
            "output_dir": tmp_path / "loop-public",
            "run_id": "full_analyst_10h_loop_20260629_v1",
            "alaya_mode": "real",
            "loop_duration_seconds": 36000,
        }
    )

    update_loop_public_status(
        cfg,
        current_cycle=0,
        last_successful_cycle=0,
        loop_status="running",
        phase="preflight",
        started_at_utc="2026-06-29T00:00:00Z",
        sample_symbols=(),
    )

    status_path = cfg.output_dir / "status_full_analyst_loop.json"
    report_path = cfg.output_dir / "full_analyst_loop_latest.md"
    status = json.loads(status_path.read_text())
    public_text = status_path.read_text() + "\n" + report_path.read_text()
    assert status["status"] == "running"
    assert status["run_status"] == "running"
    assert status["phase"] == "preflight"
    assert status["alaya_mode"] == "real"
    assert status["alaya_sync_status"] == "pending"
    assert status["sample_symbols"] == []
    assert status["publish_count"] == 0
    assert report_path.exists()
    assert (cfg.static_dir / "status_full_analyst_loop.json").exists()
    assert "stdout" not in public_text
    assert "stderr" not in public_text


def test_loop_public_status_resets_stale_run_id(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700", "HKEX:9988"))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "mode": LOOP_MODE,
            "output_dir": tmp_path / "loop-public",
            "run_id": "full_analyst_10h_loop_20260629_v2",
            "alaya_mode": "real",
            "loop_duration_seconds": 36000,
        }
    )
    status_path = cfg.output_dir / "status_full_analyst_loop.json"
    cfg.output_dir.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "run_id": "full_analyst_10h_loop_20260629_v1",
                "mode": LOOP_MODE,
                "status": "running",
                "publish_count": 99,
                "sample_symbols": ["OLD"],
            }
        ),
        encoding="utf-8",
    )

    update_loop_public_status(
        cfg,
        current_cycle=0,
        last_successful_cycle=0,
        loop_status="running",
        phase="preflight",
        started_at_utc="2026-06-29T00:00:00Z",
        sample_symbols=(),
    )

    status = json.loads(status_path.read_text())
    assert status["run_id"] == "full_analyst_10h_loop_20260629_v2"
    assert status["publish_count"] == 0
    assert status["sample_symbols"] == []
    assert status["phase"] == "preflight"


def test_loop_cycles_keep_distinct_private_summaries_and_cycle_heartbeat(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "mode": LOOP_MODE,
            "output_dir": tmp_path / "loop-public",
            "run_id": "full_analyst_10h_loop_20260629_v1",
            "loop_current_cycle": 1,
            "loop_last_successful_cycle": 0,
        }
    )

    first_exit = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=RecordingAlaya(),
    )
    second_cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "loop_current_cycle": 2,
            "loop_last_successful_cycle": 1,
        }
    )
    second_exit = run(
        second_cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=RecordingAlaya(),
    )

    run_dir = cfg.private_audit_root / cfg.run_id
    heartbeat = json.loads((run_dir / "heartbeat.json").read_text())
    cycle_001 = json.loads((run_dir / "cycle_001_summary.json").read_text())
    cycle_002 = json.loads((run_dir / "cycle_002_summary.json").read_text())
    assert first_exit == 0
    assert second_exit == 0
    assert cycle_001["cycle_id"] == "cycle_001"
    assert cycle_001["current_cycle"] == 1
    assert cycle_002["cycle_id"] == "cycle_002"
    assert cycle_002["current_cycle"] == 2
    assert heartbeat["current_cycle"] == 2
    assert heartbeat["last_successful_cycle"] == 2


def test_loop_llm_symbol_heartbeat_refreshes_public_status(monkeypatch, tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700", "HKEX:9988"))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "mode": LOOP_MODE,
            "output_dir": tmp_path / "loop-public",
            "run_id": "full_analyst_10h_loop_20260629_v1",
            "loop_current_cycle": 3,
            "loop_last_successful_cycle": 2,
            "loop_duration_seconds": 36000,
        }
    )
    from scripts import public_stock_pool_full_analyst_pipeline as module

    ticks = count()

    def ticking_utc_now() -> str:
        return (
            datetime(2026, 6, 29, tzinfo=timezone.utc) + timedelta(seconds=next(ticks))
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    monkeypatch.setattr(module, "utc_now_iso", ticking_utc_now)
    runner = StatusReadingRunner(valid_payload(), cfg.output_dir / "status_full_analyst_loop.json")

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=runner,
        alaya_client=RecordingAlaya(),
        loop_started_at_utc="2026-06-29T00:00:00Z",
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_loop.json").read_text())
    assert exit_code == 0
    assert len(runner.public_heartbeats) == 2
    assert runner.public_heartbeats[0] is not None
    assert runner.public_heartbeats[1] is not None
    assert runner.public_heartbeats[1] != runner.public_heartbeats[0]
    assert status["current_cycle"] == 3
    assert status["sample_symbols"] == ["HKEX:0700", "HKEX:9988"]


def test_loop_completed_status_updates_markdown_status_block(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "mode": LOOP_MODE,
            "output_dir": tmp_path / "loop-public",
            "run_id": "full_analyst_concurrency3_fullpool_20260630_v1_run1",
            "loop_current_cycle": 1,
            "loop_last_successful_cycle": 0,
            "loop_duration_seconds": 36000,
        }
    )

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=StaticRunner(valid_payload()),
        alaya_client=RecordingAlaya(),
        loop_started_at_utc="2026-06-29T00:00:00Z",
    )

    report_path = cfg.output_dir / "full_analyst_loop_latest.md"
    assert exit_code == 0
    assert "- phase: artifact" in report_path.read_text()

    update_loop_public_status(
        cfg,
        current_cycle=1,
        last_successful_cycle=1,
        loop_status="completed",
        phase="completed",
        started_at_utc="2026-06-29T00:00:00Z",
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_loop.json").read_text())
    markdown = report_path.read_text()
    assert status["status"] == "completed"
    assert status["run_status"] == "completed"
    assert status["phase"] == "completed"
    assert "- status: completed" in markdown
    assert "- run_status: completed" in markdown
    assert "- phase: completed" in markdown
    assert "- phase: artifact" not in markdown


def test_public_artifacts_do_not_expose_forbidden_runtime_surfaces(tmp_path: Path) -> None:
    cfg = config(tmp_path)

    run(cfg, universe_items=universe(), price_rows=price_rows())

    public_text = "\n".join(path.read_text() for path in cfg.output_dir.rglob("*") if path.is_file())
    assert "OPENAI_API_KEY" not in public_text
    assert "sk-" not in public_text
    assert "Bearer" not in public_text
    assert "Authorization" not in public_text
    assert "prompt_text" not in public_text
    assert "raw_provider_response" not in public_text
    assert "completion" not in public_text
    assert "stdout" not in public_text
    assert "stderr" not in public_text

    private_attempts = list((cfg.private_audit_root / cfg.run_id / "attempts").glob("*.json"))
    assert private_attempts
    assert "prompt_text" in private_attempts[0].read_text()
