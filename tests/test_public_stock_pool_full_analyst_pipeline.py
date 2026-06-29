import json
from datetime import date
from pathlib import Path

from scripts.public_stock_pool_full_research import RunnerResult
from scripts.public_stock_pool_full_analyst_pipeline import (
    BOUNDARY_LINES,
    LOOP_MODE,
    LOOP_SMOKE_MODE,
    MODE,
    FullAnalystConfig,
    GotraInternalAlayaSyncClient,
    MockAlayaSyncClient,
    assert_public_safe,
    run,
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
    assert status["alaya_synced_count"] == 2
    assert status["provider_model_io_embedded"] is False
    assert "local checks + one-shot runtime smoke" in status["evidence_layer"]
    assert (cfg.private_audit_root / cfg.run_id / "heartbeat.json").exists()
    assert (cfg.private_audit_root / cfg.run_id / "events.jsonl").exists()
    assert (cfg.private_audit_root / cfg.run_id / "cycle_001_summary.json").exists()


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
    assert records[0]["cognition_flywheel_layer"] == "full_analyst_public_research"
    assert records[0]["event_hash"] == event_meta["event_hash"]


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
            "summary": "This is not a buy recommendation and no target price is provided.",
            "boundary": list(BOUNDARY_LINES),
        }
    )


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
