from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import baseline_v3_6y_short_horizon_first_capture as capture_v36y
from scripts import baseline_v3_6z_short_horizon_outcome_recheck as recheck
from scripts import baseline_v3_four_arm as v3


def test_immature_horizon_returns_not_matured(tmp_path: Path) -> None:
    source_summary, source_sha = _write_source_bundle(tmp_path)
    _write_prices(
        tmp_path / "prices",
        [
            ("2026-06-20", 100.0),
            ("2026-06-22", 103.0),
        ],
    )
    config = _config(
        tmp_path,
        source_summary=source_summary,
        source_sha=source_sha,
        as_of="2026-06-22T00:00:00Z",
    )

    summary = recheck.run_recheck(config)

    assert summary["status"] == recheck.STATUS_NOT_MATURED
    assert summary["outcome_status"] == recheck.OUTCOME_STATUS_NOT_MATURED
    assert summary["next_check_after"] == "2026-06-23T00:00:00Z"
    assert summary["resolved_count"] == 0
    assert summary["scored_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_30d_verdict_allowed"] is False


def test_matured_missing_outcome_price_blocks_data(tmp_path: Path) -> None:
    source_summary, source_sha = _write_source_bundle(tmp_path)
    _write_prices(tmp_path / "prices", [("2026-06-20", 100.0)])
    config = _config(
        tmp_path,
        source_summary=source_summary,
        source_sha=source_sha,
        as_of="2026-06-23T00:00:00Z",
    )

    summary = recheck.run_recheck(config)

    assert summary["status"] == recheck.STATUS_BLOCKED_DATA
    assert summary["outcome_status"] == recheck.OUTCOME_STATUS_BLOCKED_DATA
    assert summary["resolved_count"] == 0
    assert summary["scored_count"] == 0
    assert "outcome_price_unavailable" in summary["blocker_reasons"]


def test_matured_with_price_resolves_and_scores_short_canary(tmp_path: Path) -> None:
    source_summary, source_sha = _write_source_bundle(tmp_path)
    _write_prices(
        tmp_path / "prices",
        [
            ("2026-06-20", 100.0),
            ("2026-06-22", 103.0),
        ],
    )
    config = _config(
        tmp_path,
        source_summary=source_summary,
        source_sha=source_sha,
        as_of="2026-06-23T00:00:00Z",
    )

    summary = recheck.run_recheck(config)

    assert summary["status"] == recheck.STATUS_READY
    assert summary["outcome_status"] == recheck.OUTCOME_STATUS_RESOLVED
    assert summary["decision_price"] == 100.0
    assert summary["outcome_price"] == 103.0
    assert summary["actual_change_pct"] == 3.0
    assert summary["actual_direction"] == "long"
    assert summary["resolved_count"] == 1
    assert summary["scored_count"] == 1
    assert summary["readiness_status"] == recheck.STATUS_READY
    assert summary["v3_7_30d_verdict_allowed"] is False
    assert summary["direct_llm_interpretation"] == "direct_llm_parametric_memory_control"


