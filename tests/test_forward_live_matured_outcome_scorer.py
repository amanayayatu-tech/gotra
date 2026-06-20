from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_matured_outcome_scorer as scorer
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver


def test_scorer_scores_direction_hit_and_error_metrics(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    _write_resolved_pair(root, ticker="MSFT", direction="avoid", expected=-3.0, actual=-4.0)
    _write_resolved_pair(root, ticker="NVDA", direction="neutral", expected=0.0, actual=0.5)
    config = _scorer_config(tmp_path, input_root=root, run_id="baseline_v3_5e_matured_outcome_scorer_scored")

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_SCORED
    assert summary["resolved_outcome_count"] == 3
    assert summary["scored_outcome_count"] == 3
    assert summary["ticker_count"] == 3
    assert summary["cluster_count"] == 3
    assert summary["date_count"] == 1
    assert summary["direction_hit_rate"] == 1.0
    assert summary["metric_available_count"] == 3
    assert summary["metric_unavailable_count"] == 0
    assert summary["mae"] == pytest.approx((1.0 + 1.0 + 0.5) / 3.0)
    assert summary["mse"] == pytest.approx((1.0 + 1.0 + 0.25) / 3.0)
    assert summary["policy_return_status"] == scorer.POLICY_RETURN_NOT_COMPUTED
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False


def test_scorer_computes_mae_mse_on_expected_change_available_subset(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    _write_resolved_pair(root, ticker="MSFT", direction="avoid", expected=-3.0, actual=-4.0)
    _write_resolved_pair(root, ticker="NVDA", direction="neutral", expected=None, actual=0.5)
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_metric_subset",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_SCORED
    assert summary["metric_available_count"] == 2
    assert summary["metric_unavailable_count"] == 1
    assert summary["mae"] == pytest.approx(1.0)
    assert summary["mse"] == pytest.approx(1.0)


def test_scorer_excludes_immature_blocked_and_blocks_future_data(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_outcome(root, ticker="AAPL", status=resolver.STATUS_NOT_MATURED)
    _write_outcome(root, ticker="MSFT", status=resolver.STATUS_BLOCKED_DATA)
    _write_outcome(root, ticker="NVDA", status=resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA)
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_exclusions",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_BLOCKED_FUTURE_DATA
    assert summary["scored_outcome_count"] == 0
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_NOT_MATURED] == 1
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_BLOCKED_DATA] == 1
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_BLOCKED_SOURCE_FUTURE_DATA] == 1
    assert summary["future_data_violation_count"] == 1
    assert summary["future_data_blocker_count"] == 1


def test_scorer_excludes_unknown_direction_buckets(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_resolved_pair(root, ticker="AAPL", direction="up", expected=3.0, actual=4.0)
    _write_resolved_pair(
        root,
        ticker="MSFT",
        direction="avoid",
        expected=-3.0,
        actual=-4.0,
        actual_direction="down",
    )
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_unknown_direction",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_DATA_INSUFFICIENT
    assert summary["scored_outcome_count"] == 0
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_UNKNOWN_PREDICTED_DIRECTION] == 1
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_UNKNOWN_ACTUAL_DIRECTION] == 1


