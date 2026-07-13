from __future__ import annotations

import json

from gotra.beta_daily_research import DailyResearchStaging, build_pipeline_command, enablement_manifest, validate_staged_run


def test_enablement_fails_closed_without_manifest(tmp_path):
    result = enablement_manifest(tmp_path / "missing.json")
    assert result["enabled"] is False
    assert "absent" in result["reason"]


def test_enablement_requires_reviewed_canary_and_no_backfill(tmp_path):
    path = tmp_path / "enable.json"
    path.write_text(json.dumps({
        "enabled": True,
        "history_backfilled": False,
        "fixture_allowed": False,
        "start_from_next_scheduled_run_only": True,
        "reviewed_canary_manifest_sha256": "abc123",
    }), encoding="utf-8")
    assert enablement_manifest(path)["enabled"] is True


def test_pipeline_command_is_live_v4_and_staging_only(tmp_path):
    staging = DailyResearchStaging(tmp_path, tmp_path / "output", tmp_path / "private", tmp_path / "static", "daily-test")
    command = build_pipeline_command(staging, symbols=("HKEX:0700",), python="python")
    assert "codex-cli" in command
    assert "fixture" not in command
    assert "--v40-cognition-flywheel" in command
    assert str(staging.static_dir) in command
    assert "/var/www" not in " ".join(command)


def test_staged_validation_rejects_missing_artifacts(tmp_path):
    staging = DailyResearchStaging(tmp_path, tmp_path / "output", tmp_path / "private", tmp_path / "static", "daily-test")
    result = validate_staged_run(staging, symbols=("HKEX:0700",))
    assert result["ok"] is False
    assert result["errors"] == ["status artifact missing"]


def test_staged_validation_accepts_one_real_v4_symbol(tmp_path):
    staging = DailyResearchStaging(
        tmp_path,
        tmp_path / "output",
        tmp_path / "private",
        tmp_path / "static",
        "daily-test",
    )
    (staging.output_dir / "symbols").mkdir(parents=True)
    status = {
        "run_id": staging.run_id,
        "run_status": "completed",
        "failed_count": 0,
        "blocked_count": 0,
        "publish_count": 1,
        "publish_with_boundary_count": 1,
        "needs_review_count": 0,
        "data_gap_count": 0,
        "public_scan_status": "ok",
        "alaya_readback_status": "verified",
        "ledger_integrity_status": "ok",
        "execution_model": "deep_research_dossier_then_parallel_perspectives",
        "symbol_schema": "gotra.full_analyst.symbol.v4",
        "llm_runner": "codex-cli",
    }
    (staging.output_dir / "status_full_analyst_evening_hk.json").write_text(
        json.dumps(status), encoding="utf-8"
    )
    payload = {
        "schema": "gotra.full_analyst.symbol.v4",
        "market_data_snapshot": {
            "price_status": "ok",
            "provider": "public_market_source",
            "future_data_risk": False,
        },
        "agent_outputs": {
            key: {"summary": f"specific {key}"}
            for key in (
                "f_partner_view",
                "w_partner_view",
                "g_partner_view",
                "chairman_synthesis",
                "red_team_audit",
            )
        },
        **{key: f"hash-{key}" for key in (
            "research_task_hash",
            "evidence_packet_hash",
            "market_data_snapshot_hash",
            "k_dossier_hash",
            "research_quality_gate_hash",
            "knowledge_gate_hash",
            "research_signal_hash",
            "publication_decision_hash",
            "public_payload_hash",
        )},
    }
    (staging.output_dir / "symbols" / "HKEX_0700.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    result = validate_staged_run(staging, symbols=("HKEX:0700",))

    assert result["ok"] is True
    assert result["real_data_input"] is True
    assert result["publication_count"] == 1
