from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_8l_evidence_bounded_conclusion_template as template


def test_valid_template_is_ready(tmp_path: Path) -> None:
    summary = template.build_summary(_config(tmp_path))

    assert summary["template_status"] == template.STATUS_READY, summary["blocker_reasons"]
    assert summary["evidence_layer"] == template.EVIDENCE_LAYER
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_canary_executed"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["actual_30d_readiness_status"] == template.ACTUAL_30D_READINESS_STATUS
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["cognitive_lift_superiority_verdict_status"] == template.SUPERIORITY_STATUS
    assert summary["direct_llm_interpretation"] == template.DIRECT_INTERPRETATION
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["source_real_calls_count_total"] == 7
    assert summary["source_token_usage_total"] == 13369


def test_superiority_or_external_claim_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["allowed_conclusion_text"].append(
        "This proves cognitive lift superiority, names a winner, and gives trading advice."
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] in {
        template.STATUS_BLOCKED_VERDICT_OVERREACH,
        template.STATUS_BLOCKED_CLAIM_BOUNDARY,
    }
    assert summary["claim_boundary_status"] == "blocked" or summary["verdict_boundary_status"] == "blocked"


def test_missing_runtime_boundary_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = None
    payload["v3_7_actual_verdict_executable"] = True
    payload["provider_or_backend_called"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]


def test_direct_llm_clean_baseline_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["direct_llm_clean_baseline"] = True
    payload["notes"] = "direct_llm_parametric_memory_control is a clean no-future baseline."
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_clean_baseline_not_false" in summary["blocker_reasons"]


def test_negated_direct_llm_caveat_is_allowed(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "direct_llm_parametric_memory_control is not a clean no-future baseline."
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_READY, summary["blocker_reasons"]
    assert summary["direct_llm_boundary_status"] == "clean"


def test_missing_required_source_stage_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"] = payload["source_stages"][:-1]
    payload = _refresh_digests(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_BLOCKED_MISSING_EVIDENCE
    assert "source_stage_order_mismatch" in summary["blocker_reasons"]
    assert "source_stage_set_mismatch" in summary["blocker_reasons"]


def test_wrong_canonical_pr_or_merge_commit_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][1]["pr_number"] = 66
    payload["source_stages"][1]["merge_commit"] = payload["source_stages"][0]["merge_commit"]
    payload = _refresh_digests(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_BLOCKED_MISSING_EVIDENCE
    assert "source_stage_pr_mismatch" in summary["blocker_reasons"]
    assert "source_stage_merge_commit_mismatch" in summary["blocker_reasons"]


def test_unexpected_overclaim_field_is_scanned(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected"] = {"marketing": "public science proof with investment advice"}
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] in {
        template.STATUS_BLOCKED_VERDICT_OVERREACH,
        template.STATUS_BLOCKED_CLAIM_BOUNDARY,
    }
    assert summary["claim_boundary_status"] == "blocked"


def test_unexpected_raw_or_forbidden_path_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected"] = {
        "path": "data/backtest/" + "runs/raw.json",
        "raw_tmp_path": "raw_payload.json",
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_raw_full_transcript_or_non_tmp_path_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["transcript_path"] = "/var/tmp/full_transcript.txt"
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] == template.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_malformed_status_calls_tokens_return_structured_schema_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][0]["real_calls_count"] = ["bad"]
    payload["source_stages"][0]["token_usage_total"] = "86"
    payload["source_stages"][0]["status"] = 123
    payload = _refresh_digests(payload)
    fixture = _write_fixture(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["template_status"] in {
        template.STATUS_BLOCKED_SCHEMA,
        template.STATUS_BLOCKED_MISSING_EVIDENCE,
    }
    assert "real_calls_count_invalid" in summary["blocker_reasons"]
    assert "token_usage_total_invalid" in summary["blocker_reasons"]
    assert "source_stage_status_mismatch" in summary["blocker_reasons"]


def test_final_manifest_hash_matches_summary_bytes(tmp_path: Path) -> None:
    summary = template.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["template_status"] == template.STATUS_READY
    assert manifest["summary_sha256"] == template.sha256_file(Path(summary["summary_path"]))
    assert manifest["provider_or_backend_called"] is False
    assert manifest["real_calls_count"] == 0


def _config(tmp_path: Path, *, fixture: Path | None = None) -> template.TemplateConfig:
    return template.TemplateConfig(
        template_id="baseline_v3_8l_evidence_bounded_conclusion_template_test",
        output_dir=Path("/tmp") / "gotra_v3_8l_pytest",
        allow_overwrite=True,
        summary_fixture=fixture,
    )


def _ready_fixture() -> dict:
    cfg = template.TemplateConfig(
        template_id="baseline_v3_8l_evidence_bounded_conclusion_template_test",
        output_dir=Path("/tmp") / "gotra_v3_8l_pytest",
        allow_overwrite=True,
    )
    summary = template.base_summary(
        cfg,
        run_root=cfg.output_dir / cfg.template_id,
        status=template.STATUS_READY,
    )
    return _refresh_digests(summary)


def _refresh_digests(payload: dict) -> dict:
    stages = [stage for stage in payload.get("source_stages", []) if isinstance(stage, dict)]
    for stage in stages:
        if "metadata_sha256" in stage:
            stage["metadata_sha256"] = template.stable_sha256_json(template.stage_hash_payload(stage))
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
    payload["source_stage_metadata_sha256"] = template.stable_sha256_json(stages)
    payload["source_real_calls_count_total"] = sum(
        stage.get("real_calls_count", 0)
        for stage in stages
        if isinstance(stage.get("real_calls_count"), int) and not isinstance(stage.get("real_calls_count"), bool)
    )
    payload["source_token_usage_total"] = sum(
        stage.get("token_usage_total", 0)
        for stage in stages
        if isinstance(stage.get("token_usage_total"), int) and not isinstance(stage.get("token_usage_total"), bool)
    )
    payload["conclusion_template_sha256"] = template.conclusion_template_digest(payload)
    return payload


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    fixture = tmp_path / "summary_fixture.json"
    fixture.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return fixture
