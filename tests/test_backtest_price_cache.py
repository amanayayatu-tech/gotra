from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from gotra.backtest.price_cache import (
    PRICE_COLUMNS,
    YahooAdjustedCloseCache,
    build_yahoo_chart_url,
    fetch_yahoo_adjusted_close,
    read_price_cache,
    slice_price_cache,
    write_price_cache,
)


def test_yahoo_chart_url_uses_period1_period2_and_1d_interval() -> None:
    url = build_yahoo_chart_url("aapl", "2016-01-01", "2016-01-31")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.path == "/v8/finance/chart/AAPL"
    assert query["period1"] == [str(_epoch("2016-01-01"))]
    assert query["period2"] == [str(_epoch("2016-02-01"))]
    assert query["interval"] == ["1d"]
    assert query["events"] == ["history"]
    assert query["includeAdjustedClose"] == ["true"]


def test_fetch_prefers_adjusted_close_and_falls_back_to_close() -> None:
    seen_urls: list[str] = []

    def fake_fetcher(url: str) -> bytes:
        seen_urls.append(url)
        return _chart_payload(
            timestamps=["2020-01-02", "2020-01-03"],
            closes=[101.0, 103.0],
            adjusted=[99.25, None],
        )

    frame = fetch_yahoo_adjusted_close(
        "nvda",
        "2020-01-01",
        "2020-01-31",
        fetcher=fake_fetcher,
    )

    assert seen_urls
    assert list(frame.columns) == PRICE_COLUMNS
    assert frame["ticker"].tolist() == ["NVDA", "NVDA"]
    assert frame["adj_close"].tolist() == [99.25, 103.0]
    assert frame["source_url"].tolist() == [seen_urls[0], seen_urls[0]]
    assert frame["evidence_unverified"].tolist() == [False, False]


def test_write_and_read_price_cache_roundtrip(tmp_path: Path) -> None:
    def fake_fetcher(_url: str) -> bytes:
        return _chart_payload(
            timestamps=["2021-06-01", "2021-06-02"],
            closes=[12.0, 12.5],
            adjusted=[11.75, 12.25],
        )

    cache_path = write_price_cache(
        "0700.hk",
        "2021-06-01",
        "2021-06-02",
        price_dir=tmp_path,
        fetcher=fake_fetcher,
    )
    frame = read_price_cache("0700.HK", price_dir=tmp_path)

    assert cache_path == tmp_path / "0700.HK.csv"
    assert cache_path.exists()
    assert list(frame.columns) == PRICE_COLUMNS
    assert frame.to_dict("records") == [
        {
            "date": "2021-06-01",
            "ticker": "0700.HK",
            "adj_close": 11.75,
            "source_url": frame.loc[0, "source_url"],
            "evidence_unverified": False,
        },
        {
            "date": "2021-06-02",
            "ticker": "0700.HK",
            "adj_close": 12.25,
            "source_url": frame.loc[1, "source_url"],
            "evidence_unverified": False,
        },
    ]


def test_slice_price_cache_enforces_as_of_cutoff(tmp_path: Path) -> None:
    cache = YahooAdjustedCloseCache(
        price_dir=tmp_path,
        fetcher=lambda _url: _chart_payload(
            timestamps=["2022-01-03", "2022-01-04", "2022-01-05"],
            closes=[20.0, 21.0, 22.0],
            adjusted=[19.5, 20.5, 21.5],
        ),
    )
    cache.write("MSFT", "2022-01-03", "2022-01-05")

    sliced = cache.slice("MSFT", as_of="2022-01-04")
    read_with_cutoff = read_price_cache("MSFT", price_dir=tmp_path, cutoff="2022-01-04")
    module_sliced = slice_price_cache("MSFT", "2022-01-04", price_dir=tmp_path)

    assert sliced["date"].tolist() == ["2022-01-03", "2022-01-04"]
    assert read_with_cutoff["date"].tolist() == sliced["date"].tolist()
    assert module_sliced["date"].tolist() == sliced["date"].tolist()
    assert all(date <= "2022-01-04" for date in sliced["date"])


def _chart_payload(
    *,
    timestamps: list[str],
    closes: list[float | None],
    adjusted: list[float | None] | None,
) -> bytes:
    indicators = {"quote": [{"close": closes}]}
    if adjusted is not None:
        indicators["adjclose"] = [{"adjclose": adjusted}]
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [_epoch(value) for value in timestamps],
                    "indicators": indicators,
                }
            ],
            "error": None,
        }
    }
    return json.dumps(payload).encode("utf-8")


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp())
