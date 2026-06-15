from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from gotra.backtest.budget import BudgetExceeded
from gotra.backtest.ledger import (
    ProviderCall,
    SQLiteDecisionCache,
    SQLiteDecisionLedger,
    SQLiteLedger,
)


def test_sqlite_ledger_initializes_wal_and_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    ledger = SQLiteLedger(db_path, run_id="run", max_tokens=100)

    assert ledger.journal_mode() == "wal"
    assert ledger.snapshot()["max_tokens"] == 100
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }

    assert {"decision_cache", "budget", "provider_calls", "steps", "run_flags"} <= tables


def test_sqlite_ledger_cache_and_budget(tmp_path: Path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite", run_id="run", cache_namespace="ns", max_tokens=100)
    cache = SQLiteDecisionCache(ledger)

    assert cache.get("key") is None
    cache.set("key", {"direction": "long", "expected_change_pct": 1})
    assert cache.get("key") == {"direction": "long", "expected_change_pct": 1}

    ledger.charge(cache_key="key", estimated_tokens=20, cache_hit=False)
    ledger.charge(cache_key="key", estimated_tokens=20, cache_hit=True)
    assert ledger.snapshot()["spent_tokens"] == 20
    assert ledger.snapshot()["cache_hits"] == 1
    assert ledger.snapshot()["cache_misses"] == 1


def test_sqlite_ledger_namespace_and_run_id_isolation(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    alpha = SQLiteDecisionLedger(db_path, run_id="run-a", namespace="alpha", max_tokens=100)
    alpha_same_namespace = SQLiteLedger(db_path, run_id="run-b", cache_namespace="alpha")
    beta = SQLiteLedger(db_path, run_id="run-c", cache_namespace="beta", max_tokens=50)

    alpha.decision_cache.set(
        "decision",
        {"direction": "long"},
        prompt_hash="prompt-hash",
        arm="baseline",
        ticker="AAPL",
        decision_date="2020-01-01",
        token_usage={"total_tokens": 12},
    )
    beta.decision_cache.set("decision", {"direction": "short"})
    alpha.budget.charge(cache_key="decision", estimated_tokens=10, cache_hit=False)
    beta.budget.charge(cache_key="decision", estimated_tokens=3, cache_hit=False)

    assert alpha_same_namespace.decision_cache.get("decision") == {"direction": "long"}
    assert beta.decision_cache.get("decision") == {"direction": "short"}
    assert alpha.budget.snapshot()["spent_tokens"] == 10
    assert beta.budget.snapshot()["spent_tokens"] == 3
    rows = alpha.list_decision_cache()
    assert rows[0]["namespace"] == "alpha"
    assert rows[0]["prompt_hash"] == "prompt-hash"
    assert rows[0]["token_usage_json"] == '{"total_tokens": 12}'


def test_sqlite_ledger_budget_overage(tmp_path: Path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite", run_id="run", max_tokens=10)

    ledger.preflight(estimated_tokens=10)
    with pytest.raises(BudgetExceeded):
        ledger.preflight(estimated_tokens=11)
    with pytest.raises(BudgetExceeded):
        ledger.charge(cache_key="a", estimated_tokens=11, cache_hit=False)
    assert ledger.snapshot()["spent_tokens"] == 0

    ledger.charge(cache_key="a", estimated_tokens=11, cache_hit=False, allow_overage=True)
    assert ledger.snapshot()["spent_tokens"] == 11
    assert ledger.snapshot()["over_budget"] is True
    assert "token budget exceeded" in str(ledger.snapshot()["over_budget_error"]).lower()


def test_sqlite_ledger_concurrent_budget_charges_are_atomic(tmp_path: Path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite", run_id="run", max_tokens=10_000)

    def charge(_index: int) -> None:
        ledger.charge(cache_key="k", estimated_tokens=1, cache_hit=False)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(charge, range(200)))

    snapshot = ledger.snapshot()
    assert snapshot["spent_tokens"] == 200
    assert snapshot["cache_misses"] == 200


def test_sqlite_ledger_concurrent_cache_and_budget_writes_are_atomic(tmp_path: Path) -> None:
    ledger = SQLiteLedger(
        tmp_path / "ledger.sqlite",
        run_id="run",
        cache_namespace="race",
        max_tokens=10_000,
    )

    def write(index: int) -> dict[str, int] | None:
        cache_key = f"k-{index}"
        ledger.charge(cache_key=cache_key, estimated_tokens=1, cache_hit=False)
        ledger.decision_cache.set(cache_key, {"index": index})
        return ledger.decision_cache.get(cache_key)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(write, range(80)))

    assert sorted(result["index"] for result in results if result is not None) == list(range(80))
    assert ledger.snapshot()["spent_tokens"] == 80
    assert ledger.snapshot()["cache_misses"] == 80
    assert len(ledger.list_decision_cache()) == 80


def test_sqlite_ledger_records_provider_calls_and_steps(tmp_path: Path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite", run_id="run")
    ledger.record_provider_call(
        ProviderCall(
            call_id="call-1",
            worker_id="worker-1",
            arm="baseline",
            ticker="AAPL",
            decision_date="2020-01-01",
            cache_key="cache",
            status="ok",
            started_at="2020-01-01T00:00:00+00:00",
            finished_at="2020-01-01T00:00:01+00:00",
            elapsed_ms=1000,
            estimated_tokens=123,
        )
    )
    ledger.record_step(
        step_id="step-1",
        step_index=1,
        arm="baseline",
        ticker="AAPL",
        decision_date="2020-01-01",
        status="scored",
        step_path="baseline/step_2020-01-01_AAPL.json",
    )
    ledger.set_run_flag(abort_reason="", paused_reason="budget")
    registered_step_id = ledger.register_step(
        step_index=2,
        arm="alaya",
        ticker="MSFT",
        decision_date="2020-02-01",
        status="planned",
        step_path="alaya/step_2020-02-01_MSFT.json",
    )
    call_id = ledger.start_provider_call(
        worker_id="worker-2",
        arm="alaya",
        ticker="MSFT",
        decision_date="2020-02-01",
        cache_key="cache-2",
        estimated_tokens=456,
    )
    ledger.finish_provider_call(call_id, status="ok", elapsed_ms=250)

    assert (tmp_path / "ledger.sqlite").exists()
    assert ledger.get_run_flags()["paused_reason"] == "budget"
    assert [step["step_id"] for step in ledger.list_steps()] == ["step-1", registered_step_id]
    assert [call["status"] for call in ledger.list_provider_calls()] == ["ok", "ok"]
    with sqlite3.connect(tmp_path / "ledger.sqlite") as conn:
        assert conn.execute("pragma journal_mode").fetchone()[0] == "wal"
