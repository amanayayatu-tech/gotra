from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd
import pytest

from gotra.backtest.statistics import cluster_bootstrap_ci, paired_loss_differences_v3
from scripts import baseline_v3_four_arm as v3


def test_four_arm_payload_boundaries_and_input_layers() -> None:
    price_rows = _price_rows()
    feedback = [
        {
            "decision_date": "2024-01-02",
            "outcome_availability_date": "2024-02-01",
            "error": 2.0,
        }
    ]

    direct = v3.build_prompt_payload(
        arm="direct_llm",
        input_layer="richer_research_packet",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )
    formatting = v3.build_prompt_payload(
        arm="ksana_formatting_only",
        input_layer="richer_research_packet",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )
    real = v3.build_prompt_payload(
        arm="ksana_real_research",
        input_layer="richer_research_packet",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )
    full = v3.build_prompt_payload(
        arm="full_gotra",
        input_layer="richer_research_packet",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )
    price_only_real = v3.build_prompt_payload(
        arm="ksana_real_research",
        input_layer="price_only_packet",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )

    assert "ksana_research_workflow" not in direct
    assert "alaya_feedback_history" not in direct
    assert direct["research_artifacts"]
    assert "never ksana" in direct["input_policy"]["direct_llm_richer_packet_contract"]
    assert "ksana_research_workflow" in formatting
    assert "research_artifacts" not in formatting
    assert "alaya_feedback_history" not in formatting
    assert real["research_artifacts"]
    assert "alaya_feedback_history" not in real
    assert full["research_artifacts"]
    assert full["alaya_feedback_history"] == feedback
    assert full["alaya_knowledge_state"]["strong_knowledge_auto_approval_allowed"] is False
    assert "research_artifacts" not in price_only_real
    assert full["output_contract"]["schema"] == v3.DECISION_SCHEMA
    assert direct["output_contract"]["ksana_refs"].startswith("MUST be exactly []")
    assert direct["output_contract"]["alaya_memory_refs"].startswith("MUST be exactly []")


def test_direct_llm_provider_prompt_requires_empty_ref_arrays() -> None:
    payload = v3.build_prompt_payload(
        arm="direct_llm",
        input_layer="price_only_packet",
        ticker="AAPL",
        decision_date=date(2024, 1, 2),
        price_rows=_price_rows(),
        feedback=[],
        provider="mock",
        provider_model="local-deterministic",
    )

    prompt = v3.render_provider_prompt(payload)

    assert 'For direct_llm, output "ksana_refs": [] exactly.' in prompt
    assert 'For direct_llm, output "alaya_memory_refs": [] exactly.' in prompt
    assert "never write full_gotra, alaya, ksana" in prompt
    assert '"ksana_refs": []' in prompt
    assert '"alaya_memory_refs": []' in prompt
    assert '"ksana_refs": "MUST be exactly []' in prompt
    assert '"alaya_memory_refs": "MUST be exactly []' in prompt


def test_cache_key_contains_input_layer_and_definition_version() -> None:
    price_key = v3.cache_key_for(
        arm="ksana_real_research",
        input_layer="price_only_packet",
        provider="glm_sophnet",
        provider_model="GLM-5.2",
        provider_base_url="https://api.sophnet.com/v1/chat/completions",
        provider_max_tokens=1600,
        prompt_hash="abc123",
    )
    rich_key = v3.cache_key_for(
        arm="ksana_real_research",
        input_layer="richer_research_packet",
        provider="glm_sophnet",
        provider_model="GLM-5.2",
        provider_base_url="https://api.sophnet.com/v1/chat/completions",
        provider_max_tokens=1600,
        prompt_hash="abc123",
    )

    assert price_key != rich_key
    assert "baseline-v3-four-arm-2026-06-19" in price_key
    assert "price_only_packet" in price_key
    assert "richer_research_packet" in rich_key
    assert "max_tokens=1600" in rich_key


def test_strict_decision_json_rejects_unknown_keys_without_invention() -> None:
    extra = _decision_payload()
    extra["actual_change_pct"] = 12.3
    missing = _decision_payload()
    missing.pop("reasoning")

    try:
        v3.parse_provider_decision(extra)
    except ValueError as exc:
        assert "unexpected decision JSON keys: actual_change_pct" in str(exc)
    else:
        raise AssertionError("expected unknown-key schema failure")

    try:
        v3.parse_provider_decision(missing)
    except ValueError as exc:
        assert "reasoning is required" in str(exc)
    else:
        raise AssertionError("expected missing-field schema failure")


