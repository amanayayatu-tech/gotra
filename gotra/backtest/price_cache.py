"""Yahoo adjusted-close CSV cache for Phase BT walk-forward backtests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
import time as time_module
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_PRICE_DIR = Path("data/backtest/prices")
YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
PRICE_COLUMNS = ["date", "ticker", "adj_close", "source_url", "evidence_unverified"]

DateLike = str | date | datetime | pd.Timestamp
Fetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class YahooAdjustedCloseCache:
    """Fetch, persist, and as-of slice Yahoo adjusted daily closes."""

    price_dir: Path = DEFAULT_PRICE_DIR
    fetcher: Fetcher | None = None

    def fetch(self, ticker: str, start: DateLike, end: DateLike) -> pd.DataFrame:
        """Fetch Yahoo chart rows for an inclusive date range."""

        return fetch_yahoo_adjusted_close(ticker, start, end, fetcher=self.fetcher)

    def write(self, ticker: str, start: DateLike, end: DateLike) -> Path:
        """Fetch and write ``data/backtest/prices/<ticker>.csv`` style cache files."""

        return write_price_cache(
            ticker,
            start,
            end,
            price_dir=self.price_dir,
            fetcher=self.fetcher,
        )

    def read(self, ticker: str, cutoff: DateLike | None = None) -> pd.DataFrame:
        """Read a cached ticker, optionally bounded by a cutoff date."""

        return read_price_cache(ticker, price_dir=self.price_dir, cutoff=cutoff)

    def slice(
        self,
        ticker: str,
        as_of: DateLike,
        start: DateLike | None = None,
    ) -> pd.DataFrame:
        """Read cached rows with ``date <= as_of`` and optional lower bound."""

        return slice_price_cache(ticker, as_of, price_dir=self.price_dir, start=start)


def build_yahoo_chart_url(ticker: str, start: DateLike, end: DateLike) -> str:
    """Build a Yahoo chart URL using period1/period2 and 1d interval.

    Yahoo treats ``period2`` as an exclusive Unix timestamp. The public helper accepts
    an inclusive end date, so the URL uses midnight UTC on the day after ``end``.
    """

    normalized_ticker = _normalize_ticker(ticker)
    start_date = _coerce_date(start)
    end_date = _coerce_date(end)
    if end_date < start_date:
        raise ValueError("end must be on or after start")

    params = {
        "period1": str(_epoch_seconds(start_date)),
        "period2": str(_epoch_seconds(end_date + timedelta(days=1))),
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }
    safe_ticker = quote(normalized_ticker, safe="")
    return f"{YAHOO_CHART_BASE_URL}/{safe_ticker}?{urlencode(params)}"


def fetch_yahoo_adjusted_close(
    ticker: str,
    start: DateLike,
    end: DateLike,
    *,
    fetcher: Fetcher | None = None,
) -> pd.DataFrame:
    """Fetch Yahoo chart data and return normalized adjusted-close rows."""

    normalized_ticker = _normalize_ticker(ticker)
    start_date = _coerce_date(start)
    end_date = _coerce_date(end)
    url = build_yahoo_chart_url(normalized_ticker, start_date, end_date)
    payload = (fetcher or _fetch_url)(url)
    chart = _extract_chart(payload)

    timestamps = chart.get("timestamp") or []
    indicators = chart.get("indicators") or {}
    quote_payload = (indicators.get("quote") or [{}])[0] or {}
    close_values = quote_payload.get("close") or []
    adj_payload = (indicators.get("adjclose") or [{}])[0] or {}
    adjusted_values = adj_payload.get("adjclose") or []

    rows: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        row_date = datetime.fromtimestamp(int(timestamp), UTC).date()
        if row_date < start_date or row_date > end_date:
            continue
        adj_close = _float_or_none(_at(adjusted_values, index))
        if adj_close is None:
            adj_close = _float_or_none(_at(close_values, index))
        if adj_close is None:
            continue
        rows.append(
            {
                "date": row_date.isoformat(),
                "ticker": normalized_ticker,
                "adj_close": adj_close,
                "source_url": url,
                "evidence_unverified": False,
            }
        )

    return _normalize_price_frame(pd.DataFrame(rows, columns=PRICE_COLUMNS))


def write_price_cache(
    ticker: str,
    start: DateLike,
    end: DateLike,
    *,
    price_dir: str | Path = DEFAULT_PRICE_DIR,
    fetcher: Fetcher | None = None,
) -> Path:
    """Fetch a full date range and persist it as ``<price_dir>/<ticker>.csv``."""

    normalized_ticker = _normalize_ticker(ticker)
    frame = fetch_yahoo_adjusted_close(normalized_ticker, start, end, fetcher=fetcher)
    cache_path = _cache_path(price_dir, normalized_ticker)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False)
    return cache_path


def read_price_cache(
    ticker: str,
    *,
    price_dir: str | Path = DEFAULT_PRICE_DIR,
    cutoff: DateLike | None = None,
) -> pd.DataFrame:
    """Read a cached adjusted-close CSV, with optional as-of cutoff enforcement."""

    cache_path = _cache_path(price_dir, ticker)
    frame = pd.read_csv(cache_path)
    frame = _normalize_price_frame(frame)
    if cutoff is not None:
        frame = _apply_cutoff(frame, cutoff)
    return frame.reset_index(drop=True)


def slice_price_cache(
    ticker: str,
    as_of: DateLike,
    *,
    price_dir: str | Path = DEFAULT_PRICE_DIR,
    start: DateLike | None = None,
) -> pd.DataFrame:
    """Read cached rows bounded to ``start <= date <= as_of``.

    The upper-bound check is explicit and repeated after filtering so callers cannot
    accidentally receive rows after the walk-forward as-of date.
    """

    frame = read_price_cache(ticker, price_dir=price_dir, cutoff=as_of)
    if start is not None:
        start_date = _coerce_date(start)
        dates = pd.to_datetime(frame["date"]).dt.date
        frame = frame.loc[dates >= start_date]
    return _apply_cutoff(frame, as_of).reset_index(drop=True)


def _fetch_url(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - transient Yahoo transport errors are retried.
            last_error = exc
            if attempt < 2:
                time_module.sleep(0.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("Yahoo chart fetch failed")


def _extract_chart(payload: bytes) -> dict[str, Any]:
    decoded = json.loads(payload.decode("utf-8"))
    chart_root = decoded.get("chart") or {}
    if chart_root.get("error"):
        raise RuntimeError(f"Yahoo chart error: {chart_root['error']}")
    result = (chart_root.get("result") or [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError("Yahoo chart response did not include a result")
    return result


def _normalize_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    missing = [column for column in PRICE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"price cache missing columns: {missing}")

    normalized = frame.loc[:, PRICE_COLUMNS].copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.date.astype(str)
    normalized["ticker"] = normalized["ticker"].astype(str)
    normalized["adj_close"] = pd.to_numeric(normalized["adj_close"], errors="coerce")
    normalized = normalized.dropna(subset=["date", "ticker", "adj_close"])
    normalized["source_url"] = normalized["source_url"].astype(str)
    normalized["evidence_unverified"] = normalized["evidence_unverified"].map(_bool_value)
    normalized = normalized.sort_values("date").drop_duplicates(["date"], keep="last")
    return normalized.reset_index(drop=True)


def _apply_cutoff(frame: pd.DataFrame, cutoff: DateLike) -> pd.DataFrame:
    cutoff_date = _coerce_date(cutoff)
    dates = pd.to_datetime(frame["date"]).dt.date
    sliced = frame.loc[dates <= cutoff_date].copy()
    if not sliced.empty:
        max_date = pd.to_datetime(sliced["date"]).dt.date.max()
        if max_date > cutoff_date:
            raise AssertionError("price cache slice included rows after cutoff")
    return sliced


def _cache_path(price_dir: str | Path, ticker: str) -> Path:
    normalized_ticker = _normalize_ticker(ticker)
    if "/" in normalized_ticker or "\\" in normalized_ticker:
        raise ValueError("ticker must not contain path separators")
    return Path(price_dir) / f"{normalized_ticker}.csv"


def _normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker is required")
    return normalized


def _coerce_date(value: DateLike) -> date:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _epoch_seconds(value: date) -> int:
    return int(datetime.combine(value, time.min, UTC).timestamp())


def _at(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)
