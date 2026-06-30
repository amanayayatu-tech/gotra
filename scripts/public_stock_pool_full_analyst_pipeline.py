"""Run an independent full-analyst pipeline pilot for public stock symbols.

This one-shot pilot is intentionally separate from the daily public stock-pool
reports. It may call a local Codex CLI runner, but public artifacts never embed
prompt text, completions, messages, raw provider responses, stdout, or stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.public_stock_pool_full_research import (  # noqa: E402
    CodexCliRunner,
    RunnerResult,
    ensure_private_dir,
    parse_model_json,
    sanitize_text,
    scrub_secret_text,
    write_private_json_atomic,
)
from scripts.public_stock_pool_report import (  # noqa: E402
    ExchangeDates,
    fetch_one,
    latest_completed_hk_session,
    latest_completed_us_session,
    trading_date_for_exchange,
    yahoo_ticker,
)
from gotra.judge_agent.audit_chain import (  # noqa: E402
    append_audit_event,
    read_audit_events,
    verify_audit_chain,
)
from gotra.public_api.app import research_universe_items  # noqa: E402


SCHEMA = "gotra.full_analyst.pipeline.v1"
STATUS_SCHEMA = "gotra.full_analyst.status.v1"
SYMBOL_SCHEMA = "gotra.full_analyst.symbol.v1"
PRIVATE_ATTEMPT_SCHEMA = "gotra.full_analyst.private_attempt.v1"
MODE = "full-analyst-evening-hk-test"
LOOP_MODE = "full-analyst-production-loop"
LOOP_SMOKE_MODE = "full-analyst-loop-smoke"
LOOP_MODES = {LOOP_MODE, LOOP_SMOKE_MODE}
REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_RUN_ID = "full_analyst_evening_hk_20260629_v1"
DEFAULT_LOOP_RUN_ID = "full_analyst_10h_loop_20260629_v1"
DEFAULT_OUTPUT_DIR = Path("/opt/gotra/data/reports/full_analyst_test")
DEFAULT_LOOP_OUTPUT_DIR = Path("/opt/gotra/data/reports/full_analyst_loop")
DEFAULT_PRIVATE_AUDIT_ROOT = Path("/opt/gotra/data/private/full_analyst_runs")
DEFAULT_STATIC_DIR = Path("/var/www/gotra-public-ledger/reports")
DEFAULT_SYMBOLS = ("HKEX:0700", "HKEX:1810", "HKEX:9688", "HKEX:9969", "HKEX:0501")
PROMPT_TEMPLATE_VERSION = "gotra.full_analyst.prompt.v1"
BOUNDARY_LINES = (
    "research information only",
    "not investment advice",
    "not trading signal",
    "not performance proof",
    "not science/public proof",
    "no directional recommendation",
    "no price objective",
    "no allocation guidance",
    "no outcome promise",
    "no provider/model I/O is embedded",
)
REQUIRED_SYMBOL_KEYS = (
    "schema",
    "run_id",
    "symbol",
    "exchange",
    "as_of_date",
    "trading_date",
    "price_coverage_status",
    "research_summary",
    "key_updates",
    "positive_case",
    "negative_case",
    "red_team_review",
    "risk_factors",
    "watch_items",
    "source_notes",
    "boundary",
)
LIST_KEYS = {
    "key_updates",
    "positive_case",
    "negative_case",
    "red_team_review",
    "risk_factors",
    "watch_items",
    "source_notes",
    "boundary",
}
FORBIDDEN_PUBLIC_RE = re.compile(
    r"OPENAI_API_KEY|sk-[A-Za-z0-9_-]+|Bearer\s+|Authorization|PRIVATE KEY|"
    r"prompt_text|messages|completion|raw_provider_response|stdout|stderr|"
    r"target price|\b(?:buy|sell|hold)\s+(?:recommendation|rating|signal)\b|position sizing|return promise|"
    r"目标价|买入|卖出|持有建议|仓位|收益承诺",
    re.IGNORECASE,
)
FORBIDDEN_OUTPUT_KEY_RE = re.compile(r"^(prompt_text|prompt|completion|messages|raw_provider_response|stdout|stderr)$", re.I)


@dataclass(frozen=True)
class FullAnalystConfig:
    run_id: str
    mode: str
    output_dir: Path
    private_audit_root: Path
    static_dir: Path
    publish_static: bool
    as_of_date: date
    trading_date: date
    universe_url: str
    symbols: tuple[str, ...]
    llm_runner: str
    alaya_mode: str
    max_concurrency: int
    per_symbol_timeout_seconds: int
    retries: int
    codex_bin: str
    model: str
    reasoning_effort: str
    heartbeat_interval_seconds: int
    loop_duration_seconds: int
    sample_cadence_seconds: int
    loop_current_cycle: int = 1
    loop_last_successful_cycle: int = 0


class AnalystRunner(Protocol):
    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        """Return final model text without persisting provider I/O."""


class AlayaSyncClient(Protocol):
    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a public-safe sync result."""


class ConfigurationBlocker(RuntimeError):
    """Raised for public-safe hard blockers that must stop the run."""


class PublicScanError(RuntimeError):
    """Raised when a public artifact fails the safety scanner."""


class FixtureAnalystRunner:
    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del timeout_seconds
        payload = prompt_input_payload(prompt_text)
        symbol = str(payload["symbol"])
        exchange = str(payload["exchange"])
        response = {
            "schema": SYMBOL_SCHEMA,
            "run_id": payload["run_id"],
            "symbol": symbol,
            "exchange": exchange,
            "as_of_date": payload["as_of_date"],
            "trading_date": payload["trading_date"],
            "price_coverage_status": payload["price_coverage_status"],
            "research_summary": f"Public-safe analyst pilot summary for {exchange}:{symbol}.",
            "key_updates": ["No proprietary or raw provider input is exposed."],
            "positive_case": ["Business quality and market structure should be reviewed with public sources."],
            "negative_case": ["Valuation, competition, and execution risks remain material watch items."],
            "red_team_review": ["Do not infer a trading action from this pilot summary."],
            "risk_factors": ["Data coverage and source freshness need continued monitoring."],
            "watch_items": ["Next public filing or verified market data update."],
            "source_notes": ["Fixture runner; replace with real public-source research before stronger claims."],
            "boundary": list(BOUNDARY_LINES),
        }
        return RunnerResult(True, text=json.dumps(response, ensure_ascii=False), elapsed_seconds=0.001, returncode=0)


class MockAlayaSyncClient:
    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        stable = stable_hash(
            {
                "run_id": payload["run_id"],
                "symbol": payload["symbol"],
                "exchange": payload["exchange"],
                "judge_status": payload["judge_status"],
            }
        )
        return {
            "status": "synced",
            "mode": "mock",
            "event_id": f"mock-alaya-{stable[:16]}",
            "event_hash": stable,
            "readback_status": "not_applicable",
        }


