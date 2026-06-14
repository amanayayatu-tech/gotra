"""Preregistered Phase BT protocol constants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class TickerSpec:
    symbol: str
    name: str
    listing_date: date


@dataclass(frozen=True)
class StyleWindow:
    name: str
    start: date
    end: date


DEFAULT_START = date(2016, 1, 1)
DEFAULT_END = date(2026, 1, 31)
INITIAL_WINDOW_MONTHS = 12
WINDOW_DAYS = 30
FULL_STEP_MONTHS = 1
SAMPLED_STEP_MONTHS = 3

DEFAULT_UNIVERSE: tuple[TickerSpec, ...] = (
    TickerSpec("0700.HK", "Tencent", date(2004, 6, 16)),
    TickerSpec("3690.HK", "Meituan", date(2018, 9, 20)),
    TickerSpec("6060.HK", "ZhongAn Online", date(2017, 9, 28)),
    TickerSpec("NVDA", "NVIDIA", date(1999, 1, 22)),
    TickerSpec("1810.HK", "Xiaomi", date(2018, 7, 9)),
    TickerSpec("9988.HK", "Alibaba HK", date(2019, 11, 26)),
    TickerSpec("1211.HK", "BYD H Shares", date(2002, 7, 31)),
    TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
    TickerSpec("TSM", "Taiwan Semiconductor", date(1997, 10, 9)),
    TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),
)

STYLE_WINDOWS: tuple[StyleWindow, ...] = (
    StyleWindow("US-China trade war", date(2018, 3, 1), date(2019, 12, 31)),
    StyleWindow("COVID shock", date(2020, 1, 1), date(2020, 4, 30)),
    StyleWindow("HK platform regulation", date(2021, 7, 1), date(2021, 12, 31)),
    StyleWindow("Global rate hikes", date(2022, 1, 1), date(2022, 12, 31)),
    StyleWindow("Generative AI regime", date(2023, 1, 1), date(2024, 12, 31)),
)


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def decision_dates(
    *,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    initial_months: int = INITIAL_WINDOW_MONTHS,
    step_months: int = SAMPLED_STEP_MONTHS,
) -> tuple[date, ...]:
    current = add_months(start, initial_months)
    dates: list[date] = []
    while current <= end:
        dates.append(current)
        current = add_months(current, step_months)
    return tuple(dates)


def selected_universe(symbols: list[str] | None = None) -> tuple[TickerSpec, ...]:
    if not symbols:
        return DEFAULT_UNIVERSE
    requested = {symbol.upper() for symbol in symbols}
    selected = tuple(spec for spec in DEFAULT_UNIVERSE if spec.symbol.upper() in requested)
    missing = sorted(requested - {spec.symbol.upper() for spec in selected})
    if missing:
        raise ValueError(f"unknown BT tickers: {', '.join(missing)}")
    return selected


def style_window_for(value: str | date) -> str | None:
    current = parse_date(value)
    for window in STYLE_WINDOWS:
        if window.start <= current <= window.end:
            return window.name
    return None


def ticker_slug(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_").lower()


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date(year, month, 1)).days
