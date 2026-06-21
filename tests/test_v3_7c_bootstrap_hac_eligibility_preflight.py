from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import baseline_v3_7c_bootstrap_hac_eligibility_preflight as preflight


def test_valid_multi_ticker_multi_date_fixture_is_ready_without_verdict(tmp_path: Path) -> None:
    summary = preflight.run_preflight(_config(tmp_path, _paired_rows()))

    assert summary["preflight_status"] == preflight.STATUS_READY
    assert summary["sample_count"] == 4
    assert summary["paired_clean_count"] == 4
    assert summary["ticker_cluster_count"] == 2
    assert summary["date_cluster_count"] == 2
    assert summary["bootstrap_eligible"] is True
    assert summary["hac_eligible"] is True
    assert summary["winner_emitted"] is False
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_insufficient_sample_count_blocks_before_ready(tmp_path: Path) -> None:
    summary = preflight.run_preflight(_config(tmp_path, _paired_rows(keys=(("AAPL", "2026-06-01"),))))

    assert summary["preflight_status"] == preflight.STATUS_INSUFFICIENT_SAMPLE
    assert summary["sample_count"] == 1
    assert summary["winner_emitted"] is False


def test_single_cluster_blocks_cluster_coverage(tmp_path: Path) -> None:
    keys = (
        ("AAPL", "2026-06-01"),
        ("AAPL", "2026-06-02"),
        ("AAPL", "2026-06-03"),
        ("AAPL", "2026-06-04"),
    )
    summary = preflight.run_preflight(_config(tmp_path, _paired_rows(keys=keys)))

    assert summary["preflight_status"] == preflight.STATUS_INSUFFICIENT_CLUSTER
    assert summary["ticker_cluster_count"] == 1
    assert summary["date_cluster_count"] == 4


def test_date_coverage_can_block_when_cluster_threshold_allows_single_date(tmp_path: Path) -> None:
    keys = (
        ("AAPL", "2026-06-01"),
        ("MSFT", "2026-06-01"),
        ("NVDA", "2026-06-01"),
        ("GOOG", "2026-06-01"),
    )
    summary = preflight.run_preflight(
        _config(
            tmp_path,
            _paired_rows(keys=keys),
            min_date_clusters=1,
            min_ticker_clusters=2,
            min_date_coverage=2,
        )
    )

    assert summary["preflight_status"] == preflight.STATUS_INSUFFICIENT_DATE
    assert summary["date_coverage_count"] == 1


