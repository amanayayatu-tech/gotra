from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd

from scripts import baseline_v2_three_arm_pilot as pilot


def test_arm_payload_boundaries_do_not_mix_direct_ksana_or_alaya() -> None:
    price_rows = _price_rows()
    feedback = [
        {
            "decision_date": "2024-01-02",
            "outcome_availability_date": "2024-02-01",
            "error": 2.0,
        }
    ]

    direct = pilot.build_prompt_payload(
        arm="direct_llm",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )
    ksana = pilot.build_prompt_payload(
        arm="ksana_only",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )
    full = pilot.build_prompt_payload(
        arm="full_gotra",
        ticker="AAPL",
        decision_date=date(2024, 7, 2),
        price_rows=price_rows,
        feedback=feedback,
        provider="mock",
        provider_model="local-deterministic",
    )

    assert "ksana_research_workflow" not in direct
    assert "alaya_feedback_history" not in direct
    assert "ksana_research_workflow" in ksana
    assert "alaya_feedback_history" not in ksana
    assert "ksana_research_workflow" in full
    assert full["alaya_feedback_history"] == feedback
    assert full["alaya_knowledge_state"]["strong_knowledge_auto_approval_allowed"] is False
    assert full["output_contract"]["schema"] == pilot.DECISION_SCHEMA


def test_schema_parser_normalizes_all_arms_to_one_output_contract() -> None:
    parsed = pilot.parse_provider_decision(_decision_payload(direction="hold", confidence=72))

    assert parsed.direction == "neutral"
    assert parsed.expected_change_pct == 1.25
    assert parsed.confidence == 0.72
    assert parsed.evidence_refs == ["adjusted_close_history"]
    assert parsed.future_data_allowed is False


def test_normalizer_strips_fenced_json_with_surrounding_prose() -> None:
    content = "provider note\n```json\n" + json.dumps(_decision_payload()) + "\n```\ntrailing"

    normalized, metadata = pilot.normalize_provider_decision_content(content)
    parsed = pilot.parse_provider_decision(content)

    assert json.loads(normalized)["schema"] == pilot.DECISION_SCHEMA
    assert metadata["normalization_applied"] is True
    assert "strip_markdown_fence_lines" in metadata["normalization_steps"]
    assert "extract_first_balanced_json_object" in metadata["normalization_steps"]
    assert parsed.schema == pilot.DECISION_SCHEMA
    assert parsed.normalization_applied is True


def test_render_provider_prompt_v2_separates_contract_and_forbids_input_echo() -> None:
    payload = pilot.build_prompt_payload(
        arm="ksana_only",
        ticker="AAPL",
        decision_date=date(2024, 1, 2),
        price_rows=_price_rows(),
        feedback=[],
        provider="kimi",
        provider_model="Kimi-K2.6",
    )

    rendered = pilot.render_provider_prompt(payload)

    assert "OUTPUT REQUIREMENTS:" in rendered
    assert "Do not copy INPUT PACKET" in rendered
    assert "INPUT_PACKET_DO_NOT_COPY:" in rendered
    assert "DECISION_JSON_ALLOWED_KEYS:" in rendered
    assert "direction must be exactly one of: long, avoid, neutral, watch, short" in rendered
    assert "Do not use direction synonyms" in rendered
    assert "confidence must be a JSON number in [0, 1]" in rendered
    assert 'never use "medium"' in rendered
    assert "output_contract" in rendered
    assert '"output_contract":' not in rendered
    assert rendered.rstrip().endswith("FINAL ANSWER:")


def test_parse_rejects_complete_input_echo_json() -> None:
    payload = pilot.build_prompt_payload(
        arm="ksana_only",
        ticker="AAPL",
        decision_date=date(2024, 1, 2),
        price_rows=_price_rows(),
        feedback=[],
        provider="kimi",
        provider_model="Kimi-K2.6",
    )

    try:
        pilot.parse_provider_decision(json.dumps(payload))
    except pilot.InputEchoError as exc:
        assert "arm_contract" in exc.detected_keys
        assert "output_contract" in exc.detected_keys
        assert "raw_inputs" in exc.detected_keys
    else:
        raise AssertionError("expected InputEchoError")


def test_raw_prefix_detector_classifies_incomplete_input_echo() -> None:
    raw = '{"arm_contract": {"task": "x"}, "raw_inputs": {"recent_adjusted_close": ['

    error = pilot.ProviderRequestError(
        "bad json",
        provider_error_class="JSONDecodeError",
        raw_content=raw,
    )

    assert pilot.detect_input_echo_raw_content(raw) == ["arm_contract", "raw_inputs"]
    assert pilot.classify_exception(error) == "input_echo_error"


def test_balanced_json_extraction_respects_quoted_braces_and_escaped_quotes() -> None:
    payload = _decision_payload()
    payload["reasoning"] = 'quoted brace { stays in string } and escaped " quote'
    content = "prefix " + json.dumps(payload) + " trailing {ignored}"

    normalized, metadata = pilot.normalize_provider_decision_content(content)
    parsed = pilot.parse_provider_decision(content)

    assert json.loads(normalized)["reasoning"] == payload["reasoning"]
    assert metadata["normalization_steps"] == ["extract_first_balanced_json_object"]
    assert parsed.reasoning == payload["reasoning"]