def test_malformed_or_wrong_source_summary_blocks_provenance(tmp_path: Path) -> None:
    source_summary, _source_sha = _write_source_bundle(tmp_path)
    config = _config(
        tmp_path,
        source_summary=source_summary,
        source_sha="0" * 64,
        as_of="2026-06-23T00:00:00Z",
    )

    wrong_hash = recheck.run_recheck(config)

    assert wrong_hash["status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert wrong_hash["resolved_count"] == 0
    assert wrong_hash["scored_count"] == 0
    assert wrong_hash["provider_or_backend_called"] is False
    assert wrong_hash["codex_cli_new_call"] is False

    missing_config = _config(
        tmp_path,
        source_summary=tmp_path / "missing_summary.json",
        source_sha="0" * 64,
        run_id="baseline_v3_6z_short_horizon_outcome_recheck_missing_source_unit",
        as_of="2026-06-23T00:00:00Z",
    )
    missing = recheck.run_recheck(missing_config)

    assert missing["status"] == recheck.STATUS_BLOCKED_PROVENANCE
    assert missing["source_summary_sha256"] == ""


def test_actual_direction_buckets_are_v3_contract(tmp_path: Path) -> None:
    assert _ready_direction(tmp_path / "neutral", 100.0, 100.5) == "neutral"
    assert _ready_direction(tmp_path / "long", 100.0, 102.0) == "long"
    assert _ready_direction(tmp_path / "avoid", 100.0, 98.0) == "avoid"


def test_cli_blocked_provenance_is_non_zero(tmp_path: Path) -> None:
    source_summary, _source_sha = _write_source_bundle(tmp_path)

    exit_code = recheck.main(
        [
            "--recheck-run-id",
            "baseline_v3_6z_short_horizon_outcome_recheck_cli_blocked_unit",
            "--source-summary",
            str(source_summary),
            "--expected-source-summary-sha256",
            "bad",
            "--expected-run-id",
            SOURCE_RUN_ID,
            "--output-dir",
            str(tmp_path / "runs"),
            "--as-of-timestamp-utc",
            "2026-06-23T00:00:00Z",
            "--price-dir",
            str(tmp_path / "prices"),
        ]
    )

    assert exit_code == 1


SOURCE_RUN_ID = "baseline_v3_6y_short_horizon_first_capture_codex_unit"


def _ready_direction(tmp_path: Path, decision_price: float, outcome_price: float) -> str:
    source_summary, source_sha = _write_source_bundle(tmp_path)
    _write_prices(
        tmp_path / "prices",
        [
            ("2026-06-20", decision_price),
            ("2026-06-22", outcome_price),
        ],
    )
    summary = recheck.run_recheck(
        _config(
            tmp_path,
            source_summary=source_summary,
            source_sha=source_sha,
            as_of="2026-06-23T00:00:00Z",
        )
    )
    assert summary["status"] == recheck.STATUS_READY
    return str(summary["actual_direction"])


def _write_source_bundle(tmp_path: Path) -> tuple[Path, str]:
    run_root = tmp_path / "source_run" / SOURCE_RUN_ID
    artifact_path = (
        run_root
        / "captures"
        / "direct_llm"
        / "capture_2026-06-21_aapl_h1_price_only_packet.json"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema": capture_v36y.CAPTURE_SCHEMA,
        "run_id": SOURCE_RUN_ID,
        "source_decision_id": "source-decision-id",
        "capture_status": "captured",
        "capture_family": "v3.6v_short_horizon_forward_live",
        "arm": "direct_llm",
        "arm_interpretation": "direct_llm_parametric_memory_control",
        "input_layer": "price_only_packet",
        "ticker": "AAPL",
        "decision_timestamp_utc": "2026-06-21T03:00:00Z",
        "decision_date_local": "2026-06-21",
        "horizon_days": 1,
        "horizon_end_date": "2026-06-22",
        "outcome_price_available_after_utc": "2026-06-23T00:00:00Z",
        "future_outcome_status": "not_matured",
        "future_outcome_scoring_status": "NOT_MATURED",
        "outcome_scoring_allowed_now": False,
        "backend": v3.CODEX_CLI_BACKEND,
        "codex_cli_version": "codex-cli 0.test",
        "model": "gpt-5.5",
        "reasoning": "high",
        "prompt_hash": "prompt-hash",
        "source_prompt_identity_hash": "prompt-hash",
        "output_transcript_path": str(run_root / "codex_cli_transcripts" / "transcript.txt"),
        "parsed_decision_hash": "parsed-decision-hash",
        "latest_visible_price_date": "2026-06-20",
        "visible_price_rows": 10,
        "future_rows_excluded": 1,
        "future_data_allowed": False,
        "future_data_violation": False,
        "not_equivalent_to_30d": True,
        "v3_7_30d_verdict_allowed": False,
        "decision": {
            "direction": "long",
            "expected_change_pct": 1.0,
        },
    }
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    summary_path = run_root / "summary.json"
    summary = {
        "schema": capture_v36y.SUMMARY_SCHEMA,
        "run_id": SOURCE_RUN_ID,
        "run_root": str(run_root),
        "status": capture_v36y.STATUS_PASS,
        "horizon_end_date": "2026-06-22",
        "outcome_price_available_after_utc": "2026-06-23T00:00:00Z",
        "actual_capture_artifacts": 1,
        "prompt_hash_count": 1,
        "parsed_decision_hash_count": 1,
        "codex_cli_transcript_path_count": 1,
        "provider_or_backend_called": True,
        "codex_cli_called": True,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "maturity_ledger": [
            {
                "source_decision_id": artifact["source_decision_id"],
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
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary_path, recheck.file_sha256(summary_path)


def _write_prices(price_dir: Path, rows: list[tuple[str, float]]) -> None:
    price_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": date,
                "ticker": "AAPL",
                "adj_close": price,
                "source_url": "fixture",
                "evidence_unverified": False,
            }
            for date, price in rows
        ]
    ).to_csv(price_dir / "AAPL.csv", index=False)


def _config(
    tmp_path: Path,
    *,
    source_summary: Path,
    source_sha: str,
    as_of: str,
    run_id: str = "baseline_v3_6z_short_horizon_outcome_recheck_unit",
) -> recheck.RecheckConfig:
    return recheck.RecheckConfig(
        recheck_run_id=run_id,
        source_summary=source_summary,
        expected_source_summary_sha256=source_sha,
        expected_run_id=SOURCE_RUN_ID,
        output_dir=tmp_path / "runs",
        as_of_timestamp_utc=recheck.parse_timestamp(as_of),
        price_dir=tmp_path / "prices",
    )
