import argparse
import json
from datetime import date
from pathlib import Path

from scripts import public_stock_pool_report as report_module
from scripts.public_stock_pool_report import (
    build_status,
    build_failure_status,
    exchanges_for_mode,
    exit_code_for_status,
    mark_artifact_write_failure,
    mode_slug,
    normalize_allowed_missing_symbols,
    resolve_exchange_dates,
    target_universe_items,
    write_outputs,
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


def test_morning_hk_uses_previous_completed_hk_session() -> None:
    dates = resolve_exchange_dates(
        mode="morning-hk",
        as_of_date=date(2026, 6, 29),
        trading_date=None,
        us_trading_date=None,
    )

    assert dates.primary_trading_date == date(2026, 6, 26)
    assert dates.hkex_trading_date == date(2026, 6, 26)
    assert dates.nasdaq_trading_date == date(2026, 6, 26)
    assert dates.nyse_trading_date == date(2026, 6, 26)


def test_us_modes_use_previous_completed_us_session() -> None:
    morning = resolve_exchange_dates(
        mode="morning-us",
        as_of_date=date(2026, 6, 29),
        trading_date=None,
        us_trading_date=None,
    )
    evening = resolve_exchange_dates(
        mode="evening-us",
        as_of_date=date(2026, 6, 30),
        trading_date=None,
        us_trading_date=None,
    )

    assert morning.primary_trading_date == date(2026, 6, 26)
    assert morning.nasdaq_trading_date == date(2026, 6, 26)
    assert morning.nyse_trading_date == date(2026, 6, 26)
    assert evening.primary_trading_date == date(2026, 6, 29)
    assert evening.nasdaq_trading_date == date(2026, 6, 29)
    assert evening.nyse_trading_date == date(2026, 6, 29)


def test_modes_select_expected_exchanges() -> None:
    items = [
        {"symbol": "0700", "exchange": "HKEX"},
        {"symbol": "NVDA", "exchange": "NASDAQ"},
        {"symbol": "UBER", "exchange": "NYSE"},
    ]

    assert exchanges_for_mode("morning-hk") == ("HKEX",)
    assert exchanges_for_mode("evening-hk") == ("HKEX",)
    assert exchanges_for_mode("morning-us") == ("NASDAQ", "NYSE")
    assert exchanges_for_mode("evening-us") == ("NASDAQ", "NYSE")
    assert exchanges_for_mode("morning-global") == ("HKEX", "NASDAQ", "NYSE")
    assert [item["symbol"] for item in target_universe_items(items, exchanges_for_mode("morning-hk"))] == ["0700"]
    assert [item["symbol"] for item in target_universe_items(items, exchanges_for_mode("morning-us"))] == ["NVDA", "UBER"]
    assert [item["symbol"] for item in target_universe_items(items, exchanges_for_mode("morning-global"))] == [
        "0700",
        "NVDA",
        "UBER",
    ]


def test_yahoo_ticker_maps_hkex_suffix_only() -> None:
    assert yahoo_ticker("0700", "HKEX") == "0700.HK"
    assert yahoo_ticker("NVDA", "NASDAQ") == "NVDA"
    assert yahoo_ticker("UBER", "NYSE") == "UBER"


def test_fetch_one_retries_transient_provider_failure(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_fetch_yahoo_adjusted_close(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary provider failure")
        return report_module.pd.DataFrame(
            [
                {"date": "2026-06-25", "adj_close": 99.0},
                {"date": "2026-06-26", "adj_close": 100.0},
            ]
        )

    monkeypatch.setattr(report_module, "fetch_yahoo_adjusted_close", fake_fetch_yahoo_adjusted_close)
    dates = resolve_exchange_dates(
        mode="morning-us",
        as_of_date=date(2026, 6, 29),
        trading_date=date(2026, 6, 26),
        us_trading_date=None,
    )

    row = report_module.fetch_one({"symbol": "NVDA", "exchange": "NASDAQ"}, dates, fetch_retries=2)

    assert row["ok"] is True
    assert row["fetch_attempts"] == 2
    assert calls["count"] == 2
    assert row["one_session_change_pct"] == 1.0101


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
    assert status["mode_label"] == "Global summary report"
    assert status["mode_slug"] == "morning_global"
    assert status["target_exchanges"] == ["HKEX", "NASDAQ", "NYSE"]
    assert status["universe_count"] == 3
    assert status["success_count"] == 2
    assert status["failed_count"] == 1
    assert status["data_gap_count"] == 0
    assert status["allowed_missing_symbols"] == []
    assert status["allowed_missing_count"] == 0
    assert status["unexpected_failed_count"] == 1
    assert status["data_gap_symbols"] == []
    assert status["unexpected_failed_symbols"] == [
        {
            "exchange": "NYSE",
            "symbol": "UBER",
            "provider_ticker": "UBER",
            "reason": "missing",
        }
    ]
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
    assert mode_slug("evening-us") == "evening_us"


def test_write_outputs_keeps_mode_specific_and_compatibility_aliases(tmp_path: Path) -> None:
    dates = resolve_exchange_dates(
        mode="morning-us",
        as_of_date=date(2026, 6, 30),
        trading_date=None,
        us_trading_date=None,
    )
    items = [
        {"symbol": "NVDA", "exchange": "NASDAQ"},
        {"symbol": "UBER", "exchange": "NYSE"},
    ]
    results = [
        {
            "ok": True,
            "symbol": "NVDA",
            "exchange": "NASDAQ",
            "provider_ticker": "NVDA",
            "close_date": "2026-06-29",
            "adj_close": 150.0,
            "previous_date": "2026-06-26",
            "previous_adj_close": 149.0,
            "one_session_change_pct": 0.6711,
        },
        {
            "ok": True,
            "symbol": "UBER",
            "exchange": "NYSE",
            "provider_ticker": "UBER",
            "close_date": "2026-06-29",
            "adj_close": 90.0,
            "previous_date": "2026-06-26",
            "previous_adj_close": 91.0,
            "one_session_change_pct": -1.0989,
        },
    ]

    paths = write_outputs(
        report_dir=tmp_path,
        mode="morning-us",
        as_of_date=date(2026, 6, 30),
        exchange_dates=dates,
        items=items,
        results=results,
        fetch_retries=2,
    )

    assert Path(paths["report_path"]).name == "public_stock_pool_morning_us_2026-06-29.md"
    assert Path(paths["latest_path"]).name == "latest_morning_us.md"
    assert Path(paths["status_path"]).name == "status_morning_us.json"
    assert (tmp_path / "latest_morning_us.md").is_file()
    assert (tmp_path / "status_morning_us.json").is_file()
    assert (tmp_path / "latest.md").is_file()
    assert (tmp_path / "status.json").is_file()
    mode_status = json.loads((tmp_path / "status_morning_us.json").read_text(encoding="utf-8"))
    compat_status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert mode_status == compat_status
    assert mode_status["mode"] == "morning-us"
    assert mode_status["target_exchanges"] == ["NASDAQ", "NYSE"]
    assert mode_status["fetch_retries"] == 2
    assert mode_status["status_file"] == "status_morning_us.json"
    assert mode_status["compat_status_file"] == "status.json"


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


def test_allowed_provider_gap_records_data_gap_and_exits_zero() -> None:
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
    assert status["data_gap_count"] == 1
    assert status["allowed_missing_symbols"] == ["0501.HK", "HKEX:0501"]
    assert status["allowed_missing_count"] == 1
    assert status["unexpected_failed_count"] == 0
    assert status["data_gap_symbols"] == [
        {
            "exchange": "HKEX",
            "symbol": "0501",
            "provider_ticker": "0501.HK",
            "reason": "empty_price_frame",
        }
    ]
    assert status["unexpected_failed_symbols"] == []
    assert status["failed_symbols"][0]["reason"] == "empty_price_frame"
    assert status["exit_status"] == 0
    assert exit_code_for_status(status) == 0


def test_us_evening_allowed_cwan_close_gap_exits_zero() -> None:
    dates = resolve_exchange_dates(
        mode="evening-us",
        as_of_date=date(2026, 6, 30),
        trading_date=date(2026, 6, 29),
        us_trading_date=None,
    )
    items = [
        {"symbol": "CWAN", "exchange": "NYSE"},
        {"symbol": "NVDA", "exchange": "NASDAQ"},
    ]
    results = [
        {
            "ok": False,
            "symbol": "CWAN",
            "exchange": "NYSE",
            "provider_ticker": "CWAN",
            "reason": "trading_date_close_missing",
            "close_date": "2026-06-29",
        },
        {"ok": True, "symbol": "NVDA", "exchange": "NASDAQ", "provider_ticker": "NVDA"},
    ]

    status = build_status(
        mode="evening-us",
        as_of_date=date(2026, 6, 30),
        exchange_dates=dates,
        items=items,
        results=results,
        report_path=Path("public_stock_pool_evening_us_2026-06-29.md"),
        latest_path=Path("latest_evening_us.md"),
        status_path=Path("status_evening_us.json"),
        allowed_missing_symbols=normalize_allowed_missing_symbols(["NYSE:CWAN"]),
    )

    assert status["run_status"] == "completed_with_allowed_data_gaps"
    assert status["exit_status"] == 0
    assert status["data_gap_count"] == 1
    assert status["unexpected_failed_count"] == 0
    assert status["data_gap_symbols"] == [
        {
            "exchange": "NYSE",
            "symbol": "CWAN",
            "provider_ticker": "CWAN",
            "reason": "trading_date_close_missing",
        }
    ]


def test_global_summary_allows_hkex_and_us_provider_gaps() -> None:
    dates = resolve_exchange_dates(
        mode="morning-global",
        as_of_date=date(2026, 7, 3),
        trading_date=date(2026, 7, 2),
        us_trading_date=None,
    )
    items = [
        {"symbol": "0501", "exchange": "HKEX"},
        {"symbol": "CWAN", "exchange": "NYSE"},
        {"symbol": "NVDA", "exchange": "NASDAQ"},
    ]
    results = [
        {
            "ok": False,
            "symbol": "0501",
            "exchange": "HKEX",
            "provider_ticker": "0501.HK",
            "reason": "empty_price_frame",
            "close_date": "2026-07-02",
        },
        {
            "ok": False,
            "symbol": "CWAN",
            "exchange": "NYSE",
            "provider_ticker": "CWAN",
            "reason": "trading_date_close_missing",
            "close_date": "2026-07-02",
        },
        {"ok": True, "symbol": "NVDA", "exchange": "NASDAQ", "provider_ticker": "NVDA"},
    ]

    status = build_status(
        mode="morning-global",
        as_of_date=date(2026, 7, 3),
        exchange_dates=dates,
        items=items,
        results=results,
        report_path=Path("public_stock_pool_morning_global_2026-07-02.md"),
        latest_path=Path("latest_morning_global.md"),
        status_path=Path("status_morning_global.json"),
        allowed_missing_symbols=normalize_allowed_missing_symbols(["HKEX:0501", "NYSE:CWAN"]),
    )

    assert status["run_status"] == "completed_with_allowed_data_gaps"
    assert status["failed_count"] == 2
    assert status["data_gap_count"] == 2
    assert status["allowed_missing_count"] == 2
    assert status["unexpected_failed_count"] == 0
    assert status["data_gap_symbols"] == [
        {
            "exchange": "HKEX",
            "symbol": "0501",
            "provider_ticker": "0501.HK",
            "reason": "empty_price_frame",
        },
        {
            "exchange": "NYSE",
            "symbol": "CWAN",
            "provider_ticker": "CWAN",
            "reason": "trading_date_close_missing",
        },
    ]
    assert status["unexpected_failed_symbols"] == []
    assert status["exit_status"] == 0


def test_allowed_data_gap_markdown_is_publicly_explicit(tmp_path: Path) -> None:
    dates = resolve_exchange_dates(
        mode="evening-us",
        as_of_date=date(2026, 6, 30),
        trading_date=date(2026, 6, 29),
        us_trading_date=None,
    )
    items = [{"symbol": "CWAN", "exchange": "NYSE"}]
    results = [
        {
            "ok": False,
            "symbol": "CWAN",
            "exchange": "NYSE",
            "provider_ticker": "CWAN",
            "reason": "trading_date_close_missing",
            "close_date": "2026-06-29",
        }
    ]

    paths = write_outputs(
        report_dir=tmp_path,
        mode="evening-us",
        as_of_date=date(2026, 6, 30),
        exchange_dates=dates,
        items=items,
        results=results,
        allowed_missing_symbols=normalize_allowed_missing_symbols(["NYSE:CWAN"]),
    )

    status = paths["status"]
    markdown = Path(paths["latest_path"]).read_text(encoding="utf-8")
    assert status["run_status"] == "completed_with_allowed_data_gaps"
    assert "## Allowed Data Gaps" in markdown
    assert "- run_status: completed_with_allowed_data_gaps" in markdown
    assert "| NYSE | CWAN | CWAN | trading_date_close_missing |" in markdown


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
    assert status["data_gap_count"] == 0
    assert status["allowed_missing_count"] == 0
    assert status["unexpected_failed_count"] == 1
    assert status["data_gap_symbols"] == []
    assert status["unexpected_failed_symbols"] == [
        {
            "exchange": "NYSE",
            "symbol": "UBER",
            "provider_ticker": "UBER",
            "reason": "empty_price_frame",
        }
    ]
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
    assert status["data_gap_symbols"] == []
    assert status["unexpected_failed_symbols"] == []


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
