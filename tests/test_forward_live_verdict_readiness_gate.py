from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_matured_outcome_scorer as scorer_v35e
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver
from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness


def test_readiness_reports_data_not_matured_when_no_resolved_outcomes(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_reference(root, "AAPL", "2026-06-20")
    _write_outcome(root, "AAPL", "2026-06-20", status=resolver.STATUS_NOT_MATURED)

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "not_matured"))

    assert summary["status"] == readiness.STATUS_DATA_NOT_MATURED
    assert summary["matured_outcome_count"] == 0
    assert "no_resolved_mature_outcomes" in summary["blocking_reasons"]


def test_readiness_reports_data_insufficient_for_too_few_clean_pairs(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_clean_pair(root, "AAPL", "2026-06-20")
    _write_clean_pair(root, "MSFT", "2026-06-20")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "too_few"))

    assert summary["status"] == readiness.STATUS_DATA_INSUFFICIENT
    assert summary["paired_clean_count"] == 2
    assert "paired_clean_count_below_minimum" in summary["blocking_reasons"]


def test_readiness_reports_insufficient_cluster_coverage(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_clean_pair(root, "AAPL", "2026-06-20")
    _write_clean_pair(root, "AAPL", "2026-06-21")
    _write_clean_pair(root, "AAPL", "2026-06-22")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "one_cluster"))

    assert summary["status"] == readiness.STATUS_INSUFFICIENT_CLUSTER_COVERAGE
    assert summary["cluster_count"] == 1
    assert "cluster_count_below_minimum" in summary["blocking_reasons"]


def test_readiness_blocks_when_deterministic_reference_missing(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_outcome(root, "AAPL", "2026-06-20")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "missing_det"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PAIRING
    assert summary["deterministic_reference_available_count"] == 0
    assert "missing_deterministic_reference" in summary["blocking_reasons"]


def test_readiness_blocks_when_full_gotra_pair_missing(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_reference(root, "AAPL", "2026-06-20")
    _write_outcome(root, "AAPL", "2026-06-20", arm="ksana_real_research")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "missing_full"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PAIRING
    assert summary["full_gotra_available_count"] == 0
    assert "missing_full_gotra_outcomes" in summary["blocking_reasons"]


def test_readiness_blocks_future_data_violation(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_reference(root, "AAPL", "2026-06-20")
    _write_outcome(
        root,
        "AAPL",
        "2026-06-20",
        source_updates={"future_data_violation": True},
    )

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "future_data"))

    assert summary["status"] == readiness.STATUS_BLOCKED_FUTURE_DATA
    assert summary["future_data_violation_count"] == 1
    assert "future_data_violation_detected" in summary["blocking_reasons"]


def test_readiness_blocks_future_data_contaminated_deterministic_reference(
    tmp_path: Path,
) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    reference = _write_reference(root, "AAPL", "2026-06-20")
    payload = json.loads(reference.read_text(encoding="utf-8"))
    payload["future_data_violation"] = True
    reference.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_outcome(root, "AAPL", "2026-06-20")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "future_det"))

    assert summary["status"] == readiness.STATUS_BLOCKED_FUTURE_DATA
    assert summary["future_data_violation_count"] == 1
    assert summary["deterministic_reference_future_data_violation_count"] == 1
    assert "future_data_violation_detected" in summary["blocking_reasons"]


