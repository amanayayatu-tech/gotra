from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import baseline_v3_8t_rubric_reasoning_effective_n_preflight as preflight


def test_valid_effective_n_preflight_is_eligibility_ready(tmp_path: Path) -> None:
    summary = preflight.build_summary(_config(tmp_path))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == preflight.STATUS_READY
    assert summary["eligibility_preflight_status"] == preflight.STATUS_READY
    assert summary["actual_30d_readiness_status"] == preflight.ACTUAL_30D_READINESS_STATUS
    assert summary["cognitive_lift_superiority_verdict_status"] == preflight.SUPERIORITY_STATUS
    assert summary["direct_llm_interpretation"] == preflight.DIRECT_INTERPRETATION
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_or_backend_called_for_preflight"] is False
    assert summary["codex_cli_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["raw_output_boundary"] == preflight.RAW_OUTPUT_BOUNDARY
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["work_unit_counts"]["clean_paired_unit_count"] == 36
    assert summary["work_unit_counts"]["effective_independent_pair_count"] == 30
    assert summary["work_unit_counts"]["effective_independent_pair_count_source"] == "cluster_bootstrap"
    assert all(summary["statistical_eligibility"].values())
    assert summary["effect_summary"] == {"emitted": False, "values": None}
    assert summary["blocker_reasons"] == []


def test_missing_required_candidate_arm_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["clean_paired_units"][0]["candidate_arms"] = ["full_gotra"]
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_IDENTITY
    assert "paired_required_candidate_arm_missing" in summary["blocker_reasons"]


def test_missing_clean_non_direct_reference_comparator_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["clean_comparator_policy"]["selected_clean_references"] = []
    payload["clean_paired_units"][0]["clean_reference_arm"] = None
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_COMPARATOR_BOUNDARY
    assert "non_direct_clean_comparator_missing" in summary["blocker_reasons"]


def test_only_direct_llm_comparator_blocks_with_comparator_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["clean_comparator_policy"]["selected_clean_references"] = [preflight.DIRECT_INTERPRETATION]
    payload["clean_paired_units"][0]["clean_reference_arm"] = preflight.DIRECT_INTERPRETATION
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_COMPARATOR_BOUNDARY
    assert "only_clean_comparator_is_parametric_control" in summary["blocker_reasons"]


def test_raw_count_used_as_independent_n_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["effective_n_policy"]["raw_count_used_as_independent_n"] = True
    payload["work_unit_counts"]["effective_independent_pair_count"] = payload["work_unit_counts"][
        "clean_paired_unit_count"
    ]
    payload["work_unit_counts"]["effective_independent_pair_count_source"] = "raw_count"
    payload["work_unit_counts"]["raw_count_used_as_independent_n"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_EFFECTIVE_N
    assert "raw_count_used_as_independent_n" in summary["blocker_reasons"]
    assert "effective_n_source_is_raw_count" in summary["blocker_reasons"]


def test_effective_n_below_preregistered_minimum_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["work_unit_counts"]["effective_independent_pair_count"] = 29
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_EFFECTIVE_N
    assert "effective_n_below_preregistered_minimum" in summary["blocker_reasons"]


def test_missing_clustering_dimensions_or_estimator_list_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["effective_n_policy"]["clustering_dimensions"] = ["ticker", "decision_date"]
    payload["effective_n_policy"]["effective_n_estimator"] = ["cluster_bootstrap"]
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_EFFECTIVE_N
    assert "clustering_dimensions_missing_or_invalid" in summary["blocker_reasons"]
    assert "effective_n_estimator_list_missing_or_invalid" in summary["blocker_reasons"]


def test_eligibility_flags_not_all_true_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["statistical_eligibility"]["sample_size_ready"] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    assert "statistical_eligibility_flag_not_true" in summary["blocker_reasons"]


@pytest.mark.parametrize(
    ("effect_key", "effect_value"),
    [
        ("p_value", 0.04),
        ("effect_estimate", 0.33),
        ("confidence_interval", [0.1, 0.6]),
        ("bootstrap_interval", [0.1, 0.6]),
        ("hac_adjusted_standard_error", 0.07),
        ("winner", "full_gotra"),
        ("proved", True),
        ("established", True),
        ("outperformed", True),
    ],
)
def test_effect_fields_before_eligibility_block(tmp_path: Path, effect_key: str, effect_value: object) -> None:
    payload = _ready_fixture()
    payload["statistical_eligibility"]["sample_size_ready"] = False
    payload["effect_summary"] = {"emitted": True, "values": {effect_key: effect_value}}
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_STATISTICAL_ELIGIBILITY
    assert "effect_summary_emitted_before_eligibility" in summary["blocker_reasons"]
    assert f"{effect_key}_before_eligibility" in summary["blocker_reasons"]


def test_raw_path_outside_tmp_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["raw_paths"] = ["/var/tmp/gotra_v3_8t/raw_output.json"]
    payload["clean_paired_units"][0]["raw_paths"] = ["/var/tmp/gotra_v3_8t/raw_output.json"]
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_RAW_BOUNDARY
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_raw_full_transcript_in_repo_facing_field_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["repo_facing_summary"] = "full transcript: raw output copied into this repo-facing field"
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "repo_raw_or_full_transcript_reference" in summary["blocker_reasons"]


def test_scorer_reliability_ready_false_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["statistical_eligibility"]["scorer_reliability_ready"] = False
    payload["scorer_reliability"]["scorer_reliability_ready"] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_SCORER_RELIABILITY
    assert "scorer_reliability_ready_false" in summary["blocker_reasons"]


@pytest.mark.parametrize(
    ("flag", "expected_status", "expected_rule"),
    [
        ("claim_boundary_clean", preflight.STATUS_BLOCKED_CLAIM_BOUNDARY, "claim_boundary_clean_false"),
        ("direct_llm_boundary_clean", preflight.STATUS_BLOCKED_DIRECT_BOUNDARY, "direct_llm_boundary_clean_false"),
        ("comparator_boundary_clean", preflight.STATUS_BLOCKED_COMPARATOR_BOUNDARY, "comparator_boundary_clean_false"),
        ("raw_artifact_boundary_clean", preflight.STATUS_BLOCKED_RAW_BOUNDARY, "raw_artifact_boundary_clean_false"),
    ],
)
def test_boundary_eligibility_flags_false_block(
    tmp_path: Path,
    flag: str,
    expected_status: str,
    expected_rule: str,
) -> None:
    payload = _ready_fixture()
    payload["statistical_eligibility"][flag] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == expected_status
    assert expected_rule in summary["blocker_reasons"]


def test_market_pnl_public_science_trading_investment_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["claim_text"] = (
        "GOTRA proved market edge with P&L, public science proof, trading signal, "
        "and investment advice."
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "claim_boundary_forbidden_wording" in summary["blocker_reasons"]


def test_attempt_to_change_actual_or_cognitive_lift_verdict_fields_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "ACTUAL_30D_VERDICT_READY"
    payload["cognitive_lift_superiority_verdict_status"] = "COGNITIVE_LIFT_SUPERIORITY_VERDICT_READY"
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "cognitive_lift_superiority_status_invalid" in summary["blocker_reasons"]


def test_attempt_to_output_bounded_verdict_or_public_claim_at_preflight_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["rubric_anchored_reasoning_quality_verdict_status"] = preflight.STATUS_BOUNDED_VERDICT
    payload["effect_summary"] = {"emitted": True, "values": None, "status": preflight.STATUS_BOUNDED_VERDICT}
    payload["claim_text"] = "public claim: bounded rubric-anchored reasoning-quality verdict is ready."
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "bounded_or_public_verdict_status_not_allowed_at_preflight" in summary["blocker_reasons"]
    assert "bounded_verdict_status_not_allowed_at_preflight" in summary["blocker_reasons"]


def test_provider_codex_or_formal_execution_flags_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called_for_preflight"] = True
    payload["codex_cli_new_call"] = True
    payload["formal_lite_entered"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = preflight.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["eligibility_preflight_status"] == preflight.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_for_preflight_not_false" in summary["blocker_reasons"]
    assert "codex_cli_new_call_not_false" in summary["blocker_reasons"]
    assert "formal_lite_entered_not_false" in summary["blocker_reasons"]


def test_manifest_hash_matches_written_summary(tmp_path: Path) -> None:
    summary = preflight.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["rubric_anchored_reasoning_quality_verdict_status"] == preflight.STATUS_READY
    assert manifest["eligibility_preflight_status"] == preflight.STATUS_READY
    assert manifest["summary_sha256"] == preflight.prereg.sha256_file(Path(summary["summary_path"]))
    assert manifest["provider_or_backend_called"] is False
    assert manifest["codex_cli_new_call"] is False
    assert manifest["formal_lite_entered"] is False
    assert manifest["raw_output_boundary"] == preflight.RAW_OUTPUT_BOUNDARY


def _config(tmp_path: Path, *, fixture: Path | None = None) -> preflight.EffectiveNPreflightConfig:
    return preflight.EffectiveNPreflightConfig(
        preflight_id="gotra_v3_8t_rubric_reasoning_effective_n_preflight_20260622T000000Z",
        output_dir=Path("/tmp") / f"gotra_v3_8t_pytest_{tmp_path.name}",
        allow_overwrite=True,
        summary_fixture=fixture,
    )


def _ready_fixture() -> dict[str, object]:
    cfg = preflight.EffectiveNPreflightConfig(
        preflight_id="gotra_v3_8t_rubric_reasoning_effective_n_preflight_20260622T000000Z",
        output_dir=Path("/tmp") / "gotra_v3_8t_pytest_fixture_source",
        allow_overwrite=True,
    )
    summary = preflight.build_summary(cfg)
    payload = copy.deepcopy(summary)
    for key in ("preflight_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    fixture = tmp_path / "summary_fixture.json"
    fixture.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return fixture