def test_malformed_json_remains_json_decode_error() -> None:
    content = '{"schema": "gotra.baseline_v2.three_arm_decision.v1", "reasoning": '

    normalized, metadata = pilot.normalize_provider_decision_content(content)

    assert normalized.startswith("{")
    assert metadata["normalization_failure_reason"] == "no_complete_balanced_json_object"
    try:
        pilot.parse_provider_decision(content)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("expected JSONDecodeError")


def test_missing_required_field_remains_schema_contract_error_without_invention() -> None:
    payload = _decision_payload()
    payload.pop("reasoning")

    try:
        pilot.parse_provider_decision(json.dumps(payload))
    except ValueError as exc:
        assert "reasoning is required" in str(exc)
    else:
        raise AssertionError("expected schema contract ValueError")


def test_cache_key_contains_arm_provider_prompt_hash_and_definition_version() -> None:
    key = pilot.cache_key_for(
        arm="ksana_only",
        provider="glm_sophnet",
        provider_model="GLM-5.2",
        provider_base_url="https://api.sophnet.com/v1/chat/completions",
        provider_max_tokens=1600,
        prompt_hash="abc123",
    )

    assert "baseline-v2-three-arm-2026-06-18" in key
    assert "ksana_only" in key
    assert "glm_sophnet" in key
    assert "GLM-5.2" in key
    assert "https://api.sophnet.com/v1/chat/completions" in key
    assert "max_tokens=1600" in key
    assert key.endswith(":abc123")


def test_per_arm_complexity_normalized_timeout_policy(tmp_path: Path) -> None:
    config = _config(tmp_path)

    assert pilot.effective_request_timeout_seconds(
        config,
        arm="direct_llm",
        prompt_bytes=0,
    ) == 300.0
    assert pilot.effective_request_timeout_seconds(
        config,
        arm="direct_llm",
        prompt_bytes=1,
    ) == 320.0
    assert pilot.effective_request_timeout_seconds(
        config,
        arm="full_gotra",
        prompt_bytes=100_000,
    ) == 720.0


def test_timeout_policy_records_size_without_prompt_text(tmp_path: Path) -> None:
    config = _config(tmp_path)

    policy = pilot.request_timeout_policy(config, arm="ksana_only", prompt_bytes=2048)

    assert policy["policy"] == "per_arm_complexity_normalized_v2"
    assert policy["arm_base_timeout_seconds"] == 420.0
    assert policy["prompt_bytes"] == 2048
    assert "prompt" not in json.dumps(policy).replace("prompt_bytes", "")


def test_deepseek_flash_cli_defaults_and_rate_limit_manifest(tmp_path: Path) -> None:
    args = pilot.build_arg_parser().parse_args(
        [
            "--mode",
            "mock",
            "--provider",
            "glm_sophnet",
            "--provider-model",
            "DeepSeek-V4-Flash",
            "--provider-base-url",
            "https://api.sophnet.com/v1/chat/completions",
            "--run-id",
            "baseline_v2_three_arm_mock_deepseek_defaults",
            "--runs-root",
            str(tmp_path / "runs"),
            "--price-dir",
            str(tmp_path / "prices"),
        ]
    )

    config = pilot.config_from_args(args)

    assert config.direct_llm_timeout_seconds == 90.0
    assert config.ksana_only_timeout_seconds == 120.0
    assert config.full_gotra_timeout_seconds == 180.0
    assert config.timeout_per_kb_seconds == 5.0
    assert config.max_request_timeout_seconds == 240.0
    assert config.timeout_retries == 0
    assert config.timeout_retry_backoff_seconds == 0.0
    assert config.provider_base_url == "https://api.sophnet.com/v1/chat/completions"
    assert pilot.timeout_policy_manifest(config)["policy"] == (
        "per_arm_complexity_normalized_deepseek_flash_v2"
    )
    assert pilot.provider_limit_metadata(config)["provider_rpm_limit"] == 120

    run_root = tmp_path / "runs" / "baseline_v2_three_arm_mock_deepseek_defaults"
    run_root.mkdir(parents=True)
    pilot.write_manifest(run_root, config)
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["target_provider_model"] == "DeepSeek-V4-Flash"
    assert manifest["provider_base_url"] == "https://api.sophnet.com/v1/chat/completions"
    assert manifest["provider_rpm_limit"] == 120
    assert manifest["provider_tpm_limit"] == 600000
    assert manifest["provider_rpm_target"] == 90
    assert manifest["provider_tpm_target"] == 450000
    assert manifest["rate_limit_source"] == "user_provided_sophnet_screenshot_2026-06-19"


