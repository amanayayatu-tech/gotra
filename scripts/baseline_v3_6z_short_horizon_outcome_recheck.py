#!/usr/bin/env python3
"""GOTRA v3.6Z short-horizon canary outcome maturity recheck."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd

from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import parse_date
from scripts import baseline_v3_6y_short_horizon_first_capture as capture_v36y
from scripts import baseline_v3_four_arm as v3


SUMMARY_SCHEMA = "gotra.baseline_v3_6z.short_horizon_outcome_recheck_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6z.short_horizon_outcome_recheck_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6z_short_horizon_outcome_recheck_"
SCRIPT_VERSION = "v3.6z-20260621"
DEFAULT_OUTCOME_WINDOW_DAYS = 7

STATUS_READY = "SHORT_HORIZON_READY"
STATUS_NOT_MATURED = "SHORT_HORIZON_NOT_MATURED"
STATUS_BLOCKED_DATA = "BLOCKED_DATA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_RUN_ID_EXISTS = "SHORT_HORIZON_RECHECK_BLOCKED_RUN_ID_EXISTS"

OUTCOME_STATUS_RESOLVED = "RESOLVED"
OUTCOME_STATUS_NOT_MATURED = "NOT_MATURED"
OUTCOME_STATUS_BLOCKED_DATA = "BLOCKED_DATA"

VALID_DIRECTIONS = {"long", "avoid", "neutral"}


@dataclass(frozen=True)
class RecheckConfig:
    recheck_run_id: str
    source_summary: Path
    expected_source_summary_sha256: str
    expected_run_id: str
    output_dir: Path
    as_of_timestamp_utc: datetime
    price_dir: Path
    outcome_window_days: int = DEFAULT_OUTCOME_WINDOW_DAYS
    allow_overwrite: bool = False


@dataclass(frozen=True)
class SourceBundle:
    summary: dict[str, Any]
    summary_sha256: str
    artifact_path: Path
    artifact: dict[str, Any]


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC).replace(microsecond=0)
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"recheck_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("recheck_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: RecheckConfig) -> None:
    validate_run_id(config.recheck_run_id)
    if config.outcome_window_days < 0:
        raise ValueError("outcome_window_days must be >= 0")
    if not config.expected_run_id:
        raise ValueError("expected_run_id is required")
    if not config.expected_source_summary_sha256:
        raise ValueError("expected_source_summary_sha256 is required")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_artifact_paths(summary: dict[str, Any]) -> list[Path]:
    run_root = Path(str(summary.get("run_root") or ""))
    if not run_root.exists():
        return []
    return sorted(path for path in (run_root / "captures").glob("**/*.json") if path.is_file())


def load_source_bundle(config: RecheckConfig) -> SourceBundle:
    if not config.source_summary.exists():
        raise FileNotFoundError(f"source summary not found: {config.source_summary}")
    summary_sha = file_sha256(config.source_summary)
    if summary_sha != config.expected_source_summary_sha256:
        raise ValueError(
            "source summary sha256 mismatch: "
            f"expected={config.expected_source_summary_sha256} actual={summary_sha}"
        )
    summary = load_json(config.source_summary)
    if summary.get("schema") != capture_v36y.SUMMARY_SCHEMA:
        raise ValueError("source summary schema mismatch")
    if summary.get("run_id") != config.expected_run_id:
        raise ValueError(
            f"source run_id mismatch: expected={config.expected_run_id} actual={summary.get('run_id')}"
        )
    if summary.get("status") != capture_v36y.STATUS_PASS:
        raise ValueError(f"source summary status is not pass: {summary.get('status')}")
    if int(summary.get("actual_capture_artifacts") or 0) != 1:
        raise ValueError("source summary must contain exactly one capture artifact")
    if int(summary.get("prompt_hash_count") or 0) < 1:
        raise ValueError("source summary missing prompt_hash_count")
    if int(summary.get("parsed_decision_hash_count") or 0) < 1:
        raise ValueError("source summary missing parsed_decision_hash_count")
    if summary.get("formal_lite_entered") is not False:
        raise ValueError("source summary unexpectedly entered formal-lite")
    if summary.get("direct_llm_interpretation") != "direct_llm_parametric_memory_control":
        raise ValueError("source summary missing direct_llm_parametric_memory_control caveat")
    artifact_paths = source_artifact_paths(summary)
    artifacts: list[tuple[Path, dict[str, Any]]] = []
    for path in artifact_paths:
        payload = load_json(path)
        if payload.get("schema") == capture_v36y.CAPTURE_SCHEMA:
            artifacts.append((path, payload))
    if len(artifacts) != 1:
        raise ValueError(f"expected exactly one source capture artifact, found {len(artifacts)}")
    artifact_path, artifact = artifacts[0]
    validate_source_artifact(summary=summary, artifact=artifact)
    return SourceBundle(
        summary=summary,
        summary_sha256=summary_sha,
        artifact_path=artifact_path,
        artifact=artifact,
    )


def validate_source_artifact(*, summary: dict[str, Any], artifact: dict[str, Any]) -> None:
    required_fields = [
        "source_decision_id",
        "ticker",
        "decision_date_local",
        "horizon_days",
        "horizon_end_date",
        "outcome_price_available_after_utc",
        "prompt_hash",
        "parsed_decision_hash",
        "output_transcript_path",
        "latest_visible_price_date",
    ]
    missing = [field for field in required_fields if not artifact.get(field)]
    if missing:
        raise ValueError("source capture artifact missing required fields: " + ",".join(missing))
    if artifact.get("run_id") != summary.get("run_id"):
        raise ValueError("source artifact run_id does not match summary")
    if artifact.get("future_outcome_status") != capture_v36y.FUTURE_OUTCOME_STATUS:
        raise ValueError("source artifact future_outcome_status is not not_matured")
    if artifact.get("formal_lite_entered") is True:
        raise ValueError("source artifact unexpectedly entered formal-lite")
    if artifact.get("arm_interpretation") != "direct_llm_parametric_memory_control":
        raise ValueError("source artifact missing direct_llm_parametric_memory_control caveat")
    if int(artifact.get("horizon_days") or 0) <= 0:
        raise ValueError("source artifact horizon_days must be positive")
    if parse_date(str(artifact["horizon_end_date"])) <= parse_date(
        str(artifact["decision_date_local"])
    ):
        raise ValueError("source artifact horizon_end_date must be after decision_date_local")


def daily_close_available_cutoff(as_of_timestamp_utc: datetime) -> date:
    return as_of_timestamp_utc.astimezone(UTC).date() - timedelta(days=1)


def available_after_timestamp(horizon_end_date: date) -> datetime:
    return datetime.combine(
        horizon_end_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=UTC,
    )


def price_on_or_before(
    *,
    ticker: str,
    target_date: date,
    price_dir: Path,
    as_of_timestamp_utc: datetime,
) -> tuple[date, float, str]:
    cutoff = daily_close_available_cutoff(as_of_timestamp_utc)
    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    visible = frame.loc[dates <= target_date]
    if visible.empty:
        raise LookupError(f"missing decision price for {ticker} on/before {target_date}")
    row = visible.iloc[-1]
    return parse_date(str(row["date"])), float(row["adj_close"]), str(price_dir / f"{ticker}.csv")


def outcome_price_in_window(
    *,
    ticker: str,
    horizon_end_date: date,
    price_dir: Path,
    as_of_timestamp_utc: datetime,
    outcome_window_days: int,
) -> tuple[date, float, str] | None:
    allowed_end = horizon_end_date + timedelta(days=outcome_window_days)
    cutoff = min(daily_close_available_cutoff(as_of_timestamp_utc), allowed_end)
    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    candidates = frame.loc[(dates >= horizon_end_date) & (dates <= cutoff)]
    if candidates.empty:
        return None
    row = candidates.iloc[0]
    return parse_date(str(row["date"])), float(row["adj_close"]), str(price_dir / f"{ticker}.csv")


def empty_outcome_fields() -> dict[str, Any]:
    return {
        "decision_price": None,
        "decision_price_date": "",
        "outcome_price": None,
        "outcome_price_date": "",
        "actual_change_pct": None,
        "actual_direction": "",
    }


def source_identity(bundle: SourceBundle) -> dict[str, Any]:
    artifact = bundle.artifact
    return {
        "source_run_id": artifact["run_id"],
        "source_decision_id": artifact["source_decision_id"],
        "source_capture_artifact": str(bundle.artifact_path),
        "source_artifact_sha256": file_sha256(bundle.artifact_path),
        "ticker": artifact["ticker"],
        "arm": artifact["arm"],
        "arm_interpretation": artifact["arm_interpretation"],
        "input_layer": artifact["input_layer"],
        "decision_date": artifact["decision_date_local"],
        "horizon_days": int(artifact["horizon_days"]),
        "horizon_end_date": artifact["horizon_end_date"],
        "prompt_hash": artifact["prompt_hash"],
        "parsed_decision_hash": artifact["parsed_decision_hash"],
        "output_transcript_path": artifact["output_transcript_path"],
        "source_capture_backend": artifact.get("backend", ""),
        "source_capture_codex_cli_version": artifact.get("codex_cli_version", ""),
        "source_capture_model": artifact.get("model", ""),
        "source_capture_reasoning": artifact.get("reasoning", ""),
    }


def base_summary(
    *,
    config: RecheckConfig,
    output_root: Path,
    status: str,
    bundle: SourceBundle | None = None,
    blocker_reasons: list[str] | None = None,
) -> dict[str, Any]:
    source_summary_sha = bundle.summary_sha256 if bundle else (
        file_sha256(config.source_summary) if config.source_summary.exists() else ""
    )
    source_run_id = (
        str(bundle.summary.get("run_id") or "") if bundle else config.expected_run_id
    )
    summary = {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "recheck_run_id": config.recheck_run_id,
        "recheck_run_root": str(output_root),
        "status": status,
        "source_run_id": source_run_id,
        "source_summary_path": str(config.source_summary),
        "source_summary_sha256": source_summary_sha,
        "expected_source_summary_sha256": config.expected_source_summary_sha256,
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "evidence_layer": "short_horizon_forward_live_canary_engineering",
        "maturity_status": status,
        "outcome_status": "",
        "resolved_count": 0,
        "scored_count": 0,
        "readiness_status": status,
        "next_check_after": "",
        "blocker_reasons": blocker_reasons or [],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_30d_verdict_allowed": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a 30D forward-live verdict",
            "not a winner/verdict stage",
        ],
    }
    if bundle:
        horizon_end = parse_date(str(bundle.artifact["horizon_end_date"]))
        summary.update(source_identity(bundle))
        summary["horizon_end_date"] = horizon_end.isoformat()
        summary["next_check_after"] = available_after_timestamp(horizon_end).isoformat().replace(
            "+00:00",
            "Z",
        )
    else:
        summary["horizon_end_date"] = ""
    summary.update(empty_outcome_fields())
    return summary


def blocked_run_id_summary(config: RecheckConfig, output_root: Path) -> dict[str, Any]:
    summary = base_summary(
        config=config,
        output_root=output_root,
        status=STATUS_BLOCKED_RUN_ID_EXISTS,
        blocker_reasons=["output_run_id_exists"],
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def write_summary_files(
    *,
    config: RecheckConfig,
    output_root: Path,
    summary: dict[str, Any],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "recheck_run_id": config.recheck_run_id,
        "status": summary["status"],
        "source_run_id": summary["source_run_id"],
        "source_summary_path": str(config.source_summary),
        "source_summary_sha256": summary["source_summary_sha256"],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def blocked_provenance_summary(
    *,
    config: RecheckConfig,
    output_root: Path,
    reason: str,
) -> dict[str, Any]:
    summary = base_summary(
        config=config,
        output_root=output_root,
        status=STATUS_BLOCKED_PROVENANCE,
        blocker_reasons=[reason],
    )
    write_summary_files(config=config, output_root=output_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def recheck_status_for(config: RecheckConfig, bundle: SourceBundle) -> dict[str, Any]:
    artifact = bundle.artifact
    horizon_end = parse_date(str(artifact["horizon_end_date"]))
    available_after = available_after_timestamp(horizon_end)
    if config.as_of_timestamp_utc < available_after:
        summary = base_summary(
            config=config,
            output_root=config.output_dir / config.recheck_run_id,
            status=STATUS_NOT_MATURED,
            bundle=bundle,
        )
        summary.update(
            {
                "outcome_status": OUTCOME_STATUS_NOT_MATURED,
                "readiness_status": STATUS_NOT_MATURED,
                "blocker_reasons": ["daily_close_not_available"],
            }
        )
        return summary

    ticker = str(artifact["ticker"])
    latest_visible = parse_date(str(artifact["latest_visible_price_date"]))
    try:
        decision_price_date, decision_price, decision_price_source = price_on_or_before(
            ticker=ticker,
            target_date=latest_visible,
            price_dir=config.price_dir,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
        )
        outcome = outcome_price_in_window(
            ticker=ticker,
            horizon_end_date=horizon_end,
            price_dir=config.price_dir,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
            outcome_window_days=config.outcome_window_days,
        )
    except (FileNotFoundError, LookupError, ValueError, KeyError) as exc:
        return blocked_data_summary(config=config, bundle=bundle, reason=v3.redact_error(str(exc)))
    if outcome is None:
        return blocked_data_summary(
            config=config,
            bundle=bundle,
            reason="outcome_price_unavailable",
        )
    outcome_price_date, outcome_price, outcome_price_source = outcome
    actual_change_pct = v3.change_pct(decision_price, outcome_price)
    actual_direction = v3.actual_direction(actual_change_pct)
    if actual_direction not in VALID_DIRECTIONS:
        return blocked_data_summary(
            config=config,
            bundle=bundle,
            reason=f"invalid_actual_direction:{actual_direction}",
        )
    summary = base_summary(
        config=config,
        output_root=config.output_dir / config.recheck_run_id,
        status=STATUS_READY,
        bundle=bundle,
    )
    summary.update(
        {
            "maturity_status": STATUS_READY,
            "outcome_status": OUTCOME_STATUS_RESOLVED,
            "decision_price": decision_price,
            "decision_price_date": decision_price_date.isoformat(),
            "decision_price_source": decision_price_source,
            "outcome_price": outcome_price,
            "outcome_price_date": outcome_price_date.isoformat(),
            "outcome_price_source": outcome_price_source,
            "actual_change_pct": actual_change_pct,
            "actual_direction": actual_direction,
            "resolved_count": 1,
            "scored_count": 1,
            "readiness_status": STATUS_READY,
            "blocker_reasons": [],
        }
    )
    return summary


def blocked_data_summary(
    *,
    config: RecheckConfig,
    bundle: SourceBundle,
    reason: str,
) -> dict[str, Any]:
    summary = base_summary(
        config=config,
        output_root=config.output_dir / config.recheck_run_id,
        status=STATUS_BLOCKED_DATA,
        bundle=bundle,
        blocker_reasons=[reason],
    )
    summary.update(
        {
            "outcome_status": OUTCOME_STATUS_BLOCKED_DATA,
            "readiness_status": STATUS_BLOCKED_DATA,
        }
    )
    return summary


def run_recheck(config: RecheckConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.recheck_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    try:
        bundle = load_source_bundle(config)
    except Exception as exc:  # noqa: BLE001 - surfaced as structured provenance blocker.
        return blocked_provenance_summary(
            config=config,
            output_root=output_root,
            reason=v3.redact_error(str(exc)),
        )
    summary = recheck_status_for(config, bundle)
    write_summary_files(config=config, output_root=output_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recheck-run-id", required=True)
    parser.add_argument("--source-summary", type=Path, required=True)
    parser.add_argument("--expected-source-summary-sha256", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--outcome-window-days", type=int, default=DEFAULT_OUTCOME_WINDOW_DAYS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RecheckConfig:
    return RecheckConfig(
        recheck_run_id=str(args.recheck_run_id),
        source_summary=args.source_summary,
        expected_source_summary_sha256=str(args.expected_source_summary_sha256),
        expected_run_id=str(args.expected_run_id),
        output_dir=args.output_dir,
        as_of_timestamp_utc=parse_timestamp(str(args.as_of_timestamp_utc or "")),
        price_dir=args.price_dir,
        outcome_window_days=int(args.outcome_window_days),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_recheck(config_from_args(parse_args(argv)))
    except Exception as exc:
        print(f"short-horizon outcome recheck failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("status") in {STATUS_READY, STATUS_NOT_MATURED} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
