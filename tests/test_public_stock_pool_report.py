import argparse
from datetime import date
from pathlib import Path

from scripts.public_stock_pool_report import (
    build_status,
    build_failure_status,
    exit_code_for_status,
    mark_artifact_write_failure,
    normalize_allowed_missing_symbols,
    resolve_exchange_dates,
    yahoo_ticker,
)


def test_morning_global_uses_previous_completed_us_session() -> None:
    dates = resolve_exchange_dates(
        mode="morning-global",
        as_of_date=date(2026, 6, 30),
        trading_date=None,
        us_trading_date=None,
    )

    assert dates.primary_trading_date == date(2026, 6, 29)
    assert dates.hkex_trading_date == date(2026, 6, 29)
    assert dates.nasdaq_trading_date == date(2026, 6, 29)
    assert dates.nyse_trading_date == date(2026, 6, 29)


def test_evening_hk_keeps_us_on_previous_completed_session() -> None:
    dates = resolve_exchange_dates(
        mode="evening-hk",
        as_of_date=date(2026, 6, 29),
        trading_date=None,
        us_trading_date=None,
    )

    assert dates.primary_trading_date == date(2026, 6, 29)
    assert dates.hkex_trading_date == date(2026, 6, 29)
    assert dates.nasdaq_trading_date == date(2026, 6, 26)
    assert dates.nyse_trading_date == date(2026, 6, 26)


def test_yahoo_ticker_maps_hkex_suffix_only() -> None:
    assert yahoo_ticker("0700", "HKEX") == "0700.HK"
    assert yahoo_ticker("NVDA", "NASDAQ") == "NVDA"
    assert yahoo_ticker("UBER", "NYSE") == "UBER"


def test_build_status_keeps_public_safe_metadata() -> None:
    dates = resolve_exchange_dates(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        trading_date=date(2026, 6, 26),
        us_trading_date=None,
    )
    items = [
        {"symbol": "0700", "exchange": "HKEX"},
        {"symbol": "NVDA", "exchange": "NASDAQ"},
        {"symbol": "UBER", "exchange": "NYSE"},
    ]
    results = [
        {"ok": True, "symbol": "0700", "exchange": "HKEX", "provider_ticker": "0700.HK"},
        {"ok": True, "symbol": "NVDA", "exchange": "NASDAQ", "provider_ticker": "NVDA"},
        {"ok": False, "symbol": "UBER", "exchange": "NYSE", "provider_ticker": "UBER", "reason": "missing", "close_date": "2026-06-26"},
    ]

    status = build_status(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        exchange_dates=dates,
        items=items,
        results=results,
        report_path=Path("public_stock_pool_eod_2026-06-26.md"),
        latest_path=Path("latest.md"),
        status_path=Path("status.json"),
    )

    assert status["schema"] == "gotra.public_stock_pool_report.v1"
    assert status["ok"] is False
    assert status["run_status"] == "partial"
    assert status["universe_count"] == 3
    assert status["success_count"] == 2
    assert status["failed_count"] == 1
    assert status["allowed_missing_symbols"] == []
    assert status["allowed_missing_count"] == 0
    assert status["unexpected_failed_count"] == 1
    assert status["exit_status"] == 2
    assert exit_code_for_status(status) == 2
    assert status["by_exchange"]["NYSE"]["failed"] == 1
    assert status["missing_symbols"] == [
        {
            "exchange": "NYSE",
            "symbol": "UBER",
            "provider_ticker": "UBER",
            "reason": "missing",
        }
    ]
    assert status["failed_symbols"] == status["missing_symbols"]
    assert status["artifact_write_status"] == "ok"
    assert status["artifact_write_failure_reason"] is None
    assert "not investment advice" in status["boundary"]


def test_status_exit_zero_when_all_symbols_succeed() -> None:
    dates = resolve_exchange_dates(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        trading_date=date(2026, 6, 26),
        us_trading_date=None,
    )
    items = [{"symbol": "0700", "exchange": "HKEX"}]
    results = [{"ok": True, "symbol": "0700", "exchange": "HKEX", "provider_ticker": "0700.HK"}]

    status = build_status(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        exchange_dates=dates,
        items=items,
        results=results,
        report_path=Path("public_stock_pool_eod_2026-06-26.md"),
        latest_path=Path("latest.md"),
        status_path=Path("status.json"),
    )

    assert status["ok"] is True
    assert status["run_status"] == "completed"
    assert status["failed_count"] == 0
    assert status["allowed_missing_count"] == 0
    assert status["unexpected_failed_count"] == 0
    assert status["exit_status"] == 0
    assert exit_code_for_status(status) == 0


