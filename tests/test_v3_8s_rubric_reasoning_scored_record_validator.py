from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import baseline_v3_8s_rubric_reasoning_scored_record_validator as scored


def test_valid_scored_record_validation_is_evaluation_ready(tmp_path: Path) -> None:
    summary = scored.build_summary(_config(tmp_path))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == scored.STATUS_READY
    assert summary["evaluation_status"] == scored.STATUS_READY
    assert summary["actual_30d_readiness_status"] == scored.ACTUAL_30D_READINESS_STATUS
    assert summary["cognitive_lift_superiority_verdict_status"] == scored.SUPERIORITY_STATUS
    assert summary["direct_llm_interpretation"] == scored.DIRECT_INTERPRETATION
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_or_backend_called_for_evaluation"] is False
    assert summary["codex_cli_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["raw_output_boundary"] == scored.RAW_OUTPUT_BOUNDARY
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["blocker_reasons"] == []


def test_missing_required_scored_record_field_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"][0].pop("prompt_hash")
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_SCHEMA
    assert "scored_record_missing_field" in summary["blocker_reasons"]


def test_invalid_64_hex_hash_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"][0]["arm_identity_unblinded_hash"] = "not-a-64-hex"
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_SCHEMA
    assert "arm_identity_unblinded_hash_invalid_64_hex" in summary["blocker_reasons"]


def test_dimension_score_outside_range_and_non_half_step_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"][0]["dimension_scores"]["problem_decomposition"] = 5.5
    payload["scored_records"][1]["dimension_scores"]["evidence_grounding"] = 3.25
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_SCHEMA
    assert "dimension_score_invalid_range_or_step" in summary["blocker_reasons"]


def test_composite_score_mismatch_from_locked_equal_weights_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"][0]["composite_score"] = 4.0
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_SCHEMA
    assert "composite_score_mismatch" in summary["blocker_reasons"]


def test_scoring_blind_false_or_raw_arm_identity_leak_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"][0]["scoring_blind"] = False
    payload["scored_records"][1]["scorer_facing_metadata"]["notes"] = "This scorer-facing record is full_gotra."
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_BLIND_SCORING
    assert "scoring_blind_not_true" in summary["blocker_reasons"]
    assert "scorer_facing_raw_arm_identity_leak" in summary["blocker_reasons"]


def test_paired_identity_mismatch_across_arms_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    for record in payload["scored_records"]:
        if record["arm_identity_unblinded_hash"] == scored.arm_hash("ksana_real_research"):
            record["ticker"] = "MSFT"
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_IDENTITY
    assert "paired_identity_mismatch_across_candidate_arms" in summary["blocker_reasons"]


def test_direct_llm_clean_no_future_no_memory_baseline_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["direct_llm_clean_baseline"] = True
    payload["notes"] = "direct_llm_parametric_memory_control is a clean no-future no-memory baseline."
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_clean_baseline_not_false" in summary["blocker_reasons"]
    assert "direct_llm_unsafe_role_wording" in summary["blocker_reasons"]


def test_direct_llm_as_only_clean_comparator_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["clean_comparator_policy"]["clean_comparator_hashes"] = [scored.arm_hash(scored.DIRECT_INTERPRETATION)]
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_COMPARATOR_BOUNDARY
    assert "only_clean_comparator_is_parametric_control" in summary["blocker_reasons"]


def test_raw_path_outside_tmp_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"][0]["raw_output_tmp_path"] = "/var/tmp/gotra_v3_8s/raw_output.json"
    payload["scored_records"][0]["raw_output_sha256"] = scored.synthetic_hash("raw-output")
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_RAW_BOUNDARY
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_raw_full_transcript_in_repo_facing_field_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["repo_facing_summary"] = "full transcript: raw output copied into this repo-facing field"
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "repo_raw_or_full_transcript_reference" in summary["blocker_reasons"]


def test_effect_fields_before_eligibility_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["effect_summary"] = {
        "emitted": True,
        "values": {"effect_estimate": 0.5, "confidence_interval": [0.1, 0.9]},
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    assert "effect_summary_emitted_before_eligibility" in summary["blocker_reasons"]
    assert "effect_estimate_before_eligibility" in summary["blocker_reasons"]


def test_raw_count_used_as_independent_n_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["effective_n_policy"]["raw_count_used_as_independent_n"] = True
    payload["work_unit_counts"]["effective_independent_pair_count_source"] = "raw_count"
    payload["work_unit_counts"]["raw_count_used_as_independent_n"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_EFFECTIVE_N
    assert "raw_count_used_as_independent_n" in summary["blocker_reasons"]
    assert "effective_n_source_is_raw_count" in summary["blocker_reasons"]


def test_scorer_reliability_failure_with_only_one_scorer_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["scored_records"] = [
        record for record in payload["scored_records"] if record["scorer_id"] == "scorer_alpha"
    ]
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_SCORER_RELIABILITY
    assert "scorer_count_below_minimum" in summary["blocker_reasons"]


def test_market_pnl_public_science_trading_investment_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["claim_text"] = (
        "GOTRA proved market edge with P&L, public science proof, trading advice, "
        "and investment advice."
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "claim_boundary_forbidden_wording" in summary["blocker_reasons"]


def test_attempt_to_change_actual_or_cognitive_lift_verdict_fields_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "ACTUAL_30D_VERDICT_READY"
    payload["cognitive_lift_superiority_verdict_status"] = "COGNITIVE_LIFT_SUPERIORITY_VERDICT_READY"
    fixture = _write_fixture(tmp_path, payload)

    summary = scored.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["evaluation_status"] == scored.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "cognitive_lift_superiority_status_invalid" in summary["blocker_reasons"]


def _config(tmp_path: Path, *, fixture: Path | None = None) -> scored.ScoredRecordConfig:
    return scored.ScoredRecordConfig(
        validation_id="gotra_v3_8s_rubric_reasoning_scored_records_20260622T000000Z",
        output_dir=Path("/tmp") / f"gotra_v3_8s_pytest_{tmp_path.name}",
        allow_overwrite=True,
        summary_fixture=fixture,
    )


def _ready_fixture() -> dict[str, object]:
    config = scored.ScoredRecordConfig(
        validation_id="gotra_v3_8s_rubric_reasoning_scored_records_20260622T000000Z",
        output_dir=Path("/tmp") / "gotra_v3_8s_pytest_fixture_source",
        allow_overwrite=True,
    )
    summary = scored.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("validation_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    fixture = tmp_path / "summary_fixture.json"
    fixture.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return fixture