def test_decision_json_requires_json_numbers_not_strings_or_percentages() -> None:
    string_expected = _decision_payload()
    string_expected["expected_change_pct"] = "1.25"
    string_confidence = _decision_payload()
    string_confidence["confidence"] = "0.72"
    percent_confidence = _decision_payload()
    percent_confidence["confidence"] = 72

    with pytest.raises(ValueError, match="expected_change_pct must be a JSON number"):
        v3.parse_provider_decision(string_expected)
    with pytest.raises(ValueError, match="confidence must be a JSON number"):
        v3.parse_provider_decision(string_confidence)
    with pytest.raises(ValueError, match="confidence out of range"):
        v3.parse_provider_decision(percent_confidence)


def test_research_source_leak_and_future_data_guards() -> None:
    leak_step = {
        "arm": "ksana_formatting_only",
        "research_artifacts": [
            {
                "name": "future_news",
                "kind": "news_items",
                "source_kind": "real",
            }
        ],
    }
    future_step = {
        "future_data_allowed": False,
        "decision_date": "2024-01-02",
        "outcome_as_of": "2024-02-01",
        "decision_inputs": [
            {"name": "adjusted_close_history", "availability_date": "2024-01-02"},
            {"name": "synthetic_news_context", "availability_date": "2024-01-03"},
        ],
        "outcome_inputs": [{"name": "outcome", "availability_date": "2024-02-01"}],
    }

    assert v3.research_source_leak_violations(leak_step) == [
        "formatting_only non-price research artifact: future_news"
    ]
    assert v3.future_data_violations(future_step) == [
        "decision input after decision_date: synthetic_news_context"
    ]


def test_parse_ref_isolation_normalization_and_input_echo() -> None:
    content = "provider note\n```json\n" + json.dumps(_decision_payload()) + "\n```\ntrailing"

    normalized, metadata = v3.normalize_provider_decision_content(content)
    parsed = v3.parse_provider_decision(content)

    assert json.loads(normalized)["schema"] == v3.DECISION_SCHEMA
    assert metadata["normalization_applied"] is True
    assert parsed.schema == v3.DECISION_SCHEMA
    assert parsed.normalization_applied is True

    direct_echo = _decision_payload()
    direct_echo["ksana_refs"] = ["not_allowed"]
    direct_alaya_echo = _decision_payload()
    direct_alaya_echo["alaya_memory_refs"] = ["full_gotra"]
    ksana_with_alaya = _decision_payload(arm="ksana_real_research")
    ksana_with_alaya["alaya_memory_refs"] = ["not_allowed"]
    try:
        v3.parse_provider_decision(direct_echo)
    except ValueError as exc:
        assert "direct_llm must not include" in str(exc)
    else:
        raise AssertionError("expected direct ref isolation failure")

    try:
        v3.parse_provider_decision(direct_alaya_echo)
    except ValueError as exc:
        assert "direct_llm must not include" in str(exc)
    else:
        raise AssertionError("expected direct alaya ref isolation failure")

    try:
        v3.parse_provider_decision(ksana_with_alaya)
    except ValueError as exc:
        assert "ksana_real_research must not include alaya_memory_refs" in str(exc)
    else:
        raise AssertionError("expected ksana ref isolation failure")

    raw_echo = '{"arm_contract": {"task": "x"}, "research_artifacts": [{"name": "x"}]'
    try:
        v3.parse_provider_decision(raw_echo)
    except v3.InputEchoError as exc:
        assert exc.detected_keys == ("arm_contract", "research_artifacts")
    else:
        raise AssertionError("expected InputEchoError")


