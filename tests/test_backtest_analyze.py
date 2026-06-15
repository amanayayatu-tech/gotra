from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess

from gotra.backtest.analyze import analyze_run
from gotra.backtest.analyze import main as analyze_main


def test_analyze_run_rebuilds_summary_and_quality(tmp_path: Path) -> None:
    run_root = _write_fixture_run(tmp_path / "runs" / "analyze_rebuild")
    (run_root / "summary.json").unlink()

    result = analyze_run(run_root)

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    quality = json.loads((run_root / "quality_summary.json").read_text(encoding="utf-8"))
    assert result["summary"]["steps_written"] == 4
    assert summary["metrics"]["scored_steps"] == 4
    assert summary["metrics"]["paired_steps"] == 2
    assert summary["audit"]["ok"] is True
    assert summary["analysis_rebuilt_from_artifacts"] is True
    assert {row["metric"] for row in quality["rows"]} >= {
        "future_leak_audit",
        "steps_written",
        "provider_errors",
        "provider_abort",
        "token_budget",
        "event_log_actor",
        "baseline_replay_agreement",
        "paired_step_coverage",
        "latency_observed",
    }
    assert _row_status(quality, "future_leak_audit") == "pass"
    assert _row_status(quality, "provider_errors") == "pass"
    assert _row_status(quality, "paired_step_coverage") == "pass"
    assert _row_status(quality, "latency_observed") == "na"


def test_analyze_run_rebuilds_core_metrics_after_summary_delete(tmp_path: Path) -> None:
    run_root = _write_fixture_run(tmp_path / "runs" / "analyze_rebuild_again")
    first = analyze_run(run_root)
    (run_root / "summary.json").unlink()

    second = analyze_run(run_root)

    assert second["summary"]["audit"] == first["summary"]["audit"]
    assert second["summary"]["metrics"] == first["summary"]["metrics"]
    assert second["summary"]["provider_errors"] == 0
    assert second["summary"]["token_budget"]["spent_tokens"] == 400


def test_analyze_run_marks_audit_failure(tmp_path: Path) -> None:
    run_root = _write_fixture_run(tmp_path / "runs" / "analyze_failure")
    step_path = next((run_root / "baseline").glob("step_*.json"))
    step = json.loads(step_path.read_text(encoding="utf-8"))
    step["decision_inputs"].append(
        {"name": "future", "source": "fixture", "availability_date": "2099-01-01"}
    )
    step_path.write_text(json.dumps(step), encoding="utf-8")

    result = analyze_run(run_root)

    assert result["summary"]["system_health"]["status"] == "failed"
    assert _row_status(result["quality_summary"], "future_leak_audit") == "fail"


def test_analyze_main_does_not_call_provider_network_or_subprocess(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = _write_fixture_run(tmp_path / "runs" / "analyze_no_provider")
    (run_root / "summary.json").unlink()

    def blocked(*_args, **_kwargs):
        raise AssertionError("analyzer must not call provider, network, or subprocess")

    monkeypatch.setenv("PERPLEXITY_API_KEY", "must-not-matter")
    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    assert analyze_main(["--run-root", str(run_root)]) == 0


def test_analyze_run_marks_missing_event_log_as_low_coverage(tmp_path: Path) -> None:
    run_root = _write_fixture_run(tmp_path / "runs" / "analyze_low_coverage")
    (run_root / "event_log.jsonl").unlink()

    result = analyze_run(run_root)

    assert _row_status(result["quality_summary"], "future_leak_audit") == "pass"
    assert _row_status(result["quality_summary"], "event_log_actor") == "low_coverage"


def _write_fixture_run(run_root: Path) -> Path:
    for arm in ("baseline", "alaya"):
        (run_root / arm).mkdir(parents=True)
    _write_step(
        run_root / "baseline" / "step_2020-01-01_aapl.json",
        step=1,
        arm="baseline",
        ticker="AAPL",
        decision_date="2020-01-01",
        mse=4.0,
    )
    _write_step(
        run_root / "alaya" / "step_2020-01-01_aapl.json",
        step=2,
        arm="alaya",
        ticker="AAPL",
        decision_date="2020-01-01",
        mse=1.0,
    )
    _write_step(
        run_root / "baseline" / "step_2020-02-01_msft.json",
        step=3,
        arm="baseline",
        ticker="MSFT",
        decision_date="2020-02-01",
        mse=9.0,
    )
    _write_step(
        run_root / "alaya" / "step_2020-02-01_msft.json",
        step=4,
        arm="alaya",
        ticker="MSFT",
        decision_date="2020-02-01",
        mse=4.0,
    )
    _write_event_log(run_root)
    _write_system_health(run_root)
    (run_root / "summary.json").write_text(
        json.dumps({"run_id": run_root.name, "steps_written": 0}),
        encoding="utf-8",
    )
    return run_root


def _write_step(
    path: Path,
    *,
    step: int,
    arm: str,
    ticker: str,
    decision_date: str,
    mse: float,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "gotra.bt.step.v1",
                "step": step,
                "date": decision_date,
                "run_mode": "sampled",
                "status": "scored",
                "ticker": ticker,
                "ticker_name": ticker,
                "arm": arm,
                "decision_date": decision_date,
                "window_days": 30,
                "window_end_date": "2020-02-01",
                "outcome_as_of": "2020-02-01",
                "decision_direction": "long",
                "expected_change_pct": 1.0,
                "actual_change_pct": 2.0,
                "error": 1.0,
                "mse": mse,
                "confidence": 0.5,
                "reasoning": "fixture",
                "prompt_hash": "fixture",
                "estimated_tokens": 100,
                "token_usage_source": "estimated",
                "cache_hit": False,
                "cache_namespace": "",
                "provider": "heuristic",
                "provider_metadata": {},
                "provider_network_enabled": False,
                "decision_inputs": [
                    {
                        "name": "adjusted_close_history",
                        "kind": "price",
                        "source": "fixture",
                        "availability_date": decision_date,
                        "rows": 252,
                    }
                ],
                "outcome_inputs": [
                    {
                        "name": "outcome_adjusted_close",
                        "kind": "price",
                        "source": "fixture",
                        "availability_date": "2020-02-01",
                    }
                ],
                "future_data_allowed": False,
                "audit_actor": "backtest/walk_forward",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_event_log(run_root: Path) -> None:
    rows = []
    for step_path in sorted(run_root.glob("*/step_*.json")):
        step = json.loads(step_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "actor": "backtest/walk_forward",
                "event_type": "bt_step_scored",
                "ticker": step["ticker"],
                "arm": step["arm"],
                "decision_date": step["decision_date"],
                "mse": step["mse"],
                "created_at": "2026-06-15T00:00:00+00:00",
            }
        )
    (run_root / "event_log.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_system_health(run_root: Path) -> None:
    (run_root / "system_health.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "paused": False,
                "pause_reason": "",
                "aborted_provider_unhealthy": False,
                "provider_abort_reason": "",
                "alerts": [],
                "run_mode": "sampled",
                "provider": "heuristic",
                "provider_errors": 0,
                "sampled_validation_only": True,
                "token_budget": {
                    "max_tokens": 10_000,
                    "spent_tokens": 400,
                    "cache_hits": 0,
                    "cache_misses": 4,
                    "over_budget": False,
                    "over_budget_error": "",
                },
            }
        ),
        encoding="utf-8",
    )


def _row_status(quality: dict, metric: str) -> str:
    for row in quality["rows"]:
        if row["metric"] == metric:
            return row["status"]
    raise AssertionError(f"missing quality row: {metric}")
