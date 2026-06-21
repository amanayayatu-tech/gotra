from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts import baseline_v3_6y_short_horizon_first_capture as capture_v36y
from scripts import baseline_v3_7d_short_horizon_canary_maturity_recheck as recheck


SOURCE_RUN_ID = "baseline_v3_6y_short_horizon_first_capture_codex_unit"


def test_immature_horizon_returns_not_matured(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-22T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_NOT_MATURED
    assert summary["outcome_status"] == recheck.OUTCOME_STATUS_NOT_MATURED
    assert summary["next_check_after"] == "2026-06-23T00:00:00Z"
    assert summary["resolved_count"] == 0
    assert summary["scored_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["actual_30d_readiness_status"] == recheck.ACTUAL_30D_READINESS_STATUS


def test_matured_but_no_price_blocks_data(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_DATA
    assert summary["outcome_status"] == recheck.OUTCOME_STATUS_BLOCKED_DATA
    assert summary["resolved_count"] == 0
    assert summary["scored_count"] == 0
    assert summary["v3_7_actual_verdict_executable"] is False


def test_matured_with_price_is_readable_without_30d_verdict(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)
    _write_prices(tmp_path / "prices", [("2026-06-20", 100.0), ("2026-06-22", 103.0)])

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_READY
    assert summary["outcome_status"] == recheck.OUTCOME_STATUS_RESOLVED
    assert summary["decision_price"] == 100.0
    assert summary["outcome_price"] == 103.0
    assert summary["actual_change_pct"] == 3.0
    assert summary["actual_direction"] == "long"
    assert summary["resolved_count"] == 1
    assert summary["scored_count"] == 1
    assert summary["readiness_status"] == recheck.STATUS_READY
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False


def test_missing_source_summary_blocks_provenance(tmp_path: Path) -> None:
    _source_summary, _source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=tmp_path / "missing_summary.json",
            source_sha="0" * 64,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
            run_id="baseline_v3_7d_short_horizon_canary_maturity_recheck_missing_source",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert "source_summary_not_found" in summary["blocker_reasons"]


def test_malformed_source_summary_blocks_schema(tmp_path: Path) -> None:
    source_summary = tmp_path / "bad_summary.json"
    source_summary.write_text(json.dumps([None]), encoding="utf-8")
    source_sha = recheck.sha256_file(source_summary)
    _ok_summary, _ok_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path / "bundle")

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
            run_id="baseline_v3_7d_short_horizon_canary_maturity_recheck_bad_summary",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_SCHEMA
    assert "malformed_json_root" in summary["blocker_reasons"]


def test_wrong_summary_hash_or_run_id_blocks_provenance(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)

    wrong_hash = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha="0" * 64,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
            run_id="baseline_v3_7d_short_horizon_canary_maturity_recheck_wrong_hash",
        )
    )
    assert wrong_hash["maturity_status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert "source_summary_sha256_mismatch" in wrong_hash["blocker_reasons"]

    wrong_run = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
            expected_run_id="wrong-run-id",
            run_id="baseline_v3_7d_short_horizon_canary_maturity_recheck_wrong_run",
        )
    )
    assert wrong_run["maturity_status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert "source_run_id_mismatch" in wrong_run["blocker_reasons"]


def test_actual_direction_buckets_are_long_avoid_neutral(tmp_path: Path) -> None:
    assert _ready_direction(tmp_path / "long", 100.0, 102.0) == "long"
    assert _ready_direction(tmp_path / "avoid", 100.0, 98.0) == "avoid"
    assert _ready_direction(tmp_path / "neutral", 100.0, 100.5) == "neutral"


def test_claim_overreach_blocks_overclaim(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, _artifact_sha = _write_source_bundle(
        tmp_path,
        artifact_updates={"rationale": "This canary is OOS public science proof and trading advice."},
    )
    artifact_sha = recheck.sha256_file(artifact_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_OVERCLAIM
    assert summary["v3_7_actual_verdict_executable"] is False


def test_nested_decision_claim_overreach_blocks_overclaim(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, _artifact_sha = _write_source_bundle(
        tmp_path,
        artifact_updates={
            "decision": {
                "reasoning": "This short-horizon output is OOS public science proof.",
                "risk_factors": ["This is trading advice."],
            }
        },
    )
    artifact_sha = recheck.sha256_file(artifact_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_OVERCLAIM
    assert summary["v3_7_actual_verdict_executable"] is False


def test_future_visible_source_price_blocks_future_data(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, _artifact_sha = _write_source_bundle(
        tmp_path,
        artifact_updates={"latest_visible_price_date": "2026-06-22"},
    )
    artifact_sha = recheck.sha256_file(artifact_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_FUTURE_DATA
    assert "source_future_visible_price_date" in summary["blocker_reasons"]
    assert summary["v3_7_actual_verdict_executable"] is False


def test_summary_ledger_mismatch_blocks_provenance(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, _artifact_sha = _write_source_bundle(
        tmp_path,
        artifact_updates={"source_decision_id": "different-source-decision-id"},
    )
    artifact_sha = recheck.sha256_file(artifact_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert "source_artifact_identity_mismatch" in summary["blocker_reasons"]


def test_failed_source_summary_blocks_ready(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(
        tmp_path,
        summary_updates={"status": capture_v36y.STATUS_SCHEMA_FAIL},
    )

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert "source_summary_not_pass" in summary["blocker_reasons"]


def test_forbidden_source_artifact_path_blocks_provenance(tmp_path: Path) -> None:
    source_summary, source_sha, _artifact_path, artifact_sha = _write_source_bundle(tmp_path)

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=Path("data/backtest/runs/source.json"),
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )

    assert summary["maturity_status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert "forbidden_source_artifact_path" in summary["blocker_reasons"]


def test_ready_writes_verifiable_manifest_digest(tmp_path: Path) -> None:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)
    _write_prices(tmp_path / "prices", [("2026-06-20", 100.0), ("2026-06-22", 103.0)])

    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(Path(summary["summary_path"]))
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def _ready_direction(tmp_path: Path, decision_price: float, outcome_price: float) -> str:
    source_summary, source_sha, artifact_path, artifact_sha = _write_source_bundle(tmp_path)
    _write_prices(tmp_path / "prices", [("2026-06-20", decision_price), ("2026-06-22", outcome_price)])
    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            artifact_path=artifact_path,
            artifact_sha=artifact_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )
    assert summary["maturity_status"] == recheck.STATUS_READY
    assert summary["actual_direction"] in recheck.VALID_DIRECTIONS
    return str(summary["actual_direction"])


def _write_source_bundle(
    tmp_path: Path,
    *,
    artifact_updates: dict[str, object] | None = None,
    summary_updates: dict[str, object] | None = None,
) -> tuple[Path, str, Path, str]:
    run_root = tmp_path / "source_run" / SOURCE_RUN_ID
    artifact_path = run_root / "captures" / "direct_llm" / "capture_2026-06-21_aapl_1d.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact: dict[str, object] = {
        "schema": capture_v36y.CAPTURE_SCHEMA,
        "run_id": SOURCE_RUN_ID,
        "source_decision_id": "source-decision-id",
        "capture_status": "captured",
        "ticker": "AAPL",
        "arm": "direct_llm",
        "input_layer": "price_only_packet",
        "capture_timestamp": "2026-06-21T03:00:00Z",
        "decision_timestamp_utc": "2026-06-21T03:00:00Z",
        "decision_date": "2026-06-21",
        "decision_date_local": "2026-06-21",
        "latest_visible_price_date": "2026-06-20",
        "horizon": "1D",
        "horizon_days": 1,
        "horizon_end_date": "2026-06-22",
        "prompt_hash": "prompt-hash",
        "parsed_decision_hash": "parsed-decision-hash",
        "outcome_price_available_after_utc": "2026-06-23T00:00:00Z",
        "backend": "codex_cli_llm_backend",
        "codex_cli_version": "0.141.0",
        "model": "gpt-5.5",
        "reasoning": "high",
        "formal_lite_entered": False,
        "future_data_violation": False,
        "future_outcome_status": "not_matured",
        "future_outcome_scoring_status": "NOT_MATURED",
        "arm_interpretation": "direct_llm_parametric_memory_control",
        "summary": "Short-horizon engineering fixture for local metadata recheck only.",
    }
    if artifact_updates:
        artifact.update(artifact_updates)
    _write_json(artifact_path, artifact)
    summary_path = run_root / "summary.json"
    summary = {
        "schema": capture_v36y.SUMMARY_SCHEMA,
        "run_id": SOURCE_RUN_ID,
        "status": capture_v36y.STATUS_PASS,
        "run_root": str(run_root),
        "source_artifact_path": str(artifact_path),
        "capture_timestamp": "2026-06-21T03:00:00Z",
        "horizon": "1D",
        "horizon_days": 1,
        "horizon_end_date": "2026-06-22",
        "prompt_hash": "prompt-hash",
        "prompt_hash_count": 1,
        "parsed_decision_hash": "parsed-decision-hash",
        "parsed_decision_hash_count": 1,
        "actual_capture_artifacts": 1,
        "capture_error_count": 0,
        "future_data_violation_count": 0,
        "deterministic_reference_future_data_violations": 0,
        "maturity_ledger_count": 1,
        "maturity_ledger": [
            {
                "source_decision_id": "source-decision-id",
                "ticker": "AAPL",
                "arm": "direct_llm",
                "input_layer": "price_only_packet",
                "decision_date_local": "2026-06-21",
                "horizon_days": 1,
                "horizon_end_date": "2026-06-22",
                "outcome_price_available_after_utc": "2026-06-23T00:00:00Z",
                "future_outcome_status": "not_matured",
                "outcome_scoring_allowed_now": False,
            }
        ],
        "provider_or_backend_called": True,
        "codex_cli_called": True,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "engineering local only",
            "no science public proof",
            "no trading or investment advice",
            "not a 30D forward-live verdict",
        ],
    }
    if summary_updates:
        summary.update(summary_updates)
    _write_json(summary_path, summary)
    return summary_path, recheck.sha256_file(summary_path), artifact_path, recheck.sha256_file(artifact_path)


def _config(
    tmp_path: Path,
    *,
    source_summary: Path,
    source_sha: str,
    artifact_path: Path,
    artifact_sha: str,
    as_of: str,
    expected_run_id: str = SOURCE_RUN_ID,
    run_id: str = "baseline_v3_7d_short_horizon_canary_maturity_recheck_unit",
) -> recheck.RecheckConfig:
    return recheck.RecheckConfig(
        recheck_run_id=run_id,
        source_summary=source_summary,
        expected_source_summary_sha256=source_sha,
        expected_source_artifact_sha256=artifact_sha,
        expected_run_id=expected_run_id,
        source_artifact=artifact_path,
        output_dir=tmp_path / "runs",
        as_of_timestamp_utc=recheck.parse_timestamp(as_of),
        price_dir=tmp_path / "prices",
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_prices(price_dir: Path, rows: list[tuple[str, float]]) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": date_text,
                "ticker": "AAPL",
                "adj_close": price,
                "source_url": "fixture",
                "evidence_unverified": False,
            }
            for date_text, price in rows
        ]
    ).to_csv(price_dir / "AAPL.csv", index=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
