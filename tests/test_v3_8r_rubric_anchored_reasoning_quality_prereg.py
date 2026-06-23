from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import baseline_v3_8r_rubric_anchored_reasoning_quality_prereg as prereg


def test_valid_rubric_anchored_reasoning_quality_prereg_is_ready(tmp_path: Path) -> None:
    summary = prereg.build_summary(_config(tmp_path))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_READY
    assert summary["prereg_status"] == prereg.STATUS_READY
    assert summary["actual_30d_readiness_status"] == prereg.ACTUAL_30D_READINESS_STATUS
    assert summary["cognitive_lift_superiority_verdict_status"] == prereg.SUPERIORITY_STATUS
    assert summary["direct_llm_interpretation"] == prereg.DIRECT_INTERPRETATION
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["provider_or_backend_called_for_prereg"] is False
    assert summary["provider_canary_executed_for_prereg"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["raw_output_boundary"] == prereg.RAW_OUTPUT_BOUNDARY
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["blocker_reasons"] == []


def test_direct_llm_clean_no_future_no_memory_baseline_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["direct_llm_clean_baseline"] = True
    payload["notes"] = "direct_llm_parametric_memory_control is a clean no-future no-memory baseline."
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_clean_baseline_not_false" in summary["blocker_reasons"]
    assert "direct_llm_unsafe_role_wording" in summary["blocker_reasons"]


def test_direct_llm_as_only_clean_comparator_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["primary_comparison"]["clean_comparators"] = [prereg.DIRECT_INTERPRETATION]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_COMPARATOR_BOUNDARY
    assert "only_clean_comparator_is_parametric_control" in summary["blocker_reasons"]


@pytest.mark.parametrize(
    ("field", "expected_status", "expected_rule"),
    [
        ("rubric_sha256", prereg.STATUS_BLOCKED_RUBRIC_LOCK, "rubric_sha256_missing_or_invalid"),
        ("source_artifact_sha256", prereg.STATUS_BLOCKED_PREREG, "source_artifact_sha256_missing_or_invalid"),
        ("probe_rule_sha256", prereg.STATUS_BLOCKED_PREREG, "probe_rule_sha256_missing_or_invalid"),
    ],
)
def test_missing_required_digest_blocks(
    tmp_path: Path,
    field: str,
    expected_status: str,
    expected_rule: str,
) -> None:
    payload = _ready_fixture()
    payload.pop(field)
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == expected_status
    assert expected_rule in summary["blocker_reasons"]


def test_effect_fields_before_eligibility_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["effect_summary"] = {
        "emitted": True,
        "values": {"effect_estimate": 0.42, "confidence_interval": [0.1, 0.8]},
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    assert "effect_summary_emitted_before_eligibility" in summary["blocker_reasons"]
    assert "effect_estimate_before_eligibility" in summary["blocker_reasons"]


def test_raw_path_outside_tmp_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["raw_paths"] = ["/var/tmp/gotra_v3_8r/raw_output.json"]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_RAW_BOUNDARY
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_raw_full_transcript_in_repo_facing_field_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["repo_facing_summary"] = "full transcript: raw output copied into this repo-facing field"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "repo_raw_or_full_transcript_reference" in summary["blocker_reasons"]


def test_market_public_trading_investment_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["claim_text"] = (
        "GOTRA proved market edge with P&L, public science proof, trading advice, "
        "and investment advice."
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "claim_boundary_forbidden_wording" in summary["blocker_reasons"]


def test_attempt_to_change_actual_or_cognitive_lift_verdict_fields_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "ACTUAL_30D_VERDICT_READY"
    payload["cognitive_lift_superiority_verdict_status"] = "COGNITIVE_LIFT_SUPERIORITY_VERDICT_READY"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "cognitive_lift_superiority_status_invalid" in summary["blocker_reasons"]


def test_raw_count_used_as_independent_n_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["effective_n_policy"]["raw_count_used_as_independent_n"] = True
    payload["work_unit_counts"]["clean_paired_unit_count"] = 200
    payload["work_unit_counts"]["effective_independent_pair_count"] = 200
    payload["work_unit_counts"]["effective_independent_pair_count_source"] = "raw_count"
    payload["work_unit_counts"]["raw_count_used_as_independent_n"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_EFFECTIVE_N
    assert "raw_count_used_as_independent_n" in summary["blocker_reasons"]
    assert "effective_n_source_is_raw_count" in summary["blocker_reasons"]


def test_provider_codex_or_formal_execution_flags_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called_for_prereg"] = True
    payload["codex_cli_new_call"] = True
    payload["formal_lite_entered"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_BLOCKED_PROVIDER_AUTHORIZATION
    assert "provider_or_backend_called_for_prereg_not_false" in summary["blocker_reasons"]
    assert "codex_cli_new_call_not_false" in summary["blocker_reasons"]
    assert "formal_lite_entered_not_false" in summary["blocker_reasons"]


def test_manifest_hash_matches_written_summary(tmp_path: Path) -> None:
    summary = prereg.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["rubric_anchored_reasoning_quality_verdict_status"] == prereg.STATUS_READY
    assert manifest["summary_sha256"] == prereg.sha256_file(Path(summary["summary_path"]))
    assert manifest["provider_or_backend_called_for_prereg"] is False
    assert manifest["codex_cli_new_call"] is False
    assert manifest["formal_lite_entered"] is False
    assert manifest["raw_output_boundary"] == prereg.RAW_OUTPUT_BOUNDARY


def _config(tmp_path: Path, *, fixture: Path | None = None) -> prereg.PreregConfig:
    return prereg.PreregConfig(
        preregistration_id="gotra_v3_8r_rubric_reasoning_quality_20260622T000000Z",
        output_dir=Path("/tmp") / f"gotra_v3_8r_pytest_{tmp_path.name}",
        allow_overwrite=True,
        summary_fixture=fixture,
    )


def _ready_fixture() -> dict[str, object]:
    cfg = prereg.PreregConfig(
        preregistration_id="gotra_v3_8r_rubric_reasoning_quality_20260622T000000Z",
        output_dir=Path("/tmp") / "gotra_v3_8r_pytest_fixture_source",
        allow_overwrite=True,
    )
    summary = prereg.build_summary(cfg)
    payload = copy.deepcopy(summary)
    for key in ("preregistration_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    fixture = tmp_path / "summary_fixture.json"
    fixture.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return fixture
