from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

from scripts import baseline_v3_8k_cognitive_lift_fixture_dry_run as dry_run


def test_valid_fixture_dry_run_is_ready(tmp_path: Path) -> None:
    summary = dry_run.build_summary(_config(tmp_path))

    assert summary["dry_run_status"] == dry_run.STATUS_READY
    assert summary["dimension_count"] == 8
    assert summary["paired_sample_count"] == 1
    assert summary["fixture_pair_count"] == 1
    assert summary["cognitive_lift_superiority_verdict_status"] == dry_run.SUPERIORITY_STATUS
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_canary_executed"] is False
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["actual_30d_readiness_status"] == dry_run.ACTUAL_30D_READINESS_STATUS
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["direct_llm_interpretation"] == dry_run.DIRECT_INTERPRETATION
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["claim_boundary_status"] == "clean"
    assert summary["evidence_layer"] == dry_run.EVIDENCE_LAYER


def test_missing_paired_identity_blocks_structurally(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["fixture_records"][0].pop("paired_sample_id")  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] in {dry_run.STATUS_BLOCKED_SCHEMA, dry_run.STATUS_BLOCKED_PROTOCOL}
    assert "fixture_record_missing_field" in summary["blocker_reasons"]
    assert "paired_record_arms_mismatch" in summary["blocker_reasons"]


def test_missing_dimension_evidence_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["fixture_records"][0]["dimension_evidence"][dry_run.DIMENSIONS[0]] = []  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_SCHEMA
    assert "dimension_evidence_missing" in summary["blocker_reasons"]


def test_direct_llm_clean_or_no_future_label_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["direct_llm_clean_baseline"] = True
    payload["notes"] = "direct_llm_parametric_memory_control is a clean no-future baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_DIRECT_BOUNDARY
    assert "direct_llm_clean_baseline_not_false" in summary["blocker_reasons"]
    assert summary["direct_llm_boundary_status"] == "blocked"


def test_provider_or_canary_flags_block_runtime(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    payload["provider_canary_executed"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "provider_canary_executed_not_false" in summary["blocker_reasons"]


def test_overclaim_wording_blocks_claim_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "This proves cognitive lift superiority, has a winner, and is public science proof with trading advice."
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_CLAIM_BOUNDARY
    assert summary["claim_boundary_status"] == "blocked"


def test_forbidden_or_raw_repo_path_blocks_artifact_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected_artifact_path"] = "data/backtest/" + "runs/dry_run.json"
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_actual_verdict_executable_blocks_runtime(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["v3_7_actual_verdict_executable"] = True
    payload["v3_7_actual_verdict_executed"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executed_not_false" in summary["blocker_reasons"]


def test_malformed_score_returns_structured_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["fixture_records"][0]["dimension_scores"][dry_run.DIMENSIONS[0]] = "high"  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] in {dry_run.STATUS_BLOCKED_SCHEMA, dry_run.STATUS_BLOCKED_METADATA}
    assert "dimension_score_invalid" in summary["blocker_reasons"]


def test_unexpected_fixture_field_is_recursively_scanned(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["unexpected_nested"] = {
        "narrative": "This dry-run is investment advice.",
        "path": "raw_" + "outputs/provider.txt",
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = dry_run.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]
    assert summary["claim_boundary_status"] == "blocked"


def test_output_dir_outside_tmp_does_not_write(tmp_path: Path) -> None:
    output_dir = Path("/var/tmp") / f"gotra_v3_8k_outside_tmp_{tmp_path.name}"
    run_id = "baseline_v3_8k_cognitive_lift_fixture_dry_run_outside_tmp"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    summary = dry_run.build_summary(
        dry_run.DryRunConfig(
            dry_run_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["dry_run_status"] == dry_run.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["runtime_boundary_status"] == "blocked"
    assert not run_root.exists()


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = dry_run.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == dry_run.sha256_file(Path(summary["summary_path"]))
    assert manifest["dry_run_status"] == dry_run.STATUS_READY
    assert manifest["fixture_records_sha256"] == summary["fixture_records_sha256"]
    assert manifest["provider_or_backend_called"] is False
    assert manifest["provider_canary_executed"] is False


def _ready_fixture() -> dict[str, object]:
    config = dry_run.DryRunConfig(
        dry_run_id="baseline_v3_8k_cognitive_lift_fixture_dry_run_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8k_fixture_source"),
        allow_overwrite=True,
    )
    summary = dry_run.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("dry_run_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "dry_run_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, fixture: Path | None = None) -> dry_run.DryRunConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8k_unit_{tmp_path.name}" / "runs"
    return dry_run.DryRunConfig(
        dry_run_id="baseline_v3_8k_cognitive_lift_fixture_dry_run_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        summary_fixture=fixture,
    )
