"""Planning and execution helpers for Phase BT parallel runs."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable, TypeVar

from gotra.backtest.protocol import TickerSpec


T = TypeVar("T")


@dataclass(frozen=True)
class StepTask:
    step_index: int
    ticker: TickerSpec
    decision_date: date
    arm: str

    @property
    def step_id(self) -> str:
        return f"{self.step_index:06d}:{self.decision_date.isoformat()}:{self.ticker.symbol}:{self.arm}"


def stable_step_plan(
    *,
    tickers: Iterable[TickerSpec],
    decision_dates: Iterable[date],
    arms: Iterable[str],
    max_steps: int | None = None,
) -> list[StepTask]:
    """Return deterministic step tasks in existing serial runner order."""

    normalized_arms = tuple(dict.fromkeys(str(arm) for arm in arms))
    ordered_tickers = tuple(tickers)
    ordered_decision_dates = tuple(decision_dates)
    tasks: list[StepTask] = []
    step_index = 1
    for decision_date in ordered_decision_dates:
        for ticker in ordered_tickers:
            if decision_date < ticker.listing_date:
                continue
            if max_steps is not None and len(tasks) >= max_steps:
                return tasks
            for arm in normalized_arms:
                if max_steps is not None and len(tasks) >= max_steps:
                    return tasks
                tasks.append(
                    StepTask(
                        step_index=step_index,
                        ticker=ticker,
                        decision_date=decision_date,
                        arm=arm,
                    )
                )
                step_index += 1
    return tasks


def run_independent_tasks(
    tasks: list[StepTask],
    worker: Callable[[StepTask], T],
    *,
    max_workers: int,
) -> list[T]:
    """Run independent tasks concurrently and return results in step-plan order."""

    if max_workers <= 1:
        return [worker(task) for task in tasks]
    results: dict[int, T] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_index: dict[Future[T], int] = {
            executor.submit(worker, task): task.step_index for task in tasks
        }
        for future in as_completed(future_by_index):
            results[future_by_index[future]] = future.result()
    return [results[task.step_index] for task in tasks]


def run_ticker_chains(
    tasks: list[StepTask],
    worker: Callable[[StepTask], T],
    *,
    max_workers: int,
) -> list[T]:
    """Run one sequential chain per ticker, with different tickers concurrent."""

    chains: dict[str, list[StepTask]] = defaultdict(list)
    for task in tasks:
        chains[task.ticker.symbol].append(task)
    ordered_chains = [
        sorted(chain, key=lambda item: (item.decision_date, item.step_index))
        for _ticker, chain in sorted(chains.items())
    ]

    def run_chain(chain: list[StepTask]) -> list[T]:
        return [worker(task) for task in chain]

    by_index: dict[int, T] = {}
    if max_workers <= 1:
        for chain in ordered_chains:
            for task, result in zip(chain, run_chain(chain), strict=True):
                by_index[task.step_index] = result
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_chain, chain): chain for chain in ordered_chains}
            for future in as_completed(futures):
                chain = futures[future]
                for task, result in zip(chain, future.result(), strict=True):
                    by_index[task.step_index] = result
    return [by_index[task.step_index] for task in tasks]
