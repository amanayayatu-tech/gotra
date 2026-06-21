from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_7e_evidence_dashboard_hardening as dashboard


def test_valid_internal_dashboard_is_ready(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_dashboard())

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_READY
    assert summary["main_commit"] == "d5e21f5d8f26f6ea21d1a592d2643a97a084098f"
    assert summary["actual_30d_readiness_status"] == dashboard.ACTUAL_30D_READINESS_STATUS
    assert summary["actual_30d_next_check_after"] == dashboard.ACTUAL_30D_NEXT_CHECK_AFTER
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["v3_7_actual_verdict_executed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["evidence_layer"] == dashboard.EVIDENCE_LAYER


def test_30d_non_ready_forces_v3_7_actual_verdict_executable_false(tmp_path: Path) -> None:
    payload = _valid_dashboard(
        readiness_updates={"v3_7_actual_verdict_executable": True},
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_SCHEMA
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_short_horizon_status_does_not_authorize_30d_verdict(tmp_path: Path) -> None:
    payload = _valid_dashboard(
        sections_updates={"short_horizon_status": "SHORT_HORIZON_READY"},
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_READY
    assert summary["short_horizon_status"] == "SHORT_HORIZON_READY"
    assert summary["v3_7_actual_verdict_executable"] is False


def test_missing_required_section_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_dashboard()
    del payload["main"]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_SCHEMA
    assert "missing_main_section" in summary["blocker_reasons"]


def test_missing_provenance_section_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_dashboard()
    del payload["provenance"]
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_SCHEMA
    assert "missing_provenance_section" in summary["blocker_reasons"]


def test_provider_codex_formal_true_flags_block_schema(tmp_path: Path) -> None:
    for flag in ("provider_or_backend_called", "codex_cli_new_call", "formal_lite_entered"):
        payload = _valid_dashboard()
        payload[flag] = True
        fixture = _write_fixture(tmp_path / flag, payload)

        summary = dashboard.build_summary(_config(tmp_path / flag, fixture))

        assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_SCHEMA
        assert f"{flag}_not_false" in summary["blocker_reasons"]


def test_overclaim_blocks_dashboard(tmp_path: Path) -> None:
    payload = _valid_dashboard(
        sections_updates={
            "can_say": ["This dashboard is OOS public science proof and trading advice."],
        }
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] > 0


def test_winner_or_verdict_execution_claim_blocks_overclaim(tmp_path: Path) -> None:
    payload = _valid_dashboard(
        sections_updates={
            "can_say": ["v3.7 verdict ready"],
        }
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_OVERCLAIM
    assert "v3_7_verdict_allowed" in summary["blocker_reasons"]


def test_forbidden_raw_artifact_path_blocks_artifact_boundary(tmp_path: Path) -> None:
    payload = _valid_dashboard(
        provenance_updates={"source_documents": ["data/backtest/runs/raw_summary.json"]},
    )
    fixture = _write_fixture(tmp_path, payload)

    summary = dashboard.build_summary(_config(tmp_path, fixture))

    assert summary["dashboard_status"] == dashboard.STATUS_BLOCKED_ARTIFACT
    assert "forbidden_dashboard_artifact_path" in summary["blocker_reasons"]


def test_cli_returns_nonzero_for_blocked_dashboard(tmp_path: Path) -> None:
    payload = _valid_dashboard(readiness_updates={"provider_or_backend_called": True})
    fixture = _write_fixture(tmp_path, payload)

    status = dashboard.main(
        [
            "--dashboard-run-id",
            "baseline_v3_7e_evidence_dashboard_hardening_cli_blocked",
            "--dashboard-fixture",
            str(fixture),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def test_ready_writes_verifiable_manifest_digest(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_dashboard())
    summary = dashboard.build_summary(_config(tmp_path, fixture))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == dashboard.sha256_file(Path(summary["summary_path"]))
    assert manifest["v3_7_actual_verdict_executable"] is False


def _valid_dashboard(
    *,
    main_updates: dict[str, object] | None = None,
    readiness_updates: dict[str, object] | None = None,
    provenance_updates: dict[str, object] | None = None,
    sections_updates: dict[str, object] | None = None,
) -> dict[str, object]:
    main: dict[str, object] = {
        "main_commit": "d5e21f5d8f26f6ea21d1a592d2643a97a084098f",
        "open_pr_count": 0,
        "main_ci_status": "SUCCESS",
    }
    readiness: dict[str, object] = {
        "actual_30d_readiness_status": dashboard.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": dashboard.ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
    }
    provenance: dict[str, object] = {
        "builder_input_mode": "fixture",
        "source_documents": [
            "docs/GOTRA_V3_7A_FIXTURE_VERDICT_HARNESS_DRY_RUN_RESULT_20260621.md",
            "docs/GOTRA_V3_7D_SHORT_HORIZON_CANARY_MATURITY_RECHECK_RESULT_20260622.md",
        ],
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
    }
    sections: dict[str, object] = {
        "short_horizon_status": "SHORT_HORIZON_ENGINEERING_STATUS_ONLY",
        "v3_7a_fixture_harness_status": "V3_7_FIXTURE_HARNESS_READY",
        "v3_7b_report_schema_status": "V3_7_REPORT_SCHEMA_READY",
        "v3_7c_stat_preflight_status": "V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY",
        "v3_7d_short_horizon_recheck_status": "SHORT_HORIZON_READY",
        "v3_7k_ksana_packet_v2_status": "KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY",
        "known_blockers": ["actual_30d_data_not_matured"],
        "can_say": [
            "engineering internal dashboard is schema clean",
            "actual readiness remains DATA_NOT_MATURED",
            "short horizon status is engineering internal only",
        ],
        "cannot_say": [
            "no public proof",
            "no trading advice",
            "no actual 30D winner",
        ],
        "next_safe_actions": ["continue 30D maturity monitor", "review internal dashboard only"],
        "evidence_layer": dashboard.EVIDENCE_LAYER,
    }
    if main_updates:
        main.update(main_updates)
    if readiness_updates:
        readiness.update(readiness_updates)
    if provenance_updates:
        provenance.update(provenance_updates)
    if sections_updates:
        sections.update(sections_updates)
    return {
        "main": main,
        "readiness": readiness,
        "provenance": provenance,
        "sections": sections,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "evidence_layer": dashboard.EVIDENCE_LAYER,
    }


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "dashboard_fixture.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, fixture: Path) -> dashboard.DashboardConfig:
    return dashboard.DashboardConfig(
        dashboard_run_id="baseline_v3_7e_evidence_dashboard_hardening_unit",
        output_dir=tmp_path / "runs",
        dashboard_fixture=fixture,
        allow_overwrite=True,
    )