def test_statistics_v3_pairs_by_arm_input_layer_and_segment() -> None:
    steps = [
        _step("AAPL", "2024-01-02", "price_only_packet", "direct_llm", mse=9.0, segment="warm_up"),
        _step(
            "AAPL",
            "2024-01-02",
            "price_only_packet",
            "ksana_real_research",
            mse=2.0,
            segment="warm_up",
        ),
        _step("AAPL", "2024-02-01", "price_only_packet", "direct_llm", mse=9.0),
        _step("AAPL", "2024-02-01", "price_only_packet", "ksana_real_research", mse=4.0),
        _step("AAPL", "2024-02-01", "richer_research_packet", "direct_llm", mse=8.0),
        _step(
            "AAPL",
            "2024-02-01",
            "richer_research_packet",
            "ksana_real_research",
            mse=3.0,
        ),
        _step("MSFT", "2024-02-01", "price_only_packet", "direct_llm", mse=7.0),
        _step("MSFT", "2024-02-01", "price_only_packet", "ksana_real_research", mse=1.0),
    ]

    price_only = paired_loss_differences_v3(
        steps,
        "direct_llm",
        "ksana_real_research",
        input_layer="price_only_packet",
    )
    richer = paired_loss_differences_v3(
        steps,
        "direct_llm",
        "ksana_real_research",
        input_layer="richer_research_packet",
    )

    assert price_only == {"AAPL": [5.0], "MSFT": [6.0]}
    assert richer == {"AAPL": [5.0]}
    first = cluster_bootstrap_ci(price_only, iters=200, seed=7)
    second = cluster_bootstrap_ci(price_only, iters=200, seed=7)
    one_cluster = cluster_bootstrap_ci(
        {"AAPL": [5.0, 6.0]},
        iters=200,
        seed=7,
        left_arm="direct_llm",
        right_arm="ksana_real_research",
    )
    assert first == second
    assert first["n_clusters"] == 2
    assert first["mean_loss_diff"] == 5.5
    assert first["statistical_test_completed"] is True
    assert "right_arm_better_significant" in first
    assert one_cluster["statistical_test_completed"] is False
    assert one_cluster["right_arm_better_significant"] is False
    assert one_cluster["passed"] is False
    assert one_cluster["reason"] == "not_enough_paired_steps"
    assert one_cluster["insufficient_reason"] == "not_enough_paired_steps"
    assert one_cluster["n_clusters"] == 1


def test_product_metrics_for_constructed_step() -> None:
    step = _product_metric_step(
        evidence_refs=["adjusted_close_history", "synthetic_news_context"],
        available_refs=["adjusted_close_history", "synthetic_news_context"],
    )

    metrics = v3.product_metrics_for_step(step)

    assert metrics["evidence_coverage"] == 1.0
    assert metrics["evidence_coverage_valid_ref_count"] == 2
    assert metrics["evidence_coverage_invalid_ref_count"] == 0
    assert metrics["evidence_coverage_duplicate_ref_count"] == 0
    assert metrics["reasoning_auditability"] == 1.0
    assert metrics["error_attribution_quality"] == 1.0
    assert metrics["claim_specificity"] == 1.0
    assert metrics["risk_disclosure_quality"] == 1.0


def test_product_metrics_evidence_coverage_deduplicates_refs() -> None:
    step = _product_metric_step(
        evidence_refs=[
            "adjusted_close_history",
            "synthetic_news_context",
            "synthetic_news_context",
        ],
        available_refs=[
            "adjusted_close_history",
            "synthetic_news_context",
            "synthetic_fundamentals_snapshot",
        ],
    )

    metrics = v3.product_metrics_for_step(step)

    assert metrics["evidence_coverage"] == 0.666667
    assert metrics["evidence_coverage_valid_ref_count"] == 2
    assert metrics["evidence_coverage_available_ref_count"] == 3
    assert metrics["evidence_coverage_invalid_ref_count"] == 0
    assert metrics["evidence_coverage_duplicate_ref_count"] == 1


def test_product_metrics_evidence_coverage_rejects_unavailable_refs() -> None:
    step = _product_metric_step(
        evidence_refs=[
            "adjusted_close_history",
            "return_21d_pct",
            "future_alpha_leak",
            "return_21d_pct",
        ],
        available_refs=["adjusted_close_history", "synthetic_news_context"],
    )

    metrics = v3.product_metrics_for_step(step)

    assert metrics["evidence_coverage"] == 0.5
    assert metrics["evidence_coverage_valid_ref_count"] == 1
    assert metrics["evidence_coverage_available_ref_count"] == 2
    assert metrics["evidence_coverage_invalid_ref_count"] == 2
    assert metrics["evidence_coverage_duplicate_ref_count"] == 1
    for key, value in metrics.items():
        if key.endswith("_count"):
            assert value >= 0
        else:
            assert 0.0 <= value <= 1.0


