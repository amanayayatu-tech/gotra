from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_7h_claim_boundary_regression as regression


def test_valid_internal_fixture_is_ready(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture())

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_READY
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["claim_boundary_status"] == "clean"
    assert summary["runtime_boundary_status"] == "clean"
    assert summary["digest_boundary_status"] == "clean"
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["evidence_layer"] == regression.EVIDENCE_LAYER


def test_status_like_ready_for_forward_live_verdict_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["readiness_status"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_OVERCLAIM
    assert "ready_for_forward_live_verdict_status" in summary["blocker_reasons"]


def test_missing_explicit_runtime_boundary_flag_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload.pop("provider_or_backend_called")
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "missing_provider_or_backend_called" in summary["blocker_reasons"]


def test_true_runtime_or_verdict_flag_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["v3_7_actual_verdict_executable"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_short_horizon_claiming_actual_30d_verdict_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["statement"] = "short-horizon canary is equivalent to actual 30D v3.7 verdict ready"
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_OVERCLAIM
    assert "short_horizon_or_prep_as_actual_30d_verdict" in summary["blocker_reasons"]


def test_unmarked_direct_llm_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["statement"] = "direct_llm is the clean no-future baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_OVERCLAIM
    assert summary["direct_llm_blocker_count"] > 0


def test_oos_public_trading_winner_claim_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["claim"] = "This is OOS public science proof and trading advice with a winner claim."
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] > 0


def test_generic_artifact_path_field_blocks_without_reading_content(tmp_path: Path, monkeypatch) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["artifact_path"] = "data/backtest/runs/raw.json"
    fixture = _write_fixture(tmp_path, payload)
    original_read_text = Path.read_text

    def fail_read(path: Path, *args: object, **kwargs: object) -> str:
        if "data/backtest/runs" in str(path):
            raise AssertionError("forbidden artifact content should not be read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_negative_test_fixture_text_allowed_only_with_explicit_context(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["text"] = "This fixture says v3.7 verdict ready and OOS public science proof."
    payload["documents"][0]["negative_test_context"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_READY
    assert summary["negative_test_context_count"] == 1


def test_negative_text_without_context_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["text"] = "This fixture says v3.7 verdict ready and OOS public science proof."
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_OVERCLAIM


def test_digest_omission_of_boundary_fields_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["digest_declarations"][0]["covered_fields"] = ["nodes", "edges"]
    fixture = _write_fixture(tmp_path, payload)

    summary = regression.build_summary(_config(tmp_path, fixture))

    assert summary["regression_status"] == regression.STATUS_BLOCKED_DIGEST_BOUNDARY
    assert "boundary_critical_digest_fields_omitted" in summary["blocker_reasons"]


def test_manifest_digest_is_verifiable(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture())
    summary = regression.build_summary(_config(tmp_path, fixture))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert summary["regression_status"] == regression.STATUS_READY
    assert manifest["summary_sha256"] == regression.sha256_file(Path(summary["summary_path"]))
    assert manifest["provider_or_backend_called"] is False
    assert manifest["v3_7_actual_verdict_executable"] is False


def test_cli_returns_nonzero_for_blockers(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["documents"][0]["payload"]["verdict_status"] = "actual v3.7 verdict executable"
    fixture = _write_fixture(tmp_path, payload)

    status = regression.main(
        [
            "--regression-run-id",
            "baseline_v3_7h_claim_boundary_regression_cli_blocked",
            "--fixture",
            str(fixture),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def _valid_fixture(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_layer": regression.EVIDENCE_LAYER,
        "actual_30d_readiness_status": regression.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": regression.ACTUAL_30D_NEXT_CHECK_AFTER,
        "direct_llm_interpretation": regression.DIRECT_LLM_INTERPRETATION,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "digest_declarations": [
            {
                "digest_name": "graph_content_sha256",
                "covered_fields": list(regression.BOUNDARY_CRITICAL_DIGEST_FIELDS) + ["nodes", "edges"],
            }
        ],
        "documents": [
            {
                "path": "docs/GOTRA_V3_7H_SAFE_FIXTURE.md",
                "text": "engineering/internal only; not OOS; not science; not public; not trading; v3_7_allowed=false",
                "require_boundary_flags": True,
                "payload": {
                    "evidence_layer": regression.EVIDENCE_LAYER,
                    "actual_30d_readiness_status": regression.ACTUAL_30D_READINESS_STATUS,
                    "status": "ENGINEERING_INTERNAL_GUARD_READY",
                    "provider_or_backend_called": False,
                    "codex_cli_new_call": False,
                    "codex_cli_called": False,
                    "formal_lite_entered": False,
                    "v3_7_actual_verdict_executable": False,
                    "v3_7_actual_verdict_executed": False,
                    "direct_llm_interpretation": regression.DIRECT_LLM_INTERPRETATION,
                    "summary_path": "docs/GOTRA_V3_7G_PROVENANCE_GRAPH_HASH_INDEX_VALIDATOR_RESULT_20260622.md",
                    "non_claims": "not actual 30D verdict; not OOS/science/public/trading claim",
                },
            }
        ],
    }
    payload.update(updates)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "claim_boundary_regression_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, fixture: Path) -> regression.RegressionConfig:
    return regression.RegressionConfig(
        regression_run_id="baseline_v3_7h_claim_boundary_regression_unit",
        output_dir=tmp_path / "runs",
        fixture=fixture,
        allow_overwrite=True,
    )
