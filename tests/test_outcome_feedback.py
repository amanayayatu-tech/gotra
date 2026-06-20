from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from gotra.judge_agent.outcome_feedback import (
    PRODUCER_SCHEMA_VERSION,
    generate_outcome_feedback_artifacts,
    stable_feedback_ref,
    write_feedback_artifacts_jsonl,
)
from scripts import baseline_v3_four_arm as v3


GENERATED_AT = datetime(2026, 6, 20, 9, 0, tzinfo=UTC)


def test_resolved_predictions_generate_v3_accepted_outcome_feedback() -> None:
    result = generate_outcome_feedback_artifacts(_eligible_predictions(), generated_at=GENERATED_AT)

    assert result.diagnostics["generated_artifact_count"] == 3
    assert result.diagnostics["rejected_prediction_count"] == 0
    assert {artifact["feedback_source_kind"] for artifact in result.artifacts} == {
        "outcome_feedback",
        "realized_error_feedback",
    }
    for artifact in result.artifacts:
        assert artifact["producer_schema_version"] == PRODUCER_SCHEMA_VERSION
        assert artifact["source_prediction_id"]
        assert artifact["judge_decision_hash"]
        assert artifact["generated_at_utc"] == "2026-06-20T09:00:00Z"
        assert len(artifact["provenance_hash"]) == 64
        assert not (v3.FORBIDDEN_FEEDBACK_ARTIFACT_FIELDS & set(artifact))

    filtered = v3.filter_external_feedback_artifacts(
        list(result.artifacts),
        decision_date=date(2024, 4, 2),
        ticker="AAPL",
        input_layer="richer_research_packet",
        current_run_id="current_run",
    )
    diagnostics = v3.strict_feedback_diagnostics(
        feedback=filtered["accepted_feedback"],
        decision_date=date(2024, 4, 2),
    )

    assert len(filtered["accepted_feedback"]) == 3
    assert diagnostics["true_independent_feedback_eligible"] is True
    assert diagnostics["true_independent_feedback_count"] == 3
    assert diagnostics["true_independent_feedback_prior_wave_count"] == 3


def test_generation_rejects_unresolved_missing_nonfinite_inconsistent_and_future_rows() -> None:
    rows = [
        _prediction("pending", status="open"),
        {**_prediction("missing-ticker"), "ticker": ""},
        {**_prediction("nonfinite"), "actual_return": "NaN"},
        {**_prediction("bad-mse"), "mse": 0.0},
        {**_prediction("bad-order"), "availability_date": "2024-01-15"},
        {**_prediction("forbidden"), "future_return": 0.5},
        {**_prediction("current-run"), "run_id": "current_run"},
    ]

    result = generate_outcome_feedback_artifacts(
        rows,
        current_run_id="current_run",
        generated_at=GENERATED_AT,
    )

    assert result.artifacts == ()
    assert result.diagnostics["rejected_unresolved_count"] == 1
    assert result.diagnostics["rejected_schema_count"] == 1
    assert result.diagnostics["rejected_nonfinite_count"] == 1
    assert result.diagnostics["rejected_inconsistent_numeric_count"] == 1
    assert result.diagnostics["rejected_future_data_count"] == 2
    assert result.diagnostics["rejected_current_run_count"] == 1


def test_dedup_and_provenance_hash_are_stable() -> None:
    rows = [_prediction("dup"), _prediction("dup")]

    first = generate_outcome_feedback_artifacts(rows, generated_at=GENERATED_AT)
    second = generate_outcome_feedback_artifacts([_prediction("dup")], generated_at=GENERATED_AT)

    assert len(first.artifacts) == 1
    assert first.diagnostics["rejected_duplicate_count"] == 1
    assert first.artifacts[0]["feedback_ref"] == stable_feedback_ref(
        ticker="AAPL",
        input_layer="*",
        source_decision_date=date(2024, 1, 2),
        prediction_id="dup",
    )
    assert first.artifacts[0]["provenance_hash"] == second.artifacts[0]["provenance_hash"]