@dataclass(frozen=True)
class GotraInternalAlayaSyncClient:
    state_path: Path
    actor: str

    @classmethod
    def from_config(cls, config: FullAnalystConfig) -> "GotraInternalAlayaSyncClient":
        default_state_path = (
            config.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"
        )
        state_path = Path(os.getenv("GOTRA_FULL_ANALYST_ALAYA_STATE_PATH", str(default_state_path)))
        actor = os.getenv("GOTRA_FULL_ANALYST_ALAYA_ACTOR") or "gotra/full_analyst_pipeline"
        return cls(
            state_path=state_path,
            actor=actor,
        )

    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        public_payload = build_alaya_public_payload(payload)
        source_payload_hash = stable_hash(public_payload)
        event = {
            "event_type": "full_analyst_memory_sync",
            "audit_actor": self.actor,
            "run_id": payload["run_id"],
            "cognition_flywheel_layer": "full_analyst_public_research",
            "feedback_ref": f"full_analyst:{payload['run_id']}:{payload['exchange']}:{payload['symbol']}",
            "knowledge_id": f"full_analyst:{payload['exchange']}:{payload['symbol']}",
            "knowledge_flag": "full_analyst_candidate",
            "symbol": payload["symbol"],
            "exchange": payload["exchange"],
            "judge_status": payload["judge_status"],
            "price_coverage_status": payload["price_coverage_status"],
            "source_payload_hash": source_payload_hash,
            "public_payload": public_payload,
        }
        try:
            written = append_audit_event(self.state_path, event)
        except OSError:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_write_failed",
                "readback_status": "skipped",
            }
        verification = verify_audit_chain(self.state_path)
        if not verification.ok:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_hash_chain_invalid",
                "event_id": str(written.get("event_hash") or ""),
                "event_hash": str(written.get("event_hash") or ""),
                "readback_status": "failed",
            }
        event_hash = str(written.get("event_hash") or "")
        readback = [
            record
            for record in read_audit_events(self.state_path)
            if str(record.get("event_hash") or "") == event_hash
        ]
        if not readback:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_readback_missing",
                "event_id": event_hash,
                "event_hash": event_hash,
                "readback_status": "failed",
            }
        readback_payload_hash = str(readback[0].get("source_payload_hash") or "")
        if readback_payload_hash != source_payload_hash:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_readback_mismatch",
                "event_id": event_hash,
                "event_hash": event_hash,
                "readback_status": "mismatch",
            }
        return {
            "status": "synced",
            "mode": "real",
            "event_id": event_hash,
            "event_hash": event_hash,
            "readback_status": "verified",
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a GOTRA full analyst one-shot pilot.")
    parser.add_argument("--mode", choices=(MODE, LOOP_MODE, LOOP_SMOKE_MODE), required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--private-audit-root", type=Path, default=DEFAULT_PRIVATE_AUDIT_ROOT)
    parser.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR)
    parser.add_argument("--publish-static", action="store_true")
    parser.add_argument("--as-of-date", default=datetime.now(REPORT_TIMEZONE).date().isoformat())
    parser.add_argument("--trading-date", default="")
    parser.add_argument("--universe-url", default="local")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--llm-runner", choices=("codex-cli", "fixture"), default=os.getenv("GOTRA_FULL_ANALYST_LLM_RUNNER", "codex-cli"))
    parser.add_argument("--alaya-mode", choices=("mock", "off", "real"), default="mock")
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--per-symbol-timeout-seconds", type=int, default=int(os.getenv("GOTRA_FULL_ANALYST_TIMEOUT_SECONDS", "300")))
    parser.add_argument("--retries", type=int, default=int(os.getenv("GOTRA_FULL_ANALYST_RETRIES", "0")))
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default=os.getenv("GOTRA_FULL_ANALYST_LLM_MODEL", "gpt-5.5"))
    parser.add_argument("--reasoning-effort", default=os.getenv("GOTRA_FULL_ANALYST_REASONING_EFFORT", "high"))
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=300)
    parser.add_argument("--loop-duration-seconds", type=int, default=36000)
    parser.add_argument("--sample-cadence-seconds", type=int, default=1800)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> FullAnalystConfig:
    as_of_date = date.fromisoformat(str(args.as_of_date))
    trading_date = date.fromisoformat(str(args.trading_date)) if args.trading_date else latest_completed_hk_session(as_of_date)
    is_loop = str(args.mode) in LOOP_MODES
    output_dir = args.output_dir if args.output_dir is not None else (DEFAULT_LOOP_OUTPUT_DIR if is_loop else DEFAULT_OUTPUT_DIR)
    run_id = str(args.run_id or (DEFAULT_LOOP_RUN_ID if is_loop else DEFAULT_RUN_ID))
    return FullAnalystConfig(
        run_id=run_id,
        mode=str(args.mode),
        output_dir=output_dir,
        private_audit_root=args.private_audit_root,
        static_dir=args.static_dir,
        publish_static=bool(args.publish_static),
        as_of_date=as_of_date,
        trading_date=trading_date,
        universe_url=str(args.universe_url),
        symbols=tuple(normalize_symbol_key(value) for value in (args.symbol or list(DEFAULT_SYMBOLS))),
        llm_runner=str(args.llm_runner),
        alaya_mode=str(args.alaya_mode),
        max_concurrency=max(1, int(args.max_concurrency)),
        per_symbol_timeout_seconds=max(30, int(args.per_symbol_timeout_seconds)),
        retries=max(0, int(args.retries)),
        codex_bin=str(args.codex_bin),
        model=str(args.model),
        reasoning_effort=str(args.reasoning_effort),
        heartbeat_interval_seconds=max(60, int(args.heartbeat_interval_seconds)),
        loop_duration_seconds=max(0, int(args.loop_duration_seconds)),
        sample_cadence_seconds=max(60, int(args.sample_cadence_seconds)),
    )


def private_run_dir(config: FullAnalystConfig) -> Path:
    return config.private_audit_root / config.run_id


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_public_universe(config: FullAnalystConfig) -> list[dict[str, str]]:
    if config.universe_url == "local":
        return [
            {
                "symbol": str(item["symbol"]).strip().upper(),
                "exchange": str(item["exchange"]).strip().upper(),
                "provider_ticker": yahoo_ticker(str(item["symbol"]).strip().upper(), str(item["exchange"]).strip().upper()),
                "source": str(item.get("source") or ""),
                "source_date": str(item.get("source_date") or ""),
                "purpose": str(item.get("purpose") or ""),
                "boundary": str(item.get("boundary") or ""),
            }
            for item in research_universe_items()
        ]
    from scripts.public_stock_pool_full_research import load_universe

    return load_universe(config.universe_url)


def selected_universe(universe: list[dict[str, str]], symbols: tuple[str, ...]) -> list[dict[str, str]]:
    by_key = {f"{item['exchange']}:{item['symbol']}": item for item in universe}
    selected: list[dict[str, str]] = []
    missing: list[str] = []
    for key in symbols:
        item = by_key.get(key)
        if item is None:
            missing.append(key)
            continue
        selected.append(item)
    if missing:
        raise RuntimeError(f"requested symbols not in public universe: {','.join(missing)}")
    if len({f'{item["exchange"]}:{item["symbol"]}' for item in selected}) != len(selected):
        raise RuntimeError("duplicate selected symbols")
    return selected


def normalize_symbol_key(value: str) -> str:
    raw = str(value).strip().upper()
    if ":" not in raw:
        if raw.endswith(".HK"):
            return f"HKEX:{raw.removesuffix('.HK')}"
        raise ValueError(f"symbol must be EXCHANGE:SYMBOL: {value}")
    exchange, symbol = raw.split(":", 1)
    exchange = exchange.strip()
    symbol = symbol.strip()
    if exchange not in {"HKEX", "NASDAQ", "NYSE"} or not symbol:
        raise ValueError(f"unsupported symbol key: {value}")
    return f"{exchange}:{symbol}"


def exchange_dates_for_config(config: FullAnalystConfig) -> ExchangeDates:
    us_date = latest_completed_us_session(config.as_of_date)
    return ExchangeDates(
        primary_trading_date=config.trading_date,
        hkex_trading_date=config.trading_date,
        nasdaq_trading_date=us_date,
        nyse_trading_date=us_date,
        reason="full analyst evening HK pilot; HKEX uses latest completed HK session",
    )