def _product_metric_step(*, evidence_refs: list[str], available_refs: list[str]) -> dict[str, object]:
    return {
        "schema": v3.STEP_SCHEMA,
        "definition_version": v3.DEFINITION_VERSION,
        "run_id": "baseline_v3_four_arm_mock_product",
        "status": "scored",
        "ticker": "AAPL",
        "arm": "full_gotra",
        "input_layer": "richer_research_packet",
        "scoring_segment": "scored",
        "decision_date": "2024-02-01",
        "window_days": 30,
        "direction": "long",
        "expected_change_pct": 2.5,
        "confidence": 0.7,
        "reasoning": "Used adjusted_close_history and synthetic_news_context.",
        "evidence_refs": evidence_refs,
        "risk_factors": ["fixture risk"],
        "available_evidence_count": len(available_refs),
        "decision_inputs": [{"name": ref, "kind": "fixture"} for ref in available_refs],
        "feedback_used_count": 1,
        "alaya_memory_refs": ["feedback:aapl:richer_research_packet:2024-01-02"],
    }


def test_short_counts_as_downside_hit() -> None:
    assert v3.actual_direction(-3.0) == "avoid"
    assert v3.direction_hit_for(predicted_direction="short", actual_change_pct=-3.0) is True
    assert v3.direction_hit_for(predicted_direction="avoid", actual_change_pct=-3.0) is True
    assert v3.direction_hit_for(predicted_direction="short", actual_change_pct=3.0) is False


def test_matured_feedback_filters_future_outcomes() -> None:
    feedback = [
        {
            "decision_date": "2024-01-02",
            "outcome_availability_date": "2024-02-01",
            "error": 1.0,
        },
        {
            "decision_date": "2024-02-01",
            "outcome_availability_date": "2024-03-15",
            "error": 2.0,
        },
    ]

    matured = v3.matured_feedback(feedback, decision_date=date(2024, 3, 1))

    assert [item["decision_date"] for item in matured] == ["2024-01-02"]


def test_full_gotra_alaya_refs_must_match_available_feedback_refs() -> None:
    decision = replace(
        v3.parse_provider_decision(_decision_payload(arm="full_gotra")),
        alaya_memory_refs=["feedback:aapl:price_only_packet:2024-01-02"],
    )

    with pytest.raises(v3.ProviderRequestError, match="invalid alaya_memory_refs"):
        v3.validate_alaya_memory_refs(decision, arm="full_gotra", feedback=[])
    with pytest.raises(v3.ProviderRequestError, match="invalid alaya_memory_refs"):
        v3.validate_alaya_memory_refs(
            decision,
            arm="full_gotra",
            feedback=[{"feedback_ref": "feedback:aapl:richer_research_packet:2024-01-02"}],
        )
    v3.validate_alaya_memory_refs(
        decision,
        arm="full_gotra",
        feedback=[{"feedback_ref": "feedback:aapl:price_only_packet:2024-01-02"}],
    )