def test_provider_canary_cli_respects_requested_concurrency(tmp_path: Path) -> None:
    args = pilot.build_arg_parser().parse_args(
        [
            "--mode",
            "provider-canary",
            "--provider",
            "glm_sophnet",
            "--provider-model",
            "DeepSeek-V4-Flash",
            "--provider-concurrency",
            "2",
            "--max-provider-concurrency",
            "2",
            "--run-id",
            "baseline_v2_three_arm_canary_deepseek_concurrency",
            "--runs-root",
            str(tmp_path / "runs"),
            "--price-dir",
            str(tmp_path / "prices"),
        ]
    )

    config = pilot.config_from_args(args)

    assert config.provider_concurrency == 2
    assert config.max_provider_concurrency == 2


def test_provider_canary_run_uses_requested_concurrency(tmp_path: Path, monkeypatch) -> None:
    captured: list[int] = []

    def fake_run_date_wave(**kwargs: object) -> list[dict[str, object]]:
        captured.append(int(kwargs["concurrency"]))
        return []

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    monkeypatch.setattr(pilot, "run_date_wave", fake_run_date_wave)
    args = pilot.build_arg_parser().parse_args(
        [
            "--mode",
            "provider-canary",
            "--provider",
            "glm_sophnet",
            "--provider-model",
            "DeepSeek-V4-Flash",
            "--provider-base-url",
            "https://api.sophnet.com/v1/chat/completions",
            "--provider-concurrency",
            "2",
            "--max-provider-concurrency",
            "2",
            "--run-id",
            "baseline_v2_three_arm_canary_deepseek_concurrency_run",
            "--runs-root",
            str(tmp_path / "runs"),
            "--price-dir",
            str(tmp_path / "prices"),
        ]
    )

    pilot.run_three_arm(pilot.config_from_args(args))

    assert captured
    assert set(captured) == {2}


def test_endpoint_discovery_requires_extractable_nonempty_content() -> None:
    no_content = pilot.classify_endpoint_discovery_result(
        label="api_v1",
        url="https://api.sophnet.com/v1/chat/completions",
        http_status=200,
        body_text=json.dumps({"choices": [{"message": {"content": ""}}]}),
    )
    success = pilot.classify_endpoint_discovery_result(
        label="api_v1",
        url="https://api.sophnet.com/v1/chat/completions",
        http_status=200,
        body_text=json.dumps({"choices": [{"message": {"content": "{\"ok\":true}"}}]}),
    )

    assert no_content["success"] is False
    assert no_content["result"] == "incompatible_response"
    assert success["success"] is True
    assert success["result"] == "success"


def test_endpoint_discovery_prefers_api_v1_when_both_success() -> None:
    results = [
        {
            "label": "api_v1",
            "url": "https://api.sophnet.com/v1/chat/completions",
            "success": True,
            "result": "success",
        },
        {
            "label": "www_open_apis",
            "url": "https://www.sophnet.com/api/open-apis/v1/chat/completions",
            "success": True,
            "result": "success",
        },
    ]

    selected = pilot.select_endpoint_or_blocker(results)

    assert selected["selected_label"] == "api_v1"
    assert selected["selected_base_url"] == "https://api.sophnet.com/v1/chat/completions"
    assert selected["blocker"] == ""


def test_endpoint_discovery_uses_www_open_apis_when_api_v1_fails() -> None:
    results = [
        {
            "label": "api_v1",
            "url": "https://api.sophnet.com/v1/chat/completions",
            "success": False,
            "result": "timeout_or_unreachable",
        },
        {
            "label": "www_open_apis",
            "url": "https://www.sophnet.com/api/open-apis/v1/chat/completions",
            "success": True,
            "result": "success",
        },
    ]

    selected = pilot.select_endpoint_or_blocker(results)

    assert selected["selected_label"] == "www_open_apis"
    assert selected["selected_base_url"] == (
        "https://www.sophnet.com/api/open-apis/v1/chat/completions"
    )
    assert selected["blocker"] == ""


def test_endpoint_discovery_blocks_only_when_both_fail() -> None:
    results = [
        {
            "label": "api_v1",
            "url": "https://api.sophnet.com/v1/chat/completions",
            "success": False,
            "result": "timeout_or_unreachable",
        },
        {
            "label": "www_open_apis",
            "url": "https://www.sophnet.com/api/open-apis/v1/chat/completions",
            "success": False,
            "result": "timeout_or_unreachable",
        },
    ]

    selected = pilot.select_endpoint_or_blocker(results)

    assert selected["selected_base_url"] == ""
    assert selected["blocker"] == "PROVIDER_ENDPOINTS_UNREACHABLE"


def test_missing_step_does_not_get_reconstructed_into_paired_coverage() -> None:
    steps = [
        _step("AAPL", "2024-01-02", "direct_llm"),
        _step("AAPL", "2024-01-02", "ksana_only"),
        _step("AAPL", "2024-01-02", "full_gotra"),
        _step("MSFT", "2024-01-02", "direct_llm"),
        _step("MSFT", "2024-01-02", "ksana_only"),
    ]
    config = _config(Path("/tmp/unused"), tickers=("AAPL", "MSFT"), dates=(date(2024, 1, 2),))

    summary = pilot.summarize_run(
        config=config,
        steps=steps,
        total_points=2,
        provider_preflight_error="",
        stop_reason="",
        max_provider_concurrency_used=1,
        downgrade_events=[],
    )

    assert summary["paired_complete_points"] == 1
    assert summary["paired_coverage"] == 0.5


