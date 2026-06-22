from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_8m_paired_cognitive_lift_evaluation_readiness as readiness


def test_valid_readiness_package_is_ready(tmp_path: Path) -> None:
    summary = readiness.build_summary(_config(tmp_path))

    assert summary["readiness_status"] == readiness.STATUS_READY, summary["blocker_reasons"]
    assert summary["evidence_layer"] == readiness.EVIDENCE_LAYER
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_canary_executed"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["actual_30d_readiness_status"] == readiness.ACTUAL_30D_READINESS_STATUS
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["cognitive_lift_superiority_verdict_status"] == readiness.SUPERIORITY_STATUS
    assert summary["provider_canary_authorization_status"] == readiness.AUTHORIZATION_STATUS
    assert summary["future_provider_30d_verdict_authorization_checklist"]["call_cap"] == "X"


def test_missing_paired_identity_schema_field_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["paired_sample_identity_schema"]["required_fields"].remove("ticker")
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_SCHEMA
    assert "paired_identity_required_fields_mismatch" in summary["blocker_reasons"]


def test_direct_llm_clean_baseline_wording_blocks_but_negated_caveat_allows(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "direct_llm_parametric_memory_control is not a clean no-future baseline."
    payload = _refresh_digest(payload)
    clean_fixture = _write_fixture(tmp_path, payload)

    clean_summary = readiness.build_summary(_config(tmp_path, fixture=clean_fixture))

    assert clean_summary["readiness_status"] == readiness.STATUS_READY, clean_summary["blocker_reasons"]

    payload["notes"] = "direct_llm_parametric_memory_control is a clean no-future baseline."
    payload = _refresh_digest(payload)
    blocked_fixture = _write_fixture(tmp_path, payload)

    blocked_summary = readiness.build_summary(_config(tmp_path, fixture=blocked_fixture))

    assert blocked_summary["readiness_status"] == readiness.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_unsafe_role_wording" in blocked_summary["blocker_reasons"]


def test_source_stage_canonical_mismatch_or_swapped_commit_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][1]["pr_number"] = payload["source_stages"][0]["pr_number"]
    payload["source_stages"][1]["merge_commit"] = payload["source_stages"][0]["merge_commit"]
    payload["source_stages"][1]["status"] = "TAMPERED_STATUS"
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_MISSING_EVIDENCE
    assert "source_stage_pr_number_canonical_mismatch" in summary["blocker_reasons"]
    assert "source_stage_merge_commit_canonical_mismatch" in summary["blocker_reasons"]
    assert "source_stage_status_canonical_mismatch" in summary["blocker_reasons"]
    assert "source_stage_hashes_mismatch" in summary["blocker_reasons"]


def test_actual_readiness_ready_or_actual_verdict_executable_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    payload["v3_7_actual_verdict_executable"] = True
    payload["maturity_readiness_blockers"]["actual_30d_readiness_status"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    payload["maturity_readiness_blockers"]["actual_v3_7_verdict_executable"] = True
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] in {
        readiness.STATUS_BLOCKED_MATURITY_READINESS,
        readiness.STATUS_BLOCKED_RUNTIME_BOUNDARY,
        readiness.STATUS_BLOCKED_VERDICT_OVERREACH,
    }
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_provider_canary_execution_flag_or_text_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_canary_executed"] = True
    payload["can_say"].append("Provider canary was executed in v3.8M.")
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_canary_executed_not_false" in summary["blocker_reasons"]
    assert "provider_canary_execution_text_claim" in summary["blocker_reasons"]


def test_placeholder_caps_are_not_executable_authorization(tmp_path: Path) -> None:
    payload = _ready_fixture()
    auth = payload["future_provider_30d_verdict_authorization_checklist"]
    auth["execution_allowed"] = True
    auth["provider_canary_execution_allowed"] = True
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    assert "execution_allowed_not_false" in summary["blocker_reasons"]
    assert "provider_canary_execution_allowed_not_false" in summary["blocker_reasons"]


