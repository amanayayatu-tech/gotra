from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from scripts import baseline_v3_8c_ksana_packet_v2_real_token_canary as packet_canary
from scripts import baseline_v3_8d_gotra_orchestrator_real_token_dry_run as dry_run


def test_valid_local_fixture_summary_passes(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary())

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_PASS
    assert summary["real_calls_count"] == 3
    assert summary["schema_pass_rate"] == 1.0
    assert summary["overclaim_rate"] == 0.0
    assert summary["provider_or_backend_called"] is True
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False


def test_missing_required_provenance_fields_block_schema(tmp_path: Path) -> None:
    payload = _ready_summary()
    payload.pop("generated_at")
    call_results = list(payload["call_results"])  # type: ignore[index]
    first = dict(call_results[0])
    first.pop("run_id")
    call_results[0] = first
    payload["call_results"] = call_results
    fixture = _write_summary_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_SCHEMA
    assert "summary_missing_field" in summary["blocker_reasons"]
    assert "call_result_missing_field" in summary["blocker_reasons"]


def test_missing_usage_metadata_on_real_path_blocks_metadata(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(monkeypatch, [{"content": json.dumps(_packet()), "usage": None}])

    summary = dry_run.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_METADATA
    assert "usage_metadata_missing" in summary["blocker_reasons"]
    assert summary["provider_or_backend_called"] is True


def test_call_count_or_token_budget_over_limit_blocks_runtime_boundary(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(
        tmp_path,
        _ready_summary(real_calls_count=6, requested_call_count=6, call_count=6),
    )

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "call_count_over_budget" in summary["blocker_reasons"]


def test_token_usage_over_budget_blocks_runtime_boundary(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(token_usage_total=dry_run.HARD_TOKEN_BUDGET + 1))

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "token_usage_over_budget" in summary["blocker_reasons"]


def test_runtime_paths_must_be_under_tmp(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(raw_response_tmp_path="/Users/peachy/raw.json"))

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "runtime_path_not_tmp" in summary["blocker_reasons"] or "raw_response_tmp_path_not_tmp" in summary["blocker_reasons"]


def test_unsafe_runtime_flags_block(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(formal_lite_entered=True))

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "formal_lite_entered_not_false" in summary["blocker_reasons"]


def test_status_like_overclaim_blocks(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(
        tmp_path,
        _ready_summary(blocker_reasons=["synthetic status says actual v3.7 verdict ready"]),
    )

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_future_data_metadata_violation_blocks(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(future_data_violation_count=1))

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_SCHEMA
    assert "future_data_violation_present" in summary["blocker_reasons"]


def test_old_provider_and_formal_lite_boundaries_block(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(backend_name="kimi_legacy_backend"))

    summary = dry_run.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "backend_not_allowed" in summary["blocker_reasons"]


def test_fake_real_call_path_passes(tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(monkeypatch, [{"content": json.dumps(_packet()), "usage": _usage()}])

    summary = dry_run.build_summary(_real_config(tmp_path, call_count=1))

    assert summary["dry_run_status"] == dry_run.STATUS_PASS
    assert summary["real_calls_count"] == 1
    assert summary["token_usage_total"] == 12
    assert summary["raw_response_tmp_paths"][0].startswith("/tmp/")
    assert summary["orchestrator_trace_sha256s"][0]
    assert summary["scorer_entered"] is False
    assert summary["actual_outcome_used"] is False
    assert summary["comparison_result_emitted"] is False


def test_base_url_rejected_before_client_construction(tmp_path: Path, monkeypatch) -> None:
    class FailIfConstructed:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("client should not be constructed for disallowed endpoint")

    monkeypatch.setattr(dry_run, "CodexResponsesCompletionClient", FailIfConstructed)

    summary = dry_run.build_summary(
        _real_config_with_options(tmp_path, call_count=1, base_url="https://example.invalid/capture")
    )

    assert summary["dry_run_status"] == dry_run.STATUS_PROVIDER_BLOCKED_PRE_HTTP
    assert "base_url_not_allowed" in summary["blocker_reasons"]
    assert summary["provider_or_backend_called"] is False


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

    monkeypatch.setattr(dry_run, "CodexResponsesCompletionClient", FakeClient)


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
    trace_paths = [str(result["orchestrator_trace_tmp_path"]) for result in call_results]
    payload: dict[str, object] = {
        "dry_run_status": dry_run.STATUS_PASS,
        "schema": dry_run.SUMMARY_SCHEMA,
        "script_version": dry_run.SCRIPT_VERSION,
        "dry_run_run_id": "baseline_v3_8d_gotra_orchestrator_real_token_dry_run_unit",
        "generated_at": "2026-06-22T04:00:00Z",
        "backend_name": dry_run.DEFAULT_BACKEND_NAME,
        "model": dry_run.DEFAULT_MODEL,
        "reasoning_effort": dry_run.DEFAULT_REASONING_EFFORT,
        "real_calls_count": call_count,
        "requested_call_count": call_count,
        "max_call_count": dry_run.MAX_CALL_COUNT,
        "token_usage_total": call_count * 12,
        "token_budget": dry_run.DEFAULT_TOKEN_BUDGET,
        "latency_ms_values": [101 + index for index in range(call_count)],
        "schema_pass_count": call_count,
        "schema_pass_rate": 1.0,
        "overclaim_blocker_count": 0,
        "overclaim_rate": 0.0,
        "future_data_violation_count": 0,
        "usage_available_count": call_count,
        "usage_availability_rate": 1.0,
        "source_artifact_paths": [str(result["source_artifact_path"]) for result in call_results],
        "source_artifact_sha256s": ["a" * 64 for _ in range(call_count)],
        "raw_response_tmp_paths": raw_paths,
        "raw_response_sha256s": ["c" * 64 for _ in range(call_count)],
        "parsed_packet_tmp_paths": parsed_paths,
        "parsed_packet_sha256s": ["d" * 64 for _ in range(call_count)],
        "orchestrator_trace_tmp_paths": trace_paths,
        "orchestrator_trace_sha256s": ["e" * 64 for _ in range(call_count)],
        "input_fixture_hashes": ["a" * 64 for _ in range(call_count)],
        "prompt_hashes": ["b" * 64 for _ in range(call_count)],
        "call_results": call_results,
        "provider_or_backend_called": True,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "scorer_entered": False,
        "actual_outcome_used": False,
        "comparison_result_emitted": False,
        "actual_30d_readiness_status": dry_run.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": dry_run.ACTUAL_30D_NEXT_CHECK_AFTER,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "evidence_layer": dry_run.EVIDENCE_LAYER,
        "direct_llm_interpretation": packet_canary.DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_actual_v3_7_or_v3_8_verdict": True,
            "not_30d_readiness": True,
            "not_oos_science_public_trading_claim": True,
            "not_investment_advice": True,
            "not_provider_benchmark": True,
            "not_model_comparison_claim": True,
        },
        "blocker_reasons": [],
    }
    payload.update(updates)
    return payload


def _call_result(index: int = 0) -> dict[str, object]:
    call_id = f"call_{index + 1:03d}"
    return {
        "run_id": "baseline_v3_8d_gotra_orchestrator_real_token_dry_run_unit",
        "call_id": call_id,
        "generated_at": "2026-06-22T04:00:00Z",
        "backend_name": dry_run.DEFAULT_BACKEND_NAME,
        "model": dry_run.DEFAULT_MODEL,
        "sdk_version": "python-test",
        "api_version": "codex_responses_oauth_streaming",
        "prompt_hash": "b" * 64,
        "input_fixture_hash": "a" * 64,
        "source_artifact_path": f"/tmp/gotra_v3_8d_unit/{call_id}_synthetic_brief.json",
        "source_artifact_sha256": "a" * 64,
        "raw_response_tmp_path": f"/tmp/gotra_v3_8d_unit/{call_id}_raw_response.json",
        "raw_response_sha256": "c" * 64,
        "parsed_packet_tmp_path": f"/tmp/gotra_v3_8d_unit/{call_id}_parsed_packet.json",
        "parsed_packet_sha256": "d" * 64,
        "orchestrator_trace_tmp_path": f"/tmp/gotra_v3_8d_unit/{call_id}_orchestrator_trace.json",
        "orchestrator_trace_sha256": "e" * 64,
        "schema_status": "clean",
        "claim_boundary_status": "clean",
        "provenance_hash_status": "clean",
        "latency_ms": 100 + index,
        "token_usage_input": 8,
        "token_usage_output": 4,
        "token_usage_total": 12,
        "blocker_reasons": [],
    }


def _packet(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": packet_canary.PACKET_SCHEMA,
        "source_run_id": "baseline_v3_8d_gotra_orchestrator_real_token_dry_run_unit",
        "source_artifact_path": "/tmp/gotra_v3_8d_unit/synthetic_brief.json",
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
            }
        ],
        "why_it_matters": "The packet checks whether the schema can express operational structure.",
        "confidence": 0.55,
        "falsification_triggers": ["Ticket categories do not change after process documentation updates."],
        "expected_observable_evidence": ["Mock support queue counts and onboarding checklist completion logs."],
        "counterfactuals": ["A staffing explanation would show timing aligned with coverage gaps."],
        "disagreement_with_price_only": ["The fictional brief uses operations-only signals rather than prices."],
        "evidence_gaps": ["No real customer or future outcome data is included."],
        "uncertainty_decomposition": {"operations": "mock-only", "data_quality": "synthetic brief only"},
        "non_claims": [
            "not a provider canary verdict",
            "not an actual v3.7 or v3.8 verdict",
            "not OOS/science/public/trading claim",
            "not investment advice",
            f"historical direct_llm remains {packet_canary.DIRECT_LLM_INTERPRETATION}",
        ],
        "evidence_layer": packet_canary.EVIDENCE_LAYER,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "provenance": {
            "source_run_id": "baseline_v3_8d_gotra_orchestrator_real_token_dry_run_unit",
            "source_artifact_path": "/tmp/gotra_v3_8d_unit/synthetic_brief.json",
            "backend": packet_canary.DEFAULT_BACKEND_NAME,
            "model": packet_canary.DEFAULT_MODEL,
            "call_id": "call_001",
        },
    }
    payload.update(updates)
    return payload


def _usage() -> dict[str, int]:
    return {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}


def _config(tmp_path: Path, *, summary_fixture: Path | None = None) -> dry_run.DryRunConfig:
    return dry_run.DryRunConfig(
        dry_run_run_id="baseline_v3_8d_gotra_orchestrator_real_token_dry_run_unit",
        output_dir=tmp_path / "runs",
        allow_overwrite=True,
        summary_fixture=summary_fixture,
    )


def _real_config(tmp_path: Path, *, call_count: int) -> dry_run.DryRunConfig:
    return _real_config_with_options(tmp_path, call_count=call_count)


def _real_config_with_options(
    tmp_path: Path,
    *,
    call_count: int,
    base_url: str | None = None,
    auth_json_path: Path | None | object = ...,
) -> dry_run.DryRunConfig:
    resolved_auth_path = _write_auth(tmp_path) if auth_json_path is ... else auth_json_path
    return dry_run.DryRunConfig(
        dry_run_run_id="baseline_v3_8d_gotra_orchestrator_real_token_dry_run_unit",
        output_dir=_tmp_output_dir(tmp_path),
        allow_overwrite=True,
        real_token_dry_run=True,
        auth_json_path=resolved_auth_path,  # type: ignore[arg-type]
        base_url=base_url,
        call_count=call_count,
    )


def _tmp_output_dir(tmp_path: Path) -> Path:
    path = Path("/tmp") / f"gotra_v3_8d_unit_{tmp_path.name}" / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_summary_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "summary_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_auth(tmp_path: Path) -> Path:
    path = tmp_path / "auth.json"
    path.write_text(json.dumps({"auth_placeholder": "test", "account_id": "test-account-id"}), encoding="utf-8")
    return path