def test_jsonl_writer_is_append_only_and_v3_loader_can_read_it(tmp_path: Path) -> None:
    first = generate_outcome_feedback_artifacts([_prediction("one")], generated_at=GENERATED_AT)
    second = generate_outcome_feedback_artifacts([_prediction("two")], generated_at=GENERATED_AT)
    path = tmp_path / "feedback.jsonl"

    write_feedback_artifacts_jsonl(path, first.artifacts)
    write_feedback_artifacts_jsonl(path, second.artifacts)

    loaded = v3.load_feedback_artifact_fixture(path)
    assert [item["source_prediction_id"] for item in loaded] == ["one", "two"]
    with pytest.raises(FileExistsError):
        write_feedback_artifacts_jsonl(path, second.artifacts, append=False)


def test_current_run_and_same_date_rows_do_not_count_as_true_independent() -> None:
    current_artifact = generate_outcome_feedback_artifacts(
        [_prediction("current-source", run_id="current_run")],
        generated_at=GENERATED_AT,
    ).artifacts[0]
    same_date_artifact = generate_outcome_feedback_artifacts(
        [
            _prediction(
                "same-date",
                source_decision_date="2024-04-02",
                source_horizon_end_date="2024-05-02",
                availability_date="2024-05-03",
            )
        ],
        generated_at=GENERATED_AT,
    ).artifacts[0]

    filtered = v3.filter_external_feedback_artifacts(
        [current_artifact, same_date_artifact],
        decision_date=date(2024, 4, 2),
        ticker="AAPL",
        input_layer="price_only_packet",
        current_run_id="current_run",
    )

    assert filtered["accepted_feedback"] == []
    assert filtered["rejected_feedback_current_run_count"] == 1
    assert filtered["rejected_feedback_future_data_count"] == 1


def test_closed_loop_mock_run_consumes_generated_outcome_feedback(tmp_path: Path) -> None:
    run_id = "baseline_v3_2_v3_3b_closed_loop_mock"
    for ticker in ("AAPL", "MSFT", "NVDA"):
        _write_prices(tmp_path / "prices", ticker, days=620)
    generated = generate_outcome_feedback_artifacts(
        _eligible_predictions(),
        current_run_id=run_id,
        generated_at=GENERATED_AT,
    )
    feedback_path = tmp_path / "generated_feedback.jsonl"
    write_feedback_artifacts_jsonl(feedback_path, generated.artifacts)
    config = _config(
        tmp_path,
        run_id=run_id,
        tickers=("AAPL", "MSFT", "NVDA"),
        dates=(
            date(2024, 1, 2),
            date(2024, 2, 1),
            date(2024, 3, 1),
            date(2024, 4, 2),
            date(2024, 5, 2),
            date(2024, 6, 3),
        ),
    )
    config = replace(
        config,
        warm_up_dates=2,
        research_artifacts_path=Path("tests/fixtures/baseline_v3_1_research_artifacts.json"),
        feedback_artifacts_path=feedback_path,
    )

    summary = v3.run_four_arm(config)
    later_step = json.loads(
        (
            tmp_path
            / "runs"
            / run_id
            / "full_gotra"
            / "step_2024-04-02_aapl_richer_research_packet.json"
        ).read_text(encoding="utf-8")
    )

    assert summary["status"] == "MOCK_PASS"
    assert summary["provider_call_status"] == "no real provider HTTP call"
    assert summary["true_independent_feedback_eligible_points"] > 0
    assert summary["h2_data_status"] == "STRICT_FEEDBACK_ELIGIBLE_PRESENT"
    assert summary["feedback_source_leak_count"] == 0
    assert later_step["true_independent_feedback_eligible"] is True
    assert {
        item["source_step_id"].rsplit("/", 1)[-1]
        for item in later_step["alaya_feedback_history"]
        if str(item.get("feedback_source_kind")) in {"outcome_feedback", "realized_error_feedback"}
    } == {"pred-wave-1", "pred-wave-2", "pred-wave-3"}


