from datetime import date
from pathlib import Path

from scripts.public_stock_pool_report import (
    build_status,
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
    assert status["universe_count"] == 3
    assert status["success_count"] == 2
    assert status["failed_count"] == 1
    assert status["by_exchange"]["NYSE"]["failed"] == 1
    assert status["missing_symbols"] == [
        {
            "exchange": "NYSE",
            "symbol": "UBER",
            "provider_ticker": "UBER",
            "reason": "missing",
        }
    ]
    assert "not investment advice" in status["boundary"]
