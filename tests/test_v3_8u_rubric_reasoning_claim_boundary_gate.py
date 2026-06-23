from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import baseline_v3_8u_rubric_reasoning_claim_boundary_gate as gate


LOCAL_READINESS_TEXT = (
    "当前证据支持 GOTRA rubric-anchored reasoning-quality evaluation 的 "
    "prereg/schema/tooling readiness。尚未满足 effective-N、scorer reliability、"
    "clustered statistical eligibility 和 claim-boundary fan-in 条件, 因此不得输出 "
    "bounded reasoning-quality verdict。原 cognitive_lift_superiority_verdict_status "
    "仍为 NOT_YET_VERDICT_READY, actual_30d_readiness_status 仍为 DATA_NOT_MATURED。"
)
LOCAL_FIXTURE_TEXT = (
    "本地 fixture/schema 验证显示 paired identity、locked rubric、direct_llm boundary、"
    "raw-output boundary 和 claim-boundary 守门可执行。该证据层级为 local checks / "
    "engineering readiness, 不构成真实 reasoning-quality superiority, 也不构成 30D "
    "outcome verdict。"
)


def test_valid_claim_boundary_gate_is_eligibility_ready(tmp_path: Path) -> None:
    summary = gate.build_summary(_config(tmp_path))

    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == gate.STATUS_READY
    assert summary["claim_boundary_gate_status"] == gate.STATUS_READY
    assert summary["conclusion_template_ready"] is True
    assert summary["claim_boundary_gate_ready"] is True
    assert summary["actual_30d_readiness_status"] == gate.ACTUAL_30D_READINESS_STATUS
    assert summary["cognitive_lift_superiority_verdict_status"] == gate.SUPERIORITY_STATUS
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["direct_llm_interpretation"] == gate.DIRECT_INTERPRETATION
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_or_backend_called_for_claim_gate"] is False
    assert summary["codex_cli_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["raw_output_boundary"] == gate.RAW_OUTPUT_BOUNDARY
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert set(gate.REQUIRED_EVIDENCE_LAYERS).issubset(summary["evidence_layers"])
    assert set(gate.REQUIRED_CONCLUSION_TEMPLATE_KEYS).issubset(summary["conclusion_templates"])
    assert summary["blocker_reasons"] == []


@pytest.mark.parametrize("field", ["can_say", "cannot_say", "non_claims"])
def test_missing_can_say_cannot_say_or_non_claims_blocks(tmp_path: Path, field: str) -> None:
    payload = _ready_fixture()
    payload.pop(field)
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_SCHEMA
    assert "summary_missing_field" in summary["blocker_reasons"]


def test_allowed_local_readiness_text_is_accepted(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["allowed_conclusion_text"] = [LOCAL_READINESS_TEXT, LOCAL_FIXTURE_TEXT]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_READY, summary["blocker_reasons"]
    assert summary["claim_boundary_status"] == "clean"
    assert summary["direct_llm_boundary_status"] == "clean"


def test_direct_llm_clean_no_future_no_memory_baseline_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["direct_llm_clean_baseline"] = True
    payload["claim_text"] = (
        "direct_llm_parametric_memory_control is a clean no-future/no-memory baseline."
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_clean_baseline_not_false" in summary["blocker_reasons"]
    assert "direct_llm_unsafe_role_wording" in summary["blocker_reasons"]


def test_direct_llm_as_only_clean_comparator_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["clean_comparator_policy"]["selected_clean_references"] = [gate.DIRECT_INTERPRETATION]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_COMPARATOR_BOUNDARY
    assert "only_clean_comparator_is_parametric_control" in summary["blocker_reasons"]


def test_market_pnl_public_science_trading_investment_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["claim_text"] = (
        "GOTRA 已证明 market edge with realized P&L and public science proof. "
        "GOTRA 可用于交易/投资建议."
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "claim_boundary_forbidden_wording" in summary["blocker_reasons"]


@pytest.mark.parametrize(
    "wording",
    [
        "GOTRA is the winner before bounded gates.",
        "GOTRA proved the reasoning-quality claim before bounded gates.",
        "GOTRA confirmed the reasoning-quality claim before bounded gates.",
        "GOTRA established the reasoning-quality claim before bounded gates.",
        "GOTRA outperformed the comparator before bounded gates.",
        "GOTRA reasoning-quality superiority is ready before bounded gates.",
    ],
)
def test_comparative_or_superiority_wording_blocks_before_bounded_prereqs(
    tmp_path: Path,
    wording: str,
) -> None:
    payload = _ready_fixture()
    payload["claim_text"] = wording
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "claim_boundary_forbidden_wording" in summary["blocker_reasons"]


def test_raw_path_outside_tmp_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["raw_paths"] = ["/var/tmp/gotra_v3_8u/raw_output.json"]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_RAW_BOUNDARY
    assert "raw_reference_not_tmp" in summary["blocker_reasons"]


def test_raw_full_transcript_in_repo_facing_field_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["repo_facing_summary"] = "full transcript: raw output copied into this repo-facing field"
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "repo_raw_or_full_transcript_reference" in summary["blocker_reasons"]


def test_attempt_to_change_preserved_runtime_status_fields_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "ACTUAL_30D_VERDICT_READY"
    payload["cognitive_lift_superiority_verdict_status"] = "COGNITIVE_LIFT_SUPERIORITY_READY"
    payload["v3_7_actual_verdict_executable"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "cognitive_lift_superiority_status_invalid" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_attempt_to_emit_bounded_verdict_without_scored_evidence_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["rubric_anchored_reasoning_quality_verdict_status"] = gate.STATUS_BOUNDED_VERDICT
    payload["effect_summary"] = {"emitted": True, "values": None, "status": gate.STATUS_BOUNDED_VERDICT}
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "bounded_verdict_status_without_provider_scored_evidence" in summary["blocker_reasons"]
    assert "provider_scored_evidence_missing_for_bounded_verdict" in summary["blocker_reasons"]
    assert "usage_metadata_missing_for_bounded_verdict" in summary["blocker_reasons"]
    assert "effective_n_missing_for_bounded_verdict" in summary["blocker_reasons"]
    assert "scorer_reliability_missing_for_bounded_verdict" in summary["blocker_reasons"]
    assert "clustered_statistical_eligibility_missing_for_bounded_verdict" in summary[
        "blocker_reasons"
    ]
    assert "claim_boundary_fan_in_missing_for_bounded_verdict" in summary["blocker_reasons"]


def test_non_controller_pack_conclusion_template_status_normalizes_to_metadata(
    tmp_path: Path,
) -> None:
    payload = _ready_fixture()
    payload["rubric_anchored_reasoning_quality_verdict_status"] = (
        gate.STATUS_NON_CONTROLLER_CONCLUSION_READY
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_READY, summary["blocker_reasons"]
    assert summary["rubric_anchored_reasoning_quality_verdict_status"] == gate.STATUS_READY
    assert summary["status_normalization"]["non_controller_status_observed"] == (
        gate.STATUS_NON_CONTROLLER_CONCLUSION_READY
    )
    assert summary["status_normalization"]["normalized_to"] == gate.STATUS_READY
    assert summary["conclusion_template_ready"] is True


def test_claim_boundary_flags_false_blocks_claim_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["claim_boundary_flags"]["claim_boundary_clean"] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["claim_boundary_gate_status"] == gate.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert "claim_boundary_clean_false" in summary["blocker_reasons"]


def test_manifest_hash_matches_written_summary(tmp_path: Path) -> None:
    summary = gate.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["rubric_anchored_reasoning_quality_verdict_status"] == gate.STATUS_READY
    assert manifest["claim_boundary_gate_status"] == gate.STATUS_READY
    assert manifest["summary_sha256"] == gate.prereg.sha256_file(Path(summary["summary_path"]))
    assert manifest["provider_or_backend_called"] is False
    assert manifest["codex_cli_new_call"] is False
    assert manifest["formal_lite_entered"] is False
    assert manifest["raw_output_boundary"] == gate.RAW_OUTPUT_BOUNDARY


def _config(tmp_path: Path, *, fixture: Path | None = None) -> gate.ClaimBoundaryGateConfig:
    return gate.ClaimBoundaryGateConfig(
        gate_id="gotra_v3_8u_rubric_reasoning_claim_boundary_gate_20260622T000000Z",
        output_dir=Path("/tmp") / f"gotra_v3_8u_pytest_{tmp_path.name}",
        allow_overwrite=True,
        summary_fixture=fixture,
    )


def _ready_fixture() -> dict[str, object]:
    cfg = gate.ClaimBoundaryGateConfig(
        gate_id="gotra_v3_8u_rubric_reasoning_claim_boundary_gate_20260622T000000Z",
        output_dir=Path("/tmp") / "gotra_v3_8u_pytest_fixture_source",
        allow_overwrite=True,
    )
    summary = gate.build_summary(cfg)
    payload = copy.deepcopy(summary)
    for key in ("gate_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    fixture = tmp_path / "summary_fixture.json"
    fixture.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return fixture