def _eligible_predictions() -> list[dict[str, object]]:
    return [
        _prediction(
            "pred-wave-1",
            source_decision_date="2024-01-02",
            source_horizon_end_date="2024-02-01",
            availability_date="2024-02-02",
            actual_return=0.012,
            prior_prediction=0.008,
            source_kind="outcome_feedback",
        ),
        _prediction(
            "pred-wave-2",
            source_decision_date="2024-02-01",
            source_horizon_end_date="2024-03-02",
            availability_date="2024-03-04",
            actual_return=-0.004,
            prior_prediction=0.006,
            source_kind="realized_error_feedback",
        ),
        _prediction(
            "pred-wave-3",
            source_decision_date="2024-03-01",
            source_horizon_end_date="2024-03-31",
            availability_date="2024-04-01",
            actual_return=0.021,
            prior_prediction=0.014,
            source_kind="outcome_feedback",
        ),
    ]


def _prediction(
    prediction_id: str,
    *,
    status: str = "resolved",
    ticker: str = "AAPL",
    input_layer: str = "*",
    run_id: str = "prior_run_v3_3b",
    source_decision_date: str = "2024-01-02",
    source_horizon_end_date: str = "2024-02-01",
    availability_date: str = "2024-02-02",
    actual_return: object = 0.012,
    prior_prediction: object = 0.008,
    source_kind: str = "outcome_feedback",
) -> dict[str, object]:
    error = float(actual_return) - float(prior_prediction) if _is_floaty(actual_return, prior_prediction) else 0.0
    return {
        "id": prediction_id,
        "status": status,
        "ticker": ticker,
        "input_layer": input_layer,
        "run_id": run_id,
        "source_step_id": f"{run_id}/full_gotra/{prediction_id}",
        "decision_date": source_decision_date,
        "source_horizon_end_date": source_horizon_end_date,
        "availability_date": availability_date,
        "actual_return": actual_return,
        "prior_prediction": prior_prediction,
        "error": error,
        "mse": error * error,
        "feedback_source_kind": source_kind,
        "source_gate_id": f"gate-{prediction_id}",
        "source_knowledge_id": f"kb-{prediction_id}",
        "judge_provenance_ref": f"judge:{prediction_id}",
        "judge_decision_hash": f"hash-{prediction_id}",
        "summary": f"Resolved prediction feedback {prediction_id}.",
    }


def _is_floaty(*values: object) -> bool:
    try:
        for value in values:
            float(value)
    except (TypeError, ValueError):
        return False
    return True


def _price_rows(days: int = 220) -> pd.DataFrame:
    start = date(2023, 1, 1)
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


def _write_prices(price_dir: Path, ticker: str, *, days: int = 500) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    _price_rows(days=days).assign(ticker=ticker).to_csv(price_dir / f"{ticker}.csv", index=False)


def _config(
    root: Path,
    *,
    run_id: str,
    tickers: tuple[str, ...],
    dates: tuple[date, ...],
) -> v3.RunConfig:
    return v3.RunConfig(
        mode="mock",
        run_id=run_id,
        provider="glm_sophnet",
        provider_model="GLM-5.2",
        provider_base_url=v3.DEFAULT_GLM_BASE_URL,
        tickers=tickers,
        dates=dates,
        input_layers=v3.INPUT_LAYERS,
        warm_up_dates=1,
        repeat_run_index=0,
        runs_root=root / "runs",
        price_dir=root / "prices",
        token_budget=500_000_000,
        provider_concurrency=1,
        max_provider_concurrency=1,
        adaptive_concurrency=True,
        direct_llm_timeout_seconds=300.0,
        ksana_formatting_only_timeout_seconds=420.0,
        ksana_real_research_timeout_seconds=480.0,
        full_gotra_timeout_seconds=540.0,
        timeout_per_kb_seconds=20.0,
        max_request_timeout_seconds=720.0,
        timeout_retries=1,
        timeout_retry_backoff_seconds=0.0,
        scheduler_policy="per_date_feedback_snapshot_interleaved_point_layer_arm_v3",
    )
