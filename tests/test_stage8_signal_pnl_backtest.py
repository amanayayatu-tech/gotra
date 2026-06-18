from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd
import pytest


def load_stage8_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "stage8_signal_pnl_backtest.py"
    spec = importlib.util.spec_from_file_location("stage8_signal_pnl_backtest_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def step_df(*, source_run: str = "fixture_run", arm: str = "baseline") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_run": source_run,
                "arm": arm,
                "path": f"{source_run}/{arm}/step_1.json",
                "ticker": "AAPL",
                "decision_date": pd.Timestamp("2020-01-01"),
                "actual_change_pct": 5.0,
                "actual_return": 0.05,
                "decision_direction": "long",
                "expected_change_pct": 3.0,
                "vote_consistency": np.nan,
                "mse": 1.0,
                "future_data_allowed": False,
            }
        ]
    )


def stub_common(module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(module, "worktree_report", lambda: "fixture worktree")
    monkeypatch.setattr(
        module,
        "probe_fields",
        lambda _root: {
            "n_steps": 1,
            "n_actual_non_null": 1,
            "actual_coverage": "1/1 = 1.0000",
        },
    )
    monkeypatch.setattr(module, "random_cumrets", lambda *_args, **_kwargs: np.array([0.0, 0.1]))


def test_build_reference_arm_refuses_missing_candidate_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_stage8_module()
    compare_json = tmp_path / "compare.json"
    monkeypatch.setattr(module, "COMPARE_JSON", compare_json)
    compare_json.write_text(
        """{
  "reference_run": "missing-reference-run",
  "mismatches": [
    {"reason": "missing_candidate_step", "ticker": "AAPL", "decision_date": "2020-01-01"}
  ]
}
""",
        encoding="utf-8",
    )

    reference_df, reference_source, reference_run_path = module.build_reference_arm(step_df())

    assert reference_df.empty
    assert reference_source == "reference_step_json_required_missing_candidate_step"
    assert reference_run_path == "missing-reference-run"


def test_build_analysis_baseline_only_handles_missing_compare(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_stage8_module()
    stub_common(module, monkeypatch, tmp_path)
    monkeypatch.setattr(module, "COMPARE_JSON", tmp_path / "missing_compare.json")
    monkeypatch.setattr(module, "select_mode", lambda: "BASELINE_ONLY")

    def fake_load_steps(run_name: str, arm: str) -> pd.DataFrame:
        if run_name == module.BASELINE_RUN and arm == "baseline":
            return step_df(source_run=run_name, arm=arm)
        return pd.DataFrame()

    monkeypatch.setattr(module, "load_steps", fake_load_steps)

    analysis = module.build_analysis("pytest")

    assert analysis["mode"] == "BASELINE_ONLY"
    assert analysis["primary_reference"] is None
    assert "reference_from_compare" not in analysis["random_blocks"][(False, module.PRIMARY_COST_BPS)]
    report = module.render_report(analysis)
    assert "reference_from_compare：NA" in report


def test_build_analysis_full_mode_loads_stage7_arms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_stage8_module()
    stub_common(module, monkeypatch, tmp_path)
    monkeypatch.setattr(module, "COMPARE_JSON", tmp_path / "missing_compare.json")
    monkeypatch.setattr(module, "select_mode", lambda: "FULL")
    calls: list[tuple[str, str]] = []

    def fake_load_steps(run_name: str, arm: str) -> pd.DataFrame:
        calls.append((run_name, arm))
        if run_name == module.STAGE7_FULL_RUN and arm in {"baseline", "alaya"}:
            return step_df(source_run=run_name, arm=arm)
        return pd.DataFrame()

    monkeypatch.setattr(module, "load_steps", fake_load_steps)

    analysis = module.build_analysis("pytest")

    assert (module.STAGE7_FULL_RUN, "baseline") in calls
    assert (module.STAGE7_FULL_RUN, "alaya") in calls
    assert (module.BASELINE_RUN, "baseline") not in calls
    assert analysis["baseline_label"] == "stage7_baseline"
    assert analysis["primary_alaya"] is not None
    assert {result.label for result in analysis["results"]} >= {"stage7_baseline", "stage7_alaya"}
