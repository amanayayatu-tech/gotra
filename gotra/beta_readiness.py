"""Beta-readiness helpers for the GOTRA launch roadmap.

The helpers define the pre-beta contract only. They do not start the 30-day
clock, schedule research jobs, enable paid access, or claim launch readiness.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BETA_UNIVERSE_SCHEMA = "gotra.launch.beta_universe.v1"
BETA_STATUS_SCHEMA = "gotra.launch.beta_status.v1"
BETA_METRICS_SCHEMA = "gotra.launch.beta_metrics.v1"
DEFAULT_BETA_UNIVERSE_PATH = Path(__file__).resolve().parents[1] / "config" / "beta_universe.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_beta_universe(path: Path | str = DEFAULT_BETA_UNIVERSE_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_beta_universe(payload)
    return payload


def validate_beta_universe(payload: dict[str, Any]) -> None:
    if payload.get("schema") != BETA_UNIVERSE_SCHEMA:
        raise ValueError("beta_universe_invalid_schema")
    symbols = payload.get("universe")
    if not isinstance(symbols, list) or not 10 <= len(symbols) <= 20:
        raise ValueError("beta_universe_symbol_count_out_of_range")
    seen: set[str] = set()
    for item in symbols:
        if not isinstance(item, dict):
            raise ValueError("beta_universe_invalid_item")
        symbol = str(item.get("symbol") or "")
        if ":" not in symbol:
            raise ValueError("beta_universe_invalid_symbol")
        if symbol in seen:
            raise ValueError("beta_universe_duplicate_symbol")
        seen.add(symbol)
        windows = item.get("review_windows")
        if windows != [1, 7, 30, 90]:
            raise ValueError("beta_universe_invalid_review_windows")
    if payload.get("beta_clock_started") is not False:
        raise ValueError("beta_clock_must_not_be_started_in_readiness")
    if payload.get("paid_subscription_enabled") is not False:
        raise ValueError("paid_subscription_must_remain_disabled")
    if payload.get("performance_proof_claimed") is not False:
        raise ValueError("performance_proof_claim_must_remain_false")


def build_beta_status(universe: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    validate_beta_universe(universe)
    return {
        "schema": BETA_STATUS_SCHEMA,
        "generated_at": generated_at or utc_now_iso(),
        "beta_state": "ready_not_started",
        "beta_started": False,
        "beta_clock_started": False,
        "beta_complete": False,
        "universe_count": len(universe["universe"]),
        "daily_events_template_ready": True,
        "weekly_report_template_ready": True,
        "team_review_required_before_start": True,
        "paid_subscription_enabled": False,
        "boundary": _boundary(),
    }


def build_beta_metrics_template(universe: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    validate_beta_universe(universe)
    return {
        "schema": BETA_METRICS_SCHEMA,
        "generated_at": generated_at or utc_now_iso(),
        "elapsed_days": 0,
        "required_days": 30,
        "beta_complete": False,
        "universe_count": len(universe["universe"]),
        "public_judgment_count": 0,
        "continuous_output_rate": None,
        "review_coverage_rate": None,
        "error_publication_rate": None,
        "weekly_report_count": 0,
        "launch_gate_eligible": False,
        "boundary": _boundary(),
    }


def _boundary() -> dict[str, bool]:
    return {
        "not_investment_advice": True,
        "not_trading_signal": True,
        "no_target_price": True,
        "no_position_sizing": True,
        "no_return_promise": True,
        "no_performance_proof": True,
        "no_science_public_proof": True,
        "alaya_internal_only": True,
        "paid_ready": False,
        "launch_ready": False,
    }
