"""Minimal public-safe read-only API adapter.

This module deliberately does not import ResearchOS Web UI code, read `.env`,
start subprocesses, connect to providers, or expose private workflow state.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import FastAPI


SERVICE_NAME = "gotra-public-api"
PUBLIC_MODE = "public_safe_read_only"
SOURCE = "科技成长赛道选股报告_美股港股_20260628.md"
SOURCE_DATE = "2026-06-28"
PURPOSE = "research_candidate_pool"
BOUNDARY = (
    "research information only; not investment advice; not trading signal; "
    "not performance proof"
)

HKEX_SYMBOLS = (
    "0068",
    "0136",
    "0268",
    "0285",
    "0501",
    "0696",
    "0700",
    "0800",
    "1024",
    "1060",
    "1357",
    "1478",
    "1530",
    "1548",
    "1810",
    "1896",
    "1952",
    "2018",
    "2157",
    "2162",
    "2269",
    "2273",
    "2400",
    "2507",
    "2533",
    "2556",
    "2586",
    "2696",
    "3738",
    "6600",
    "6682",
    "6990",
    "9606",
    "9660",
    "9688",
    "9911",
    "9926",
    "9969",
)

NASDAQ_SYMBOLS = (
    "ACAD",
    "ADBE",
    "ADMA",
    "ADPT",
    "AGIO",
    "APP",
    "APPF",
    "ARQT",
    "ATAI",
    "AUPH",
    "AVPT",
    "BILI",
    "BMRN",
    "BRZE",
    "BSY",
    "CART",
    "CLBT",
    "CPRX",
    "CRNX",
    "CRWD",
    "DAVE",
    "DUOL",
    "EXEL",
    "EXLS",
    "FROG",
    "FRSH",
    "FSLY",
    "GOOGL",
    "GRAB",
    "GTLB",
    "HRMY",
    "IDCC",
    "INCY",
    "INSM",
    "INTU",
    "LEGN",
    "LGND",
    "LIF",
    "LYFT",
    "MDB",
    "META",
    "MNDY",
    "MSFT",
    "NBIX",
    "NFLX",
    "NVDA",
    "NXT",
    "ONDS",
    "OSIS",
    "OUST",
    "PI",
    "PTC",
    "PTGX",
    "PTRN",
    "QLYS",
    "RELY",
    "ROP",
    "SAIL",
    "SMCI",
    "SMTC",
    "SOUN",
    "SPSC",
    "STOK",
    "TARS",
    "TGTX",
    "TNGX",
    "TTAN",
    "TTD",
    "UTHR",
    "VRTX",
    "VSAT",
    "WAY",
    "WDAY",
    "ZS",
)

NYSE_SYMBOLS = (
    "APH",
    "BMI",
    "CACI",
    "CWAN",
    "ESTC",
    "FN",
    "GRMN",
    "IOT",
    "KVYO",
    "PATH",
    "PAY",
    "PCOR",
    "PINS",
    "QBTS",
    "QTWO",
    "RAMP",
    "RCUS",
    "RDDT",
    "S",
    "SPOT",
    "STUB",
    "TOST",
    "UBER",
    "UI",
    "YMM",
    "ZETA",
)


class ResearchUniverseItem(TypedDict):
    symbol: str
    exchange: Literal["HKEX", "NASDAQ", "NYSE"]
    source: str
    source_date: str
    purpose: str
    boundary: str


def _item(symbol: str, exchange: Literal["HKEX", "NASDAQ", "NYSE"]) -> ResearchUniverseItem:
    return {
        "symbol": symbol,
        "exchange": exchange,
        "source": SOURCE,
        "source_date": SOURCE_DATE,
        "purpose": PURPOSE,
        "boundary": BOUNDARY,
    }


def research_universe_items() -> list[ResearchUniverseItem]:
    return [
        *[_item(symbol, "HKEX") for symbol in HKEX_SYMBOLS],
        *[_item(symbol, "NASDAQ") for symbol in NASDAQ_SYMBOLS],
        *[_item(symbol, "NYSE") for symbol in NYSE_SYMBOLS],
    ]


app = FastAPI(
    title="GOTRA Public API",
    description="Public-safe read-only API adapter for GOTRA public surfaces.",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "mode": PUBLIC_MODE,
    }


@app.get("/api/research-universe")
def research_universe() -> dict[str, object]:
    items = research_universe_items()
    return {
        "ok": True,
        "count": len(items),
        "items": items,
    }


@app.get("/api/public-ledger/status")
def public_ledger_status() -> dict[str, object]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "backend_mode": PUBLIC_MODE,
        "boundaries": [
            "read_only",
            "public_safe",
            "research_information_only",
            "not_investment_advice",
            "not_trading_signal",
            "not_performance_proof",
            "no_env",
            "no_llm",
            "no_provider",
            "no_admin",
            "no_write_operations",
            "no_subprocess",
            "no_private_researchos_ui",
        ],
    }