def test_readiness_blocks_missing_provenance(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_reference(root, "AAPL", "2026-06-20")
    outcome = _write_outcome(root, "AAPL", "2026-06-20")
    payload = json.loads(outcome.read_text(encoding="utf-8"))
    payload.pop("scheduler_run_id", None)
    payload["provenance"].pop("scheduler_run_id", None)
    outcome.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "missing_provenance"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
    assert summary["provenance_failure_count"] == 1
    assert "provenance_failure_detected" in summary["blocking_reasons"]


def test_readiness_ready_for_clean_sufficient_fixture(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_clean_pair(root, "AAPL", "2026-06-20")
    _write_clean_pair(root, "AAPL", "2026-06-21")
    _write_clean_pair(root, "MSFT", "2026-06-20")
    _write_clean_pair(root, "MSFT", "2026-06-21")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "ready"))

    assert summary["status"] == readiness.STATUS_READY
    assert summary["matured_outcome_count"] == 4
    assert summary["scored_outcome_count"] == 4
    assert summary["deterministic_reference_available_count"] == 4
    assert summary["full_gotra_available_count"] == 4
    assert summary["paired_clean_count"] == 4
    assert summary["cluster_count"] == 2
    assert summary["date_count"] == 2
    assert summary["bootstrap_eligible"] is True
    assert summary["hac_eligible"] is True
    assert summary["blocking_reasons"] == []
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_readiness_requires_successful_scorer_summary(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(
        root,
        status=scorer_v35e.STATUS_DATA_INSUFFICIENT,
        scored_outcome_count=2,
    )
    _write_clean_pair(root, "AAPL", "2026-06-20")
    _write_clean_pair(root, "AAPL", "2026-06-21")
    _write_clean_pair(root, "MSFT", "2026-06-20")
    _write_clean_pair(root, "MSFT", "2026-06-21")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "failed_scorer"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
    assert summary["scorer_summary_success_count"] == 0
    assert "missing_successful_matured_outcome_scorer_summary" in summary["blocking_reasons"]
    assert "scorer_summary:status:DATA_INSUFFICIENT" in summary["blocking_reasons"]


def test_readiness_requires_boundary_clean_scorer_summary(tmp_path: Path) -> None:
    cases: list[tuple[str, dict[str, object], str | None, str]] = [
        ("provider", {"provider_or_backend_called": True}, None, "provider_or_backend_called_not_false"),
        ("codex", {"codex_cli_called": True}, None, "codex_cli_called_not_false"),
        ("formal", {"formal_lite_entered": True}, None, "formal_lite_entered_not_false"),
        ("missing_direct", {}, None, "direct_llm_interpretation_missing_or_invalid"),
        (
            "wrong_direct",
            {},
            "direct_llm",
            "direct_llm_interpretation_missing_or_invalid",
        ),
    ]
    for suffix, updates, direct_llm_interpretation, reason in cases:
        root = tmp_path / suffix
        _write_scorer_summary(
            root,
            updates=updates,
            direct_llm_interpretation=direct_llm_interpretation,
        )
        _write_clean_pair(root, "AAPL", "2026-06-20")
        _write_clean_pair(root, "AAPL", "2026-06-21")
        _write_clean_pair(root, "MSFT", "2026-06-20")
        _write_clean_pair(root, "MSFT", "2026-06-21")

        summary = readiness.run_readiness_gate(_config(tmp_path, root, suffix))

        assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
        assert summary["scorer_summary_success_count"] == 0
        assert summary["scorer_summary_failure_counts"][reason] == 1
        assert f"scorer_summary:{reason}" in summary["blocking_reasons"]


def test_readiness_rejects_unscorable_source_decisions(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    invalid_direction = {"decision": {"direction": "up", "expected_change_pct": 3.0}}
    for ticker in ("AAPL", "MSFT"):
        for decision_date in ("2026-06-20", "2026-06-21"):
            _write_reference(root, ticker, decision_date)
            _write_outcome(root, ticker, decision_date, source_updates=invalid_direction)

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "bad_direction"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
    assert summary["full_gotra_available_count"] == 0
    assert summary["outcome_failure_counts"]["unknown_predicted_direction"] == 4
    assert "outcome:unknown_predicted_direction" in summary["blocking_reasons"]


def test_readiness_blocks_duplicate_full_gotra_pairing_keys(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_clean_pair(root, "AAPL", "2026-06-20")
    _write_outcome(root, "AAPL", "2026-06-20", output_suffix="_duplicate")
    _write_clean_pair(root, "AAPL", "2026-06-21")
    _write_clean_pair(root, "MSFT", "2026-06-20")
    _write_clean_pair(root, "MSFT", "2026-06-21")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "duplicate_full"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
    assert summary["outcome_failure_counts"]["duplicate_full_gotra_key"] == 1
    assert "outcome:duplicate_full_gotra_key" in summary["blocking_reasons"]


def test_readiness_blocks_duplicate_deterministic_reference_keys(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_clean_pair(root, "AAPL", "2026-06-20")
    _write_reference(root, "AAPL", "2026-06-20", output_suffix="_duplicate")
    _write_clean_pair(root, "AAPL", "2026-06-21")
    _write_clean_pair(root, "MSFT", "2026-06-20")
    _write_clean_pair(root, "MSFT", "2026-06-21")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "duplicate_det"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
    assert summary["deterministic_reference_failure_counts"][
        "duplicate_deterministic_reference_key"
    ] == 1
    assert summary["deterministic_reference_pairing_failure_count"] == 1
    assert (
        "deterministic_reference:duplicate_deterministic_reference_key"
        in summary["blocking_reasons"]
    )


def test_readiness_blocks_scheduler_provenance_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_reference(root, "AAPL", "2026-06-20")
    outcome = _write_outcome(root, "AAPL", "2026-06-20")
    payload = json.loads(outcome.read_text(encoding="utf-8"))
    payload["provenance"]["scheduler_run_id"] = "baseline_v3_5c_outcome_scheduler_stale"
    outcome.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "scheduler_mismatch"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PROVENANCE
    assert summary["outcome_failure_counts"]["scheduler_run_id_mismatch"] == 1
    assert "outcome:scheduler_run_id_mismatch" in summary["blocking_reasons"]


def test_direct_llm_is_not_clean_full_gotra_pair(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_reference(root, "AAPL", "2026-06-20")
    _write_outcome(root, "AAPL", "2026-06-20", arm="direct_llm")

    summary = readiness.run_readiness_gate(_config(tmp_path, root, "direct_arm"))

    assert summary["status"] == readiness.STATUS_BLOCKED_PAIRING
    assert summary["direct_llm_interpretation"] == "direct_llm_parametric_memory_control"
    assert summary["full_gotra_available_count"] == 0


def test_readiness_run_id_collision_returns_nonzero_cli(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    _write_scorer_summary(root)
    _write_clean_pair(root, "AAPL", "2026-06-20")
    run_id = readiness.READINESS_RUN_ID_PREFIX + "existing"
    run_root = tmp_path / "out" / run_id
    run_root.mkdir(parents=True)
    (run_root / "summary.json").write_text('{"status":"old"}', encoding="utf-8")

    code = readiness.main(
        [
            "--input-root",
            str(root),
            "--readiness-run-id",
            run_id,
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 1
    assert json.loads((run_root / "summary.json").read_text(encoding="utf-8")) == {
        "status": "old"
    }


def _config(tmp_path: Path, input_root: Path, suffix: str) -> readiness.ReadinessConfig:
    return readiness.ReadinessConfig(
        input_roots=(input_root,),
        readiness_run_id=readiness.READINESS_RUN_ID_PREFIX + suffix,
        output_dir=tmp_path / "out",
    )


def _write_clean_pair(root: Path, ticker: str, decision_date: str) -> None:
    _write_reference(root, ticker, decision_date)
    _write_outcome(root, ticker, decision_date)


def _write_scorer_summary(
    root: Path,
    *,
    status: str = scorer_v35e.STATUS_SCORED,
    scored_outcome_count: int = 4,
    updates: dict[str, object] | None = None,
    direct_llm_interpretation: str | None = "direct_llm_parametric_memory_control",
) -> None:
    payload = {
        "schema": scorer_v35e.SUMMARY_SCHEMA,
        "scorer_run_id": "baseline_v3_5e_matured_outcome_scorer_fixture",
        "status": status,
        "scored_outcome_count": scored_outcome_count,
        "future_data_violation_count": 0,
        "future_data_blocker_count": 0,
        "provenance_failure_count": 0,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
    }
    if direct_llm_interpretation is not None:
        payload["direct_llm_interpretation"] = direct_llm_interpretation
    if updates:
        payload.update(updates)
    path = root / "scorer" / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_reference(
    root: Path,
    ticker: str,
    decision_date: str,
    *,
    output_suffix: str = "",
) -> Path:
    payload = {
        "schema": capture_v35a.DETERMINISTIC_CAPTURE_SCHEMA,
        "run_id": "baseline_v3_5a_forward_live_readiness_fixture",
        "baseline": "deterministic_price_only_baseline",
        "ticker": ticker,
        "decision_date_local": decision_date,
        "horizon_days": 30,
        "horizon_end_date": "2026-07-20",
        "latest_visible_price_date": "2026-06-19",
        "future_data_violation": False,
        "llm_used": False,
        "provider_or_backend_called": False,
    }
    path = (
        root
        / "deterministic_price_only_baseline"
        / f"reference_{decision_date}_{ticker}{output_suffix}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_source_capture(
    root: Path,
    ticker: str,
    decision_date: str,
    *,
    arm: str = "full_gotra",
    input_layer: str = readiness.DEFAULT_PRIMARY_INPUT_LAYER,
    updates: dict[str, object] | None = None,
) -> Path:
    payload = {
        "schema": capture_v35a.CAPTURE_SCHEMA,
        "run_id": "baseline_v3_5a_forward_live_readiness_fixture",
        "capture_status": "captured",
        "arm": arm,
        "input_layer": input_layer,
        "ticker": ticker,
        "decision_timestamp_utc": f"{decision_date}T02:00:00Z",
        "decision_date_local": decision_date,
        "horizon_days": 30,
        "horizon_end_date": "2026-07-20",
        "future_outcome_status": "not_matured",
        "future_outcome_scoring_status": "NOT_MATURED",
        "backend": "local_mock",
        "prompt_hash": f"prompt_{ticker}_{decision_date}_{arm}_{input_layer}",
        "latest_visible_price_date": "2026-06-19",
        "future_data_violation": False,
        "decision": {
            "direction": "long",
            "expected_change_pct": 3.0,
        },
    }
    if updates:
        payload.update(updates)
    path = (
        root
        / "captures"
        / arm
        / f"capture_{decision_date}_{ticker.lower()}_{input_layer}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_outcome(
    root: Path,
    ticker: str,
    decision_date: str,
    *,
    status: str = resolver.STATUS_RESOLVED,
    arm: str = "full_gotra",
    input_layer: str = readiness.DEFAULT_PRIMARY_INPUT_LAYER,
    source_updates: dict[str, object] | None = None,
    output_suffix: str = "",
) -> Path:
    source = _write_source_capture(
        root,
        ticker,
        decision_date,
        arm=arm,
        input_layer=input_layer,
        updates=source_updates,
    )
    artifact_ref = f"captures/{arm}/capture_{decision_date}_{ticker.lower()}_{input_layer}.json"
    source_id = resolver.source_decision_id(
        json.loads(source.read_text(encoding="utf-8")),
        artifact_ref,
    )
    resolved = status == resolver.STATUS_RESOLVED
    payload = {
        "schema": resolver.RESOLVER_SCHEMA,
        "resolver_run_id": "baseline_v3_5b_outcome_resolver_readiness_fixture",
        "scheduler_run_id": "baseline_v3_5c_outcome_scheduler_readiness_fixture",
        "source_run_id": "baseline_v3_5a_forward_live_readiness_fixture",
        "source_decision_id": source_id,
        "source_decision_artifact": artifact_ref,
        "ticker": ticker,
        "arm": arm,
        "input_layer": input_layer,
        "decision_date": decision_date,
        "horizon_days": 30,
        "horizon_end_date": "2026-07-20",
        "outcome_status": status,
        "outcome_price_date": "2026-07-20" if resolved else None,
        "decision_price_date": "2026-06-19" if resolved else None,
        "decision_price": 100.0 if resolved else None,
        "outcome_price": 104.0 if resolved else None,
        "actual_change_pct": 4.0 if resolved else None,
        "actual_direction": "long" if resolved else None,
        "source_future_data_violation": False,
        "source_future_data_violation_reasons": [],
        "resolved_at": "2026-07-21T00:00:00Z",
        "provenance": {
            "source_capture_run_id": "baseline_v3_5a_forward_live_readiness_fixture",
            "source_decision_id": source_id,
            "source_artifact_path": str(source),
            "source_artifact_ref": artifact_ref,
            "resolver_run_id": "baseline_v3_5b_outcome_resolver_readiness_fixture",
            "scheduler_run_id": "baseline_v3_5c_outcome_scheduler_readiness_fixture",
        },
    }
    path = (
        root
        / "resolver_outputs"
        / "baseline_v3_5b_outcome_resolver_readiness_fixture"
        / "outcomes"
        / status.lower()
        / f"outcome_{decision_date}_{ticker.lower()}_{arm}_{input_layer}{output_suffix}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
