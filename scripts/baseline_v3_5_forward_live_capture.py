#!/usr/bin/env python3
"""GOTRA v3.5A forward-live / future-only decision capture."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pandas as pd

from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import parse_date, ticker_slug
from scripts import baseline_v3_four_arm as v3


CAPTURE_SCHEMA = "gotra.baseline_v3_5a.forward_live_capture.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3_5a.forward_live_capture_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_5a.forward_live_capture_manifest.v1"
DETERMINISTIC_CAPTURE_SCHEMA = (
    "gotra.baseline_v3_5a.deterministic_price_only_capture_reference.v1"
)
RUN_ID_PREFIX = "baseline_v3_5a_forward_live_"
FUTURE_OUTCOME_STATUS = "not_matured"
FUTURE_OUTCOME_SCORING_STATUS = "NOT_MATURED"
DEFAULT_TICKERS = ("AAPL", "MSFT", "NVDA", "TSM", "0700.HK")
DEFAULT_V3_5A_CODEX_CLI_REASONING = "high"
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
}

Mode = Literal["mock", "codex-cli-capture"]


@dataclass(frozen=True)
class CaptureConfig:
    mode: Mode
    run_id: str
    tickers: tuple[str, ...]
    arms: tuple[v3.Arm, ...]
    input_layers: tuple[v3.InputLayer, ...]
    capture_timestamp_utc: datetime
    timezone: str
    horizon_days: int
    runs_root: Path
    price_dir: Path
    provider_model: str
    provider_max_tokens: int
    codex_cli_reasoning_setting: str
    codex_cli_binary: str
    backend_concurrency: int
    request_timeout_seconds: float
    research_artifacts_path: Path | None = None
    feedback_artifacts_path: Path | None = None


def parse_capture_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def local_capture_date(config: CaptureConfig) -> date:
    return config.capture_timestamp_utc.astimezone(ZoneInfo(config.timezone)).date()


def horizon_end_date(config: CaptureConfig) -> date:
    return local_capture_date(config) + timedelta(days=config.horizon_days)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: CaptureConfig) -> None:
    validate_run_id(config.run_id)
    if not config.tickers:
        raise ValueError("at least one ticker is required")
    if not config.arms:
        raise ValueError("at least one arm is required")
    if not config.input_layers:
        raise ValueError("at least one input layer is required")
    if config.horizon_days != v3.WINDOW_DAYS:
        raise ValueError(
            f"v3.5A capture currently supports horizon_days={v3.WINDOW_DAYS} only"
        )
    if config.backend_concurrency <= 0:
        raise ValueError("backend_concurrency must be > 0")
    slugs: dict[str, str] = {}
    for ticker in config.tickers:
        slug = ticker_slug(ticker)
        prior = slugs.get(slug)
        if prior is not None and prior != ticker:
            raise ValueError(
                f"ticker slug collision: {prior!r} and {ticker!r} both map to {slug!r}"
            )
        slugs[slug] = ticker


def preflight_visible_price_rows(config: CaptureConfig) -> None:
    decision_date_local = local_capture_date(config)
    for ticker in config.tickers:
        visible_price_rows(
            ticker,
            decision_date_local=decision_date_local,
            price_dir=config.price_dir,
        )


def visible_price_rows(
    ticker: str,
    *,
    decision_date_local: date,
    price_dir: Path,
) -> tuple[pd.DataFrame, int]:
    frame = read_price_cache(ticker, price_dir=price_dir)
    dated = frame.copy()
    dated["_gotra_visible_date"] = pd.to_datetime(dated["date"]).dt.date
    # The cache has daily dates but no intraday availability timestamp, so v3.5A
    # treats same-day rows as unavailable and defaults to the last prior row.
    visible = dated[dated["_gotra_visible_date"] < decision_date_local].drop(
        columns=["_gotra_visible_date"]
    )
    if visible.empty:
        raise RuntimeError(f"no visible price rows for {ticker} at {decision_date_local}")
    return visible, int(len(frame) - len(visible))


def timestamp_after_capture(
    value: Any,
    *,
    capture_timestamp_utc: datetime,
    decision_date_local: date,
) -> bool:
    if value in (None, ""):
        return False
    text = str(value).strip()
    try:
        if "T" in text or ":" in text:
            parsed_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=UTC)
            return parsed_dt.astimezone(UTC) > capture_timestamp_utc
        return parse_date(text) > decision_date_local
    except Exception:  # noqa: BLE001 - unknown source timestamp formats are handled elsewhere.
        return False


def capture_research_filter_result(
    *,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    ticker: str,
    decision_date_local: date,
    capture_timestamp_utc: datetime,
    price_rows: pd.DataFrame,
    research_artifacts_path: Path | None,
) -> dict[str, Any]:
    result = v3.research_artifact_filter_result(
        arm=arm,
        input_layer=input_layer,
        decision_date=decision_date_local,
        price_rows=price_rows,
        research_artifacts_path=research_artifacts_path,
        ticker=ticker,
    )
    accepted: list[dict[str, Any]] = []
    rejected_source_timestamp = 0
    for artifact in result["accepted_artifacts"]:
        source_values = [
            artifact.get("availability_date"),
            artifact.get("captured_at"),
            artifact.get("publish_timestamp"),
            artifact.get("decision_date_max"),
        ]
        if any(
            timestamp_after_capture(
                value,
                capture_timestamp_utc=capture_timestamp_utc,
                decision_date_local=decision_date_local,
            )
            for value in source_values
        ):
            rejected_source_timestamp += 1
            continue
        accepted.append(artifact)
    return {
        **result,
        "accepted_artifacts": accepted,
        "rejected_research_artifact_count": int(result["rejected_research_artifact_count"])
        + rejected_source_timestamp,
        "rejected_research_future_data_count": int(
            result["rejected_research_future_data_count"]
        )
        + rejected_source_timestamp,
        "rejected_research_source_timestamp_count": rejected_source_timestamp,
    }


def feedback_for_capture(
    *,
    config: CaptureConfig,
    ticker: str,
    input_layer: v3.InputLayer,
) -> dict[str, Any]:
    return v3.feedback_artifact_filter_result(
        feedback_artifacts_path=config.feedback_artifacts_path,
        decision_date=local_capture_date(config),
        ticker=ticker,
        input_layer=input_layer,
        current_run_id=config.run_id,
    )


def deterministic_capture_reference_for_ticker(
    *,
    config: CaptureConfig,
    ticker: str,
    visible_rows: pd.DataFrame,
    future_rows_excluded: int,
) -> dict[str, Any]:
    decision_date_local = local_capture_date(config)
    decision = v3.deterministic_price_only_baseline_decision(
        ticker=ticker,
        decision_date=decision_date_local,
        price_rows=visible_rows,
    )
    latest_visible_date = str(decision["latest_visible_price_date"])
    future_data_violation = parse_date(latest_visible_date) > decision_date_local
    return {
        "schema": DETERMINISTIC_CAPTURE_SCHEMA,
        "run_id": config.run_id,
        "baseline": "deterministic_price_only_baseline",
        "ticker": ticker,
        "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "decision_date_local": decision_date_local.isoformat(),
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "latest_visible_price_date": latest_visible_date,
        "visible_price_rows": int(decision["visible_price_rows"]),
        "future_rows_excluded": future_rows_excluded,
        "direction": decision["direction"],
        "expected_change_pct": decision["expected_change_pct"],
        "confidence": decision["confidence"],
        "input_cutoff": decision["input_cutoff"],
        "future_data_allowed": False,
        "future_data_violation": future_data_violation,
        "llm_used": False,
        "provider_or_backend_called": False,
    }


def deterministic_reference_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    future_violations = [record for record in records if record["future_data_violation"]]
    status = "REFERENCE_READY" if records and not future_violations else "REFERENCE_NEEDS_FIX"
    latest_dates = [str(record["latest_visible_price_date"]) for record in records]
    return {
        "schema": DETERMINISTIC_CAPTURE_SCHEMA,
        "status": status,
        "count": len(records),
        "unique_capture_point_count": len(records),
        "future_data_violations": len(future_violations),
        "latest_visible_price_date_max": max(latest_dates) if latest_dates else "",
        "llm_used": False,
        "provider_or_backend_called": False,
        "clean_historical_reference_status": (
            "PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE"
            if status == "REFERENCE_READY"
            else "MISSING_OR_BLOCKED_DETERMINISTIC_PRICE_ONLY_BASELINE"
        ),
    }


def deterministic_reference_empty_summary() -> dict[str, Any]:
    return {
        "schema": DETERMINISTIC_CAPTURE_SCHEMA,
        "status": "REFERENCE_NOT_COMPUTED",
        "count": 0,
        "unique_capture_point_count": 0,
        "future_data_violations": 0,
        "latest_visible_price_date_max": "",
        "llm_used": False,
        "provider_or_backend_called": False,
        "clean_historical_reference_status": (
            "MISSING_OR_BLOCKED_DETERMINISTIC_PRICE_ONLY_BASELINE"
        ),
    }


def deterministic_reference_summary_fields(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "deterministic_price_only_reference": reference,
        "deterministic_price_only_reference_status": reference["status"],
        "deterministic_price_only_reference_count": reference["count"],
        "deterministic_price_only_reference_future_data_violations": reference[
            "future_data_violations"
        ],
        "deterministic_price_only_reference_provider_or_backend_called": reference[
            "provider_or_backend_called"
        ],
        "deterministic_price_only_baseline": reference,
        "deterministic_price_only_baseline_status": reference["status"],
        "deterministic_price_only_baseline_count": reference["count"],
        "deterministic_price_only_baseline_future_data_violations": reference[
            "future_data_violations"
        ],
        "deterministic_price_only_baseline_provider_or_backend_called": reference[
            "provider_or_backend_called"
        ],
        "clean_historical_reference_status": reference["clean_historical_reference_status"],
    }


def build_capture_payload(
    *,
    config: CaptureConfig,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    visible_rows: pd.DataFrame,
    research_filter: dict[str, Any],
    feedback_filter: dict[str, Any],
) -> dict[str, Any]:
    decision_date_local = local_capture_date(config)
    feedback = feedback_filter["accepted_feedback"] if arm == "full_gotra" else []
    payload = v3.build_prompt_payload(
        arm=arm,
        input_layer=input_layer,
        ticker=ticker,
        decision_date=decision_date_local,
        price_rows=visible_rows,
        feedback=feedback,
        provider=v3.CODEX_CLI_BACKEND,
        provider_model=config.provider_model,
        scoring_segment="scored",
        research_artifacts_path=None,
        research_artifacts_override=research_filter["accepted_artifacts"],
    )
    payload["capture_policy"] = {
        "mode": "forward_live_future_only_capture",
        "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "decision_date_local": decision_date_local.isoformat(),
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "outcome_scoring_allowed_now": False,
        "do_not_include_realized_return_or_outcome_fields": True,
    }
    payload["input_policy"]["actual_outcome_visible"] = False
    payload["input_policy"]["future_outcome_status"] = FUTURE_OUTCOME_STATUS
    return payload


def capture_artifact_path(
    run_root: Path,
    *,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
    ticker: str,
    decision_date_local: date,
) -> Path:
    return (
        run_root
        / "captures"
        / arm
        / f"capture_{decision_date_local.isoformat()}_{ticker_slug(ticker)}_{input_layer}.json"
    )


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


def validate_no_outcome_fields(artifact: dict[str, Any]) -> None:
    present = sorted(FORBIDDEN_OUTCOME_FIELDS & set(artifact))
    if present:
        raise ValueError("capture artifact contains forbidden outcome fields: " + ",".join(present))
    nested = artifact.get("decision")
    if isinstance(nested, dict):
        nested_present = sorted(FORBIDDEN_OUTCOME_FIELDS & set(nested))
        if nested_present:
            raise ValueError(
                "capture decision contains forbidden outcome fields: "
                + ",".join(nested_present)
            )


def capture_one(
    *,
    config: CaptureConfig,
    run_root: Path,
    client: v3.MockDecisionClient | v3.CodexCliBackendDecisionClient,
    ticker: str,
    arm: v3.Arm,
    input_layer: v3.InputLayer,
) -> dict[str, Any]:
    decision_date_local = local_capture_date(config)
    visible_rows, future_rows_excluded = visible_price_rows(
        ticker,
        decision_date_local=decision_date_local,
        price_dir=config.price_dir,
    )
    research_filter = capture_research_filter_result(
        arm=arm,
        input_layer=input_layer,
        ticker=ticker,
        decision_date_local=decision_date_local,
        capture_timestamp_utc=config.capture_timestamp_utc,
        price_rows=visible_rows,
        research_artifacts_path=config.research_artifacts_path,
    )
    feedback_filter = feedback_for_capture(
        config=config,
        ticker=ticker,
        input_layer=input_layer,
    )
    payload = build_capture_payload(
        config=config,
        ticker=ticker,
        arm=arm,
        input_layer=input_layer,
        visible_rows=visible_rows,
        research_filter=research_filter,
        feedback_filter=feedback_filter,
    )
    prompt_hash = v3.stable_json_hash(payload)
    if config.mode == "mock":
        decision = v3.MockDecisionClient(
            provider="local_mock",
            provider_model=config.provider_model,
            provider_base_url="local://mock",
        ).complete(payload)
    else:
        decision = client.complete(
            payload,
            request_timeout_seconds=config.request_timeout_seconds,
        )
    point = v3.DecisionPoint(ticker, decision_date_local, input_layer)
    v3.validate_provider_decision_identity(decision, point=point, arm=arm)
    v3.validate_alaya_memory_refs(
        decision,
        arm=arm,
        feedback=payload.get("alaya_feedback_history") or [],
    )
    artifact = {
        "schema": CAPTURE_SCHEMA,
        "run_id": config.run_id,
        "capture_status": "captured",
        "arm": arm,
        "input_layer": input_layer,
        "ticker": ticker,
        "decision_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "decision_date_local": decision_date_local.isoformat(),
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "backend": v3.CODEX_CLI_BACKEND if config.mode == "codex-cli-capture" else "local_mock",
        "codex_cli_version": decision.codex_cli_version if config.mode != "mock" else "",
        "model": decision.codex_cli_model if config.mode != "mock" else config.provider_model,
        "reasoning": decision.codex_cli_reasoning_setting
        if config.mode != "mock"
        else config.codex_cli_reasoning_setting,
        "prompt_hash": prompt_hash,
        "output_transcript_path": decision.output_transcript_path
        if config.mode != "mock"
        else "",
        "parsed_decision_hash": decision.parsed_decision_hash
        if config.mode != "mock"
        else "",
        "latest_visible_price_date": str(visible_rows.iloc[-1]["date"]),
        "visible_price_rows": int(len(visible_rows)),
        "future_rows_excluded": future_rows_excluded,
        "future_data_allowed": False,
        "future_data_violation": parse_date(str(visible_rows.iloc[-1]["date"]))
        > decision_date_local,
        "research_artifact_count": len(research_filter["accepted_artifacts"]),
        "rejected_research_artifact_count": int(
            research_filter["rejected_research_artifact_count"]
        ),
        "rejected_research_future_data_count": int(
            research_filter["rejected_research_future_data_count"]
        ),
        "rejected_research_source_timestamp_count": int(
            research_filter.get("rejected_research_source_timestamp_count") or 0
        ),
        "feedback_artifact_count": len(feedback_filter["accepted_feedback"])
        if arm == "full_gotra"
        else 0,
        "rejected_feedback_artifact_count": int(
            feedback_filter["rejected_feedback_artifact_count"]
        ),
        "rejected_feedback_future_data_count": int(
            feedback_filter["rejected_feedback_future_data_count"]
        ),
        "decision": decision_summary(decision),
    }
    validate_no_outcome_fields(artifact)
    path = capture_artifact_path(
        run_root,
        arm=arm,
        input_layer=input_layer,
        ticker=ticker,
        decision_date_local=decision_date_local,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return artifact


def build_client(
    *,
    config: CaptureConfig,
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


def run_capture(config: CaptureConfig) -> dict[str, Any]:
    validate_config(config)
    run_root = config.runs_root / config.run_id
    if run_root.exists() and any(run_root.iterdir()):
        return blocked_summary(config=config, run_root=run_root)
    preflight_visible_price_rows(config)
    run_root.mkdir(parents=True, exist_ok=True)
    client = build_client(config=config, run_root=run_root)
    manifest = manifest_for(config=config, run_root=run_root)
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    deterministic_records: list[dict[str, Any]] = []
    reference_dir = run_root / "deterministic_price_only_baseline"
    reference_dir.mkdir(parents=True, exist_ok=True)
    for ticker in config.tickers:
        visible_rows, future_rows_excluded = visible_price_rows(
            ticker,
            decision_date_local=local_capture_date(config),
            price_dir=config.price_dir,
        )
        reference = deterministic_capture_reference_for_ticker(
            config=config,
            ticker=ticker,
            visible_rows=visible_rows,
            future_rows_excluded=future_rows_excluded,
        )
        deterministic_records.append(reference)
        (reference_dir / f"reference_capture_{ticker_slug(ticker)}.json").write_text(
            json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    artifacts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    tasks = [
        (ticker, arm, input_layer)
        for ticker in config.tickers
        for input_layer in config.input_layers
        for arm in config.arms
    ]
    workers = 1 if config.mode == "mock" else max(1, config.backend_concurrency)
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
            except Exception as exc:  # noqa: BLE001 - summary must preserve capture blockers.
                errors.append(
                    {
                        "ticker": ticker,
                        "arm": arm,
                        "input_layer": input_layer,
                        "error_type": exc.__class__.__name__,
                        "error_message": v3.redact_error(str(exc)),
                    }
                )

    summary = summary_for(
        config=config,
        run_root=run_root,
        artifacts=artifacts,
        deterministic_reference=deterministic_reference_summary(deterministic_records),
        errors=errors,
    )
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def blocked_summary(*, config: CaptureConfig, run_root: Path) -> dict[str, Any]:
    reference = deterministic_reference_empty_summary()
    summary = {
        "schema": SUMMARY_SCHEMA,
        "run_id": config.run_id,
        "status": "BLOCKED_RUN_ID_EXISTS",
        "forward_live_capture_status": "BLOCKED_RUN_ID_EXISTS",
        "run_root": str(run_root),
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "expected_capture_decisions": expected_capture_decisions(config),
        "actual_capture_artifacts": 0,
        "capture_error_count": 0,
        "capture_errors": [],
        "codex_cli_transcript_path_count": 0,
        "parsed_decision_hash_count": 0,
        "future_data_violation_count": 0,
        **deterministic_reference_summary_fields(reference),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(*, config: CaptureConfig, run_root: Path) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "run_id": config.run_id,
        "run_root": str(run_root),
        "mode": config.mode,
        "backend": v3.CODEX_CLI_BACKEND if config.mode == "codex-cli-capture" else "local_mock",
        "provider_model": config.provider_model,
        "codex_cli_reasoning_setting": config.codex_cli_reasoning_setting,
        "capture_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "decision_date_local": local_capture_date(config).isoformat(),
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "tickers": list(config.tickers),
        "arms": list(config.arms),
        "input_layers": list(config.input_layers),
        "expected_capture_decisions": expected_capture_decisions(config),
        "research_artifacts_path": str(config.research_artifacts_path or ""),
        "feedback_artifacts_path": str(config.feedback_artifacts_path or ""),
    }


def expected_capture_decisions(config: CaptureConfig) -> int:
    return len(config.tickers) * len(config.input_layers) * len(config.arms)


def summary_for(
    *,
    config: CaptureConfig,
    run_root: Path,
    artifacts: list[dict[str, Any]],
    deterministic_reference: dict[str, Any],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    transcript_count = sum(1 for item in artifacts if item.get("output_transcript_path"))
    parsed_hash_count = sum(1 for item in artifacts if item.get("parsed_decision_hash"))
    future_data_violations = sum(1 for item in artifacts if item.get("future_data_violation"))
    expected = expected_capture_decisions(config)
    reference_ready = (
        deterministic_reference["status"] == "REFERENCE_READY"
        and int(deterministic_reference["count"]) > 0
        and int(deterministic_reference["future_data_violations"]) == 0
        and deterministic_reference["provider_or_backend_called"] is False
    )
    status = (
        "FORWARD_LIVE_CAPTURE_PASS"
        if expected > 0
        and len(artifacts) == expected
        and not errors
        and future_data_violations == 0
        and reference_ready
        else "FORWARD_LIVE_CAPTURE_FAIL"
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "run_id": config.run_id,
        "run_root": str(run_root),
        "status": status,
        "forward_live_capture_status": status,
        "mode": config.mode,
        "evidence_layer": (
            "forward-live capture engineering evidence only; outcomes not matured"
        ),
        "backend": v3.CODEX_CLI_BACKEND if config.mode == "codex-cli-capture" else "local_mock",
        "codex_cli_version": artifacts[0].get("codex_cli_version", "") if artifacts else "",
        "model": config.provider_model,
        "reasoning": config.codex_cli_reasoning_setting,
        "capture_timestamp_utc": config.capture_timestamp_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "decision_date_local": local_capture_date(config).isoformat(),
        "horizon_days": config.horizon_days,
        "horizon_end_date": horizon_end_date(config).isoformat(),
        "future_outcome_status": FUTURE_OUTCOME_STATUS,
        "future_outcome_scoring_status": FUTURE_OUTCOME_SCORING_STATUS,
        "outcome_matured_count": 0,
        "outcome_scored_count": 0,
        "expected_capture_decisions": expected,
        "actual_capture_artifacts": len(artifacts),
        "capture_error_count": len(errors),
        "capture_errors": errors[:10],
        "codex_cli_transcript_path_count": transcript_count,
        "parsed_decision_hash_count": parsed_hash_count,
        "prompt_hash_count": sum(1 for item in artifacts if item.get("prompt_hash")),
        "future_data_violation_count": future_data_violations,
        "research_future_data_rejected_count": sum(
            int(item.get("rejected_research_future_data_count") or 0) for item in artifacts
        ),
        "research_source_timestamp_rejected_count": sum(
            int(item.get("rejected_research_source_timestamp_count") or 0)
            for item in artifacts
        ),
        "feedback_future_data_rejected_count": sum(
            int(item.get("rejected_feedback_future_data_count") or 0) for item in artifacts
        ),
        **deterministic_reference_summary_fields(deterministic_reference),
        "arm_interpretation": {
            "direct_llm": (
                "direct_llm_parametric_memory_control; forward-live outcome has not happened yet"
            ),
            "clean_historical_reference": "deterministic_price_only_baseline",
            "outcome_scoring": "not entered until horizon outcome matures",
        },
    }


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mock", "codex-cli-capture"], required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tickers", default=",".join(DEFAULT_TICKERS))
    parser.add_argument("--arms", default="all")
    parser.add_argument("--input-layer", default="both")
    parser.add_argument("--capture-timestamp-utc", default="")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--horizon-days", type=int, default=v3.WINDOW_DAYS)
    parser.add_argument("--runs-root", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--provider-model", default=v3.DEFAULT_CODEX_CLI_MODEL)
    parser.add_argument("--provider-max-tokens", type=int, default=2000)
    parser.add_argument(
        "--codex-cli-reasoning-setting",
        default=DEFAULT_V3_5A_CODEX_CLI_REASONING,
    )
    parser.add_argument("--codex-cli-binary", default="codex")
    parser.add_argument("--backend-concurrency", type=int, default=1)
    parser.add_argument("--request-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--research-artifacts-path", type=Path, default=None)
    parser.add_argument("--feedback-artifacts-path", type=Path, default=None)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> CaptureConfig:
    return CaptureConfig(
        mode=args.mode,
        run_id=str(args.run_id),
        tickers=parse_csv(str(args.tickers)),
        arms=parse_arms(str(args.arms)),
        input_layers=parse_input_layers(str(args.input_layer)),
        capture_timestamp_utc=parse_capture_timestamp(str(args.capture_timestamp_utc or "")),
        timezone=str(args.timezone),
        horizon_days=int(args.horizon_days),
        runs_root=args.runs_root,
        price_dir=args.price_dir,
        provider_model=str(args.provider_model),
        provider_max_tokens=int(args.provider_max_tokens),
        codex_cli_reasoning_setting=str(args.codex_cli_reasoning_setting),
        codex_cli_binary=str(args.codex_cli_binary),
        backend_concurrency=int(args.backend_concurrency),
        request_timeout_seconds=float(args.request_timeout_seconds),
        research_artifacts_path=args.research_artifacts_path,
        feedback_artifacts_path=args.feedback_artifacts_path,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_capture(config_from_args(args))
    return 0 if str(summary.get("status")) == "FORWARD_LIVE_CAPTURE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
