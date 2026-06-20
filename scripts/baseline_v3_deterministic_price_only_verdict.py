#!/usr/bin/env python3
"""Offline deterministic price-only vs full_gotra verdict harness."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import random
from statistics import mean
import sys
from typing import Any

from scripts import baseline_v3_four_arm as v3


SUMMARY_SCHEMA = "gotra.baseline_v3.deterministic_price_only_vs_full_gotra_verdict.v1"
RUN_ID_PREFIX = "deterministic_price_only_vs_full_gotra_verdict_"
DEFAULT_SOURCE_RUN = Path(
    "data/backtest/runs/baseline_v3_4_scaled_reference_internal_20260620T120015Z"
)
DEFAULT_PRIMARY_INPUT_LAYER = "richer_research_packet"
DEFAULT_BOOTSTRAP_REPS = 10000
DEFAULT_BOOTSTRAP_SEED = 20260621
DEFAULT_MIN_PAIRED_POINTS = 20
DEFAULT_MIN_CLUSTERS = 2

VERDICT_FULL_GOTRA_BETTER = "FULL_GOTRA_BETTER"
VERDICT_DETERMINISTIC_BETTER = "DETERMINISTIC_BETTER"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
VERDICT_DATA_INSUFFICIENT = "DATA_INSUFFICIENT_FOR_DETERMINISTIC_VERDICT"


@dataclass(frozen=True)
class VerdictConfig:
    source_run_dir: Path
    output_dir: Path
    run_id: str
    primary_input_layer: str = DEFAULT_PRIMARY_INPUT_LAYER
    bootstrap_reps: int = DEFAULT_BOOTSTRAP_REPS
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED
    min_paired_points: int = DEFAULT_MIN_PAIRED_POINTS
    min_clusters: int = DEFAULT_MIN_CLUSTERS


@dataclass(frozen=True)
class PairRecord:
    ticker: str
    decision_date: str
    horizon_days: int
    deterministic_artifact: str
    full_gotra_artifact: str
    deterministic_mse: float
    full_gotra_mse: float
    deterministic_mae: float
    full_gotra_mae: float
    deterministic_direction_hit: bool
    full_gotra_direction_hit: bool
    deterministic_policy_return_pct: float
    full_gotra_policy_return_pct: float

    def to_json(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "decision_date": self.decision_date,
            "horizon_days": self.horizon_days,
            "deterministic_artifact": self.deterministic_artifact,
            "full_gotra_artifact": self.full_gotra_artifact,
            "deterministic_mse": self.deterministic_mse,
            "full_gotra_mse": self.full_gotra_mse,
            "deterministic_mae": self.deterministic_mae,
            "full_gotra_mae": self.full_gotra_mae,
            "deterministic_direction_hit": self.deterministic_direction_hit,
            "full_gotra_direction_hit": self.full_gotra_direction_hit,
            "deterministic_policy_return_pct": self.deterministic_policy_return_pct,
            "full_gotra_policy_return_pct": self.full_gotra_policy_return_pct,
        }


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_run_id() -> str:
    return RUN_ID_PREFIX + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def numeric(value: Any) -> float:
    return float(value)


def bool_value(value: Any) -> bool:
    return bool(value)


def pair_key(record: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(record.get("ticker") or ""),
        str(record.get("decision_date") or ""),
        int(record.get("horizon_days") or v3.WINDOW_DAYS),
    )


def full_gotra_key(record: dict[str, Any]) -> tuple[str, str, int, str]:
    ticker = str(record.get("ticker") or "")
    decision_date = str(record.get("decision_date") or "")
    horizon = int(record.get("horizon_days") or v3.WINDOW_DAYS)
    input_layer = str(record.get("input_layer") or "")
    return ticker, decision_date, horizon, input_layer


def source_metadata(source_run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    summary_path = source_run_dir / "summary.json"
    return {
        "source_run_dir": str(source_run_dir),
        "source_summary_path": str(summary_path),
        "source_summary_sha256": sha256_file(summary_path) if summary_path.exists() else "",
        "source_run_id": str(summary.get("run_id") or source_run_dir.name),
        "source_status": summary.get("status"),
        "source_provider": summary.get("provider"),
        "source_backend_name": summary.get("backend_name"),
        "source_expected_steps": summary.get("expected_steps"),
        "source_scored_step_count": summary.get("scored_step_count"),
        "source_paired_coverage": summary.get("paired_coverage"),
        "source_future_data_violation_count": int(summary.get("future_data_violation_count") or 0),
        "source_research_source_leak_count": int(summary.get("research_source_leak_count") or 0),
        "source_feedback_source_leak_count": int(summary.get("feedback_source_leak_count") or 0),
        "deterministic_reference_status": summary.get(
            "deterministic_price_only_baseline_status"
        ),
        "deterministic_reference_count": summary.get(
            "deterministic_price_only_baseline_count"
        ),
        "clean_historical_reference_status": summary.get("clean_historical_reference_status"),
    }


def load_reference_records(source_run_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    reference_dir = source_run_dir / "deterministic_price_only_baseline"
    return [(path, load_json(path)) for path in sorted(reference_dir.glob("*.json"))]


def load_full_gotra_records(source_run_dir: Path) -> dict[tuple[str, str, int, str], tuple[Path, dict[str, Any]]]:
    records: dict[tuple[str, str, int, str], tuple[Path, dict[str, Any]]] = {}
    for path in sorted((source_run_dir / "full_gotra").glob("*.json")):
        payload = load_json(path)
        records[full_gotra_key(payload)] = (path, payload)
    return records


def record_has_provenance(path: Path, record: dict[str, Any]) -> bool:
    return path.exists() and bool(record.get("run_id")) and bool(record.get("schema"))


def record_metric_complete(record: dict[str, Any]) -> bool:
    required = [
        "mse",
        "mae",
        "actual_change_pct",
        "actual_direction",
        "direction_hit",
        "policy_a_return_pct",
    ]
    return all(record.get(key) is not None for key in required)


def excluded_reason_for_reference(path: Path, record: dict[str, Any]) -> str:
    if record.get("status") != "scored":
        return "deterministic_not_scored"
    if not record_has_provenance(path, record):
        return "deterministic_missing_provenance"
    if record.get("future_data_violation"):
        return "deterministic_future_data_violation"
    if not record_metric_complete(record):
        return "deterministic_missing_metrics"
    return ""


def excluded_reason_for_full(path: Path, record: dict[str, Any]) -> str:
    if record.get("status") != "scored":
        return "full_gotra_not_scored"
    if record.get("scoring_segment") != "scored":
        return "full_gotra_not_scored_segment"
    if not record_has_provenance(path, record):
        return "full_gotra_missing_provenance"
    if record.get("future_data_violation"):
        return "full_gotra_future_data_violation"
    if record.get("research_source_leak") or record.get("feedback_source_leak"):
        return "full_gotra_source_leak"
    if not record_metric_complete(record):
        return "full_gotra_missing_metrics"
    return ""


def outcomes_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        abs(numeric(left["actual_change_pct"]) - numeric(right["actual_change_pct"])) < 1e-9
        and str(left["actual_direction"]) == str(right["actual_direction"])
    )


def build_pairs(config: VerdictConfig) -> tuple[list[PairRecord], Counter[str]]:
    excluded: Counter[str] = Counter()
    full_records = load_full_gotra_records(config.source_run_dir)
    pairs: list[PairRecord] = []
    for ref_path, ref in load_reference_records(config.source_run_dir):
        ref_reason = excluded_reason_for_reference(ref_path, ref)
        if ref_reason:
            excluded[ref_reason] += 1
            continue
        ticker, decision_date, horizon = pair_key(ref)
        full_key = (ticker, decision_date, horizon, config.primary_input_layer)
        full_item = full_records.get(full_key)
        if full_item is None:
            excluded["missing_full_gotra_primary_input_layer"] += 1
            continue
        full_path, full = full_item
        full_reason = excluded_reason_for_full(full_path, full)
        if full_reason:
            excluded[full_reason] += 1
            continue
        if not outcomes_match(ref, full):
            excluded["outcome_mismatch"] += 1
            continue
        pairs.append(
            PairRecord(
                ticker=ticker,
                decision_date=decision_date,
                horizon_days=horizon,
                deterministic_artifact=str(ref_path),
                full_gotra_artifact=str(full_path),
                deterministic_mse=numeric(ref["mse"]),
                full_gotra_mse=numeric(full["mse"]),
                deterministic_mae=numeric(ref["mae"]),
                full_gotra_mae=numeric(full["mae"]),
                deterministic_direction_hit=bool_value(ref["direction_hit"]),
                full_gotra_direction_hit=bool_value(full["direction_hit"]),
                deterministic_policy_return_pct=numeric(ref["policy_a_return_pct"]),
                full_gotra_policy_return_pct=numeric(full["policy_a_return_pct"]),
            )
        )
    return pairs, excluded


def mean_or_none(values: list[float]) -> float | None:
    return round(mean(values), 6) if values else None


def sum_or_none(values: list[float]) -> float | None:
    return round(sum(values), 6) if values else None


def metric_summary(pairs: list[PairRecord]) -> dict[str, Any]:
    if not pairs:
        return {
            "paired_count": 0,
            "deterministic_price_only": {},
            "full_gotra": {},
        }
    return {
        "paired_count": len(pairs),
        "deterministic_price_only": {
            "mse": mean_or_none([p.deterministic_mse for p in pairs]),
            "mae": mean_or_none([p.deterministic_mae for p in pairs]),
            "direction_hit_rate": mean_or_none(
                [1.0 if p.deterministic_direction_hit else 0.0 for p in pairs]
            ),
            "policy_a_cumulative_return_pct": sum_or_none(
                [p.deterministic_policy_return_pct for p in pairs]
            ),
        },
        "full_gotra": {
            "mse": mean_or_none([p.full_gotra_mse for p in pairs]),
            "mae": mean_or_none([p.full_gotra_mae for p in pairs]),
            "direction_hit_rate": mean_or_none(
                [1.0 if p.full_gotra_direction_hit else 0.0 for p in pairs]
            ),
            "policy_a_cumulative_return_pct": sum_or_none(
                [p.full_gotra_policy_return_pct for p in pairs]
            ),
        },
    }


def diff_by_cluster(pairs: list[PairRecord], metric: str) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for pair in pairs:
        if metric == "mse_loss_diff_det_minus_full":
            value = pair.deterministic_mse - pair.full_gotra_mse
        elif metric == "mae_loss_diff_det_minus_full":
            value = pair.deterministic_mae - pair.full_gotra_mae
        elif metric == "direction_hit_diff_full_minus_det":
            value = (1.0 if pair.full_gotra_direction_hit else 0.0) - (
                1.0 if pair.deterministic_direction_hit else 0.0
            )
        elif metric == "policy_return_diff_full_minus_det":
            value = pair.full_gotra_policy_return_pct - pair.deterministic_policy_return_pct
        else:
            raise ValueError(f"unknown metric diff: {metric}")
        grouped[pair.ticker].append(round(value, 12))
    return dict(sorted(grouped.items()))


def cluster_bootstrap_mean_ci(
    diffs_by_cluster: dict[str, list[float]],
    *,
    reps: int,
    seed: int,
    alpha: float = 0.05,
) -> dict[str, Any]:
    clusters = [(cluster, list(values)) for cluster, values in sorted(diffs_by_cluster.items()) if values]
    flat = [value for _cluster, values in clusters for value in values]
    if len(clusters) < 2 or not flat:
        return {
            "completed": False,
            "reason": "not_enough_paired_clusters",
            "mean": mean_or_none(flat),
            "ci_low": None,
            "ci_high": None,
            "n": len(flat),
            "cluster_count": len(clusters),
            "bootstrap_reps": reps,
            "seed": seed,
        }
    rng = random.Random(seed)
    samples: list[float] = []
    cluster_count = len(clusters)
    for _ in range(max(1, reps)):
        sampled: list[float] = []
        for _cluster_index in range(cluster_count):
            _cluster, values = clusters[rng.randrange(cluster_count)]
            sampled.extend(values)
        samples.append(mean(sampled))
    samples.sort()
    low_index = int((alpha / 2) * (len(samples) - 1))
    high_index = int((1 - alpha / 2) * (len(samples) - 1))
    return {
        "completed": True,
        "mean": round(mean(flat), 6),
        "ci_low": round(samples[low_index], 6),
        "ci_high": round(samples[high_index], 6),
        "n": len(flat),
        "cluster_count": cluster_count,
        "bootstrap_reps": reps,
        "seed": seed,
        "positive_diff_semantics": "positive means full_gotra better",
    }


def paired_statistics(pairs: list[PairRecord], config: VerdictConfig) -> dict[str, Any]:
    metrics = [
        "mse_loss_diff_det_minus_full",
        "mae_loss_diff_det_minus_full",
        "direction_hit_diff_full_minus_det",
        "policy_return_diff_full_minus_det",
    ]
    return {
        metric: cluster_bootstrap_mean_ci(
            diff_by_cluster(pairs, metric),
            reps=config.bootstrap_reps,
            seed=config.bootstrap_seed,
        )
        for metric in metrics
    }


def verdict_from_stats(
    *,
    pairs: list[PairRecord],
    cluster_count: int,
    stats: dict[str, Any],
    config: VerdictConfig,
) -> tuple[str, str]:
    if len(pairs) < config.min_paired_points:
        return VERDICT_DATA_INSUFFICIENT, "paired_count_below_minimum"
    if cluster_count < config.min_clusters:
        return VERDICT_DATA_INSUFFICIENT, "cluster_count_below_minimum"
    primary = stats["mse_loss_diff_det_minus_full"]
    if not primary.get("completed"):
        return VERDICT_DATA_INSUFFICIENT, str(primary.get("reason") or "bootstrap_not_completed")
    if primary["ci_low"] > 0:
        return VERDICT_FULL_GOTRA_BETTER, "mse_ci_excludes_zero_positive"
    if primary["ci_high"] < 0:
        return VERDICT_DETERMINISTIC_BETTER, "mse_ci_excludes_zero_negative"
    return VERDICT_INCONCLUSIVE, "mse_ci_includes_zero"


def run_verdict(config: VerdictConfig) -> dict[str, Any]:
    if not config.source_run_dir.exists():
        raise FileNotFoundError(f"source run dir not found: {config.source_run_dir}")
    source_summary_path = config.source_run_dir / "summary.json"
    source_summary = load_json(source_summary_path)
    pairs, excluded = build_pairs(config)
    clusters = sorted({pair.ticker for pair in pairs})
    stats = paired_statistics(pairs, config)
    verdict, verdict_reason = verdict_from_stats(
        pairs=pairs,
        cluster_count=len(clusters),
        stats=stats,
        config=config,
    )
    future_violations = (
        int(source_summary.get("future_data_violation_count") or 0)
        + excluded.get("deterministic_future_data_violation", 0)
        + excluded.get("full_gotra_future_data_violation", 0)
    )
    if future_violations:
        verdict = VERDICT_DATA_INSUFFICIENT
        verdict_reason = "future_data_violation_detected"
    run_root = config.output_dir / config.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "run_id": config.run_id,
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "VERDICT_READY" if verdict != VERDICT_DATA_INSUFFICIENT else VERDICT_DATA_INSUFFICIENT,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "evidence_layer": "offline/internal historical deterministic verdict only",
        "non_claims": [
            "not OOS",
            "not science/public proof",
            "not trading or investment advice",
            "not provider/backend/formal-lite",
        ],
        "comparison": "deterministic_price_only_baseline_vs_full_gotra",
        "primary_full_gotra_input_layer": config.primary_input_layer,
        "deterministic_baseline_rule": (
            "existing v3.4 deterministic_price_only_baseline reference; "
            "price-only, no LLM, no parameter memory, features available by decision_date"
        ),
        "direct_llm_caveat": (
            "direct_llm is direct_llm_parametric_memory_control and is not used as the clean baseline"
        ),
        "paired_count": len(pairs),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "min_paired_points": config.min_paired_points,
        "min_clusters": config.min_clusters,
        "bootstrap_reps": config.bootstrap_reps,
        "bootstrap_seed": config.bootstrap_seed,
        "metric_summary": metric_summary(pairs),
        "paired_statistics": stats,
        "excluded_reason_counts": dict(sorted(excluded.items())),
        "future_data_violation_count": future_violations,
        "provider_or_backend_called": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "source_metadata": source_metadata(config.source_run_dir, source_summary),
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_root / "pairs.json").write_text(
        json.dumps([pair.to_json() for pair in pairs], ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-dir", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--run-id", default=stable_run_id())
    parser.add_argument("--primary-input-layer", default=DEFAULT_PRIMARY_INPUT_LAYER)
    parser.add_argument("--bootstrap-reps", type=int, default=DEFAULT_BOOTSTRAP_REPS)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--min-paired-points", type=int, default=DEFAULT_MIN_PAIRED_POINTS)
    parser.add_argument("--min-clusters", type=int, default=DEFAULT_MIN_CLUSTERS)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> VerdictConfig:
    return VerdictConfig(
        source_run_dir=args.source_run_dir,
        output_dir=args.output_dir,
        run_id=str(args.run_id),
        primary_input_layer=str(args.primary_input_layer),
        bootstrap_reps=int(args.bootstrap_reps),
        bootstrap_seed=int(args.bootstrap_seed),
        min_paired_points=int(args.min_paired_points),
        min_clusters=int(args.min_clusters),
    )


def main(argv: list[str] | None = None) -> int:
    run_verdict(config_from_args(parse_args(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