def test_provider_decision_identity_mismatch_is_not_scored_or_cached(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", days=500)
    run_root = tmp_path / "runs" / "baseline_v3_four_arm_mock_identity"
    run_root.mkdir(parents=True)
    for arm in v3.ARMS:
        (run_root / arm).mkdir(parents=True)

    class MismatchedClient:
        provider = "mock"
        provider_model = "local"
        provider_base_url = "mock://local"
        provider_transport = "local_mock"
        last_raw_content = json.dumps(_decision_payload(arm="full_gotra"))

        def complete(self, *_args: object, **_kwargs: object) -> v3.ProviderDecision:
            return v3.parse_provider_decision(self.last_raw_content)

    cache = v3.LocalJsonCache(run_root / "cache.json")
    step = v3.complete_step(
        config=_config(tmp_path, run_id="baseline_v3_four_arm_mock_identity"),
        run_root=run_root,
        cache=cache,
        client=MismatchedClient(),  # type: ignore[arg-type]
        point=v3.DecisionPoint("AAPL", date(2024, 1, 2), "price_only_packet"),
        arm="direct_llm",
        feedback=[],
    )

    assert step["status"] == "provider_error"
    assert step["error_type"] == "schema_contract_error"
    assert "identity mismatch" in step["error_message"]
    assert step["provider_raw_content_path"]
    assert cache.values == {}


def test_mock_pass_fails_when_price_missing_prevents_scored_coverage(tmp_path: Path) -> None:
    summary = v3.run_four_arm(
        _config(
            tmp_path,
            run_id="baseline_v3_four_arm_mock_missing_prices",
            tickers=("MISSING",),
            dates=(date(2024, 1, 2), date(2024, 2, 1)),
        )
    )

    assert summary["status"] == "HARNESS_NEEDS_FIX"
    assert summary["price_missing_count"] > 0
    assert summary["scored_step_count"] == 0
    assert summary["paired_coverage"] == 0.0


def test_mock_pass_requires_positive_scored_coverage(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", days=500)

    summary = v3.run_four_arm(
        _config(
            tmp_path,
            run_id="baseline_v3_four_arm_mock_zero_scored",
            tickers=("AAPL",),
            dates=(date(2024, 1, 2),),
        )
    )

    assert summary["status"] == "DATA_INSUFFICIENT"
    assert summary["expected_scored_points"] == 0
    assert summary["paired_complete_points"] == 0


def test_pilot_stop_reason_uses_unattempted_scored_points() -> None:
    steps: list[dict[str, object]] = []
    for index in range(20):
        ticker = f"T{index:02d}"
        decision_date = f"2024-02-{index + 1:02d}"
        for arm in v3.ARMS:
            if index >= 18 and arm == "full_gotra":
                steps.append(
                    _error_step(
                        ticker,
                        decision_date,
                        "price_only_packet",
                        arm,
                        error_type="provider_timeout",
                    )
                )
            else:
                steps.append(_step(ticker, decision_date, "price_only_packet", arm, mse=1.0))

    assert v3.pilot_stop_reason(steps=steps, total_points=20) == "paired coverage no longer feasible"


def test_hac_runs_within_clusters_not_flattened_across_tickers() -> None:
    steps: list[dict[str, object]] = []
    for ticker in ("AAPL", "MSFT"):
        for decision_date in ("2024-02-01", "2024-03-01"):
            steps.append(_step(ticker, decision_date, "price_only_packet", "direct_llm", mse=5.0))
            steps.append(_step(ticker, decision_date, "price_only_packet", "ksana_real_research", mse=3.0))

    hac = v3.statistical_tests(steps)["price_only_packet"]["C3_direct_minus_real_research"]["hac"]

    assert hac["statistical_test_completed"] is False
    assert hac["reason"] == "not_enough_time_points"
    assert hac["n"] == 4


def test_c4_pairing_uses_feedback_eligible_points_only() -> None:
    steps = [
        _step("AAPL", "2024-02-01", "price_only_packet", "ksana_real_research", mse=5.0),
        _step("AAPL", "2024-02-01", "price_only_packet", "full_gotra", mse=4.0),
        _step("AAPL", "2024-03-01", "price_only_packet", "ksana_real_research", mse=6.0),
        _step("AAPL", "2024-03-01", "price_only_packet", "full_gotra", mse=2.0),
    ]
    steps[3]["feedback_used_count"] = 1

    c4 = v3.paired_diffs(steps)["C4_real_research_minus_full_gotra_mse"]

    assert c4["feedback_eligible_only"] is True
    assert c4["paired_points"] == 1
    assert c4["mse_delta_left_minus_right"] == 4.0


def test_nonpositive_step_months_rejected() -> None:
    args = v3.build_arg_parser().parse_args(
        ["--mode", "mock", "--start", "2024-01-01", "--end", "2024-02-01", "--step-months", "0"]
    )

    try:
        v3.config_from_args(args)
    except ValueError as exc:
        assert "--step-months must be a positive integer" in str(exc)
    else:
        raise AssertionError("expected nonpositive step-months failure")


def test_provider_canary_status_does_not_require_feedback_path() -> None:
    config = replace(
        _config(Path("/tmp/unused"), mode="provider-canary", dates=(date(2024, 1, 2),)),
        input_layers=("price_only_packet",),
        warm_up_dates=0,
    )
    steps = [
        _step("AAPL", "2024-01-02", "price_only_packet", arm, mse=1.0)
        for arm in v3.ARMS
    ]
    for step in steps:
        step["feedback_used_count"] = 0

    summary = v3.summarize_run(
        config=config,
        steps=steps,
        total_points=1,
        provider_preflight_error="",
        stop_reason="",
        max_provider_concurrency_used=1,
        downgrade_events=[],
    )

    assert summary["status"] == "PROVIDER_CANARY_PASS"
    assert summary["full_gotra_feedback_available_scored_points"] == 0
    assert summary["feedback_path_exercised"] is False


def test_glm_provider_max_tokens_is_sent_in_request_body(monkeypatch) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        requests.append(body)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(_decision_payload())}}]},
        )

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    client = v3.GlmSophnetDecisionClient(
        provider_max_tokens=77,
        transport=httpx.MockTransport(handler),
    )
    decision = client.complete(
        v3.build_prompt_payload(
            arm="direct_llm",
            input_layer="price_only_packet",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="glm_sophnet",
            provider_model="GLM-5.2",
        )
    )

    assert decision.schema == v3.DECISION_SCHEMA
    assert requests[0]["max_tokens"] == 77
    assert client.provider_max_tokens_applied is True