def test_allowed_provider_gap_keeps_partial_status_but_exit_zero() -> None:
    dates = resolve_exchange_dates(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        trading_date=date(2026, 6, 26),
        us_trading_date=None,
    )
    items = [
        {"symbol": "0501", "exchange": "HKEX"},
        {"symbol": "0700", "exchange": "HKEX"},
    ]
    results = [
        {
            "ok": False,
            "symbol": "0501",
            "exchange": "HKEX",
            "provider_ticker": "0501.HK",
            "reason": "empty_price_frame",
            "close_date": "2026-06-26",
        },
        {"ok": True, "symbol": "0700", "exchange": "HKEX", "provider_ticker": "0700.HK"},
    ]

    status = build_status(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        exchange_dates=dates,
        items=items,
        results=results,
        report_path=Path("public_stock_pool_eod_2026-06-26.md"),
        latest_path=Path("latest.md"),
        status_path=Path("status.json"),
        allowed_missing_symbols=normalize_allowed_missing_symbols(["HKEX:0501", "0501.HK"]),
    )

    assert status["ok"] is False
    assert status["run_status"] == "completed_with_allowed_data_gaps"
    assert status["failed_count"] == 1
    assert status["allowed_missing_symbols"] == ["0501.HK", "HKEX:0501"]
    assert status["allowed_missing_count"] == 1
    assert status["unexpected_failed_count"] == 0
    assert status["failed_symbols"][0]["reason"] == "empty_price_frame"
    assert status["exit_status"] == 0
    assert exit_code_for_status(status) == 0


def test_unexpected_provider_gap_exits_two() -> None:
    dates = resolve_exchange_dates(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        trading_date=date(2026, 6, 26),
        us_trading_date=None,
    )
    items = [{"symbol": "UBER", "exchange": "NYSE"}]
    results = [
        {
            "ok": False,
            "symbol": "UBER",
            "exchange": "NYSE",
            "provider_ticker": "UBER",
            "reason": "empty_price_frame",
            "close_date": "2026-06-26",
        }
    ]

    status = build_status(
        mode="morning-global",
        as_of_date=date(2026, 6, 28),
        exchange_dates=dates,
        items=items,
        results=results,
        report_path=Path("public_stock_pool_eod_2026-06-26.md"),
        latest_path=Path("latest.md"),
        status_path=Path("status.json"),
        allowed_missing_symbols=normalize_allowed_missing_symbols(["HKEX:0501"]),
    )

    assert status["ok"] is False
    assert status["run_status"] == "partial"
    assert status["failed_count"] == 1
    assert status["allowed_missing_count"] == 0
    assert status["unexpected_failed_count"] == 1
    assert status["exit_status"] == 2
    assert exit_code_for_status(status) == 2


def test_failure_status_records_write_reason_without_failed_symbols(tmp_path: Path) -> None:
    args = argparse.Namespace(
        mode="morning-global",
        as_of_date="not-a-date",
        report_dir=tmp_path / "reports",
        static_dir=tmp_path / "static",
        publish_static=True,
        allowed_missing_symbol=["HKEX:0501"],
    )

    status = build_failure_status(args=args, exc=RuntimeError("disk full"), stage="run")

    assert status["ok"] is False
    assert status["run_status"] == "failed"
    assert status["artifact_write_status"] == "failed"
    assert status["artifact_write_failure_reason"] == "run: RuntimeError: disk full"
    assert status["allowed_missing_symbols"] == ["HKEX:0501"]
    assert status["exit_status"] == 2
    assert status["failed_symbols"] == []
    assert status["missing_symbols"] == []


def test_mark_artifact_write_failure_preserves_symbol_failures() -> None:
    status = {
        "ok": False,
        "run_status": "partial",
        "failed_count": 1,
        "allowed_missing_count": 1,
        "unexpected_failed_count": 0,
        "failed_symbols": [{"exchange": "NYSE", "symbol": "UBER", "reason": "missing"}],
        "artifact_write_status": "ok",
        "exit_status": 0,
    }

    failed = mark_artifact_write_failure(status, stage="publish_static", exc=PermissionError("denied"))

    assert failed["ok"] is False
    assert failed["run_status"] == "failed"
    assert failed["artifact_write_status"] == "failed"
    assert failed["artifact_write_failure_reason"] == "publish_static: PermissionError: denied"
    assert failed["failure_stage"] == "publish_static"
    assert failed["exit_status"] == 2
    assert failed["failed_symbols"] == status["failed_symbols"]