def test_provider_canary_stops_on_missing_sophnet_key_without_printing_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    monkeypatch.delenv("SOPHNET_API_KEY", raising=False)
    config = _config(
        tmp_path,
        mode="provider-canary",
        run_id="baseline_v2_three_arm_canary_missing_key",
        tickers=("AAPL",),
        dates=(date(2024, 1, 2),),
    )

    summary = pilot.run_three_arm(config)

    assert summary["status"] == "PROVIDER_BLOCKED_PRE_HTTP"
    assert summary["provider_preflight_error"] == (
        "PROVIDER_BLOCKED_PRE_HTTP: SOPHNET_API_KEY/API_KEY=not_set"
    )
    assert summary["provider_call_status"] == "no real provider HTTP call"
    assert summary["provider_error_count"] == 3
    run_root = tmp_path / "runs" / "baseline_v2_three_arm_canary_missing_key"
    assert (run_root / "direct_llm" / "step_2024-01-02_aapl.json").exists()
    assert "secret" not in (run_root / "summary.json").read_text(encoding="utf-8").lower()


def test_mock_run_keeps_full_gotra_feedback_time_ordered(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL", days=700)
    config = _config(
        tmp_path,
        mode="mock",
        run_id="baseline_v2_three_arm_mock_feedback",
        tickers=("AAPL",),
        dates=(date(2024, 1, 2), date(2024, 7, 2)),
    )

    summary = pilot.run_three_arm(config)

    assert summary["status"] == "MOCK_PASS"
    run_root = tmp_path / "runs" / "baseline_v2_three_arm_mock_feedback"
    first_full = json.loads(
        (run_root / "full_gotra" / "step_2024-01-02_aapl.json").read_text(encoding="utf-8")
    )
    second_full = json.loads(
        (run_root / "full_gotra" / "step_2024-07-02_aapl.json").read_text(encoding="utf-8")
    )
    direct_second = json.loads(
        (run_root / "direct_llm" / "step_2024-07-02_aapl.json").read_text(encoding="utf-8")
    )

    assert first_full["feedback_used_count"] == 0
    assert second_full["feedback_used_count"] == 1
    assert direct_second["ksana_workflow_enabled"] is False
    assert direct_second["alaya_feedback_enabled"] is False
    assert second_full["alaya_memory_refs"] == ["matured_feedback"]
    assert second_full["prompt_chars"] > 0
    assert second_full["prompt_bytes"] >= second_full["prompt_chars"]
    assert second_full["request_timeout_seconds"] >= 560.0
    assert second_full["request_timeout_seconds"] <= 720.0
    assert second_full["request_timeout_policy"]["policy"] == "per_arm_complexity_normalized_v2"
    assert "request_diagnostics_by_arm" in summary
    assert summary["full_gotra_feedback_used_in_later_date"] is True


def test_existing_run_id_blocks_without_overwriting(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "baseline_v2_three_arm_mock_existing"
    run_root.mkdir(parents=True)
    sentinel = run_root / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    config = _config(
        tmp_path,
        run_id="baseline_v2_three_arm_mock_existing",
        tickers=("AAPL",),
        dates=(date(2024, 1, 2),),
    )

    summary = pilot.run_three_arm(config)

    assert summary["status"] == "BLOCKED_RUN_ID_EXISTS"
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (run_root / "summary.json").exists()


def test_glm_sophnet_client_uses_sophnet_endpoint_and_api_key_priority(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url == pilot.DEFAULT_GLM_BASE_URL
        assert request.headers["Authorization"] == "Bearer sophnet-secret"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "GLM-5.2"
        assert body["stream"] is False
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(_decision_payload(), ensure_ascii=False),
                        }
                    }
                ]
            },
        )

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    monkeypatch.setenv("API_KEY", "fallback-secret")

    client = pilot.GlmSophnetDecisionClient(transport=httpx.MockTransport(handler))
    decision = client.complete(
        pilot.build_prompt_payload(
            arm="direct_llm",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="glm_sophnet",
            provider_model="GLM-5.2",
        )
    )

    assert len(requests) == 1
    assert decision.schema == pilot.DECISION_SCHEMA
    assert decision.arm == "direct_llm"
    assert decision.provider_attempts == 1


def test_provider_base_url_override_passed_to_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    selected_base_url = "https://api.sophnet.com/v1/chat/completions"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(_decision_payload())}}]},
        )

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    client = pilot.GlmSophnetDecisionClient(
        base_url=selected_base_url,
        transport=httpx.MockTransport(handler),
    )

    client.complete(
        pilot.build_prompt_payload(
            arm="direct_llm",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="glm_sophnet",
            provider_model="DeepSeek-V4-Flash",
        )
    )

    assert requests[0].url == selected_base_url


