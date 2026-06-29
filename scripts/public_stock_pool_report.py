"""Generate public-safe stock-pool close-data reports.

This script is intentionally read-only with respect to GOTRA services: it imports the
public research universe, fetches adjusted close rows through the existing Yahoo chart
helper, and writes static markdown/JSON artifacts. It does not call LLM providers,
read .env files, expose private UI state, or generate trading instructions.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from gotra.backtest.price_cache import fetch_yahoo_adjusted_close  # noqa: E402
from gotra.public_api.app import research_universe_items  # noqa: E402


Mode = Literal["morning-global", "evening-hk"]
Exchange = Literal["HKEX", "NASDAQ", "NYSE"]

REPORT_DIR = Path("data/reports")
STATIC_REPORT_DIR = Path("/var/www/gotra-public-ledger/reports")
BOUNDARY_LINES = (
    "research information only",
    "not investment advice",
    "not trading signal",
    "not performance proof",
)
DATA_SOURCE = "Yahoo Finance chart API via GOTRA price_cache helper"
SCHEMA = "gotra.public_stock_pool_report.v1"
REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")
LOGGER = logging.getLogger("gotra.public_stock_pool_report")


@dataclass(frozen=True)
class ExchangeDates:
    primary_trading_date: date
    hkex_trading_date: date
    nasdaq_trading_date: date
    nyse_trading_date: date
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a public-safe GOTRA stock-pool report.")
    parser.add_argument("--mode", choices=("morning-global", "evening-hk"), required=True)
    parser.add_argument("--as-of-date", help="Local Asia/Shanghai as-of date, YYYY-MM-DD.")
    parser.add_argument(
        "--trading-date",
        help="Override the primary/HKEX trading date, YYYY-MM-DD. US dates still follow mode unless --us-trading-date is set.",
    )
    parser.add_argument("--us-trading-date", help="Override NASDAQ/NYSE trading date, YYYY-MM-DD.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--static-dir", type=Path, default=STATIC_REPORT_DIR)
    parser.add_argument("--publish-static", action="store_true")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument(
        "--allowed-missing-symbol",
        action="append",
        default=[],
        help=(
            "Known provider coverage gap to allow without failing the process. "
            "Repeatable. Supports EXCHANGE:SYMBOL, such as HKEX:0501, or provider tickers, such as 0501.HK."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    try:
        return run(args)
    except Exception as exc:  # noqa: BLE001 - service failures must be preserved in journal/status.
        LOGGER.exception(
            "public stock-pool report failed mode=%s report_dir=%s static_dir=%s publish_static=%s",
            args.mode,
            args.report_dir,
            args.static_dir,
            args.publish_static,
        )
        status = write_failure_status(args=args, exc=exc, stage="run")
        return int(status["exit_status"]) if status else 1


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def run(args: argparse.Namespace) -> int:
    LOGGER.info(
        "starting public stock-pool report mode=%s publish_static=%s report_dir=%s static_dir=%s",
        args.mode,
        args.publish_static,
        args.report_dir,
        args.static_dir,
    )
    allowed_missing_symbols = normalize_allowed_missing_symbols(args.allowed_missing_symbol)
    as_of_date = parse_date(args.as_of_date) if args.as_of_date else datetime.now(REPORT_TIMEZONE).date()
    exchange_dates = resolve_exchange_dates(
        mode=args.mode,
        as_of_date=as_of_date,
        trading_date=parse_date(args.trading_date) if args.trading_date else None,
        us_trading_date=parse_date(args.us_trading_date) if args.us_trading_date else None,
    )
    items = research_universe_items()
    if len(items) != 138:
        raise RuntimeError(f"expected 138 public-universe items, got {len(items)}")
    LOGGER.info(
        "resolved report dates as_of_date=%s primary=%s hkex=%s nasdaq=%s nyse=%s universe=%s",
        as_of_date.isoformat(),
        exchange_dates.primary_trading_date.isoformat(),
        exchange_dates.hkex_trading_date.isoformat(),
        exchange_dates.nasdaq_trading_date.isoformat(),
        exchange_dates.nyse_trading_date.isoformat(),
        len(items),
    )

    results = fetch_universe(items, exchange_dates, max_workers=max(1, args.max_workers))
    paths = write_outputs(
        report_dir=args.report_dir,
        mode=args.mode,
        as_of_date=as_of_date,
        exchange_dates=exchange_dates,
        items=items,
        results=results,
        allowed_missing_symbols=allowed_missing_symbols,
    )
    log_status_summary(paths["status"])
    if args.publish_static:
        try:
            publish_static(paths, args.static_dir)
        except Exception as exc:  # noqa: BLE001 - preserve publish failure in status.json and journal.
            status = mark_artifact_write_failure(paths["status"], stage="publish_static", exc=exc)
            write_status_json(Path(paths["status_path"]), status)
            paths["status"] = status
            try:
                publish_status_static(Path(paths["status_path"]), args.static_dir)
            except Exception as status_exc:  # noqa: BLE001 - journal retains the status copy failure.
                LOGGER.exception(
                    "status.json static publish failed path=%s static_dir=%s reason=%s",
                    paths["status_path"],
                    args.static_dir,
                    status_exc,
                )
            log_status_summary(status)
            print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
            return int(status["exit_status"])
        LOGGER.info("published static report artifacts static_dir=%s", args.static_dir)

    print(json.dumps(paths["status"], ensure_ascii=False, indent=2, sort_keys=True))
    return int(paths["status"]["exit_status"])


def resolve_exchange_dates(
    *,
    mode: Mode,
    as_of_date: date,
    trading_date: date | None,
    us_trading_date: date | None,
) -> ExchangeDates:
    if mode == "morning-global":
        primary = trading_date or latest_completed_us_session(as_of_date)
        return ExchangeDates(
            primary_trading_date=primary,
            hkex_trading_date=primary,
            nasdaq_trading_date=us_trading_date or primary,
            nyse_trading_date=us_trading_date or primary,
            reason="after US market close; full-market latest completed session",
        )

    hkex_date = trading_date or latest_completed_hk_session(as_of_date)
    us_date = us_trading_date or latest_completed_us_session(as_of_date)
    return ExchangeDates(
        primary_trading_date=hkex_date,
        hkex_trading_date=hkex_date,
        nasdaq_trading_date=us_date,
        nyse_trading_date=us_date,
        reason=(
            "after HK market close; HKEX uses latest completed HK session, "
            "US exchanges use previous completed US session"
        ),
    )


def latest_completed_us_session(as_of_date: date) -> date:
    return previous_weekday(as_of_date - timedelta(days=1))


def latest_completed_hk_session(as_of_date: date) -> date:
    return previous_weekday(as_of_date)


def previous_weekday(value: date) -> date:
    current = value
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def fetch_universe(
    items: list[dict[str, str]],
    exchange_dates: ExchangeDates,
    *,
    max_workers: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_one, item, exchange_dates) for item in items]
        for future in as_completed(futures):
            results.append(future.result())
    sorted_results = sorted(results, key=lambda row: (str(row["exchange"]), str(row["symbol"])))
    failures = [row for row in sorted_results if not row.get("ok")]
    if failures:
        LOGGER.warning(
            "stock-pool fetch completed with failed_symbols=%s",
            ",".join(f"{row['exchange']}:{row['symbol']}:{row.get('reason', 'unknown')}" for row in failures),
        )
    return sorted_results


def fetch_one(item: dict[str, str], exchange_dates: ExchangeDates) -> dict[str, Any]:
    symbol = str(item["symbol"]).strip().upper()
    exchange = str(item["exchange"])
    ticker = yahoo_ticker(symbol, exchange)
    trading_date = trading_date_for_exchange(exchange, exchange_dates)
    start_date = trading_date - timedelta(days=10)
    try:
        frame = fetch_yahoo_adjusted_close(ticker, start_date, trading_date)
        if frame.empty:
            return failed_row(item, ticker, trading_date, "empty_price_frame")
        close_row = row_for_date(frame, trading_date)
        if close_row is None:
            return failed_row(item, ticker, trading_date, "trading_date_close_missing")
        previous_row = previous_row_before(frame, trading_date)
        close = float(close_row["adj_close"])
        previous_close = float(previous_row["adj_close"]) if previous_row is not None else None
        change_pct = None
        if previous_close not in (None, 0):
            change_pct = (close / previous_close - 1.0) * 100.0
        return {
            "ok": True,
            "symbol": symbol,
            "exchange": exchange,
            "provider_ticker": ticker,
            "close_date": trading_date.isoformat(),
            "adj_close": round(close, 6),
            "previous_date": str(previous_row["date"]) if previous_row is not None else "",
            "previous_adj_close": round(previous_close, 6) if previous_close is not None else None,
            "one_session_change_pct": round(change_pct, 4) if change_pct is not None else None,
        }
    except Exception as exc:  # noqa: BLE001 - per-symbol failures must preserve coverage.
        return failed_row(item, ticker, trading_date, f"{type(exc).__name__}: {str(exc)[:240]}")


def failed_row(
    item: dict[str, str],
    provider_ticker: str,
    trading_date: date,
    reason: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "symbol": str(item["symbol"]).strip().upper(),
        "exchange": str(item["exchange"]),
        "provider_ticker": provider_ticker,
        "close_date": trading_date.isoformat(),
        "reason": reason,
    }


def yahoo_ticker(symbol: str, exchange: str) -> str:
    if exchange == "HKEX":
        return f"{symbol}.HK"
    return symbol


def trading_date_for_exchange(exchange: str, dates: ExchangeDates) -> date:
    if exchange == "HKEX":
        return dates.hkex_trading_date
    if exchange == "NASDAQ":
        return dates.nasdaq_trading_date
    if exchange == "NYSE":
        return dates.nyse_trading_date
    raise ValueError(f"unsupported exchange: {exchange}")


def row_for_date(frame: pd.DataFrame, target: date) -> pd.Series | None:
    rows = frame.loc[pd.to_datetime(frame["date"]).dt.date == target]
    if rows.empty:
        return None
    return rows.iloc[-1]


def previous_row_before(frame: pd.DataFrame, target: date) -> pd.Series | None:
    rows = frame.loc[pd.to_datetime(frame["date"]).dt.date < target]
    if rows.empty:
        return None
    return rows.iloc[-1]


def write_outputs(
    *,
    report_dir: Path,
    mode: Mode,
    as_of_date: date,
    exchange_dates: ExchangeDates,
    items: list[dict[str, str]],
    results: list[dict[str, Any]],
    allowed_missing_symbols: tuple[str, ...] = (),
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"public_stock_pool_eod_{exchange_dates.primary_trading_date}.md"
    latest_path = report_dir / "latest.md"
    status_path = report_dir / "status.json"
    status = build_status(
        mode=mode,
        as_of_date=as_of_date,
        exchange_dates=exchange_dates,
        items=items,
        results=results,
        report_path=report_path,
        latest_path=latest_path,
        status_path=status_path,
        allowed_missing_symbols=allowed_missing_symbols,
    )
    markdown = render_markdown(status=status, results=results)
    write_text_atomic(report_path, markdown)
    write_text_atomic(latest_path, markdown)
    write_status_json(status_path, status)
    chmod_public(report_path)
    chmod_public(latest_path)
    LOGGER.info(
        "wrote report artifacts report_path=%s latest_path=%s status_path=%s",
        report_path.resolve(),
        latest_path.resolve(),
        status_path.resolve(),
    )
    return {
        "report_path": str(report_path.resolve()),
        "latest_path": str(latest_path.resolve()),
        "status_path": str(status_path.resolve()),
        "status": status,
    }


def build_status(
    *,
    mode: Mode,
    as_of_date: date,
    exchange_dates: ExchangeDates,
    items: list[dict[str, str]],
    results: list[dict[str, Any]],
    report_path: Path,
    latest_path: Path,
    status_path: Path,
    allowed_missing_symbols: tuple[str, ...] = (),
) -> dict[str, Any]:
    successes = [row for row in results if row.get("ok")]
    failures = [row for row in results if not row.get("ok")]
    exchanges = ("HKEX", "NASDAQ", "NYSE")
    allowed_missing = tuple(sorted(set(normalize_allowed_missing_symbols(allowed_missing_symbols))))
    failed_symbols = [
        {
            "exchange": row["exchange"],
            "symbol": row["symbol"],
            "provider_ticker": row["provider_ticker"],
            "reason": row.get("reason", "unknown"),
        }
        for row in failures
    ]
    allowed_missing_count = sum(1 for row in failures if is_allowed_missing_failure(row, allowed_missing))
    unexpected_failed_count = len(failures) - allowed_missing_count
    run_status = "completed"
    if failures and unexpected_failed_count == 0:
        run_status = "completed_with_allowed_data_gaps"
    elif failures:
        run_status = "partial"
    status = {
        "schema": SCHEMA,
        "ok": not failures,
        "run_status": run_status,
        "mode": mode,
        "as_of_date": as_of_date.isoformat(),
        "trading_date": exchange_dates.primary_trading_date.isoformat(),
        "exchange_trading_dates": {
            "HKEX": exchange_dates.hkex_trading_date.isoformat(),
            "NASDAQ": exchange_dates.nasdaq_trading_date.isoformat(),
            "NYSE": exchange_dates.nyse_trading_date.isoformat(),
        },
        "reason": exchange_dates.reason,
        "session_status": "weekend/no-new-session"
        if as_of_date.weekday() >= 5
        else "scheduled-session-check",
        "universe_count": len(items),
        "success_count": len(successes),
        "failed_count": len(failures),
        "allowed_missing_symbols": list(allowed_missing),
        "allowed_missing_count": allowed_missing_count,
        "unexpected_failed_count": unexpected_failed_count,
        "by_exchange": {
            exchange: {
                "universe": sum(1 for item in items if item["exchange"] == exchange),
                "success": sum(1 for row in successes if row["exchange"] == exchange),
                "failed": sum(1 for row in failures if row["exchange"] == exchange),
                "trading_date": trading_date_for_exchange(exchange, exchange_dates).isoformat(),
            }
            for exchange in exchanges
        },
        "missing_symbols": failed_symbols,
        "failed_symbols": failed_symbols,
        "source": DATA_SOURCE,
        "boundary": list(BOUNDARY_LINES),
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "report_file": report_path.name,
        "latest_file": latest_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "ok",
        "artifact_write_failure_reason": None,
        "failure_stage": None,
    }
    status["exit_status"] = exit_code_for_status(status)
    return status


def build_failure_status(*, args: argparse.Namespace, exc: Exception, stage: str) -> dict[str, Any]:
    as_of = failure_as_of_date(args.as_of_date)
    status_path = args.report_dir / "status.json"
    reason = failure_reason(stage=stage, exc=exc)
    return {
        "schema": SCHEMA,
        "ok": False,
        "run_status": "failed",
        "mode": args.mode,
        "as_of_date": as_of.isoformat(),
        "trading_date": None,
        "exchange_trading_dates": {},
        "reason": "report generation failed before a complete public-safe report was written",
        "session_status": "failed",
        "universe_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "allowed_missing_symbols": list(normalize_allowed_missing_symbols(getattr(args, "allowed_missing_symbol", []))),
        "allowed_missing_count": 0,
        "unexpected_failed_count": 0,
        "by_exchange": {},
        "missing_symbols": [],
        "failed_symbols": [],
        "source": DATA_SOURCE,
        "boundary": list(BOUNDARY_LINES),
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "report_file": None,
        "latest_file": None,
        "status_file": status_path.name,
        "artifact_write_status": "failed",
        "artifact_write_failure_reason": reason,
        "failure_stage": stage,
        "exit_status": 2,
    }


def failure_reason(*, stage: str, exc: Exception) -> str:
    return f"{stage}: {type(exc).__name__}: {str(exc)[:240]}"


def failure_as_of_date(value: str | None) -> date:
    if not value:
        return datetime.now(REPORT_TIMEZONE).date()
    try:
        return parse_date(value)
    except Exception:  # noqa: BLE001 - failure status must survive malformed input.
        return datetime.now(REPORT_TIMEZONE).date()


def mark_artifact_write_failure(status: dict[str, Any], *, stage: str, exc: Exception) -> dict[str, Any]:
    failed = dict(status)
    failed["ok"] = False
    failed["run_status"] = "failed"
    failed["artifact_write_status"] = "failed"
    failed["artifact_write_failure_reason"] = failure_reason(stage=stage, exc=exc)
    failed["failure_stage"] = stage
    failed["failure_time_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    failed["exit_status"] = exit_code_for_status(failed)
    return failed


def normalize_allowed_missing_symbols(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw_value in values or ():
        value = str(raw_value).strip().upper()
        if not value:
            continue
        if ":" in value:
            exchange, symbol = value.split(":", 1)
            exchange = exchange.strip()
            symbol = symbol.strip()
            if exchange and symbol:
                normalized.add(f"{exchange}:{symbol}")
            continue
        normalized.add(value)
    return tuple(sorted(normalized))


def failure_symbol_keys(row: dict[str, Any]) -> set[str]:
    exchange = str(row.get("exchange") or "").strip().upper()
    symbol = str(row.get("symbol") or "").strip().upper()
    provider_ticker = str(row.get("provider_ticker") or "").strip().upper()
    keys = {key for key in (provider_ticker, f"{exchange}:{symbol}" if exchange and symbol else "") if key}
    if exchange == "HKEX" and symbol:
        keys.add(f"{symbol}.HK")
    return keys


def is_allowed_missing_failure(row: dict[str, Any], allowed_missing_symbols: tuple[str, ...]) -> bool:
    if not allowed_missing_symbols:
        return False
    return bool(failure_symbol_keys(row) & set(allowed_missing_symbols))


def exit_code_for_status(status: dict[str, Any]) -> int:
    if status.get("artifact_write_status") != "ok":
        return 2
    failed_count = int(status.get("failed_count") or 0)
    if failed_count == 0:
        return 0
    unexpected_failed_count = int(status.get("unexpected_failed_count", failed_count) or 0)
    return 0 if unexpected_failed_count == 0 else 2


def write_failure_status(*, args: argparse.Namespace, exc: Exception, stage: str) -> dict[str, Any] | None:
    status = build_failure_status(args=args, exc=exc, stage=stage)
    status_path = args.report_dir / "status.json"
    try:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        write_status_json(status_path, status)
        LOGGER.error(
            "wrote failure status.json path=%s reason=%s",
            status_path.resolve(),
            status["artifact_write_failure_reason"],
        )
    except Exception as status_exc:  # noqa: BLE001 - this exact failure must remain visible in journal.
        LOGGER.exception("status.json write failed path=%s reason=%s", status_path, status_exc)
        return None

    if args.publish_static:
        try:
            publish_status_static(status_path, args.static_dir)
        except Exception as status_exc:  # noqa: BLE001 - journal retains the static status copy failure.
            LOGGER.exception(
                "failure status.json static publish failed path=%s static_dir=%s reason=%s",
                status_path,
                args.static_dir,
                status_exc,
            )
    return status


def log_status_summary(status: dict[str, Any]) -> None:
    LOGGER.info(
        "report status ok=%s run_status=%s success_count=%s failed_count=%s trading_date=%s status_file=%s",
        status.get("ok"),
        status.get("run_status"),
        status.get("success_count"),
        status.get("failed_count"),
        status.get("trading_date"),
        status.get("status_file"),
    )
    failed_symbols = status.get("failed_symbols") or []
    if failed_symbols:
        LOGGER.warning("failed symbols: %s", json.dumps(failed_symbols, ensure_ascii=False, sort_keys=True))


def render_markdown(*, status: dict[str, Any], results: list[dict[str, Any]]) -> str:
    successes = [row for row in results if row.get("ok")]
    failures = [row for row in results if not row.get("ok")]
    lines: list[str] = [
        f"# GOTRA Public Stock Pool Report - {status['trading_date']}",
        "",
        "## Run Metadata",
        "",
        f"- as_of_date: {status['as_of_date']}",
        f"- trading_date: {status['trading_date']}",
        f"- mode: {status['mode']}",
        f"- reason: {status['reason']}",
        f"- session_status: {status['session_status']}",
        f"- generated_at_utc: {status['generated_at_utc']}",
        f"- universe_count: {status['universe_count']}",
        f"- success_count: {status['success_count']}",
        f"- failed_count: {status['failed_count']}",
        f"- source: {status['source']}",
        "",
        "## Public Safety Boundary",
        "",
    ]
    lines.extend(f"- {line}" for line in BOUNDARY_LINES)
    lines.extend(
        [
            "- no buy/sell/hold/position instruction is generated",
            "- no raw provider/model I/O is embedded",
            "",
            "## Exchange Dates And Coverage",
            "",
            "| Exchange | Trading Date | Universe | Success | Failed |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for exchange, values in status["by_exchange"].items():
        lines.append(
            f"| {exchange} | {values['trading_date']} | {values['universe']} | "
            f"{values['success']} | {values['failed']} |"
        )

    if failures:
        lines.extend(
            [
                "",
                "## Missing Or Failed Symbols",
                "",
                "| Exchange | Symbol | Provider Ticker | Requested Close Date | Reason |",
                "|---|---:|---|---|---|",
            ]
        )
        for row in failures:
            reason = str(row.get("reason", "unknown")).replace("|", "/")
            lines.append(
                f"| {row['exchange']} | {row['symbol']} | {row['provider_ticker']} | "
                f"{row['close_date']} | {reason} |"
            )

    lines.extend(
        [
            "",
            "## Close Data",
            "",
            "Rows are sorted by exchange and symbol, not by return or ranking.",
            "",
            "| Exchange | Symbol | Provider Ticker | Close Date | Adj Close | Previous Date | Previous Adj Close | One-Session Change % |",
            "|---|---:|---|---|---:|---|---:|---:|",
        ]
    )
    for row in successes:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["exchange"]),
                    str(row["symbol"]),
                    str(row["provider_ticker"]),
                    str(row["close_date"]),
                    format_value(row["adj_close"]),
                    str(row.get("previous_date") or ""),
                    format_value(row.get("previous_adj_close")),
                    format_value(row.get("one_session_change_pct")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This report records observed adjusted close data availability for the public research universe only. It does not rank securities for action, claim forecast skill, prove strategy performance, or provide investment, trading, portfolio, tax, or legal advice.",
            "",
        ]
    )
    return "\n".join(lines)


def publish_static(paths: dict[str, Any], static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    owner = static_owner(static_dir)
    apply_owner(static_dir, owner)
    sources = [
        Path(paths["report_path"]),
        Path(paths["latest_path"]),
        Path(paths["status_path"]),
    ]
    for source in sources:
        target = static_dir / source.name
        shutil.copy2(source, target)
        chmod_public(target)
        apply_owner(target, owner)
    chmod_public(static_dir)


def publish_status_static(status_path: Path, static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    owner = static_owner(static_dir)
    apply_owner(static_dir, owner)
    target = static_dir / status_path.name
    shutil.copy2(status_path, target)
    chmod_public(target)
    apply_owner(target, owner)


def write_status_json(path: Path, status: dict[str, Any]) -> None:
    try:
        write_text_atomic(path, json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        chmod_public(path)
    except Exception as exc:  # noqa: BLE001 - caller logs or writes a fallback failure status.
        LOGGER.exception("status.json write failed path=%s reason=%s", path, exc)
        raise


def write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def chmod_public(path: Path) -> None:
    path.chmod(0o755 if path.is_dir() else 0o644)


def static_owner(static_dir: Path) -> tuple[int, int] | None:
    try:
        parent_stat = static_dir.parent.stat()
    except OSError:
        return None
    return parent_stat.st_uid, parent_stat.st_gid


def apply_owner(path: Path, owner: tuple[int, int] | None) -> None:
    if owner is None:
        return
    try:
        os.chown(path, owner[0], owner[1])
    except PermissionError:
        return


def parse_date(value: str) -> date:
    return datetime.combine(pd.to_datetime(value).date(), time.min).date()


def format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
