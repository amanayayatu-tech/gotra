import importlib
import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
KSANA_PIN = "de7f05bd302d823b5d4992321480224de4b0391f"


def test_phase0_packages_import() -> None:
    modules = [
        "gotra",
        "gotra.judge_agent",
        "gotra.perplexity_executor",
        "gotra.daemon_orchestration",
        "gotra.reporting_ext",
        "gotra.backtest",
        "integrations.alaya",
    ]

    for module in modules:
        assert importlib.import_module(module)


def test_pinned_ksana_packages_import() -> None:
    modules = ["chairman", "orchestrator", "business_agents"]

    for module in modules:
        assert importlib.import_module(module)


def test_investment_event_schema_is_valid() -> None:
    schema_path = ROOT / "contracts" / "investment_event.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)


def test_investment_event_schema_accepts_minimal_run_event() -> None:
    schema_path = ROOT / "contracts" / "investment_event.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    event = {
        "event_id": "evt_RUN-20260614_investment_run_started",
        "schema_version": "investment_event.v1",
        "event_type": "investment_run_started",
        "occurred_at": "2026-06-14T00:00:00Z",
        "source": "ksana_researchos",
        "source_id": "RUN-20260614",
        "payload": {"run_id": "RUN-20260614"},
        "sha256": "0" * 64,
    }

    Draft202012Validator(schema).validate(event)


def test_backtest_preregistration_marker_is_tracked_location() -> None:
    marker = ROOT / "data" / "backtest" / "PREREGISTERED.md"

    assert marker.exists()
    assert "Phase 0" in marker.read_text(encoding="utf-8")


def test_ksana_submodule_is_pinned_in_parent_index() -> None:
    output = subprocess.check_output(
        ["git", "ls-files", "-s", "engine/ksana"],
        cwd=ROOT,
        text=True,
    )

    assert f"160000 {KSANA_PIN}" in output