def test_kimi_provider_base_url_override_passed_to_client(monkeypatch) -> None:
    seen: dict[str, object] = {}
    selected_base_url = "https://api.sophnet.com/v1/chat/completions"

    class FakeKimiCompletionClient:
        def __init__(self, **kwargs: object) -> None:
            seen.update(kwargs)

        def complete(self, **kwargs: object) -> dict[str, str]:
            seen["max_tokens"] = kwargs["max_tokens"]
            seen["user_prompt"] = kwargs["user_prompt"]
            return {"content": json.dumps(_decision_payload())}

    monkeypatch.setattr(pilot, "KimiCompletionClient", FakeKimiCompletionClient)

    client = pilot.KimiDecisionClient(
        model="Kimi-K2.6",
        request_timeout_seconds=240,
        provider_base_url=selected_base_url,
        provider_max_tokens=1600,
    )
    decision = client.complete(
        pilot.build_prompt_payload(
            arm="direct_llm",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="kimi",
            provider_model="Kimi-K2.6",
        )
    )

    assert seen["model"] == "Kimi-K2.6"
    assert seen["base_url"] == selected_base_url
    assert seen["max_tokens"] == 1600
    assert "Do not copy INPUT PACKET" in str(seen["user_prompt"])
    assert '"output_contract":' not in str(seen["user_prompt"])
    assert decision.provider_attempts == 1


def test_kimi_env_file_api_key_aliases_to_sophnet_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SOPHNET_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    env_file = tmp_path / ".env.sophnet"
    env_file.write_text("API_KEY=local-test-secret\n", encoding="utf-8")

    args = pilot.build_arg_parser().parse_args(
        [
            "--mode",
            "provider-canary",
            "--provider",
            "kimi",
            "--provider-model",
            "Kimi-K2.6",
            "--env-file",
            str(env_file),
            "--run-id",
            "baseline_v2_three_arm_canary_kimi26_test",
            "--runs-root",
            str(tmp_path / "runs"),
        ]
    )
    config = pilot.config_from_args(args)

    assert config.provider_base_url == "https://api.sophnet.com/v1/chat/completions"
    assert pilot.provider_preflight_blocker(config) == ""
    assert os.getenv("SOPHNET_API_KEY") == "local-test-secret"


def test_kimi_http_429_is_classified_for_circuit_breaker(monkeypatch) -> None:
    class FakeKimiCompletionClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def complete(self, **_kwargs: object) -> dict[str, str]:
            raise RuntimeError("SophNet Kimi request failed with HTTP 429")

    monkeypatch.setattr(pilot, "KimiCompletionClient", FakeKimiCompletionClient)

    client = pilot.KimiDecisionClient(
        model="Kimi-K2.6",
        request_timeout_seconds=240,
        provider_base_url="https://api.sophnet.com/v1/chat/completions",
        provider_max_tokens=1600,
    )

    try:
        client.complete(
            pilot.build_prompt_payload(
                arm="direct_llm",
                ticker="AAPL",
                decision_date=date(2024, 1, 2),
                price_rows=_price_rows(),
                feedback=[],
                provider="kimi",
                provider_model="Kimi-K2.6",
            )
        )
    except pilot.ProviderRequestError as exc:
        assert exc.provider_error_class == "HTTP_429"
        assert exc.provider_attempts == 1
        assert pilot.classify_exception(exc) == "provider_http_429"
    else:
        raise AssertionError("expected ProviderRequestError")


def test_raw_content_artifact_redacts_and_truncates_excerpt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOPHNET_API_KEY", "secret-token")
    raw = "prefix secret-token " + ("x" * 1500)

    fields = pilot.raw_content_artifact_fields(
        run_root=tmp_path / "runs" / "baseline_v2_three_arm_raw",
        point=pilot.DecisionPoint("AAPL", date(2024, 1, 2)),
        arm="full_gotra",
        raw_content=raw,
    )

    raw_path = Path(str(fields["provider_raw_content_path"]))
    saved = raw_path.read_text(encoding="utf-8")
    assert "secret-token" not in saved
    assert "[redacted]" in saved
    assert len(str(fields["provider_raw_content_excerpt"])) <= 1200
    assert fields["provider_raw_content_chars"] == len(saved)
    assert fields["provider_raw_content_sha256"]


