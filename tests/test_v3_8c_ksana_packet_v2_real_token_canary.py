from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as canary


def test_valid_synthetic_real_token_like_summary_passes(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary())

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_PASS
    assert summary["real_calls_count"] == 3
    assert summary["schema_pass_rate"] == 1.0
    assert summary["overclaim_rate"] == 0.0
    assert summary["missing_field_rate"] == 0.0
    assert summary["provider_or_backend_called"] is True
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_missing_required_packet_v2_field_blocks_schema(tmp_path: Path, monkeypatch) -> None:
    packet = _packet()
    packet.pop("ranked_hypotheses")
    _install_fake_client(monkeypatch, [{"content": json.dumps(packet), "usage": _usage()}])

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_SCHEMA
    assert "missing_or_invalid_packet_v2_schema_field" in summary["blocker_reasons"]


def test_missing_input_fixture_hash_blocks_provenance(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(
        monkeypatch,
        [{"content": json.dumps(_packet()), "usage": _usage()}],
        autofill_input_hash=False,
    )

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_SCHEMA
    assert "missing_or_inconsistent_provenance" in summary["blocker_reasons"]


def test_overclaim_packet_blocks(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(why_it_matters="This is public science proof and trading advice.")
    _install_fake_client(monkeypatch, [{"content": json.dumps(packet), "usage": _usage()}])

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"
    assert summary["overclaim_rate"] > 0


def test_missing_usage_metadata_blocks_metadata(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(monkeypatch, [{"content": json.dumps(_packet()), "usage": None}])

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_METADATA
    assert "usage_metadata_missing" in summary["blocker_reasons"]
    assert summary["provider_or_backend_called"] is True


def test_call_count_over_budget_blocks_runtime_boundary(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(real_calls_count=6, call_count=6))

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "call_count_over_budget" in summary["blocker_reasons"]


def test_requested_call_count_must_be_fulfilled(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(real_calls_count=3, requested_call_count=4, call_count=3))

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "requested_call_count_not_fulfilled" in summary["blocker_reasons"]


def test_fake_real_call_count_four_can_pass(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(
        monkeypatch,
        [{"content": json.dumps(_packet()), "usage": _usage()} for _ in range(4)],
    )

    summary = canary.build_summary(_real_config(tmp_path, call_count=4))

    assert summary["canary_status"] == canary.STATUS_PASS
    assert summary["real_calls_count"] == 4
    assert summary["requested_call_count"] == 4


def test_unsafe_runtime_flag_blocks(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(formal_lite_entered=True))

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "formal_lite_entered_not_false" in summary["blocker_reasons"]


def test_reasoning_effort_must_remain_xhigh(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(reasoning_effort="low"))

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "reasoning_effort_not_allowed" in summary["blocker_reasons"]


def test_base_url_must_be_allowlisted_before_client_creation(tmp_path: Path, monkeypatch) -> None:
    class FailIfConstructed:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("client should not be constructed for disallowed base_url")

    monkeypatch.setattr(canary, "CodexResponsesCompletionClient", FailIfConstructed)

    summary = canary.build_summary(
        _real_config_with_options(tmp_path, call_count=1, base_url="https://example.invalid/capture")
    )

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "base_url_not_allowed" in summary["blocker_reasons"]
    assert summary["provider_or_backend_called"] is False


def test_real_output_dir_must_be_under_tmp_before_client_creation(tmp_path: Path, monkeypatch) -> None:
    class FailIfConstructed:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("client should not be constructed for non-/tmp output dir")

    monkeypatch.setattr(canary, "CodexResponsesCompletionClient", FailIfConstructed)
    config = _real_config_with_options(
        tmp_path,
        call_count=1,
        output_dir=Path("/var/tmp") / f"gotra_v3_8c_non_tmp_output_{tmp_path.name}",
    )

    summary = canary.build_summary(config)

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "real_output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["provider_or_backend_called"] is False


def test_env_auth_path_is_validated_when_no_arg_is_supplied(tmp_path: Path, monkeypatch) -> None:
    missing_env_auth = tmp_path / "missing-auth.json"
    monkeypatch.setenv("CODEX_AUTH_JSON", str(missing_env_auth))

    summary = canary.build_summary(_real_config_with_options(tmp_path, call_count=1, auth_json_path=None))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "auth_json_not_found" in summary["blocker_reasons"]
    assert summary["provider_or_backend_called"] is False


def test_raw_response_path_outside_tmp_blocks(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(raw_response_tmp_path="/Users/peachy/raw.json"))

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "raw_or_packet_path_not_tmp" in summary["blocker_reasons"]


def test_parsed_packet_path_is_required_in_call_result(tmp_path: Path) -> None:
    fixture_payload = _ready_summary()
    call_results = list(fixture_payload["call_results"])  # type: ignore[index]
    dict(call_results[0]).pop("parsed_packet_tmp_path", None)
    call_result = dict(call_results[0])
    call_result.pop("parsed_packet_tmp_path", None)
    call_results[0] = call_result
    fixture_payload["call_results"] = call_results
    fixture = _write_summary_fixture(tmp_path, fixture_payload)

    summary = canary.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "call_result_missing_field" in summary["blocker_reasons"]


def test_malformed_response_blocks_schema(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(monkeypatch, [{"content": "not json", "usage": _usage()}])

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_SCHEMA
    assert "parsed_packet_json_parse_failed" in summary["blocker_reasons"]


def test_secret_redaction_and_runtime_error_do_not_leak_key(tmp_path: Path, monkeypatch) -> None:
    secret_value = "Bearer " + "abcdefghijklmnop"

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def complete(self, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("backend failed with " + secret_value)

    monkeypatch.setattr(canary, "CodexResponsesCompletionClient", FakeClient)

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "abcdefghijklmnop" not in json.dumps(summary)
    assert canary.redact_secrets(secret_value) == "[REDACTED]"


def test_direct_llm_clean_baseline_wording_blocks(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(counterfactuals=["direct_llm is a clean no-future baseline"])
    _install_fake_client(monkeypatch, [{"content": json.dumps(packet), "usage": _usage()}])

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_BLOCKED_OVERCLAIM
    assert any("direct_llm" in reason for reason in summary["blocker_reasons"])


def test_valid_fake_real_call_path_passes(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(monkeypatch, [{"content": json.dumps(_packet()), "usage": _usage()}])

    summary = canary.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["canary_status"] == canary.STATUS_PASS
    assert summary["real_calls_count"] == 1
    assert summary["token_usage_total"] == 12
    assert summary["raw_response_tmp_paths"][0].startswith("/tmp/")
    assert summary["parsed_packet_sha256s"][0]


def test_run_id_reuse_cli_prints_single_json_summary(tmp_path: Path, capsys) -> None:
    run_id = "baseline_v3_8c_ksana_packet_v2_real_token_canary_collision"
    output_dir = tmp_path / "runs"
    fixture = _write_summary_fixture(tmp_path, _ready_summary(real_calls_count=1, call_count=1))

    first = canary.main(
        [
            "--canary-run-id",
            run_id,
            "--summary-fixture",
            str(fixture),
            "--output-dir",
            str(output_dir),
            "--allow-overwrite",
        ]
    )
    capsys.readouterr()
    second = canary.main(
        [
            "--canary-run-id",
            run_id,
            "--summary-fixture",
            str(fixture),
            "--output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr().out

    assert first == 0
    assert second == 1
    parsed = json.loads(captured)
    assert parsed["canary_status"] == canary.STATUS_RUN_ID_EXISTS


def _install_fake_client(monkeypatch, responses: list[dict[str, Any]], *, autofill_input_hash: bool = True) -> None:
    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            self._responses = list(responses)

        def complete(self, **_kwargs: object) -> dict[str, object]:
            if not self._responses:
                raise RuntimeError("no fake response configured")
            response = dict(self._responses.pop(0))
            if autofill_input_hash and isinstance(response.get("content"), str):
                response["content"] = _packet_content_with_prompt_hash(
                    str(response["content"]),
                    str(_kwargs.get("user_prompt") or ""),
                )
            return response

    monkeypatch.setattr(canary, "CodexResponsesCompletionClient", FakeClient)


def _packet_content_with_prompt_hash(content: str, user_prompt: str) -> str:
    digest_match = re.search(r"\b[0-9a-f]{64}\b", user_prompt)
    if not digest_match:
        return content
    try:
        packet = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(packet, dict) and isinstance(packet.get("provenance"), dict):
        packet["provenance"]["input_fixture_hash"] = digest_match.group(0)
        return json.dumps(packet)
    return content


def _ready_summary(**updates: object) -> dict[str, object]:
    call_count = int(updates.pop("call_count", updates.get("real_calls_count", 3)))
    call_results = [_call_result(index) for index in range(call_count)]
    if "raw_response_tmp_path" in updates and call_results:
        call_results[0]["raw_response_tmp_path"] = updates.pop("raw_response_tmp_path")
    raw_paths = [str(result["raw_response_tmp_path"]) for result in call_results]
    parsed_paths = [str(result["parsed_packet_tmp_path"]) for result in call_results]
    payload: dict[str, object] = {
        "canary_status": canary.STATUS_PASS,
        "backend_name": canary.DEFAULT_BACKEND_NAME,
        "model": canary.DEFAULT_MODEL,
        "reasoning_effort": canary.DEFAULT_REASONING_EFFORT,
        "real_calls_count": call_count,
        "requested_call_count": call_count,
        "max_call_count": canary.MAX_CALL_COUNT,
        "token_usage_total": call_count * 12,
        "token_budget": canary.DEFAULT_TOKEN_BUDGET,
        "latency_ms_values": [101 + index for index in range(call_count)],
        "schema_pass_count": call_count,
        "schema_pass_rate": 1.0,
        "overclaim_blocker_count": 0,
        "overclaim_rate": 0.0,
        "missing_field_count": 0,
        "missing_field_rate": 0.0,
        "usage_available_count": call_count,
        "usage_availability_rate": 1.0,
        "raw_response_tmp_paths": raw_paths,
        "raw_response_sha256s": ["c" * 64 for _ in range(call_count)],
        "parsed_packet_tmp_paths": parsed_paths,
        "parsed_packet_sha256s": ["d" * 64 for _ in range(call_count)],
        "input_fixture_hashes": ["a" * 64 for _ in range(call_count)],
        "prompt_hashes": ["b" * 64 for _ in range(call_count)],
        "call_results": call_results,
        "provider_or_backend_called": True,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "actual_30d_readiness_status": canary.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": canary.ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "evidence_layer": canary.EVIDENCE_LAYER,
        "direct_llm_interpretation": canary.DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_provider_canary_verdict": True,
            "not_actual_v3_7_or_v3_8_verdict": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
        },
    }
    payload.update(updates)
    return payload


def _call_result(index: int = 0) -> dict[str, object]:
    return {
        "run_id": "baseline_v3_8c_ksana_packet_v2_real_token_canary_unit",
        "call_id": f"call_{index + 1:03d}",
        "backend_name": canary.DEFAULT_BACKEND_NAME,
        "model": canary.DEFAULT_MODEL,
        "sdk_version": "python-test",
        "api_version": "codex_responses_oauth_streaming",
        "prompt_hash": "b" * 64,
        "input_fixture_hash": "a" * 64,
        "raw_response_tmp_path": f"/tmp/gotra_v3_8c_unit/call_{index + 1:03d}_raw_response.json",
        "raw_response_sha256": "c" * 64,
        "parsed_packet_tmp_path": f"/tmp/gotra_v3_8c_unit/call_{index + 1:03d}_parsed_packet.json",
        "parsed_packet_sha256": "d" * 64,
        "schema_status": "clean",
        "claim_boundary_status": "clean",
        "provenance_hash_status": "clean",
        "latency_ms": 100 + index,
        "token_usage_input": 8,
        "token_usage_output": 4,
        "token_usage_total": 12,
        "ranked_hypothesis_count": 2,
        "blocker_reasons": [],
    }


def _packet(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": canary.PACKET_SCHEMA,
        "source_run_id": "baseline_v3_8c_ksana_packet_v2_real_token_canary_unit",
        "source_artifact_path": "/tmp/gotra_v3_8c_unit/synthetic_brief.json",
        "ticker": "SYNALP",
        "decision_date": "2026-06-22",
        "research_mode": "synthetic_ksana_packet_v2_real_token_schema_canary",
        "ranked_hypotheses": [
            {
                "rank": 1,
                "hypothesis": "Support-ticket clustering may explain training friction.",
                "confidence": 0.58,
                "why_it_matters": "It gives a falsifiable operations check.",
                "falsification_triggers": ["No ticket concentration appears in weekly logs."],
                "expected_observable_evidence": ["Weekly support log category counts."],
                "counterfactuals": ["If onboarding is unchanged, ticket mix should remain flat."],
            },
            {
                "rank": 2,
                "hypothesis": "Release-note quality may reduce repeated questions.",
                "confidence": 0.52,
                "why_it_matters": "It separates documentation effects from staffing effects.",
                "falsification_triggers": ["Repeated questions rise despite clearer release notes."],
                "expected_observable_evidence": ["FAQ repeat-rate sample."],
                "counterfactuals": ["If staffing is the driver, notes alone will not change repeats."],
            },
        ],
        "why_it_matters": "The packet checks whether the schema can express falsifiable operational structure.",
        "confidence": 0.55,
        "falsification_triggers": ["Ticket categories do not change after process documentation updates."],
        "expected_observable_evidence": ["Mock support queue counts and onboarding checklist completion logs."],
        "counterfactuals": ["A pure staffing explanation would show timing aligned with coverage gaps."],
        "disagreement_with_price_only": ["The fictional brief uses operations-only signals rather than prices."],
        "evidence_gaps": ["No real customer or future outcome data is included."],
        "uncertainty_decomposition": {"operations": "mock-only", "data_quality": "synthetic brief only"},
        "non_claims": [
            "not a provider canary verdict",
            "not an actual v3.7 or v3.8 verdict",
            "not OOS/science/public/trading claim",
            "not investment advice",
            f"historical direct_llm remains {canary.DIRECT_LLM_INTERPRETATION}",
        ],
        "evidence_layer": canary.EVIDENCE_LAYER,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "provenance": {
            "source_run_id": "baseline_v3_8c_ksana_packet_v2_real_token_canary_unit",
            "source_artifact_path": "/tmp/gotra_v3_8c_unit/synthetic_brief.json",
            "backend": canary.DEFAULT_BACKEND_NAME,
            "model": canary.DEFAULT_MODEL,
            "call_id": "call_001",
        },
    }
    payload.update(updates)
    return payload


def _usage() -> dict[str, int]:
    return {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}


def _config(tmp_path: Path, *, summary_fixture: Path | None = None) -> canary.CanaryConfig:
    return canary.CanaryConfig(
        canary_run_id="baseline_v3_8c_ksana_packet_v2_real_token_canary_unit",
        output_dir=tmp_path / "runs",
        allow_overwrite=True,
        summary_fixture=summary_fixture,
    )


def _real_config(tmp_path: Path, *, call_count: int) -> canary.CanaryConfig:
    return _real_config_with_options(tmp_path, call_count=call_count)


def _real_config_with_options(
    tmp_path: Path,
    *,
    call_count: int,
    output_dir: Path | None = None,
    base_url: str | None = None,
    auth_json_path: Path | None | object = ...,
) -> canary.CanaryConfig:
    resolved_auth_path = _write_auth(tmp_path) if auth_json_path is ... else auth_json_path
    return canary.CanaryConfig(
        canary_run_id="baseline_v3_8c_ksana_packet_v2_real_token_canary_unit",
        output_dir=output_dir or _tmp_output_dir(tmp_path),
        allow_overwrite=True,
        real_token_canary=True,
        auth_json_path=resolved_auth_path,  # type: ignore[arg-type]
        base_url=base_url,
        call_count=call_count,
    )


def _tmp_output_dir(tmp_path: Path) -> Path:
    path = Path("/tmp") / f"gotra_v3_8c_unit_{tmp_path.name}" / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_summary_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "summary_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_auth(tmp_path: Path) -> Path:
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps({"auth_placeholder": "test", "account_id": "test-account-id"}),
        encoding="utf-8",
    )
    return path
