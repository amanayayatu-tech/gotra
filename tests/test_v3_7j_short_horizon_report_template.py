from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_7j_short_horizon_report_template as template


def test_valid_matured_mock_short_horizon_report_is_ready(tmp_path: Path) -> None:
    report = _write_report(tmp_path, _valid_report())

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_READY
    assert summary["horizon"] == "1D"
    assert summary["actual_direction"] == "long"
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["evidence_layer"] == template.EVIDENCE_LAYER


def test_not_matured_report_returns_not_matured(tmp_path: Path) -> None:
    payload = _valid_report(
        maturity_status=template.STATUS_NOT_MATURED,
        outcome_status="NOT_MATURED",
        decision_price=None,
        outcome_price=None,
        actual_change_pct=None,
        actual_direction="",
        resolved_count=0,
        scored_count=0,
        next_check_after="2026-06-23T00:00:00Z",
    )
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_NOT_MATURED
    assert summary["resolved_count"] == 0
    assert summary["scored_count"] == 0


def test_matured_missing_outcome_or_price_blocks_data(tmp_path: Path) -> None:
    payload = _valid_report(outcome_price=None)
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_DATA
    assert "outcome_price_missing" in summary["blocker_reasons"]


def test_missing_or_malformed_source_hash_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_report(source_summary_sha256="not-a-sha")
    payload["provenance"]["source_summary_sha256"] = "not-a-sha"
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_SCHEMA
    assert "source_summary_sha256_invalid" in summary["blocker_reasons"]


def test_wrong_source_run_id_blocks_provenance(tmp_path: Path) -> None:
    payload = _valid_report()
    payload["provenance"]["source_run_id"] = "different-run"
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_PROVENANCE
    assert "source_run_id_mismatch" in summary["blocker_reasons"]


def test_forbidden_raw_artifact_path_blocks_provenance(tmp_path: Path) -> None:
    payload = _valid_report(source_artifact_path="data/backtest/runs/raw.json")
    payload["provenance"]["source_artifact_path"] = "data/backtest/runs/raw.json"
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_PROVENANCE
    assert "forbidden_source_artifact_path" in summary["blocker_reasons"]


def test_30d_horizon_blocks_schema_or_overclaim(tmp_path: Path) -> None:
    payload = _valid_report(horizon="30D", summary="short-horizon report is actual 30D verdict ready")
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_SCHEMA
    assert "horizon_30d_not_allowed" in summary["blocker_reasons"]


def test_provider_codex_formal_lite_missing_or_true_flags_block(tmp_path: Path) -> None:
    payload = _valid_report(provider_or_backend_called=True)
    payload.pop("codex_cli_new_call")
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_SCHEMA
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "missing_codex_cli_new_call" in summary["blocker_reasons"]


def test_actual_verdict_executable_or_executed_true_blocks(tmp_path: Path) -> None:
    payload = _valid_report(v3_7_actual_verdict_executable=True, v3_7_actual_verdict_executed=True)
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_SCHEMA
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executed_not_false" in summary["blocker_reasons"]


def test_overclaim_public_science_trading_winner_wording_blocks(tmp_path: Path) -> None:
    payload = _valid_report(
        narrative="This short-horizon result is OOS public science proof and trading advice with a winner claim."
    )
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_direct_llm_without_parametric_memory_control_blocks(tmp_path: Path) -> None:
    payload = _valid_report(direct_llm_interpretation="direct_llm", narrative="direct_llm is a clean no-future baseline")
    report = _write_report(tmp_path, payload)

    summary = template.build_summary(_config(tmp_path, report))

    assert summary["template_status"] == template.STATUS_BLOCKED_SCHEMA
    assert "direct_llm_interpretation_mismatch" in summary["blocker_reasons"]


def test_manifest_digest_stable_and_covers_boundary_fields(tmp_path: Path) -> None:
    report = _write_report(tmp_path, _valid_report())
    summary_a = template.build_summary(
        _config(tmp_path / "a", report, "baseline_v3_7j_short_horizon_report_template_a")
    )
    summary_b = template.build_summary(
        _config(tmp_path / "b", report, "baseline_v3_7j_short_horizon_report_template_b")
    )
    changed = _valid_report(v3_7_actual_verdict_executable=True)
    changed_report = _write_report(tmp_path / "changed", changed)
    summary_c = template.build_summary(
        _config(tmp_path / "c", changed_report, "baseline_v3_7j_short_horizon_report_template_c")
    )
    manifest = json.loads(Path(summary_a["manifest_path"]).read_text(encoding="utf-8"))

    assert summary_a["template_status"] == template.STATUS_READY
    assert summary_a["report_content_sha256"] == summary_b["report_content_sha256"]
    assert summary_a["report_content_sha256"] != summary_c["report_content_sha256"]
    assert manifest["summary_sha256"] == template.sha256_file(Path(summary_a["summary_path"]))


def test_cli_returns_nonzero_for_blocker(tmp_path: Path) -> None:
    report = _write_report(tmp_path, _valid_report(horizon="30D"))

    status = template.main(
        [
            "--template-run-id",
            "baseline_v3_7j_short_horizon_report_template_cli_blocked",
            "--report",
            str(report),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def _valid_report(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "report_schema_version": template.REPORT_SCHEMA_VERSION,
        "source_run_id": "baseline_v3_6y_short_horizon_first_capture_codex_fixture",
        "source_summary_sha256": "a" * 64,
        "source_artifact_path": "fixtures/short_horizon/source_artifact.json",
        "source_artifact_sha256": "b" * 64,
        "capture_timestamp": "2026-06-21T03:00:00Z",
        "horizon": "1D",
        "horizon_end_date": "2026-06-22",
        "maturity_status": "SHORT_HORIZON_READY",
        "outcome_status": "RESOLVED",
        "decision_price": 100.0,
        "outcome_price": 103.0,
        "actual_change_pct": 3.0,
        "actual_direction": "long",
        "resolved_count": 1,
        "scored_count": 1,
        "readiness_status": "SHORT_HORIZON_READY",
        "next_check_after": "2026-06-23T00:00:00Z",
        "blocker_reasons": [],
        "evidence_layer": template.EVIDENCE_LAYER,
        "actual_30d_readiness_status": template.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": template.ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": template.DIRECT_LLM_INTERPRETATION,
        "non_claims": "not provider run; not actual 30D verdict; not OOS/science/public/trading claim; not investment advice",
        "summary": "Fixture-only short-horizon report template. v3_7_actual_verdict_executable=false.",
        "provenance": {
            "source_run_id": "baseline_v3_6y_short_horizon_first_capture_codex_fixture",
            "source_summary_sha256": "a" * 64,
            "source_artifact_path": "fixtures/short_horizon/source_artifact.json",
        },
    }
    payload.update(updates)
    return payload


def _write_report(tmp_path: Path, payload: dict[str, object]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "short_horizon_report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(
    tmp_path: Path,
    report: Path,
    run_id: str = "baseline_v3_7j_short_horizon_report_template_unit",
) -> template.ReportConfig:
    return template.ReportConfig(
        template_run_id=run_id,
        output_dir=tmp_path / "runs",
        report=report,
        allow_overwrite=True,
    )