def test_schema_parse_failure_writes_provider_raw_content_path(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    run_root = tmp_path / "runs" / "baseline_v2_three_arm_canary_raw"
    run_root.mkdir(parents=True)
    for arm in pilot.ARMS:
        (run_root / arm).mkdir(parents=True)
    raw_content = "prefix " + '{"schema": ' + ("x" * 1300)

    class FailingClient:
        provider = "kimi"
        provider_model = "Kimi-K2.6"
        provider_base_url = "https://api.sophnet.com/v1/chat/completions"
        provider_transport = "sophnet_chat_completions"

        def complete(self, *_args: object, **_kwargs: object) -> pilot.ProviderDecision:
            _normalized, metadata = pilot.normalize_provider_decision_content(raw_content)
            raise pilot.ProviderRequestError(
                "bad json",
                provider_error_class="JSONDecodeError",
                provider_attempts=1,
                raw_content=raw_content,
                normalization_metadata=metadata,
            )

    config = _config(
        tmp_path,
        mode="provider-canary",
        run_id="baseline_v2_three_arm_canary_raw",
    )

    step = pilot.complete_step(
        config=config,
        run_root=run_root,
        cache=pilot.LocalJsonCache(run_root / "cache.json"),
        client=FailingClient(),  # type: ignore[arg-type]
        point=pilot.DecisionPoint("AAPL", date(2024, 1, 2)),
        arm="full_gotra",
        feedback=[],
    )

    assert step["error_type"] == "json_decode_error"
    assert step["provider_raw_content_path"]
    assert Path(str(step["provider_raw_content_path"])).exists()
    assert len(step["provider_raw_content_excerpt"]) <= 1200
    assert step["provider_raw_content_sha256"]
    assert step["normalization_failure_reason"] == "no_complete_balanced_json_object"


def test_input_echo_error_step_records_detected_keys_and_summary_count(tmp_path: Path) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    run_root = tmp_path / "runs" / "baseline_v2_three_arm_canary_input_echo"
    run_root.mkdir(parents=True)
    for arm in pilot.ARMS:
        (run_root / arm).mkdir(parents=True)
    raw_content = '{"arm_contract": {"task": "x"}, "raw_inputs": {"recent_adjusted_close": ['

    class FailingClient:
        provider = "kimi"
        provider_model = "Kimi-K2.6"
        provider_base_url = "https://api.sophnet.com/v1/chat/completions"
        provider_transport = "sophnet_chat_completions"

        def complete(self, *_args: object, **_kwargs: object) -> pilot.ProviderDecision:
            _normalized, metadata = pilot.normalize_provider_decision_content(raw_content)
            raise pilot.ProviderRequestError(
                "bad json",
                provider_error_class="JSONDecodeError",
                provider_attempts=1,
                raw_content=raw_content,
                normalization_metadata=metadata,
            )

    config = _config(
        tmp_path,
        mode="provider-canary",
        run_id="baseline_v2_three_arm_canary_input_echo",
    )

    step = pilot.complete_step(
        config=config,
        run_root=run_root,
        cache=pilot.LocalJsonCache(run_root / "cache.json"),
        client=FailingClient(),  # type: ignore[arg-type]
        point=pilot.DecisionPoint("AAPL", date(2024, 1, 2)),
        arm="ksana_only",
        feedback=[],
    )
    summary = pilot.summarize_run(
        config=config,
        steps=[step],
        total_points=1,
        provider_preflight_error="",
        stop_reason=pilot.circuit_breaker_reason([step]),
        max_provider_concurrency_used=1,
        downgrade_events=[],
    )

    assert step["error_type"] == "input_echo_error"
    assert step["input_echo_detected_keys"] == ["arm_contract", "raw_inputs"]
    assert step["provider_raw_content_path"]
    assert summary["input_echo_error_count"] == 1
    assert summary["schema_error_count"] == 1
    assert summary["root_failure"] == "input_echo_error/ksana_only/AAPL/2024-01-02"


def test_provider_max_tokens_appears_in_manifest_summary_step_and_cache_key(
    tmp_path: Path,
) -> None:
    _write_prices(tmp_path / "prices", "AAPL")
    config = _config(
        tmp_path,
        run_id="baseline_v2_three_arm_mock_max_tokens",
        tickers=("AAPL",),
        dates=(date(2024, 1, 2),),
    )
    config = replace(config, provider_max_tokens=1600)

    summary = pilot.run_three_arm(config)
    run_root = tmp_path / "runs" / "baseline_v2_three_arm_mock_max_tokens"
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    step = json.loads(
        (run_root / "direct_llm" / "step_2024-01-02_aapl.json").read_text(encoding="utf-8")
    )

    assert summary["provider_max_tokens"] == 1600
    assert manifest["provider_max_tokens"] == 1600
    assert step["provider_max_tokens"] == 1600
    assert "max_tokens=1600" in step["cache_key"]


def test_glm_sophnet_retries_without_temperature_when_provider_rejects_it(monkeypatch) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        requests.append(body)
        if "temperature" in body:
            return httpx.Response(400, text="temperature is not supported")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(_decision_payload())}}]},
        )

    monkeypatch.setenv("API_KEY", "fallback-secret")
    monkeypatch.delenv("SOPHNET_API_KEY", raising=False)

    client = pilot.GlmSophnetDecisionClient(transport=httpx.MockTransport(handler))
    decision = client.complete(
        pilot.build_prompt_payload(
            arm="direct_llm",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="glm_sophnet",
            provider_model="GLM-5.2",
        )
    )

    assert len(requests) == 2
    assert "temperature" in requests[0]
    assert "temperature" not in requests[1]
    assert decision.direction == "long"
    assert decision.provider_attempts == 2
    assert decision.provider_retry_count == 0
    assert decision.provider_temperature_fallback is True