def test_scorer_blocks_missing_source_provenance(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    outcome = _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    payload = json.loads(outcome.read_text(encoding="utf-8"))
    payload["provenance"]["source_artifact_path"] = str(tmp_path / "missing_capture.json")
    outcome.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_missing_provenance",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_BLOCKED_PROVENANCE
    assert summary["provenance_failure_count"] == 1
    assert summary["scored_outcome_count"] == 0


def test_scorer_blocks_source_artifact_identity_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    outcome = _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    other_source = _write_source_capture(
        root,
        ticker="MSFT",
        decision_date="2026-06-20",
        direction="avoid",
        expected=-3.0,
    )
    payload = json.loads(outcome.read_text(encoding="utf-8"))
    payload["provenance"]["source_artifact_path"] = str(other_source)
    outcome.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_source_mismatch",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_BLOCKED_PROVENANCE
    assert summary["scored_outcome_count"] == 0
    assert summary["provenance_failure_count"] == 1
    assert summary["provenance_failures"][0]["reason"] in {
        "source_artifact_path_ref_mismatch",
        "source_decision_id_recomputed_mismatch",
        "source_ticker_mismatch",
    }


def test_scorer_counts_each_future_data_violation_once(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_outcome(root, ticker="AAPL", status=resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA)
    _write_resolved_pair(
        root,
        ticker="MSFT",
        direction="long",
        expected=3.0,
        actual=4.0,
        source_future_data_violation=True,
    )
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_unique_future_count",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_BLOCKED_FUTURE_DATA
    assert summary["future_data_violation_count"] == 2
    assert summary["future_data_blocker_count"] == 2
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_BLOCKED_SOURCE_FUTURE_DATA] == 1
    assert summary["excluded_count_by_reason"][scorer.EXCLUDED_SOURCE_FUTURE_DATA] == 1


def test_scorer_blocks_contaminated_source_capture_after_reverse_lookup(
    tmp_path: Path,
) -> None:
    root = tmp_path / "outcomes"
    flag_outcome = _write_resolved_pair(
        root,
        ticker="AAPL",
        direction="long",
        expected=3.0,
        actual=4.0,
        source_updates={"future_data_violation": True},
    )
    latest_visible_outcome = _write_resolved_pair(
        root,
        ticker="MSFT",
        direction="long",
        expected=3.0,
        actual=4.0,
        source_updates={"latest_visible_price_date": "2026-06-21"},
    )
    for outcome in [flag_outcome, latest_visible_outcome]:
        payload = json.loads(outcome.read_text(encoding="utf-8"))
        payload["source_future_data_violation"] = False
        payload["source_future_data_violation_reasons"] = []
        outcome.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_source_guard",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_BLOCKED_FUTURE_DATA
    assert summary["scored_outcome_count"] == 0
    assert summary["future_data_violation_count"] == 2
    reasons = {
        reason
        for failure in summary["future_data_failures"]
        for reason in failure["source_future_data_violation_reasons"]
    }
    assert "source_future_data_violation_flag" in reasons
    assert "latest_visible_price_date_after_capture_allowed_date" in reasons


@pytest.mark.parametrize("missing_field", ["record_resolver_run_id", "provenance_resolver_run_id"])
def test_scorer_requires_resolver_run_id_in_provenance(
    tmp_path: Path,
    missing_field: str,
) -> None:
    root = tmp_path / "outcomes"
    outcome = _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    payload = json.loads(outcome.read_text(encoding="utf-8"))
    if missing_field == "record_resolver_run_id":
        payload.pop("resolver_run_id", None)
    else:
        payload["provenance"].pop("resolver_run_id", None)
    outcome.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id=f"baseline_v3_5e_matured_outcome_scorer_missing_{missing_field}",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_BLOCKED_PROVENANCE
    assert summary["scored_outcome_count"] == 0
    assert summary["provenance_failure_count"] == 1


def test_scorer_reports_data_not_matured_when_no_resolved_outcomes(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_outcome(root, ticker="AAPL", status=resolver.STATUS_NOT_MATURED)
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_not_matured",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_DATA_NOT_MATURED
    assert summary["resolved_outcome_count"] == 0
    assert summary["scored_outcome_count"] == 0


def test_scorer_reports_data_insufficient_for_too_few_resolved_outcomes(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_too_few",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_DATA_INSUFFICIENT
    assert summary["resolved_outcome_count"] == 1
    assert summary["scored_outcome_count"] == 1


def test_scorer_reports_insufficient_cluster_coverage(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_resolved_pair(
        root,
        ticker="AAPL",
        decision_date="2026-06-20",
        direction="long",
        expected=3.0,
        actual=4.0,
    )
    _write_resolved_pair(
        root,
        ticker="AAPL",
        decision_date="2026-06-21",
        direction="long",
        expected=3.0,
        actual=4.0,
    )
    _write_resolved_pair(
        root,
        ticker="AAPL",
        decision_date="2026-06-22",
        direction="long",
        expected=3.0,
        actual=4.0,
    )
    config = _scorer_config(
        tmp_path,
        input_root=root,
        run_id="baseline_v3_5e_matured_outcome_scorer_one_cluster",
    )

    summary = scorer.run_scorer(config)

    assert summary["status"] == scorer.STATUS_INSUFFICIENT_CLUSTER_COVERAGE
    assert summary["scored_outcome_count"] == 3
    assert summary["cluster_count"] == 1


def test_scorer_run_id_collision_returns_nonzero_cli(tmp_path: Path) -> None:
    root = tmp_path / "outcomes"
    _write_resolved_pair(root, ticker="AAPL", direction="long", expected=3.0, actual=4.0)
    run_id = "baseline_v3_5e_matured_outcome_scorer_existing"
    run_root = tmp_path / "runs" / run_id
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("exists", encoding="utf-8")

    code = scorer.main(
        [
            "--input-root",
            str(root),
            "--scorer-run-id",
            run_id,
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert code == 1


def _write_resolved_pair(
    root: Path,
    *,
    ticker: str,
    direction: str,
    expected: float | None,
    actual: float,
    actual_direction: str | None = None,
    decision_date: str = "2026-06-20",
    source_updates: dict[str, object] | None = None,
    source_future_data_violation: bool = False,
) -> Path:
    source = _write_source_capture(
        root,
        ticker=ticker,
        decision_date=decision_date,
        direction=direction,
        expected=expected,
        updates=source_updates,
    )
    if actual_direction is None:
        actual_direction = "long" if actual >= 2.0 else "avoid" if actual <= -2.0 else "neutral"
    return _write_outcome(
        root,
        ticker=ticker,
        status=resolver.STATUS_RESOLVED,
        source_path=source,
        decision_date=decision_date,
        actual_change_pct=actual,
        actual_direction=actual_direction,
        source_future_data_violation=source_future_data_violation,
    )


def _write_source_capture(
    root: Path,
    *,
    ticker: str,
    decision_date: str,
    direction: str,
    expected: float | None,
    updates: dict[str, object] | None = None,
) -> Path:
    path = root / "captures" / f"capture_{decision_date}_{ticker.lower()}.json"
    decision: dict[str, object] = {"direction": direction}
    if expected is not None:
        decision["expected_change_pct"] = expected
    payload = {
        "schema": capture_v35a.CAPTURE_SCHEMA,
        "run_id": "baseline_v3_5a_forward_live_scorer_fixture",
        "capture_status": "captured",
        "arm": "full_gotra",
        "input_layer": "richer_research_packet",
        "ticker": ticker,
        "decision_timestamp_utc": f"{decision_date}T02:00:00Z",
        "decision_date_local": decision_date,
        "horizon_days": 30,
        "horizon_end_date": "2026-07-20",
        "future_outcome_status": "not_matured",
        "future_outcome_scoring_status": "NOT_MATURED",
        "backend": "local_mock",
        "prompt_hash": f"prompt_{ticker}_{decision_date}",
        "latest_visible_price_date": "2026-06-19",
        "future_data_violation": False,
        "decision": decision,
    }
    if updates:
        payload.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_outcome(
    root: Path,
    *,
    ticker: str,
    status: str,
    source_path: Path | None = None,
    decision_date: str = "2026-06-20",
    actual_change_pct: float | None = None,
    actual_direction: str | None = None,
    source_future_data_violation: bool | None = None,
) -> Path:
    source_run_id = "baseline_v3_5a_forward_live_scorer_fixture"
    source_artifact_ref = f"captures/capture_{decision_date}_{ticker.lower()}.json"
    source_id = _source_decision_id_for(source_path, source_artifact_ref)
    if source_future_data_violation is None:
        source_future_data_violation = status == resolver.STATUS_BLOCKED_SOURCE_FUTURE_DATA
    provenance = {
        "source_capture_run_id": source_run_id,
        "source_decision_id": source_id,
        "source_artifact_path": str(source_path or root / "captures" / "missing.json"),
        "source_artifact_ref": source_artifact_ref,
        "resolver_run_id": "baseline_v3_5b_outcome_resolver_scorer_fixture",
    }
    resolved = status == resolver.STATUS_RESOLVED
    payload = {
        "schema": resolver.RESOLVER_SCHEMA,
        "resolver_run_id": "baseline_v3_5b_outcome_resolver_scorer_fixture",
        "source_run_id": source_run_id,
        "source_decision_id": source_id,
        "source_decision_artifact": provenance["source_artifact_ref"],
        "ticker": ticker,
        "arm": "full_gotra",
        "input_layer": "richer_research_packet",
        "decision_date": decision_date,
        "horizon_days": 30,
        "horizon_end_date": "2026-07-20",
        "outcome_status": status,
        "outcome_price_date": "2026-07-20" if resolved else None,
        "decision_price_date": "2026-06-19" if resolved else None,
        "decision_price": 100.0 if resolved else None,
        "outcome_price": 100.0 + (actual_change_pct or 0.0) if resolved else None,
        "actual_change_pct": actual_change_pct if resolved else None,
        "actual_direction": actual_direction if resolved else None,
        "source_future_data_violation": source_future_data_violation,
        "source_future_data_violation_reasons": (
            ["source_future_data_violation_flag"]
            if source_future_data_violation
            else []
        ),
        "resolved_at": "2026-07-21T00:00:00Z",
        "provenance": provenance,
    }
    path = (
        root
        / "resolver_outputs"
        / "baseline_v3_5b_outcome_resolver_scorer_fixture"
        / "outcomes"
        / status.lower()
        / f"outcome_{decision_date}_{ticker.lower()}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _source_decision_id_for(source_path: Path | None, artifact_ref: str) -> str:
    if source_path is None:
        return "missing_source_decision_id"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    return resolver.source_decision_id(payload, artifact_ref)


def _scorer_config(
    root: Path,
    *,
    input_root: Path,
    run_id: str,
) -> scorer.ScorerConfig:
    return scorer.ScorerConfig(
        input_roots=(input_root,),
        scorer_run_id=run_id,
        output_dir=root / "runs",
    )
