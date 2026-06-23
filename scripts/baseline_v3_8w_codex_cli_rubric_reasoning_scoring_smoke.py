#!/usr/bin/env python3
"""GOTRA v3.8W Codex CLI rubric reasoning scoring smoke harness."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_8j_cognitive_lift_rubric_prereg_schema as rubric  # noqa: E402
from scripts import baseline_v3_8r_rubric_anchored_reasoning_quality_prereg as prereg  # noqa: E402


SUMMARY_SCHEMA = "gotra.v3_8w.codex_cli_rubric_reasoning_scoring_smoke_summary.v1"
MANIFEST_SCHEMA = "gotra.v3_8w.codex_cli_rubric_reasoning_scoring_smoke_manifest.v1"
RUN_ID_PREFIX = "gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_"
RUN_ID_RE = re.compile(rf"^{RUN_ID_PREFIX}[0-9TZ_-]+$")
SCRIPT_VERSION = "v3.8w-20260622"
EVIDENCE_LAYER = "smoke_evidence_codex_cli_llm_api_rubric_reasoning_scoring"
RUBRIC_VERSION = rubric.SCHEMA_VERSION
ACTUAL_30D_READINESS_STATUS = rubric.ACTUAL_30D_READINESS_STATUS
SUPERIORITY_STATUS = rubric.SUPERIORITY_STATUS
DIRECT_INTERPRETATION = rubric.DIRECT_INTERPRETATION
DIRECT_INTERPRETATION_KEY = rubric.DIRECT_INTERPRETATION_KEY
DIRECT_CLEAN_BASELINE_KEY = rubric.DIRECT_CLEAN_BASELINE_KEY
RAW_ROOT = Path("/tmp/gotra_rubric_reasoning_quality")
RAW_OUTPUT_BOUNDARY = "/tmp/gotra_rubric_reasoning_quality/** only"
COST_CAP_USD = 500.00
TOKEN_BUDGET_HARD_CAP = 1_000_000_000

STATUS_PASS = "PASS"
STATUS_BLOCKED_USAGE_METADATA = "BLOCKED_USAGE_METADATA"
STATUS_BLOCKED_COST_CAP_EXHAUSTED = "BLOCKED_COST_CAP_EXHAUSTED"
STATUS_BLOCKED_RAW_BOUNDARY = "BLOCKED_RAW_BOUNDARY"
STATUS_BLOCKED_RUNTIME_BOUNDARY = "BLOCKED_RUNTIME_BOUNDARY"
STATUS_NEEDS_REPAIR = "NEEDS_REPAIR"

ALLOWED_STATUSES = {
    STATUS_PASS,
    STATUS_BLOCKED_USAGE_METADATA,
    STATUS_BLOCKED_COST_CAP_EXHAUSTED,
    STATUS_BLOCKED_RAW_BOUNDARY,
    STATUS_BLOCKED_RUNTIME_BOUNDARY,
    STATUS_NEEDS_REPAIR,
}
CLI_SUCCESS_STATUSES = {STATUS_PASS}
REQUIRED_RAW_FILES = ("stream_jsonl_path", "last_message_path")
TOKEN_FIELD_NAMES = {
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}
COST_FIELD_RE = re.compile(r"(?:^|_)(?:cost|cost_usd|total_cost_usd|observed_cost_usd)$")
RAW_CONTENT_RE = re.compile(
    r"\b(?:full transcript|raw transcript|provider transcript|raw provider output)\b",
    re.IGNORECASE,
)
CLAIM_BOUNDARY_RE = re.compile(
    r"\b(?:market\s+edge|public\s+science\s+proof|trading\s+advice|"
    r"investment\s+advice|30D\s+actual\s+verdict\s+ready)\b|P\s*(?:&|&amp;)\s*L",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SmokeConfig:
    smoke_id: str
    output_dir: Path
    stream_jsonl_path: Path
    last_message_path: Path
    stderr_path: Path | None = None
    command: str = ""
    latency_ms: int | None = None
    model_config: str | None = None
    run_mode: str = "smoke"
    run_scope: str = "minimal_codex_cli_json_smoke"
    cost_cap_usd: float = COST_CAP_USD
    allow_overwrite: bool = False


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_under_raw_root(path: Path | str | None) -> bool:
    if path is None:
        return True
    try:
        Path(path).resolve().relative_to(RAW_ROOT.resolve())
    except ValueError:
        return False
    return True


def validate_run_id(run_id: str) -> list[dict[str, Any]]:
    if RUN_ID_RE.fullmatch(run_id) is None:
        return [prereg.blocked_item("summary.smoke_id", "smoke_id_invalid", "smoke_id has invalid shape")]
    return []


def jsonl_objects(path: Path) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if not path.exists():
        return objects
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def recursive_items(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(recursive_items(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(recursive_items(child, f"{path}[{index}]"))
    return items


def extract_usage_metadata(events: list[dict[str, Any]]) -> dict[str, Any]:
    token_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }
    usage_paths: list[str] = []
    cost_values: list[float] = []
    model_values: list[str] = []
    for event in events:
        for path, value in recursive_items(event):
            key = path.rsplit(".", maxsplit=1)[-1]
            if isinstance(value, int | float) and key in TOKEN_FIELD_NAMES:
                token_totals[key] += int(value)
                usage_paths.append(path)
            if isinstance(value, int | float) and COST_FIELD_RE.search(key):
                cost_values.append(float(value))
            if isinstance(value, str) and key in {"model", "model_slug", "provider_model"}:
                model_values.append(value)
    inferred_total = token_totals["total_tokens"]
    if inferred_total == 0:
        inferred_total = (
            token_totals["input_tokens"]
            + token_totals["output_tokens"]
            + token_totals["cached_input_tokens"]
            + token_totals["reasoning_output_tokens"]
        )
    return {
        "usage_metadata_available": bool(usage_paths and inferred_total > 0),
        "usage_paths": sorted(set(usage_paths)),
        "token_usage": token_totals,
        "token_usage_total": inferred_total,
        "cost_observed_usd": round(sum(cost_values), 6) if cost_values else None,
        "model_config": sorted(set(model_values)),
    }


def raw_file_paths(config: SmokeConfig) -> list[Path]:
    paths = [config.stream_jsonl_path, config.last_message_path]
    if config.stderr_path is not None:
        paths.append(config.stderr_path)
    return paths


def raw_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256_file(path) for path in paths if path.exists() and path.is_file()}


def base_summary(config: SmokeConfig, *, run_root: Path, status: str) -> dict[str, Any]:
    raw_paths = [str(path) for path in raw_file_paths(config)]
    is_batch = config.run_mode == "synthetic_batch"
    return {
        "schema": SUMMARY_SCHEMA,
        "schema_id": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "smoke_id": config.smoke_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "created_at_utc": utc_now_iso(),
        "status": status,
        "evidence_layer": EVIDENCE_LAYER,
        "authorized_llm_path": "codex_cli_llm_api",
        "allowed_command_family": ["codex exec"],
        "run_mode": config.run_mode,
        "run_scope": config.run_scope,
        "command": config.command,
        "model_config": config.model_config,
        "cost_cap_usd": config.cost_cap_usd,
        "cost_observed_usd": None,
        "hard_stop_if_projected_cost_exceeds_cap": STATUS_BLOCKED_COST_CAP_EXHAUSTED,
        "token_budget_hard_cap": TOKEN_BUDGET_HARD_CAP,
        "token_budget_policy": "hard_cap_not_target",
        "real_calls_count": 1,
        "token_usage_total": 0,
        "usage_metadata_available": False,
        "usage_paths": [],
        "latency_summary_ms": {
            "min": config.latency_ms,
            "median": config.latency_ms,
            "max": config.latency_ms,
        },
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "raw_tmp_paths": raw_paths,
        "raw_tmp_sha256s": {},
        "repo_raw_artifacts": [],
        "no_raw_repo": True,
        "provider_or_backend_called": False,
        "provider_canary_executed": False,
        "codex_cli_called": True,
        "codex_cli_new_call": True,
        "formal_lite_entered": False,
        "actual_30d_verdict_executed": False,
        "v3_7_actual_verdict_executable": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "rubric_anchored_reasoning_quality_verdict_status": "RUBRIC_ANCHORED_REASONING_QUALITY_EVALUATION_READY",
        DIRECT_INTERPRETATION_KEY: DIRECT_INTERPRETATION,
        DIRECT_CLEAN_BASELINE_KEY: False,
        "clean_comparator_policy": {
            "direct_llm_diagnostic_only": True,
            "required_non_direct_comparator": True,
            "selected_clean_references": ["deterministic_price_only"],
        },
        "effect_summary": {"emitted": False, "values": None},
        "can_say": [
            "v3.8W Codex CLI minimal smoke path executed within raw tmp boundary",
            "repo-facing artifact contains only hashes, counts, status, and summary metadata",
        ],
        "cannot_say": [
            "not_bounded_reasoning_quality_verdict",
            "not_actual_30d_verdict",
            "not_forward_live_outcome_superiority",
            "not_realized_pnl_verdict",
            "not_public_science_proof",
            "not_trading_or_investment_advice",
            "not_superiority_over_direct_llm_as_clean_baseline",
        ],
        "non_claims": [
            "not_market_edge_verdict",
            "not_realized_pnl_verdict",
            "not_actual_30d_verdict",
            "not_forward_live_outcome_superiority",
            "not_public_science_proof",
            "not_trading_or_investment_advice",
            "not_superiority_over_direct_llm_as_clean_baseline",
            "direct_llm_is_parametric_memory_control_only",
        ],
        "bounded_batch_executed": is_batch,
        "bounded_batch_reason": (
            "synthetic/local bounded batch executed after smoke usage metadata was available"
            if is_batch
            else "minimal smoke run; bounded batch eligibility checked separately"
        ),
        "blocker_reasons": [],
        "blocked_items": [],
    }


def validate_summary_payload(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(validate_run_id(str(summary.get("smoke_id") or "")))
    if summary.get("status") not in ALLOWED_STATUSES:
        blockers.append(prereg.blocked_item("summary.status", "status_invalid", "status is not allowed"))
    if summary.get("run_mode") not in {"smoke", "synthetic_batch"}:
        blockers.append(
            prereg.blocked_item("summary.run_mode", "run_mode_invalid", "run_mode is not allowed")
        )
    if not isinstance(summary.get("run_scope"), str) or not summary.get("run_scope"):
        blockers.append(
            prereg.blocked_item("summary.run_scope", "run_scope_missing", "run_scope is required")
        )
    if summary.get("run_mode") == "synthetic_batch":
        if summary.get("bounded_batch_executed") is not True:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_batch_executed",
                    "synthetic_batch_metadata_not_true",
                    "synthetic batch summaries must mark bounded_batch_executed=true",
                )
            )
        reason = str(summary.get("bounded_batch_reason") or "")
        if "synthetic/local bounded batch" not in reason:
            blockers.append(
                prereg.blocked_item(
                    "summary.bounded_batch_reason",
                    "synthetic_batch_reason_missing",
                    "synthetic batch reason must explain the scoped batch",
                )
            )
    elif summary.get("bounded_batch_executed") is not False:
        blockers.append(
            prereg.blocked_item(
                "summary.bounded_batch_executed",
                "smoke_batch_metadata_not_false",
                "minimal smoke summaries must not mark batch execution",
            )
        )
    for key in REQUIRED_RAW_FILES:
        raw_path = summary.get(key) or _path_from_summary(summary, key)
        if raw_path and not is_under_raw_root(raw_path):
            blockers.append(
                prereg.blocked_item(f"summary.{key}", "raw_path_not_under_boundary", "raw path must stay under raw root")
            )
    for path in summary.get("raw_tmp_paths", []):
        if not is_under_raw_root(path):
            blockers.append(
                prereg.blocked_item(path, "raw_tmp_path_not_under_boundary", "raw path must stay under raw root")
            )
    if summary.get("repo_raw_artifacts") != []:
        blockers.append(
            prereg.blocked_item("summary.repo_raw_artifacts", "repo_raw_artifacts_not_empty", "repo raw artifacts must be empty")
        )
    if summary.get("no_raw_repo") is not True:
        blockers.append(prereg.blocked_item("summary.no_raw_repo", "no_raw_repo_not_true", "no raw repo must be true"))
    if summary.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(
            prereg.blocked_item("summary.actual_30d_readiness_status", "actual_30d_readiness_status_invalid", "must remain DATA_NOT_MATURED")
        )
    if summary.get("cognitive_lift_superiority_verdict_status") != SUPERIORITY_STATUS:
        blockers.append(
            prereg.blocked_item("summary.cognitive_lift_superiority_verdict_status", "cognitive_lift_superiority_status_invalid", "must remain not ready")
        )
    if summary.get(DIRECT_CLEAN_BASELINE_KEY) is not False:
        blockers.append(
            prereg.blocked_item(f"summary.{DIRECT_CLEAN_BASELINE_KEY}", "direct_llm_clean_baseline_not_false", "direct control cannot be clean baseline")
        )
    if summary.get(DIRECT_INTERPRETATION_KEY) != DIRECT_INTERPRETATION:
        blockers.append(
            prereg.blocked_item(f"summary.{DIRECT_INTERPRETATION_KEY}", "direct_llm_interpretation_invalid", "direct interpretation must be parametric-memory control")
        )
    for flag in (
        "provider_or_backend_called",
        "provider_canary_executed",
        "formal_lite_entered",
        "actual_30d_verdict_executed",
        "v3_7_actual_verdict_executable",
    ):
        if summary.get(flag) is not False:
            blockers.append(prereg.blocked_item(f"summary.{flag}", f"{flag}_not_false", f"{flag} must be false"))
    if summary.get("cost_observed_usd") is not None and float(summary["cost_observed_usd"]) > COST_CAP_USD:
        blockers.append(
            prereg.blocked_item("summary.cost_observed_usd", "cost_cap_exhausted", "observed cost exceeds cap")
        )
    if int(summary.get("token_usage_total") or 0) >= TOKEN_BUDGET_HARD_CAP:
        blockers.append(
            prereg.blocked_item("summary.token_usage_total", "token_cap_exhausted", "token usage reached hard cap")
        )
    for path, text in prereg.recursive_strings(summary, path="summary"):
        if path.endswith("command") or path.endswith("raw_output_boundary"):
            continue
        if RAW_CONTENT_RE.search(text):
            blockers.append(
                prereg.blocked_item(path, "repo_facing_raw_reference", "repo-facing summary cannot include raw/full transcript wording")
            )
        if CLAIM_BOUNDARY_RE.search(text):
            blockers.append(
                prereg.blocked_item(path, "claim_boundary_forbidden_wording", "summary contains forbidden claim wording")
            )
    return blockers


def _path_from_summary(summary: dict[str, Any], key: str) -> str | None:
    if key == "stream_jsonl_path":
        return next((path for path in summary.get("raw_tmp_paths", []) if path.endswith("stream.jsonl")), None)
    if key == "last_message_path":
        return next((path for path in summary.get("raw_tmp_paths", []) if path.endswith("last_message.txt")), None)
    return None


def finalize_summary(summary: dict[str, Any]) -> None:
    blockers = validate_summary_payload(summary)
    if blockers:
        if any(item["rule_id"] == "cost_cap_exhausted" for item in blockers):
            summary["status"] = STATUS_BLOCKED_COST_CAP_EXHAUSTED
        elif any("raw" in item["rule_id"] for item in blockers):
            summary["status"] = STATUS_BLOCKED_RAW_BOUNDARY
        else:
            summary["status"] = STATUS_NEEDS_REPAIR
    elif summary["status"] == STATUS_PASS and summary.get("usage_metadata_available") is not True:
        summary["status"] = STATUS_BLOCKED_USAGE_METADATA
        blockers.append(
            prereg.blocked_item(
                "summary.usage_metadata_available",
                "usage_metadata_unavailable",
                "Codex CLI JSON stream did not expose adequate usage metadata",
            )
        )
    summary["blocker_reasons"] = sorted({str(item["rule_id"]) for item in blockers})
    summary["blocked_items"] = blockers


def build_summary(config: SmokeConfig) -> dict[str, Any]:
    run_root = config.output_dir / config.smoke_id
    run_id_blockers = validate_run_id(config.smoke_id)
    if run_id_blockers:
        summary = base_summary(config, run_root=run_root, status=STATUS_NEEDS_REPAIR)
        summary["blocker_reasons"] = ["smoke_id_invalid"]
        summary["blocked_items"] = run_id_blockers
        return summary
    if not is_under_raw_root(config.output_dir):
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RAW_BOUNDARY)
        summary["blocker_reasons"] = ["output_dir_not_raw_root"]
        return summary
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config, run_root=run_root, status=STATUS_BLOCKED_RUNTIME_BOUNDARY)
        summary["blocker_reasons"] = ["run_id_exists"]
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    summary = base_summary(config, run_root=run_root, status=STATUS_PASS)
    missing = [str(path) for path in raw_file_paths(config) if not path.exists()]
    if missing:
        summary["status"] = STATUS_BLOCKED_RUNTIME_BOUNDARY
        summary["blocker_reasons"] = ["raw_file_missing"]
        summary["blocked_items"] = [
            prereg.blocked_item(path, "raw_file_missing", "expected raw tmp file is missing") for path in missing
        ]
        write_outputs(summary, run_root=run_root)
        return summary
    events = jsonl_objects(config.stream_jsonl_path)
    usage = extract_usage_metadata(events)
    summary.update(
        {
            "usage_metadata_available": usage["usage_metadata_available"],
            "usage_paths": usage["usage_paths"],
            "token_usage": usage["token_usage"],
            "token_usage_total": usage["token_usage_total"],
            "cost_observed_usd": usage["cost_observed_usd"],
            "raw_tmp_sha256s": raw_hashes(raw_file_paths(config)),
        }
    )
    if not config.model_config and usage["model_config"]:
        summary["model_config"] = ",".join(usage["model_config"])
    finalize_summary(summary)
    write_outputs(summary, run_root=run_root)
    return summary


def write_outputs(summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "smoke_id": summary.get("smoke_id"),
        "status": summary.get("status"),
        "run_mode": summary.get("run_mode"),
        "run_scope": summary.get("run_scope"),
        "bounded_batch_executed": summary.get("bounded_batch_executed"),
        "bounded_batch_reason": summary.get("bounded_batch_reason"),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "real_calls_count": summary.get("real_calls_count"),
        "token_usage_total": summary.get("token_usage_total"),
        "usage_metadata_available": summary.get("usage_metadata_available"),
        "cost_observed_usd": summary.get("cost_observed_usd"),
        "raw_tmp_sha256s": summary.get("raw_tmp_sha256s"),
        "repo_raw_artifacts": [],
        "raw_output_boundary": RAW_OUTPUT_BOUNDARY,
        "cognitive_lift_superiority_verdict_status": SUPERIORITY_STATUS,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "created_at_utc": utc_now_iso(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-id", default=default_run_id())
    parser.add_argument("--output-dir", type=Path, default=RAW_ROOT / "summaries")
    parser.add_argument("--stream-jsonl-path", type=Path, required=True)
    parser.add_argument("--last-message-path", type=Path, required=True)
    parser.add_argument("--stderr-path", type=Path)
    parser.add_argument("--command", default="")
    parser.add_argument("--latency-ms", type=int)
    parser.add_argument("--model-config")
    parser.add_argument("--run-mode", choices=("smoke", "synthetic_batch"), default="smoke")
    parser.add_argument("--run-scope", default="minimal_codex_cli_json_smoke")
    parser.add_argument("--cost-cap-usd", type=float, default=COST_CAP_USD)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> SmokeConfig:
    return SmokeConfig(
        smoke_id=str(args.smoke_id),
        output_dir=args.output_dir,
        stream_jsonl_path=args.stream_jsonl_path,
        last_message_path=args.last_message_path,
        stderr_path=args.stderr_path,
        command=str(args.command),
        latency_ms=args.latency_ms,
        model_config=args.model_config,
        run_mode=str(args.run_mode),
        run_scope=str(args.run_scope),
        cost_cap_usd=float(args.cost_cap_usd),
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    summary = build_summary(config_from_args(parse_args(argv)))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