def test_kimi_retryable_timeout_recovers_with_attempt_metadata() -> None:
    client = v3.KimiDecisionClient(
        model="Kimi-K2.6",
        request_timeout_seconds=1,
        provider_base_url="mock://kimi",
        provider_max_tokens=77,
        timeout_retries=1,
        timeout_retry_backoff_seconds=0,
    )
    calls = 0

    def complete_once_after_timeout(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("SophNet Kimi request timed out")
        return {"content": json.dumps(_decision_payload())}

    client.client.complete = complete_once_after_timeout  # type: ignore[method-assign]

    decision = client.complete(
        v3.build_prompt_payload(
            arm="direct_llm",
            input_layer="price_only_packet",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="kimi",
            provider_model="Kimi-K2.6",
        )
    )

    assert calls == 2
    assert decision.provider_attempts == 2
    assert decision.provider_retry_count == 1
    assert decision.last_retryable_error_type == "TimeoutException"


def test_kimi_schema_and_input_echo_errors_are_not_retried() -> None:
    schema_client = v3.KimiDecisionClient(
        model="Kimi-K2.6",
        request_timeout_seconds=1,
        provider_base_url="mock://kimi",
        provider_max_tokens=77,
        timeout_retries=1,
        timeout_retry_backoff_seconds=0,
    )
    echo_client = v3.KimiDecisionClient(
        model="Kimi-K2.6",
        request_timeout_seconds=1,
        provider_base_url="mock://kimi",
        provider_max_tokens=77,
        timeout_retries=1,
        timeout_retry_backoff_seconds=0,
    )
    schema_calls = 0
    echo_calls = 0
    bad_schema = _decision_payload()
    bad_schema["future_data_allowed"] = True

    def complete_bad_schema(**_kwargs: object) -> dict[str, object]:
        nonlocal schema_calls
        schema_calls += 1
        return {"content": json.dumps(bad_schema)}

    def complete_input_echo(**_kwargs: object) -> dict[str, object]:
        nonlocal echo_calls
        echo_calls += 1
        return {"content": '{"arm_contract": {"task": "x"}, "research_artifacts": [{"name": "x"}]'}

    schema_client.client.complete = complete_bad_schema  # type: ignore[method-assign]
    echo_client.client.complete = complete_input_echo  # type: ignore[method-assign]
    payload = v3.build_prompt_payload(
        arm="direct_llm",
        input_layer="price_only_packet",
        ticker="AAPL",
        decision_date=date(2024, 1, 2),
        price_rows=_price_rows(),
        feedback=[],
        provider="kimi",
        provider_model="Kimi-K2.6",
    )

    with pytest.raises(v3.ProviderRequestError, match="future_data_allowed must be false") as schema_exc:
        schema_client.complete(payload)
    with pytest.raises(v3.ProviderRequestError, match="echoed the input packet") as echo_exc:
        echo_client.complete(payload)

    assert schema_calls == 1
    assert echo_calls == 1
    assert schema_exc.value.provider_retry_count == 0
    assert echo_exc.value.provider_retry_count == 0
    assert schema_exc.value.provider_error_class == "SchemaContractError"
    assert echo_exc.value.provider_error_class == "InputEchoError"


def test_failed_runtime_retry_is_not_scored_or_cached(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", days=500)
    run_root = tmp_path / "runs" / "baseline_v3_four_arm_retry_fail"
    run_root.mkdir(parents=True)
    for arm in v3.ARMS:
        (run_root / arm).mkdir(parents=True)

    class TimeoutClient:
        provider = "kimi"
        provider_model = "Kimi-K2.6"
        provider_base_url = "mock://kimi"
        provider_transport = "sophnet_chat_completions"
        last_raw_content = ""

        def complete(self, *_args: object, **_kwargs: object) -> v3.ProviderDecision:
            error = v3.ProviderRequestError(
                "SophNet Kimi request timed out",
                provider_error_class="TimeoutException",
                provider_attempts=2,
                provider_retry_count=1,
            )
            error.last_retryable_error_type = "TimeoutException"
            raise error

    cache = v3.LocalJsonCache(run_root / "cache.json")
    step = v3.complete_step(
        config=_config(tmp_path, run_id="baseline_v3_four_arm_retry_fail"),
        run_root=run_root,
        cache=cache,
        client=TimeoutClient(),  # type: ignore[arg-type]
        point=v3.DecisionPoint("AAPL", date(2024, 1, 2), "price_only_packet"),
        arm="ksana_real_research",
        feedback=[],
    )

    assert step["status"] == "provider_error"
    assert step["error_type"] == "provider_timeout"
    assert step["provider_attempts"] == 2
    assert step["provider_retry_count"] == 1
    assert step["last_retryable_error_type"] == "TimeoutException"
    assert cache.values == {}


def test_summary_records_retry_recovery_diagnostics(tmp_path: Path) -> None:
    step = _step("AAPL", "2024-02-01", "price_only_packet", "direct_llm", mse=1.0)
    step["provider_attempts"] = 2
    step["provider_retry_count"] = 1
    step["last_retryable_error_type"] = "TimeoutException"

    summary = v3.summarize_run(
        config=replace(_config(tmp_path), input_layers=("price_only_packet",), warm_up_dates=0),
        steps=[step],
        total_points=1,
        provider_preflight_error="",
        stop_reason="",
        max_provider_concurrency_used=1,
        downgrade_events=[],
    )

    assert summary["retryable_provider_error_recovered_count"] == 1
    assert summary["unrecovered_provider_timeout_count"] == 0
    direct_diag = summary["request_diagnostics_by_arm"]["direct_llm"]
    assert direct_diag["retryable_provider_error_recovered_count"] == 1
    assert direct_diag["last_retryable_error_types"] == ["TimeoutException"]


def test_mock_run_writes_warm_up_feedback_and_v3_artifacts(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", days=520)
    config = _config(
        tmp_path,
        run_id="baseline_v3_four_arm_mock_impl_test",
        tickers=("AAPL",),
        dates=(
            date(2024, 1, 2),
            date(2024, 2, 1),
            date(2024, 3, 1),
            date(2024, 4, 1),
        ),
    )
    config = replace(config, provider_max_tokens=1600)

    summary = v3.run_four_arm(config)
    run_root = tmp_path / "runs" / "baseline_v3_four_arm_mock_impl_test"
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    warm_step = json.loads(
        (
            run_root
            / "full_gotra"
            / "step_2024-01-02_aapl_richer_research_packet.json"
        ).read_text(encoding="utf-8")
    )
    later_step = json.loads(
        (
            run_root
            / "full_gotra"
            / "step_2024-02-01_aapl_richer_research_packet.json"
        ).read_text(encoding="utf-8")
    )
    later_price_step = json.loads(
        (
            run_root
            / "full_gotra"
            / "step_2024-02-01_aapl_price_only_packet.json"
        ).read_text(encoding="utf-8")
    )
    direct_price = json.loads(
        (
            run_root
            / "direct_llm"
            / "step_2024-02-01_aapl_price_only_packet.json"
        ).read_text(encoding="utf-8")
    )

    assert summary["status"] == "MOCK_PASS"
    assert summary["provider_call_status"] == "no real provider HTTP call"
    assert summary["expected_scored_points"] == 6
    assert summary["paired_complete_points"] == 6
    assert summary["paired_coverage"] == 1.0
    assert summary["future_data_violations"] == 0
    assert summary["research_source_leak_count"] == 0
    assert summary["synthetic_evidence_count"] > 0
    assert summary["source_kind_counts"]["synthetic"] > 0
    assert summary["provider_max_tokens"] == 1600
    assert summary["provider_max_tokens_applied"] is False
    assert summary["scored_step_count"] == summary["expected_steps"]
    assert summary["full_gotra_scored_points"] == 6
    assert summary["decision_schema"] == v3.DECISION_SCHEMA
    assert summary["metrics"]["direct_llm"]["calibration"]["confidence_count"] == 6
    assert summary["metrics"]["direct_llm"]["calibration"]["brier_score_direction"] is not None
    assert summary["metrics"]["direct_llm"]["calibration"]["abstain_count"] == 0
    assert summary["metrics"]["direct_llm"]["calibration"]["calibration_bins"]
    assert "C3_direct_minus_real_research" in summary["statistical_tests"]["richer_research_packet"]
    assert manifest["schema"] == v3.MANIFEST_SCHEMA
    assert manifest["definition_version"] == v3.DEFINITION_VERSION
    assert manifest["input_layers"] == ["price_only_packet", "richer_research_packet"]
    assert manifest["provider_max_tokens"] == 1600
    assert manifest["provider_max_tokens_applied"] is False
    assert warm_step["scoring_segment"] == "warm_up"
    assert later_step["scoring_segment"] == "scored"
    assert later_step["feedback_used_count"] > 0
    assert later_step["alaya_memory_refs"] == [
        "feedback:aapl:richer_research_packet:2024-01-02"
    ]
    assert later_price_step["alaya_memory_refs"] == [
        "feedback:aapl:price_only_packet:2024-01-02"
    ]
    assert "richer_research_packet" not in later_price_step["alaya_memory_refs"][0]
    assert "price_only_packet" not in later_step["alaya_memory_refs"][0]
    assert later_step["research_artifact_count"] == 2
    assert later_step["synthetic_evidence_count"] == 2
    assert later_step["source_kind_counts"]["synthetic"] == 2
    assert "richer_research_packet" in later_step["cache_key"]
    assert direct_price["ksana_workflow_enabled"] is False
    assert direct_price["alaya_feedback_enabled"] is False
    assert direct_price["provider_max_tokens"] == 1600
    assert direct_price["provider_max_tokens_applied"] is False
    assert direct_price["definition_version"] == v3.DEFINITION_VERSION
    assert direct_price["schema"] == v3.STEP_SCHEMA
    assert (run_root / "ledger.jsonl").exists()


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
    mode: v3.Mode = "mock",
    run_id: str = "baseline_v3_four_arm_mock_test",
    tickers: tuple[str, ...] = ("AAPL",),
    dates: tuple[date, ...] = (date(2024, 1, 2), date(2024, 2, 1)),
) -> v3.RunConfig:
    return v3.RunConfig(
        mode=mode,
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


def _step(
    ticker: str,
    decision_date: str,
    input_layer: str,
    arm: str,
    *,
    mse: float,
    segment: str = "scored",
) -> dict[str, object]:
    return {
        "status": "scored",
        "ticker": ticker,
        "decision_date": decision_date,
        "input_layer": input_layer,
        "scoring_segment": segment,
        "arm": arm,
        "mse": mse,
        "mae": 1.0,
        "policy_a_return_pct": 0.0,
        "direction_hit": True,
        "confidence": 0.7,
        "actual_change_pct": 1.0,
        "abstain_reason": None,
        "feedback_used_count": 0,
    }


def _error_step(
    ticker: str,
    decision_date: str,
    input_layer: str,
    arm: str,
    *,
    error_type: str,
) -> dict[str, object]:
    return {
        "status": "provider_error",
        "error_type": error_type,
        "ticker": ticker,
        "decision_date": decision_date,
        "input_layer": input_layer,
        "scoring_segment": "scored",
        "arm": arm,
    }


def _decision_payload(
    *,
    arm: v3.Arm = "direct_llm",
    direction: str = "long",
    confidence: float = 0.72,
) -> dict[str, object]:
    return {
        "schema": v3.DECISION_SCHEMA,
        "arm": arm,
        "ticker": "AAPL",
        "decision_date": "2024-01-02",
        "horizon_days": 30,
        "direction": direction,
        "expected_change_pct": 1.25,
        "confidence": confidence,
        "reasoning": "Valid adjusted_close_history.",
        "evidence_refs": ["adjusted_close_history"],
        "ksana_refs": [],
        "alaya_memory_refs": [],
        "risk_factors": [],
        "abstain_reason": None,
        "input_cutoff": "2024-01-02",
        "future_data_allowed": False,
    }
