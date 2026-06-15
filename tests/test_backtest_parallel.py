from __future__ import annotations

from collections import defaultdict
from datetime import date
import threading
import time

from gotra.backtest.parallel import run_independent_tasks, run_ticker_chains, stable_step_plan
from gotra.backtest.protocol import TickerSpec


def test_stable_step_plan_uses_serial_order() -> None:
    tasks = stable_step_plan(
        tickers=(
            TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
            TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),
        ),
        decision_dates=(date(2020, 1, 1), date(2020, 2, 1)),
        arms=("baseline", "alaya"),
    )

    assert [
        (task.step_index, task.ticker.symbol, task.decision_date.isoformat(), task.arm)
        for task in tasks
    ] == [
        (1, "AAPL", "2020-01-01", "baseline"),
        (2, "AAPL", "2020-01-01", "alaya"),
        (3, "MSFT", "2020-01-01", "baseline"),
        (4, "MSFT", "2020-01-01", "alaya"),
        (5, "AAPL", "2020-02-01", "baseline"),
        (6, "AAPL", "2020-02-01", "alaya"),
        (7, "MSFT", "2020-02-01", "baseline"),
        (8, "MSFT", "2020-02-01", "alaya"),
    ]


def test_independent_tasks_run_concurrently_and_return_plan_order() -> None:
    tasks = stable_step_plan(
        tickers=(
            TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
            TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),
        ),
        decision_dates=(date(2020, 1, 1), date(2020, 2, 1)),
        arms=("baseline",),
    )

    started = time.perf_counter()
    results = run_independent_tasks(
        tasks,
        lambda task: _sleep_result(task.step_index),
        max_workers=4,
    )
    elapsed = time.perf_counter() - started

    assert results == [1, 2, 3, 4]
    assert elapsed < 0.18


def test_ticker_chains_preserve_same_ticker_order_but_overlap_tickers() -> None:
    tasks = stable_step_plan(
        tickers=(
            TickerSpec("AAPL", "Apple", date(1980, 12, 12)),
            TickerSpec("MSFT", "Microsoft", date(1986, 3, 13)),
        ),
        decision_dates=(date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)),
        arms=("alaya",),
    )
    active_by_ticker: dict[str, int] = defaultdict(int)
    max_active_total = 0
    lock = threading.Lock()
    seen_by_ticker: dict[str, list[int]] = defaultdict(list)

    def worker(task):
        nonlocal max_active_total
        with lock:
            active_by_ticker[task.ticker.symbol] += 1
            assert active_by_ticker[task.ticker.symbol] == 1
            max_active_total = max(max_active_total, sum(active_by_ticker.values()))
        time.sleep(0.04)
        with lock:
            seen_by_ticker[task.ticker.symbol].append(task.step_index)
            active_by_ticker[task.ticker.symbol] -= 1
        return task.step_index

    results = run_ticker_chains(tasks, worker, max_workers=2)

    assert results == [task.step_index for task in tasks]
    assert max_active_total > 1
    assert seen_by_ticker["AAPL"] == [1, 3, 5]
    assert seen_by_ticker["MSFT"] == [2, 4, 6]


def _sleep_result(value: int) -> int:
    time.sleep(0.05)
    return value
