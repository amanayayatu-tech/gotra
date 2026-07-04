"""Minimal public-safe read-only API adapter.

This module deliberately does not import ResearchOS Web UI code, read `.env`,
start subprocesses, connect to providers, or expose private workflow state.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal, TypedDict

from fastapi import FastAPI
from fastapi.responses import JSONResponse


SERVICE_NAME = "gotra-public-api"
PUBLIC_MODE = "public_safe_read_only"
SOURCE = "科技成长赛道选股报告_美股港股_20260628.md"
SOURCE_DATE = "2026-06-28"
PURPOSE = "research_candidate_pool"
BOUNDARY = (
    "research information only; not investment advice; not trading signal; "
    "not performance proof"
)
DEFAULT_REPORTS_DIR = Path("/var/www/gotra-public-ledger/reports")
LEDGER_FILE_NAME = "research_ledger.json"
LEDGER_MANIFEST_SCHEMA = "gotra.public_research_ledger.v1"
LEDGER_ENTRY_SCHEMA = "gotra.ledger_entry.v1"
REVIEW_RESULT_SCHEMA = "gotra.review_result.v1"
REVIEW_UNAVAILABLE_REASON_SCHEMA = "gotra.review_unavailable_reason.v1"

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


def stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def ledger_entry_hash_basis(entry: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in entry.items() if key != "hash"}


def ledger_path() -> Path:
    return Path(os.environ.get("GOTRA_PUBLIC_REPORTS_DIR", str(DEFAULT_REPORTS_DIR))) / LEDGER_FILE_NAME


def load_public_research_ledger(path: Path | None = None) -> dict[str, object]:
    target = path or ledger_path()
    if not target.exists():
        return {
            "schema": LEDGER_MANIFEST_SCHEMA,
            "generated_at": "",
            "entry_count": 0,
            "integrity": {"ok": True, "entry_count": 0, "latest_hash": "0" * 64},
            "entries": [],
        }
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ledger_manifest_not_object")
    return payload


def verify_public_research_ledger(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("schema") != LEDGER_MANIFEST_SCHEMA:
        return {"ok": False, "reason": "ledger_manifest_schema_mismatch"}
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return {"ok": False, "reason": "ledger_entries_not_list"}
    previous_hash = "0" * 64
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            return {"ok": False, "reason": "ledger_entry_not_object", "entry_index": index}
        if raw_entry.get("schema") != LEDGER_ENTRY_SCHEMA:
            return {"ok": False, "reason": "ledger_entry_schema_mismatch", "entry_index": index}
        expected_hash = stable_hash(ledger_entry_hash_basis(raw_entry))
        if raw_entry.get("hash") != expected_hash:
            return {
                "ok": False,
                "reason": "ledger_entry_hash_mismatch",
                "entry_index": index,
                "entry_id": raw_entry.get("entry_id"),
            }
        if raw_entry.get("previous_hash") != previous_hash:
            return {
                "ok": False,
                "reason": "ledger_previous_hash_mismatch",
                "entry_index": index,
                "entry_id": raw_entry.get("entry_id"),
                "expected_previous_hash": previous_hash,
                "actual_previous_hash": raw_entry.get("previous_hash"),
            }
        previous_hash = str(raw_entry.get("hash") or "")
    return {"ok": True, "entry_count": len(raw_entries), "latest_hash": previous_hash}


def public_ledger_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    entries = payload.get("entries")
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def public_ledger_review_results(payload: dict[str, object]) -> list[dict[str, object]]:
    results = payload.get("review_results")
    return [result for result in results if isinstance(result, dict)] if isinstance(results, list) else []


def public_ledger_review_unavailable(payload: dict[str, object]) -> list[dict[str, object]]:
    reasons = payload.get("review_unavailable")
    return [reason for reason in reasons if isinstance(reason, dict)] if isinstance(reasons, list) else []


def public_ledger_review_coverage(payload: dict[str, object]) -> dict[str, object]:
    coverage = payload.get("review_coverage")
    if isinstance(coverage, dict):
        return coverage
    entries = public_ledger_entries(payload)
    return {
        "supported_windows_days": [1, 7, 30, 90],
        "total_count": len(entries),
        "due_count": 0,
        "reviewed_count": 0,
        "not_due_count": len(entries),
        "unavailable_count": 0,
        "missing_due_entry_ids": [],
        "by_window_days": [],
        "boundary": "review coverage is unavailable in this legacy manifest; not performance proof",
    }


def review_status_for_entry(entry: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
    entry_id = str(entry.get("entry_id") or "")
    for result in public_ledger_review_results(payload):
        if result.get("entry_id") == entry_id:
            return {"review_status": "reviewed", "review_result": result, "review_unavailable_reason": None}
    for reason in public_ledger_review_unavailable(payload):
        if reason.get("entry_id") == entry_id:
            return {"review_status": "review_unavailable", "review_result": None, "review_unavailable_reason": reason}
    return {"review_status": "not_due", "review_result": None, "review_unavailable_reason": None}


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


@app.get("/api/track-record", response_model=None)
def track_record(
    symbol: str | None = None,
    date: str | None = None,
    window_days: int | None = None,
    status: str | None = None,
):
    payload = load_public_research_ledger()
    integrity = verify_public_research_ledger(payload)
    if not integrity.get("ok"):
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error": "integrity_error",
                "integrity": integrity,
                "boundary": BOUNDARY,
            },
        )
    entries = public_ledger_entries(payload)
    if symbol:
        symbol_upper = symbol.upper()
        entries = [
            entry
            for entry in entries
            if str(entry.get("symbol") or "").upper() == symbol_upper
            or f"{entry.get('exchange')}:{entry.get('symbol')}".upper() == symbol_upper
        ]
    if date:
        entries = [entry for entry in entries if str(entry.get("as_of_date") or "") == date]
    if window_days is not None:
        entries = [entry for entry in entries if int(entry.get("window_days") or 0) == window_days]
    if status:
        entries = [entry for entry in entries if str(entry.get("status") or "") == status]
    return {
        "ok": True,
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "count": len(entries),
        "integrity": integrity,
        "filters": {
            "symbol": symbol,
            "date": date,
            "window_days": window_days,
            "status": status,
        },
        "boundary": BOUNDARY,
        "items": entries,
    }


@app.get("/api/track-record/review-coverage", response_model=None)
def track_record_review_coverage():
    payload = load_public_research_ledger()
    integrity = verify_public_research_ledger(payload)
    if not integrity.get("ok"):
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error": "integrity_error",
                "integrity": integrity,
                "boundary": BOUNDARY,
            },
        )
    return {
        "ok": True,
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "integrity": integrity,
        "review_coverage": public_ledger_review_coverage(payload),
        "boundary": BOUNDARY,
    }


@app.get("/api/track-record/{entry_id}", response_model=None)
def track_record_entry(entry_id: str):
    payload = load_public_research_ledger()
    integrity = verify_public_research_ledger(payload)
    if not integrity.get("ok"):
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error": "integrity_error",
                "integrity": integrity,
                "boundary": BOUNDARY,
            },
        )
    for entry in public_ledger_entries(payload):
        if entry.get("entry_id") == entry_id:
            versions = [
                item
                for item in public_ledger_entries(payload)
                if item.get("base_entry_id") == entry.get("base_entry_id")
            ]
            return {
                "ok": True,
                "entry": entry,
                "version_chain": versions,
                **review_status_for_entry(entry, payload),
                "integrity": integrity,
                "boundary": BOUNDARY,
            }
    return JSONResponse(
        status_code=404,
        content={
            "ok": False,
            "error": "ledger_entry_not_found",
            "entry_id": entry_id,
            "boundary": BOUNDARY,
        },
    )