def test_glm_sophnet_retries_timeout_only(monkeypatch) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.TimeoutException("slow provider")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(_decision_payload())}}]},
        )

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    client = pilot.GlmSophnetDecisionClient(
        transport=httpx.MockTransport(handler),
        timeout_retries=1,
        timeout_retry_backoff_seconds=0,
    )

    decision = client.complete(
        pilot.build_prompt_payload(
            arm="direct_llm",
            ticker="AAPL",
            decision_date=date(2024, 1, 2),
            price_rows=_price_rows(),
            feedback=[],
            provider="glm_sophnet",
            provider_model="GLM-5.2",
        )
    )

    assert calls == 2
    assert decision.provider_attempts == 2
    assert decision.provider_retry_count == 1


def test_glm_sophnet_timeout_retries_zero_does_not_retry(monkeypatch) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.TimeoutException("slow provider")

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    client = pilot.GlmSophnetDecisionClient(
        transport=httpx.MockTransport(handler),
        timeout_retries=0,
        timeout_retry_backoff_seconds=0,
    )

    try:
        client.complete(
            pilot.build_prompt_payload(
                arm="direct_llm",
                ticker="AAPL",
                decision_date=date(2024, 1, 2),
                price_rows=_price_rows(),
                feedback=[],
                provider="glm_sophnet",
                provider_model="DeepSeek-V4-Flash",
            )
        )
    except pilot.ProviderRequestError as exc:
        assert exc.provider_error_class == "TimeoutException"
        assert exc.provider_attempts == 1
        assert exc.provider_retry_count == 0
    else:
        raise AssertionError("expected ProviderRequestError")

    assert calls == 1


def test_glm_sophnet_does_not_retry_http_429(monkeypatch) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, text="Rate limit exceeded")

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    client = pilot.GlmSophnetDecisionClient(
        transport=httpx.MockTransport(handler),
        timeout_retries=1,
        timeout_retry_backoff_seconds=0,
    )

    try:
        client.complete(
            pilot.build_prompt_payload(
                arm="direct_llm",
                ticker="AAPL",
                decision_date=date(2024, 1, 2),
                price_rows=_price_rows(),
                feedback=[],
                provider="glm_sophnet",
                provider_model="GLM-5.2",
            )
        )
    except pilot.ProviderRequestError as exc:
        assert exc.provider_error_class == "HTTP_429"
        assert exc.provider_attempts == 1
    else:
        raise AssertionError("expected ProviderRequestError")

    assert calls == 1


def test_json_decode_error_does_not_retry_and_is_classified(monkeypatch) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setenv("SOPHNET_API_KEY", "sophnet-secret")
    client = pilot.GlmSophnetDecisionClient(
        transport=httpx.MockTransport(handler),
        timeout_retries=1,
        timeout_retry_backoff_seconds=0,
    )

    try:
        client.complete(
            pilot.build_prompt_payload(
                arm="direct_llm",
                ticker="AAPL",
                decision_date=date(2024, 1, 2),
                price_rows=_price_rows(),
                feedback=[],
                provider="glm_sophnet",
                provider_model="GLM-5.2",
            )
        )
    except Exception as exc:  # noqa: BLE001 - parser output is intentionally invalid.
        assert pilot.classify_exception(exc) == "json_decode_error"
        assert getattr(exc, "provider_attempts") == 1
    else:
        raise AssertionError("expected parser error")

    assert calls == 1


def test_provider_error_and_future_data_trigger_pilot_fuses() -> None:
    error_steps = [
        {"status": "provider_error", "ticker": "AAPL", "decision_date": "2024-01-02", "arm": "a"},
        {"status": "provider_error", "ticker": "AAPL", "decision_date": "2024-01-02", "arm": "b"},
        {"status": "provider_error", "ticker": "AAPL", "decision_date": "2024-01-02", "arm": "c"},
    ]
    future_step = {
        "status": "provider_error",
        "error_type": "future_data_violation",
        "ticker": "AAPL",
        "decision_date": "2024-01-02",
        "arm": "direct_llm",
    }

    assert "consecutive provider_error" in pilot.pilot_stop_reason(steps=error_steps, total_points=1)
    assert "future-data" in pilot.pilot_stop_reason(steps=[future_step], total_points=1)


def test_http_429_and_consecutive_timeout_trigger_circuit_breaker() -> None:
    http_429_step = {
        "status": "provider_error",
        "error_type": "provider_http_429",
        "ticker": "AAPL",
        "decision_date": "2024-01-02",
        "arm": "direct_llm",
    }
    timeout_steps = [
        {
            "status": "provider_error",
            "error_type": "provider_timeout",
            "ticker": "AAPL",
            "decision_date": "2024-01-02",
            "arm": "direct_llm",
        },
        {
            "status": "provider_error",
            "error_type": "provider_timeout",
            "ticker": "AAPL",
            "decision_date": "2024-01-02",
            "arm": "ksana_only",
        },
    ]

    assert pilot.circuit_breaker_reason([http_429_step]) == "HTTP 429 observed"
    assert pilot.circuit_breaker_reason(timeout_steps) == "consecutive provider_timeout >= 2"