def test_concrete_provider_authorization_missing_metadata_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    auth = payload["future_provider_30d_verdict_authorization_checklist"]
    auth["authorization_status"] = "AUTHORIZED"
    auth["call_cap"] = 3
    auth["token_cap"] = 25000
    auth["cost_cap"] = None
    auth["usage_metadata_required"] = False
    auth["raw_output_boundary"] = "repo/raw.json"
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "authorization_status_not_placeholder" in summary["blocker_reasons"]
    assert "authorization_concrete_caps_not_allowed" in summary["blocker_reasons"]
    assert "usage_metadata_required_not_true" in summary["blocker_reasons"]
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_superiority_public_science_trading_guidance_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["can_say"].append("This proves superiority, names a winner, and gives investment guidance.")
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] in {
        readiness.STATUS_BLOCKED_VERDICT_OVERREACH,
        readiness.STATUS_BLOCKED_CLAIM_BOUNDARY,
    }
    assert "comparative_or_action_guidance_claim" in summary["blocker_reasons"]


def test_raw_full_transcript_or_non_tmp_raw_path_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected"] = {"path": "/home/me/raw.json", "transcript_path": "/var/tmp/full_transcript.txt"}
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_boolean_zero_counters_block_without_crash(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["real_calls_count"] = False
    payload["token_usage_total"] = False
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "real_calls_count_not_numeric_zero" in summary["blocker_reasons"]
    assert "token_usage_total_not_numeric_zero" in summary["blocker_reasons"]


def test_unexpected_field_with_overclaim_or_raw_path_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected"] = {
        "marketing": "public science proof and trading advice",
        "artifact_path": "data/backtest/" + "runs/raw.json",
    }
    payload = _refresh_digest(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = readiness.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["readiness_status"] == readiness.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]
    assert "comparative_or_action_guidance_claim" in summary["blocker_reasons"]


def test_final_manifest_hash_matches_summary_bytes(tmp_path: Path) -> None:
    summary = readiness.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["readiness_status"] == readiness.STATUS_READY
    assert manifest["summary_sha256"] == readiness.sha256_file(Path(summary["summary_path"]))
    assert manifest["provider_or_backend_called"] is False
    assert manifest["real_calls_count"] == 0
    assert manifest["provider_canary_authorization_status"] == readiness.AUTHORIZATION_STATUS


def _config(tmp_path: Path, *, fixture: Path | None = None) -> readiness.ReadinessConfig:
    return readiness.ReadinessConfig(
        readiness_pack_id="baseline_v3_8m_paired_cognitive_lift_evaluation_readiness_test",
        output_dir=Path("/tmp") / "gotra_v3_8m_pytest",
        allow_overwrite=True,
        summary_fixture=fixture,
    )


def _ready_fixture() -> dict:
    cfg = readiness.ReadinessConfig(
        readiness_pack_id="baseline_v3_8m_paired_cognitive_lift_evaluation_readiness_test",
        output_dir=Path("/tmp") / "gotra_v3_8m_pytest",
        allow_overwrite=True,
    )
    summary = readiness.base_summary(
        cfg,
        run_root=cfg.output_dir / cfg.readiness_pack_id,
        status=readiness.STATUS_READY,
    )
    return _refresh_digest(summary)


def _refresh_digest(payload: dict) -> dict:
    stages = [stage for stage in payload.get("source_stages", []) if isinstance(stage, dict)]
    for stage in stages:
        if "metadata_sha256" in stage:
            stage["metadata_sha256"] = readiness.stable_sha256_json(readiness.stage_hash_payload(stage))
    payload["source_stage_hashes"] = {
        stage["stage_id"]: stage.get("metadata_sha256")
        for stage in stages
        if "stage_id" in stage
    }
    payload["source_stage_statuses"] = {
        stage["stage_id"]: stage.get("status")
        for stage in stages
        if "stage_id" in stage
    }
    payload["source_stage_metadata_sha256"] = readiness.stable_sha256_json(stages)
    payload["readiness_package_sha256"] = readiness.readiness_package_digest(payload)
    return payload


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    fixture = tmp_path / "summary_fixture.json"
    fixture.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return fixture
