from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_7f_continuous_monitor_ledger as ledger


def test_valid_internal_ledger_is_ready(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_ledger())

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_READY
    assert summary["main_commit"] == "dac5f685b09abffa361a5d65a83cfb6fabca996d"
    assert summary["actual_30d_readiness_status"] == ledger.ACTUAL_30D_READINESS_STATUS
    assert summary["actual_30d_next_check_after"] == ledger.ACTUAL_30D_NEXT_CHECK_AFTER
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["v3_7_actual_verdict_executed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["evidence_layer"] == ledger.EVIDENCE_LAYER


def test_missing_required_ledger_field_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_ledger()
    del payload["main_commit"]
    fixture = _write_fixture(tmp_path, payload)

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_BLOCKED_SCHEMA
    assert "missing_main_commit" in summary["blocker_reasons"]


def test_30d_not_ready_with_verdict_executable_true_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_ledger(v3_7_actual_verdict_executable=True)
    fixture = _write_fixture(tmp_path, payload)

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_BLOCKED_SCHEMA
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_short_horizon_and_dashboard_status_do_not_authorize_actual_verdict(tmp_path: Path) -> None:
    payload = _valid_ledger(short_horizon_status="SHORT_HORIZON_READY", v3_7e_dashboard_status="V3_7_EVIDENCE_DASHBOARD_READY")
    fixture = _write_fixture(tmp_path, payload)

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_READY
    assert summary["short_horizon_status"] == "SHORT_HORIZON_READY"
    assert summary["v3_7_actual_verdict_executable"] is False


def test_provider_codex_formal_true_flags_block_schema(tmp_path: Path) -> None:
    for flag in ("provider_or_backend_called", "codex_cli_new_call", "formal_lite_entered"):
        payload = _valid_ledger(**{flag: True})
        fixture = _write_fixture(tmp_path / flag, payload)

        summary = ledger.build_summary(_config(tmp_path / flag, fixture))

        assert summary["ledger_status"] == ledger.STATUS_BLOCKED_SCHEMA
        assert f"{flag}_not_false" in summary["blocker_reasons"]


def test_forbidden_raw_artifact_path_blocks_artifact_boundary(tmp_path: Path) -> None:
    payload = _valid_ledger(source_documents=["data/backtest/runs/raw_summary.json"])
    fixture = _write_fixture(tmp_path, payload)

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_BLOCKED_ARTIFACT
    assert "forbidden_ledger_artifact_path" in summary["blocker_reasons"]


def test_overclaim_blocks_ledger(tmp_path: Path) -> None:
    payload = _valid_ledger(next_safe_actions=["This is public science proof and trading advice."])
    fixture = _write_fixture(tmp_path, payload)

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] > 0


def test_verdict_execution_wording_blocks_overclaim(tmp_path: Path) -> None:
    payload = _valid_ledger(known_blockers=["v3.7 verdict ready"])
    fixture = _write_fixture(tmp_path, payload)

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_BLOCKED_OVERCLAIM
    assert "v3_7_verdict_allowed" in summary["blocker_reasons"]


def test_manifest_digest_is_verifiable(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_ledger())
    summary = ledger.build_summary(_config(tmp_path, fixture))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == ledger.sha256_file(Path(summary["summary_path"]))
    assert manifest["v3_7_actual_verdict_executable"] is False


def test_ledger_entries_select_latest_deterministically(tmp_path: Path) -> None:
    older = _valid_ledger(generated_at="2026-06-21T00:00:00Z", main_commit="older")
    newer = _valid_ledger(generated_at="2026-06-22T00:00:00Z", main_commit="newer")
    fixture = _write_fixture(tmp_path, {"ledger_entries": [newer, older]})

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_READY
    assert summary["main_commit"] == "newer"
    assert summary["selected_ledger_entry_index"] == 0
    assert summary["ledger_entry_count"] == 2


def test_ledger_entries_reject_non_object_entries(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, {"ledger_entries": [_valid_ledger(), None]})

    summary = ledger.build_summary(_config(tmp_path, fixture))

    assert summary["ledger_status"] == ledger.STATUS_BLOCKED_SCHEMA
    assert "ledger_entry_not_object" in summary["blocker_reasons"]


def test_cli_returns_nonzero_for_blocked_status(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_ledger(provider_or_backend_called=True))

    status = ledger.main(
        [
            "--ledger-run-id",
            "baseline_v3_7f_continuous_monitor_ledger_cli_blocked",
            "--ledger-fixture",
            str(fixture),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def _valid_ledger(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ledger_schema_version": ledger.LEDGER_SCHEMA_VERSION,
        "generated_at": "2026-06-22T00:00:00Z",
        "main_commit": "dac5f685b09abffa361a5d65a83cfb6fabca996d",
        "main_ci_status": "SUCCESS",
        "open_pr_count": 0,
        "latest_merged_pr": 59,
        "latest_merged_pr_head": "c729488b80219157434811b232fb43517a893c50",
        "latest_merged_pr_commit": "dac5f685b09abffa361a5d65a83cfb6fabca996d",
        "actual_30d_readiness_status": ledger.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ledger.ACTUAL_30D_NEXT_CHECK_AFTER,
        "actual_30d_checked_capture_run_count": 4,
        "actual_30d_capture_artifact_count": 128,
        "actual_30d_matured_candidate_count": 0,
        "actual_30d_resolved_count": 0,
        "actual_30d_scored_count": 0,
        "actual_30d_blocker_reasons": ["capture_horizons_not_matured", "readiness_not_ready"],
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "short_horizon_status": "SHORT_HORIZON_ENGINEERING_STATUS_ONLY",
        "v3_7a_fixture_harness_status": "V3_7_FIXTURE_HARNESS_READY",
        "v3_7b_report_schema_status": "V3_7_REPORT_SCHEMA_READY",
        "v3_7c_stat_preflight_status": "V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY",
        "v3_7d_short_horizon_recheck_status": "SHORT_HORIZON_READY",
        "v3_7e_dashboard_status": "V3_7_EVIDENCE_DASHBOARD_READY",
        "known_blockers": ["actual_30d_data_not_matured"],
        "next_safe_actions": ["continue 30D maturity monitor", "review internal ledger only"],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "evidence_layer": ledger.EVIDENCE_LAYER,
        "source_documents": [
            "docs/GOTRA_V3_7D_SHORT_HORIZON_CANARY_MATURITY_RECHECK_RESULT_20260622.md",
            "docs/GOTRA_V3_7E_EVIDENCE_DASHBOARD_HARDENING_RESULT_20260622.md",
        ],
    }
    payload.update(updates)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "ledger_fixture.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, fixture: Path) -> ledger.LedgerConfig:
    return ledger.LedgerConfig(
        ledger_run_id="baseline_v3_7f_continuous_monitor_ledger_unit",
        output_dir=tmp_path / "runs",
        ledger_fixture=fixture,
        allow_overwrite=True,
    )