def fetch_price_rows(
    items: list[dict[str, str]],
    config: FullAnalystConfig,
    price_rows: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if price_rows is not None:
        return price_rows
    dates = exchange_dates_for_config(config)
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        rows[f"{item['exchange']}:{item['symbol']}"] = fetch_one(item, dates, fetch_retries=2)
    return rows


def build_prompt(item: dict[str, str], price_row: dict[str, Any], config: FullAnalystConfig, *, attempt: int, last_error: str) -> str:
    payload = {
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat(),
        "price_coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "price_context": public_price_context(price_row),
        "required_schema": SYMBOL_SCHEMA,
        "required_keys": list(REQUIRED_SYMBOL_KEYS),
        "boundary": list(BOUNDARY_LINES),
    }
    retry_note = ""
    if attempt > 1:
        retry_note = f"\nRetry attempt {attempt}. Previous failure: {sanitize_text(last_error)[:160]}."
    return (
        "Return STRICT JSON only. No markdown, no code fences, no commentary.\n"
        "Produce a public-safe analyst pilot summary with positive_case, negative_case, and red_team_review.\n"
        "Do not provide investment advice, trading signal, directional recommendation, price objective, "
        "allocation guidance, outcome promise, performance proof, or science/public proof.\n"
        "Avoid the literal phrases buy recommendation, sell recommendation, hold recommendation, "
        "target price, stdout, stderr, completion, messages, and raw_provider_response in all JSON values.\n"
        "Copy the boundary array exactly from the Input JSON.\n"
        "Do not include prompt_text, completion, messages, raw_provider_response, stdout, stderr, "
        "Authorization, Bearer, API keys, or secrets.\n"
        "Use arrays for key_updates, positive_case, negative_case, red_team_review, risk_factors, "
        "watch_items, source_notes, and boundary.\n"
        f"Input JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}{retry_note}"
    )


def prompt_input_payload(prompt_text: str) -> dict[str, Any]:
    marker = "Input JSON:"
    index = prompt_text.find(marker)
    if index < 0:
        raise ValueError("prompt missing Input JSON payload")
    payload = prompt_text[index + len(marker):].strip()
    if "\nRetry attempt" in payload:
        payload = payload.split("\nRetry attempt", 1)[0].strip()
    return json.loads(payload)


def public_price_context(price_row: dict[str, Any]) -> dict[str, Any]:
    if price_row.get("ok"):
        return {
            "status": "ok",
            "close_date": price_row.get("close_date"),
            "one_session_change_pct": price_row.get("one_session_change_pct"),
        }
    return {
        "status": "data_gap",
        "close_date": price_row.get("close_date"),
        "reason": sanitize_text(str(price_row.get("reason") or "unknown")),
    }


def build_alaya_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public_payload = {
        "schema": "gotra.cognition_flywheel.full_analyst_memory.v1",
        "gotra_schema": SYMBOL_SCHEMA,
        "run_id": payload["run_id"],
        "symbol": payload["symbol"],
        "exchange": payload["exchange"],
        "as_of_date": payload["as_of_date"],
        "trading_date": payload["trading_date"],
        "judge_status": payload["judge_status"],
        "price_coverage_status": payload["price_coverage_status"],
        "research_summary": payload["research_summary"],
        "key_updates": payload["key_updates"],
        "positive_case": payload["positive_case"],
        "negative_case": payload["negative_case"],
        "red_team_review": payload["red_team_review"],
        "risk_factors": payload["risk_factors"],
        "watch_items": payload["watch_items"],
        "source_notes": payload["source_notes"],
        "boundary": payload["boundary"],
    }
    assert_public_safe(public_payload)
    return public_payload


def run_symbol(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    alaya_client: AlayaSyncClient,
) -> dict[str, Any]:
    started_at = utc_now_iso()
    started = time.monotonic()
    attempts: list[dict[str, Any]] = []
    last_error = ""
    for attempt in range(1, config.retries + 2):
        prompt = build_prompt(item, price_row, config, attempt=attempt, last_error=last_error)
        prompt_hash = stable_hash({"prompt": prompt})
        attempt_record = {
            "schema": PRIVATE_ATTEMPT_SCHEMA,
            "run_id": config.run_id,
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "attempt": attempt,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            "prompt_hash": prompt_hash,
            "prompt_text": scrub_secret_text(prompt),
            "model": config.model,
            "reasoning_effort": config.reasoning_effort,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "status": "failed",
            "failure_reason": "",
        }
        result = runner.complete(prompt, timeout_seconds=config.per_symbol_timeout_seconds)
        attempt_record["stdout_bytes"] = result.stdout_bytes
        attempt_record["stderr_bytes"] = result.stderr_bytes
        attempt_record["returncode"] = result.returncode
        if not result.ok:
            last_error = result.reason or "runner_failed"
            attempt_record["failure_reason"] = last_error
            attempts.append(public_attempt(attempt, last_error))
            write_private_attempt(config, item, attempt_record)
            continue
        try:
            symbol_payload = sanitize_symbol_payload(
                parse_model_json(result.text),
                item=item,
                price_row=price_row,
                config=config,
            )
            judge_status, judge_reasons = judge_symbol(symbol_payload)
            symbol_payload["judge_status"] = judge_status
            symbol_payload["judge_reasons"] = judge_reasons
            alaya_result = alaya_sync(symbol_payload, alaya_client, config)
            symbol_payload["alaya_sync_status"] = alaya_result["status"]
            symbol_payload["alaya_sync_ref"] = alaya_result.get("event_id", "")
            symbol_payload["alaya_event_hash"] = alaya_result.get("event_hash", "")
            symbol_payload["alaya_readback_status"] = alaya_result.get("readback_status", "not_applicable")
            symbol_payload["alaya_failure_reason"] = alaya_result.get("reason", "")
            attempt_record["status"] = "success"
            attempt_record["parsed_structured_output"] = symbol_payload
            write_private_attempt(config, item, attempt_record)
            return {
                "status": "success",
                "symbol": item["symbol"],
                "exchange": item["exchange"],
                "provider_ticker": item["provider_ticker"],
                "price_coverage_status": symbol_payload["price_coverage_status"],
                "judge_status": judge_status,
                "judge_reasons": judge_reasons,
                "alaya_sync_status": alaya_result["status"],
                "alaya_sync_ref": alaya_result.get("event_id", ""),
                "alaya_event_hash": alaya_result.get("event_hash", ""),
                "alaya_readback_status": alaya_result.get("readback_status", "not_applicable"),
                "alaya_failure_reason": alaya_result.get("reason", ""),
                "attempts": attempt,
                "attempt_metrics": attempts,
                "started_at_utc": started_at,
                "finished_at_utc": utc_now_iso(),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "research": symbol_payload,
            }
        except Exception as exc:  # noqa: BLE001 - keep per-symbol failure visible.
            last_error = normalize_failure_reason(exc)
            attempt_record["failure_reason"] = last_error
            attempts.append(public_attempt(attempt, last_error))
            write_private_attempt(config, item, attempt_record)
    return {
        "status": "failed",
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "price_coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "judge_status": "blocked",
        "judge_reasons": [last_error or "unknown_failure"],
        "alaya_sync_status": "skipped",
        "alaya_sync_ref": "",
        "alaya_event_hash": "",
        "alaya_readback_status": "skipped",
        "alaya_failure_reason": "",
        "attempts": len(attempts),
        "attempt_metrics": attempts,
        "started_at_utc": started_at,
        "finished_at_utc": utc_now_iso(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "research": None,
        "failure_reason": last_error or "unknown_failure",
    }


def public_attempt(attempt: int, reason: str) -> dict[str, Any]:
    return {"attempt": attempt, "failure_reason": sanitize_text(reason)[:240]}


def normalize_failure_reason(exc: Exception) -> str:
    text = str(exc)
    if text.startswith("missing_required_fields"):
        return "missing_required_fields"
    if text.startswith("forbidden_raw_io_keys"):
        return "forbidden_raw_io_keys_detected"
    if text.startswith("forbidden_public_content_detected"):
        return "forbidden_public_content_detected"
    return f"{type(exc).__name__}: {text[:180]}"


def write_private_attempt(config: FullAnalystConfig, item: dict[str, str], payload: dict[str, Any]) -> None:
    path = private_run_dir(config) / "attempts" / f"{item['exchange']}_{item['symbol']}_attempt_{payload['attempt']}.json"
    write_private_json_atomic(path, payload)


def sanitize_symbol_payload(
    payload: dict[str, Any],
    *,
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
) -> dict[str, Any]:
    forbidden_keys = [key for key in payload if FORBIDDEN_OUTPUT_KEY_RE.match(str(key))]
    if forbidden_keys:
        raise ValueError(f"forbidden_raw_io_keys: {','.join(sorted(forbidden_keys))}")
    missing = [key for key in REQUIRED_SYMBOL_KEYS if key not in payload]
    if missing:
        raise ValueError(f"missing_required_fields: {','.join(missing)}")
    sanitized: dict[str, Any] = {}
    for key in REQUIRED_SYMBOL_KEYS:
        value = payload.get(key)
        if key in LIST_KEYS:
            sanitized[key] = sanitize_list(value)
        else:
            sanitized[key] = sanitize_text(str(value or ""))
    sanitized["schema"] = SYMBOL_SCHEMA
    sanitized["run_id"] = config.run_id
    sanitized["symbol"] = item["symbol"]
    sanitized["exchange"] = item["exchange"]
    sanitized["as_of_date"] = config.as_of_date.isoformat()
    sanitized["trading_date"] = trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat()
    sanitized["price_coverage_status"] = "ok" if price_row.get("ok") else "data_gap"
    sanitized["price_context"] = public_price_context(price_row)
    sanitized["boundary"] = list(BOUNDARY_LINES)
    assert_public_safe(sanitized)
    return sanitized


def sanitize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [sanitize_text(str(item))[:500] for item in value if str(item).strip()][:12]
    if value in (None, ""):
        return []
    return [sanitize_text(str(value))[:500]]


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    scan_text = normalize_negated_boundary_text(text)
    match = FORBIDDEN_PUBLIC_RE.search(scan_text)
    if match:
        token = re.sub(r"[^a-z0-9_ -]+", "", match.group(0).lower()).strip().replace(" ", "_")
        raise ValueError(f"forbidden_public_content_detected:{token[:80] or 'unknown'}")


def normalize_negated_boundary_text(text: str) -> str:
    """Keep public scans strict while avoiding blocks on explicit no-advice disclaimers."""

    replacements = (
        (
            re.compile(
                r"\b(?:not\s+(?:a|an)\s+|no\s+)(?:buy|sell|hold)\s+"
                r"(?:recommendation|rating|signal)\b",
                re.IGNORECASE,
            ),
            "no_directional_action",
        ),
        (
            re.compile(r"\b(?:not\s+(?:a|an)\s+|no\s+)target\s+price\b", re.IGNORECASE),
            "no_price_objective",
        ),
    )
    normalized = text
    for pattern, replacement in replacements:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def judge_symbol(symbol_payload: dict[str, Any]) -> tuple[str, list[str]]:
    if symbol_payload["price_coverage_status"] == "data_gap":
        return "needs_review", ["price coverage is data_gap; do not promote to publish"]
    assert_public_safe(symbol_payload)
    required_lists = ("positive_case", "negative_case", "red_team_review", "risk_factors", "watch_items", "source_notes")
    empty = [key for key in required_lists if not symbol_payload.get(key)]
    if empty:
        return "blocked", [f"empty required analyst sections: {','.join(empty)}"]
    return "publish", ["public-safe structured analyst summary passed local judge gate"]


def alaya_sync(symbol_payload: dict[str, Any], alaya_client: AlayaSyncClient, config: FullAnalystConfig) -> dict[str, Any]:
    if symbol_payload["judge_status"] != "publish":
        return {"status": "skipped", "reason": "judge_status_not_publish", "readback_status": "skipped"}
    if config.alaya_mode == "off":
        return {"status": "skipped", "reason": "alaya_mode_off", "readback_status": "skipped"}
    result = alaya_client.sync(symbol_payload)
    if result.get("status") != "synced":
        return {
            "status": "failed",
            "reason": public_safe_failure_category(str(result.get("reason") or "unknown")),
            "event_id": sanitize_text(str(result.get("event_id") or ""))[:160],
            "event_hash": sanitize_text(str(result.get("event_hash") or ""))[:160],
            "readback_status": sanitize_text(str(result.get("readback_status") or "failed"))[:80],
        }
    write_private_json_atomic(
        private_run_dir(config) / "alaya_events" / f"{symbol_payload['exchange']}_{symbol_payload['symbol']}.json",
        sanitize_private_metadata(result),
    )
    return result


def run_jobs(
    items: list[dict[str, str]],
    price_rows: dict[str, dict[str, Any]],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    alaya_client: AlayaSyncClient,
    *,
    started_at_utc: str,
) -> list[dict[str, Any]]:
    sample_symbols = tuple(f"{item['exchange']}:{item['symbol']}" for item in items)
    if config.max_concurrency == 1:
        results = []
        for item in items:
            refresh_loop_runtime_heartbeat(
                config,
                phase="llm",
                started_at_utc=started_at_utc,
                sample_symbols=sample_symbols,
            )
            results.append(
                run_symbol(
                    item,
                    price_rows[f"{item['exchange']}:{item['symbol']}"],
                    config,
                    runner,
                    alaya_client,
                )
            )
        return results
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=config.max_concurrency) as executor:
        refresh_loop_runtime_heartbeat(
            config,
            phase="llm",
            started_at_utc=started_at_utc,
            sample_symbols=sample_symbols,
        )
        futures = {
            executor.submit(run_symbol, item, price_rows[f"{item['exchange']}:{item['symbol']}"], config, runner, alaya_client): item
            for item in items
        }
        for future in as_completed(futures):
            refresh_loop_runtime_heartbeat(
                config,
                phase="llm",
                started_at_utc=started_at_utc,
                sample_symbols=sample_symbols,
            )
            results.append(future.result())
    return sorted(results, key=lambda row: (str(row["exchange"]), str(row["symbol"])))


def build_status(
    *,
    config: FullAnalystConfig,
    results: list[dict[str, Any]],
    started_at_utc: str,
    elapsed_seconds: float,
    report_path: Path,
    status_path: Path,
) -> dict[str, Any]:
    failed = [row for row in results if row["status"] != "success"]
    blocked = [row for row in results if row["judge_status"] == "blocked"]
    needs_review = [row for row in results if row["judge_status"] == "needs_review"]
    publish = [row for row in results if row["judge_status"] == "publish"]
    alaya_failed = [row for row in results if row["alaya_sync_status"] == "failed"]
    alaya_readback_failed = [
        row for row in results if row.get("alaya_readback_status") in {"failed", "mismatch"}
    ]
    alaya_verified = [row for row in results if row.get("alaya_readback_status") == "verified"]
    run_status = "completed"
    if failed or blocked or alaya_failed or alaya_readback_failed:
        run_status = "completed_with_blockers"
    elif needs_review:
        run_status = "completed_with_review_items"
    exit_status = 0 if not failed and not blocked and not alaya_failed and not alaya_readback_failed else 2
    alaya_sync_status = "ok"
    if config.alaya_mode == "off":
        alaya_sync_status = "skipped"
    elif alaya_failed:
        alaya_sync_status = "failed"
    elif not publish:
        alaya_sync_status = "skipped"
    alaya_readback_status = "not_applicable"
    if config.alaya_mode == "real":
        if alaya_readback_failed:
            alaya_readback_status = "failed"
        elif alaya_verified:
            alaya_readback_status = "verified"
        elif publish:
            alaya_readback_status = "missing"
    last_error_category = first_error_category(failed, blocked, alaya_failed, alaya_readback_failed)
    current_cycle = max(1, config.loop_current_cycle)
    last_successful_cycle = current_cycle if exit_status == 0 else config.loop_last_successful_cycle
    status = {
        "schema": STATUS_SCHEMA,
        "ok": exit_status == 0,
        "run_status": run_status,
        "mode": config.mode,
        "run_id": config.run_id,
        "status": "completed" if exit_status == 0 else "failed",
        "phase": "artifact",
        "current_cycle": current_cycle,
        "last_successful_cycle": last_successful_cycle,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "sample_symbols": list(config.symbols),
        "universe_count": len(results),
        "success_count": sum(1 for row in results if row["status"] == "success"),
        "failed_count": len(failed),
        "publish_count": len(publish),
        "needs_review_count": len(needs_review),
        "blocked_count": len(blocked),
        "data_gap_count": sum(1 for row in results if row["price_coverage_status"] == "data_gap"),
        "alaya_synced_count": sum(1 for row in results if row["alaya_sync_status"] == "synced"),
        "alaya_failed_count": len(alaya_failed),
        "alaya_readback_verified_count": len(alaya_verified),
        "alaya_readback_failed_count": len(alaya_readback_failed),
        "alaya_sync_status": alaya_sync_status,
        "alaya_readback_status": alaya_readback_status,
        "failed_symbols": failure_rows(failed),
        "blocked_symbols": failure_rows(blocked),
        "needs_review_symbols": failure_rows(needs_review),
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "last_heartbeat_utc": utc_now_iso(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "remaining_seconds": 0,
        "consecutive_failures": 1 if exit_status else 0,
        "llm_runner": config.llm_runner,
        "llm_model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "alaya_mode": config.alaya_mode,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "latest_public_report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "ok",
        "artifact_write_failure_reason": None,
        "public_scan_status": "ok",
        "last_error_category": last_error_category,
        "last_error_public_message": public_error_message(last_error_category),
        "heartbeat_stale": False,
        "provider_model_io_embedded": False,
        "evidence_layer": evidence_layer_for_mode(config.mode),
        "limitations": [
            "not 10h evidence" if config.mode == LOOP_SMOKE_MODE else "not formal acceptance",
            "not science/public proof",
            "not performance proof",
            "not a trading signal",
            "not investment advice",
        ],
    }
    status["exit_status"] = exit_status
    return status


def failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "exchange": row["exchange"],
            "symbol": row["symbol"],
            "provider_ticker": row["provider_ticker"],
            "judge_status": row["judge_status"],
            "reason": "; ".join(row.get("judge_reasons") or [row.get("failure_reason", "")]),
        }
        for row in rows
    ]


