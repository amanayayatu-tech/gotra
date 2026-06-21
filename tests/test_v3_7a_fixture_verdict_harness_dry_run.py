from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import baseline_v3_7a_fixture_verdict_harness_dry_run as harness


def test_paired_fixture_inputs_ready_without_winner_or_actual_verdict(
    tmp_path: Path,
) -> None:
    summary = harness.run_harness(
        _config(tmp_path, [_deterministic_fixture(), _full_gotra_fixture()])
    )

    assert summary["harness_status"] == harness.STATUS_READY
    assert summary["fixture_pair_count"] == 1
    assert summary["deterministic_fixture_count"] == 1
    assert summary["full_gotra_fixture_count"] == 1
    assert summary["paired_clean_count"] == 1
    assert summary["winner_emitted"] is False
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_missing_deterministic_fixture_blocks_pairing(tmp_path: Path) -> None:
    summary = harness.run_harness(_config(tmp_path, [_full_gotra_fixture()]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_PAIRING
    assert "missing_deterministic_fixture" in summary["blocker_reasons"]
    assert summary["winner_emitted"] is False


def test_missing_full_gotra_fixture_blocks_pairing(tmp_path: Path) -> None:
    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture()]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_PAIRING
    assert "missing_full_gotra_fixture" in summary["blocker_reasons"]
    assert summary["actual_30d_verdict_executed"] is False


def test_unpaired_fixture_rows_block_pairing(tmp_path: Path) -> None:
    full = _full_gotra_fixture(ticker="MSFT")

    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture(), full]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_PAIRING
    assert summary["unpaired_fixture_count"] == 2
    assert "unpaired_fixture_rows" in summary["blocker_reasons"]


def test_duplicate_pair_keys_block_pairing(tmp_path: Path) -> None:
    duplicate = _deterministic_fixture(source_hash="det-hash-duplicate")

    summary = harness.run_harness(
        _config(tmp_path, [_deterministic_fixture(), duplicate, _full_gotra_fixture()])
    )

    assert summary["harness_status"] == harness.STATUS_BLOCKED_PAIRING
    assert summary["duplicate_pair_count"] == 1
    assert "duplicate_pair_key" in summary["blocker_reasons"]


def test_future_data_violation_blocks_harness(tmp_path: Path) -> None:
    full = _full_gotra_fixture()
    full["future_data_violation"] = True

    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture(), full]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_FUTURE_DATA
    assert summary["future_data_violation_count"] == 1


def test_provenance_mismatch_blocks_harness(tmp_path: Path) -> None:
    full = _full_gotra_fixture()
    full["provenance"]["source_run_id"] = "wrong-run"

    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture(), full]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_PROVENANCE
    assert summary["provenance_blocker_count"] >= 1
    assert "source_run_id_mismatch" in summary["blocker_reasons"]


def test_missing_source_hash_blocks_provenance(tmp_path: Path) -> None:
    full = _full_gotra_fixture()
    full.pop("source_hash")

    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture(), full]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_PROVENANCE
    assert "missing_source_hash" in summary["blocker_reasons"]


def test_schema_unsafe_row_blocks_harness(tmp_path: Path) -> None:
    full = _full_gotra_fixture()
    full.pop("ticker")

    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture(), full]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_SCHEMA
    assert summary["schema_blocker_count"] >= 1
    assert "invalid_pair_key" in summary["blocker_reasons"]


def test_winner_or_overclaim_wording_blocks_harness(tmp_path: Path) -> None:
    full = _full_gotra_fixture()
    full["winner"] = "full_gotra"
    full["claim"] = "This fixture proves an OOS public trading claim."

    summary = harness.run_harness(_config(tmp_path, [_deterministic_fixture(), full]))

    assert summary["harness_status"] == harness.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] >= 1
    assert summary["winner_emitted"] is False


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    summary = harness.run_harness(
        _config(tmp_path, [_deterministic_fixture(), _full_gotra_fixture()])
    )
    summary_path = Path(summary["summary_path"])
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(summary_path)
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def test_empty_fixture_set_is_data_insufficient(tmp_path: Path) -> None:
    summary = harness.run_harness(_config(tmp_path, []))

    assert summary["harness_status"] == harness.STATUS_DATA_INSUFFICIENT
    assert summary["winner_emitted"] is False
    assert summary["actual_30d_verdict_executed"] is False


def _config(
    tmp_path: Path,
    fixtures: list[dict[str, object]],
) -> harness.FixtureHarnessConfig:
    manifest = tmp_path / f"fixtures_{len(list(tmp_path.iterdir()))}.json"
    manifest.write_text(
        json.dumps({"fixtures": [{"path": "tests/fixtures/v3_7a.json", "payload": fixture} for fixture in fixtures]}),
        encoding="utf-8",
    )
    return harness.FixtureHarnessConfig(
        harness_run_id=f"{harness.RUN_ID_PREFIX}test_{len(list(tmp_path.iterdir()))}",
        output_dir=tmp_path / "runs",
        fixture_manifest=manifest,
    )


def _deterministic_fixture(
    *,
    ticker: str = "AAPL",
    decision_date: str = "2026-06-21",
    source_hash: str = "det-hash",
) -> dict[str, object]:
    return _fixture(
        fixture_kind="deterministic_reference",
        ticker=ticker,
        decision_date=decision_date,
        source_run_id="deterministic_fixture_run",
        source_hash=source_hash,
        source_artifact_path="fixtures/deterministic/aapl.json",
    )


def _full_gotra_fixture(
    *,
    ticker: str = "AAPL",
    decision_date: str = "2026-06-21",
    source_hash: str = "full-hash",
) -> dict[str, object]:
    payload = _fixture(
        fixture_kind="full_gotra",
        ticker=ticker,
        decision_date=decision_date,
        source_run_id="full_gotra_fixture_run",
        source_hash=source_hash,
        source_artifact_path="fixtures/full_gotra/aapl.json",
    )
    payload["arm"] = "full_gotra"
    payload["input_layer"] = "synthetic_fixture"
    return payload


def _fixture(
    *,
    fixture_kind: str,
    ticker: str,
    decision_date: str,
    source_run_id: str,
    source_hash: str,
    source_artifact_path: str,
) -> dict[str, object]:
    return {
        "fixture_kind": fixture_kind,
        "ticker": ticker,
        "decision_date": decision_date,
        "horizon_days": 30,
        "source_run_id": source_run_id,
        "source_hash": source_hash,
        "source_artifact_path": source_artifact_path,
        "future_data_violation": False,
        "summary": "Fixture-only engineering dry-run. Not OOS evidence. Not trading advice.",
        "non_claims": [
            "not an actual 30D forward-live verdict",
            "not science/public proof",
        ],
        "provenance": {
            "source_run_id": source_run_id,
            "source_hash": source_hash,
            "source_artifact_path": source_artifact_path,
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
