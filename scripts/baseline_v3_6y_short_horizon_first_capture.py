#!/usr/bin/env python3
"""GOTRA v3.6Y short-horizon first-capture canary."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pandas as pd

from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import parse_date, ticker_slug
from scripts import baseline_v3_6v_short_horizon_cohort_plan as plan_v36v
from scripts import baseline_v3_four_arm as v3


CAPTURE_SCHEMA = "gotra.baseline_v3_6y.short_horizon_capture_canary.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3_6y.short_horizon_capture_canary_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6y.short_horizon_capture_canary_manifest.v1"
DETERMINISTIC_REFERENCE_SCHEMA = (
    "gotra.baseline_v3_6y.short_horizon_deterministic_reference.v1"
)
RUN_ID_PREFIX = "baseline_v3_6y_short_horizon_first_capture_"
SCRIPT_VERSION = "v3.6y-20260621"

STATUS_PASS = "SHORT_HORIZON_CAPTURE_CANARY_PASS"
STATUS_NOT_RUN = "SHORT_HORIZON_CAPTURE_CANARY_NOT_RUN"
STATUS_BLOCKED_RUN_ID_EXISTS = "SHORT_HORIZON_CAPTURE_BLOCKED_RUN_ID_EXISTS"
STATUS_BLOCKED_DATA = "SHORT_HORIZON_CAPTURE_BLOCKED_DATA"
STATUS_BLOCKED_BACKEND = "SHORT_HORIZON_CAPTURE_BLOCKED_BACKEND"
STATUS_SCHEMA_FAIL = "SHORT_HORIZON_CAPTURE_SCHEMA_FAIL"
STATUS_PROVENANCE_FAIL = "SHORT_HORIZON_CAPTURE_PROVENANCE_FAIL"
STATUS_FAIL = "SHORT_HORIZON_CAPTURE_CANARY_FAIL"

FUTURE_OUTCOME_STATUS = "not_matured"
FUTURE_OUTCOME_SCORING_STATUS = "NOT_MATURED"
DEFAULT_TICKERS = ("AAPL",)
DEFAULT_HORIZON_DAYS = 1
DEFAULT_ARMS: tuple[v3.Arm, ...] = ("direct_llm",)
DEFAULT_INPUT_LAYERS: tuple[v3.InputLayer, ...] = ("price_only_packet",)
DEFAULT_MODEL = v3.DEFAULT_CODEX_CLI_MODEL
DEFAULT_REASONING = "high"
FORBIDDEN_OUTCOME_FIELDS = {
    "actual_change_pct",
    "actual_return",
    "actual_direction",
    "direction_hit",
    "error",
    "mse",
    "mae",
    "policy_a_return_pct",
    "realized_return",
    "realized_after_decision",
    "future_return",
    "outcome_after_current_decision",
    "verdict",
    "winner",
}

Mode = Literal["mock", "codex-cli-capture"]


class ShortHorizonProvenanceError(ValueError):
    """Raised when a capture decision references unavailable provenance."""


@dataclass(frozen=True)
class CanaryConfig:
    mode: Mode
    execute_backend: bool
    run_id: str
    output_dir: Path
    tickers: tuple[str, ...]
    horizon_days: int
    arms: tuple[v3.Arm, ...]
    input_layers: tuple[v3.InputLayer, ...]
    capture_timestamp_utc: datetime
    timezone: str
    price_dir: Path
    provider_model: str
    provider_max_tokens: int
    codex_cli_reasoning_setting: str
    codex_cli_binary: str
    backend_concurrency: int
    request_timeout_seconds: float
    allow_overwrite: bool = False


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def local_capture_date(config: CanaryConfig) -> date:
    return config.capture_timestamp_utc.astimezone(ZoneInfo(config.timezone)).date()


def horizon_end_date(config: CanaryConfig) -> date:
    return local_capture_date(config) + timedelta(days=config.horizon_days)


def outcome_price_available_after_utc(config: CanaryConfig) -> str:
    return plan_v36v.daily_close_available_after_utc(horizon_end_date(config))


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_arms(value: str) -> tuple[v3.Arm, ...]:
    if value == "all":
        return v3.ARMS
    return tuple(v3.normalize_arm(item) for item in parse_csv(value))


def parse_input_layers(value: str) -> tuple[v3.InputLayer, ...]:
    if value == "both":
        return v3.INPUT_LAYERS
    return tuple(v3.normalize_input_layer(item) for item in parse_csv(value))


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: CanaryConfig) -> None:
    validate_run_id(config.run_id)
    if not config.tickers:
        raise ValueError("at least one ticker is required")
    if len(config.tickers) != 1:
        raise ValueError("v3.6Y first canary must use exactly one ticker")
    if config.horizon_days <= 0:
        raise ValueError("horizon_days must be > 0")
    if not config.arms:
        raise ValueError("at least one arm is required")
    if not config.input_layers:
        raise ValueError("at least one input layer is required")
    unsupported_layers = sorted(
        layer for layer in config.input_layers if layer != "price_only_packet"
    )
    if unsupported_layers:
        raise ValueError(
            "v3.6Y first-capture canary only supports price_only_packet; "
            "richer_research_packet/both require real filtered research artifacts "
            "and are blocked in this canary"
        )
    unsupported_arms = sorted(arm for arm in config.arms if arm != "direct_llm")
    if unsupported_arms:
        raise ValueError(
            "v3.6Y first-capture canary only supports direct_llm; "
            "full_gotra/all require visible feedback provenance and are blocked in "
            "this canary"
        )
    if config.backend_concurrency <= 0:
        raise ValueError("backend_concurrency must be > 0")
    slugs: dict[str, str] = {}
    for ticker in config.tickers:
        slug = ticker_slug(ticker)
        prior = slugs.get(slug)
        if prior is not None:
            raise ValueError(
                f"duplicate ticker slug: {prior!r} and {ticker!r} both map to {slug!r}"
            )
        slugs[slug] = ticker


def visible_price_rows(
    ticker: str,
    *,
    decision_date_local: date,
    price_dir: Path,
) -> tuple[pd.DataFrame, int, str]:
    frame = read_price_cache(ticker, price_dir=price_dir)
    dated = frame.copy()
    dated["_gotra_visible_date"] = pd.to_datetime(dated["date"]).dt.date
    visible = dated[dated["_gotra_visible_date"] < decision_date_local].drop(
        columns=["_gotra_visible_date"]
    )
    if visible.empty:
        raise RuntimeError(f"no visible price rows for {ticker} at {decision_date_local}")
    latest_visible = str(visible.iloc[-1]["date"])
    return visible, int(len(frame) - len(visible)), latest_visible


def stable_json_hash(payload: dict[str, Any]) -> str:
    return v3.stable_json_hash(payload)


def source_decision_id(
    *,
    run_id: str,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    decision_date_local: date,
    horizon_days: int,
    prompt_hash: str,
) -> str:
    return stable_json_hash(
        {
            "schema": CAPTURE_SCHEMA,
            "run_id": run_id,
            "ticker": ticker,
            "arm": arm,
            "input_layer": input_layer,
            "decision_date_local": decision_date_local.isoformat(),
            "horizon_days": horizon_days,
            "prompt_hash": prompt_hash,
        }
    )


def build_prompt_payload(
    *,
    config: CanaryConfig,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    visible_rows: pd.DataFrame,
) -> dict[str, Any]:
    decision_date = local_capture_date(config)
    payload = v3.build_prompt_payload(
        arm=arm,
        input_layer=input_layer,
        ticker=ticker,
        decision_date=decision_date,
        price_rows=visible_rows,
        feedback=[],
        provider=v3.CODEX_CLI_BACKEND,
        provider_model=config.provider_model,
        scoring_segment="scored",
        research_artifacts_path=None,
        research_artifacts_override=[],
    )
    payload["horizon_days"] = config.horizon_days
    payload["output_contract"]["horizon_days"] = config.horizon_days
    payload["capture_policy"] = {
        "mode": "short_horizon_forward_live_first_capture_canary",
        "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "decision_date_local": decision_date.isoformat(),
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "outcome_price_available_after_utc": outcome_price_available_after_utc(config),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "outcome_scoring_allowed_now": False,
        "not_equivalent_to_30d": True,
    }
    payload["input_policy"]["actual_outcome_visible"] = False
    payload["input_policy"]["future_outcome_status"] = FUTURE_OUTCOME_STATUS
    payload["input_policy"]["short_horizon_family"] = "v3.6v_short_horizon_forward_live"
    return payload


def decision_summary(decision: v3.ProviderDecision) -> dict[str, Any]:
    return {
        "schema": decision.schema,
        "arm": decision.arm,
        "ticker": decision.ticker,
        "decision_date": decision.decision_date,
        "horizon_days": decision.horizon_days,
        "direction": decision.direction,
        "expected_change_pct": decision.expected_change_pct,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "evidence_refs": decision.evidence_refs,
        "ksana_refs": decision.ksana_refs,
        "alaya_memory_refs": decision.alaya_memory_refs,
        "risk_factors": decision.risk_factors,
        "abstain_reason": decision.abstain_reason,
        "input_cutoff": decision.input_cutoff,
        "future_data_allowed": decision.future_data_allowed,
    }


def validate_decision_identity(
    *,
    decision: v3.ProviderDecision,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    decision_date_local: date,
    horizon_days: int,
) -> None:
    del input_layer
    mismatches: list[str] = []
    if decision.arm != arm:
        mismatches.append(f"arm expected={arm} actual={decision.arm}")
    if decision.ticker != ticker:
        mismatches.append(f"ticker expected={ticker} actual={decision.ticker}")
    if parse_date(decision.decision_date) != decision_date_local:
        mismatches.append(
            "decision_date expected="
            f"{decision_date_local.isoformat()} actual={decision.decision_date}"
        )
    if int(decision.horizon_days) != horizon_days:
        mismatches.append(
            f"horizon_days expected={horizon_days} actual={decision.horizon_days}"
        )
    if mismatches:
        raise ValueError("decision identity mismatch: " + "; ".join(mismatches))


def validate_visible_alaya_memory_refs(
    *,
    decision: v3.ProviderDecision,
    arm: v3.Arm,
    visible_feedback_refs: set[str],
) -> None:
    if arm != "full_gotra":
        return
    refs = [str(item) for item in decision.alaya_memory_refs]
    if not refs:
        return
    invalid_refs = sorted(ref for ref in refs if ref not in visible_feedback_refs)
    if not visible_feedback_refs or invalid_refs:
        raise ShortHorizonProvenanceError(
            "invalid alaya_memory_refs for short-horizon capture: "
            + ",".join(invalid_refs or refs)
            + f"; visible_feedback_refs={len(visible_feedback_refs)}"
        )


def validate_no_outcome_fields(payload: dict[str, Any]) -> None:
    present = sorted(FORBIDDEN_OUTCOME_FIELDS & set(payload))
    if present:
        raise ValueError("capture artifact contains forbidden outcome fields: " + ",".join(present))
    nested = payload.get("decision")
    if isinstance(nested, dict):
        nested_present = sorted(FORBIDDEN_OUTCOME_FIELDS & set(nested))
        if nested_present:
            raise ValueError(
                "capture decision contains forbidden outcome fields: "
                + ",".join(nested_present)
            )


def artifact_path(
    run_root: Path,
    *,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    decision_date_local: date,
    horizon_days: int,
) -> Path:
    return (
        run_root
        / "captures"
        / arm
        / f"capture_{decision_date_local.isoformat()}_{ticker_slug(ticker)}_h{horizon_days}_{input_layer}.json"
    )


def deterministic_reference_for_ticker(
    *,
    config: CanaryConfig,
    ticker: str,
    visible_rows: pd.DataFrame,
    future_rows_excluded: int,
) -> dict[str, Any]:
    decision_date = local_capture_date(config)
    decision = v3.deterministic_price_only_baseline_decision(
        ticker=ticker,
        decision_date=decision_date,
        price_rows=visible_rows,
    )
    latest_visible = str(decision["latest_visible_price_date"])
    return {
        "schema": DETERMINISTIC_REFERENCE_SCHEMA,
        "run_id": config.run_id,
        "baseline": "deterministic_price_only_baseline",
        "ticker": ticker,
        "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "decision_date_local": decision_date.isoformat(),
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "latest_visible_price_date": latest_visible,
        "visible_price_rows": int(decision["visible_price_rows"]),
        "future_rows_excluded": future_rows_excluded,
        "direction": decision["direction"],
        "expected_change_pct": decision["expected_change_pct"],
        "confidence": decision["confidence"],
        "future_data_violation": parse_date(latest_visible) >= decision_date,
        "llm_used": False,
        "provider_or_backend_called": False,
    }


def build_client(
    *,
    config: CanaryConfig,
    run_root: Path,
) -> v3.MockDecisionClient | v3.CodexCliBackendDecisionClient:
    if config.mode == "mock":
        return v3.MockDecisionClient(
            provider="local_mock",
            provider_model=config.provider_model,
            provider_base_url="local://mock",
        )
    return v3.CodexCliBackendDecisionClient(
        model=config.provider_model,
        reasoning_setting=config.codex_cli_reasoning_setting,
        run_root=run_root,
        provider_max_tokens=config.provider_max_tokens,
        codex_binary=config.codex_cli_binary,
        project_root=Path.cwd(),
    )


def capture_one(
    *,
    config: CanaryConfig,
    run_root: Path,
    client: v3.MockDecisionClient | v3.CodexCliBackendDecisionClient,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
) -> dict[str, Any]:
    decision_date = local_capture_date(config)
    visible_rows, future_rows_excluded, latest_visible = visible_price_rows(
        ticker,
        decision_date_local=decision_date,
        price_dir=config.price_dir,
    )
    payload = build_prompt_payload(
        config=config,
        ticker=ticker,
        arm=arm,
        input_layer=input_layer,
        visible_rows=visible_rows,
    )
    prompt_hash = stable_json_hash(payload)
    decision = client.complete(
        payload,
        request_timeout_seconds=config.request_timeout_seconds,
    )
    validate_decision_identity(
        decision=decision,
        ticker=ticker,
        arm=arm,
        input_layer=input_layer,
        decision_date_local=decision_date,
        horizon_days=config.horizon_days,
    )
    validate_visible_alaya_memory_refs(
        decision=decision,
        arm=arm,
        visible_feedback_refs=set(),
    )
    source_id = source_decision_id(
        run_id=config.run_id,
        ticker=ticker,
        arm=arm,
        input_layer=input_layer,
        decision_date_local=decision_date,
        horizon_days=config.horizon_days,
        prompt_hash=prompt_hash,
    )
    artifact = {
        "schema": CAPTURE_SCHEMA,
        "run_id": config.run_id,
        "source_decision_id": source_id,
        "capture_status": "captured",
        "capture_family": "v3.6v_short_horizon_forward_live",
        "arm": arm,
        "arm_interpretation": (
            "direct_llm_parametric_memory_control"
            if arm == "direct_llm"
            else arm
        ),
        "input_layer": input_layer,
        "ticker": ticker,
        "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "decision_date_local": decision_date.isoformat(),
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "outcome_price_available_after_utc": outcome_price_available_after_utc(config),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "outcome_scoring_allowed_now": False,
        "backend": v3.CODEX_CLI_BACKEND if config.mode == "codex-cli-capture" else "local_mock",
        "codex_cli_version": decision.codex_cli_version if config.mode != "mock" else "",
        "model": decision.codex_cli_model if config.mode != "mock" else config.provider_model,
        "reasoning": decision.codex_cli_reasoning_setting
        if config.mode != "mock"
        else config.codex_cli_reasoning_setting,
        "prompt_hash": prompt_hash,
        "source_prompt_identity_hash": prompt_hash,
        "output_transcript_path": decision.output_transcript_path
        if config.mode != "mock"
        else "",
        "parsed_decision_hash": decision.parsed_decision_hash
        if config.mode != "mock"
        else "",
        "latest_visible_price_date": latest_visible,
        "visible_price_rows": int(len(visible_rows)),
        "future_rows_excluded": future_rows_excluded,
        "future_data_allowed": False,
        "future_data_violation": parse_date(latest_visible) >= decision_date,
        "not_equivalent_to_30d": True,
        "v3_7_30d_verdict_allowed": False,
        "decision": decision_summary(decision),
    }
    validate_no_outcome_fields(artifact)
    path = artifact_path(
        run_root,
        ticker=ticker,
        arm=arm,
        input_layer=input_layer,
        decision_date_local=decision_date,
        horizon_days=config.horizon_days,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifact


def expected_capture_decisions(config: CanaryConfig) -> int:
    return len(config.tickers) * len(config.arms) * len(config.input_layers)


def maturity_ledger_for(config: CanaryConfig, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for artifact in sorted(
        artifacts,
        key=lambda item: (
            str(item.get("ticker")),
            str(item.get("arm")),
            str(item.get("input_layer")),
        ),
    ):
        ledger.append(
            {
                "source_decision_id": artifact["source_decision_id"],
                "ticker": artifact["ticker"],
                "arm": artifact["arm"],
                "input_layer": artifact["input_layer"],
                "decision_date_local": artifact["decision_date_local"],
                "horizon_days": artifact["horizon_days"],
                "horizon_end_date": artifact["horizon_end_date"],
                "outcome_price_available_after_utc": artifact[
                    "outcome_price_available_after_utc"
                ],
                "future_outcome_status": FUTURE_OUTCOME_STATUS,
                "outcome_scoring_allowed_now": False,
            }
        )
    return ledger


def summary_base(config: CanaryConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "run_id": config.run_id,
        "run_root": str(run_root),
        "script_version": SCRIPT_VERSION,
        "status": STATUS_NOT_RUN,
        "capture_family": "v3.6v_short_horizon_forward_live",
        "evidence_layer": "engineering/local + forward-live capture canary only",
        "does_not_inherit_30d_conclusions": True,
        "not_equivalent_to_30d": True,
        "thirty_day_forward_live_maturity_status": "DATA_NOT_MATURED",
        "v3_7_30d_verdict_allowed": False,
        "v3_7_verdict_executed": False,
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "outcome_scoring_allowed_now": False,
        "capture_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "decision_date_local": local_capture_date(config).isoformat(),
        "timezone": config.timezone,
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "outcome_price_available_after_utc": outcome_price_available_after_utc(config),
        "tickers": list(config.tickers),
        "arms": list(config.arms),
        "input_layers": list(config.input_layers),
        "mode": config.mode,
        "backend": v3.CODEX_CLI_BACKEND if config.mode == "codex-cli-capture" else "local_mock",
        "execute_backend": config.execute_backend,
        "model": config.provider_model,
        "reasoning": config.codex_cli_reasoning_setting,
        "expected_capture_decisions": expected_capture_decisions(config),
        "actual_capture_artifacts": 0,
        "capture_error_count": 0,
        "capture_errors": [],
        "prompt_hash_count": 0,
        "codex_cli_version": "",
        "codex_cli_version_count": 0,
        "codex_cli_version_values": [],
        "codex_cli_transcript_path_count": 0,
        "parsed_decision_hash_count": 0,
        "future_data_violation_count": 0,
        "deterministic_reference_count": 0,
        "deterministic_reference_future_data_violations": 0,
        "deterministic_reference_provider_or_backend_called": False,
        "maturity_ledger_count": 0,
        "maturity_ledger": [],
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a 30D forward-live verdict",
            "not a winner/verdict/scoring stage",
        ],
    }


def blocked_run_id_summary(config: CanaryConfig, *, run_root: Path) -> dict[str, Any]:
    summary = summary_base(config, run_root=run_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def not_run_summary(config: CanaryConfig, *, run_root: Path, reason: str) -> dict[str, Any]:
    summary = summary_base(config, run_root=run_root)
    summary.update(
        {
            "status": STATUS_NOT_RUN,
            "blocker_reasons": [reason],
        }
    )
    write_summary_files(config=config, run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def write_summary_files(
    *,
    config: CanaryConfig,
    run_root: Path,
    summary: dict[str, Any],
) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "run_id": config.run_id,
        "run_root": str(run_root),
        "status": summary["status"],
        "mode": config.mode,
        "execute_backend": config.execute_backend,
        "backend": summary["backend"],
        "model": config.provider_model,
        "reasoning": config.codex_cli_reasoning_setting,
        "capture_timestamp_utc": summary["capture_timestamp_utc"],
        "decision_date_local": summary["decision_date_local"],
        "horizon_days": config.horizon_days,
        "horizon_end_date": summary["horizon_end_date"],
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "provider_or_backend_called": summary["provider_or_backend_called"],
        "codex_cli_called": summary["codex_cli_called"],
        "formal_lite_entered": False,
    }
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def capture_failure_category(capture_errors: list[dict[str, Any]]) -> str:
    if not capture_errors:
        return ""
    if any(
        str(error.get("error_type")) == "ShortHorizonProvenanceError"
        for error in capture_errors
    ):
        return "provenance"
    schema_error_classes = {"JSONDecodeError", "SchemaContractError", "InputEchoError"}
    schema_error_types = {"KeyError", "TypeError", "ValueError"}
    if any(
        str(error.get("provider_error_class")) in schema_error_classes
        or str(error.get("error_type")) in schema_error_types
        for error in capture_errors
    ):
        return "schema"
    backend_error_classes = {
        "AuthMissing",
        "CodexCliBackendBlocked",
        "TimeoutException",
        "ConnectionError",
        "HTTPError",
        "RateLimitError",
    }
    if all(
        str(error.get("provider_error_class")) in backend_error_classes
        or str(error.get("error_type")) in {"ProviderRequestError", "RuntimeError"}
        for error in capture_errors
    ):
        return "backend"
    return "schema"


def blocker_reasons_for_status(status: str) -> list[str]:
    if status == STATUS_BLOCKED_BACKEND:
        return ["backend_blocked"]
    if status == STATUS_PROVENANCE_FAIL:
        return ["capture_provenance_failed"]
    if status == STATUS_SCHEMA_FAIL:
        return ["capture_schema_failed"]
    return ["capture_failed"]


def run_capture(config: CanaryConfig) -> dict[str, Any]:
    validate_config(config)
    run_root = config.output_dir / config.run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    if config.mode == "codex-cli-capture" and not config.execute_backend:
        return not_run_summary(
            config,
            run_root=run_root,
        reason="codex_cli_backend_requires_explicit_execute_backend",
        )

    run_root.mkdir(parents=True, exist_ok=True)
    deterministic_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for ticker in config.tickers:
        try:
            visible_rows, future_rows_excluded, _latest = visible_price_rows(
                ticker,
                decision_date_local=local_capture_date(config),
                price_dir=config.price_dir,
            )
            deterministic_records.append(
                deterministic_reference_for_ticker(
                    config=config,
                    ticker=ticker,
                    visible_rows=visible_rows,
                    future_rows_excluded=future_rows_excluded,
                )
            )
        except Exception as exc:  # noqa: BLE001 - canary must surface data blockers.
            errors.append(
                {
                    "ticker": ticker,
                    "error_type": exc.__class__.__name__,
                    "error_message": v3.redact_error(str(exc)),
                    "reason": "price_cache_unavailable",
                }
            )
    if errors:
        summary = summary_base(config, run_root=run_root)
        summary.update(
            {
                "status": STATUS_BLOCKED_DATA,
                "capture_error_count": len(errors),
                "capture_errors": errors,
                "blocker_reasons": ["local_price_cache_blocked"],
            }
        )
        write_summary_files(config=config, run_root=run_root, summary=summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary

    client = build_client(config=config, run_root=run_root)
    artifacts: list[dict[str, Any]] = []
    tasks = [
        (ticker, arm, input_layer)
        for ticker in config.tickers
        for input_layer in config.input_layers
        for arm in config.arms
    ]
    workers = 1 if config.mode == "mock" else max(1, config.backend_concurrency)
    capture_errors: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                capture_one,
                config=config,
                run_root=run_root,
                client=client,
                ticker=ticker,
                arm=arm,
                input_layer=input_layer,
            ): (ticker, arm, input_layer)
            for ticker, arm, input_layer in tasks
        }
        for future in as_completed(futures):
            ticker, arm, input_layer = futures[future]
            try:
                artifacts.append(future.result())
            except Exception as exc:  # noqa: BLE001 - canary must not hide blockers.
                capture_errors.append(
                    {
                        "ticker": ticker,
                        "arm": arm,
                        "input_layer": input_layer,
                        "error_type": exc.__class__.__name__,
                        "provider_error_class": str(
                            getattr(exc, "provider_error_class", "")
                        ),
                        "error_message": v3.redact_error(str(exc)),
                    }
                )

    future_violations = sum(1 for item in artifacts if item.get("future_data_violation"))
    reference_future_violations = sum(
        1 for item in deterministic_records if item.get("future_data_violation")
    )
    transcript_count = sum(1 for item in artifacts if item.get("output_transcript_path"))
    parsed_hash_count = sum(1 for item in artifacts if item.get("parsed_decision_hash"))
    codex_cli_versions = sorted(
        {
            str(item.get("codex_cli_version"))
            for item in artifacts
            if str(item.get("codex_cli_version") or "")
        }
    )
    expected = expected_capture_decisions(config)
    backend_called = config.mode == "codex-cli-capture" and config.execute_backend
    status = (
        STATUS_PASS
        if expected > 0
        and len(artifacts) == expected
        and not capture_errors
        and future_violations == 0
        and reference_future_violations == 0
        else STATUS_FAIL
    )
    failure_category = capture_failure_category(capture_errors)
    if capture_errors:
        if failure_category == "backend":
            status = STATUS_BLOCKED_BACKEND
        elif failure_category == "provenance":
            status = STATUS_PROVENANCE_FAIL
        else:
            status = STATUS_SCHEMA_FAIL
    summary = summary_base(config, run_root=run_root)
    summary.update(
        {
            "status": status,
            "actual_capture_artifacts": len(artifacts),
            "capture_error_count": len(capture_errors),
            "capture_errors": capture_errors[:10],
            "prompt_hash_count": sum(1 for item in artifacts if item.get("prompt_hash")),
            "codex_cli_version": codex_cli_versions[0]
            if len(codex_cli_versions) == 1
            else "",
            "codex_cli_version_count": len(codex_cli_versions),
            "codex_cli_version_values": codex_cli_versions,
            "codex_cli_transcript_path_count": transcript_count,
            "parsed_decision_hash_count": parsed_hash_count,
            "future_data_violation_count": future_violations,
            "deterministic_reference_count": len(deterministic_records),
            "deterministic_reference_future_data_violations": reference_future_violations,
            "maturity_ledger": maturity_ledger_for(config, artifacts),
            "maturity_ledger_count": len(artifacts),
            "provider_or_backend_called": backend_called,
            "codex_cli_called": backend_called,
            "blocker_reasons": []
            if status == STATUS_PASS
            else blocker_reasons_for_status(status),
        }
    )
    write_summary_files(config=config, run_root=run_root, summary=summary)
    reference_dir = run_root / "deterministic_price_only_baseline"
    reference_dir.mkdir(parents=True, exist_ok=True)
    for record in deterministic_records:
        (reference_dir / f"reference_{ticker_slug(str(record['ticker']))}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mock", "codex-cli-capture"], default="mock")
    parser.add_argument("--execute-backend", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--tickers", default=",".join(DEFAULT_TICKERS))
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    parser.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    parser.add_argument("--input-layer", default=",".join(DEFAULT_INPUT_LAYERS))
    parser.add_argument("--capture-timestamp-utc", default="")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--provider-model", default=DEFAULT_MODEL)
    parser.add_argument("--provider-max-tokens", type=int, default=2000)
    parser.add_argument("--codex-cli-reasoning-setting", default=DEFAULT_REASONING)
    parser.add_argument("--codex-cli-binary", default="codex")
    parser.add_argument("--backend-concurrency", type=int, default=1)
    parser.add_argument("--request-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> CanaryConfig:
    return CanaryConfig(
        mode=args.mode,
        execute_backend=bool(args.execute_backend),
        run_id=str(args.run_id),
        output_dir=args.output_dir,
        tickers=parse_csv(str(args.tickers)),
        horizon_days=int(args.horizon_days),
        arms=parse_arms(str(args.arms)),
        input_layers=parse_input_layers(str(args.input_layer)),
        capture_timestamp_utc=parse_timestamp(str(args.capture_timestamp_utc or "")),
        timezone=str(args.timezone),
        price_dir=args.price_dir,
        provider_model=str(args.provider_model),
        provider_max_tokens=int(args.provider_max_tokens),
        codex_cli_reasoning_setting=str(args.codex_cli_reasoning_setting),
        codex_cli_binary=str(args.codex_cli_binary),
        backend_concurrency=int(args.backend_concurrency),
        request_timeout_seconds=float(args.request_timeout_seconds),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_capture(config_from_args(parse_args(argv)))
    except Exception as exc:
        print(f"short-horizon capture canary failed: {exc}", file=sys.stderr)
        return 2
    return 0 if str(summary.get("status")) == STATUS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