def first_error_category(*groups: list[dict[str, Any]]) -> str | None:
    for rows in groups:
        for row in rows:
            if row.get("alaya_sync_status") == "failed":
                return public_safe_failure_category(
                    str(row.get("alaya_failure_reason") or row.get("alaya_readback_status") or "alaya_sync_failed")
                )
            reasons = row.get("judge_reasons") or [row.get("failure_reason") or row.get("alaya_sync_status")]
            if reasons:
                return public_safe_failure_category(str(reasons[0]))
    return None


def public_error_message(category: str | None) -> str | None:
    if not category:
        return None
    return f"Public-safe blocker category: {category}"


def public_safe_failure_category(reason: str) -> str:
    text = sanitize_text(str(reason or "unknown")).lower()
    if "readback_mismatch" in text or "mismatch" in text:
        return "alaya_readback_mismatch"
    if "readback" in text:
        return "alaya_readback_failed"
    if "gotra_internal_state" in text:
        return "gotra_internal_state_sync_failed"
    if "alaya" in text and ("http" in text or "write" in text or "sync" in text):
        return "alaya_sync_failed"
    if "missing_required_fields" in text:
        return "missing_required_fields"
    if "forbidden_raw_io_keys" in text:
        return "forbidden_raw_io_keys_detected"
    if "forbidden_public_content_detected" in text:
        return "forbidden_public_content_detected"
    if "artifact" in text or "permission" in text:
        return "artifact_write_failed"
    return re.sub(r"[^a-z0-9_]+", "_", text)[:80].strip("_") or "unknown_failure"