def test_missing_full_gotra_arm_blocks_pairing(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows = [row for row in rows if row["fixture_kind"] == "deterministic_reference"]

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_PAIRING
    assert "missing_full_gotra_pair" in summary["blocker_reasons"]


def test_missing_deterministic_arm_blocks_pairing(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows = [row for row in rows if row["fixture_kind"] == "full_gotra"]

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_PAIRING
    assert "missing_deterministic_reference_pair" in summary["blocker_reasons"]


def test_duplicate_pair_key_blocks_pairing(tmp_path: Path) -> None:
    rows = _paired_rows()
    duplicate = dict(rows[0])
    duplicate["source_run_id"] = "duplicate-det-run"
    duplicate["provenance"] = dict(duplicate["provenance"], source_run_id="duplicate-det-run")
    rows.append(duplicate)

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_PAIRING
    assert summary["duplicate_pair_count"] == 1
    assert "duplicate_pair_key" in summary["blocker_reasons"]


def test_future_data_violation_blocks_preflight(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows[1]["future_data_violation_count"] = 1

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_FUTURE_DATA
    assert summary["future_data_violation_count"] == 1


def test_provenance_run_id_mismatch_blocks_preflight(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows[1]["provenance"] = dict(rows[1]["provenance"], source_run_id="wrong-run")

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_PROVENANCE
    assert summary["provenance_blocker_count"] >= 1
    assert "missing_or_invalid_provenance" in summary["blocker_reasons"]


def test_forbidden_source_artifact_path_blocks_provenance(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows[1]["source_artifact_path"] = "data/backtest/runs/source.json"
    rows[1]["provenance"] = dict(rows[1]["provenance"], source_artifact_path="data/backtest/runs/source.json")

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_PROVENANCE
    assert summary["provenance_blocker_count"] >= 1


def test_malformed_row_or_negative_count_blocks_schema(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows[0]["future_data_violation_count"] = -1
    rows[1]["horizon_days"] = "thirty"

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_SCHEMA
    assert summary["schema_blocker_count"] >= 1


def test_non_object_fixture_entry_blocks_schema(tmp_path: Path) -> None:
    manifest = tmp_path / "fixtures.json"
    manifest.write_text(json.dumps({"fixtures": [None]}), encoding="utf-8")

    summary = preflight.run_preflight(
        preflight.PreflightConfig(
            preflight_run_id=f"{preflight.RUN_ID_PREFIX}non_object",
            output_dir=tmp_path / "runs",
            fixture_manifest=manifest,
        )
    )

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_SCHEMA
    assert "malformed_fixture_row" in summary["blocker_reasons"]


def test_overclaim_winner_pvalue_or_trading_wording_blocks(tmp_path: Path) -> None:
    rows = _paired_rows()
    rows[0]["winner"] = "full_gotra"
    rows[1]["p_value"] = 0.01
    rows[2]["summary"] = "This fixture is OOS public proof and trading advice."

    summary = preflight.run_preflight(_config(tmp_path, rows))

    assert summary["preflight_status"] == preflight.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] >= 1
    assert summary["winner_emitted"] is False


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    summary = preflight.run_preflight(_config(tmp_path, _paired_rows()))
    summary_path = Path(summary["summary_path"])
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(summary_path)
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def _config(
    tmp_path: Path,
    rows: list[dict[str, object]],
    *,
    min_sample_count: int = preflight.DEFAULT_MIN_SAMPLE_COUNT,
    min_paired_clean_count: int = preflight.DEFAULT_MIN_PAIRED_CLEAN_COUNT,
    min_ticker_clusters: int = preflight.DEFAULT_MIN_TICKER_CLUSTERS,
    min_date_clusters: int = preflight.DEFAULT_MIN_DATE_CLUSTERS,
    min_date_coverage: int = preflight.DEFAULT_MIN_DATE_COVERAGE,
    min_ticker_coverage: int = preflight.DEFAULT_MIN_TICKER_COVERAGE,
) -> preflight.PreflightConfig:
    manifest = tmp_path / f"fixtures_{len(list(tmp_path.iterdir()))}.json"
    manifest.write_text(
        json.dumps(
            {
                "fixtures": [
                    {"path": f"tests/fixtures/v3_7c/{index}.json", "payload": row}
                    for index, row in enumerate(rows)
                ]
            }
        ),
        encoding="utf-8",
    )
    return preflight.PreflightConfig(
        preflight_run_id=f"{preflight.RUN_ID_PREFIX}test_{len(list(tmp_path.iterdir()))}",
        output_dir=tmp_path / "runs",
        fixture_manifest=manifest,
        min_sample_count=min_sample_count,
        min_paired_clean_count=min_paired_clean_count,
        min_ticker_clusters=min_ticker_clusters,
        min_date_clusters=min_date_clusters,
        min_date_coverage=min_date_coverage,
        min_ticker_coverage=min_ticker_coverage,
    )


def _paired_rows(
    *,
    keys: tuple[tuple[str, str], ...] = (
        ("AAPL", "2026-06-01"),
        ("AAPL", "2026-06-02"),
        ("MSFT", "2026-06-01"),
        ("MSFT", "2026-06-02"),
    ),
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ticker, decision_date in keys:
        rows.append(_row(ticker=ticker, decision_date=decision_date, fixture_kind="deterministic_reference"))
        rows.append(_row(ticker=ticker, decision_date=decision_date, fixture_kind="full_gotra"))
    return rows


def _row(*, ticker: str, decision_date: str, fixture_kind: str) -> dict[str, object]:
    suffix = f"{fixture_kind}_{ticker}_{decision_date}"
    source_run_id = f"{suffix}_run"
    source_path = f"fixtures/v3_7c/{suffix}.json"
    source_hash = _hash_for(suffix)
    return {
        "fixture_kind": fixture_kind,
        "ticker": ticker,
        "decision_date": decision_date,
        "horizon_days": 30,
        "outcome_status": "RESOLVED",
        "actual_change_pct": 1.5,
        "decision_price": 100.0,
        "outcome_price": 101.5,
        "source_run_id": source_run_id,
        "source_artifact_path": source_path,
        "source_artifact_sha256": source_hash,
        "future_data_violation_count": 0,
        "summary": "Fixture-only eligibility preflight. Not OOS evidence. Not trading advice.",
        "provenance": {
            "source_run_id": source_run_id,
            "source_artifact_path": source_path,
            "source_artifact_sha256": source_hash,
        },
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": preflight.EVIDENCE_LAYER,
    }


def _hash_for(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
