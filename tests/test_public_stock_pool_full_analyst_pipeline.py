import json
import subprocess
import threading
import time
from datetime import date, datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pytest

from scripts.public_stock_pool_full_research import RunnerResult
from scripts.public_stock_pool_full_analyst_pipeline import (
    BOUNDARY_LINES,
    LOOP_MODE,
    LOOP_SMOKE_MODE,
    MODE,
    ALAYA_EVENT_SCHEMA,
    ALAYA_EVENT_SCHEMA_V3,
    ALAYA_EVENT_SCHEMA_V35,
    ALAYA_EVENT_SCHEMA_V40,
    CHAIRMAN_SCHEMA_V4,
    EVIDENCE_PACKET_SCHEMA,
    EVIDENCE_PACKET_SCHEMA_V2,
    EXECUTION_MODEL,
    EXECUTION_MODEL_V3,
    EXECUTION_MODEL_V35,
    EXECUTION_MODEL_V40,
    FullAnalystConfig,
    GotraInternalAlayaSyncClient,
    K_DOSSIER_SCHEMA,
    KNOWLEDGE_GATE_SCHEMA,
    LEDGER_ENTRY_SCHEMA,
    LEDGER_MANIFEST_SCHEMA,
    MARKET_DATA_SNAPSHOT_SCHEMA,
    METHODOLOGY_VERSION,
    METHODOLOGY_VERSION_V3,
    METHODOLOGY_VERSION_V35,
    METHODOLOGY_VERSION_V40,
    MockAlayaSyncClient,
    PERSPECTIVE_AGENT_SCHEMA_V4,
    PUBLICATION_DECISION_SCHEMA,
    PROMPT_TEMPLATE_VERSION,
    PROMPT_TEMPLATE_VERSION_V3,
    PROMPT_TEMPLATE_VERSION_V35,
    PROMPT_TEMPLATE_VERSION_V40,
    RED_TEAM_SCHEMA_V4,
    RESEARCH_QUALITY_GATE_SCHEMA,
    RESEARCH_SIGNAL_SCHEMA,
    REVIEW_RESULT_SCHEMA,
    RESEARCH_TASK_SCHEMA,
    RESEARCH_TASK_SCHEMA_V2,
    SYMBOL_SCHEMA,
    SYMBOL_SCHEMA_V3,
    SYMBOL_SCHEMA_V35,
    SYMBOL_SCHEMA_V40,
    assert_public_safe,
    build_prompt,
    build_ledger_entry,
    config_from_args,
    fixture_k_dossier_output,
    fixture_research_task_output,
    fixture_v3_agent_output,
    prompt_input_payload,
    parse_args,
    run,
    sanitize_research_task,
    sanitize_v3_agent_output,
    selected_universe,
    stable_hash,
    update_loop_public_status,
    v3_agent_failure_record,
    validate_evidence_packet_contract,
    load_existing_research_ledger,
    merge_research_ledger,
    validate_publication_decision_contract,
    validate_ledger_entry_contract,
    validate_review_result_contract,
    validate_research_signal_contract,
    verify_ledger_chain,
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
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del timeout_seconds
        payload = prompt_input_payload(prompt_text)
        self.payloads.append(payload)
        if payload.get("required_schema") in {RESEARCH_TASK_SCHEMA, RESEARCH_TASK_SCHEMA_V2}:
            self.calls.append("research_task_planner")
            return RunnerResult(True, text=json.dumps(fixture_research_task_output(payload)), elapsed_seconds=0.01, returncode=0)
        if payload.get("required_schema") == K_DOSSIER_SCHEMA:
            self.calls.append("k_deep_research_dossier")
            return RunnerResult(True, text=json.dumps(fixture_k_dossier_output(payload)), elapsed_seconds=0.01, returncode=0)
        self.calls.append(str(payload["agent_id"]))
        return RunnerResult(True, text=json.dumps(fixture_v3_agent_output(payload)), elapsed_seconds=0.01, returncode=0)


class V3FailingAgentRunner(V3FixtureRunner):
    def __init__(self, failed_agent: str) -> None:
        super().__init__()
        self.failed_agent = failed_agent

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        payload = prompt_input_payload(prompt_text)
        self.payloads.append(payload)
        if payload.get("required_schema") in {RESEARCH_TASK_SCHEMA, RESEARCH_TASK_SCHEMA_V2}:
            self.calls.append("research_task_planner")
            return RunnerResult(True, text=json.dumps(fixture_research_task_output(payload)), elapsed_seconds=0.01, returncode=0)
        if payload.get("required_schema") == K_DOSSIER_SCHEMA:
            self.calls.append("k_deep_research_dossier")
            return RunnerResult(True, text=json.dumps(fixture_k_dossier_output(payload)), elapsed_seconds=0.01, returncode=0)
        self.calls.append(str(payload["agent_id"]))
        if payload["agent_id"] == self.failed_agent:
            return RunnerResult(False, reason="simulated independent agent failure", elapsed_seconds=0.01, returncode=1)
        return RunnerResult(True, text=json.dumps(fixture_v3_agent_output(payload)), elapsed_seconds=0.01, returncode=0)


class V3RetrySafetyRunner(V3FixtureRunner):
    def __init__(self, retry_agent: str) -> None:
        super().__init__()
        self.retry_agent = retry_agent
        self.agent_attempts: dict[str, int] = {}

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del timeout_seconds
        payload = prompt_input_payload(prompt_text)
        self.payloads.append(payload)
        if payload.get("required_schema") in {RESEARCH_TASK_SCHEMA, RESEARCH_TASK_SCHEMA_V2}:
            self.calls.append("research_task_planner")
            return RunnerResult(True, text=json.dumps(fixture_research_task_output(payload)), elapsed_seconds=0.01, returncode=0)
        if payload.get("required_schema") == K_DOSSIER_SCHEMA:
            self.calls.append("k_deep_research_dossier")
            return RunnerResult(True, text=json.dumps(fixture_k_dossier_output(payload)), elapsed_seconds=0.01, returncode=0)
        agent_id = str(payload["agent_id"])
        self.calls.append(agent_id)
        self.agent_attempts[agent_id] = self.agent_attempts.get(agent_id, 0) + 1
        if agent_id == self.retry_agent and self.agent_attempts[agent_id] == 1:
            response = fixture_v3_agent_output(payload)
            response["findings"] = ["This clause contains a target price and must be retried."]
            return RunnerResult(True, text=json.dumps(response), elapsed_seconds=0.01, returncode=0)
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
        self.payloads.append(payload)
        if payload.get("required_schema") in {RESEARCH_TASK_SCHEMA, RESEARCH_TASK_SCHEMA_V2}:
            self.calls.append("research_task_planner")
            return RunnerResult(True, text=json.dumps(fixture_research_task_output(payload)), elapsed_seconds=0.01, returncode=0)
        if payload.get("required_schema") == K_DOSSIER_SCHEMA:
            with self.lock:
                self.calls.append("k_deep_research_dossier")
                self.started["k_deep_research_dossier"] = time.monotonic()
            time.sleep(0.05)
            response = fixture_k_dossier_output(payload)
            with self.lock:
                self.finished["k_deep_research_dossier"] = time.monotonic()
                self.finished["k_deep_research"] = self.finished["k_deep_research_dossier"]
            return RunnerResult(True, text=json.dumps(response), elapsed_seconds=0.01, returncode=0)
        agent_id = str(payload["agent_id"])
        with self.lock:
            self.calls.append(agent_id)
            self.started[agent_id] = time.monotonic()
            if agent_id in {"f_partner_view", "w_partner_view", "g_partner_view"} and "k_deep_research_dossier" in self.started and "k_deep_research_dossier" not in self.finished:
                self.order_errors.append(f"{agent_id}_started_before_k_dossier_finished")
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
        "confidence_boundary": {
            "overall": "Confidence is limited by public evidence freshness.",
            "not_supported": "No stronger issuer conclusion is supported without official-source refresh.",
        },
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
    assert "{" not in output["confidence_boundary"]
    assert "}" not in output["confidence_boundary"]
    assert output["output_hash"]


def test_v35_structured_task_and_evidence_refs_are_not_python_dict_text(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    task = sanitize_research_task(
        {
            "schema": RESEARCH_TASK_SCHEMA,
            "run_id": cfg.run_id,
            "symbol": "0700",
            "exchange": "HKEX",
            "provider_ticker": "0700.HK",
            "as_of_date": cfg.as_of_date.isoformat(),
            "selection_reason": {
                "why_today": "Coverage is current enough for a bounded research task.",
                "data_gap": "Official issuer source coverage is incomplete.",
            },
            "trigger_context": {"coverage_status": "ok"},
            "research_mission": {"summary": "Map evidence strength before any synthesis."},
            "core_questions": ["Question one?", "Question two?", "Question three?"],
            "required_sources": [{"source_type": "price_data", "purpose": "confirm coverage", "required": True}],
            "must_not_conclude_without": ["official issuer evidence"],
            "evidence_gap_policy": ["keep missing official source visible"],
            "agent_briefs": {"k_deep_research": {"summary": "Use packet evidence only."}},
            "reader_boundary": "Research content only. This does not constitute investment advice.",
        },
        item=universe()[0],
        price_row=price_rows()["HKEX:0700"],
        config=cfg,
    )
    output = sanitize_v3_agent_output(
        {
            "status": "ok",
            "findings": [{"summary": "Structured finding should become reader text."}],
            "evidence_refs": [
                {"evidence_id": "price_context", "source_type": "price_data"},
                {"evidence_id": "public_stock_pool_metadata", "source_type": "public_stock_pool_metadata"},
            ],
            "evidence_gaps": [{"summary": "Official issuer evidence is missing."}],
            "uncertainties": ["Source coverage is incomplete."],
            "watch_conditions": ["Next verified public update."],
        },
        agent_id="k_deep_research",
        item=universe()[0],
        config=cfg,
        input_context_hash="input-hash",
        started_at="2026-07-03T00:00:00Z",
        finished_at="2026-07-03T00:00:01Z",
        duration_seconds=1.0,
    )

    assert "{" not in task["selection_reason"]
    assert "}" not in task["selection_reason"]
    assert task["research_mission"] == "Map evidence strength before any synthesis."
    assert output["evidence_refs"] == ["price_context", "public_stock_pool_metadata"]
    assert all("{" not in item and "}" not in item for item in output["findings"])
    assert all("{" not in item and "}" not in item for item in output["evidence_gaps"])


def test_v35_research_task_neutralizes_boundary_policy_terms(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    task = sanitize_research_task(
        {
            "schema": RESEARCH_TASK_SCHEMA,
            "run_id": cfg.run_id,
            "symbol": "0700",
            "exchange": "HKEX",
            "provider_ticker": "0700.HK",
            "as_of_date": cfg.as_of_date.isoformat(),
            "selection_reason": "The symbol needs a bounded evidence task before any synthesis.",
            "trigger_context": {"coverage_status": "data_gap"},
            "research_mission": (
                "Audit for target price, price targets, price objectives, buy recommendation, "
                "sell rating, hold signal, position sizing, and return promise wording."
            ),
            "core_questions": [
                "Which primary public sources are required?",
                "Which evidence gaps must stay visible?",
                "Which boundary categories must be audited before reader publication?",
            ],
            "required_sources": [{"source_type": "price_data", "purpose": "confirm coverage", "required": True}],
            "must_not_conclude_without": [
                "No target price or buy recommendation category may appear as a conclusion."
            ],
            "evidence_gap_policy": ["Keep position sizing and return promise language out of reader copy."],
            "agent_briefs": {
                "red_team_audit": "Check target price, sell rating, hold signal, and position sizing wording."
            },
            "reader_boundary": "Research content only. This does not constitute investment advice.",
        },
        item=universe()[0],
        price_row=price_rows()["HKEX:0700"],
        config=cfg,
    )

    text = json.dumps(task, ensure_ascii=False).lower()
    assert "target price" not in text
    assert "price target" not in text
    assert "price objective" not in text
    assert "buy recommendation" not in text
    assert "sell rating" not in text
    assert "hold signal" not in text
    assert "position sizing" not in text
    assert "return promise" not in text
    assert "price-objective wording" in text
    assert "directional-action wording" in text
    assert "allocation-guidance wording" in text
    assert "outcome-promise wording" in text
    assert_public_safe(task)


def test_v35_research_task_fills_default_required_sources_when_missing(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    task = sanitize_research_task(
        {
            "schema": RESEARCH_TASK_SCHEMA,
            "run_id": cfg.run_id,
            "symbol": "0700",
            "exchange": "HKEX",
            "provider_ticker": "0700.HK",
            "as_of_date": cfg.as_of_date.isoformat(),
            "selection_reason": "The symbol needs a bounded evidence task before synthesis.",
            "trigger_context": {"coverage_status": "data_gap"},
            "research_mission": "Resolve public evidence coverage and preserve unresolved gaps.",
            "core_questions": [
                "Which public sources are required today?",
                "Which source gaps must remain visible?",
                "Which claims should wait for official evidence?",
            ],
            "required_sources": [],
            "must_not_conclude_without": ["official issuer evidence", "fresh price coverage"],
            "evidence_gap_policy": ["Keep missing required sources visible."],
            "agent_briefs": {"k_deep_research": "Use the evidence packet only."},
            "reader_boundary": "Research content only. This does not constitute investment advice.",
        },
        item=universe()[0],
        price_row=price_rows()["HKEX:0700"],
        config=cfg,
    )

    source_types = {source["source_type"] for source in task["required_sources"]}
    assert {"exchange_filing", "company_report", "price_data", "current_public_status"} <= source_types
    assert all(source["purpose"] for source in task["required_sources"])
    assert_public_safe(task)


def test_v35_research_task_fills_blank_required_source_purposes(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    task = sanitize_research_task(
        {
            "schema": RESEARCH_TASK_SCHEMA,
            "run_id": cfg.run_id,
            "symbol": "0700",
            "exchange": "HKEX",
            "provider_ticker": "0700.HK",
            "as_of_date": cfg.as_of_date.isoformat(),
            "selection_reason": "The symbol needs a bounded evidence task before synthesis.",
            "trigger_context": {"coverage_status": "data_gap"},
            "research_mission": "Resolve public evidence coverage and preserve unresolved gaps.",
            "core_questions": [
                "Which public sources are required today?",
                "Which source gaps must remain visible?",
                "Which claims should wait for official evidence?",
            ],
            "required_sources": [{"source_type": "exchange filing", "purpose": "", "required": True}],
            "must_not_conclude_without": ["official issuer evidence", "fresh price coverage"],
            "evidence_gap_policy": ["Keep missing required sources visible."],
            "agent_briefs": {"k_deep_research": "Use the evidence packet only."},
            "reader_boundary": "Research content only. This does not constitute investment advice.",
        },
        item=universe()[0],
        price_row=price_rows()["HKEX:0700"],
        config=cfg,
    )

    assert task["required_sources"] == [
        {
            "source_type": "exchange_filing",
            "purpose": "Review exchange-hosted issuer filings, announcements, circulars, financial reports, disclosure records, and other official documents needed to establish issuer-specific public facts.",
            "required": True,
        }
    ]
    assert_public_safe(task)


def test_v3_agent_retries_public_safety_failure_then_publishes(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "execution_model": EXECUTION_MODEL_V3,
            "requested_execution_model": EXECUTION_MODEL_V3,
            "agent_concurrency": 1,
            "retries": 1,
        }
    )
    runner = V3RetrySafetyRunner("k_deep_research")

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=runner,
        alaya_client=RecordingAlaya(),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    k_latest = json.loads(
        (cfg.private_audit_root / cfg.run_id / "agents" / "HKEX_0700_k_deep_research.json").read_text()
    )
    k_attempt_1 = json.loads(
        (cfg.private_audit_root / cfg.run_id / "agents" / "HKEX_0700_k_deep_research_attempt_1.json").read_text()
    )
    k_attempt_2 = json.loads(
        (cfg.private_audit_root / cfg.run_id / "agents" / "HKEX_0700_k_deep_research_attempt_2.json").read_text()
    )
    symbol_payload = json.loads((cfg.output_dir / "symbols" / "HKEX_0700.json").read_text())

    assert exit_code == 0
    assert status["publish_count"] == 1
    assert runner.calls.count("k_deep_research") == 2
    assert k_attempt_1["status"] == "failed"
    assert k_attempt_1["failure_reason"] == "forbidden_public_content_detected"
    assert k_attempt_1["public_safety_triggers"] == ["price_objective_wording"]
    assert "Retry attempt 2" in k_attempt_2["prompt_text"]
    assert k_latest["status"] == "success"
    assert k_latest["public_output"]["retry_count"] == 1
    assert k_latest["public_output"]["public_safety_triggers"] == ["price_objective_wording"]
    assert symbol_payload["agent_retry_counts"]["k_deep_research"] == 1
    assert symbol_payload["agent_public_safety_triggers"]["k_deep_research"] == ["price_objective_wording"]


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


def test_v35_fixture_run_builds_task_evidence_and_alaya_hash_readback(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "v35_research_system": True,
            "execution_model": EXECUTION_MODEL_V35,
            "requested_execution_model": EXECUTION_MODEL_V35,
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
    assert runner.calls[0] == "research_task_planner"
    assert status["run_status"] == "completed_with_review_items"
    assert status["prompt_template_version"] == PROMPT_TEMPLATE_VERSION_V35
    assert status["symbol_schema"] == SYMBOL_SCHEMA_V35
    assert status["methodology_version"] == METHODOLOGY_VERSION_V35
    assert status["execution_model"] == EXECUTION_MODEL_V35
    assert status["agent_parallelism"] == 4
    assert status["agent_calls_total"] == 7
    assert status["publish_count"] == 0
    assert status["needs_review_count"] == 1
    assert status["blocked_count"] == 0
    assert status["alaya_event_schema"] == ALAYA_EVENT_SCHEMA_V35
    assert status["alaya_readback_status"] == "verified"
    assert status["research_task_seconds"] >= 0
    assert status["evidence_packet_seconds"] >= 0

    assert symbol_payload["schema"] == SYMBOL_SCHEMA_V35
    assert symbol_payload["prompt_template_version"] == PROMPT_TEMPLATE_VERSION_V35
    assert symbol_payload["methodology_version"] == METHODOLOGY_VERSION_V35
    assert symbol_payload["execution_model"] == EXECUTION_MODEL_V35
    assert symbol_payload["research_task"]["schema"] == RESEARCH_TASK_SCHEMA
    assert symbol_payload["research_task"]["selection_reason"]
    assert symbol_payload["research_task_hash"] == symbol_payload["research_task"]["task_hash"]
    assert symbol_payload["evidence_packet"]["schema"] == EVIDENCE_PACKET_SCHEMA
    assert symbol_payload["evidence_packet"]["evidence_items"]
    assert symbol_payload["evidence_packet_hash"] == symbol_payload["evidence_packet"]["evidence_packet_hash"]
    assert symbol_payload["missing_required_sources"]
    assert symbol_payload["research_status"] == "needs_review"
    assert symbol_payload["judge_status"] == "needs_review"
    assert symbol_payload["agent_timings"]["research_task_seconds"] >= 0
    assert symbol_payload["agent_timings"]["evidence_packet_seconds"] >= 0
    assert symbol_payload["agent_hashes"]["chairman_synthesis"]
    assert symbol_payload["agent_hashes"]["red_team_audit"]

    assert records[0]["event_schema"] == ALAYA_EVENT_SCHEMA_V35
    assert records[0]["cognition_flywheel_layer"] == "full_analyst_research_task_evidence_agents"
    assert records[0]["research_task_hash"] == symbol_payload["research_task_hash"]
    assert records[0]["evidence_packet_hash"] == symbol_payload["evidence_packet_hash"]
    assert records[0]["agent_hashes"] == symbol_payload["agent_hashes"]
    assert records[0]["chairman_hash"] == symbol_payload["agent_hashes"]["chairman_synthesis"]
    assert records[0]["red_team_hash"] == symbol_payload["agent_hashes"]["red_team_audit"]
    assert records[0]["public_payload_hash"] == symbol_payload["public_payload_hash"]


def test_v35_agents_receive_research_task_and_evidence_packet(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "v35_research_system": True,
            "execution_model": EXECUTION_MODEL_V35,
            "requested_execution_model": EXECUTION_MODEL_V35,
            "agent_concurrency": 4,
        }
    )
    runner = V3FixtureRunner()

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=price_rows(),
        runner=runner,
        alaya_client=RecordingAlaya(),
    )

    payloads_by_agent = {
        str(payload["agent_id"]): payload
        for payload in runner.payloads
        if payload.get("required_schema") != RESEARCH_TASK_SCHEMA
    }
    assert exit_code == 0
    for agent_id in ("k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view"):
        payload = payloads_by_agent[agent_id]
        assert payload["research_task"]["schema"] == RESEARCH_TASK_SCHEMA
        assert payload["evidence_packet"]["schema"] == EVIDENCE_PACKET_SCHEMA
        assert payload["agent_brief"]
        assert payload["required_questions"]
        assert payload["must_not_conclude_without"]

    chairman = payloads_by_agent["chairman_synthesis"]
    red_team = payloads_by_agent["red_team_audit"]
    assert chairman["research_task"]["schema"] == RESEARCH_TASK_SCHEMA
    assert chairman["evidence_packet"]["schema"] == EVIDENCE_PACKET_SCHEMA
    assert set(chairman["dependencies"]) == {"k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view"}
    assert red_team["research_task"]["schema"] == RESEARCH_TASK_SCHEMA
    assert red_team["evidence_packet"]["schema"] == EVIDENCE_PACKET_SCHEMA
    assert "chairman_synthesis" in red_team["dependencies"]


def test_v35_requested_can_explicitly_fallback_to_v2() -> None:
    args = parse_args(["--mode", MODE, "--v35-research-system"])

    cfg = config_from_args(args)

    assert cfg.requested_execution_model == EXECUTION_MODEL_V35
    assert cfg.execution_model == EXECUTION_MODEL_V35
    assert cfg.v3_independent_agents is True
    assert cfg.v35_research_system is True

    fallback_args = parse_args(["--mode", MODE, "--v35-research-system", "--fallback-to-v2"])
    fallback_cfg = config_from_args(fallback_args)

    assert fallback_cfg.requested_execution_model == EXECUTION_MODEL_V35
    assert fallback_cfg.execution_model == EXECUTION_MODEL
    assert fallback_cfg.v3_independent_agents is False
    assert fallback_cfg.v35_research_system is False
    assert fallback_cfg.explicit_v2_fallback is True


def test_v40_fixture_run_builds_k_first_gates_and_alaya_hash_readback(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "v40_cognition_flywheel": True,
            "execution_model": EXECUTION_MODEL_V40,
            "requested_execution_model": EXECUTION_MODEL_V40,
            "agent_concurrency": 3,
            "alaya_mode": "real",
        }
    )
    state_path = cfg.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"
    runner = V3OrderingRunner()

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
    payloads_by_agent = {
        str(payload["agent_id"]): payload
        for payload in runner.payloads
        if payload.get("required_schema") not in {RESEARCH_TASK_SCHEMA, RESEARCH_TASK_SCHEMA_V2, K_DOSSIER_SCHEMA}
    }

    assert exit_code == 0
    assert runner.order_errors == []
    assert runner.calls[0] == "research_task_planner"
    assert runner.calls.index("k_deep_research_dossier") < runner.calls.index("f_partner_view")
    assert runner.calls.index("k_deep_research_dossier") < runner.calls.index("w_partner_view")
    assert runner.calls.index("k_deep_research_dossier") < runner.calls.index("g_partner_view")
    assert runner.calls.index("chairman_synthesis") > runner.calls.index("f_partner_view")
    assert runner.calls.index("red_team_audit") > runner.calls.index("chairman_synthesis")
    assert "k_deep_research" not in runner.calls

    assert status["run_status"] == "completed_with_review_items"
    assert status["prompt_template_version"] == PROMPT_TEMPLATE_VERSION_V40
    assert status["symbol_schema"] == SYMBOL_SCHEMA_V40
    assert status["market_data_snapshot_schema"] == MARKET_DATA_SNAPSHOT_SCHEMA
    assert status["research_task_schema"] == RESEARCH_TASK_SCHEMA_V2
    assert status["evidence_packet_schema"] == EVIDENCE_PACKET_SCHEMA_V2
    assert status["k_dossier_schema"] == K_DOSSIER_SCHEMA
    assert status["perspective_agent_schema"] == PERSPECTIVE_AGENT_SCHEMA_V4
    assert status["chairman_schema"] == CHAIRMAN_SCHEMA_V4
    assert status["red_team_schema"] == RED_TEAM_SCHEMA_V4
    assert status["research_quality_gate_schema"] == RESEARCH_QUALITY_GATE_SCHEMA
    assert status["knowledge_gate_schema"] == KNOWLEDGE_GATE_SCHEMA
    assert status["research_signal_schema"] == RESEARCH_SIGNAL_SCHEMA
    assert status["daily_reader_schema"] == "gotra.daily_reader_brief.v4"
    assert status["methodology_version"] == METHODOLOGY_VERSION_V40
    assert status["execution_model"] == EXECUTION_MODEL_V40
    assert status["agent_parallelism"] == 3
    assert status["agent_calls_total"] == 7
    assert status["publish_count"] == 0
    assert status["needs_review_count"] == 1
    assert status["blocked_count"] == 0
    assert status["failed_count"] == 0
    assert status["alaya_event_schema"] == ALAYA_EVENT_SCHEMA_V40
    assert status["alaya_sync_status"] == "ok"
    assert status["alaya_readback_status"] == "verified"

    assert symbol_payload["schema"] == SYMBOL_SCHEMA_V40
    assert symbol_payload["prompt_template_version"] == PROMPT_TEMPLATE_VERSION_V40
    assert symbol_payload["methodology_version"] == METHODOLOGY_VERSION_V40
    assert symbol_payload["execution_model"] == EXECUTION_MODEL_V40
    assert symbol_payload["market_data_snapshot"]["schema"] == MARKET_DATA_SNAPSHOT_SCHEMA
    assert symbol_payload["market_data_snapshot"]["provider"] == "yahoo_chart_api_via_gotra_price_cache"
    assert symbol_payload["market_data_snapshot"]["market"] == "Hong Kong public equity market"
    assert symbol_payload["market_data_snapshot"]["currency"] == "HKD"
    assert symbol_payload["market_data_snapshot"]["quality_flags"]
    assert symbol_payload["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot"]["snapshot_hash"]
    assert symbol_payload["research_task"]["schema"] == RESEARCH_TASK_SCHEMA_V2
    assert symbol_payload["evidence_packet"]["schema"] == EVIDENCE_PACKET_SCHEMA_V2
    validate_evidence_packet_contract(symbol_payload["evidence_packet"])
    assert symbol_payload["evidence_packet"]["packet_id"].endswith(":HKEX:0700:evidence_packet")
    assert symbol_payload["evidence_packet"]["as_of"] == cfg.as_of_date.isoformat()
    assert symbol_payload["evidence_packet"]["future_data_check"] is True
    assert isinstance(symbol_payload["evidence_packet"]["missing_items"], list)
    assert symbol_payload["evidence_packet"]["sources"]
    for source in symbol_payload["evidence_packet"]["sources"]:
        assert source["retrieved_at"]
        assert source["source_id"]
        assert source["source_type"]
        assert source["source_name"]
    invalid_packet = json.loads(json.dumps(symbol_payload["evidence_packet"]))
    del invalid_packet["sources"][0]["retrieved_at"]
    with pytest.raises(ValueError, match="evidence_packet_source_missing_retrieved_at"):
        validate_evidence_packet_contract(invalid_packet)
    assert symbol_payload["evidence_packet"]["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
    assert symbol_payload["evidence_packet"]["market_data_snapshot"]["snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
    assert any(item["evidence_id"] == "market_data_snapshot" for item in symbol_payload["evidence_packet"]["evidence_items"])
    assert symbol_payload["k_deep_research_dossier"]["schema"] == K_DOSSIER_SCHEMA
    assert symbol_payload["k_dossier_hash"] == symbol_payload["k_deep_research_dossier"]["dossier_hash"]
    assert symbol_payload["agent_hashes"]["k_deep_research"] == symbol_payload["k_dossier_hash"]
    assert symbol_payload["agent_outputs"]["f_partner_view"]["schema"] == PERSPECTIVE_AGENT_SCHEMA_V4
    assert symbol_payload["agent_outputs"]["w_partner_view"]["schema"] == PERSPECTIVE_AGENT_SCHEMA_V4
    assert symbol_payload["agent_outputs"]["g_partner_view"]["schema"] == PERSPECTIVE_AGENT_SCHEMA_V4
    assert symbol_payload["agent_outputs"]["chairman_synthesis"]["schema"] == CHAIRMAN_SCHEMA_V4
    assert symbol_payload["agent_outputs"]["red_team_audit"]["schema"] == RED_TEAM_SCHEMA_V4
    assert symbol_payload["agent_outputs"]["red_team_audit"]["red_team_role"] == "audit_not_judge"
    assert symbol_payload["research_quality_gate"]["schema"] == RESEARCH_QUALITY_GATE_SCHEMA
    assert symbol_payload["research_quality_gate"]["red_team_is_judge"] is False
    assert symbol_payload["research_quality_gate_hash"] == symbol_payload["research_quality_gate"]["gate_hash"]
    assert symbol_payload["knowledge_gate"]["schema"] == KNOWLEDGE_GATE_SCHEMA
    assert symbol_payload["knowledge_gate_hash"] == symbol_payload["knowledge_gate"]["gate_hash"]
    assert symbol_payload["knowledge_persistence"] == "persist_with_limitations"
    assert symbol_payload["reader_boundary_gate"]["does_not_hide_research_content"] is True
    assert symbol_payload["reader_boundary_gate"]["data_gap_visible"] is True
    assert symbol_payload["reader_boundary_gate"]["needs_review_visible"] is True
    assert symbol_payload["reader_boundary_gate"]["red_team_visible"] is True
    validate_research_signal_contract(symbol_payload["research_signal"])
    assert symbol_payload["research_signal"]["schema"] == RESEARCH_SIGNAL_SCHEMA
    assert symbol_payload["research_signal_hash"] == symbol_payload["research_signal"]["signal_hash"]
    assert symbol_payload["research_signal"]["evidence_packet_hash"] == symbol_payload["evidence_packet_hash"]
    assert symbol_payload["research_signal"]["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
    assert symbol_payload["research_signal"]["evidence_ids"]
    assert symbol_payload["research_signal"]["counter_evidence"]
    assert symbol_payload["research_signal"]["uncertainty"]
    assert symbol_payload["research_signal"]["window_days"] == 30
    assert symbol_payload["research_signal"]["review_due_at"] == "2026-07-29"
    validate_publication_decision_contract(symbol_payload["publication_decision"])
    assert symbol_payload["publication_decision"]["schema"] == PUBLICATION_DECISION_SCHEMA
    assert symbol_payload["publication_decision"]["signal_id"] == symbol_payload["research_signal"]["signal_id"]
    assert symbol_payload["publication_decision"]["research_signal_hash"] == symbol_payload["research_signal_hash"]
    assert symbol_payload["publication_decision"]["decision"] == "needs_review"
    assert symbol_payload["publication_decision"]["reader_safe_reasons"]
    assert symbol_payload["publication_decision_hash"] == symbol_payload["publication_decision"]["decision_hash"]
    assert symbol_payload["publication_decision_schema"] == PUBLICATION_DECISION_SCHEMA
    assert set(symbol_payload["agent_research_signals"]) == set(symbol_payload["agent_outputs"])
    assert set(symbol_payload["agent_research_signal_hashes"]) == set(symbol_payload["agent_outputs"])
    for agent_id, signal in symbol_payload["agent_research_signals"].items():
        validate_research_signal_contract(signal)
        assert signal["signal_hash"] == symbol_payload["agent_research_signal_hashes"][agent_id]
        assert signal["evidence_packet_hash"] == symbol_payload["evidence_packet_hash"]
        assert signal["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
    assert symbol_payload["parallelism"]["k_dossier_first"] is True
    assert symbol_payload["parallelism"]["fwg_ran_in_parallel"] is True
    assert symbol_payload["parallelism"]["kfwg_ran_in_parallel"] is False
    assert symbol_payload["judge_status"] == "needs_review"

    for agent_id in ("f_partner_view", "w_partner_view", "g_partner_view"):
        payload = payloads_by_agent[agent_id]
        assert payload["required_schema"] == PERSPECTIVE_AGENT_SCHEMA_V4
        assert payload["research_task"]["schema"] == RESEARCH_TASK_SCHEMA_V2
        assert payload["evidence_packet"]["schema"] == EVIDENCE_PACKET_SCHEMA_V2
        assert payload["evidence_packet"]["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
        assert payload["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
        assert payload["k_deep_research_dossier"]["schema"] == K_DOSSIER_SCHEMA
        assert payload["k_dossier_hash"] == symbol_payload["k_dossier_hash"]
        assert payload["agent_brief"]
        assert payload["must_not_conclude_without"]

    chairman = payloads_by_agent["chairman_synthesis"]
    red_team = payloads_by_agent["red_team_audit"]
    assert chairman["required_schema"] == CHAIRMAN_SCHEMA_V4
    assert set(chairman["dependencies"]) == {"k_deep_research", "f_partner_view", "w_partner_view", "g_partner_view"}
    assert chairman["k_dossier_hash"] == symbol_payload["k_dossier_hash"]
    assert red_team["required_schema"] == RED_TEAM_SCHEMA_V4
    assert "chairman_synthesis" in red_team["dependencies"]
    assert red_team["k_dossier_hash"] == symbol_payload["k_dossier_hash"]

    assert records[0]["event_schema"] == ALAYA_EVENT_SCHEMA_V40
    assert records[0]["cognition_flywheel_layer"] == METHODOLOGY_VERSION_V40
    assert records[0]["research_task_hash"] == symbol_payload["research_task_hash"]
    assert records[0]["evidence_packet_hash"] == symbol_payload["evidence_packet_hash"]
    assert records[0]["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
    assert records[0]["public_payload"]["market_data_snapshot_hash"] == symbol_payload["market_data_snapshot_hash"]
    assert records[0]["k_dossier_hash"] == symbol_payload["k_dossier_hash"]
    assert records[0]["agent_hashes"] == symbol_payload["agent_hashes"]
    assert records[0]["chairman_hash"] == symbol_payload["agent_hashes"]["chairman_synthesis"]
    assert records[0]["red_team_hash"] == symbol_payload["agent_hashes"]["red_team_audit"]
    assert records[0]["research_quality_gate_hash"] == symbol_payload["research_quality_gate_hash"]
    assert records[0]["knowledge_gate_hash"] == symbol_payload["knowledge_gate_hash"]
    assert records[0]["research_signal_hash"] == symbol_payload["research_signal_hash"]
    assert records[0]["public_payload"]["research_signal"]["signal_hash"] == symbol_payload["research_signal_hash"]
    assert records[0]["publication_decision_hash"] == symbol_payload["publication_decision_hash"]
    assert records[0]["public_payload"]["publication_decision"]["decision_hash"] == symbol_payload["publication_decision_hash"]
    assert records[0]["public_payload_hash"] == symbol_payload["public_payload_hash"]
    assert records[0]["knowledge_persistence"] == symbol_payload["knowledge_persistence"]
    assert records[0]["unresolved_questions"] == symbol_payload["unresolved_questions"]
    assert "readback_status" in records[0]


def test_v40_market_data_snapshot_future_data_risk_blocks_publication(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    cfg = FullAnalystConfig(
        **{
            **cfg.__dict__,
            "v3_independent_agents": True,
            "v40_cognition_flywheel": True,
            "execution_model": EXECUTION_MODEL_V40,
            "requested_execution_model": EXECUTION_MODEL_V40,
            "agent_concurrency": 3,
            "alaya_mode": "real",
        }
    )
    future_price_rows = price_rows()
    future_price_rows["HKEX:0700"] = {
        **future_price_rows["HKEX:0700"],
        "close_date": "2026-06-30",
        "adj_close": 100.0,
        "previous_date": "2026-06-29",
        "previous_adj_close": 99.0,
    }
    state_path = cfg.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"

    exit_code = run(
        cfg,
        universe_items=universe(),
        price_rows=future_price_rows,
        runner=V3OrderingRunner(),
        alaya_client=GotraInternalAlayaSyncClient(state_path=state_path, actor="test/full_analyst_pipeline"),
    )

    status = json.loads((cfg.output_dir / "status_full_analyst_evening_hk.json").read_text())
    symbol_payload = json.loads((cfg.output_dir / "symbols" / "HKEX_0700.json").read_text())

    assert exit_code == 2
    assert status["run_status"] == "completed_with_blockers"
    assert status["blocked_count"] == 1
    assert status["failed_count"] == 0
    assert symbol_payload["market_data_snapshot"]["future_data_risk"] is True
    assert symbol_payload["evidence_packet"]["future_data_check"] is False
    assert symbol_payload["evidence_packet"]["future_data_check_details"]["passed"] is False
    assert "future_data_risk" in symbol_payload["market_data_snapshot"]["quality_flags"]
    assert symbol_payload["judge_status"] == "blocked"
    assert "future_data_check" in " ".join(symbol_payload["judge_reasons"])
    validate_publication_decision_contract(symbol_payload["publication_decision"])
    assert symbol_payload["publication_decision"]["decision"] == "blocked"
    assert symbol_payload["publication_decision"]["blocker_type"] == "future_data"
    assert symbol_payload["publication_decision"]["gates"]["future_data_check"]["status"] == "blocked"
    assert symbol_payload["publication_decision_hash"] == symbol_payload["publication_decision"]["decision_hash"]


def valid_research_signal() -> dict[str, object]:
    return {
        "schema": RESEARCH_SIGNAL_SCHEMA,
        "signal_id": "run:HKEX:0700:symbol:research_signal",
        "run_id": "run",
        "symbol": "0700",
        "exchange": "HKEX",
        "provider_ticker": "0700.HK",
        "as_of_date": "2026-06-29",
        "source_id": "symbol",
        "hypothesis": "Research state remains bounded by verified public evidence and visible review items.",
        "confidence": "needs_review",
        "evidence_ids": ["market_data_snapshot"],
        "counter_evidence": ["Official issuer evidence remains incomplete."],
        "uncertainty": ["Source freshness limits confidence."],
        "window_days": 30,
        "review_due_at": "2026-07-29",
        "evidence_packet_id": "run:HKEX:0700:evidence_packet",
        "evidence_packet_hash": "evidence-hash",
        "market_data_snapshot_hash": "snapshot-hash",
        "market_data_snapshot_schema": MARKET_DATA_SNAPSHOT_SCHEMA,
        "research_status": "needs_review",
        "boundary": "research-only structured signal; not a trading instruction",
        "signal_hash": "signal-hash",
    }


def valid_publication_decision() -> dict[str, object]:
    return {
        "schema": PUBLICATION_DECISION_SCHEMA,
        "decision_id": "run:HKEX:0700:publication_decision",
        "run_id": "run",
        "symbol": "0700",
        "exchange": "HKEX",
        "as_of_date": "2026-06-29",
        "signal_id": "run:HKEX:0700:symbol:research_signal",
        "research_signal_hash": "signal-hash",
        "decision": "needs_review",
        "reader_safe_reasons": ["Research quality gate requires visible review items."],
        "blocker_type": "",
        "gates": {
            "public_safety_scan": {
                "gate": "public_safety_scan",
                "status": "pass",
                "reader_safe_reason": "public safety scan passed",
            },
            "secret_scan": {
                "gate": "secret_scan",
                "status": "pass",
                "reader_safe_reason": "no secret marker detected",
            },
            "forbidden_wording_scan": {
                "gate": "forbidden_wording_scan",
                "status": "pass",
                "reader_safe_reason": "no restricted wording detected",
            },
            "research_signal_contract": {
                "gate": "research_signal_contract",
                "status": "pass",
                "reader_safe_reason": "ResearchSignal contract passed",
            },
        },
        "publish_with_boundary": True,
        "evidence_layer": "local checks + smoke evidence",
        "boundary": "research-only publication decision; not an action instruction",
    }


def valid_published_symbol_payload() -> dict[str, object]:
    signal = valid_research_signal()
    decision = valid_publication_decision()
    decision["decision"] = "publish"
    decision["reader_safe_reasons"] = ["All publication gates passed with research-only boundary."]
    decision["publish_with_boundary"] = True
    decision["decision_hash"] = "decision-hash"
    return {
        "schema": SYMBOL_SCHEMA_V40,
        "run_id": "run",
        "symbol": "0700",
        "exchange": "HKEX",
        "provider_ticker": "0700.HK",
        "as_of_date": "2026-06-29",
        "methodology_version": METHODOLOGY_VERSION_V40,
        "execution_model": EXECUTION_MODEL_V40,
        "research_status": "candidate",
        "evidence_packet_hash": "evidence-hash",
        "research_signal": signal,
        "research_signal_hash": signal["signal_hash"],
        "publication_decision": decision,
        "publication_decision_hash": decision["decision_hash"],
        "evidence_packet": {
            "schema": EVIDENCE_PACKET_SCHEMA_V2,
            "packet_id": "run:HKEX:0700:evidence_packet",
            "evidence_packet_hash": "evidence-hash",
            "evidence_items": [
                {
                    "evidence_id": "market_data_snapshot",
                    "source_type": "price_data",
                    "public_safe": True,
                }
            ],
        },
    }


def test_ledger_entry_contract_and_hash_chain() -> None:
    entry = build_ledger_entry(
        valid_published_symbol_payload(),
        previous_hash="0" * 64,
        version=1,
        published_at="2026-06-29T10:00:00+00:00",
    )

    assert entry["schema"] == LEDGER_ENTRY_SCHEMA
    assert entry["entry_id"].endswith(":v1")
    assert entry["signal_id"] == "run:HKEX:0700:symbol:research_signal"
    assert entry["status"] == "publish"
    assert entry["previous_hash"] == "0" * 64
    validate_ledger_entry_contract(entry)
    assert verify_ledger_chain([entry])["ok"] is True


def test_research_ledger_update_appends_version_without_overwrite() -> None:
    payload = valid_published_symbol_payload()
    first = merge_research_ledger([], [payload], generated_at="2026-06-29T10:00:00+00:00")
    assert first["schema"] == LEDGER_MANIFEST_SCHEMA
    assert first["entry_count"] == 1
    assert first["appended_count"] == 1

    updated = valid_published_symbol_payload()
    updated["research_signal"] = {
        **updated["research_signal"],  # type: ignore[arg-type]
        "hypothesis": "Updated public research state remains bounded by the same evidence chain.",
        "signal_hash": "signal-hash-v2",
    }
    updated["research_signal_hash"] = "signal-hash-v2"
    updated["publication_decision"] = {
        **updated["publication_decision"],  # type: ignore[arg-type]
        "research_signal_hash": "signal-hash-v2",
        "decision_hash": "decision-hash-v2",
    }
    updated["publication_decision_hash"] = "decision-hash-v2"
    second = merge_research_ledger(first["entries"], [updated], generated_at="2026-06-29T11:00:00+00:00")

    assert second["entry_count"] == 2
    assert second["appended_count"] == 1
    assert second["entries"][0]["version"] == 1
    assert second["entries"][1]["version"] == 2
    assert second["entries"][1]["previous_hash"] == second["entries"][0]["hash"]
    assert second["entries"][1]["previous_version_hash"] == second["entries"][0]["hash"]
    assert second["integrity"]["ok"] is True


def test_research_ledger_adds_review_result_for_due_entry_with_public_prices() -> None:
    entry = build_ledger_entry(
        valid_published_symbol_payload(),
        previous_hash="0" * 64,
        version=1,
        published_at="2026-06-29T10:00:00+00:00",
    )
    entry["review_price_observation"] = {
        "start_price": 100,
        "end_price": 104,
        "benchmark_start_price": 200,
        "benchmark_end_price": 206,
        "price_source_id": "fixture_public_adjusted_close",
        "benchmark_source_id": "fixture_public_benchmark",
        "currency": "HKD",
        "quality_flags": ["fixture_public_price_observation"],
    }
    entry["hash"] = stable_hash({key: value for key, value in entry.items() if key != "hash"})

    manifest = merge_research_ledger([entry], [], generated_at="2026-07-30T10:00:00+00:00")

    assert manifest["review_coverage"]["total_count"] == 1
    assert manifest["review_coverage"]["reviewed_count"] == 1
    assert manifest["review_coverage"]["unavailable_count"] == 0
    result = manifest["review_results"][0]
    assert result["schema"] == REVIEW_RESULT_SCHEMA
    assert result["entry_id"] == entry["entry_id"]
    assert result["window_days"] == 30
    assert result["raw_return"] == 4.0
    assert result["benchmark_return"] == 3.0
    assert result["attribution"]["classification"] == "above_benchmark"
    validate_review_result_contract(result)


def test_research_ledger_due_entry_gets_unavailable_reason_without_public_prices() -> None:
    manifest = merge_research_ledger([], [valid_published_symbol_payload()], generated_at="2026-07-30T10:00:00+00:00")

    assert manifest["review_results"] == []
    assert manifest["review_coverage"]["due_count"] == 1
    assert manifest["review_coverage"]["unavailable_count"] == 1
    assert manifest["review_coverage"]["missing_due_entry_ids"] == []
    reason = manifest["review_unavailable"][0]
    assert reason["review_unavailable_reason"] == "public_review_price_or_benchmark_data_unavailable"
    assert reason["entry_id"] == manifest["entries"][0]["entry_id"]


def test_research_ledger_not_due_entry_is_not_silently_marked_failed() -> None:
    manifest = merge_research_ledger([], [valid_published_symbol_payload()], generated_at="2026-07-01T10:00:00+00:00")

    assert manifest["review_results"] == []
    assert manifest["review_unavailable"] == []
    assert manifest["review_coverage"]["not_due_count"] == 1
    assert manifest["review_coverage"]["reviewed_count"] == 0


def test_research_ledger_integrity_detects_tampering() -> None:
    payload = valid_published_symbol_payload()
    manifest = merge_research_ledger([], [payload], generated_at="2026-06-29T10:00:00+00:00")
    tampered = [dict(manifest["entries"][0])]
    tampered[0]["previous_hash"] = "1" * 64

    integrity = verify_ledger_chain(tampered)

    assert integrity["ok"] is False
    assert integrity["reason"] in {"ledger_entry_hash_mismatch", "ledger_previous_hash_mismatch"}


def test_load_existing_research_ledger_blocks_corrupt_chain(tmp_path: Path) -> None:
    payload = valid_published_symbol_payload()
    manifest = merge_research_ledger([], [payload], generated_at="2026-06-29T10:00:00+00:00")
    manifest["entries"][0]["previous_hash"] = "1" * 64
    ledger_path = tmp_path / "research_ledger.json"
    ledger_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="ledger_existing_integrity_failed"):
        load_existing_research_ledger(ledger_path)


def test_load_existing_research_ledger_blocks_invalid_json(tmp_path: Path) -> None:
    ledger_path = tmp_path / "research_ledger.json"
    ledger_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="ledger_existing_json_invalid"):
        load_existing_research_ledger(ledger_path)


def test_research_signal_contract_blocks_missing_required_field() -> None:
    signal = valid_research_signal()
    signal.pop("review_due_at")

    with pytest.raises(ValueError, match="research_signal_missing_required_fields"):
        validate_research_signal_contract(signal)


def test_research_signal_contract_blocks_empty_evidence() -> None:
    signal = valid_research_signal()
    signal["evidence_ids"] = []

    with pytest.raises(ValueError, match="research_signal_empty_evidence_ids"):
        validate_research_signal_contract(signal)


def test_research_signal_contract_blocks_compliance_wording() -> None:
    signal = valid_research_signal()
    signal["hypothesis"] = "\u5efa\u8bae\u4e70\u5165\u4e14\u5fc5\u6da8"

    with pytest.raises(ValueError, match="BLOCKED: 合规禁词"):
        validate_research_signal_contract(signal)


def test_publication_decision_contract_blocks_needs_review_without_reason() -> None:
    decision = valid_publication_decision()
    decision["reader_safe_reasons"] = []

    with pytest.raises(ValueError, match="publication_decision_missing_reader_safe_reasons"):
        validate_publication_decision_contract(decision)


def test_publication_decision_contract_blocks_blocked_without_type() -> None:
    decision = valid_publication_decision()
    decision["decision"] = "blocked"
    decision["reader_safe_reasons"] = ["A publication gate blocked the item."]
    decision["blocker_type"] = ""

    with pytest.raises(ValueError, match="publication_decision_missing_blocker_type"):
        validate_publication_decision_contract(decision)


def test_publication_decision_contract_blocks_publish_with_failed_gate() -> None:
    decision = valid_publication_decision()
    decision["decision"] = "publish"
    decision["reader_safe_reasons"] = ["All publication gates passed with research-only boundary."]
    decision["gates"]["forbidden_wording_scan"]["status"] = "blocked"  # type: ignore[index]
    decision["gates"]["forbidden_wording_scan"]["reader_safe_reason"] = "[BLOCKED: 合规禁词] wording gate failed"  # type: ignore[index]

    with pytest.raises(ValueError, match="publication_decision_publish_with_failed_gates"):
        validate_publication_decision_contract(decision)


def test_v40_requested_can_explicitly_fallback_to_v2() -> None:
    args = parse_args(["--mode", MODE, "--v40-cognition-flywheel"])

    cfg = config_from_args(args)

    assert cfg.requested_execution_model == EXECUTION_MODEL_V40
    assert cfg.execution_model == EXECUTION_MODEL_V40
    assert cfg.v3_independent_agents is True
    assert cfg.v40_cognition_flywheel is True

    fallback_args = parse_args(["--mode", MODE, "--v40-cognition-flywheel", "--fallback-to-v2"])
    fallback_cfg = config_from_args(fallback_args)

    assert fallback_cfg.requested_execution_model == EXECUTION_MODEL_V40
    assert fallback_cfg.execution_model == EXECUTION_MODEL
    assert fallback_cfg.v3_independent_agents is False
    assert fallback_cfg.v40_cognition_flywheel is False
    assert fallback_cfg.explicit_v2_fallback is True


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


def test_list_style_boundary_terms_do_not_trip_public_scanner() -> None:
    assert_public_safe(
        {
            "summary": (
                "Public safety: research content only; no investment advice, trading signal, "
                "directional recommendation, target price, allocation guidance, outcome promise, "
                "performance proof, or science/public proof."
            )
        }
    )



def test_full_analyst_code_does_not_use_external_alaya_env_names() -> None:
    forbidden_env_names = ["ALAYA" + "_BASE_URL", "ALAYA" + "_WRITE_PATH"]
    tracked = subprocess.run(
        ["git", "ls-files", "scripts", "gotra", "tests"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    source_suffixes = {".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}
    offenders: list[str] = []
    for rel in tracked:
        candidate = Path(rel)
        if candidate.suffix not in source_suffixes or not candidate.exists():
            continue
        source = candidate.read_text(errors="ignore")
        for name in forbidden_env_names:
            if name in source:
                offenders.append(f"{rel}:{name}")

    assert offenders == []

def test_source_completion_word_does_not_trip_raw_io_scanner() -> None:
    assert_public_safe({"summary": "Evidence completion remains incomplete because required public sources are missing."})


def test_completion_key_still_trips_raw_io_scanner() -> None:
    try:
        assert_public_safe({"completion": {"text": "raw provider field"}})
    except ValueError as exc:
        assert "forbidden_public_content_detected" in str(exc)
    else:
        raise AssertionError("raw completion key should remain blocked")


def test_red_team_absence_audit_terms_do_not_trip_public_scanner() -> None:
    assert_public_safe(
        {
            "summary": (
                "The red-team audit does not contain any direct buy recommendation, sell rating, "
                "hold signal, or target price. Price target language is absent and not found."
            )
        }
    )


def test_direct_target_price_claim_still_trips_public_scanner() -> None:
    try:
        assert_public_safe({"summary": "This clause contains a target price and must be retried."})
    except ValueError as exc:
        assert "forbidden_public_content_detected" in str(exc)
    else:
        raise AssertionError("direct target price wording should remain blocked")


def test_direct_buy_recommendation_still_trips_public_scanner() -> None:
    try:
        assert_public_safe({"summary": "This clause contains a buy recommendation."})
    except ValueError as exc:
        assert "forbidden_public_content_detected" in str(exc)
    else:
        raise AssertionError("direct buy recommendation wording should remain blocked")


def test_red_team_output_neutralizes_audited_forbidden_terms(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    output = sanitize_v3_agent_output(
        {
            "status": "needs_review",
            "findings": ["Target price language is absent; no buy recommendation is present."],
            "evidence_refs": ["price_context"],
            "evidence_gaps": ["Official source coverage is missing."],
            "uncertainties": ["Potential buy/sell/hold wording is not found in the synthesis."],
            "watch_conditions": ["Keep target price and sell rating language absent."],
            "final_red_team_verdict": "needs_review",
            "possible_hallucinations": ["A price target claim would be unsupported."],
            "overconfidence_risks": ["No position sizing should appear."],
        },
        agent_id="red_team_audit",
        item=universe()[0],
        config=cfg,
        input_context_hash="input-hash",
        started_at="2026-07-03T00:00:00Z",
        finished_at="2026-07-03T00:00:01Z",
        duration_seconds=1.0,
    )
    text = json.dumps(output, ensure_ascii=False).lower()
    assert "target price" not in text
    assert "price target" not in text
    assert "buy recommendation" not in text
    assert "sell rating" not in text
    assert "buy/sell/hold" not in text
    assert "position sizing" not in text
    assert "price-objective wording" in text
    assert "directional-action wording" in text
    assert "allocation-guidance wording" in text
    assert_public_safe(output)


def test_red_team_output_neutralizes_boundary_terms_outside_findings(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    output = sanitize_v3_agent_output(
        {
            "agent_role": "Red team checks target price, buy recommendation, and position sizing wording.",
            "status": "needs_review",
            "findings": ["No issuer conclusion can be promoted."],
            "evidence_refs": ["price_context"],
            "evidence_gaps": ["Official source coverage is missing."],
            "uncertainties": ["Boundary language must stay visible."],
            "watch_conditions": ["Keep the audit strict."],
            "final_red_team_verdict": "needs_review",
        },
        agent_id="red_team_audit",
        item=universe()[0],
        config=cfg,
        input_context_hash="input-hash",
        started_at="2026-07-03T00:00:00Z",
        finished_at="2026-07-03T00:00:01Z",
        duration_seconds=1.0,
    )

    text = json.dumps(output, ensure_ascii=False).lower()
    assert "target price" not in text
    assert "buy recommendation" not in text
    assert "position sizing" not in text
    assert "price-objective wording" in text
    assert "directional-action wording" in text
    assert "allocation-guidance wording" in text
    assert_public_safe(output)


def test_red_team_failure_record_keeps_public_safety_trigger_auditable(tmp_path: Path) -> None:
    cfg = config(tmp_path, symbols=("HKEX:0700",))
    output = v3_agent_failure_record(
        agent_id="red_team_audit",
        item=universe()[0],
        config=cfg,
        input_context_hash="input-hash",
        started_at="2026-07-03T00:00:00Z",
        finished_at="2026-07-03T00:00:01Z",
        duration_seconds=1.0,
        reason="forbidden_public_content_detected:target_price",
        retry_count=1,
        public_safety_triggers=["price_objective_wording"],
    )

    assert output["failure_reason"] == "forbidden_public_content_detected"
    assert output["retry_count"] == 1
    assert output["public_safety_triggers"] == ["price_objective_wording"]
    assert "target_price" not in json.dumps(output, ensure_ascii=False).lower()
    assert_public_safe(output)


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