def evidence_layer_for_mode(mode: str) -> str:
    if mode == LOOP_SMOKE_MODE:
        return "local checks + short loop smoke + public-safe artifact smoke"
    if mode == LOOP_MODE:
        return "local checks + server runtime loop evidence + public-safe artifact smoke"
    return "local checks + one-shot runtime smoke + public-safe artifact smoke"


def report_paths(config: FullAnalystConfig) -> tuple[Path, Path]:
    if config.mode in LOOP_MODES:
        return config.output_dir / "full_analyst_loop_latest.md", config.output_dir / "status_full_analyst_loop.json"
    report_path = config.output_dir / f"full_analyst_evening_hk_{config.as_of_date.isoformat()}.md"
    status_path = config.output_dir / "status_full_analyst_evening_hk.json"
    return report_path, status_path


def write_outputs(config: FullAnalystConfig, results: list[dict[str, Any]], status: dict[str, Any]) -> dict[str, str]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "symbols").mkdir(parents=True, exist_ok=True)
    report_path, status_path = report_paths(config)
    symbol_payloads = [row["research"] for row in results if row.get("research")]
    scan_public_artifacts(status=status, results=results, symbol_payloads=symbol_payloads)
    for row in results:
        if row.get("research"):
            write_public_json(config.output_dir / "symbols" / f"{row['exchange']}_{row['symbol']}.json", row["research"])
    markdown = render_markdown(status, results)
    scan_public_text(markdown)
    write_public_text(report_path, markdown)
    write_public_json(status_path, status)
    if config.publish_static:
        publish_static(report_path, status_path, config.static_dir)
    return {"report_path": str(report_path.resolve()), "status_path": str(status_path.resolve())}


def write_public_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    path.chmod(0o644)


def write_public_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    scan_public_text(text)
    write_public_text(path, text)


def scan_public_artifacts(*, status: dict[str, Any], results: list[dict[str, Any]], symbol_payloads: list[dict[str, Any]]) -> None:
    del results
    scan_public_text(json.dumps(status, ensure_ascii=False, sort_keys=True))
    for payload in symbol_payloads:
        scan_public_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def scan_public_text(text: str) -> None:
    try:
        assert_public_safe(text)
    except Exception as exc:  # noqa: BLE001 - collapse scanner details to a public-safe category.
        raise PublicScanError(public_safe_failure_category(str(exc))) from exc


