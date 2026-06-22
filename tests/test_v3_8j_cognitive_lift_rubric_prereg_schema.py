from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

from scripts import baseline_v3_8j_cognitive_lift_rubric_prereg_schema as rubric


def test_valid_rubric_prereg_fixture_is_ready(tmp_path: Path) -> None:
    summary = rubric.build_summary(_config(tmp_path))

    assert summary["rubric_status"] == rubric.STATUS_READY
    assert summary["dimension_count"] == 8
    assert summary["cognitive_lift_superiority_verdict_status"] == rubric.SUPERIORITY_STATUS
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_canary_executed"] is False
    assert summary["v3_8j_real_calls_count"] == 0
    assert summary["v3_8j_token_usage_total"] == 0
    assert summary["actual_30d_readiness_status"] == rubric.ACTUAL_30D_READINESS_STATUS
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["direct_llm_interpretation"] == rubric.DIRECT_INTERPRETATION
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["claim_boundary_status"] == "clean"
    assert summary["evidence_layer"] == rubric.EVIDENCE_LAYER


def test_missing_required_dimension_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["dimensions"] = payload["dimensions"][:-1]  # type: ignore[index]
    payload["dimension_count"] = 7
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] in {rubric.STATUS_BLOCKED_SCHEMA, rubric.STATUS_BLOCKED_PROTOCOL}
    assert "dimension_order_or_set_mismatch" in summary["blocker_reasons"]


def test_dimension_without_evidence_or_provenance_requirements_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["dimensions"][0]["required_evidence_fields"] = []  # type: ignore[index]
    payload["dimensions"][0]["minimum_provenance_requirements"] = []  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_SCHEMA
    assert "required_evidence_fields_invalid" in summary["blocker_reasons"]
    assert "minimum_provenance_requirements_invalid" in summary["blocker_reasons"]


def test_protocol_missing_paired_sample_identity_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["paired_comparison_protocol"]["paired_keys"] = ["ticker", "decision_date"]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_PROTOCOL
    assert "protocol_paired_keys_incomplete" in summary["blocker_reasons"]


def test_protocol_unmatched_visible_boundary_or_horizon_gate_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    protocol = payload["paired_comparison_protocol"]  # type: ignore[index]
    protocol["same_visible_data_boundary_required"] = False
    protocol["same_horizon_readiness_gate_required"] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_PROTOCOL
    assert "same_visible_data_boundary_required_not_true" in summary["blocker_reasons"]
    assert "same_horizon_readiness_gate_required_not_true" in summary["blocker_reasons"]


def test_direct_llm_clean_or_no_future_label_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["direct_llm_clean_baseline"] = True
    payload["notes"] = "direct_llm_parametric_memory_control is a clean no-future baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_clean_baseline_not_false" in summary["blocker_reasons"]
    assert summary["direct_llm_boundary_status"] == "blocked"


def test_direct_control_cannot_be_primary_arm(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["paired_comparison_protocol"]["primary_arms"] = [  # type: ignore[index]
        "ksana_real_research",
        "direct_llm_parametric_memory_control",
    ]
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_control_as_primary_arm" in summary["blocker_reasons"]


def test_actual_verdict_executable_blocks_runtime(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["v3_7_actual_verdict_executable"] = True
    payload["v3_7_actual_verdict_executed"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_provider_or_canary_flags_block_runtime(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    payload["provider_canary_executed"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "provider_canary_executed_not_false" in summary["blocker_reasons"]


def test_overclaim_wording_blocks_claim_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "This proves cognitive lift superiority, has a winner, and is public science proof with trading advice."
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_forbidden_or_raw_repo_path_blocks_artifact_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected_artifact_path"] = "data/backtest/" + "runs/rubric.json"
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_malformed_generated_at_and_score_range_return_structured_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["generated_at"] = "not-a-time"
    payload["dimensions"][0]["allowed_score_range"] = {"type": "integer", "min": "zero", "max": 4}  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_SCHEMA
    assert "generated_at_invalid" in summary["blocker_reasons"]
    assert "score_range_invalid" in summary["blocker_reasons"]


def test_unexpected_fixture_field_is_recursively_scanned(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected_nested"] = {
        "narrative": "This rubric is investment advice.",
        "path": "raw_" + "outputs/provider.txt",
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = rubric.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]
    assert summary["claim_boundary_status"] == "blocked"


def test_output_dir_outside_tmp_does_not_write(tmp_path: Path) -> None:
    output_dir = Path("/var/tmp") / f"gotra_v3_8j_outside_tmp_{tmp_path.name}"
    run_id = "baseline_v3_8j_cognitive_lift_rubric_prereg_outside_tmp"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    summary = rubric.build_summary(
        rubric.RubricConfig(
            prereg_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["rubric_status"] == rubric.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["runtime_boundary_status"] == "blocked"
    assert not run_root.exists()


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = rubric.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == rubric.sha256_file(Path(summary["summary_path"]))
    assert manifest["rubric_status"] == rubric.STATUS_READY
    assert manifest["provider_or_backend_called"] is False
    assert manifest["provider_canary_executed"] is False


def _ready_fixture() -> dict[str, object]:
    config = rubric.RubricConfig(
        prereg_id="baseline_v3_8j_cognitive_lift_rubric_prereg_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8j_fixture_source"),
        allow_overwrite=True,
    )
    summary = rubric.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("prereg_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "rubric_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, fixture: Path | None = None) -> rubric.RubricConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8j_unit_{tmp_path.name}" / "runs"
    return rubric.RubricConfig(
        prereg_id="baseline_v3_8j_cognitive_lift_rubric_prereg_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        summary_fixture=fixture,
    )
