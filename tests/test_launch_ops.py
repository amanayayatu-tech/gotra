from __future__ import annotations

import json

import pytest

from scripts import launch_ops as launch_ops_cli
from gotra.ops import launch_ops


def test_heartbeat_has_required_launch_fields(tmp_path):
    payload = launch_ops.heartbeat_payload(
        run_id="roadmap_stage12_test",
        status="running",
        current_step="production_smoke",
        evidence_layer="smoke evidence",
    )

    assert payload["schema"] == launch_ops.HEARTBEAT_SCHEMA
    for field in launch_ops.REQUIRED_HEARTBEAT_FIELDS:
        assert payload[field]

    path = tmp_path / "heartbeat.json"
    launch_ops.write_heartbeat(path, payload)
    assert path.exists()


def test_status_summary_has_five_required_status_categories():
    summary = launch_ops.status_summary(
        run_id="roadmap_stage12_test",
        evidence_layer="local checks",
        frontend={"status": "pass"},
        backend={"status": "pass"},
        data={"status": "pass_with_review_items"},
        release={"status": "not_started"},
        review={"status": "pass"},
    )

    assert summary["schema"] == launch_ops.STATUS_SUMMARY_SCHEMA
    for category in launch_ops.STATUS_CATEGORIES:
        assert isinstance(summary[category], dict)
    assert summary["boundary"]["not_investment_advice"] is True
    assert summary["boundary"]["alaya_internal_only"] is True


def test_launch_ops_cli_status_summary_accepts_category_statuses(tmp_path):
    output = tmp_path / "status.json"

    exit_code = launch_ops_cli.main(
        [
            "status-summary",
            "--run-id",
            "roadmap_stage12_test",
            "--output",
            str(output),
            "--frontend-status",
            "pass",
            "--backend-status",
            "pass",
            "--data-status",
            "pass_with_review_items",
            "--release-status",
            "pass",
            "--review-status",
            "pass",
            "--data-note",
            "known live ledger availability review item",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["frontend"]["status"] == "pass"
    assert payload["data"]["status"] == "pass_with_review_items"
    assert payload["data"]["note"] == "known live ledger availability review item"


def test_release_bundle_writes_manifest_checksums_and_public_summary(tmp_path):
    evidence = tmp_path / "smoke.json"
    evidence.write_text('{"status":"pass"}\n', encoding="utf-8")
    status = launch_ops.status_summary(
        run_id="roadmap_stage12_test",
        evidence_layer="smoke evidence",
        frontend={"status": "pass"},
        backend={"status": "pass"},
        data={"status": "pass"},
        release={"status": "pass"},
        review={"status": "pass"},
    )

    result = launch_ops.build_release_bundle(
        output_dir=tmp_path / "bundle",
        run_id="roadmap_stage12_test",
        evidence_paths=[evidence],
        status=status,
        public_safe_summary=(
            "Stage 12 release bundle dry run. Evidence layer: smoke evidence. "
            "Not 10h formal acceptance, not investment advice, not a trading signal, not performance proof."
        ),
    )

    assert result["checksums_verified"] is True
    bundle_dir = tmp_path / "bundle"
    for name in launch_ops.RELEASE_BUNDLE_FILES:
        assert (bundle_dir / name).exists()
    verification = launch_ops.verify_release_bundle(bundle_dir)
    assert verification["ok"] is True
    manifest = (bundle_dir / "EVIDENCE_MANIFEST.json").read_text(encoding="utf-8")
    assert "smoke.json" in manifest


def test_release_bundle_rejects_secret_or_raw_provider_leak(tmp_path):
    evidence = tmp_path / "smoke.json"
    evidence.write_text('{"status":"pass"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="public_safe_summary_forbidden_pattern"):
        launch_ops.build_release_bundle(
            output_dir=tmp_path / "bundle",
            run_id="roadmap_stage12_test",
            evidence_paths=[evidence],
            public_safe_summary="Authorization: Bearer token should not appear",
        )


def test_rollback_dry_run_checks_without_restoring_files(tmp_path):
    static_dir = tmp_path / "www"
    backup_dir = tmp_path / "backup"
    static_dir.mkdir()
    backup_dir.mkdir()

    result = launch_ops.rollback_dry_run(
        static_dir=static_dir,
        backup_dir=backup_dir,
        required_routes=["/today", "/track-record", "/methodology", "/audit"],
    )

    assert result["schema"] == launch_ops.ROLLBACK_DRY_RUN_SCHEMA
    assert result["status"] == "pass"
    assert result["mode"] == "dry_run"
    assert result["checks"]["would_restore_backup_to_static"] is True
    assert result["checks"]["required_routes"] == ["/today", "/track-record", "/methodology", "/audit"]