def test_scheduler_interleaves_full_gotra_with_each_point(tmp_path: Path, monkeypatch) -> None:
    order: list[tuple[str, str]] = []
    config = _config(
        tmp_path,
        mode="provider-canary",
        tickers=("AAPL", "MSFT"),
        dates=(date(2024, 1, 2),),
    )

    def fake_complete_step(**kwargs: object) -> dict[str, object]:
        point = kwargs["point"]
        arm = kwargs["arm"]
        assert isinstance(point, pilot.DecisionPoint)
        order.append((point.ticker, str(arm)))
        return {
            **_step(point.ticker, point.decision_date.isoformat(), arm),  # type: ignore[arg-type]
            "outcome_as_of": "2024-02-01",
            "actual_change_pct": 1.0,
            "expected_change_pct": 1.0,
            "direction": "neutral",
            "error": 0.0,
        }

    monkeypatch.setattr(pilot, "complete_step", fake_complete_step)

    pilot.run_date_wave(
        config=config,
        run_root=tmp_path / "runs" / "unused",
        cache=pilot.LocalJsonCache(tmp_path / "cache.json"),
        client=pilot.MockDecisionClient(
            provider="mock",
            provider_model="local",
            provider_base_url="mock://local",
        ),
        points=[pilot.DecisionPoint("AAPL", date(2024, 1, 2)), pilot.DecisionPoint("MSFT", date(2024, 1, 2))],
        feedback_by_ticker={"AAPL": [], "MSFT": []},
        concurrency=1,
        circuit_breaker=pilot.CircuitBreakerState(),
        prior_steps=[],
    )

    assert order == [
        ("AAPL", "direct_llm"),
        ("AAPL", "ksana_only"),
        ("AAPL", "full_gotra"),
        ("MSFT", "direct_llm"),
        ("MSFT", "ksana_only"),
        ("MSFT", "full_gotra"),
    ]


def test_future_data_audit_reports_decision_input_after_cutoff() -> None:
    step = {
        "future_data_allowed": False,
        "decision_date": "2024-01-02",
        "outcome_as_of": "2024-02-01",
        "decision_inputs": [{"name": "future", "availability_date": "2024-01-03"}],
        "outcome_inputs": [{"name": "outcome", "availability_date": "2024-02-01"}],
    }

    assert pilot.future_data_violations(step) == ["decision input after decision_date: future"]


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
    mode: pilot.Mode = "mock",
    run_id: str = "baseline_v2_three_arm_mock_test",
    tickers: tuple[str, ...] = ("AAPL",),
    dates: tuple[date, ...] = (date(2024, 1, 2),),
) -> pilot.RunConfig:
    return pilot.RunConfig(
        mode=mode,
        run_id=run_id,
        provider="glm_sophnet",
        provider_model="GLM-5.2",
        provider_base_url=pilot.DEFAULT_GLM_BASE_URL,
        tickers=tickers,
        dates=dates,
        runs_root=root / "runs",
        price_dir=root / "prices",
        token_budget=500_000_000,
        provider_concurrency=1,
        max_provider_concurrency=1,
        adaptive_concurrency=True,
        direct_llm_timeout_seconds=300.0,
        ksana_only_timeout_seconds=420.0,
        full_gotra_timeout_seconds=540.0,
        timeout_per_kb_seconds=20.0,
        max_request_timeout_seconds=720.0,
        timeout_retries=1,
        timeout_retry_backoff_seconds=0.0,
        scheduler_policy="per_date_feedback_snapshot_interleaved_point_arm_v2",
    )


def _step(ticker: str, decision_date: str, arm: pilot.Arm) -> dict[str, object]:
    return {
        "status": "scored",
        "ticker": ticker,
        "decision_date": decision_date,
        "arm": arm,
        "mse": 1.0,
        "mae": 1.0,
        "policy_a_return_pct": 0.0,
        "direction_hit": True,
    }


def _decision_payload(
    *,
    arm: pilot.Arm = "direct_llm",
    direction: str = "long",
    confidence: float = 0.72,
) -> dict[str, object]:
    return {
        "schema": pilot.DECISION_SCHEMA,
        "arm": arm,
        "ticker": "AAPL",
        "decision_date": "2024-01-02",
        "horizon_days": 30,
        "direction": direction,
        "expected_change_pct": "1.25",
        "confidence": confidence,
        "reasoning": "Valid.",
        "evidence_refs": ["adjusted_close_history"],
        "ksana_refs": [],
        "alaya_memory_refs": [],
        "risk_factors": [],
        "abstain_reason": None,
        "input_cutoff": "2024-01-02",
        "future_data_allowed": False,
    }
