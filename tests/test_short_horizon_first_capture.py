from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import baseline_v3_6y_short_horizon_first_capture as canary
from scripts import baseline_v3_four_arm as v3


CAPTURE_TS = datetime(2026, 6, 21, 3, 0, tzinfo=UTC)


def test_short_horizon_mock_capture_writes_not_matured_artifact(
    tmp_path: Path,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _config(
        tmp_path,
        mode="mock",
        run_id="baseline_v3_6y_short_horizon_first_capture_mock_unit",
    )

    summary = canary.run_capture(config)
    artifact = _capture_artifact(tmp_path, config.run_id)

    assert summary["status"] == canary.STATUS_PASS
    assert summary["expected_capture_decisions"] == 1
    assert summary["actual_capture_artifacts"] == 1
    assert summary["future_outcome_status"] == "not_matured"
    assert summary["future_outcome_scoring_status"] == "NOT_MATURED"
    assert summary["horizon_days"] == 1
    assert summary["horizon_end_date"] == "2026-06-22"
    assert summary["outcome_price_available_after_utc"] == "2026-06-23T00:00:00Z"
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_30d_verdict_allowed"] is False
    assert summary["direct_llm_interpretation"] == (
        "direct_llm_parametric_memory_control"
    )
    assert summary["maturity_ledger_count"] == 1
    assert artifact["future_outcome_status"] == "not_matured"
    assert artifact["future_outcome_scoring_status"] == "NOT_MATURED"
    assert artifact["outcome_scoring_allowed_now"] is False
    assert artifact["horizon_days"] == 1
    assert artifact["horizon_end_date"] == "2026-06-22"
    assert artifact["backend"] == "local_mock"
    assert artifact["model"] == "gpt-5.5"
    assert artifact["reasoning"] == "high"
    assert artifact["prompt_hash"]
    assert artifact["output_transcript_path"] == ""
    assert artifact["parsed_decision_hash"] == ""
    assert artifact["arm_interpretation"] == "direct_llm_parametric_memory_control"
    _assert_no_outcome_or_verdict_fields(artifact)


def test_codex_cli_mode_requires_explicit_execute_backend(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _config(
        tmp_path,
        mode="codex-cli-capture",
        execute_backend=False,
        run_id="baseline_v3_6y_short_horizon_first_capture_not_run_unit",
    )

    summary = canary.run_capture(config)

    assert summary["status"] == canary.STATUS_NOT_RUN
    assert summary["actual_capture_artifacts"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["codex_cli_transcript_path_count"] == 0
    assert summary["parsed_decision_hash_count"] == 0
    assert "codex_cli_backend_requires_explicit_execute_backend" in summary[
        "blocker_reasons"
    ]


def test_codex_cli_fake_backend_records_required_metadata(
    tmp_path: Path,
    monkeypatch,
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
            self.codex_cli_version = "codex-cli 0.test"

        def complete(
            self,
            payload: dict[str, object],
            *,
            request_timeout_seconds: float | None = None,
        ) -> v3.ProviderDecision:
            del request_timeout_seconds
            decision = v3.MockDecisionClient(
                provider="local_mock",
                provider_model=self.provider_model,
                provider_base_url="local://mock",
            ).complete(payload)
            transcript_path = v3.codex_cli_transcript_path(self.run_root, payload)
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(
                json.dumps(v3.decision_to_cache_payload(decision)),
                encoding="utf-8",
            )
            return replace(
                decision,
                backend_name=v3.CODEX_CLI_BACKEND,
                codex_cli_version=self.codex_cli_version,
                codex_cli_model=self.provider_model,
                codex_cli_reasoning_setting=self.reasoning_setting,
                output_transcript_path=str(transcript_path),
                parsed_decision_hash=v3.stable_json_hash(
                    v3.decision_to_cache_payload(decision)
                ),
            )

    monkeypatch.setattr(v3, "CodexCliBackendDecisionClient", FakeCodexClient)
    config = _config(
        tmp_path,
        mode="codex-cli-capture",
        execute_backend=True,
        run_id="baseline_v3_6y_short_horizon_first_capture_fake_codex_unit",
    )

    summary = canary.run_capture(config)
    artifact = _capture_artifact(tmp_path, config.run_id)

    assert summary["status"] == canary.STATUS_PASS
    assert summary["provider_or_backend_called"] is True
    assert summary["codex_cli_called"] is True
    assert summary["codex_cli_version"] == "codex-cli 0.test"
    assert summary["codex_cli_version_count"] == 1
    assert summary["codex_cli_version_values"] == ["codex-cli 0.test"]
    assert summary["codex_cli_transcript_path_count"] == 1
    assert summary["parsed_decision_hash_count"] == 1
    assert artifact["backend"] == v3.CODEX_CLI_BACKEND
    assert artifact["codex_cli_version"] == "codex-cli 0.test"
    assert artifact["model"] == "gpt-5.5"
    assert artifact["reasoning"] == "high"
    assert artifact["output_transcript_path"]
    assert artifact["parsed_decision_hash"]
    assert Path(artifact["output_transcript_path"]).is_relative_to(
        tmp_path / "runs" / config.run_id
    )


def test_richer_input_layers_are_rejected_before_capture(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = replace(
        _config(
            tmp_path,
            mode="mock",
            run_id="baseline_v3_6y_short_horizon_first_capture_richer_blocked_unit",
        ),
        input_layers=("richer_research_packet",),
    )

    with pytest.raises(ValueError, match="only supports price_only_packet"):
        canary.run_capture(config)

    assert not (tmp_path / "runs" / config.run_id / "captures").exists()

    both_config = replace(
        config,
        run_id="baseline_v3_6y_short_horizon_first_capture_both_blocked_unit",
        input_layers=v3.INPUT_LAYERS,
    )
    with pytest.raises(ValueError, match="only supports price_only_packet"):
        canary.run_capture(both_config)


def test_full_gotra_arms_are_rejected_before_capture(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = replace(
        _config(
            tmp_path,
            mode="mock",
            run_id="baseline_v3_6y_short_horizon_first_capture_full_gotra_blocked_unit",
        ),
        arms=("full_gotra",),
    )

    with pytest.raises(ValueError, match="only supports direct_llm"):
        canary.run_capture(config)

    assert not (tmp_path / "runs" / config.run_id / "captures").exists()

    all_config = replace(
        config,
        run_id="baseline_v3_6y_short_horizon_first_capture_all_blocked_unit",
        arms=v3.ARMS,
    )
    with pytest.raises(ValueError, match="only supports direct_llm"):
        canary.run_capture(all_config)


def test_full_gotra_memory_refs_without_feedback_are_provenance_failure(
    tmp_path: Path,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _config(
        tmp_path,
        mode="mock",
        run_id="baseline_v3_6y_short_horizon_first_capture_memory_ref_unit",
    )
    visible_rows, _future_rows_excluded, _latest_visible = canary.visible_price_rows(
        "AAPL",
        decision_date_local=canary.local_capture_date(config),
        price_dir=config.price_dir,
    )
    payload = canary.build_prompt_payload(
        config=config,
        ticker="AAPL",
        arm="full_gotra",
        input_layer="price_only_packet",
        visible_rows=visible_rows,
    )
    decision = v3.MockDecisionClient(
        provider="local_mock",
        provider_model=config.provider_model,
        provider_base_url="local://mock",
    ).complete(payload)
    decision = replace(decision, arm="full_gotra", alaya_memory_refs=["invented-ref"])

    with pytest.raises(canary.ShortHorizonProvenanceError):
        canary.validate_visible_alaya_memory_refs(
            decision=decision,
            arm="full_gotra",
            visible_feedback_refs=set(),
        )


def test_backend_blocker_does_not_fabricate_capture(tmp_path: Path, monkeypatch) -> None:
    _write_prices(tmp_path / "prices", "AAPL")

    class BlockingCodexClient:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def complete(
            self,
            payload: dict[str, object],
            *,
            request_timeout_seconds: float | None = None,
        ) -> v3.ProviderDecision:
            del payload, request_timeout_seconds
            raise v3.ProviderRequestError(
                "codex unavailable",
                provider_error_class="CodexCliBackendBlocked",
            )

    monkeypatch.setattr(v3, "CodexCliBackendDecisionClient", BlockingCodexClient)
    config = _config(
        tmp_path,
        mode="codex-cli-capture",
        execute_backend=True,
        run_id="baseline_v3_6y_short_horizon_first_capture_backend_blocked_unit",
    )

    summary = canary.run_capture(config)

    assert summary["status"] == canary.STATUS_BLOCKED_BACKEND
    assert summary["actual_capture_artifacts"] == 0
    assert summary["capture_error_count"] == 1
    assert summary["provider_or_backend_called"] is True
    assert summary["codex_cli_called"] is True
    assert summary["codex_cli_transcript_path_count"] == 0
    assert summary["parsed_decision_hash_count"] == 0
    assert "backend_blocked" in summary["blocker_reasons"]


def test_schema_failure_is_not_reported_as_backend_blocker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")

    class WrongIdentityCodexClient:
        def __init__(self, **kwargs: object) -> None:
            self.provider_model = str(kwargs["model"])
            self.reasoning_setting = str(kwargs["reasoning_setting"])

        def complete(
            self,
            payload: dict[str, object],
            *,
            request_timeout_seconds: float | None = None,
        ) -> v3.ProviderDecision:
            del request_timeout_seconds
            decision = v3.MockDecisionClient(
                provider="local_mock",
                provider_model=self.provider_model,
                provider_base_url="local://mock",
            ).complete(payload)
            return replace(
                decision,
                ticker="MSFT",
                backend_name=v3.CODEX_CLI_BACKEND,
                codex_cli_version="codex-cli 0.test",
                codex_cli_model=self.provider_model,
                codex_cli_reasoning_setting=self.reasoning_setting,
            )

    monkeypatch.setattr(v3, "CodexCliBackendDecisionClient", WrongIdentityCodexClient)
    run_id = "baseline_v3_6y_short_horizon_first_capture_schema_fail_unit"

    exit_code = canary.main(
        [
            "--mode",
            "codex-cli-capture",
            "--execute-backend",
            "--run-id",
            run_id,
            "--output-dir",
            str(tmp_path / "runs"),
            "--price-dir",
            str(tmp_path / "prices"),
            "--capture-timestamp-utc",
            CAPTURE_TS.isoformat().replace("+00:00", "Z"),
        ]
    )
    summary = json.loads(
        (tmp_path / "runs" / run_id / "summary.json").read_text(encoding="utf-8")
    )

    assert exit_code == 1
    assert summary["status"] == canary.STATUS_SCHEMA_FAIL
    assert summary["status"] != canary.STATUS_BLOCKED_BACKEND
    assert "capture_schema_failed" in summary["blocker_reasons"]
    assert summary["capture_errors"][0]["error_type"] == "ValueError"


def test_existing_run_id_blocks_without_overwrite(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    run_id = "baseline_v3_6y_short_horizon_first_capture_collision_unit"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")
    config = _config(tmp_path, mode="mock", run_id=run_id)

    summary = canary.run_capture(config)

    assert summary["status"] == canary.STATUS_BLOCKED_RUN_ID_EXISTS
    assert summary["actual_capture_artifacts"] == 0
    assert summary["provider_or_backend_called"] is False
    assert (run_root / "sentinel.txt").read_text(encoding="utf-8") == "exists"


def test_source_decision_id_changes_with_prompt_hash() -> None:
    base_kwargs = {
        "run_id": "baseline_v3_6y_short_horizon_first_capture_source_id_unit",
        "ticker": "AAPL",
        "arm": "direct_llm",
        "input_layer": "price_only_packet",
        "decision_date_local": date(2026, 6, 21),
        "horizon_days": 1,
    }

    first = canary.source_decision_id(**base_kwargs, prompt_hash="prompt-a")
    second = canary.source_decision_id(**base_kwargs, prompt_hash="prompt-b")

    assert first != second


def _price_rows(days: int = 80) -> pd.DataFrame:
    start = date(2026, 4, 1)
    rows = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        rows.append(
            {
                "date": current.isoformat(),
                "ticker": "AAPL",
                "adj_close": 100 + offset,
                "source_url": "fixture",
                "evidence_unverified": False,
            }
        )
    return pd.DataFrame(rows)


def _write_prices(price_dir: Path, ticker: str) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    _price_rows().assign(ticker=ticker).to_csv(price_dir / f"{ticker}.csv", index=False)


def _config(
    tmp_path: Path,
    *,
    mode: canary.Mode,
    run_id: str,
    execute_backend: bool = False,
) -> canary.CanaryConfig:
    return canary.CanaryConfig(
        mode=mode,
        execute_backend=execute_backend,
        run_id=run_id,
        output_dir=tmp_path / "runs",
        tickers=("AAPL",),
        horizon_days=1,
        arms=("direct_llm",),
        input_layers=("price_only_packet",),
        capture_timestamp_utc=CAPTURE_TS,
        timezone="Asia/Shanghai",
        price_dir=tmp_path / "prices",
        provider_model="gpt-5.5",
        provider_max_tokens=2000,
        codex_cli_reasoning_setting="high",
        codex_cli_binary="codex",
        backend_concurrency=1,
        request_timeout_seconds=30.0,
    )


def _capture_artifact(tmp_path: Path, run_id: str) -> dict[str, object]:
    return json.loads(
        (
            tmp_path
            / "runs"
            / run_id
            / "captures"
            / "direct_llm"
            / "capture_2026-06-21_aapl_h1_price_only_packet.json"
        ).read_text(encoding="utf-8")
    )


def _assert_no_outcome_or_verdict_fields(payload: dict[str, object]) -> None:
    forbidden = canary.FORBIDDEN_OUTCOME_FIELDS
    assert not (forbidden & set(payload))
    decision = payload.get("decision")
    assert isinstance(decision, dict)
    assert not (forbidden & set(decision))
