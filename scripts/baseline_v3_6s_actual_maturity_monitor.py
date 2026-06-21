#!/usr/bin/env python3
"""GOTRA v3.6S actual forward-live maturity monitor / readiness recheck."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from scripts import baseline_v3_5_forward_live_capture as capture_v35a
from scripts import baseline_v3_5_forward_live_matured_outcome_scorer as scorer_v35e
from scripts import baseline_v3_5_forward_live_outcome_resolver as resolver_v35b
from scripts import baseline_v3_6_forward_live_verdict_readiness_gate as readiness_v36
from scripts import baseline_v3_four_arm as v3


SUMMARY_SCHEMA = "gotra.baseline_v3_6s.actual_maturity_monitor_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6s.actual_maturity_monitor_manifest.v1"
MONITOR_RUN_ID_PREFIX = "baseline_v3_6s_actual_maturity_monitor_"
MONITOR_SCRIPT_VERSION = "v3.6s-20260621"

STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_DATA_NOT_MATURED = "DATA_NOT_MATURED"
STATUS_BLOCKED_DATA = "BLOCKED_DATA"
STATUS_BLOCKED_SOURCE_FUTURE_DATA = "BLOCKED_SOURCE_FUTURE_DATA"
STATUS_RESOLVER_PATH_ELIGIBLE = "RESOLVER_PATH_ELIGIBLE"
STATUS_BLOCKED_RUN_ID_EXISTS = "MONITOR_BLOCKED_RUN_ID_EXISTS"
STATUS_FAIL = "MONITOR_FAIL"

READINESS_NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class MonitorConfig:
    input_roots: tuple[Path, ...]
    monitor_run_id: str
    as_of_timestamp_utc: datetime
    price_dir: Path
    output_dir: Path
    readiness_summary_path: Path | None = None
    outcome_window_days: int = resolver_v35b.DEFAULT_OUTCOME_WINDOW_DAYS
    allow_overwrite: bool = False


def parse_as_of_timestamp(value: str | None) -> datetime:
    return resolver_v35b.parse_as_of_timestamp(value)


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(MONITOR_RUN_ID_PREFIX):
        raise ValueError(f"monitor_run_id must start with {MONITOR_RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("monitor_run_id may contain only letters, numbers, '_' and '-'")


def validate_config(config: MonitorConfig) -> None:
    validate_run_id(config.monitor_run_id)
    if not config.input_roots:
        raise ValueError("at least one input root is required")
    for root in config.input_roots:
        if not root.exists():
            raise FileNotFoundError(f"input root not found: {root}")
    if config.outcome_window_days < 0:
        raise ValueError("outcome_window_days must be >= 0")
    if config.readiness_summary_path is not None and not config.readiness_summary_path.exists():
        raise FileNotFoundError(
            f"readiness summary path not found: {config.readiness_summary_path}"
        )


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def capture_paths_from_roots(input_roots: tuple[Path, ...]) -> list[Path]:
    paths: set[Path] = set()
    for root in input_roots:
        if root.is_file() and root.suffix.lower() == ".json":
            candidates = [root]
        elif root.is_dir():
            candidates = list(root.glob("**/*.json"))
        else:
            candidates = []
        for path in candidates:
            try:
                payload = load_json(path)
            except Exception:
                continue
            if payload.get("schema") == capture_v35a.CAPTURE_SCHEMA:
                paths.add(path)
    return sorted(paths)


def all_json_paths(input_roots: tuple[Path, ...]) -> list[Path]:
    paths: set[Path] = set()
    for root in input_roots:
        if root.is_file() and root.suffix.lower() == ".json":
            paths.add(root)
        elif root.is_dir():
            paths.update(root.glob("**/*.json"))
    return sorted(paths)


def date_from_capture(payload: dict[str, Any], *keys: str) -> date:
    return resolver_v35b.date_from_capture(payload, *keys)


def price_availability_for_capture(
    *,
    payload: dict[str, Any],
    config: MonitorConfig,
) -> tuple[bool, str]:
    ticker = str(payload.get("ticker") or "")
    if not ticker:
        return False, "capture_missing_ticker"
    decision_date = date_from_capture(payload, "decision_date_local", "decision_date")
    latest_visible_date = date_from_capture(
        payload,
        "latest_visible_price_date",
        "decision_date_local",
    )
    horizon_end = date_from_capture(payload, "horizon_end_date")
    try:
        resolver_v35b.price_on_or_before(
            ticker=ticker,
            target_date=latest_visible_date,
            price_dir=config.price_dir,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
        )
    except Exception as exc:  # noqa: BLE001 - malformed local price caches are data blockers.
        return False, "missing_decision_price:" + v3.redact_error(str(exc))
    try:
        selected = resolver_v35b.outcome_price_in_window(
            ticker=ticker,
            horizon_end_date=horizon_end,
            as_of_timestamp_utc=config.as_of_timestamp_utc,
            price_dir=config.price_dir,
            outcome_window_days=config.outcome_window_days,
        )
    except Exception as exc:  # noqa: BLE001 - malformed local price caches are data blockers.
        return False, "missing_outcome_price:" + v3.redact_error(str(exc))
    if selected is None:
        return False, "missing_outcome_price"
    if decision_date > horizon_end:
        return False, "invalid_decision_after_horizon"
    return True, ""


def source_future_data_reasons(payload: dict[str, Any]) -> list[str]:
    try:
        decision_date = date_from_capture(payload, "decision_date_local", "decision_date")
        latest_visible_date = date_from_capture(
            payload,
            "latest_visible_price_date",
            "decision_date_local",
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as guard reason.
        return ["source_future_data_guard_invalid_dates:" + v3.redact_error(str(exc))]
    return resolver_v35b.source_future_data_violation_reasons(
        payload=payload,
        decision_date=decision_date,
        latest_visible_date=latest_visible_date,
    )


def readiness_summary_status(path: Path | None) -> tuple[str, dict[str, Any] | None]:
    if path is None:
        return READINESS_NOT_RUN, None
    payload = load_json(path)
    if payload.get("schema") != readiness_v36.SUMMARY_SCHEMA:
        return "READINESS_SUMMARY_SCHEMA_MISMATCH", payload
    return str(payload.get("status") or ""), payload


def existing_resolved_count(paths: list[Path]) -> int:
    count = 0
    for path in paths:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if (
            payload.get("schema") == resolver_v35b.RESOLVER_SCHEMA
            and payload.get("outcome_status") == resolver_v35b.STATUS_RESOLVED
        ):
            count += 1
    return count


def existing_scored_count(paths: list[Path]) -> int:
    count = 0
    for path in paths:
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("schema") == scorer_v35e.SUMMARY_SCHEMA:
            count = max(count, int(payload.get("scored_outcome_count") or 0))
    return count


def next_check_after_for(immature_horizons: list[date]) -> str:
    if not immature_horizons:
        return ""
    next_date = min(immature_horizons) + timedelta(days=1)
    return datetime.combine(next_date, time(0, 0), tzinfo=UTC).isoformat().replace(
        "+00:00",
        "Z",
    )


def monitor_status(
    *,
    capture_artifact_count: int,
    source_future_data_violation_count: int,
    matured_candidate_count: int,
    matured_price_available_count: int,
    blocked_data_count: int,
) -> str:
    if capture_artifact_count == 0:
        return STATUS_DATA_INSUFFICIENT
    if source_future_data_violation_count:
        return STATUS_BLOCKED_SOURCE_FUTURE_DATA
    if blocked_data_count:
        return STATUS_BLOCKED_DATA
    if matured_candidate_count == 0:
        return STATUS_DATA_NOT_MATURED
    if matured_price_available_count > 0:
        return STATUS_RESOLVER_PATH_ELIGIBLE
    return STATUS_FAIL


def normalize_path_for_match(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def readiness_roots_match_current(
    readiness_summary: dict[str, Any] | None,
    input_roots: tuple[Path, ...],
) -> bool:
    if not readiness_summary:
        return False
    summary_roots = readiness_summary.get("input_roots")
    if not isinstance(summary_roots, list) or not summary_roots:
        return False
    expected = {normalize_path_for_match(path) for path in input_roots}
    observed = {normalize_path_for_match(Path(str(path))) for path in summary_roots}
    return observed == expected


def next_stage_planning_allowed(
    *,
    status: str,
    readiness_status: str,
    readiness_root_match: bool,
) -> bool:
    return (
        status == STATUS_RESOLVER_PATH_ELIGIBLE
        and readiness_status == readiness_v36.STATUS_READY
        and readiness_root_match
    )


def blocker_reasons_for(
    *,
    status: str,
    readiness_status: str,
    readiness_root_match: bool,
    source_future_data_violation_count: int,
    blocked_data_count: int,
) -> list[str]:
    reasons: list[str] = []
    if status == STATUS_DATA_INSUFFICIENT:
        reasons.append("no_capture_artifacts_found")
    if status == STATUS_DATA_NOT_MATURED:
        reasons.append("capture_horizons_not_matured")
    if blocked_data_count:
        reasons.append("matured_candidates_missing_usable_price_data")
    if source_future_data_violation_count:
        reasons.append("source_future_data_contamination_detected")
    if readiness_status != readiness_v36.STATUS_READY:
        reasons.append("readiness_not_ready")
    elif status != STATUS_RESOLVER_PATH_ELIGIBLE:
        reasons.append("current_monitor_not_resolver_path_eligible")
    elif not readiness_root_match:
        reasons.append("readiness_summary_root_mismatch")
    return sorted(set(reasons))


def blocked_run_id_summary(config: MonitorConfig, output_root: Path) -> dict[str, Any]:
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocker_reasons": ["output_run_id_exists"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def base_summary(*, config: MonitorConfig, output_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "monitor_run_id": config.monitor_run_id,
        "run_root": str(output_root),
        "status": STATUS_FAIL,
        "evidence_layer": "engineering/local maturity monitoring only",
        "input_roots": [str(root) for root in config.input_roots],
        "as_of_timestamp_utc": config.as_of_timestamp_utc.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "price_dir": str(config.price_dir),
        "outcome_window_days": config.outcome_window_days,
        "checked_capture_run_count": 0,
        "checked_capture_run_ids": [],
        "capture_artifact_count": 0,
        "not_matured_count": 0,
        "matured_candidate_count": 0,
        "matured_price_available_count": 0,
        "blocked_data_count": 0,
        "blocked_future_data_count": 0,
        "resolved_count": 0,
        "scored_count": 0,
        "readiness_status": READINESS_NOT_RUN,
        "next_check_after": "",
        "blocker_reasons": [],
        "resolver_path_eligible": False,
        "next_stage_planning_allowed": False,
        "v3_7_verdict_allowed": False,
        "v3_7_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": "direct_llm_parametric_memory_control",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not a forward-live verdict",
            "no full_gotra/deterministic/ksana winner verdict",
        ],
    }


def run_monitor(config: MonitorConfig) -> dict[str, Any]:
    validate_config(config)
    output_root = config.output_dir / config.monitor_run_id
    if output_root.exists() and any(output_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, output_root)
    if output_root.exists() and config.allow_overwrite:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).replace(microsecond=0)
    capture_paths = capture_paths_from_roots(config.input_roots)
    all_paths = all_json_paths(config.input_roots)
    readiness_status, readiness_summary = readiness_summary_status(config.readiness_summary_path)
    run_ids: set[str] = set()
    not_matured = 0
    matured = 0
    matured_price_available = 0
    blocked_data = 0
    source_future = 0
    immature_horizons: list[date] = []
    data_blockers: list[dict[str, Any]] = []
    future_blockers: list[dict[str, Any]] = []

    as_of_date = config.as_of_timestamp_utc.date()
    for path in capture_paths:
        payload = load_json(path)
        run_id = str(payload.get("run_id") or "")
        if run_id:
            run_ids.add(run_id)
        try:
            horizon_end = date_from_capture(payload, "horizon_end_date")
        except Exception as exc:  # noqa: BLE001 - invalid capture cannot be matured safely.
            blocked_data += 1
            data_blockers.append(
                {
                    "capture_artifact": str(path),
                    "reason": "invalid_horizon_end_date:" + v3.redact_error(str(exc)),
                }
            )
            continue
        reasons = source_future_data_reasons(payload)
        if reasons:
            source_future += 1
            future_blockers.append(
                {
                    "capture_artifact": str(path),
                    "ticker": str(payload.get("ticker") or ""),
                    "source_future_data_violation_reasons": reasons,
                }
            )
            continue
        if as_of_date < horizon_end:
            not_matured += 1
            immature_horizons.append(horizon_end)
            continue
        matured += 1
        available, reason = price_availability_for_capture(payload=payload, config=config)
        if available:
            matured_price_available += 1
        else:
            blocked_data += 1
            data_blockers.append(
                {
                    "capture_artifact": str(path),
                    "ticker": str(payload.get("ticker") or ""),
                    "horizon_end_date": horizon_end.isoformat(),
                    "reason": reason,
                }
            )

    status = monitor_status(
        capture_artifact_count=len(capture_paths),
        source_future_data_violation_count=source_future,
        matured_candidate_count=matured,
        matured_price_available_count=matured_price_available,
        blocked_data_count=blocked_data,
    )
    readiness_root_match = readiness_roots_match_current(
        readiness_summary,
        config.input_roots,
    )
    next_stage_allowed = next_stage_planning_allowed(
        status=status,
        readiness_status=readiness_status,
        readiness_root_match=readiness_root_match,
    )
    summary = base_summary(config=config, output_root=output_root)
    summary.update(
        {
            "status": status,
            "checked_capture_run_count": len(run_ids),
            "checked_capture_run_ids": sorted(run_ids),
            "capture_artifact_count": len(capture_paths),
            "not_matured_count": not_matured,
            "matured_candidate_count": matured,
            "matured_price_available_count": matured_price_available,
            "blocked_data_count": blocked_data,
            "blocked_future_data_count": source_future,
            "source_future_data_violation_count": source_future,
            "resolved_count": existing_resolved_count(all_paths),
            "scored_count": existing_scored_count(all_paths),
            "readiness_status": readiness_status,
            "readiness_summary_path": str(config.readiness_summary_path or ""),
            "readiness_summary_schema": str((readiness_summary or {}).get("schema") or ""),
            "readiness_summary_root_match": readiness_root_match,
            "next_check_after": next_check_after_for(immature_horizons),
            "blocker_reasons": blocker_reasons_for(
                status=status,
                readiness_status=readiness_status,
                readiness_root_match=readiness_root_match,
                source_future_data_violation_count=source_future,
                blocked_data_count=blocked_data,
            ),
            "data_blockers": data_blockers[:20],
            "future_data_blockers": future_blockers[:20],
            "resolver_path_eligible": status == STATUS_RESOLVER_PATH_ELIGIBLE,
            "next_stage_planning_allowed": next_stage_allowed,
            "v3_7_verdict_allowed": False,
            "v3_7_verdict_executed": False,
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
                "+00:00",
                "Z",
            ),
            "monitor_script_version": MONITOR_SCRIPT_VERSION,
        }
    )
    manifest = manifest_for(config=config, output_root=output_root, summary=summary)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def manifest_for(
    *,
    config: MonitorConfig,
    output_root: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "monitor_run_id": config.monitor_run_id,
        "run_root": str(output_root),
        "input_roots": [str(root) for root in config.input_roots],
        "status": summary["status"],
        "as_of_timestamp_utc": summary["as_of_timestamp_utc"],
        "price_dir": str(config.price_dir),
        "readiness_summary_path": str(config.readiness_summary_path or ""),
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "evidence_layer": "engineering/local maturity monitoring only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", action="append", type=Path, required=True)
    parser.add_argument("--monitor-run-id", required=True)
    parser.add_argument("--as-of-timestamp-utc", default="")
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--readiness-summary-path", type=Path, default=None)
    parser.add_argument("--outcome-window-days", type=int, default=resolver_v35b.DEFAULT_OUTCOME_WINDOW_DAYS)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> MonitorConfig:
    return MonitorConfig(
        input_roots=tuple(args.input_root),
        monitor_run_id=str(args.monitor_run_id),
        as_of_timestamp_utc=parse_as_of_timestamp(str(args.as_of_timestamp_utc or "")),
        price_dir=args.price_dir,
        output_dir=args.output_dir,
        readiness_summary_path=args.readiness_summary_path,
        outcome_window_days=int(args.outcome_window_days),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = run_monitor(config_from_args(parse_args(argv)))
    hard_blocked = {
        STATUS_BLOCKED_RUN_ID_EXISTS,
        STATUS_BLOCKED_SOURCE_FUTURE_DATA,
        STATUS_BLOCKED_DATA,
        STATUS_FAIL,
    }
    return 1 if str(summary.get("status")) in hard_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
