"""Run an independent full-analyst pipeline pilot for public stock symbols.

This one-shot pilot is intentionally separate from the daily public stock-pool
reports. It may call a local Codex CLI runner, but public artifacts never embed
prompt text, completions, messages, raw provider responses, stdout, or stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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
from gotra.public_api.app import research_universe_items  # noqa: E402


SCHEMA = "gotra.full_analyst.pipeline.v1"
STATUS_SCHEMA = "gotra.full_analyst.status.v1"
SYMBOL_SCHEMA = "gotra.full_analyst.symbol.v1"
PRIVATE_ATTEMPT_SCHEMA = "gotra.full_analyst.private_attempt.v1"
MODE = "full-analyst-evening-hk-test"
REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_RUN_ID = "full_analyst_evening_hk_20260629_v1"
DEFAULT_OUTPUT_DIR = Path("/opt/gotra/data/reports/full_analyst_test")
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


class AnalystRunner(Protocol):
    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        """Return final model text without persisting provider I/O."""


class AlayaSyncClient(Protocol):
    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a public-safe sync result."""


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
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a GOTRA full analyst one-shot pilot.")
    parser.add_argument("--mode", choices=(MODE,), required=True)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--private-audit-root", type=Path, default=DEFAULT_PRIVATE_AUDIT_ROOT)
    parser.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR)
    parser.add_argument("--publish-static", action="store_true")
    parser.add_argument("--as-of-date", default=datetime.now(REPORT_TIMEZONE).date().isoformat())
    parser.add_argument("--trading-date", default="")
    parser.add_argument("--universe-url", default="local")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--llm-runner", choices=("codex-cli", "fixture"), default="codex-cli")
    parser.add_argument("--alaya-mode", choices=("mock", "off"), default="mock")
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--per-symbol-timeout-seconds", type=int, default=300)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="high")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> FullAnalystConfig:
    as_of_date = date.fromisoformat(str(args.as_of_date))
    trading_date = date.fromisoformat(str(args.trading_date)) if args.trading_date else latest_completed_hk_session(as_of_date)
    return FullAnalystConfig(
        run_id=str(args.run_id),
        mode=str(args.mode),
        output_dir=args.output_dir,
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
    match = FORBIDDEN_PUBLIC_RE.search(text)
    if match:
        token = re.sub(r"[^a-z0-9_ -]+", "", match.group(0).lower()).strip().replace(" ", "_")
        raise ValueError(f"forbidden_public_content_detected:{token[:80] or 'unknown'}")


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
        return {"status": "skipped", "reason": "judge_status_not_publish"}
    if config.alaya_mode == "off":
        return {"status": "skipped", "reason": "alaya_mode_off"}
    result = alaya_client.sync(symbol_payload)
    if result.get("status") != "synced":
        return {"status": "failed", "reason": sanitize_text(str(result.get("reason") or "unknown"))}
    write_private_json_atomic(
        private_run_dir(config) / "alaya_events" / f"{symbol_payload['exchange']}_{symbol_payload['symbol']}.json",
        result,
    )
    return result


def run_jobs(
    items: list[dict[str, str]],
    price_rows: dict[str, dict[str, Any]],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    alaya_client: AlayaSyncClient,
) -> list[dict[str, Any]]:
    if config.max_concurrency == 1:
        return [run_symbol(item, price_rows[f"{item['exchange']}:{item['symbol']}"], config, runner, alaya_client) for item in items]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=config.max_concurrency) as executor:
        futures = {
            executor.submit(run_symbol, item, price_rows[f"{item['exchange']}:{item['symbol']}"], config, runner, alaya_client): item
            for item in items
        }
        for future in as_completed(futures):
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
    run_status = "completed"
    if failed or blocked or alaya_failed:
        run_status = "completed_with_blockers"
    elif needs_review:
        run_status = "completed_with_review_items"
    status = {
        "schema": STATUS_SCHEMA,
        "ok": not failed and not blocked and not alaya_failed,
        "run_status": run_status,
        "mode": config.mode,
        "run_id": config.run_id,
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
        "failed_symbols": failure_rows(failed),
        "blocked_symbols": failure_rows(blocked),
        "needs_review_symbols": failure_rows(needs_review),
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "llm_runner": config.llm_runner,
        "alaya_mode": config.alaya_mode,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "ok",
        "artifact_write_failure_reason": None,
        "provider_model_io_embedded": False,
        "evidence_layer": "local checks + one-shot runtime smoke + public-safe artifact smoke",
    }
    status["exit_status"] = 0 if status["artifact_write_status"] == "ok" and not failed and not blocked and not alaya_failed else 2
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


