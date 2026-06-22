from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

from scripts import baseline_v3_8i_end_to_end_connectivity_replay as replay


def test_valid_canonical_replay_is_ready(tmp_path: Path) -> None:
    summary = replay.build_summary(_config(tmp_path))

    assert summary["replay_status"] == replay.STATUS_READY
    assert summary["engineering_connectivity_status"] == replay.STATUS_READY
    assert summary["cognitive_lift_superiority_verdict_status"] == replay.SUPERIORITY_STATUS
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_canary_executed"] is False
    assert summary["v3_8i_real_calls_count"] == 0
    assert summary["v3_8i_token_usage_total"] == 0
    assert summary["actual_30d_readiness_status"] == replay.ACTUAL_30D_READINESS_STATUS
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["claim_boundary_status"] == "clean"
    assert summary["evidence_layer"] == replay.EVIDENCE_LAYER


def test_missing_stage_blocks_provenance_or_schema(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"] = payload["source_stages"][:-1]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] in {replay.STATUS_BLOCKED_SCHEMA, replay.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_set_mismatch" in summary["blocker_reasons"]


def test_swapped_pr_merge_pair_blocks_provenance(tmp_path: Path) -> None:
    payload = _ready_fixture()
    b_stage = payload["source_stages"][0]  # type: ignore[index]
    c_stage = payload["source_stages"][1]  # type: ignore[index]
    b_stage["pr_number"], c_stage["pr_number"] = c_stage["pr_number"], b_stage["pr_number"]  # type: ignore[index]
    b_stage["merge_commit"], c_stage["merge_commit"] = c_stage["merge_commit"], b_stage["merge_commit"]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] in {replay.STATUS_BLOCKED_SCHEMA, replay.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_pr_mismatch" in summary["blocker_reasons"]
    assert "source_stage_merge_commit_mismatch" in summary["blocker_reasons"]


def test_call_token_totals_inconsistent_with_canonical_records_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][1]["real_calls_count"] = 4  # type: ignore[index]
    payload["source_stages"][1]["token_usage_total"] = 999  # type: ignore[index]
    payload["source_real_calls_count_total"] = 8
    payload["source_token_usage_total"] = 7850
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] in {replay.STATUS_BLOCKED_METADATA, replay.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_real_calls_count_mismatch" in summary["blocker_reasons"]
    assert "source_stage_token_usage_total_mismatch" in summary["blocker_reasons"]


def test_raw_repo_path_or_non_tmp_raw_reference_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][2]["raw_tmp_paths"] = ["/Users/peachy/Documents/gotra/raw_response.json"]  # type: ignore[index]
    payload["source_stages"][2]["raw_tmp_sha256s"] = ["a" * 64]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] == replay.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "source_raw_tmp_path_not_tmp" in summary["blocker_reasons"]


def test_v3_8i_runtime_flags_true_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    payload["provider_canary_executed"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] == replay.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "provider_canary_executed_not_false" in summary["blocker_reasons"]


def test_actual_30d_boundary_bypass_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    payload["v3_7_actual_verdict_executable"] = True
    payload["v3_7_actual_verdict_executed"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] in {replay.STATUS_BLOCKED_RUNTIME_BOUNDARY, replay.STATUS_BLOCKED_CLAIM_BOUNDARY}
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_overclaim_wording_blocks_claim_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "This proves cognitive lift superiority and is public science proof with trading advice."
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] == replay.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_malformed_generated_at_hash_and_calls_return_structured_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["generated_at"] = "zzzz"
    payload["source_stage_metadata_sha256"] = "bad"
    payload["source_stages"][0]["real_calls_count"] = [1]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] in {
        replay.STATUS_BLOCKED_SCHEMA,
        replay.STATUS_BLOCKED_PROVENANCE,
        replay.STATUS_BLOCKED_METADATA,
    }
    assert "generated_at_invalid" in summary["blocker_reasons"]
    assert "source_stage_metadata_sha256_invalid" in summary["blocker_reasons"]
    assert "real_calls_count_invalid" in summary["blocker_reasons"]


def test_unexpected_field_forbidden_path_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected_evidence"] = "data/backtest/" + "runs/raw.json"
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] == replay.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_unexpected_field_overclaim_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected_text"] = "This replay is a provider benchmark winner."
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] == replay.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_direct_llm_mislabel_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "direct_llm is a clean baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = replay.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["replay_status"] == replay.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_output_dir_outside_tmp_does_not_write(tmp_path: Path) -> None:
    output_dir = Path("/var/tmp") / f"gotra_v3_8i_outside_tmp_{tmp_path.name}"
    run_id = "baseline_v3_8i_end_to_end_connectivity_replay_outside_tmp"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    summary = replay.build_summary(
        replay.ReplayConfig(
            replay_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["replay_status"] == replay.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["runtime_boundary_status"] == "blocked"
    assert not run_root.exists()


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = replay.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == replay.sha256_file(Path(summary["summary_path"]))
    assert manifest["replay_status"] == replay.STATUS_READY
    assert manifest["provider_or_backend_called"] is False
    assert manifest["provider_canary_executed"] is False


def _ready_fixture() -> dict[str, object]:
    config = replay.ReplayConfig(
        replay_id="baseline_v3_8i_end_to_end_connectivity_replay_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8i_fixture_source"),
        allow_overwrite=True,
    )
    summary = replay.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("replay_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "replay_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, fixture: Path | None = None) -> replay.ReplayConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8i_unit_{tmp_path.name}" / "runs"
    return replay.ReplayConfig(
        replay_id="baseline_v3_8i_end_to_end_connectivity_replay_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        summary_fixture=fixture,
    )
