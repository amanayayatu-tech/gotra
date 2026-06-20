from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from scripts import baseline_v3_5_forward_live_capture as capture
from scripts import baseline_v3_four_arm as v3


CAPTURE_TS = datetime.fromisoformat("2026-06-20T02:00:00+00:00")


def test_mock_capture_writes_not_matured_artifacts_and_summary(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _capture_config(
        tmp_path,
        mode="mock",
        run_id="baseline_v3_5a_forward_live_mock_unit",
        tickers=("AAPL",),
        arms=("direct_llm", "full_gotra"),
        input_layers=("price_only_packet", "richer_research_packet"),
    )

    summary = capture.run_capture(config)
    run_root = tmp_path / "runs" / config.run_id
    artifact = json.loads(
        (
            run_root
            / "captures"
            / "direct_llm"
            / "capture_2026-06-20_aapl_price_only_packet.json"
        ).read_text(encoding="utf-8")
    )

    assert summary["status"] == "FORWARD_LIVE_CAPTURE_PASS"
    assert summary["expected_capture_decisions"] == 4
    assert summary["actual_capture_artifacts"] == 4
    assert summary["future_outcome_status"] == "not_matured"
    assert summary["future_outcome_scoring_status"] == "NOT_MATURED"
    assert summary["outcome_matured_count"] == 0
    assert summary["outcome_scored_count"] == 0
    assert summary["codex_cli_transcript_path_count"] == 0
    assert summary["parsed_decision_hash_count"] == 0
    assert summary["deterministic_price_only_reference_count"] == 1
    assert summary["deterministic_price_only_reference_provider_or_backend_called"] is False
    assert summary["clean_historical_reference_status"] == (
        "PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE"
    )
    assert summary["arm_interpretation"]["direct_llm"].startswith(
        "direct_llm_parametric_memory_control"
    )
    assert artifact["future_outcome_status"] == "not_matured"
    assert artifact["future_outcome_scoring_status"] == "NOT_MATURED"
    assert artifact["decision_timestamp_utc"] == "2026-06-20T02:00:00Z"
    assert artifact["decision_date_local"] == "2026-06-20"
    assert artifact["horizon_end_date"] == "2026-07-20"
    assert artifact["backend"] == "local_mock"
    assert artifact["output_transcript_path"] == ""
    assert artifact["parsed_decision_hash"] == ""
    assert artifact["future_rows_excluded"] > 0
    _assert_no_outcome_fields(artifact)


def test_codex_cli_capture_fake_client_records_backend_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")

    class FakeCodexClient:
        def __init__(
            self,
            *,
            model: str,
            reasoning_setting: str,
            run_root: Path,
            provider_max_tokens: int,
            codex_binary: str = "codex",
            project_root: Path | None = None,
        ) -> None:
            del provider_max_tokens, codex_binary, project_root
            self.provider_model = model
            self.reasoning_setting = reasoning_setting
            self.run_root = run_root

        def complete(
            self,
            payload: dict[str, object],
            *,
            request_timeout_seconds: float | None = None,
        ) -> v3.ProviderDecision:
            del request_timeout_seconds
            decision_payload = _decision_payload(
                arm=v3.normalize_arm(str(payload["arm"])),
                ticker=str(payload["ticker"]),
                decision_date=str(payload["decision_date"]),
            )
            raw = json.dumps(decision_payload)
            transcript_path = v3.codex_cli_transcript_path(self.run_root, payload)
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(raw, encoding="utf-8")
            decision = v3.parse_provider_decision(raw)
            return replace(
                decision,
                backend_name=v3.CODEX_CLI_BACKEND,
                codex_cli_version="codex-cli 0.test",
                codex_cli_model=self.provider_model,
                codex_cli_reasoning_setting=self.reasoning_setting,
                output_transcript_path=str(transcript_path),
                parsed_decision_hash=v3.stable_json_hash(
                    v3.decision_to_cache_payload(decision)
                ),
            )

    monkeypatch.setattr(v3, "CodexCliBackendDecisionClient", FakeCodexClient)
    config = _capture_config(
        tmp_path,
        mode="codex-cli-capture",
        run_id="baseline_v3_5a_forward_live_codex_fake_unit",
        tickers=("AAPL",),
        arms=("direct_llm",),
        input_layers=("price_only_packet",),
    )

    summary = capture.run_capture(config)
    run_root = tmp_path / "runs" / config.run_id
    artifact = json.loads(
        (
            run_root
            / "captures"
            / "direct_llm"
            / "capture_2026-06-20_aapl_price_only_packet.json"
        ).read_text(encoding="utf-8")
    )

    assert summary["status"] == "FORWARD_LIVE_CAPTURE_PASS"
    assert summary["backend"] == v3.CODEX_CLI_BACKEND
    assert summary["codex_cli_version"] == "codex-cli 0.test"
    assert summary["codex_cli_transcript_path_count"] == 1
    assert summary["parsed_decision_hash_count"] == 1
    assert artifact["backend"] == v3.CODEX_CLI_BACKEND
    assert artifact["codex_cli_version"] == "codex-cli 0.test"
    assert artifact["model"] == "gpt-5.1"
    assert artifact["reasoning"] == "low"
    assert artifact["prompt_hash"]
    assert artifact["parsed_decision_hash"]
    assert Path(artifact["output_transcript_path"]).is_relative_to(run_root)
    _assert_no_outcome_fields(artifact)


def test_capture_rejects_research_source_after_capture_timestamp(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    research_path = tmp_path / "research.json"
    research_path.write_text(
        json.dumps(
            {
                "artifacts": [
                    _research_artifact(
                        evidence_ref="accepted_before_capture",
                        publish_timestamp="2026-06-19T02:00:00Z",
                        availability_date="2026-06-19",
                    ),
                    _research_artifact(
                        evidence_ref="captured_after_capture",
                        publish_timestamp="2026-06-20T08:00:00Z",
                        availability_date="2026-06-20",
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )
    config = _capture_config(
        tmp_path,
        mode="mock",
        run_id="baseline_v3_5a_forward_live_research_gate_unit",
        tickers=("AAPL",),
        arms=("ksana_real_research",),
        input_layers=("richer_research_packet",),
        research_artifacts_path=research_path,
    )

    summary = capture.run_capture(config)
    artifact = json.loads(
        (
            tmp_path
            / "runs"
            / config.run_id
            / "captures"
            / "ksana_real_research"
            / "capture_2026-06-20_aapl_richer_research_packet.json"
        ).read_text(encoding="utf-8")
    )

    assert summary["status"] == "FORWARD_LIVE_CAPTURE_PASS"
    assert summary["research_future_data_rejected_count"] == 1
    assert summary["research_source_timestamp_rejected_count"] == 1
    assert artifact["research_artifact_count"] == 1
    assert artifact["rejected_research_source_timestamp_count"] == 1


def test_deterministic_capture_reference_does_not_call_backend(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _capture_config(
        tmp_path,
        mode="mock",
        run_id="baseline_v3_5a_forward_live_reference_unit",
        tickers=("AAPL",),
    )
    visible_rows, future_rows_excluded = capture.visible_price_rows(
        "AAPL",
        decision_date_local=capture.local_capture_date(config),
        price_dir=tmp_path / "prices",
    )

    reference = capture.deterministic_capture_reference_for_ticker(
        config=config,
        ticker="AAPL",
        visible_rows=visible_rows,
        future_rows_excluded=future_rows_excluded,
    )

    assert reference["future_outcome_status"] == "not_matured"
    assert reference["future_outcome_scoring_status"] == "NOT_MATURED"
    assert reference["llm_used"] is False
    assert reference["provider_or_backend_called"] is False
    assert reference["future_rows_excluded"] > 0
    assert "actual_change_pct" not in reference
    assert "actual_return" not in reference


def test_capture_blocks_existing_run_id_with_not_matured_summary(tmp_path: Path) -> None:
    run_id = "baseline_v3_5a_forward_live_blocked_unit"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")
    config = _capture_config(tmp_path, mode="mock", run_id=run_id, tickers=("AAPL",))

    summary = capture.run_capture(config)

    assert summary["status"] == "BLOCKED_RUN_ID_EXISTS"
    assert summary["future_outcome_status"] == "not_matured"
    assert summary["future_outcome_scoring_status"] == "NOT_MATURED"
    assert summary["actual_capture_artifacts"] == 0
    assert summary["codex_cli_transcript_path_count"] == 0
    assert summary["deterministic_price_only_reference"]["provider_or_backend_called"] is False


def _price_rows(days: int = 620) -> pd.DataFrame:
    start = date(2025, 1, 1)
    rows = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        rows.append(
            {
                "date": current.isoformat(),
                "ticker": "AAPL",
                "adj_close": 100 + offset * 0.1,
                "source_url": "fixture",
                "evidence_unverified": False,
            }
        )
    return pd.DataFrame(rows)


def _write_prices(price_dir: Path, ticker: str, *, days: int = 620) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    _price_rows(days=days).assign(ticker=ticker).to_csv(price_dir / f"{ticker}.csv", index=False)


def _capture_config(
    root: Path,
    *,
    mode: capture.Mode,
    run_id: str,
    tickers: tuple[str, ...],
    arms: tuple[v3.Arm, ...] = ("direct_llm",),
    input_layers: tuple[v3.InputLayer, ...] = ("price_only_packet",),
    research_artifacts_path: Path | None = None,
) -> capture.CaptureConfig:
    return capture.CaptureConfig(
        mode=mode,
        run_id=run_id,
        tickers=tickers,
        arms=arms,
        input_layers=input_layers,
        capture_timestamp_utc=CAPTURE_TS,
        timezone="Asia/Shanghai",
        horizon_days=30,
        runs_root=root / "runs",
        price_dir=root / "prices",
        provider_model="gpt-5.1",
        provider_max_tokens=2000,
        codex_cli_reasoning_setting="low",
        codex_cli_binary="codex",
        backend_concurrency=1,
        request_timeout_seconds=30.0,
        research_artifacts_path=research_artifacts_path,
        feedback_artifacts_path=None,
    )


def _decision_payload(*, arm: v3.Arm, ticker: str, decision_date: str) -> dict[str, object]:
    return {
        "schema": v3.DECISION_SCHEMA,
        "arm": arm,
        "ticker": ticker,
        "decision_date": decision_date,
        "horizon_days": 30,
        "direction": "long",
        "expected_change_pct": 1.2,
        "confidence": 0.61,
        "reasoning": "fixture decision",
        "evidence_refs": ["price_features"],
        "ksana_refs": [] if arm == "direct_llm" else ["ksana_workflow"],
        "alaya_memory_refs": [],
        "risk_factors": ["fixture uncertainty"],
        "abstain_reason": None,
        "input_cutoff": decision_date,
        "future_data_allowed": False,
    }


def _research_artifact(
    *,
    evidence_ref: str,
    publish_timestamp: str,
    availability_date: str,
) -> dict[str, object]:
    return {
        "ticker": "AAPL",
        "source_name": "fixture",
        "source_url_or_id": f"fixture://{evidence_ref}",
        "publish_timestamp": publish_timestamp,
        "availability_date": availability_date,
        "source_kind": "unverified",
        "retrieval_method": "fixture",
        "evidence_ref": evidence_ref,
        "summary": "time bounded fixture research",
    }


def _assert_no_outcome_fields(artifact: dict[str, object]) -> None:
    assert not (capture.FORBIDDEN_OUTCOME_FIELDS & set(artifact))
    decision = artifact.get("decision")
    assert isinstance(decision, dict)
    assert not (capture.FORBIDDEN_OUTCOME_FIELDS & set(decision))