def report_paths(config: FullAnalystConfig) -> tuple[Path, Path]:
    report_path = config.output_dir / f"full_analyst_evening_hk_{config.as_of_date.isoformat()}.md"
    status_path = config.output_dir / "status_full_analyst_evening_hk.json"
    return report_path, status_path


def write_outputs(config: FullAnalystConfig, results: list[dict[str, Any]], status: dict[str, Any]) -> dict[str, str]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "symbols").mkdir(parents=True, exist_ok=True)
    report_path, status_path = report_paths(config)
    for row in results:
        if row.get("research"):
            write_public_json(config.output_dir / "symbols" / f"{row['exchange']}_{row['symbol']}.json", row["research"])
    markdown = render_markdown(status, results)
    assert_public_safe(markdown)
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
    assert_public_safe(text)
    write_public_text(path, text)


def publish_static(report_path: Path, status_path: Path, static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    for path in (report_path, status_path):
        target = static_dir / path.name
        shutil.copy2(path, target)
        target.chmod(0o644)


def render_markdown(status: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        f"# GOTRA Full Analyst Pipeline Pilot - {status['as_of_date']}",
        "",
        "## Evidence Layer",
        "",
        "- local checks + one-shot runtime smoke + public-safe artifact smoke",
        "- not formal acceptance",
        "- not science/public proof",
        "- not performance proof",
        "- not a trading signal",
        "",
        "## Status",
        "",
        f"- mode: {status['mode']}",
        f"- run_id: {status['run_id']}",
        f"- run_status: {status['run_status']}",
        f"- trading_date: {status['trading_date']}",
        f"- universe_count: {status['universe_count']}",
        f"- publish_count: {status['publish_count']}",
        f"- needs_review_count: {status['needs_review_count']}",
        f"- blocked_count: {status['blocked_count']}",
        f"- failed_count: {status['failed_count']}",
        f"- alaya_synced_count: {status['alaya_synced_count']}",
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


def runner_from_config(config: FullAnalystConfig) -> AnalystRunner:
    if config.llm_runner == "fixture":
        return FixtureAnalystRunner()
    return CodexCliRunner(
        codex_bin=config.codex_bin,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        cwd=REPO_ROOT,
    )


def run(
    config: FullAnalystConfig,
    *,
    universe_items: list[dict[str, str]] | None = None,
    runner: AnalystRunner | None = None,
    alaya_client: AlayaSyncClient | None = None,
    price_rows: dict[str, dict[str, Any]] | None = None,
) -> int:
    started = time.monotonic()
    started_at_utc = utc_now_iso()
    ensure_private_dir(private_run_dir(config))
    universe = universe_items if universe_items is not None else load_public_universe(config)
    items = selected_universe(universe, config.symbols)
    resolved_price_rows = fetch_price_rows(items, config, price_rows)
    active_runner = runner or runner_from_config(config)
    active_alaya = alaya_client or MockAlayaSyncClient()
    results = run_jobs(items, resolved_price_rows, config, active_runner, active_alaya)
    report_path, status_path = report_paths(config)
    status = build_status(
        config=config,
        results=results,
        started_at_utc=started_at_utc,
        elapsed_seconds=time.monotonic() - started,
        report_path=report_path,
        status_path=status_path,
    )
    try:
        paths = write_outputs(config, results, status)
    except Exception as exc:  # noqa: BLE001 - preserve failure in status file when possible.
        failed = dict(status)
        failed["ok"] = False
        failed["run_status"] = "failed"
        failed["artifact_write_status"] = "failed"
        failed["artifact_write_failure_reason"] = f"{type(exc).__name__}: {sanitize_text(str(exc))[:240]}"
        failed["exit_status"] = 2
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_public_json(status_path, failed)
        print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    runtime_summary = dict(status)
    runtime_summary["local_output_paths"] = paths
    print(json.dumps(runtime_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return int(status["exit_status"])


def main(argv: list[str] | None = None) -> int:
    try:
        return run(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - fail closed without secrets.
        print(f"full analyst pipeline failed: {sanitize_text(type(exc).__name__ + ': ' + str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
