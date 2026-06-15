"""Quarterly-first Phase BT walk-forward runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

import pandas as pd

from gotra.backtest.audit import audit_run
from gotra.backtest.budget import BudgetExceeded, TokenBudget, estimate_tokens
from gotra.backtest.ledger import ProviderCall, SQLiteDecisionCache, SQLiteLedger
from gotra.backtest.parallel import StepTask, run_independent_tasks, run_ticker_chains, stable_step_plan
from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import (
    DEFAULT_END,
    DEFAULT_START,
    SAMPLED_STEP_MONTHS,
    WINDOW_DAYS,
    TickerSpec,
    decision_dates,
    parse_date,
    selected_universe,
    style_window_for,
    ticker_slug,
)
from gotra.backtest.report import write_backtest_report
from gotra.backtest.statistics import summarize_steps


Arm = Literal["baseline", "alaya"]
ProviderName = Literal["heuristic", "codex_cli"]
RunMode = Literal["sampled", "full"]
LedgerBackend = Literal["json", "sqlite"]
ParallelMode = Literal["off", "baseline", "ticker-chains", "both"]
SAMPLED_PROMPT_VERSION = "bt-sampled-v1"
FULL_PROMPT_VERSION = "bt-full-v1"
BT_CODEX_SYSTEM_PROMPT = """You are the Gotra Phase BT gpt-5.5 xhigh decision provider.

Use only the JSON user prompt. Do not use web search, Perplexity, external APIs, files outside the
prompt, or live market data. Treat the prompt as a compact F/W/G + Chairman workflow:
- F partner: identify fundamental and valuation implications from the provided price history only.
- W partner: identify market psychology and momentum implications from the provided price history only.
- G partner: identify governance and risk implications from the provided price history only.
- Chairman: reconcile F/W/G into one 30-day expected price-change decision.

Both experimental arms share this exact skeleton. The only stateful signal is the feedback array:
empty feedback means no cognitive-compounding state; non-empty feedback means only matured prior
outcomes whose availability date is not after the decision date.

