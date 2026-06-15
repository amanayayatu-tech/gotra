"""SQLite-backed state ledger for concurrent Phase BT runs."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import uuid4

from gotra.backtest.budget import BudgetExceeded


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProviderCall:
    call_id: str
    worker_id: str
    arm: str
    ticker: str
    decision_date: str
    cache_key: str
    status: str
    started_at: str
    finished_at: str
    elapsed_ms: int
    estimated_tokens: int
    error_type: str = ""
    attempt: int = 0


class SQLiteLedger:
    """Small transactional ledger used by parallel BT workers."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        cache_namespace: str = "",
        namespace: str | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not run_id.strip():
            raise ValueError("run_id is required")
        self.path = Path(path)
        self.run_id = run_id
        self.cache_namespace = (cache_namespace if namespace is None else namespace).strip()
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._ensure_budget_row(max_tokens=max_tokens)

    @property
    def decision_cache(self) -> SQLiteDecisionCache:
        return SQLiteDecisionCache(self)

    @property
    def budget(self) -> SQLiteLedger:
        return self

    @property
    def namespace(self) -> str:
        return self.cache_namespace

    def journal_mode(self) -> str:
        with self._connect() as conn:
            row = conn.execute("pragma journal_mode").fetchone()
        return str(row[0]).lower()

    def cache_get(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select payload_json from decision_cache where cache_key = ?",
                (self._cache_key(key),),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return payload if isinstance(payload, dict) else None

    def get_decision_cache(self, key: str) -> dict[str, Any] | None:
        return self.cache_get(key)

    def cache_set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        prompt_hash: str = "",
        arm: str = "",
        ticker: str = "",
        decision_date: str = "",
        token_usage: dict[str, Any] | None = None,
    ) -> None:
        now = _now()
        with self._transaction() as conn:
            conn.execute(
                """
                insert into decision_cache (
                    cache_key, namespace, prompt_hash, arm, ticker, decision_date,
                    payload_json, token_usage_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(cache_key) do update set
                    namespace = excluded.namespace,
                    prompt_hash = excluded.prompt_hash,
                    arm = excluded.arm,
                    ticker = excluded.ticker,
                    decision_date = excluded.decision_date,
                    payload_json = excluded.payload_json,
                    token_usage_json = excluded.token_usage_json,
                    updated_at = excluded.updated_at
                """,
                (
                    self._cache_key(key),
                    self.cache_namespace,
                    prompt_hash,
                    arm,
                    ticker,
                    decision_date,
                    json.dumps(value, ensure_ascii=False, sort_keys=True),
                    json.dumps(token_usage or {}, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )

    def set_decision_cache(
        self,
        key: str,
        value: dict[str, Any],
        *,
        prompt_hash: str = "",
        arm: str = "",
        ticker: str = "",
        decision_date: str = "",
        token_usage: dict[str, Any] | None = None,
    ) -> None:
        self.cache_set(
            key,
            value,
            prompt_hash=prompt_hash,
            arm=arm,
            ticker=ticker,
            decision_date=decision_date,
            token_usage=token_usage,
        )

    def list_decision_cache(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select namespace, cache_key, prompt_hash, arm, ticker, decision_date,
                       payload_json, token_usage_json, created_at, updated_at
                from decision_cache
                where namespace = ?
                order by cache_key
                """,
                (self.cache_namespace,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = _row_to_dict(row)
            item["payload"] = json.loads(str(row["payload_json"]))
            item["token_usage"] = json.loads(str(row["token_usage_json"]))
            result.append(item)
        return result

    def charge(
        self,
        *,
        cache_key: str,
        estimated_tokens: int,
        cache_hit: bool,
        allow_overage: bool = False,
    ) -> None:
        del cache_key
        tokens = max(0, int(estimated_tokens))
        with self._transaction() as conn:
            row = self._budget_row(conn)
            spent = int(row["spent_tokens"])
            max_tokens = row["max_tokens"]
            max_tokens = int(max_tokens) if max_tokens is not None else None
            if cache_hit:
                conn.execute(
                    "update budget set cache_hits = cache_hits + 1, updated_at = ? where run_id = ?",
                    (_now(), self.run_id),
                )
                return

            proposed = spent + tokens
            if max_tokens is not None and proposed > max_tokens and not allow_overage:
                raise BudgetExceeded(
                    f"BT token budget exceeded: proposed={proposed}, max={max_tokens}"
                )
            over_budget_error = ""
            if max_tokens is not None and proposed > max_tokens:
                over_budget_error = (
                    f"BT token budget exceeded: proposed={proposed}, max={max_tokens}"
                )
            conn.execute(
                """
                update budget
                set spent_tokens = ?, cache_misses = cache_misses + 1,
                    over_budget_error = ?, updated_at = ?
                where run_id = ?
                """,
                (proposed, over_budget_error, _now(), self.run_id),
            )

    def preflight(self, *, estimated_tokens: int) -> None:
        tokens = max(0, int(estimated_tokens))
        with self._transaction() as conn:
            row = self._budget_row(conn)
            max_tokens = row["max_tokens"]
            if max_tokens is None:
                return
            proposed = int(row["spent_tokens"]) + tokens
            if proposed > int(max_tokens):
                raise BudgetExceeded(
                    f"BT token budget exceeded: proposed={proposed}, max={int(max_tokens)}"
                )

    @property
    def over_budget_error(self) -> str:
        return str(self.snapshot().get("over_budget_error") or "")

    def snapshot(self) -> dict[str, int | str | bool | None]:
        with self._connect() as conn:
            row = self._budget_row(conn)
        error = str(row["over_budget_error"] or "")
        return {
            "max_tokens": row["max_tokens"],
            "spent_tokens": int(row["spent_tokens"]),
            "cache_hits": int(row["cache_hits"]),
            "cache_misses": int(row["cache_misses"]),
            "over_budget": bool(error),
            "over_budget_error": error,
        }

    def record_provider_call(
        self,
        call: ProviderCall | None = None,
        *,
        call_id: str | None = None,
        worker_id: str = "",
        arm: str = "",
        ticker: str = "",
        decision_date: str = "",
        cache_key: str = "",
        status: str = "started",
        started_at: str = "",
        finished_at: str = "",
        elapsed_ms: int = 0,
        estimated_tokens: int = 0,
        error_type: str = "",
        attempt: int = 0,
    ) -> str:
        active_call = call or ProviderCall(
            call_id=call_id or str(uuid4()),
            worker_id=worker_id,
            arm=arm,
            ticker=ticker,
            decision_date=decision_date,
            cache_key=cache_key,
            status=status,
            started_at=started_at or _now(),
            finished_at=finished_at,
            elapsed_ms=elapsed_ms,
            estimated_tokens=estimated_tokens,
            error_type=error_type,
            attempt=attempt,
        )
        with self._transaction() as conn:
            conn.execute(
                """
                insert or replace into provider_calls (
                    call_id, run_id, worker_id, arm, ticker, decision_date, cache_key,
                    started_at, finished_at, elapsed_ms, status, estimated_tokens,
                    error_type, attempt
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    active_call.call_id,
                    self.run_id,
                    active_call.worker_id,
                    active_call.arm,
                    active_call.ticker,
                    active_call.decision_date,
                    self._cache_key(active_call.cache_key),
                    active_call.started_at,
                    active_call.finished_at,
                    int(active_call.elapsed_ms),
                    active_call.status,
                    int(active_call.estimated_tokens),
                    active_call.error_type,
                    int(active_call.attempt),
                ),
            )
        return active_call.call_id

    def start_provider_call(self, **kwargs: Any) -> str:
        return self.record_provider_call(status="started", started_at=_now(), **kwargs)

    def finish_provider_call(
        self,
        call_id: str,
        *,
        status: str,
        elapsed_ms: int = 0,
        error_type: str = "",
        finished_at: str = "",
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                update provider_calls
                set finished_at = ?, elapsed_ms = ?, status = ?, error_type = ?
                where call_id = ? and run_id = ?
                """,
                (finished_at or _now(), int(elapsed_ms), status, error_type, call_id, self.run_id),
            )

    def list_provider_calls(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from provider_calls
                where run_id = ?
                order by started_at, call_id
                """,
                (self.run_id,),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def record_step(
        self,
        *,
        step_id: str,
        step_index: int,
        arm: str,
        ticker: str,
        decision_date: str,
        status: str,
        step_path: str,
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                insert or replace into steps (
                    step_id, run_id, step_index, arm, ticker, decision_date,
                    status, step_path, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    self.run_id,
                    int(step_index),
                    arm,
                    ticker,
                    decision_date,
                    status,
                    step_path,
                    _now(),
                ),
            )

    def register_step(
        self,
        *,
        step_index: int,
        arm: str,
        ticker: str,
        decision_date: str,
        status: str,
        step_path: str = "",
        step_id: str | None = None,
    ) -> str:
        active_step_id = (
            step_id or f"{self.run_id}:{int(step_index)}:{arm}:{ticker}:{decision_date}"
        )
        self.record_step(
            step_id=active_step_id,
            step_index=step_index,
            arm=arm,
            ticker=ticker,
            decision_date=decision_date,
            status=status,
            step_path=step_path,
        )
        return active_step_id

    def list_steps(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from steps
                where run_id = ?
                order by step_index, arm, ticker, decision_date
                """,
                (self.run_id,),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def set_run_flag(self, *, abort_reason: str = "", paused_reason: str = "") -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                insert into run_flags (run_id, abort_reason, paused_reason, updated_at)
                values (?, ?, ?, ?)
                on conflict(run_id) do update set
                    abort_reason = excluded.abort_reason,
                    paused_reason = excluded.paused_reason,
                    updated_at = excluded.updated_at
                """,
                (self.run_id, abort_reason, paused_reason, _now()),
            )

    def set_run_flags(self, *, abort_reason: str = "", paused_reason: str = "") -> None:
        self.set_run_flag(abort_reason=abort_reason, paused_reason=paused_reason)

    def get_run_flags(self) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select run_id, abort_reason, paused_reason, updated_at
                from run_flags
                where run_id = ?
                """,
                (self.run_id,),
            ).fetchone()
        if row is None:
            return {
                "run_id": self.run_id,
                "abort_reason": "",
                "paused_reason": "",
                "updated_at": "",
            }
        return {key: str(row[key] or "") for key in row.keys()}

    def _cache_key(self, key: str) -> str:
        if not self.cache_namespace:
            return key
        return f"{self.cache_namespace}:{key}"

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                pragma journal_mode = wal;
                pragma foreign_keys = on;
                create table if not exists meta (
                    key text primary key,
                    value text not null
                );
                insert into meta (key, value)
                    values ('schema_version', '1')
                    on conflict(key) do nothing;
                create table if not exists decision_cache (
                    cache_key text primary key,
                    namespace text not null default '',
                    prompt_hash text not null default '',
                    arm text not null default '',
                    ticker text not null default '',
                    decision_date text not null default '',
                    payload_json text not null,
                    token_usage_json text not null default '{}',
                    created_at text not null,
                    updated_at text not null
                );
                create table if not exists budget (
                    run_id text primary key,
                    max_tokens integer,
                    spent_tokens integer not null default 0,
                    cache_hits integer not null default 0,
                    cache_misses integer not null default 0,
                    over_budget_error text not null default '',
                    updated_at text not null
                );
                create table if not exists provider_calls (
                    call_id text primary key,
                    run_id text not null,
                    worker_id text not null,
                    arm text not null,
                    ticker text not null,
                    decision_date text not null,
                    cache_key text not null,
                    started_at text not null,
                    finished_at text not null,
                    elapsed_ms integer not null,
                    status text not null,
                    estimated_tokens integer not null,
                    error_type text not null default '',
                    attempt integer not null default 0
                );
                create index if not exists provider_calls_run_idx
                    on provider_calls(run_id, arm, ticker, decision_date);
                create table if not exists steps (
                    step_id text primary key,
                    run_id text not null,
                    step_index integer not null,
                    arm text not null,
                    ticker text not null,
                    decision_date text not null,
                    status text not null,
                    step_path text not null,
                    created_at text not null
                );
                create index if not exists steps_run_idx
                    on steps(run_id, step_index);
                create table if not exists run_flags (
                    run_id text primary key,
                    abort_reason text not null default '',
                    paused_reason text not null default '',
                    updated_at text not null
                );
                """
            )

    def _ensure_budget_row(self, *, max_tokens: int | None) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                insert into budget (run_id, max_tokens, updated_at)
                values (?, ?, ?)
                on conflict(run_id) do update set
                    max_tokens = coalesce(excluded.max_tokens, budget.max_tokens),
                    updated_at = excluded.updated_at
                """,
                (self.run_id, max_tokens, _now()),
            )

    def _budget_row(self, conn: sqlite3.Connection) -> sqlite3.Row:
        row = conn.execute("select * from budget where run_id = ?", (self.run_id,)).fetchone()
        if row is None:
            conn.execute(
                "insert into budget (run_id, max_tokens, updated_at) values (?, ?, ?)",
                (self.run_id, self.max_tokens, _now()),
            )
            row = conn.execute("select * from budget where run_id = ?", (self.run_id,)).fetchone()
        assert row is not None
        return row

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=self.timeout_seconds, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma journal_mode = wal")
        conn.execute("pragma foreign_keys = on")
        conn.execute(f"pragma busy_timeout = {int(self.timeout_seconds * 1000)}")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()


class SQLiteDecisionCache:
    """Compatibility adapter for existing DecisionProvider cache calls."""

    def __init__(self, ledger: SQLiteLedger) -> None:
        self.ledger = ledger

    def get(self, key: str) -> dict[str, Any] | None:
        return self.ledger.cache_get(key)

    def set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        prompt_hash: str = "",
        arm: str = "",
        ticker: str = "",
        decision_date: str = "",
        token_usage: dict[str, Any] | None = None,
    ) -> None:
        self.ledger.cache_set(
            key,
            value,
            prompt_hash=prompt_hash,
            arm=arm,
            ticker=ticker,
            decision_date=decision_date,
            token_usage=token_usage,
        )


SQLiteDecisionLedger = SQLiteLedger


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _now() -> str:
    return datetime.now(UTC).isoformat()
