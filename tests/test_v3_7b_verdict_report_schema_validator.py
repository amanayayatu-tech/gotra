from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import baseline_v3_7b_verdict_report_schema_validator as validator


def test_valid_fixture_report_is_schema_ready_without_winner_or_actual_verdict(
    tmp_path: Path,
) -> None:
    summary = validator.run_validator(_config(tmp_path, _valid_report(tmp_path)))

    assert summary["validator_status"] == validator.STATUS_READY
    assert summary["report_schema_valid"] is True
    assert summary["readiness_summary_hash_valid"] is True
    assert summary["scored_summary_hash_valid"] is True
    assert summary["matured_count"] == 2
    assert summary["scored_count"] == 2
    assert summary["paired_clean_count"] == 2
    assert summary["winner_emitted"] is False
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_missing_readiness_summary_hash_blocks_schema(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report.pop("source_readiness_summary_sha256")

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_SCHEMA
    assert "missing_or_invalid_source_readiness_summary_sha256" in summary["blocker_reasons"]


def test_wrong_readiness_summary_hash_blocks_provenance(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["source_readiness_summary_sha256"] = "0" * 64

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_PROVENANCE
    assert "source_readiness_summary_sha256_mismatch" in summary["blocker_reasons"]


def test_missing_scored_summary_hash_blocks_schema(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report.pop("source_scored_summary_sha256")

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_SCHEMA
    assert "missing_or_invalid_source_scored_summary_sha256" in summary["blocker_reasons"]


def test_wrong_run_id_provenance_mismatch_blocks(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["provenance"]["verdict_report_run_id"] = "wrong-report-run"

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_PROVENANCE
    assert "verdict_report_run_id_mismatch" in summary["blocker_reasons"]


def test_future_data_violation_blocks(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["future_data_violation_count"] = 1

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_FUTURE_DATA
    assert summary["future_data_violation_count"] >= 1


def test_pairing_coverage_inconsistency_blocks(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["full_gotra_available_count"] = 2
    report["deterministic_reference_available_count"] = 1
    report["paired_clean_count"] = 1

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_PAIRING
    assert "paired_coverage_inconsistent" in summary["blocker_reasons"]


def test_negative_or_non_integer_counts_block_schema(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["matured_count"] = -1
    report["scored_count"] = "two"

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_SCHEMA
    assert "invalid_matured_count" in summary["blocker_reasons"]
    assert "invalid_scored_count" in summary["blocker_reasons"]


def test_forbidden_source_artifact_path_blocks_provenance(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["source_artifact_paths"] = ["data/backtest/runs/raw.json"]

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_PROVENANCE
    assert "forbidden_source_artifact_path" in summary["blocker_reasons"]


def test_overclaim_or_winner_wording_blocks(tmp_path: Path) -> None:
    report = _valid_report(tmp_path)
    report["winner"] = "full_gotra"
    report["claim"] = "This report is OOS evidence and public proof."

    summary = validator.run_validator(_config(tmp_path, report))

    assert summary["validator_status"] == validator.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] >= 1
    assert summary["winner_emitted"] is False


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    summary = validator.run_validator(_config(tmp_path, _valid_report(tmp_path)))
    summary_path = Path(summary["summary_path"])
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(summary_path)
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def test_empty_report_set_is_data_insufficient(tmp_path: Path) -> None:
    summary = validator.run_validator(_config(tmp_path, None))

    assert summary["validator_status"] == validator.STATUS_DATA_INSUFFICIENT
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["winner_emitted"] is False


def _config(
    tmp_path: Path,
    report: dict[str, object] | None,
) -> validator.ValidatorConfig:
    reports = [] if report is None else [{"path": "tests/fixtures/v3_7b_report.json", "payload": report}]
    manifest = tmp_path / f"reports_{len(list(tmp_path.iterdir()))}.json"
    manifest.write_text(json.dumps({"reports": reports}), encoding="utf-8")
    return validator.ValidatorConfig(
        validator_run_id=f"{validator.RUN_ID_PREFIX}test_{len(list(tmp_path.iterdir()))}",
        output_dir=tmp_path / "runs",
        report_manifest=manifest,
    )


def _valid_report(tmp_path: Path) -> dict[str, object]:
    readiness = tmp_path / "readiness_summary.json"
    scored = tmp_path / "scored_summary.json"
    readiness.write_text(
        json.dumps(
            {
                "schema": "gotra.synthetic.readiness_summary.v1",
                "readiness_status": "DATA_NOT_MATURED",
                "v3_7_actual_verdict_executable": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    scored.write_text(
        json.dumps(
            {
                "schema": "gotra.synthetic.scored_summary.v1",
                "scored_count": 2,
                "paired_clean_count": 2,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {
        "report_schema": validator.TARGET_REPORT_SCHEMA,
        "verdict_report_run_id": "baseline_v3_7_forward_live_verdict_report_fixture",
        "source_readiness_summary_path": str(readiness),
        "source_readiness_summary_sha256": _sha256(readiness),
        "source_scored_summary_path": str(scored),
        "source_scored_summary_sha256": _sha256(scored),
        "matured_count": 2,
        "scored_count": 2,
        "paired_clean_count": 2,
        "full_gotra_available_count": 2,
        "deterministic_reference_available_count": 2,
        "source_artifact_paths": [
            "fixtures/deterministic/aapl.json",
            "fixtures/full_gotra/aapl.json",
        ],
        "source_run_ids": ["readiness_fixture_run", "scored_fixture_run"],
        "future_data_violation_count": 0,
        "provenance_blocker_count": 0,
        "pairing_blocker_count": 0,
        "winner_emitted": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": validator.EVIDENCE_LAYER,
        "non_claims": [
            "not an actual 30D forward-live verdict",
            "not OOS evidence",
            "not science/public proof",
            "not trading or investment advice",
        ],
        "provenance": {
            "verdict_report_run_id": "baseline_v3_7_forward_live_verdict_report_fixture",
            "source_run_ids": ["readiness_fixture_run", "scored_fixture_run"],
        },
        "summary": "Schema/provenance validator fixture. Not OOS evidence. Not trading advice.",
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