Return strict JSON only, with exactly these keys:
{"direction": "long|short|watch|avoid", "expected_change_pct": number, "confidence": number,
"reasoning": "brief reason"}
"""
_EVENT_WRITE_LOCK = threading.Lock()
_STEP_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class BacktestConfig:
    data_dir: Path = Path("data/backtest")
    run_id: str = ""
    mode: RunMode = "sampled"
    provider: ProviderName = "heuristic"
    start: date = DEFAULT_START
    end: date = DEFAULT_END
    step_months: int = SAMPLED_STEP_MONTHS
    tickers: tuple[TickerSpec, ...] = selected_universe()
    window_days: int = WINDOW_DAYS
    token_budget: int | None = None
    max_steps: int | None = None
    arms: tuple[Arm, ...] = ("baseline", "alaya")
    cache_namespace: str = ""
    provider_preflight: bool = True
    provider_error_abort_consecutive: int = 8
    provider_error_abort_rate: float = 0.10
    require_stage3_provider: bool = False
    ledger: LedgerBackend = "json"
    ledger_path: Path | None = None
    provider_concurrency: int = 1
    parallel_mode: ParallelMode = "off"
    resume: bool = False


@dataclass(frozen=True)
class Decision:
    direction: str
    expected_change_pct: float
    confidence: float
    reasoning: str
    prompt_hash: str
    estimated_tokens: int
    token_usage_source: str
    cache_hit: bool


class CompletionClient(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        timeout_seconds: int,
        temperature: float,
    ) -> Any:
        """Return provider text or a provider response object."""


class DecisionProvider(Protocol):
    network_enabled: bool

    def decide(
        self,
        *,
        ticker: str,
        arm: Arm,
        decision_date: date,
        price_rows: pd.DataFrame,
        feedback: list[dict[str, Any]],
        cache: "DecisionCache",
        budget: TokenBudget,
    ) -> Decision:
        """Return one BT decision."""


class ProviderError(RuntimeError):
    """A provider produced no valid decision for a step."""

    def __init__(
        self,
        message: str,
        *,
        prompt_hash: str = "",
        estimated_tokens: int = 0,
    ) -> None:
        super().__init__(message)
        self.prompt_hash = prompt_hash
        self.estimated_tokens = estimated_tokens


class DecisionCache:
    def __init__(self, path: Path, *, namespace: str = "") -> None:
        self.path = path
        self.namespace = namespace.strip()
        self.values = self._load()

    def get(self, key: str) -> dict[str, Any] | None:
        value = self.values.get(self._key(key))
        return dict(value) if isinstance(value, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.values[self._key(key)] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, indent=2, sort_keys=True), encoding="utf-8")

    def _key(self, key: str) -> str:
        if not self.namespace:
            return key
        return f"{self.namespace}:{key}"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))


class HeuristicDecisionProvider:
    """Deterministic provider for sampled correctness validation.

    This provider is intentionally local and non-networked. It validates the Phase BT
    cache/audit/budget/report chain without claiming to prove the preregistered LLM hypothesis.
    """

    network_enabled = False

    def decide(
        self,
        *,
        ticker: str,
        arm: Arm,
        decision_date: date,
        price_rows: pd.DataFrame,
        feedback: list[dict[str, Any]],
        cache: DecisionCache,
        budget: TokenBudget,
    ) -> Decision:
        features = _price_features(price_rows)
        prompt_payload = {
            "ticker": ticker,
            "arm": arm,
            "decision_date": decision_date.isoformat(),
            "features": features,
            "feedback": feedback if arm == "alaya" else [],
            "provider": "heuristic",
            "version": SAMPLED_PROMPT_VERSION,
        }
        prompt = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_key = (
            f"{ticker}:{decision_date.isoformat()}:{arm}:heuristic:"
            f"{SAMPLED_PROMPT_VERSION}:{prompt_hash}"
        )
        cached = cache.get(cache_key)
        token_estimate = estimate_tokens(prompt)
        budget.charge(
            cache_key=cache_key,
            estimated_tokens=token_estimate,
            cache_hit=cached is not None,
        )
        if cached is not None:
            return Decision(
                direction=str(cached["direction"]),
                expected_change_pct=float(cached["expected_change_pct"]),
                confidence=float(cached["confidence"]),
                reasoning=str(cached["reasoning"]),
                prompt_hash=prompt_hash,
                estimated_tokens=token_estimate,
                token_usage_source="estimated",
                cache_hit=True,
            )

        expected = 0.55 * features["return_63d_pct"] + 0.45 * features["return_21d_pct"]
        if arm == "alaya" and feedback:
            recent_errors = [float(item["error"]) for item in feedback[-6:] if item.get("error") is not None]
            if recent_errors:
                expected += 0.35 * sum(recent_errors) / len(recent_errors)
        expected = round(max(min(expected, 25.0), -25.0), 4)
        direction = "long" if expected >= 2.0 else "avoid" if expected <= -2.0 else "watch"
        confidence = round(min(0.85, 0.45 + abs(expected) / 50 + min(len(feedback), 6) * 0.015), 4)
        reasoning = (
            "deterministic sampled validation; uses trailing adjusted-close momentum"
            + (" plus matured prior error feedback" if arm == "alaya" else "")
        )
        cache.set(
            cache_key,
            {
                "direction": direction,
                "expected_change_pct": expected,
                "confidence": confidence,
                "reasoning": reasoning,
            },
        )
        return Decision(
            direction=direction,
            expected_change_pct=expected,
            confidence=confidence,
            reasoning=reasoning,
            prompt_hash=prompt_hash,
            estimated_tokens=token_estimate,
            token_usage_source="estimated",
            cache_hit=False,
        )


class CodexDecisionProvider:
    """gpt-5.5/xhigh provider through the hardened Codex CLI client."""

    network_enabled = False

    def __init__(
        self,
        *,
        client: CompletionClient | None = None,
        max_retries: int = 2,
    ) -> None:
        self.client = client
        self.max_retries = max_retries

    def preflight(self) -> None:
        """Verify the Codex provider path before the expensive walk-forward loop."""

        completion = self._client().complete(
            system_prompt="Return strict JSON only.",
            user_prompt='Return exactly {"ok": true}.',
            max_tokens=32,
            timeout_seconds=120,
            temperature=0.0,
        )
        text, _provider_tokens = _completion_text_and_usage(completion)
        payload = json.loads(text)
        if payload != {"ok": True}:
            raise ProviderError(f"codex_cli preflight returned unexpected payload: {text}")

    def decide(
        self,
        *,
        ticker: str,
        arm: Arm,
        decision_date: date,
        price_rows: pd.DataFrame,
        feedback: list[dict[str, Any]],
        cache: DecisionCache,
        budget: TokenBudget,
    ) -> Decision:
        prompt_payload = _build_codex_prompt_payload(
            ticker=ticker,
            decision_date=decision_date,
            price_rows=price_rows,
            feedback=feedback if arm == "alaya" else [],
        )
        prompt = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True, indent=2)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_key = (
            f"{ticker}:{decision_date.isoformat()}:{arm}:codex_cli:"
            f"{FULL_PROMPT_VERSION}:{prompt_hash}"
        )
        cached = cache.get(cache_key)
        token_estimate = estimate_tokens(BT_CODEX_SYSTEM_PROMPT + "\n" + prompt)
        if cached is not None:
            budget.charge(cache_key=cache_key, estimated_tokens=token_estimate, cache_hit=True)
            return Decision(
                direction=str(cached["direction"]),
                expected_change_pct=float(cached["expected_change_pct"]),
                confidence=float(cached["confidence"]),
                reasoning=str(cached["reasoning"]),
                prompt_hash=prompt_hash,
                estimated_tokens=int(cached.get("estimated_tokens", token_estimate)),
                token_usage_source=str(cached.get("token_usage_source", "estimated")),
                cache_hit=True,
            )

        budget.preflight(estimated_tokens=token_estimate)
        last_error = ""
        for _attempt in range(self.max_retries + 1):
            try:
                completion = self._client().complete(
                    system_prompt=BT_CODEX_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    max_tokens=700,
                    timeout_seconds=240,
                    temperature=0.0,
                )
                text, provider_tokens = _completion_text_and_usage(completion)
                decision_payload = _parse_decision_json(text)
                billed_tokens = provider_tokens if provider_tokens is not None else token_estimate
                token_usage_source = "provider_usage" if provider_tokens is not None else "estimated"
                budget.charge(
                    cache_key=cache_key,
                    estimated_tokens=billed_tokens,
                    cache_hit=False,
                    allow_overage=True,
                )
                cache.set(
                    cache_key,
                    {
                        "direction": decision_payload["direction"],
                        "expected_change_pct": decision_payload["expected_change_pct"],
                        "confidence": decision_payload["confidence"],
                        "reasoning": decision_payload["reasoning"],
                        "estimated_tokens": billed_tokens,
                        "token_usage_source": token_usage_source,
                    },
                )
                return Decision(
                    direction=str(decision_payload["direction"]),
                    expected_change_pct=float(decision_payload["expected_change_pct"]),
                    confidence=float(decision_payload["confidence"]),
                    reasoning=str(decision_payload["reasoning"]),
                    prompt_hash=prompt_hash,
                    estimated_tokens=billed_tokens,
                    token_usage_source=token_usage_source,
                    cache_hit=False,
                )
            except BudgetExceeded:
                raise
            except Exception as exc:  # noqa: BLE001 - provider output is untrusted by design.
                last_error = str(exc)
        raise ProviderError(
            f"codex_cli provider failed after {self.max_retries + 1} attempts: {last_error}",
            prompt_hash=prompt_hash,
            estimated_tokens=token_estimate,
        )

    def _client(self) -> CompletionClient:
        if self.client is None:
            self.client = _build_default_codex_client()
        return self.client


class CodexCliUsageClient:
    """Codex CLI completion client that returns final text plus provider JSONL usage."""

    def __init__(self, base_client: Any) -> None:
        self.model = getattr(base_client, "model", "")
        self.project_root = Path(getattr(base_client, "project_root"))
        self.codex_binary = str(getattr(base_client, "codex_binary", "codex"))

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        timeout_seconds: int,
        temperature: float,
    ) -> dict[str, Any]:
        from chairman.llm.narrative_generator import (
            LLMError,
            LLMTimeout,
            build_codex_provider_prompt,
            codex_provider_clean_enabled,
            codex_provider_reasoning_effort,
            codex_provider_sandbox,
            codex_provider_subprocess_env,
            looks_like_codex_login_error,
        )

        if not shutil.which(self.codex_binary):
            raise LLMError("codex CLI is not installed or not on PATH")

        prompt = build_codex_provider_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".txt") as output_file:
            command = [
                self.codex_binary,
                "--ask-for-approval",
                "never",
                "exec",
                "-c",
                f'model_reasoning_effort="{codex_provider_reasoning_effort()}"',
                "--cd",
                str(self.project_root),
                "--sandbox",
                codex_provider_sandbox(),
                "--json",
                "--output-last-message",
                output_file.name,
            ]
            if codex_provider_clean_enabled():
                command.insert(command.index("-c"), "--ignore-user-config")
            if self.model:
                command.extend(["--model", self.model])
            command.append(prompt)

            with codex_provider_subprocess_env() as provider_env:
                try:
                    completed = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        check=False,
                        cwd=self.project_root,
                        env=provider_env,
                    )
                except FileNotFoundError as exc:
                    raise LLMError("codex CLI is not installed or not on PATH") from exc
                except subprocess.TimeoutExpired as exc:
                    raise LLMTimeout(str(exc)) from exc

            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            if completed.returncode != 0:
                detail = (stderr or stdout).strip()
                if looks_like_codex_login_error(detail):
                    raise LLMError("codex CLI is not logged in")
                raise LLMError(f"codex CLI failed with exit code {completed.returncode}: {detail}")

            output_file.seek(0)
            final_message = output_file.read().strip()
            return {
                "content": final_message or _last_agent_message_from_codex_jsonl(stdout),
                "usage": _codex_jsonl_usage(stdout),
            }


def run_backtest(config: BacktestConfig) -> dict[str, Any]:
    _enforce_backtest_env()
    run_id = config.run_id or datetime.now(UTC).strftime("bt_%Y%m%dT%H%M%SZ")
    run_root = config.data_dir / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    for arm in config.arms:
        (run_root / arm).mkdir(parents=True, exist_ok=True)

    cache, budget, ledger = _cache_budget_ledger(config=config, run_root=run_root, run_id=run_id)
    provider = _provider_for_run(config=config, ledger=ledger)
    provider_determinism = _provider_determinism_metadata(
        config.provider,
        require_stage3_provider=config.require_stage3_provider,
    )
    provider_determinism_error = _provider_determinism_error(provider_determinism)
    steps: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    budget_error = ""
    provider_abort_reason = ""
    provider_health = _provider_health_initial_state(
        config=config,
        provider=provider,
        budget=budget,
    )
    consecutive_provider_errors = 0

    try:
        if provider_determinism_error:
            provider_health["preflight_enabled"] = False
            provider_health["abort_reason"] = provider_determinism_error
        elif provider_health["preflight_enabled"]:
            try:
                preflight = getattr(provider, "preflight")
                preflight()
                provider_health["preflight_ok"] = True
            except Exception as exc:  # noqa: BLE001 - provider path is external.
                provider_health["preflight_ok"] = False
                provider_health["preflight_error"] = str(exc)
                provider_abort_reason = f"provider preflight failed: {exc}"

        if not provider_abort_reason and not provider_determinism_error:
            if _parallel_enabled(config):
                steps, skipped, provider_abort_reason, consecutive_provider_errors = _run_parallel(
                    config=config,
                    run_root=run_root,
                    cache=cache,
                    budget=budget,
                    ledger=ledger,
                    initial_steps=steps,
                    initial_skipped=skipped,
                    initial_consecutive_provider_errors=consecutive_provider_errors,
                )
            else:
                steps, skipped, provider_abort_reason, consecutive_provider_errors = _run_serial(
                    config=config,
                    run_root=run_root,
                    provider=provider,
                    cache=cache,
                    budget=budget,
                    initial_steps=steps,
                    initial_skipped=skipped,
                    initial_consecutive_provider_errors=consecutive_provider_errors,
                )
            if provider_abort_reason:
                provider_health["abort_reason"] = provider_abort_reason
            if budget.over_budget_error:
                raise BudgetExceeded(budget.over_budget_error)
    except BudgetExceeded as exc:
        budget_error = str(exc)

    steps = sorted(steps, key=lambda item: int(item.get("step") or 0))
    _record_steps(ledger=ledger, run_root=run_root, steps=steps)
    audit = audit_run(run_root)
    metrics = summarize_steps(steps)
    provider_errors = sum(1 for step in steps if step.get("status") == "provider_error")
    system_health = _build_system_health(
        budget=budget,
        budget_error=budget_error,
        audit_ok=audit.ok,
        provider_errors=provider_errors,
        provider_abort_reason=provider_abort_reason,
        provider_determinism_error=provider_determinism_error,
        run_mode=config.mode,
        provider=config.provider,
    )
    (run_root / "system_health.json").write_text(
        json.dumps(system_health, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    summary = {
        "run_id": run_id,
        "mode": config.mode,
        "provider": config.provider,
        "provider_metadata": _provider_metadata(config.provider),
        "provider_determinism": provider_determinism,
        "provider_determinism_error": provider_determinism_error,
        "require_stage3_provider": config.require_stage3_provider,
        "sampled_validation_only": config.mode == "sampled" or config.provider == "heuristic",
        "start": config.start.isoformat(),
        "end": config.end.isoformat(),
        "step_months": config.step_months,
        "tickers": [ticker.symbol for ticker in config.tickers],
        "arms": list(config.arms),
        "cache_namespace": config.cache_namespace,
        "window_days": config.window_days,
        "steps_written": len(steps),
        "skipped": skipped,
        "paused": bool(budget_error),
        "pause_reason": budget_error,
        "aborted_provider_unhealthy": bool(provider_abort_reason),
        "provider_abort_reason": provider_abort_reason,
        "provider_health": provider_health,
        "price_cache_network_after_cache": False,
        "perplexity_disabled": True,
        "provider_errors": provider_errors,
        "token_budget": budget.snapshot(),
        "ledger": _ledger_metadata(config=config, ledger=ledger),
        "parallel": _parallel_metadata(config),
        "system_health": system_health,
        "audit": audit.to_dict(),
        "metrics": metrics,
    }
    report_path, chart_path = write_backtest_report(
        data_dir=config.data_dir,
        run_root=run_root,
        summary=summary,
        steps=steps,
    )
    summary["report_path"] = str(report_path)
    summary["chart_path"] = str(chart_path)
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    from gotra.backtest.analyze import analyze_run

    summary = analyze_run(run_root)["summary"]
    return summary


def _cache_budget_ledger(
    *,
    config: BacktestConfig,
    run_root: Path,
    run_id: str,
) -> tuple[Any, Any, SQLiteLedger | None]:
    if config.ledger == "sqlite":
        base_budget = TokenBudget.from_env(config.token_budget)
        ledger = SQLiteLedger(
            config.ledger_path or run_root / "run_ledger.sqlite",
            run_id=run_id,
            cache_namespace=config.cache_namespace,
            max_tokens=base_budget.max_tokens,
        )
        return SQLiteDecisionCache(ledger), ledger, ledger
    cache = DecisionCache(
        config.data_dir / "runs" / "decision_cache.json",
        namespace=config.cache_namespace,
    )
    return cache, TokenBudget.from_env(config.token_budget), None


def _parallel_enabled(config: BacktestConfig) -> bool:
    return config.parallel_mode != "off" or config.provider_concurrency > 1


def _parallel_metadata(config: BacktestConfig) -> dict[str, Any]:
    return {
        "mode": config.parallel_mode,
        "provider_concurrency": config.provider_concurrency,
        "resume": config.resume,
    }


def _ledger_metadata(config: BacktestConfig, ledger: SQLiteLedger | None) -> dict[str, Any]:
    return {
        "backend": config.ledger,
        "path": str(ledger.path) if ledger else "",
    }


def _provider_for_run(
    *,
    config: BacktestConfig,
    ledger: SQLiteLedger | None,
) -> DecisionProvider:
    provider = _build_provider(config.provider)
    if ledger is None:
        return provider
    return _LedgerProvider(provider=provider, ledger=ledger)


class _LedgerProvider:
    def __init__(self, *, provider: DecisionProvider, ledger: SQLiteLedger) -> None:
        self.provider = provider
        self.ledger = ledger
        self.network_enabled = provider.network_enabled

    def preflight(self) -> None:
        preflight = getattr(self.provider, "preflight", None)
        if preflight is not None:
            preflight()

    def decide(self, **kwargs: Any) -> Decision:
        started = time.perf_counter()
        started_at = datetime.now(UTC).isoformat()
        status = "ok"
        error_type = ""
        estimated_tokens = 0
        try:
            decision = self.provider.decide(**kwargs)
            estimated_tokens = decision.estimated_tokens
            return decision
        except Exception as exc:
            status = "error"
            error_type = type(exc).__name__
            estimated_tokens = int(getattr(exc, "estimated_tokens", 0) or 0)
            raise
        finally:
            finished_at = datetime.now(UTC).isoformat()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self.ledger.record_provider_call(
                ProviderCall(
                    call_id=(
                        f"{threading.get_ident()}:{time.time_ns()}:"
                        f"{kwargs.get('ticker')}:{kwargs.get('decision_date')}:{kwargs.get('arm')}"
                    ),
                    worker_id=str(threading.get_ident()),
                    arm=str(kwargs.get("arm") or ""),
                    ticker=str(kwargs.get("ticker") or ""),
                    decision_date=str(kwargs.get("decision_date") or ""),
                    cache_key=(
                        f"{kwargs.get('ticker')}:{kwargs.get('decision_date')}:{kwargs.get('arm')}"
                    ),
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    elapsed_ms=elapsed_ms,
                    estimated_tokens=estimated_tokens,
                    error_type=error_type,
                )
            )


def _run_serial(
    *,
    config: BacktestConfig,
    run_root: Path,
    provider: DecisionProvider,
    cache: Any,
    budget: Any,
    initial_steps: list[dict[str, Any]],
    initial_skipped: list[dict[str, Any]],
    initial_consecutive_provider_errors: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, int]:
    steps = list(initial_steps)
    skipped = list(initial_skipped)
    feedback_by_ticker: dict[str, list[dict[str, Any]]] = {}
    provider_abort_reason = ""
    consecutive_provider_errors = initial_consecutive_provider_errors

    for decision_date in decision_dates(
        start=config.start,
        end=config.end,
        step_months=config.step_months,
    ):
        if provider_abort_reason:
            break
        for ticker in config.tickers:
            if config.max_steps is not None and len(steps) >= config.max_steps:
                break
            resumed_steps = _resume_ticker_steps(
                config=config,
                run_root=run_root,
                ticker=ticker,
                decision_date=decision_date,
                feedback_by_ticker=feedback_by_ticker,
            )
            if resumed_steps:
                ticker_steps = resumed_steps
            else:
                ticker_steps = _run_ticker_step(
                    ticker=ticker,
                    decision_date=decision_date,
                    config=config,
                    provider=provider,
                    cache=cache,
                    budget=budget,
                    feedback_by_ticker=feedback_by_ticker,
                    run_root=run_root,
                    skipped=skipped,
                    next_step_index=len(steps) + 1,
                )
            steps.extend(ticker_steps)
            consecutive_provider_errors = _consecutive_provider_errors(
                steps=ticker_steps,
                current=consecutive_provider_errors,
            )
            provider_abort_reason = _provider_abort_reason(
                config=config,
                provider=provider,
                steps=steps,
                consecutive_provider_errors=consecutive_provider_errors,
            )
            if provider_abort_reason or budget.over_budget_error:
                break
        if config.max_steps is not None and len(steps) >= config.max_steps:
            break
    return steps, skipped, provider_abort_reason, consecutive_provider_errors


def _run_parallel(
    *,
    config: BacktestConfig,
    run_root: Path,
    cache: Any,
    budget: Any,
    ledger: SQLiteLedger | None,
    initial_steps: list[dict[str, Any]],
    initial_skipped: list[dict[str, Any]],
    initial_consecutive_provider_errors: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, int]:
    if ledger is None or config.ledger != "sqlite":
        raise ValueError("parallel BT execution requires --ledger sqlite")
    if config.parallel_mode == "baseline" and config.arms != ("baseline",):
        raise ValueError("--parallel-mode baseline requires --arms baseline")
    if config.provider_concurrency < 1:
        raise ValueError("--provider-concurrency must be >= 1")

    if config.parallel_mode == "baseline" or config.arms == ("baseline",):
        tasks = stable_step_plan(
            tickers=config.tickers,
            decision_dates=decision_dates(
                start=config.start,
                end=config.end,
                step_months=config.step_months,
            ),
            arms=("baseline",),
            max_steps=config.max_steps,
        )
        worker = _parallel_step_worker(
            config=replace(config, arms=("baseline",)),
            run_root=run_root,
            cache=cache,
            budget=budget,
            ledger=ledger,
        )
        results = run_independent_tasks(tasks, worker, max_workers=config.provider_concurrency)
    else:
        tasks = _ticker_group_tasks(config)
        worker = _parallel_step_worker(
            config=config,
            run_root=run_root,
            cache=cache,
            budget=budget,
            ledger=ledger,
        )
        results = run_ticker_chains(tasks, worker, max_workers=config.provider_concurrency)

    steps = list(initial_steps)
    skipped = list(initial_skipped)
    for ticker_steps, ticker_skipped in results:
        steps.extend(ticker_steps)
        skipped.extend(ticker_skipped)
    consecutive_provider_errors = initial_consecutive_provider_errors
    for step in sorted(steps, key=lambda item: int(item.get("step") or 0)):
        consecutive_provider_errors = 1 + consecutive_provider_errors if step.get("status") == "provider_error" else 0
    provider_abort_reason = _provider_abort_reason(
        config=config,
        provider=_provider_for_run(config=config, ledger=ledger),
        steps=steps,
        consecutive_provider_errors=consecutive_provider_errors,
    )
    return steps, skipped, provider_abort_reason, consecutive_provider_errors


def _parallel_step_worker(
    *,
    config: BacktestConfig,
    run_root: Path,
    cache: Any,
    budget: Any,
    ledger: SQLiteLedger,
) -> Any:
    feedback_by_ticker: dict[str, list[dict[str, Any]]] = {ticker.symbol: [] for ticker in config.tickers}

    def worker(task: StepTask) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        skipped: list[dict[str, Any]] = []
        resumed_steps = _resume_ticker_steps(
            config=config,
            run_root=run_root,
            ticker=task.ticker,
            decision_date=task.decision_date,
            feedback_by_ticker=feedback_by_ticker,
        )
        if resumed_steps:
            return resumed_steps, skipped
        provider = _provider_for_run(config=config, ledger=ledger)
        ticker_steps = _run_ticker_step(
            ticker=task.ticker,
            decision_date=task.decision_date,
            config=config,
            provider=provider,
            cache=cache,
            budget=budget,
            feedback_by_ticker=feedback_by_ticker,
            run_root=run_root,
            skipped=skipped,
            next_step_index=task.step_index,
        )
        return ticker_steps, skipped

    return worker


def _ticker_group_tasks(config: BacktestConfig) -> list[StepTask]:
    first_arm = config.arms[0]
    return [
        task
        for task in stable_step_plan(
            tickers=config.tickers,
            decision_dates=decision_dates(
                start=config.start,
                end=config.end,
                step_months=config.step_months,
            ),
            arms=config.arms,
            max_steps=config.max_steps,
        )
        if task.arm == first_arm
    ]


def _resume_ticker_steps(
    *,
    config: BacktestConfig,
    run_root: Path,
    ticker: TickerSpec,
    decision_date: date,
    feedback_by_ticker: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if not config.resume:
        return []
    paths = [_step_path(run_root, arm=arm, ticker=ticker.symbol, decision_date=decision_date) for arm in config.arms]
    if not all(path.exists() for path in paths):
        return []
    steps = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for step in sorted(steps, key=lambda item: int(item.get("step") or 0)):
        if step.get("arm") == "alaya" and step.get("status") == "scored":
            feedback_by_ticker.setdefault(ticker.symbol, []).append(
                {
                    "decision_date": step["decision_date"],
                    "outcome_availability_date": step["outcome_as_of"],
                    "error": step["error"],
                    "actual_change_pct": step["actual_change_pct"],
                    "expected_change_pct": step["expected_change_pct"],
                }
            )
    return steps


def _consecutive_provider_errors(*, steps: list[dict[str, Any]], current: int) -> int:
    consecutive = current
    for step in steps:
        if step.get("status") == "provider_error":
            consecutive += 1
        else:
            consecutive = 0
    return consecutive


def _record_steps(
    *,
    ledger: SQLiteLedger | None,
    run_root: Path,
    steps: list[dict[str, Any]],
) -> None:
    if ledger is None:
        return
    for step in steps:
        ledger.record_step(
            step_id=f"{int(step.get('step') or 0):06d}:{step.get('decision_date')}:{step.get('ticker')}:{step.get('arm')}",
            step_index=int(step.get("step") or 0),
            arm=str(step.get("arm") or ""),
            ticker=str(step.get("ticker") or ""),
            decision_date=str(step.get("decision_date") or ""),
            status=str(step.get("status") or ""),
            step_path=str(_step_path(
                run_root,
                arm=str(step.get("arm") or ""),
                ticker=str(step.get("ticker") or ""),
                decision_date=parse_date(str(step.get("decision_date"))),
            )),
        )


def _build_provider(name: ProviderName) -> DecisionProvider:
    if name == "heuristic":
        return HeuristicDecisionProvider()
    if name == "codex_cli":
        return CodexDecisionProvider()
    raise ValueError(f"unsupported BT provider: {name}")


def _build_default_codex_client() -> CompletionClient:
    from gotra.judge_agent.llm import build_judge_client

    return CodexCliUsageClient(build_judge_client())


def _build_system_health(
    *,
    budget: TokenBudget,
    budget_error: str,
    audit_ok: bool,
    provider_errors: int,
    provider_abort_reason: str,
    provider_determinism_error: str,
    run_mode: RunMode,
    provider: ProviderName,
) -> dict[str, Any]:
    alerts: list[str] = []
    if provider_determinism_error:
        alerts.append(provider_determinism_error)
    if budget_error:
        alerts.append(budget_error)
    if provider_abort_reason:
        alerts.append(provider_abort_reason)
    if not audit_ok and not budget_error:
        alerts.append("future-function audit failed")
    if provider_errors:
        alerts.append(f"provider_error steps: {provider_errors}")
    status = "ok"
    if provider_determinism_error:
        status = "blocked_provider_determinism"
    elif budget_error:
        status = "paused"
    elif provider_abort_reason:
        status = "aborted_provider_unhealthy"
    elif not audit_ok or provider_errors:
        status = "failed"
    return {
        "status": status,
        "paused": bool(budget_error),
        "pause_reason": budget_error,
        "aborted_provider_unhealthy": bool(provider_abort_reason),
        "provider_abort_reason": provider_abort_reason,
        "provider_determinism_error": provider_determinism_error,
        "alerts": alerts,
        "run_mode": run_mode,
        "provider": provider,
        "provider_errors": provider_errors,
        "sampled_validation_only": run_mode == "sampled" or provider == "heuristic",
        "token_budget": budget.snapshot(),
    }


def _provider_health_initial_state(
    *,
    config: BacktestConfig,
    provider: DecisionProvider,
    budget: TokenBudget,
) -> dict[str, Any]:
    enough_budget_for_preflight = budget.max_tokens is None or budget.max_tokens >= 50_000
    preflight_enabled = (
        config.provider == "codex_cli"
        and config.provider_preflight
        and enough_budget_for_preflight
        and hasattr(provider, "preflight")
    )
    return {
        "preflight_enabled": preflight_enabled,
        "preflight_ok": None,
        "preflight_error": "",
        "abort_reason": "",
        "error_abort_consecutive": config.provider_error_abort_consecutive,
        "error_abort_rate": config.provider_error_abort_rate,
    }


def _provider_abort_reason(
    *,
    config: BacktestConfig,
    provider: DecisionProvider,
    steps: list[dict[str, Any]],
    consecutive_provider_errors: int,
) -> str:
    if config.provider != "codex_cli":
        return ""
    if (
        config.provider_error_abort_consecutive > 0
        and consecutive_provider_errors >= config.provider_error_abort_consecutive
    ):
        return (
            "provider unhealthy: "
            f"{consecutive_provider_errors} consecutive provider_error steps"
        )

    if len(steps) < max(config.provider_error_abort_consecutive, 20):
        return ""
    provider_errors = sum(1 for step in steps if step.get("status") == "provider_error")
    error_rate = provider_errors / len(steps)
    if config.provider_error_abort_rate > 0 and error_rate > config.provider_error_abort_rate:
        return (
            "provider unhealthy: "
            f"provider_error rate {error_rate:.2%} exceeds {config.provider_error_abort_rate:.2%}"
        )
    return ""


def _run_ticker_step(
    *,
    ticker: TickerSpec,
    decision_date: date,
    config: BacktestConfig,
    provider: DecisionProvider,
    cache: DecisionCache,
    budget: TokenBudget,
    feedback_by_ticker: dict[str, list[dict[str, Any]]],
    run_root: Path,
    skipped: list[dict[str, Any]],
    next_step_index: int,
) -> list[dict[str, Any]]:
    if decision_date < ticker.listing_date:
        skipped.append(
            {
                "ticker": ticker.symbol,
                "decision_date": decision_date.isoformat(),
                "reason": "listed_after_decision_date",
            }
        )
        return []

    prices = read_price_cache(ticker.symbol, price_dir=config.data_dir / "prices")
    decision_slice = _rows_on_or_before(prices, decision_date)
    start_row = _row_on_or_after(prices, decision_date)
    outcome_date = decision_date + timedelta(days=config.window_days)
    end_row = _row_on_or_after(prices, outcome_date)
    if decision_slice.empty or start_row is None or end_row is None:
        skipped.append(
            {
                "ticker": ticker.symbol,
                "decision_date": decision_date.isoformat(),
                "reason": "insufficient_price_history",
            }
        )
        return []

    steps: list[dict[str, Any]] = []
    matured_feedback = [
        item
        for item in feedback_by_ticker.get(ticker.symbol, [])
        if parse_date(item["outcome_availability_date"]) <= decision_date
    ]
    for arm in config.arms:
        actual_change = _change_pct(float(start_row["adj_close"]), float(end_row["adj_close"]))
        try:
            decision = provider.decide(
                ticker=ticker.symbol,
                arm=arm,  # type: ignore[arg-type]
                decision_date=decision_date,
                price_rows=decision_slice,
                feedback=matured_feedback if arm == "alaya" else [],
                cache=cache,
                budget=budget,
            )
        except BudgetExceeded:
            raise
        except ProviderError as exc:
            step = _build_provider_error_step(
                step_index=next_step_index + len(steps),
                ticker=ticker,
                arm=arm,  # type: ignore[arg-type]
                decision_date=decision_date,
                outcome_date=outcome_date,
                start_row=start_row,
                end_row=end_row,
                decision_slice=decision_slice,
                actual_change_pct=actual_change,
                feedback=matured_feedback if arm == "alaya" else [],
                provider=provider,
                config=config,
                error_message=str(exc),
                prompt_hash=exc.prompt_hash,
                estimated_tokens=exc.estimated_tokens,
            )
            _write_step(run_root, step)
            _append_event(run_root, step)
            steps.append(step)
            continue
        except Exception as exc:  # noqa: BLE001 - preserve the failing step for audit.
            step = _build_provider_error_step(
                step_index=next_step_index + len(steps),
                ticker=ticker,
                arm=arm,  # type: ignore[arg-type]
                decision_date=decision_date,
                outcome_date=outcome_date,
                start_row=start_row,
                end_row=end_row,
                decision_slice=decision_slice,
                actual_change_pct=actual_change,
                feedback=matured_feedback if arm == "alaya" else [],
                provider=provider,
                config=config,
                error_message=str(exc),
                prompt_hash="",
                estimated_tokens=0,
            )
            _write_step(run_root, step)
            _append_event(run_root, step)
            steps.append(step)
            continue
        error = round(actual_change - decision.expected_change_pct, 6)
        mse = round(error * error, 6)
        step = _build_step(
            step_index=next_step_index + len(steps),
            ticker=ticker,
            arm=arm,  # type: ignore[arg-type]
            decision_date=decision_date,
            outcome_date=outcome_date,
            start_row=start_row,
            end_row=end_row,
            decision_slice=decision_slice,
            decision=decision,
            actual_change_pct=actual_change,
            error=error,
            mse=mse,
            feedback=matured_feedback if arm == "alaya" else [],
            provider=provider,
            config=config,
        )
        _write_step(run_root, step)
        _append_event(run_root, step)
        steps.append(step)
        if arm == "alaya":
            feedback_by_ticker.setdefault(ticker.symbol, []).append(
                {
                    "decision_date": decision_date.isoformat(),
                    "outcome_availability_date": step["outcome_as_of"],
                    "error": error,
                    "actual_change_pct": actual_change,
                    "expected_change_pct": decision.expected_change_pct,
                }
            )
        if budget.over_budget_error:
            return steps
    return steps


def _build_step(
    *,
    step_index: int,
    ticker: TickerSpec,
    arm: Arm,
    decision_date: date,
    outcome_date: date,
    start_row: pd.Series,
    end_row: pd.Series,
    decision_slice: pd.DataFrame,
    decision: Decision,
    actual_change_pct: float,
    error: float,
    mse: float,
    feedback: list[dict[str, Any]],
    provider: DecisionProvider,
    config: BacktestConfig,
) -> dict[str, Any]:
    return {
        "schema": "gotra.bt.step.v1",
        "step": step_index,
        "date": decision_date.isoformat(),
        "run_mode": config.mode,
        "status": "scored",
        "ticker": ticker.symbol,
        "ticker_name": ticker.name,
        "arm": arm,
        "decision_date": decision_date.isoformat(),
        "window_days": config.window_days,
        "window_end_date": outcome_date.isoformat(),
        "outcome_as_of": str(end_row["date"]),
        "decision_direction": decision.direction,
        "expected_change_pct": decision.expected_change_pct,
        "actual_change_pct": actual_change_pct,
        "error": error,
        "mse": mse,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "prompt_hash": decision.prompt_hash,
        "estimated_tokens": decision.estimated_tokens,
        "token_usage_source": decision.token_usage_source,
        "cache_hit": decision.cache_hit,
        "cache_namespace": config.cache_namespace,
        "provider": config.provider,
        "provider_metadata": _provider_metadata(config.provider),
        "provider_network_enabled": provider.network_enabled,
        "style_window": style_window_for(decision_date),
        "decision_inputs": _decision_inputs(decision_slice, feedback),
        "outcome_inputs": _outcome_inputs(end_row),
        "future_data_allowed": False,
        "audit_actor": "backtest/walk_forward",
    }


def _build_provider_error_step(
    *,
    step_index: int,
    ticker: TickerSpec,
    arm: Arm,
    decision_date: date,
    outcome_date: date,
    start_row: pd.Series,
    end_row: pd.Series,
    decision_slice: pd.DataFrame,
    actual_change_pct: float,
    feedback: list[dict[str, Any]],
    provider: DecisionProvider,
    config: BacktestConfig,
    error_message: str,
    prompt_hash: str,
    estimated_tokens: int,
) -> dict[str, Any]:
    del start_row
    return {
        "schema": "gotra.bt.step.v1",
        "step": step_index,
        "date": decision_date.isoformat(),
        "error_type": "provider_error",
        "run_mode": config.mode,
        "status": "provider_error",
        "ticker": ticker.symbol,
        "ticker_name": ticker.name,
        "arm": arm,
        "decision_date": decision_date.isoformat(),
        "window_days": config.window_days,
        "window_end_date": outcome_date.isoformat(),
        "outcome_as_of": str(end_row["date"]),
        "decision_direction": None,
        "expected_change_pct": None,
        "actual_change_pct": actual_change_pct,
        "error": None,
        "mse": None,
        "confidence": None,
        "reasoning": "",
        "prompt_hash": prompt_hash,
        "estimated_tokens": estimated_tokens,
        "token_usage_source": "estimated",
        "cache_hit": False,
        "cache_namespace": config.cache_namespace,
        "provider": config.provider,
        "provider_metadata": _provider_metadata(config.provider),
        "provider_network_enabled": provider.network_enabled,
        "provider_error": error_message,
        "style_window": style_window_for(decision_date),
        "decision_inputs": _decision_inputs(decision_slice, feedback),
        "outcome_inputs": _outcome_inputs(end_row),
        "future_data_allowed": False,
        "audit_actor": "backtest/walk_forward",
    }


def _decision_inputs(
    decision_slice: pd.DataFrame,
    feedback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest_decision_row = decision_slice.iloc[-1]
    decision_inputs = [
        {
            "name": "adjusted_close_history",
            "kind": "price",
            "source": str(latest_decision_row["source_url"]),
            "availability_date": str(latest_decision_row["date"]),
            "rows": int(len(decision_slice)),
        }
    ]
    for index, item in enumerate(feedback):
        decision_inputs.append(
            {
                "name": f"matured_feedback_{index}",
                "kind": "alaya_feedback",
                "source": "prior_step_outcome",
                "availability_date": item["outcome_availability_date"],
            }
        )
    return decision_inputs


def _outcome_inputs(end_row: pd.Series) -> list[dict[str, Any]]:
    return [
        {
            "name": "outcome_adjusted_close",
            "kind": "price",
            "source": str(end_row["source_url"]),
            "availability_date": str(end_row["date"]),
        }
    ]


def _provider_metadata(provider: ProviderName) -> dict[str, Any]:
    if provider != "codex_cli":
        return {}
    return {
        "model": os.getenv("JUDGE_LLM_MODEL") or os.getenv("LLM_MODEL") or "gpt-5.5",
        "reasoning_effort": os.getenv("CODEX_PROVIDER_REASONING_EFFORT")
        or os.getenv("JUDGE_CODEX_REASONING_EFFORT")
        or "xhigh",
        "sandbox": os.getenv("CODEX_PROVIDER_SANDBOX", "read-only"),
        "clean_profile": os.getenv("CODEX_PROVIDER_CLEAN", "1") in {"1", "true", "yes", "on"},
    }


def _provider_determinism_metadata(
    provider: ProviderName,
    *,
    require_stage3_provider: bool = False,
) -> dict[str, Any]:
    if provider == "heuristic":
        return {
            "provider": provider,
            "required_for_stage3": require_stage3_provider,
            "stage3_acceptance_eligible": False,
            "temperature_control": "not_applicable",
            "top_p_control": False,
            "seed_control": False,
            "blocking_reason": (
                "heuristic is a local sampled-plumbing provider and is not a real LLM "
                "science provider"
            ),
        }
    if provider == "codex_cli":
        return {
            "provider": provider,
            "required_for_stage3": require_stage3_provider,
            "stage3_acceptance_eligible": False,
            "temperature_control": "prompt_guidance_only",
            "top_p_control": False,
            "seed_control": False,
            "blocking_reason": (
                "approved Codex CLI route does not expose reliable temperature, top_p, "
                "or seed controls for preregistered baseline replay acceptance"
            ),
        }
    raise ValueError(f"unsupported BT provider: {provider}")


def _provider_determinism_error(provider_determinism: dict[str, Any]) -> str:
    if not provider_determinism.get("required_for_stage3"):
        return ""
    if provider_determinism.get("stage3_acceptance_eligible") is True:
        return ""
    return str(provider_determinism.get("blocking_reason") or "provider is not Stage 3 eligible")


def _write_step(run_root: Path, step: dict[str, Any]) -> None:
    path = _step_path(
        run_root,
        arm=str(step["arm"]),
        ticker=str(step["ticker"]),
        decision_date=parse_date(str(step["decision_date"])),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".{threading.get_ident()}.tmp")
    tmp_path.write_text(
        json.dumps(step, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    with _STEP_WRITE_LOCK:
        tmp_path.replace(path)


def _step_path(run_root: Path, *, arm: str, ticker: str, decision_date: date) -> Path:
    return run_root / arm / f"step_{decision_date.isoformat()}_{ticker_slug(ticker)}.json"


def _append_event(run_root: Path, step: dict[str, Any]) -> None:
    event = {
        "actor": "backtest/walk_forward",
        "event_type": "bt_step_scored"
        if step.get("status") == "scored"
        else "bt_provider_error",
        "ticker": step["ticker"],
        "arm": step["arm"],
        "decision_date": step["decision_date"],
        "mse": step.get("mse"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    if step.get("provider_error"):
        event["provider_error"] = step["provider_error"]
    with _EVENT_WRITE_LOCK:
        with (run_root / "event_log.jsonl").open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _build_codex_prompt_payload(
    *,
    ticker: str,
    decision_date: date,
    price_rows: pd.DataFrame,
    feedback: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_row = price_rows.iloc[-1]
    return {
        "schema": "gotra.bt.decision_prompt.v1",
        "version": FULL_PROMPT_VERSION,
        "ticker": ticker,
        "decision_date": decision_date.isoformat(),
        "horizon_days": WINDOW_DAYS,
        "input_policy": {
            "decision_inputs_available_on_or_before": decision_date.isoformat(),
            "fundamentals_enabled": False,
            "network_research_enabled": False,
            "external_apis_enabled": False,
        },
        "framework": {
            "F_partner": "Use only price-derived evidence included in this payload.",
            "W_partner": "Use only price momentum and drawdown context included in this payload.",
            "G_partner": "Use only price-history risk context included in this payload.",
            "Chairman": "Reconcile F/W/G into one 30-day directional expected-change decision.",
        },
        "price_history": {
            "rows_available": int(len(price_rows)),
            "latest_date": str(latest_row["date"]),
            "latest_adjusted_close": float(latest_row["adj_close"]),
            "features": _price_features(price_rows),
            "recent_adjusted_close": _compact_price_rows(price_rows),
        },
        "feedback": feedback,
        "output_contract": {
            "direction": "long|short|watch|avoid",
            "expected_change_pct": "number",
            "confidence": "number in [0, 1]",
            "reasoning": "brief string",
        },
    }


def _compact_price_rows(rows: pd.DataFrame, *, max_rows: int = 64) -> list[dict[str, Any]]:
    compact = rows.tail(max_rows)[["date", "adj_close"]].copy()
    return [
        {
            "date": str(row["date"]),
            "adj_close": round(float(row["adj_close"]), 6),
        }
        for row in compact.to_dict("records")
    ]


def _completion_text_and_usage(completion: Any) -> tuple[str, int | None]:
    if isinstance(completion, str):
        return completion, None
    if isinstance(completion, dict):
        text = completion.get("content") or completion.get("text") or completion.get("message") or ""
        return str(text), _usage_total_tokens(completion.get("usage"))
    text = getattr(completion, "content", None) or getattr(completion, "text", None) or str(completion)
    usage = getattr(completion, "usage", None)
    return str(text), _usage_total_tokens(usage)


def _usage_total_tokens(usage: Any) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, int | float):
        return max(0, int(usage))
    if isinstance(usage, dict):
        for key in ("total_tokens", "total", "tokens"):
            value = usage.get(key)
            if isinstance(value, int | float):
                return max(0, int(value))
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        if isinstance(input_tokens, int | float) and isinstance(output_tokens, int | float):
            return max(0, int(input_tokens) + int(output_tokens))
    for attr in ("total_tokens", "total", "tokens"):
        value = getattr(usage, attr, None)
        if isinstance(value, int | float):
            return max(0, int(value))
    input_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None) or getattr(
        usage, "completion_tokens", None
    )
    if isinstance(input_tokens, int | float) and isinstance(output_tokens, int | float):
        return max(0, int(input_tokens) + int(output_tokens))
    return None


def _codex_jsonl_usage(stdout: str) -> dict[str, int] | None:
    last_usage: dict[str, Any] | None = None
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = event.get("usage")
        if event.get("type") == "turn.completed" and isinstance(usage, dict):
            last_usage = usage
    if last_usage is None:
        return None
    result: dict[str, int] = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
        value = last_usage.get(key, 0)
        if isinstance(value, int | float):
            result[key] = max(0, int(value))
    total = result.get("input_tokens", 0) + result.get("output_tokens", 0)
    result["total_tokens"] = max(0, total)
    return result


def _last_agent_message_from_codex_jsonl(stdout: str) -> str:
    message = ""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
        ):
            message = str(item.get("text") or "")
    return message.strip()


def _parse_decision_json(text: str) -> dict[str, Any]:
    payload = _load_json_object(text)
    direction = _normalize_direction(payload.get("direction"))
    expected_change_pct = float(payload["expected_change_pct"])
    confidence = float(payload["confidence"])
    if 1.0 < confidence <= 100.0:
        confidence = confidence / 100.0
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence out of range: {confidence}")
    reasoning = str(payload.get("reasoning") or "").strip()
    if not reasoning:
        raise ValueError("reasoning is required")
    return {
        "direction": direction,
        "expected_change_pct": expected_change_pct,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _load_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = candidate.find("{")
        if start < 0:
            raise
        parsed, _end = decoder.raw_decode(candidate[start:])
    if not isinstance(parsed, dict):
        raise ValueError("provider response must be a JSON object")
    return parsed


def _normalize_direction(value: Any) -> str:
    direction = str(value or "").strip().lower()
    aliases = {
        "buy": "long",
        "bullish": "long",
        "sell": "short",
        "bearish": "short",
        "hold": "watch",
        "neutral": "watch",
    }
    direction = aliases.get(direction, direction)
    if direction not in {"long", "short", "watch", "avoid"}:
        raise ValueError(f"unsupported direction: {value!r}")
    return direction


def _price_features(rows: pd.DataFrame) -> dict[str, float]:
    closes = [float(value) for value in rows["adj_close"].tolist()]
    latest = closes[-1]
    return {
        "return_21d_pct": _trailing_return(closes, latest=latest, days=21),
        "return_63d_pct": _trailing_return(closes, latest=latest, days=63),
        "history_rows": float(len(closes)),
    }


def _trailing_return(closes: list[float], *, latest: float, days: int) -> float:
    if len(closes) <= days:
        return 0.0
    past = closes[-days - 1]
    return _change_pct(past, latest)


def _change_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return round((end - start) / start * 100, 6)


def _rows_on_or_before(frame: pd.DataFrame, target: date) -> pd.DataFrame:
    dates = pd.to_datetime(frame["date"]).dt.date
    return frame.loc[dates <= target].reset_index(drop=True)


def _row_on_or_after(frame: pd.DataFrame, target: date) -> pd.Series | None:
    dates = pd.to_datetime(frame["date"]).dt.date
    filtered = frame.loc[dates >= target]
    if filtered.empty:
        return None
    return filtered.iloc[0]


def _enforce_backtest_env() -> None:
    if os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY"):
        raise RuntimeError("Phase BT must run with Perplexity API keys unset")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase BT walk-forward backtest.")
    parser.add_argument("--data-dir", default="data/backtest")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mode", choices=["sampled", "full"], default="sampled")
    parser.add_argument("--provider", choices=["heuristic", "codex_cli"], default="heuristic")
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument("--step-months", type=int, default=SAMPLED_STEP_MONTHS)
    parser.add_argument("--tickers", default="")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    parser.add_argument("--token-budget", type=int)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument(
        "--arms",
        default="baseline,alaya",
        help="Comma-separated arms to run: baseline, alaya, or both. Default: baseline,alaya.",
    )
    parser.add_argument(
        "--cache-namespace",
        default="",
        help="Optional cache namespace for independent provider replays without changing prompts.",
    )
    parser.add_argument("--ledger", choices=["json", "sqlite"], default="json")
    parser.add_argument("--ledger-path", default="")
    parser.add_argument("--provider-concurrency", type=int, default=1)
    parser.add_argument(
        "--parallel-mode",
        choices=["off", "baseline", "ticker-chains", "both"],
        default="off",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-provider-preflight", action="store_true")
    parser.add_argument(
        "--require-stage3-provider",
        action="store_true",
        help=(
            "Abort before provider calls unless the provider exposes reliable temperature/top_p/seed "
            "controls and is eligible for preregistered Stage 3 replay acceptance."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    symbols = [item.strip() for item in args.tickers.split(",") if item.strip()]
    summary = run_backtest(
        BacktestConfig(
            data_dir=Path(args.data_dir),
            run_id=args.run_id,
            mode=args.mode,
            provider=args.provider,
            start=parse_date(args.start),
            end=parse_date(args.end),
            step_months=args.step_months,
            tickers=selected_universe(symbols),
            window_days=args.window_days,
            token_budget=args.token_budget,
            max_steps=args.max_steps,
            arms=_parse_arms(args.arms),
            cache_namespace=args.cache_namespace,
            provider_preflight=not args.no_provider_preflight,
            require_stage3_provider=args.require_stage3_provider,
            ledger=args.ledger,
            ledger_path=Path(args.ledger_path) if args.ledger_path else None,
            provider_concurrency=args.provider_concurrency,
            parallel_mode=args.parallel_mode,
            resume=args.resume,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary.get("paused"):
        return 2
    if (summary.get("system_health") or {}).get("status") != "ok":
        return 1
    if not (summary.get("audit") or {}).get("ok"):
        return 1
    return 0


def _parse_arms(value: str) -> tuple[Arm, ...]:
    raw = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not raw:
        raise ValueError("--arms must include at least one arm")
    seen: list[Arm] = []
    for item in raw:
        if item not in {"baseline", "alaya"}:
            raise ValueError(f"unsupported arm: {item!r}")
        arm = item  # type: ignore[assignment]
        if arm not in seen:
            seen.append(arm)
    return tuple(seen)


if __name__ == "__main__":
    raise SystemExit(main())