def publish_static(report_path: Path, status_path: Path, static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    for path in (report_path, status_path):
        target = static_dir / path.name
        shutil.copy2(path, target)
        target.chmod(0o644)


def render_markdown(status: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        f"# GOTRA Full Analyst Pipeline - {status['as_of_date']}",
        "",
        "## Evidence Layer",
        "",
        f"- {status['evidence_layer']}",
        "- not formal acceptance",
        "- not science/public proof",
        "- not performance proof",
        "- not a trading signal",
        "- not investment advice",
        "",
        "## Status",
        "",
        f"- mode: {status['mode']}",
        f"- run_id: {status['run_id']}",
        f"- run_status: {status['run_status']}",
        f"- phase: {status['phase']}",
        f"- last_heartbeat_utc: {status['last_heartbeat_utc']}",
        f"- trading_date: {status['trading_date']}",
        f"- universe_count: {status['universe_count']}",
        f"- publish_count: {status['publish_count']}",
        f"- needs_review_count: {status['needs_review_count']}",
        f"- blocked_count: {status['blocked_count']}",
        f"- failed_count: {status['failed_count']}",
        f"- alaya_synced_count: {status['alaya_synced_count']}",
        f"- alaya_failed_count: {status['alaya_failed_count']}",
        f"- alaya_readback_verified_count: {status['alaya_readback_verified_count']}",
        f"- alaya_readback_failed_count: {status['alaya_readback_failed_count']}",
        f"- alaya_mode: {status['alaya_mode']}",
        f"- alaya_sync_status: {status['alaya_sync_status']}",
        f"- alaya_readback_status: {status['alaya_readback_status']}",
        f"- public_scan_status: {status['public_scan_status']}",
        "",
        "## Boundary",
        "",
        *[f"- {line}" for line in BOUNDARY_LINES],
        "",
        "## Symbol Results",
        "",
    ]
    for row in results:
        research = row.get("research") or {}
        lines.extend(
            [
                f"### {row['exchange']}:{row['symbol']}",
                "",
                f"- price_coverage_status: {row['price_coverage_status']}",
                f"- judge_status: {row['judge_status']}",
                f"- alaya_sync_status: {row['alaya_sync_status']}",
                f"- alaya_readback_status: {row.get('alaya_readback_status', 'not_applicable')}",
                f"- judge_reasons: {'; '.join(row.get('judge_reasons') or [])}",
            ]
        )
        if row["judge_status"] == "blocked" or not research:
            lines.extend(["- public_summary: blocked from public publish summary", ""])
            continue
        lines.extend(
            [
                f"- research_summary: {research['research_summary']}",
                "- key_updates:",
                *[f"  - {item}" for item in research["key_updates"]],
                "- positive_case:",
                *[f"  - {item}" for item in research["positive_case"]],
                "- negative_case:",
                *[f"  - {item}" for item in research["negative_case"]],
                "- red_team_review:",
                *[f"  - {item}" for item in research["red_team_review"]],
                "- risk_factors:",
                *[f"  - {item}" for item in research["risk_factors"]],
                "- watch_items:",
                *[f"  - {item}" for item in research["watch_items"]],
                "- source_notes:",
                *[f"  - {item}" for item in research["source_notes"]],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_private_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    allowed = {
        "status",
        "mode",
        "event_id",
        "event_hash",
        "readback_status",
        "reason",
        "schema",
        "project_id",
        "actor",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = sanitize_text(str(value))[:500] if isinstance(value, str) else value
    return sanitized


def runner_from_config(config: FullAnalystConfig) -> AnalystRunner:
    if config.llm_runner == "fixture":
        return FixtureAnalystRunner()
    return CodexCliRunner(
        codex_bin=config.codex_bin,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        cwd=REPO_ROOT,
    )


def alaya_client_from_config(config: FullAnalystConfig) -> AlayaSyncClient:
    if config.alaya_mode == "real":
        return GotraInternalAlayaSyncClient.from_config(config)
    return MockAlayaSyncClient()


def preflight_llm_config(config: FullAnalystConfig, runner: AnalystRunner | None) -> None:
    if config.llm_runner != "codex-cli" or runner is not None:
        return
    if config.model != "gpt-5.5":
        raise ConfigurationBlocker("codex_model_must_be_gpt_5_5")


def write_heartbeat(config: FullAnalystConfig, *, status: str, phase: str, current_cycle: int, last_successful_cycle: int, started_at_utc: str, last_error_category: str | None = None) -> None:
    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    elapsed = max(0, int((datetime.now(UTC) - started).total_seconds()))
    remaining = max(0, int(config.loop_duration_seconds - elapsed)) if config.mode in LOOP_MODES else 0
    payload = {
        "run_id": config.run_id,
        "status": status,
        "phase": phase,
        "current_cycle": current_cycle,
        "last_heartbeat_utc": utc_now_iso(),
        "last_successful_cycle": last_successful_cycle,
        "last_error_category": last_error_category,
        "consecutive_failures": 1 if last_error_category else 0,
        "elapsed_seconds": elapsed,
        "remaining_seconds": remaining,
    }
    write_private_json_atomic(private_run_dir(config) / "heartbeat.json", payload)


def append_event(config: FullAnalystConfig, event_type: str, payload: dict[str, Any]) -> None:
    event = {
        "run_id": config.run_id,
        "event_type": event_type,
        "created_at_utc": utc_now_iso(),
        "payload": sanitize_private_metadata(payload),
    }
    path = private_run_dir(config) / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_failure_records(config: FullAnalystConfig, results: list[dict[str, Any]], status: dict[str, Any]) -> None:
    failures = []
    for row in results:
        if row["status"] == "success" and row["judge_status"] != "blocked" and row["alaya_sync_status"] != "failed":
            continue
        failures.append(
            {
                "run_id": config.run_id,
                "created_at_utc": utc_now_iso(),
                "exchange": row["exchange"],
                "symbol": row["symbol"],
                "category": public_safe_failure_category(";".join(row.get("judge_reasons") or [row.get("failure_reason", "")])),
                "stage": row["judge_status"],
            }
        )
    path = private_run_dir(config) / "failures.jsonl"
    if failures:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for failure in failures:
                handle.write(json.dumps(failure, ensure_ascii=False, sort_keys=True) + "\n")
    cycle_index = max(1, config.loop_current_cycle)
    write_private_json_atomic(
        private_run_dir(config) / f"cycle_{cycle_index:03d}_summary.json",
        sanitize_private_metadata(status)
        | {
            "run_id": config.run_id,
            "cycle_id": f"cycle_{cycle_index:03d}",
            "current_cycle": status["current_cycle"],
            "last_successful_cycle": status["last_successful_cycle"],
            "sample_symbols": list(config.symbols),
            "publish_count": status["publish_count"],
            "needs_review_count": status["needs_review_count"],
            "blocked_count": status["blocked_count"],
            "data_gap_count": status["data_gap_count"],
            "alaya_synced_count": status["alaya_synced_count"],
            "alaya_readback_verified_count": status["alaya_readback_verified_count"],
            "artifact_write_status": status["artifact_write_status"],
            "public_scan_status": status["public_scan_status"],
            "exit_status": status["exit_status"],
            "duration_seconds": status["elapsed_seconds"],
        },
    )


def write_blocker_status(config: FullAnalystConfig, *, started_at_utc: str, reason: str, report_path: Path, status_path: Path) -> int:
    category = public_safe_failure_category(reason)
    failed = {
        "schema": STATUS_SCHEMA,
        "ok": False,
        "run_status": "blocked",
        "status": "failed",
        "mode": config.mode,
        "run_id": config.run_id,
        "phase": "preflight",
        "current_cycle": 0,
        "last_successful_cycle": 0,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "sample_symbols": list(config.symbols),
        "universe_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "publish_count": 0,
        "needs_review_count": 0,
        "blocked_count": 1,
        "data_gap_count": 0,
        "alaya_synced_count": 0,
        "alaya_failed_count": 0,
        "alaya_readback_verified_count": 0,
        "alaya_readback_failed_count": 0,
        "alaya_sync_status": "blocked" if config.alaya_mode == "real" else "skipped",
        "alaya_readback_status": "blocked" if config.alaya_mode == "real" else "skipped",
        "failed_symbols": [],
        "blocked_symbols": [{"exchange": "RUN", "symbol": "PREFLIGHT", "provider_ticker": "PREFLIGHT", "judge_status": "blocked", "reason": category}],
        "needs_review_symbols": [],
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "last_heartbeat_utc": utc_now_iso(),
        "elapsed_seconds": 0,
        "remaining_seconds": 0,
        "consecutive_failures": 1,
        "llm_runner": config.llm_runner,
        "llm_model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "alaya_mode": config.alaya_mode,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "latest_public_report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "ok",
        "artifact_write_failure_reason": None,
        "public_scan_status": "ok",
        "last_error_category": category,
        "last_error_public_message": public_error_message(category),
        "heartbeat_stale": False,
        "provider_model_io_embedded": False,
        "evidence_layer": evidence_layer_for_mode(config.mode),
        "limitations": ["not 10h evidence", "not formal acceptance", "not science/public proof", "not performance proof", "not a trading signal", "not investment advice"],
        "exit_status": 2,
    }
    write_heartbeat(config, status="failed", phase="preflight", current_cycle=0, last_successful_cycle=0, started_at_utc=started_at_utc, last_error_category=category)
    append_event(config, "blocker", {"status": "failed", "reason": category})
    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_public_text(report_path, render_blocker_markdown(failed))
    write_public_json(status_path, failed)
    if config.publish_static:
        publish_static(report_path, status_path, config.static_dir)
    print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
    return 2


def render_blocker_markdown(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# GOTRA Full Analyst Pipeline - {status['as_of_date']}",
            "",
            "## Status",
            "",
            f"- run_status: {status['run_status']}",
            f"- last_error_category: {status['last_error_category']}",
            "",
            "## Evidence Layer",
            "",
            f"- {status['evidence_layer']}",
            "- not 10h evidence",
            "- not formal acceptance",
            "- not science/public proof",
            "- not performance proof",
            "- not a trading signal",
            "- not investment advice",
        ]
    ) + "\n"


def sample_symbols_for_cycle(symbols: tuple[str, ...], successful_cycles: int) -> tuple[str, ...]:
    sample_size = 3
    if successful_cycles >= 4:
        sample_size = 10
    elif successful_cycles >= 2:
        sample_size = 5
    return tuple(symbols[: min(sample_size, len(symbols))])


def build_loop_running_status(
    config: FullAnalystConfig,
    *,
    current_cycle: int,
    last_successful_cycle: int,
    loop_status: str,
    phase: str,
    started_at_utc: str,
    sample_symbols: tuple[str, ...],
    last_error_category: str | None = None,
) -> dict[str, Any]:
    report_path, status_path = report_paths(config)
    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    elapsed = max(0, int((datetime.now(UTC) - started).total_seconds()))
    return {
        "schema": STATUS_SCHEMA,
        "ok": True,
        "run_status": "running" if loop_status == "running" else loop_status,
        "mode": config.mode,
        "run_id": config.run_id,
        "status": loop_status,
        "phase": phase,
        "current_cycle": current_cycle,
        "last_successful_cycle": last_successful_cycle,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "sample_symbols": list(sample_symbols),
        "universe_count": len(sample_symbols),
        "success_count": 0,
        "failed_count": 0,
        "publish_count": 0,
        "needs_review_count": 0,
        "blocked_count": 0,
        "data_gap_count": 0,
        "alaya_synced_count": 0,
        "alaya_failed_count": 0,
        "alaya_readback_verified_count": 0,
        "alaya_readback_failed_count": 0,
        "alaya_sync_status": "pending" if config.alaya_mode == "real" else "skipped",
        "alaya_readback_status": "pending" if config.alaya_mode == "real" else "not_applicable",
        "failed_symbols": [],
        "blocked_symbols": [],
        "needs_review_symbols": [],
        "started_at_utc": started_at_utc,
        "finished_at_utc": None,
        "last_heartbeat_utc": utc_now_iso(),
        "elapsed_seconds": elapsed,
        "remaining_seconds": max(0, int(config.loop_duration_seconds - elapsed)),
        "consecutive_failures": 1 if last_error_category else 0,
        "llm_runner": config.llm_runner,
        "llm_model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "alaya_mode": config.alaya_mode,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "latest_public_report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "pending",
        "artifact_write_failure_reason": None,
        "public_scan_status": "pending",
        "last_error_category": last_error_category,
        "last_error_public_message": public_error_message(last_error_category),
        "heartbeat_stale": False,
        "provider_model_io_embedded": False,
        "evidence_layer": evidence_layer_for_mode(config.mode),
        "limitations": [
            "not formal acceptance",
            "not science/public proof",
            "not performance proof",
            "not a trading signal",
            "not investment advice",
        ],
        "exit_status": None,
    }


def render_loop_running_markdown(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# GOTRA Full Analyst Pipeline - {status['as_of_date']}",
            "",
            "## Evidence Layer",
            "",
            f"- {status['evidence_layer']}",
            "- not formal acceptance",
            "- not science/public proof",
            "- not performance proof",
            "- not a trading signal",
            "- not investment advice",
            "",
            "## Status",
            "",
            f"- mode: {status['mode']}",
            f"- run_id: {status['run_id']}",
            f"- status: {status['status']}",
            f"- phase: {status['phase']}",
            f"- last_heartbeat_utc: {status['last_heartbeat_utc']}",
            f"- current_cycle: {status['current_cycle']}",
            f"- last_successful_cycle: {status['last_successful_cycle']}",
            f"- alaya_mode: {status['alaya_mode']}",
            f"- alaya_sync_status: {status['alaya_sync_status']}",
            f"- alaya_readback_status: {status['alaya_readback_status']}",
        ]
    ) + "\n"


def sync_loop_markdown_status(report_path: Path, status: dict[str, Any]) -> None:
    if not report_path.exists():
        return
    markdown = report_path.read_text(encoding="utf-8")
    replacements = {
        "status": status.get("status"),
        "run_status": status.get("run_status"),
        "phase": status.get("phase"),
        "last_heartbeat_utc": status.get("last_heartbeat_utc"),
        "current_cycle": status.get("current_cycle"),
        "last_successful_cycle": status.get("last_successful_cycle"),
    }
    for key, value in replacements.items():
        if value is None:
            continue
        line = f"- {key}: {value}"
        pattern = re.compile(rf"^- {re.escape(key)}: .*$", re.MULTILINE)
        if pattern.search(markdown):
            markdown = pattern.sub(line, markdown, count=1)
        elif key == "status":
            markdown = re.sub(r"(^## Status\n\n)", rf"\1{line}\n", markdown, count=1, flags=re.MULTILINE)
    scan_public_text(markdown)
    write_public_text(report_path, markdown)


def update_loop_public_status(
    config: FullAnalystConfig,
    *,
    current_cycle: int,
    last_successful_cycle: int,
    loop_status: str,
    phase: str,
    started_at_utc: str,
    sample_symbols: tuple[str, ...] | None = None,
    last_error_category: str | None = None,
) -> None:
    report_path, status_path = report_paths(config)
    status: dict[str, Any] | None = None
    should_bootstrap = not status_path.exists()
    if not should_bootstrap:
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        should_bootstrap = status.get("run_id") != config.run_id or status.get("mode") != config.mode
    if should_bootstrap:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        status = build_loop_running_status(
            config,
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            loop_status=loop_status,
            phase=phase,
            started_at_utc=started_at_utc,
            sample_symbols=sample_symbols or (),
            last_error_category=last_error_category,
        )
        markdown = render_loop_running_markdown(status)
        scan_public_text(markdown)
        write_public_text(report_path, markdown)
    if status is None:
        return
    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    elapsed = max(0, int((datetime.now(UTC) - started).total_seconds()))
    status["status"] = loop_status
    status["run_status"] = "running" if loop_status == "running" else loop_status
    status["phase"] = phase
    status["current_cycle"] = current_cycle
    status["last_successful_cycle"] = last_successful_cycle
    if sample_symbols is not None:
        status["sample_symbols"] = list(sample_symbols)
        status["universe_count"] = len(sample_symbols)
    status["last_heartbeat_utc"] = utc_now_iso()
    status["elapsed_seconds"] = elapsed
    status["remaining_seconds"] = max(0, int(config.loop_duration_seconds - elapsed))
    status["heartbeat_stale"] = False
    if last_error_category:
        status["last_error_category"] = last_error_category
        status["last_error_public_message"] = public_error_message(last_error_category)
    if loop_status != "running":
        sync_loop_markdown_status(report_path, status)
    write_public_json(status_path, status)
    if config.publish_static:
        publish_static(report_path, status_path, config.static_dir)


def refresh_loop_runtime_heartbeat(
    config: FullAnalystConfig,
    *,
    phase: str,
    started_at_utc: str,
    sample_symbols: tuple[str, ...] | None = None,
) -> None:
    write_heartbeat(
        config,
        status="running",
        phase=phase,
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=started_at_utc,
    )
    if config.mode in LOOP_MODES:
        update_loop_public_status(
            config,
            current_cycle=config.loop_current_cycle,
            last_successful_cycle=config.loop_last_successful_cycle,
            loop_status="running",
            phase=phase,
            started_at_utc=started_at_utc,
            sample_symbols=sample_symbols,
        )


def run_loop(config: FullAnalystConfig) -> int:
    loop_started = time.monotonic()
    loop_started_at_utc = utc_now_iso()
    current_cycle = 0
    last_successful_cycle = 0
    last_exit = 0
    write_heartbeat(
        config,
        status="running",
        phase="preflight",
        current_cycle=0,
        last_successful_cycle=0,
        started_at_utc=loop_started_at_utc,
    )
    update_loop_public_status(
        config,
        current_cycle=0,
        last_successful_cycle=0,
        loop_status="running",
        phase="preflight",
        started_at_utc=loop_started_at_utc,
        sample_symbols=(),
    )
    while time.monotonic() - loop_started < config.loop_duration_seconds:
        current_cycle += 1
        cycle_symbols = sample_symbols_for_cycle(config.symbols, last_successful_cycle)
        cycle_config = replace(
            config,
            symbols=cycle_symbols,
            loop_current_cycle=current_cycle,
            loop_last_successful_cycle=last_successful_cycle,
        )
        append_event(
            config,
            "cycle_started",
            {"status": "running", "event_hash": stable_hash({"cycle": current_cycle})},
        )
        write_heartbeat(
            config,
            status="running",
            phase="llm",
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            started_at_utc=loop_started_at_utc,
        )
        update_loop_public_status(
            config,
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            loop_status="running",
            phase="llm",
            started_at_utc=loop_started_at_utc,
            sample_symbols=cycle_symbols,
        )
        last_exit = run(cycle_config, loop_started_at_utc=loop_started_at_utc)
        if last_exit == 0:
            last_successful_cycle = current_cycle
        category = None if last_exit == 0 else "cycle_failed"
        update_loop_public_status(
            config,
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            loop_status="running" if last_exit == 0 else "repairing",
            phase="sleep" if last_exit == 0 else "repairing",
            started_at_utc=loop_started_at_utc,
            sample_symbols=cycle_symbols,
            last_error_category=category,
        )
        if last_exit != 0:
            return last_exit
        next_cycle_at = time.monotonic() + config.sample_cadence_seconds
        while time.monotonic() < next_cycle_at and time.monotonic() - loop_started < config.loop_duration_seconds:
            write_heartbeat(
                config,
                status="running",
                phase="sleep",
                current_cycle=current_cycle,
                last_successful_cycle=last_successful_cycle,
                started_at_utc=loop_started_at_utc,
            )
            update_loop_public_status(
                config,
                current_cycle=current_cycle,
                last_successful_cycle=last_successful_cycle,
                loop_status="running",
                phase="sleep",
                started_at_utc=loop_started_at_utc,
            )
            time.sleep(min(config.heartbeat_interval_seconds, max(1, int(next_cycle_at - time.monotonic()))))
    update_loop_public_status(
        config,
        current_cycle=current_cycle,
        last_successful_cycle=last_successful_cycle,
        loop_status="completed",
        phase="completed",
        started_at_utc=loop_started_at_utc,
    )
    write_heartbeat(
        config,
        status="completed",
        phase="completed",
        current_cycle=current_cycle,
        last_successful_cycle=last_successful_cycle,
        started_at_utc=loop_started_at_utc,
    )
    return last_exit


def run(
    config: FullAnalystConfig,
    *,
    universe_items: list[dict[str, str]] | None = None,
    runner: AnalystRunner | None = None,
    alaya_client: AlayaSyncClient | None = None,
    price_rows: dict[str, dict[str, Any]] | None = None,
    loop_started_at_utc: str | None = None,
) -> int:
    started = time.monotonic()
    started_at_utc = utc_now_iso()
    heartbeat_started_at_utc = loop_started_at_utc or started_at_utc
    ensure_private_dir(private_run_dir(config))
    report_path, status_path = report_paths(config)
    write_heartbeat(
        config,
        status="running",
        phase="preflight",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
    )
    append_event(config, "run_started", {"status": "running", "mode": config.mode})
    try:
        preflight_llm_config(config, runner)
        active_alaya = alaya_client or alaya_client_from_config(config)
    except ConfigurationBlocker as exc:
        return write_blocker_status(config, started_at_utc=started_at_utc, reason=str(exc), report_path=report_path, status_path=status_path)
    universe = universe_items if universe_items is not None else load_public_universe(config)
    items = selected_universe(universe, config.symbols)
    write_heartbeat(
        config,
        status="running",
        phase="cycle",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
    )
    resolved_price_rows = fetch_price_rows(items, config, price_rows)
    write_heartbeat(
        config,
        status="running",
        phase="llm",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
    )
    active_runner = runner or runner_from_config(config)
    results = run_jobs(
        items,
        resolved_price_rows,
        config,
        active_runner,
        active_alaya,
        started_at_utc=heartbeat_started_at_utc,
    )
    status = build_status(
        config=config,
        results=results,
        started_at_utc=started_at_utc,
        elapsed_seconds=time.monotonic() - started,
        report_path=report_path,
        status_path=status_path,
    )
    write_failure_records(config, results, status)
    try:
        paths = write_outputs(config, results, status)
    except PublicScanError as exc:
        category = public_safe_failure_category(str(exc))
        failed = dict(status)
        failed["ok"] = False
        failed["run_status"] = "failed"
        failed["status"] = "failed"
        failed["public_scan_status"] = "failed"
        failed["last_error_category"] = category
        failed["last_error_public_message"] = public_error_message(category)
        failed["exit_status"] = 2
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_public_json(status_path, failed)
        write_heartbeat(
            config,
            status="failed",
            phase="scan",
            current_cycle=config.loop_current_cycle,
            last_successful_cycle=config.loop_last_successful_cycle,
            started_at_utc=heartbeat_started_at_utc,
            last_error_category=category,
        )
        append_event(config, "public_scan_failed", {"status": "failed", "reason": category})
        print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    except Exception as exc:  # noqa: BLE001 - preserve failure in status file when possible.
        category = public_safe_failure_category(str(exc))
        failed = dict(status)
        failed["ok"] = False
        failed["run_status"] = "failed"
        failed["status"] = "failed"
        failed["artifact_write_status"] = "failed"
        failed["artifact_write_failure_reason"] = category
        failed["last_error_category"] = category
        failed["last_error_public_message"] = public_error_message(category)
        failed["exit_status"] = 2
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_public_json(status_path, failed)
        write_heartbeat(
            config,
            status="failed",
            phase="artifact",
            current_cycle=config.loop_current_cycle,
            last_successful_cycle=config.loop_last_successful_cycle,
            started_at_utc=heartbeat_started_at_utc,
            last_error_category=category,
        )
        append_event(config, "artifact_write_failed", {"status": "failed", "reason": category})
        print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    runtime_summary = dict(status)
    runtime_summary["local_output_paths"] = paths
    heartbeat_last_successful_cycle = (
        config.loop_current_cycle if status["exit_status"] == 0 else config.loop_last_successful_cycle
    )
    write_heartbeat(
        config,
        status="completed" if status["exit_status"] == 0 else "failed",
        phase="completed",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=heartbeat_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
        last_error_category=status.get("last_error_category"),
    )
    append_event(config, "run_finished", {"status": runtime_summary["status"], "event_hash": stable_hash(runtime_summary)})
    print(json.dumps(runtime_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return int(status["exit_status"])


def main(argv: list[str] | None = None) -> int:
    try:
        config = config_from_args(parse_args(argv))
        if config.mode == LOOP_MODE:
            return run_loop(config)
        return run(config)
    except Exception as exc:  # noqa: BLE001 - fail closed without secrets.
        print(f"full analyst pipeline failed: {sanitize_text(type(exc).__name__ + ': ' + str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
