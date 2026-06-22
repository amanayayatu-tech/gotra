from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

from scripts import baseline_v3_8f_real_token_evidence_dashboard as dashboard


def test_valid_dashboard_fixture_is_ready(tmp_path: Path) -> None:
    summary = dashboard.build_summary(_config(tmp_path))

    assert summary["dashboard_status"] == dashboard.STATUS_READY
    assert summary["source_real_calls_count_total"] == 7
    assert summary["source_token_usage_total"] == 13369
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["actual_30d_readiness_status"] == dashboard.ACTUAL_30D_READINESS_STATUS
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["claim_boundary_status"] == "clean"
    assert summary["evidence_layer"] == dashboard.EVIDENCE_LAYER
    assert summary["metadata_hashes"]["source_stage_metadata_sha256"] == dashboard.stable_sha256_json(summary["source_stages"])


def test_missing_source_stage_blocks_schema(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"] = payload["source_stages"][:-1]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] in {dashboard.STATUS_BLOCKED_SCHEMA, dashboard.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_set_mismatch" in summary["blocker_reasons"]


def test_missing_merge_commit_or_source_status_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][0]["merge_commit"] = ""  # type: ignore[index]
    payload["source_statuses"]["v3.8B"] = "WRONG"  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] in {dashboard.STATUS_BLOCKED_SCHEMA, dashboard.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_merge_commit_invalid" in summary["blocker_reasons"]
    assert "source_statuses_mismatch" in summary["blocker_reasons"]


def test_raw_path_outside_tmp_blocks_artifact_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][1]["raw_tmp_paths"] = ["/Users/peachy/raw.json"]  # type: ignore[index]
    payload["source_stages"][1]["raw_tmp_sha256s"] = ["a" * 64]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "source_raw_tmp_path_not_tmp" in summary["blocker_reasons"]


def test_source_overclaim_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][2]["narrative"] = "This dry-run is actual v3.7 verdict ready and public science proof."  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_v3_8f_provider_called_true_blocks_runtime(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]


def test_wrong_30d_boundary_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    payload["v3_7_actual_verdict_executable"] = True
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] in {
        dashboard.STATUS_BLOCKED_SCHEMA,
        dashboard.STATUS_BLOCKED_OVERCLAIM,
        dashboard.STATUS_BLOCKED_RUNTIME_BOUNDARY,
    }
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_inconsistent_total_calls_and_tokens_blocks_provenance(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_real_calls_count_total"] = 999
    payload["source_token_usage_total"] = 999
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_PROVENANCE
    assert "source_real_calls_total_mismatch" in summary["blocker_reasons"]
    assert "source_token_total_mismatch" in summary["blocker_reasons"]


def test_aggregate_metadata_sha_mismatch_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["metadata_hashes"]["source_stage_metadata_sha256"] = "0" * 64  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_PROVENANCE
    assert "source_stage_metadata_sha256_mismatch" in summary["blocker_reasons"]


def test_aggregate_source_latency_summary_mismatch_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_latency_summary"] = {
        "real_connection_ms": {"min": 1, "median": 1, "max": 1},
        "all_recorded_ms": {"min": 1, "median": 1, "max": 1},
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_PROVENANCE
    assert "source_latency_summary_mismatch" in summary["blocker_reasons"]


def test_changed_canonical_source_call_and_token_values_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][1]["real_calls_count"] = 4  # type: ignore[index]
    payload["source_stages"][1]["token_usage_total"] = 999  # type: ignore[index]
    payload["source_real_calls_count_total"] = 8
    payload["source_token_usage_total"] = 7850
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] in {dashboard.STATUS_BLOCKED_SCHEMA, dashboard.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_real_calls_count_mismatch" in summary["blocker_reasons"]
    assert "source_stage_token_usage_total_mismatch" in summary["blocker_reasons"]


def test_swapped_stage_pr_merge_pair_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    b_stage = payload["source_stages"][0]  # type: ignore[index]
    c_stage = payload["source_stages"][1]  # type: ignore[index]
    b_stage["pr_number"], c_stage["pr_number"] = c_stage["pr_number"], b_stage["pr_number"]  # type: ignore[index]
    b_stage["merge_commit"], c_stage["merge_commit"] = c_stage["merge_commit"], b_stage["merge_commit"]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] in {dashboard.STATUS_BLOCKED_SCHEMA, dashboard.STATUS_BLOCKED_PROVENANCE}
    assert "source_stage_pr_mismatch" in summary["blocker_reasons"]
    assert "source_stage_merge_commit_mismatch" in summary["blocker_reasons"]


def test_malformed_real_calls_count_returns_structured_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][0]["real_calls_count"] = [1]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_SCHEMA
    assert "real_calls_count_invalid" in summary["blocker_reasons"]
    assert "source_real_calls_total_mismatch" in summary["blocker_reasons"]


def test_unexpected_field_overclaim_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["marketing"] = "This internal dashboard is public science proof."
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_unexpected_field_forbidden_path_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["evidence"] = "data/backtest/" + "runs/raw.json"
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_legacy_backend_blocks_runtime(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][0]["backend_name"] = "deepseek_legacy_backend"  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "source_stage_backend_not_allowed" in summary["blocker_reasons"]


def test_top_level_backend_and_model_override_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["backend_name"] = "deepseek_legacy_backend"
    payload["model"] = "unexpected-model"
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "top_level_backend_not_allowed" in summary["blocker_reasons"]
    assert "top_level_model_not_allowed" in summary["blocker_reasons"]


def test_direct_llm_mislabel_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "direct_llm is the clean baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_output_dir_outside_tmp_does_not_write(tmp_path: Path) -> None:
    output_dir = Path("/var/tmp") / f"gotra_v3_8f_outside_tmp_{tmp_path.name}"
    run_id = "baseline_v3_8f_real_token_evidence_dashboard_outside_tmp"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    summary = dashboard.build_summary(
        dashboard.DashboardConfig(
            dashboard_run_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["runtime_boundary_status"] == "blocked"
    assert not run_root.exists()
    assert not (run_root / "summary.json").exists()


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = dashboard.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == dashboard.sha256_file(Path(summary["summary_path"]))
    assert manifest["dashboard_status"] == dashboard.STATUS_READY
    assert manifest["provider_or_backend_called"] is False


def test_cli_blocked_status_exits_nonzero(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["source_stages"][0]["repo_raw_committed"] = True  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    rc = dashboard.main(
        [
            "--dashboard-run-id",
            "baseline_v3_8f_real_token_evidence_dashboard_cli_blocked",
            "--output-dir",
            str(tmp_path / "runs"),
            "--dashboard-fixture",
            str(fixture),
            "--allow-overwrite",
        ]
    )

    assert rc == 1


def _ready_fixture() -> dict[str, object]:
    config = dashboard.DashboardConfig(
        dashboard_run_id="baseline_v3_8f_real_token_evidence_dashboard_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8f_fixture_source"),
        allow_overwrite=True,
    )
    summary = dashboard.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("dashboard_run_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "dashboard_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, fixture: Path | None = None) -> dashboard.DashboardConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8f_unit_{tmp_path.name}" / "runs"
    return dashboard.DashboardConfig(
        dashboard_run_id="baseline_v3_8f_real_token_evidence_dashboard_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        dashboard_fixture=fixture,
    )
