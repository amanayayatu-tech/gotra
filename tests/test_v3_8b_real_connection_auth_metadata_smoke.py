from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_8b_real_connection_auth_metadata_smoke as smoke


def test_valid_metadata_summary_is_ready(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary())

    summary = smoke.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["smoke_status"] == smoke.STATUS_READY
    assert summary["usage_metadata_available"] is True
    assert summary["provider_or_backend_called"] is True
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False


def test_missing_auth_blocks_pre_http(tmp_path: Path) -> None:
    missing_auth = tmp_path / "missing-auth.json"

    summary = smoke.build_summary(_config(tmp_path, real_connection=True, auth_json_path=missing_auth))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_PRE_HTTP
    assert summary["call_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert "auth_json_not_found" in summary["blocker_reasons"]


def test_auth_failure_blocks_without_secret_leak(tmp_path: Path, monkeypatch) -> None:
    auth_path = _write_auth(tmp_path)

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def complete(self, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("Codex Responses API authentication failed with HTTP 401 Bearer secret-token-value")

    monkeypatch.setattr(smoke, "CodexResponsesCompletionClient", FakeClient)
    summary = smoke.build_summary(_config(tmp_path, real_connection=True, auth_json_path=auth_path))

    assert summary["smoke_status"] == smoke.STATUS_AUTH_FAILED
    assert summary["provider_or_backend_called"] is True
    assert summary["call_count"] == 1
    assert "secret-token-value" not in json.dumps(summary)


def test_usage_missing_after_call_blocks(tmp_path: Path, monkeypatch) -> None:
    auth_path = _write_auth(tmp_path)

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def complete(self, **_kwargs: object) -> dict[str, object]:
            return {"content": "{\"ok\": true}", "usage": None}

    monkeypatch.setattr(smoke, "CodexResponsesCompletionClient", FakeClient)
    summary = smoke.build_summary(_config(tmp_path, real_connection=True, auth_json_path=auth_path, output_dir=_tmp_output_dir(tmp_path)))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_USAGE_METADATA
    assert summary["provider_or_backend_called"] is True
    assert summary["call_count"] == 1
    assert "usage_metadata_missing" in summary["blocker_reasons"]


def test_runtime_true_flags_block(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(formal_lite_entered=True))

    summary = smoke.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "formal_lite_entered_not_false" in summary["blocker_reasons"]


def test_call_count_over_budget_blocks(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(call_count=3))

    summary = smoke.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "call_count_over_budget" in summary["blocker_reasons"]


def test_raw_response_path_outside_tmp_blocks(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(raw_response_tmp_path="/Users/peachy/raw_response.json"))

    summary = smoke.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "raw_response_path_not_tmp" in summary["blocker_reasons"]


def test_secret_redaction_and_secret_summary_blocker(tmp_path: Path) -> None:
    assert smoke.redact_secrets("dummy Bearer abcdefghijklmnop") == "dummy [REDACTED]"
    fixture = _write_summary_fixture(tmp_path, _ready_summary(auth_status="Bearer abcdefghijklmnop"))

    summary = smoke.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "secret_material_detected" in summary["blocker_reasons"]


def test_overclaim_wording_blocks_claim_boundary(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(
        tmp_path,
        _ready_summary(non_claims="This is public science proof and trading advice."),
    )

    summary = smoke.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["smoke_status"] == smoke.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_cli_returns_nonzero_for_blocked_summary(tmp_path: Path) -> None:
    fixture = _write_summary_fixture(tmp_path, _ready_summary(call_count=3))

    status = smoke.main(
        [
            "--smoke-run-id",
            "baseline_v3_8b_real_connection_auth_metadata_smoke_cli_blocked",
            "--summary-fixture",
            str(fixture),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def _ready_summary(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "smoke_status": smoke.STATUS_READY,
        "backend_name": smoke.DEFAULT_BACKEND_NAME,
        "model": smoke.DEFAULT_MODEL,
        "reasoning_effort": smoke.DEFAULT_REASONING_EFFORT,
        "auth_status": "authenticated",
        "latency_ms": 123,
        "usage_metadata_available": True,
        "prompt_input_hash": "a" * 64,
        "response_output_hash": "b" * 64,
        "raw_response_tmp_path": "/tmp/gotra_v3_8b_unit/raw_response_metadata.json",
        "raw_response_sha256": "c" * 64,
        "call_count": 1,
        "max_call_count": 2,
        "token_usage_input": 8,
        "token_usage_output": 4,
        "token_usage_total": 12,
        "token_budget": smoke.DEFAULT_TOKEN_BUDGET,
        "provider_or_backend_called": True,
        "codex_cli_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_readiness_status": smoke.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": smoke.ACTUAL_30D_NEXT_CHECK_AFTER,
        "evidence_layer": smoke.EVIDENCE_LAYER,
        "non_claims": "not research packet; not actual verdict; not OOS/science/public/trading claim; not investment advice",
    }
    payload.update(updates)
    return payload


def _config(
    tmp_path: Path,
    *,
    summary_fixture: Path | None = None,
    real_connection: bool = False,
    auth_json_path: Path | None = None,
    output_dir: Path | None = None,
) -> smoke.SmokeConfig:
    return smoke.SmokeConfig(
        smoke_run_id="baseline_v3_8b_real_connection_auth_metadata_smoke_unit",
        output_dir=output_dir or tmp_path / "runs",
        allow_overwrite=True,
        summary_fixture=summary_fixture,
        real_connection=real_connection,
        auth_json_path=auth_json_path,
    )


def _tmp_output_dir(tmp_path: Path) -> Path:
    path = Path("/tmp") / f"gotra_v3_8b_unit_{tmp_path.name}" / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_summary_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "summary_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_auth(tmp_path: Path) -> Path:
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps({"access_token": "test-access-token", "account_id": "test-account-id"}),
        encoding="utf-8",
    )
    return path
