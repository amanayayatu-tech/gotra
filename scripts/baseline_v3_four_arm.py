#!/usr/bin/env python3
"""Baseline v3 four-arm formal-lite harness."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Literal

import httpx
import pandas as pd

from gotra.backtest.kimi_client import KimiCompletionClient, load_env_file
from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import add_months, parse_date, ticker_slug
from gotra.backtest.statistics import (
    cluster_bootstrap_ci,
    hac_mean_test,
    paired_loss_differences_v3,
)
from scripts import baseline_v2_three_arm_pilot as v2


Arm = Literal["direct_llm", "ksana_formatting_only", "ksana_real_research", "full_gotra"]
Mode = Literal["mock", "provider-canary", "provider-pilot", "recompute"]
InputLayer = Literal["price_only_packet", "richer_research_packet"]
ScoringSegment = Literal["warm_up", "scored"]

ARMS: tuple[Arm, ...] = (
    "direct_llm",
    "ksana_formatting_only",
    "ksana_real_research",
    "full_gotra",
)
INPUT_LAYERS: tuple[InputLayer, ...] = ("price_only_packet", "richer_research_packet")
DIRECTIONS = {"long", "avoid", "neutral", "watch", "short"}
DECISION_SCHEMA = "gotra.baseline_v3.four_arm_decision.v1"
STEP_SCHEMA = "gotra.baseline_v3.four_arm_step.v1"
SUMMARY_SCHEMA = "gotra.baseline_v3.four_arm_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3.four_arm_manifest.v1"
PROMPT_SCHEMA = "gotra.baseline_v3_four_arm.prompt.v1"
DEFINITION_VERSION = "baseline-v3-four-arm-2026-06-19"
DECISION_JSON_ALLOWED_KEYS = (
    "schema",
    "arm",
    "ticker",
    "decision_date",
    "horizon_days",
    "direction",
    "expected_change_pct",
    "confidence",
    "reasoning",
    "evidence_refs",
    "ksana_refs",
    "alaya_memory_refs",
    "risk_factors",
    "abstain_reason",
    "input_cutoff",
    "future_data_allowed",
)
INPUT_ECHO_FORBIDDEN_KEYS = (
    "arm_contract",
    "output_contract",
    "raw_inputs",
    "input_policy",
    "ksana_research_workflow",
    "research_artifacts",
    "alaya_feedback_history",
    "alaya_knowledge_state",
    "provider",
    "provider_model",
    "definition_version",
)
DEFAULT_PROVIDER = v2.DEFAULT_PROVIDER
DEFAULT_GLM_MODEL = v2.DEFAULT_GLM_MODEL
DEEPSEEK_FLASH_MODEL = v2.DEEPSEEK_FLASH_MODEL
DEFAULT_GLM_BASE_URL = v2.DEFAULT_GLM_BASE_URL
DEEPSEEK_RATE_LIMITS = v2.DEEPSEEK_RATE_LIMITS
RUN_ID_PREFIX = "baseline_v3_four_arm_"
RUN_ID_PREFIX_V3_1 = "baseline_v3_1_"
RUN_ID_PREFIX_V3_2 = "baseline_v3_2_"
RUN_ID_PREFIX_V3_4 = "baseline_v3_4_"
CODEX_CLI_BACKEND = "codex_cli_llm_backend"
DEFAULT_CODEX_CLI_MODEL = "gpt-5.5"
DEFAULT_CODEX_CLI_REASONING = "low"
WINDOW_DAYS = 30
DEFAULT_TICKERS = v2.V1_PILOT_TICKERS
DEFAULT_DATES = v2.V1_PILOT_DATES
SYSTEM_PROMPT = """You are the strict JSON decision provider for Gotra Baseline v3.

Use only context whose availability_date is <= decision_date. Do not use web
search, external market data, files, tools, actual future outcomes, or any
post-decision information. Return exactly one JSON object with schema
gotra.baseline_v3.four_arm_decision.v1. Do not wrap in markdown fences. Never
copy the INPUT PACKET and never output prompt wrapper keys.
"""


ProviderRequestError = v2.ProviderRequestError
InputEchoError = v2.InputEchoError
LocalJsonCache = v2.LocalJsonCache


@dataclass(frozen=True)
class DecisionPoint:
    ticker: str
    decision_date: date
    input_layer: InputLayer


@dataclass(frozen=True)
class RunConfig:
    mode: Mode
    run_id: str
    provider: str
    provider_model: str
    provider_base_url: str
    tickers: tuple[str, ...]
    dates: tuple[date, ...]
    input_layers: tuple[InputLayer, ...]
    warm_up_dates: int
    repeat_run_index: int
    runs_root: Path
    price_dir: Path
    token_budget: int | None
    provider_concurrency: int
    max_provider_concurrency: int
    adaptive_concurrency: bool
    direct_llm_timeout_seconds: float
    ksana_formatting_only_timeout_seconds: float
    ksana_real_research_timeout_seconds: float
    full_gotra_timeout_seconds: float
    timeout_per_kb_seconds: float
    max_request_timeout_seconds: float
    timeout_retries: int
    timeout_retry_backoff_seconds: float
    scheduler_policy: str
    provider_max_tokens: int = 1200
    resume: bool = False
    research_artifacts_path: Path | None = None
    feedback_artifacts_path: Path | None = None
    codex_cli_reasoning_setting: str = DEFAULT_CODEX_CLI_REASONING
    codex_cli_binary: str = "codex"


@dataclass(frozen=True)
class ArmTask:
    point: DecisionPoint
    arm: Arm
    feedback: list[dict[str, Any]]
    feedback_filter_diagnostics: dict[str, Any]


@dataclass
class CircuitBreakerState:
    triggered: bool = False
    trigger_reason: str = ""
    attempted_steps_at_trigger: int = 0
    inflight_at_trigger: int = 0


@dataclass(frozen=True)
class PriceContext:
    price_rows: pd.DataFrame
    start_row: pd.Series
    end_row: pd.Series
    outcome_date: date


@dataclass(frozen=True)
class ProviderDecision:
    schema: str
    arm: Arm
    ticker: str
    decision_date: str
    horizon_days: int
    direction: str
    expected_change_pct: float
    confidence: float
    reasoning: str
    evidence_refs: list[str]
    ksana_refs: list[str]
    alaya_memory_refs: list[str]
    risk_factors: list[str]
    abstain_reason: str | None
    input_cutoff: str
    future_data_allowed: bool
    provider_attempts: int = 0
    provider_retry_count: int = 0
    provider_error_class: str = ""
    provider_temperature: float | None = None
    provider_temperature_fallback: bool = False
    last_retryable_error_type: str = ""
    normalization_applied: bool = False
    normalization_steps: tuple[str, ...] = ()
    normalization_failure_reason: str = ""
    backend_name: str = ""
    codex_cli_version: str = ""
    codex_cli_model: str = ""
    codex_cli_reasoning_setting: str = ""
    output_transcript_path: str = ""
    parsed_decision_hash: str = ""


class MockDecisionClient:
    provider_transport = "local_mock"

    def __init__(self, *, provider: str, provider_model: str, provider_base_url: str) -> None:
        self.provider = provider
        self.provider_model = provider_model
        self.provider_base_url = provider_base_url
        self.provider_max_tokens_applied = False
        self.provider_max_tokens_reason = "local mock does not call provider token API"
        self.last_raw_content = ""

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        del request_timeout_seconds
        features = payload["raw_inputs"]["price_features"]
        arm = normalize_arm(payload["arm"])
        research_count = len(payload.get("research_artifacts") or [])
        expected = 0.35 * features["return_21d_pct"] + 0.25 * features["return_63d_pct"]
        if arm == "ksana_formatting_only":
            expected = 0.30 * features["return_21d_pct"] + 0.20 * features["return_63d_pct"]
        elif arm == "ksana_real_research":
            expected = (
                0.45 * features["return_21d_pct"]
                + 0.35 * features["return_63d_pct"]
                + 0.05 * research_count
            )
        elif arm == "full_gotra":
            expected = (
                0.45 * features["return_21d_pct"]
                + 0.35 * features["return_63d_pct"]
                + 0.05 * research_count
            )
            errors = [
                float(item["error"])
                for item in payload.get("alaya_feedback_history") or []
                if item.get("error") is not None
            ]
            if errors:
                expected += 0.10 * sum(errors[-3:]) / min(3, len(errors))
        expected = round(max(min(expected, 25.0), -25.0), 4)
        direction = "long" if expected >= 2.0 else "avoid" if expected <= -2.0 else "neutral"
        confidence = round(min(0.85, 0.45 + abs(expected) / 60), 4)
        evidence_refs = ["adjusted_close_history"]
        evidence_refs.extend(str(item["name"]) for item in payload.get("research_artifacts") or [])
        ksana_refs = []
        if arm == "ksana_formatting_only":
            ksana_refs = ["ksana_formatting_contract"]
        elif arm in {"ksana_real_research", "full_gotra"}:
            ksana_refs = ["ksana_real_research_artifacts"]
        feedback = payload.get("alaya_feedback_history") or []
        alaya_memory_refs = [
            str(item["feedback_ref"]) for item in feedback if item.get("feedback_ref")
        ]
        return ProviderDecision(
            schema=DECISION_SCHEMA,
            arm=arm,
            ticker=str(payload["ticker"]),
            decision_date=str(payload["decision_date"]),
            horizon_days=int(payload["horizon_days"]),
            direction=direction,
            expected_change_pct=expected,
            confidence=confidence,
            reasoning=(
                f"deterministic {arm} baseline-v3 mock decision using "
                f"{', '.join(evidence_refs)}"
            ),
            evidence_refs=evidence_refs,
            ksana_refs=ksana_refs,
            alaya_memory_refs=alaya_memory_refs if arm == "full_gotra" else [],
            risk_factors=["local_mock_not_provider_evidence"],
            abstain_reason=None,
            input_cutoff=str(payload["decision_date"]),
            future_data_allowed=False,
        )


class KimiDecisionClient:
    provider = "kimi"
    provider_transport = "sophnet_chat_completions"

    def __init__(
        self,
        *,
        model: str,
        request_timeout_seconds: float,
        provider_base_url: str,
        provider_max_tokens: int,
        provider_temperature: float | None = None,
        timeout_retries: int = 1,
        timeout_retry_backoff_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.provider_model = model
        self.provider_base_url = provider_base_url
        self.provider_max_tokens = provider_max_tokens
        self.provider_temperature = (
            kimi_provider_temperature(model) if provider_temperature is None else float(provider_temperature)
        )
        self.timeout_retries = max(0, int(timeout_retries))
        self.timeout_retry_backoff_seconds = max(0.0, float(timeout_retry_backoff_seconds))
        self.provider_max_tokens_applied = True
        self.provider_max_tokens_reason = "passed to KimiCompletionClient.complete"
        self.provider_temperature_applied = True
        self.provider_temperature_reason = "Kimi/SophNet K2.6 requires explicit temperature=1"
        self.last_raw_content = ""
        self.request_timeout_seconds = request_timeout_seconds
        self.client = KimiCompletionClient(
            model=model,
            base_url=provider_base_url,
            transport=transport,
        )

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        prompt = render_provider_prompt(payload)
        attempts = 0
        retry_count = 0
        last_retryable_error_type = ""
        while True:
            attempts += 1
            try:
                completion = self.client.complete(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt,
                    max_tokens=self.provider_max_tokens,
                    timeout_seconds=int(request_timeout_seconds or self.request_timeout_seconds),
                    temperature=self.provider_temperature,
                )
                break
            except RuntimeError as exc:
                message = str(exc)
                provider_error_class = kimi_runtime_error_class(message)
                if not kimi_runtime_error_is_retryable(message, provider_error_class):
                    raise ProviderRequestError(
                        message,
                        provider_error_class=provider_error_class,
                        provider_attempts=attempts,
                        provider_retry_count=retry_count,
                    ) from exc
                last_retryable_error_type = provider_error_class
                if retry_count >= self.timeout_retries:
                    error = ProviderRequestError(
                        message,
                        provider_error_class=provider_error_class,
                        provider_attempts=attempts,
                        provider_retry_count=retry_count,
                    )
                    error.last_retryable_error_type = last_retryable_error_type
                    raise error from exc
                retry_count += 1
                if self.timeout_retry_backoff_seconds > 0:
                    time.sleep(self.timeout_retry_backoff_seconds)
        self.last_raw_content = str(completion.get("content", ""))
        decision = _parse_raw_provider_content(
            raw_content=self.last_raw_content,
            attempts=attempts,
            retry_count=retry_count,
        )
        return replace(
            decision,
            provider_temperature=self.provider_temperature,
            last_retryable_error_type=last_retryable_error_type,
        )


def kimi_runtime_error_class(message: str) -> str:
    lowered = message.lower()
    if "http 429" in lowered:
        return "HTTP_429"
    if "timed out" in lowered or "timeout" in lowered:
        return "TimeoutException"
    if "not valid json" in lowered or "did not contain message content" in lowered:
        return "InvalidResponse"
    return "provider_http_error"


def kimi_runtime_error_is_retryable(message: str, provider_error_class: str) -> bool:
    lowered = message.lower()
    if provider_error_class == "TimeoutException":
        return True
    if provider_error_class == "provider_http_error":
        retryable_markers = (
            "http 500",
            "http 502",
            "http 503",
            "http 504",
            "proxyerror",
            "proxy error",
            "connecterror",
            "connect error",
            "readerror",
            "read error",
            "remoteprotocolerror",
            "network",
        )
        return any(marker in lowered for marker in retryable_markers)
    return False


class GlmSophnetDecisionClient(v2.GlmSophnetDecisionClient):
    provider = "glm_sophnet"
    provider_transport = "sophnet_chat_completions"

    def __init__(
        self,
        *,
        model: str = DEFAULT_GLM_MODEL,
        base_url: str = DEFAULT_GLM_BASE_URL,
        request_timeout_seconds: float = 480,
        timeout_retries: int = 1,
        timeout_retry_backoff_seconds: float = 30,
        provider_max_tokens: int = 1200,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            model=model,
            base_url=base_url,
            request_timeout_seconds=request_timeout_seconds,
            timeout_retries=timeout_retries,
            timeout_retry_backoff_seconds=timeout_retry_backoff_seconds,
            transport=transport,
        )
        self.provider_max_tokens = max(1, int(provider_max_tokens))
        self.provider_max_tokens_applied = True
        self.provider_max_tokens_reason = "included in SophNet chat completions request body"
        self.last_raw_content = ""

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        api_key = v2.sophnet_api_key()
        if not api_key:
            raise ProviderRequestError(
                "SOPHNET_API_KEY/API_KEY=not_set",
                provider_error_class="AuthMissing",
            )
        prompt = render_provider_prompt(payload)
        timeout_seconds = request_timeout_seconds or self.request_timeout_seconds
        (
            body,
            provider_attempts,
            provider_retry_count,
            provider_temperature_fallback,
        ) = self._post_with_timeout_retry(
            prompt=prompt,
            api_key=api_key,
            request_timeout_seconds=timeout_seconds,
        )
        raw_content = v2.extract_chat_content(body)
        self.last_raw_content = raw_content
        decision = _parse_raw_provider_content(
            raw_content=raw_content,
            attempts=provider_attempts,
            retry_count=provider_retry_count,
        )
        return replace(
            decision,
            provider_temperature_fallback=provider_temperature_fallback,
        )

    def _send(
        self,
        *,
        prompt: str,
        api_key: str,
        include_temperature: bool,
        request_timeout_seconds: float,
    ) -> httpx.Response:
        request = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "model": self.provider_model,
            "max_tokens": self.provider_max_tokens,
            "stream": False,
        }
        if include_temperature:
            request["temperature"] = 0
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(transport=self.transport, timeout=request_timeout_seconds) as client:
                return client.post(self.base_url, headers=headers, json=request)
        except httpx.HTTPError as exc:
            if isinstance(exc, httpx.TimeoutException):
                raise
            raise ProviderRequestError(
                f"GLM SophNet request failed: {type(exc).__name__}",
                provider_error_class=type(exc).__name__,
            ) from exc


class CodexCliBackendDecisionClient:
    provider = CODEX_CLI_BACKEND
    provider_transport = CODEX_CLI_BACKEND

    def __init__(
        self,
        *,
        model: str,
        reasoning_setting: str,
        run_root: Path,
        provider_max_tokens: int,
        codex_binary: str = "codex",
        project_root: Path | None = None,
        completion_client: Any | None = None,
        codex_cli_version_text: str | None = None,
    ) -> None:
        self.provider_model = model or DEFAULT_CODEX_CLI_MODEL
        self.provider_base_url = "local://codex-cli"
        self.provider_max_tokens = max(1, int(provider_max_tokens))
        self.codex_cli_reasoning_setting = reasoning_setting or DEFAULT_CODEX_CLI_REASONING
        self.codex_cli_binary = codex_binary
        self.project_root = project_root or Path.cwd()
        self.run_root = run_root
        self.completion_client = completion_client
        self.codex_cli_version = codex_cli_version_text or codex_cli_version(codex_binary)
        self.provider_max_tokens_applied = True
        self.provider_max_tokens_reason = "prompt guidance passed to Codex CLI backend"
        self.provider_temperature_applied = False
        self.provider_temperature_reason = "Codex CLI backend has prompt guidance only"
        self.last_raw_content = ""

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        prompt = render_provider_prompt(payload)
        transcript_path = codex_cli_transcript_path(self.run_root, payload)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        timeout_seconds = int(request_timeout_seconds or 900)
        if self.completion_client is not None:
            raw_content = str(
                self.completion_client.complete(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt,
                    max_tokens=self.provider_max_tokens,
                    timeout_seconds=timeout_seconds,
                    temperature=0.0,
                )
            )
            transcript_path.write_text(
                redact_sensitive_text(raw_content),
                encoding="utf-8",
            )
        else:
            raw_content = self._complete_with_codex_cli(
                prompt=prompt,
                transcript_path=transcript_path,
                timeout_seconds=timeout_seconds,
            )
        self.last_raw_content = raw_content
        try:
            decision = _parse_raw_provider_content(
                raw_content=raw_content,
                attempts=1,
                retry_count=0,
            )
        except ProviderRequestError as exc:
            exc.output_transcript_path = str(transcript_path)
            exc.codex_cli_version = self.codex_cli_version
            exc.codex_cli_model = self.provider_model
            exc.codex_cli_reasoning_setting = self.codex_cli_reasoning_setting
            raise
        parsed_hash = stable_json_hash(decision_to_cache_payload(decision))
        return replace(
            decision,
            backend_name=CODEX_CLI_BACKEND,
            codex_cli_version=self.codex_cli_version,
            codex_cli_model=self.provider_model,
            codex_cli_reasoning_setting=self.codex_cli_reasoning_setting,
            output_transcript_path=str(transcript_path),
            parsed_decision_hash=parsed_hash,
        )

    def _complete_with_codex_cli(
        self,
        *,
        prompt: str,
        transcript_path: Path,
        timeout_seconds: int,
    ) -> str:
        if not shutil.which(self.codex_cli_binary):
            raise ProviderRequestError(
                "codex CLI is not installed or not on PATH",
                provider_error_class="CodexCliBackendBlocked",
            )
        provider_prompt = build_codex_cli_backend_prompt(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.provider_max_tokens,
        )
        command = [
            self.codex_cli_binary,
            "--ask-for-approval",
            "never",
            "exec",
            "--ignore-user-config",
            "-c",
            f'model_reasoning_effort="{self.codex_cli_reasoning_setting}"',
            "--cd",
            str(self.project_root),
            "--sandbox",
            "read-only",
            "--output-last-message",
            str(transcript_path),
        ]
        if self.provider_model:
            command.extend(["--model", self.provider_model])
        command.append(provider_prompt)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                cwd=self.project_root,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderRequestError(
                "Codex CLI backend timed out",
                provider_error_class="TimeoutException",
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderRequestError(
                "codex CLI is not installed or not on PATH",
                provider_error_class="CodexCliBackendBlocked",
            ) from exc
        if completed.returncode != 0:
            detail = redact_error((completed.stderr or completed.stdout or "").strip())
            raise ProviderRequestError(
                "Codex CLI backend failed"
                + (f": {detail[:500]}" if detail else ""),
                provider_error_class="CodexCliBackendBlocked",
            )
        raw_content = ""
        if transcript_path.exists():
            raw_content = transcript_path.read_text(encoding="utf-8").strip()
        if not raw_content:
            raw_content = (completed.stdout or "").strip()
            if raw_content:
                transcript_path.write_text(
                    redact_sensitive_text(raw_content),
                    encoding="utf-8",
                )
        if not transcript_path.exists() or not raw_content:
            raise ProviderRequestError(
                "Codex CLI backend did not capture an output transcript",
                provider_error_class="CodexCliBackendBlocked",
            )
        return raw_content


def build_codex_cli_backend_prompt(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> str:
    return f"""You are Codex CLI acting as the {CODEX_CLI_BACKEND} decision backend for GOTRA v3.4.

Hard constraints:
- Do not modify files, run commands, call web search, call APIs, or inspect secrets.
- Use only the supplied prompt context. Do not add external market data.
- Return exactly one strict JSON object matching the requested decision schema.
- Do not wrap JSON in Markdown fences and do not add prose before or after it.
- Keep the response within roughly {max_tokens} tokens.

<system_prompt>
{system_prompt}
</system_prompt>

<user_prompt>
{user_prompt}
</user_prompt>
"""


def codex_cli_transcript_path(run_root: Path, payload: dict[str, Any]) -> Path:
    arm = normalize_arm(payload.get("arm"))
    input_layer = normalize_input_layer(payload.get("input_layer"))
    decision_date = str(payload.get("decision_date"))
    ticker = ticker_slug(str(payload.get("ticker")))
    return (
        run_root
        / "codex_cli_transcripts"
        / arm
        / f"transcript_{decision_date}_{ticker}_{input_layer}.txt"
    )


def codex_cli_version(codex_binary: str = "codex") -> str:
    if not shutil.which(codex_binary):
        return ""
    try:
        completed = subprocess.run(
            [codex_binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:  # noqa: BLE001 - preflight reports a backend blocker.
        return ""
    if completed.returncode != 0:
        return ""
    return (completed.stdout or completed.stderr or "").strip().splitlines()[0]


def _parse_raw_provider_content(
    *,
    raw_content: str,
    attempts: int,
    retry_count: int = 0,
) -> ProviderDecision:
    try:
        return replace(
            parse_provider_decision(raw_content),
            provider_attempts=attempts,
            provider_retry_count=retry_count,
        )
    except InputEchoError as exc:
        _normalized, metadata = normalize_provider_decision_content(raw_content)
        raise ProviderRequestError(
            "provider response echoed the input packet instead of decision JSON",
            provider_error_class="InputEchoError",
            provider_attempts=attempts,
            provider_retry_count=retry_count,
            raw_content=raw_content,
            normalization_metadata=metadata,
            input_echo_detected_keys=exc.detected_keys,
        ) from exc
    except json.JSONDecodeError as exc:
        _normalized, metadata = normalize_provider_decision_content(raw_content)
        raise ProviderRequestError(
            "provider response content was not valid v3 decision JSON",
            provider_error_class="JSONDecodeError",
            provider_attempts=attempts,
            provider_retry_count=retry_count,
            raw_content=raw_content,
            normalization_metadata=metadata,
        ) from exc
    except (KeyError, TypeError, ValueError) as exc:
        _normalized, metadata = normalize_provider_decision_content(raw_content)
        raise ProviderRequestError(
            str(exc),
            provider_error_class="SchemaContractError",
            provider_attempts=attempts,
            provider_retry_count=retry_count,
            raw_content=raw_content,
            normalization_metadata=metadata,
        ) from exc


def parse_bool(value: str | bool) -> bool:
    return v2.parse_bool(value)


def normalize_arm(value: Any) -> Arm:
    normalized = str(value or "").strip()
    if normalized not in ARMS:
        raise ValueError(f"invalid arm: {value!r}")
    return normalized  # type: ignore[return-value]


def normalize_input_layer(value: Any) -> InputLayer:
    normalized = str(value or "").strip()
    if normalized not in INPUT_LAYERS:
        raise ValueError(f"invalid input_layer: {value!r}")
    return normalized  # type: ignore[return-value]


def json_number_field(payload: dict[str, Any], field: str) -> float:
    value = payload[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a JSON number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def parse_provider_decision(value: str | dict[str, Any]) -> ProviderDecision:
    normalization_metadata = default_normalization_metadata()
    if isinstance(value, str):
        raw_input_echo_keys = detect_input_echo_raw_content(value)
        normalized_value, normalization_metadata = normalize_provider_decision_content(value)
        try:
            payload = json.loads(normalized_value)
        except json.JSONDecodeError as exc:
            if raw_input_echo_keys:
                raise InputEchoError(raw_input_echo_keys) from exc
            raise
    else:
        payload = dict(value)
    unexpected_keys = sorted(set(payload) - set(DECISION_JSON_ALLOWED_KEYS))
    if unexpected_keys:
        raise ValueError("unexpected decision JSON keys: " + ",".join(unexpected_keys))
    schema = str(payload.get("schema") or "")
    if schema != DECISION_SCHEMA:
        raise ValueError(f"invalid decision schema: {schema!r}")
    arm = normalize_arm(payload.get("arm"))
    ticker = str(payload.get("ticker") or "")
    decision_date = str(payload.get("decision_date") or "")
    if not ticker:
        raise ValueError("ticker is required")
    parse_date(decision_date)
    horizon_days = int(payload.get("horizon_days"))
    direction = normalize_direction(payload.get("direction"))
    expected = json_number_field(payload, "expected_change_pct")
    confidence = json_number_field(payload, "confidence")
    if not 0 <= confidence <= 1:
        raise ValueError(f"confidence out of range: {confidence}")
    evidence_refs = payload.get("evidence_refs")
    if evidence_refs is None:
        evidence_refs = []
    if not isinstance(evidence_refs, list):
        raise ValueError("evidence_refs must be a list")
    ksana_refs = list_field(payload, "ksana_refs")
    alaya_memory_refs = list_field(payload, "alaya_memory_refs")
    risk_factors = list_field(payload, "risk_factors")
    if arm == "direct_llm" and (ksana_refs or alaya_memory_refs):
        raise ValueError("direct_llm must not include ksana_refs or alaya_memory_refs")
    if arm in {"ksana_formatting_only", "ksana_real_research"} and alaya_memory_refs:
        raise ValueError(f"{arm} must not include alaya_memory_refs")
    abstain_reason = payload.get("abstain_reason")
    if abstain_reason is not None:
        abstain_reason = str(abstain_reason)
    reasoning = str(payload.get("reasoning") or "")
    if not reasoning:
        raise ValueError("reasoning is required")
    input_cutoff = str(payload.get("input_cutoff") or "")
    if parse_date(input_cutoff) != parse_date(decision_date):
        raise ValueError("input_cutoff must equal decision_date")
    if payload.get("future_data_allowed") is not False:
        raise ValueError("future_data_allowed must be false")
    return ProviderDecision(
        schema=schema,
        arm=arm,
        ticker=ticker,
        decision_date=decision_date,
        horizon_days=horizon_days,
        direction=direction,
        expected_change_pct=expected,
        confidence=confidence,
        reasoning=reasoning,
        evidence_refs=[str(item) for item in evidence_refs],
        ksana_refs=ksana_refs,
        alaya_memory_refs=alaya_memory_refs,
        risk_factors=risk_factors,
        abstain_reason=abstain_reason,
        input_cutoff=input_cutoff,
        future_data_allowed=False,
        normalization_applied=bool(normalization_metadata["normalization_applied"]),
        normalization_steps=tuple(str(item) for item in normalization_metadata["normalization_steps"]),
        normalization_failure_reason=str(normalization_metadata["normalization_failure_reason"]),
    )


def list_field(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(item) for item in value]


def strip_json_fence(value: str) -> str:
    normalized, _metadata = normalize_provider_decision_content(value)
    return normalized


def default_normalization_metadata() -> dict[str, Any]:
    return v2.default_normalization_metadata()


def detect_input_echo_payload(payload: dict[str, Any]) -> list[str]:
    return sorted(key for key in INPUT_ECHO_FORBIDDEN_KEYS if key in payload)


def detect_input_echo_raw_content(content: str, *, prefix_chars: int = 2000) -> list[str]:
    prefix = str(content)[:prefix_chars]
    detected: list[str] = []
    for key in INPUT_ECHO_FORBIDDEN_KEYS:
        if f'"{key}"' in prefix or f"'{key}'" in prefix:
            detected.append(key)
    return sorted(detected)


def normalize_provider_decision_content(content: str) -> tuple[str, dict[str, Any]]:
    return v2.normalize_provider_decision_content(content)


def normalize_direction(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "buy": "long",
        "sell": "short",
        "hold": "neutral",
        "none": "neutral",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in DIRECTIONS:
        raise ValueError(f"invalid direction: {value!r}")
    return normalized


def cache_key_for(
    *,
    arm: Arm,
    input_layer: InputLayer,
    provider: str,
    provider_model: str,
    provider_base_url: str,
    provider_max_tokens: int,
    provider_temperature: float | None = None,
    prompt_hash: str,
    definition_version: str = DEFINITION_VERSION,
) -> str:
    return ":".join(
        [
            "baseline_v3",
            definition_version,
            provider,
            provider_model,
            provider_base_url,
            f"max_tokens={int(provider_max_tokens)}",
            f"temperature={provider_temperature_identity(provider_temperature)}",
            arm,
            input_layer,
            prompt_hash,
        ]
    )


def stable_json_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def kimi_provider_temperature(_model: str) -> float:
    return 1.0


def provider_temperature_for(provider: str, provider_model: str) -> float | None:
    if provider == "kimi":
        return kimi_provider_temperature(provider_model)
    return None


def provider_temperature_identity(provider_temperature: float | None) -> str:
    if provider_temperature is None:
        return "omitted"
    return f"{float(provider_temperature):g}"


def build_prompt_payload(
    *,
    arm: Arm,
    input_layer: InputLayer,
    ticker: str,
    decision_date: date,
    price_rows: pd.DataFrame,
    feedback: list[dict[str, Any]],
    provider: str,
    provider_model: str,
    scoring_segment: ScoringSegment = "scored",
    research_artifacts_path: Path | None = None,
    research_artifacts_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    latest = price_rows.iloc[-1]
    research_artifacts = (
        research_artifacts_override
        if research_artifacts_override is not None
        else research_artifacts_for(
            arm=arm,
            input_layer=input_layer,
            decision_date=decision_date,
            price_rows=price_rows,
            research_artifacts_path=research_artifacts_path,
            ticker=ticker,
        )
    )
    payload: dict[str, Any] = {
        "schema": PROMPT_SCHEMA,
        "definition_version": DEFINITION_VERSION,
        "arm": arm,
        "input_layer": input_layer,
        "scoring_segment": scoring_segment,
        "ticker": ticker,
        "decision_date": decision_date.isoformat(),
        "horizon_days": WINDOW_DAYS,
        "provider": provider,
        "provider_model": provider_model,
        "input_policy": {
            "decision_inputs_available_on_or_before": decision_date.isoformat(),
            "input_layer": input_layer,
            "richer_research_enabled": input_layer == "richer_research_packet",
            "direct_llm_richer_packet_contract": (
                "direct_llm receives raw time-bounded research_artifacts when "
                "input_layer=richer_research_packet, but never ksana workflow output "
                "or alaya feedback"
            ),
            "actual_outcome_visible": False,
            "network_research_enabled": False,
        },
        "raw_inputs": {
            "price_history_latest_date": str(latest["date"]),
            "latest_adjusted_close": round(float(latest["adj_close"]), 6),
            "price_features": price_features(price_rows),
            "recent_adjusted_close": compact_price_rows(price_rows),
        },
        "arm_contract": arm_prompt_contract(arm),
        "output_contract": {
            "schema": DECISION_SCHEMA,
            "arm": arm,
            "ticker": ticker,
            "decision_date": decision_date.isoformat(),
            "horizon_days": WINDOW_DAYS,
            "direction": "long|avoid|neutral|watch|short",
            "expected_change_pct": "number",
            "confidence": "number in [0, 1]",
            "reasoning": "string",
            "evidence_refs": "list",
            "ksana_refs": arm_ksana_refs_contract(arm),
            "alaya_memory_refs": arm_alaya_memory_refs_contract(arm, feedback),
            "risk_factors": "list",
            "abstain_reason": "string|null",
            "input_cutoff": decision_date.isoformat(),
            "future_data_allowed": False,
        },
    }
    if research_artifacts:
        payload["research_artifacts"] = research_artifacts
    if arm in {"ksana_formatting_only", "ksana_real_research", "full_gotra"}:
        payload["ksana_research_workflow"] = ksana_workflow_for(arm)
    if arm == "full_gotra":
        payload["alaya_feedback_history"] = feedback
        payload["alaya_knowledge_state"] = {
            "history_feedback_allowed": True,
            "strong_knowledge_auto_approval_allowed": False,
            "human_gate_required_for_strong": True,
            "quarantined_conflict_stale_filtered": True,
        }
    return payload


def research_artifacts_for(
    *,
    arm: Arm,
    input_layer: InputLayer,
    decision_date: date,
    price_rows: pd.DataFrame,
    research_artifacts_path: Path | None = None,
    ticker: str = "",
) -> list[dict[str, Any]]:
    return research_artifact_filter_result(
        arm=arm,
        input_layer=input_layer,
        decision_date=decision_date,
        price_rows=price_rows,
        research_artifacts_path=research_artifacts_path,
        ticker=ticker,
    )["accepted_artifacts"]


def research_artifact_filter_result(
    *,
    arm: Arm,
    input_layer: InputLayer,
    decision_date: date,
    price_rows: pd.DataFrame,
    research_artifacts_path: Path | None = None,
    ticker: str = "",
) -> dict[str, Any]:
    if input_layer != "richer_research_packet":
        return empty_research_artifact_filter_result()
    if arm == "ksana_formatting_only":
        return empty_research_artifact_filter_result()
    if research_artifacts_path:
        return filter_external_research_artifacts(
            load_research_artifact_fixture(research_artifacts_path),
            decision_date=decision_date,
            ticker=ticker,
        )
    latest = price_rows.iloc[-1]
    source_date = str(latest["date"])
    return {
        "accepted_artifacts": [
        {
            "name": "synthetic_news_context",
            "kind": "news_items",
            "source": "local_synthetic_fixture",
            "source_kind": "synthetic",
            "availability_date": min(parse_date(source_date), decision_date).isoformat(),
            "summary": "Synthetic time-bounded event context for harness validation.",
        },
        {
            "name": "synthetic_fundamentals_snapshot",
            "kind": "fundamentals_snapshot",
            "source": "local_synthetic_fixture",
            "source_kind": "synthetic",
            "availability_date": min(parse_date(source_date), decision_date).isoformat(),
            "summary": "Synthetic snapshot used only to exercise richer packet plumbing.",
        },
        ],
        "rejected_research_artifact_count": 0,
        "rejected_research_future_data_count": 0,
        "rejected_research_schema_count": 0,
    }


REQUIRED_RESEARCH_ARTIFACT_FIELDS = {
    "ticker",
    "source_name",
    "source_url_or_id",
    "publish_timestamp",
    "availability_date",
    "source_kind",
    "retrieval_method",
    "evidence_ref",
    "summary",
}
FORBIDDEN_RESEARCH_ARTIFACT_FIELDS = {
    "actual_change_pct",
    "future_return",
    "outcome",
    "realized_after_decision",
    "window_end_price",
    "future_price",
}
REQUIRED_FEEDBACK_ARTIFACT_FIELDS = {
    "ticker",
    "feedback_ref",
    "feedback_source_kind",
    "availability_date",
    "source_run_id",
    "source_step_id",
    "source_decision_date",
    "source_horizon_end_date",
    "actual_return",
    "prior_prediction",
}
TRUE_INDEPENDENT_FEEDBACK_SOURCE_KINDS = {
    "outcome_feedback",
    "realized_error_feedback",
}
NON_INDEPENDENT_FEEDBACK_SOURCE_KINDS = {
    "self_feedback",
    "synthetic_feedback",
}
FORBIDDEN_FEEDBACK_ARTIFACT_FIELDS = {
    "current_actual_return",
    "current_step_output",
    "future_return",
    "outcome_after_current_decision",
    "realized_after_current_decision",
    "same_date_future_outcome",
}


def empty_research_artifact_filter_result() -> dict[str, Any]:
    return {
        "accepted_artifacts": [],
        "rejected_research_artifact_count": 0,
        "rejected_research_future_data_count": 0,
        "rejected_research_schema_count": 0,
    }


def load_research_artifact_fixture(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if path.suffix.lower() == ".csv":
        return [dict(row) for row in pd.read_csv(path).to_dict(orient="records")]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("artifacts", [])
    if not isinstance(payload, list):
        raise ValueError("research artifact fixture must be a list or {'artifacts': [...]}")
    return [dict(item) for item in payload if isinstance(item, dict)]


def load_feedback_artifact_fixture(path: Path) -> list[Any]:
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("feedback_artifacts", payload.get("artifacts", []))
    if not isinstance(payload, list):
        raise ValueError("feedback artifact fixture must be a list or {'feedback_artifacts': [...]}")
    return list(payload)


def filter_external_research_artifacts(
    artifacts: list[dict[str, Any]],
    *,
    decision_date: date,
    ticker: str,
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected_future = 0
    rejected_schema = 0
    for artifact in artifacts:
        artifact_ticker = str(artifact.get("ticker") or "")
        if artifact_ticker not in {ticker, "*"}:
            continue
        missing = REQUIRED_RESEARCH_ARTIFACT_FIELDS - set(artifact)
        source_kind = str(artifact.get("source_kind") or "")
        forbidden = sorted(FORBIDDEN_RESEARCH_ARTIFACT_FIELDS & set(artifact))
        if missing or source_kind not in {"real", "unverified", "synthetic"}:
            rejected_schema += 1
            continue
        if forbidden or parse_date(str(artifact["availability_date"])) > decision_date:
            rejected_future += 1
            continue
        accepted.append(normalize_research_artifact(artifact))
    return {
        "accepted_artifacts": accepted,
        "rejected_research_artifact_count": rejected_future + rejected_schema,
        "rejected_research_future_data_count": rejected_future,
        "rejected_research_schema_count": rejected_schema,
    }


def research_filter_diagnostics(result: dict[str, Any]) -> dict[str, int]:
    return {
        "rejected_research_artifact_count": int(result.get("rejected_research_artifact_count") or 0),
        "rejected_research_future_data_count": int(
            result.get("rejected_research_future_data_count") or 0
        ),
        "rejected_research_schema_count": int(result.get("rejected_research_schema_count") or 0),
    }


def normalize_research_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(artifact["evidence_ref"]),
        "kind": "research_artifact",
        "source": str(artifact["source_url_or_id"]),
        "source_kind": str(artifact["source_kind"]),
        "source_family": str(artifact.get("source_family") or ""),
        "availability_date": str(artifact["availability_date"]),
        "captured_at": str(artifact.get("captured_at") or artifact["publish_timestamp"]),
        "summary": str(artifact["summary"]),
        "text": str(artifact.get("text") or artifact["summary"]),
        "ticker": str(artifact["ticker"]),
        "source_name": str(artifact["source_name"]),
        "source_url_or_id": str(artifact["source_url_or_id"]),
        "source_url": str(artifact.get("source_url") or artifact["source_url_or_id"]),
        "source_id": str(artifact.get("source_id") or artifact["source_url_or_id"]),
        "publish_timestamp": str(artifact["publish_timestamp"]),
        "retrieval_method": str(artifact["retrieval_method"]),
        "evidence_ref": str(artifact["evidence_ref"]),
        "decision_date_scope": artifact.get("decision_date_scope"),
        "decision_date_max": artifact.get("decision_date_max"),
        "provenance_hash": str(artifact.get("provenance_hash") or ""),
    }


def empty_feedback_artifact_filter_result() -> dict[str, Any]:
    return {
        "accepted_feedback": [],
        "rejected_feedback_artifact_count": 0,
        "rejected_feedback_future_data_count": 0,
        "rejected_feedback_schema_count": 0,
        "rejected_feedback_non_independent_count": 0,
        "rejected_feedback_current_run_count": 0,
        "rejected_feedback_duplicate_count": 0,
        "feedback_source_kind_counts": feedback_source_kind_counts_for_feedback([]),
    }


def feedback_artifact_filter_result(
    *,
    feedback_artifacts_path: Path | None,
    decision_date: date,
    ticker: str,
    input_layer: InputLayer,
    current_run_id: str = "",
) -> dict[str, Any]:
    if not feedback_artifacts_path:
        return empty_feedback_artifact_filter_result()
    return filter_external_feedback_artifacts(
        load_feedback_artifact_fixture(feedback_artifacts_path),
        decision_date=decision_date,
        ticker=ticker,
        input_layer=input_layer,
        current_run_id=current_run_id,
    )


def filter_external_feedback_artifacts(
    artifacts: list[Any],
    *,
    decision_date: date,
    ticker: str,
    input_layer: InputLayer,
    current_run_id: str = "",
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected_future = 0
    rejected_schema = 0
    rejected_non_independent = 0
    rejected_current_run = 0
    rejected_duplicate = 0
    accepted_keys: set[tuple[str, ...]] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            rejected_schema += 1
            continue
        artifact_ticker = str(artifact.get("ticker") or "")
        artifact_input_layer = str(artifact.get("input_layer") or "*")
        if artifact_ticker not in {ticker, "*"}:
            continue
        if artifact_input_layer not in {input_layer, "*"}:
            continue
        source_kind = str(artifact.get("feedback_source_kind") or artifact.get("source_kind") or "")
        missing = REQUIRED_FEEDBACK_ARTIFACT_FIELDS - set(artifact)
        forbidden = sorted(FORBIDDEN_FEEDBACK_ARTIFACT_FIELDS & set(artifact))
        if missing or source_kind not in (
            TRUE_INDEPENDENT_FEEDBACK_SOURCE_KINDS | NON_INDEPENDENT_FEEDBACK_SOURCE_KINDS
        ):
            rejected_schema += 1
            continue
        if forbidden:
            rejected_future += 1
            continue
        try:
            availability_date = parse_date(str(artifact["availability_date"]))
            horizon_end_date = parse_date(str(artifact["source_horizon_end_date"]))
            source_decision_date = parse_date(str(artifact["source_decision_date"]))
        except Exception:  # noqa: BLE001 - fixture rows are untrusted inputs.
            rejected_schema += 1
            continue
        if (
            availability_date > decision_date
            or horizon_end_date > decision_date
            or source_decision_date >= decision_date
        ):
            rejected_future += 1
            continue
        if current_run_id and str(artifact.get("source_run_id") or "") == current_run_id:
            rejected_current_run += 1
            continue
        if source_kind not in TRUE_INDEPENDENT_FEEDBACK_SOURCE_KINDS:
            rejected_non_independent += 1
            continue
        try:
            normalized = normalize_feedback_artifact(
                artifact, current_decision_date=decision_date
            )
        except Exception:  # noqa: BLE001 - malformed numeric/provenance fields are rejected.
            rejected_schema += 1
            continue
        unique_key = feedback_unique_key(normalized)
        if unique_key in accepted_keys:
            rejected_duplicate += 1
            continue
        accepted_keys.add(unique_key)
        accepted.append(normalized)
    return {
        "accepted_feedback": accepted,
        "rejected_feedback_artifact_count": (
            rejected_future
            + rejected_schema
            + rejected_non_independent
            + rejected_current_run
            + rejected_duplicate
        ),
        "rejected_feedback_future_data_count": rejected_future,
        "rejected_feedback_schema_count": rejected_schema,
        "rejected_feedback_non_independent_count": rejected_non_independent,
        "rejected_feedback_current_run_count": rejected_current_run,
        "rejected_feedback_duplicate_count": rejected_duplicate,
        "feedback_source_kind_counts": feedback_source_kind_counts_for_feedback(accepted),
    }


def normalize_feedback_artifact(
    artifact: dict[str, Any],
    *,
    current_decision_date: date,
) -> dict[str, Any]:
    availability_date = str(artifact["availability_date"])
    source_kind = str(artifact["feedback_source_kind"])
    actual_return = finite_float_field(artifact, "actual_return")
    prior_prediction = finite_float_field(artifact, "prior_prediction")
    computed_error = actual_return - prior_prediction
    error = finite_float_field(artifact, "error", default=computed_error)
    computed_mse = computed_error * computed_error
    mse = finite_float_field(artifact, "mse", default=computed_mse)
    if abs(mse - computed_mse) > 1e-6:
        raise ValueError("feedback mse must match squared realized error")
    return {
        "feedback_ref": str(artifact["feedback_ref"]),
        "ticker": str(artifact["ticker"]),
        "input_layer": str(artifact.get("input_layer") or "*"),
        "prior_decision_date": str(artifact["source_decision_date"]),
        "decision_date": str(artifact["source_decision_date"]),
        "source_decision_date": str(artifact["source_decision_date"]),
        "source_horizon_end_date": str(artifact["source_horizon_end_date"]),
        "outcome_availability_date": availability_date,
        "availability_date": availability_date,
        "age_days": (current_decision_date - parse_date(availability_date)).days,
        "feedback_source_kind": source_kind,
        "source_kind": source_kind,
        "source_run_id": str(artifact["source_run_id"]),
        "source_step_id": str(artifact["source_step_id"]),
        "actual_return": actual_return,
        "prior_prediction": prior_prediction,
        "error": error,
        "mse": mse,
        "summary": str(artifact.get("summary") or ""),
    }


def finite_float_field(
    artifact: dict[str, Any],
    field: str,
    *,
    default: float | None = None,
) -> float:
    value = artifact.get(field)
    if value is None:
        if default is None:
            raise ValueError(f"{field} is required")
        value = default
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def feedback_unique_key(item: dict[str, Any]) -> tuple[str, ...]:
    feedback_ref = str(item.get("feedback_ref") or "")
    if feedback_ref:
        return ("feedback_ref", feedback_ref)
    source_step_id = str(item.get("source_step_id") or "")
    if source_step_id:
        return ("source_step_id", source_step_id)
    return (
        "provenance",
        str(item.get("source_run_id") or ""),
        str(item.get("source_step_id") or ""),
        str(item.get("source_decision_date") or ""),
        str(item.get("source_horizon_end_date") or ""),
        str(item.get("feedback_source_kind") or item.get("source_kind") or ""),
    )


def unique_feedback_artifacts(feedback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    output: list[dict[str, Any]] = []
    for item in feedback:
        key = feedback_unique_key(item)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def feedback_filter_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "rejected_feedback_artifact_count": int(result.get("rejected_feedback_artifact_count") or 0),
        "rejected_feedback_future_data_count": int(
            result.get("rejected_feedback_future_data_count") or 0
        ),
        "rejected_feedback_schema_count": int(result.get("rejected_feedback_schema_count") or 0),
        "rejected_feedback_non_independent_count": int(
            result.get("rejected_feedback_non_independent_count") or 0
        ),
        "rejected_feedback_current_run_count": int(
            result.get("rejected_feedback_current_run_count") or 0
        ),
        "rejected_feedback_duplicate_count": int(
            result.get("rejected_feedback_duplicate_count") or 0
        ),
        "feedback_source_kind_counts": dict(
            result.get("feedback_source_kind_counts")
            or feedback_source_kind_counts_for_feedback([])
        ),
    }


def feedback_filter_diagnostics_empty() -> dict[str, Any]:
    return feedback_filter_diagnostics(empty_feedback_artifact_filter_result())


def ksana_workflow_for(arm: Arm) -> dict[str, str]:
    if arm == "ksana_formatting_only":
        return {
            "F_partner": "Use only included price-derived evidence.",
            "W_partner": "Use only included price momentum evidence.",
            "G_partner": "Use only included price-risk proxy evidence.",
            "Chairman": "Reconcile F/W/G without independent research artifacts.",
        }
    return {
        "F_partner": "Use time-bounded research artifacts and price evidence.",
        "W_partner": "Use time-bounded market psychology and catalyst context.",
        "G_partner": "Use time-bounded governance, risk, and quality context.",
        "Chairman": "Reconcile research artifacts and price packet into one decision.",
    }


def render_provider_prompt(payload: dict[str, Any]) -> str:
    arm = normalize_arm(payload.get("arm"))
    arm_contract = payload.get("arm_contract") if isinstance(payload.get("arm_contract"), dict) else {}
    task = str(arm_contract.get("task") or "Make one time-bounded decision for this arm.")
    input_packet = {
        key: value
        for key, value in payload.items()
        if key
        not in {"schema", "definition_version", "provider", "provider_model", "arm_contract", "output_contract"}
    }
    forbidden_keys = ", ".join(INPUT_ECHO_FORBIDDEN_KEYS)
    allowed_keys = json.dumps(list(DECISION_JSON_ALLOWED_KEYS), ensure_ascii=False)
    arm_contract_text = json.dumps(arm_contract, ensure_ascii=False, sort_keys=True, indent=2)
    output_contract_text = json.dumps(
        payload.get("output_contract") or {},
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    ref_rules = arm_specific_ref_rules(payload)
    ref_rules_text = "\n".join(f"- {rule}" for rule in ref_rules)
    skeleton_text = json.dumps(
        decision_json_skeleton(payload),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    input_packet_text = json.dumps(input_packet, ensure_ascii=False, sort_keys=True, indent=2)
    return "\n".join(
        [
            "TASK:",
            task,
            "",
            "OUTPUT REQUIREMENTS:",
            "- Return DECISION_JSON only.",
            "- Return exactly one JSON object.",
            "- The first non-whitespace character must be {.",
            "- The last non-whitespace character must be }.",
            "- Do not use markdown fences.",
            "- Do not add prose before or after the JSON object.",
            "- Do not copy INPUT PACKET.",
            f"- Do not include these forbidden top-level keys: {forbidden_keys}.",
            "- If uncertain, return the required decision schema and use abstain_reason.",
            "",
            "DECISION_JSON_ALLOWED_KEYS:",
            allowed_keys,
            "",
            "DECISION_JSON_FIELD_RULES:",
            f"- schema must equal {DECISION_SCHEMA}.",
            f"- arm must equal {arm}.",
            f"- ticker must equal {payload.get('ticker')}.",
            f"- decision_date and input_cutoff must equal {payload.get('decision_date')}.",
            f"- horizon_days must equal {payload.get('horizon_days')}.",
            "- direction must be exactly one of: long, avoid, neutral, watch, short.",
            "- expected_change_pct must be a JSON number, not a string.",
            "- confidence must be a JSON number in [0, 1], not a word or percentage.",
            "- future_data_allowed must be false.",
            "- ksana_refs must be empty for direct_llm.",
            "- alaya_memory_refs must be empty except for full_gotra.",
            "- full_gotra alaya_memory_refs must be a subset of alaya_feedback_history[].feedback_ref.",
            "- If alaya_feedback_history is empty, full_gotra alaya_memory_refs must be [].",
            "",
            "ARM_SPECIFIC_REF_RULES:",
            ref_rules_text,
            "",
            "OUTPUT_CONTRACT_JSON:",
            output_contract_text,
            "",
            "DECISION_JSON_SKELETON_COPY_AND_FILL_VALUES:",
            skeleton_text,
            "",
            "ARM_CONTRACT:",
            arm_contract_text,
            "",
            "INPUT_PACKET_DO_NOT_COPY:",
            "BEGIN_INPUT_PACKET_DO_NOT_COPY_JSON",
            input_packet_text,
            "END_INPUT_PACKET_DO_NOT_COPY_JSON",
            "",
            "FINAL ANSWER:",
        ]
    )


def arm_ksana_refs_contract(arm: Arm) -> str:
    if arm == "direct_llm":
        return "MUST be exactly []; never put evidence refs, ksana labels, or placeholders here"
    if arm == "ksana_formatting_only":
        return "list of ksana formatting refs if used; alaya refs still forbidden"
    return "list of ksana research refs if used; direct_llm rules do not apply"


def arm_alaya_memory_refs_contract(arm: Arm, feedback: list[dict[str, Any]]) -> str:
    if arm == "full_gotra":
        refs = [str(item.get("feedback_ref")) for item in feedback if item.get("feedback_ref")]
        if refs:
            return "subset of visible alaya_feedback_history feedback_ref values: " + ", ".join(refs)
        return "MUST be exactly []; no visible alaya_feedback_history feedback_ref values"
    return "MUST be exactly []; only full_gotra may return alaya memory refs"


def arm_specific_ref_rules(payload: dict[str, Any]) -> list[str]:
    arm = normalize_arm(payload.get("arm"))
    feedback = payload.get("alaya_feedback_history") or []
    if arm == "direct_llm":
        return [
            'For direct_llm, output "ksana_refs": [] exactly.',
            'For direct_llm, output "alaya_memory_refs": [] exactly.',
            "For direct_llm, never write full_gotra, alaya, ksana, workflow labels, "
            "or evidence refs inside ksana_refs/alaya_memory_refs.",
            "For direct_llm, evidence_refs may cite only available evidence names; "
            "they do not belong in ksana_refs or alaya_memory_refs.",
        ]
    if arm in {"ksana_formatting_only", "ksana_real_research"}:
        return [
            f'For {arm}, output "alaya_memory_refs": [] exactly.',
            f"For {arm}, never write full_gotra, alaya, feedback, "
            "or memory placeholders inside alaya_memory_refs.",
        ]
    visible_refs = [str(item.get("feedback_ref")) for item in feedback if item.get("feedback_ref")]
    if not visible_refs:
        return [
            'For full_gotra with no visible feedback_ref values, output "alaya_memory_refs": [] exactly.',
            "For full_gotra, never invent generic placeholders such as full_gotra, "
            "alaya, or matured_feedback.",
        ]
    return [
        "For full_gotra, alaya_memory_refs must be a subset of these visible feedback_ref values: "
        + ", ".join(visible_refs),
        "For full_gotra, output [] if none of the visible feedback_ref values are used.",
        "For full_gotra, never invent generic placeholders such as full_gotra, "
        "alaya, or matured_feedback.",
    ]


def decision_json_skeleton(payload: dict[str, Any]) -> dict[str, Any]:
    arm = normalize_arm(payload.get("arm"))
    if arm == "ksana_formatting_only":
        ksana_refs: list[str] = ["ksana_formatting_contract"]
    elif arm in {"ksana_real_research", "full_gotra"}:
        ksana_refs = ["ksana_real_research_artifacts"]
    else:
        ksana_refs = []
    return {
        "schema": DECISION_SCHEMA,
        "arm": arm,
        "ticker": str(payload.get("ticker") or ""),
        "decision_date": str(payload.get("decision_date") or ""),
        "horizon_days": int(payload.get("horizon_days") or WINDOW_DAYS),
        "direction": "neutral",
        "expected_change_pct": 0.0,
        "confidence": 0.0,
        "reasoning": "Use available evidence only.",
        "evidence_refs": ["adjusted_close_history"],
        "ksana_refs": ksana_refs,
        "alaya_memory_refs": [],
        "risk_factors": [],
        "abstain_reason": None,
        "input_cutoff": str(payload.get("decision_date") or ""),
        "future_data_allowed": False,
    }


def arm_prompt_contract(arm: Arm) -> dict[str, Any]:
    if arm == "direct_llm":
        return {
            "task": "Make one time-bounded direct LLM decision without ksana or alaya context.",
            "allowed_context": ["time-bounded market packet", "research_artifacts if present"],
            "forbidden_context": ["ksana workflow output", "alaya memory", "future outcomes"],
        }
    if arm == "ksana_formatting_only":
        return {
            "task": "Use ksana role formatting only; do not use independent research artifacts.",
            "allowed_context": ["same price-derived packet", "ksana role structure"],
            "forbidden_context": ["independent research artifacts", "alaya memory", "future outcomes"],
        }
    if arm == "ksana_real_research":
        return {
            "task": "Use ksana role workflow with time-bounded research artifacts and no alaya memory.",
            "allowed_context": ["price packet", "research_artifacts where availability_date <= decision_date"],
            "forbidden_context": ["alaya memory", "future outcomes"],
        }
    return {
        "task": "Use ksana real research plus matured alaya feedback available by decision_date.",
        "allowed_context": [
            "price packet",
            "time-bounded research_artifacts",
            "matured alaya feedback where outcome_availability_date <= decision_date",
        ],
        "forbidden_context": ["future outcomes", "auto-approved strong knowledge"],
    }


def price_features(price_rows: pd.DataFrame) -> dict[str, float]:
    return v2.price_features(price_rows)


def compact_price_rows(price_rows: pd.DataFrame, *, max_rows: int = 32) -> list[dict[str, Any]]:
    return v2.compact_price_rows(price_rows, max_rows=max_rows)


def price_context_for(point: DecisionPoint, *, price_dir: Path) -> PriceContext:
    frame = read_price_cache(point.ticker, price_dir=price_dir)
    rows = rows_on_or_before(frame, point.decision_date)
    start_row = row_on_or_after(frame, point.decision_date)
    outcome_date = point.decision_date + timedelta(days=WINDOW_DAYS)
    end_row = row_on_or_after(frame, outcome_date)
    if rows.empty:
        raise RuntimeError(f"no price rows on or before {point.decision_date}")
    if start_row is None:
        raise RuntimeError(f"no start price on or after {point.decision_date}")
    if end_row is None:
        raise RuntimeError(f"no outcome price on or after {outcome_date}")
    return PriceContext(
        price_rows=rows,
        start_row=start_row,
        end_row=end_row,
        outcome_date=outcome_date,
    )


def rows_on_or_before(frame: pd.DataFrame, value: date) -> pd.DataFrame:
    return v2.rows_on_or_before(frame, value)


def row_on_or_after(frame: pd.DataFrame, value: date) -> pd.Series | None:
    return v2.row_on_or_after(frame, value)


def change_pct(start: float, end: float) -> float:
    return v2.change_pct(start, end)


def actual_direction(actual_change_pct: float) -> str:
    return v2.actual_direction(actual_change_pct)


def direction_hit_for(*, predicted_direction: str, actual_change_pct: float) -> bool:
    actual = actual_direction(actual_change_pct)
    if actual == "avoid":
        return predicted_direction in {"avoid", "short"}
    return predicted_direction == actual


def deterministic_price_only_baseline_decision(
    *,
    ticker: str,
    decision_date: date,
    price_rows: pd.DataFrame,
) -> dict[str, Any]:
    dated = price_rows.copy()
    dated["_gotra_decision_visible_date"] = pd.to_datetime(dated["date"]).dt.date
    visible = dated[dated["_gotra_decision_visible_date"] <= decision_date].drop(
        columns=["_gotra_decision_visible_date"]
    )
    future_rows_excluded = int(len(dated) - len(visible))
    if visible.empty:
        raise ValueError("deterministic price-only baseline has no pre-decision price rows")
    features = price_features(visible)
    expected = round(
        max(
            min(
                0.35 * features["return_21d_pct"] + 0.25 * features["return_63d_pct"],
                25.0,
            ),
            -25.0,
        ),
        4,
    )
    direction = "long" if expected >= 2.0 else "avoid" if expected <= -2.0 else "neutral"
    confidence = round(min(0.8, 0.45 + abs(expected) / 70), 4)
    latest = visible.iloc[-1]
    return {
        "schema": "gotra.baseline_v3_4.deterministic_price_only_baseline.v1",
        "baseline": "deterministic_price_only_baseline",
        "ticker": ticker,
        "decision_date": decision_date.isoformat(),
        "input_cutoff": decision_date.isoformat(),
        "latest_visible_price_date": str(latest["date"]),
        "visible_price_rows": int(len(visible)),
        "future_rows_excluded": future_rows_excluded,
        "direction": direction,
        "expected_change_pct": expected,
        "confidence": confidence,
        "future_data_allowed": False,
        "llm_used": False,
    }


def scoring_segment_for(config: RunConfig, decision_date: date) -> ScoringSegment:
    ordered_dates = sorted(config.dates)
    warm_up_dates = set(ordered_dates[: max(0, config.warm_up_dates)])
    return "warm_up" if decision_date in warm_up_dates else "scored"


def build_scored_step(
    *,
    run_id: str,
    point: DecisionPoint,
    arm: Arm,
    context: PriceContext,
    decision: ProviderDecision,
    prompt_hash: str,
    cache_key: str,
    cache_hit: bool,
    feedback: list[dict[str, Any]],
    research_artifacts: list[dict[str, Any]],
    scoring_segment: ScoringSegment,
    provider: str,
    provider_model: str,
    provider_base_url: str,
    provider_transport: str,
    diagnostics: dict[str, Any],
    feedback_filter_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actual = change_pct(float(context.start_row["adj_close"]), float(context.end_row["adj_close"]))
    error = round(actual - decision.expected_change_pct, 6)
    decision_hit = direction_hit_for(predicted_direction=decision.direction, actual_change_pct=actual)
    feedback_ages = feedback_age_days(feedback=feedback, decision_date=point.decision_date)
    strict_feedback = strict_feedback_diagnostics(
        feedback=feedback if arm == "full_gotra" else [],
        decision_date=point.decision_date,
        arm=arm,
        scoring_segment=scoring_segment,
    )
    feedback_filter_diagnostics = (
        feedback_filter_diagnostics or feedback_filter_diagnostics_empty()
    )
    available_evidence_count = 1 + len(research_artifacts) + (len(feedback) if arm == "full_gotra" else 0)
    step = {
        "schema": STEP_SCHEMA,
        "definition_version": DEFINITION_VERSION,
        "run_id": run_id,
        "status": "scored",
        "ticker": point.ticker,
        "arm": arm,
        "input_layer": point.input_layer,
        "scoring_segment": scoring_segment,
        "decision_date": point.decision_date.isoformat(),
        "window_days": WINDOW_DAYS,
        "window_end_date": context.outcome_date.isoformat(),
        "outcome_as_of": str(context.end_row["date"]),
        "direction": decision.direction,
        "expected_change_pct": decision.expected_change_pct,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "reasoning_chars": len(decision.reasoning),
        "evidence_refs": decision.evidence_refs,
        "ksana_refs": decision.ksana_refs,
        "alaya_memory_refs": decision.alaya_memory_refs,
        "risk_factors": decision.risk_factors,
        "abstain_reason": decision.abstain_reason,
        "input_cutoff": decision.input_cutoff,
        "actual_change_pct": actual,
        "actual_direction": actual_direction(actual),
        "direction_hit": decision_hit,
        "error": error,
        "mse": round(error * error, 6),
        "mae": round(abs(error), 6),
        "policy_a_return_pct": actual if decision.direction == "long" else 0.0,
        "provider": provider,
        "provider_model": provider_model,
        "provider_transport": provider_transport,
        "provider_base_url": provider_base_url,
        "network_research_enabled": False,
        "ksana_workflow_enabled": arm in {"ksana_formatting_only", "ksana_real_research", "full_gotra"},
        "alaya_feedback_enabled": arm == "full_gotra",
        "feedback_used_count": len(feedback) if arm == "full_gotra" else 0,
        "feedback_age_days_min": min(feedback_ages) if feedback_ages else None,
        "feedback_age_days_max": max(feedback_ages) if feedback_ages else None,
        **strict_feedback,
        "quarantine_excluded_count": 0,
        "strong_knowledge_auto_approved": False,
        "alaya_feedback_history": feedback if arm == "full_gotra" else [],
        **feedback_filter_diagnostics,
        "research_artifacts": research_artifacts,
        "research_artifact_count": len(research_artifacts),
        "synthetic_evidence_count": synthetic_evidence_count(research_artifacts),
        "source_kind_counts": source_kind_counts_for_artifacts(research_artifacts),
        "available_evidence_count": available_evidence_count,
        "research_source_leak": False,
        "prompt_hash": prompt_hash,
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "decision_inputs": decision_inputs(
            context.price_rows,
            research_artifacts=research_artifacts,
            feedback=feedback if arm == "full_gotra" else [],
        ),
        "outcome_inputs": outcome_inputs(context.end_row),
        "future_data_allowed": False,
        "audit_actor": "baseline_v3_four_arm",
        **diagnostics,
    }
    step["product_metrics"] = product_metrics_for_step(step)
    return step


def build_error_step(
    *,
    run_id: str,
    point: DecisionPoint,
    arm: Arm,
    provider: str,
    provider_model: str,
    provider_base_url: str,
    provider_transport: str,
    error_type: str,
    error_message: str,
    scoring_segment: ScoringSegment,
    context: PriceContext | None = None,
    prompt_hash: str = "",
    diagnostics: dict[str, Any] | None = None,
    feedback: list[dict[str, Any]] | None = None,
    feedback_filter_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = diagnostics or default_request_diagnostics(timeout_seconds=0)
    feedback = feedback or []
    feedback_filter_diagnostics = feedback_filter_diagnostics or feedback_filter_diagnostics_empty()
    provider_error_types = {
        "provider_timeout",
        "provider_http_429",
        "provider_http_error",
        "json_decode_error",
        "schema_parse_error",
        "schema_contract_error",
        "input_echo_error",
        "future_data_violation",
        "research_source_leak",
        "feedback_source_leak",
        "auth_missing",
        "codex_cli_backend_blocked",
    }
    step: dict[str, Any] = {
        "schema": STEP_SCHEMA,
        "definition_version": DEFINITION_VERSION,
        "run_id": run_id,
        "status": "provider_error" if error_type in provider_error_types else "skipped",
        "error_type": error_type,
        "error_message": redact_error(error_message),
        "ticker": point.ticker,
        "arm": arm,
        "input_layer": point.input_layer,
        "scoring_segment": scoring_segment,
        "decision_date": point.decision_date.isoformat(),
        "window_days": WINDOW_DAYS,
        "direction": None,
        "expected_change_pct": None,
        "confidence": None,
        "reasoning": "",
        "reasoning_chars": 0,
        "actual_change_pct": None,
        "direction_hit": None,
        "error": None,
        "mse": None,
        "mae": None,
        "policy_a_return_pct": 0.0,
        "provider": provider,
        "provider_model": provider_model,
        "provider_transport": provider_transport,
        "provider_base_url": provider_base_url,
        "network_research_enabled": False,
        "ksana_workflow_enabled": arm in {"ksana_formatting_only", "ksana_real_research", "full_gotra"},
        "alaya_feedback_enabled": arm == "full_gotra",
        "feedback_used_count": 0,
        "feedback_age_days_min": None,
        "feedback_age_days_max": None,
        "quarantine_excluded_count": 0,
        "strong_knowledge_auto_approved": False,
        "alaya_feedback_history": feedback if arm == "full_gotra" else [],
        **feedback_filter_diagnostics,
        "research_artifacts": [],
        "research_artifact_count": 0,
        "synthetic_evidence_count": 0,
        "source_kind_counts": source_kind_counts_for_artifacts([]),
        "available_evidence_count": 0,
        "research_source_leak": error_type == "research_source_leak",
        "prompt_hash": prompt_hash,
        "cache_key": "",
        "cache_hit": False,
        "future_data_allowed": False,
        "audit_actor": "baseline_v3_four_arm",
        **diagnostics,
    }
    if context is not None:
        actual = change_pct(float(context.start_row["adj_close"]), float(context.end_row["adj_close"]))
        step.update(
            {
                "window_end_date": context.outcome_date.isoformat(),
                "outcome_as_of": str(context.end_row["date"]),
                "actual_change_pct": actual,
                "decision_inputs": decision_inputs(
                    context.price_rows,
                    research_artifacts=[],
                    feedback=feedback if arm == "full_gotra" else [],
                ),
                "outcome_inputs": outcome_inputs(context.end_row),
            }
        )
    else:
        step.update({"decision_inputs": [], "outcome_inputs": []})
    step["product_metrics"] = product_metrics_for_step(step)
    return step


def classify_exception(exc: Exception) -> str:
    if str(getattr(exc, "provider_error_class", "") or "") == "CodexCliBackendBlocked":
        return "codex_cli_backend_blocked"
    return v2.classify_exception(exc)


def decision_inputs(
    price_rows: pd.DataFrame,
    *,
    research_artifacts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest = price_rows.iloc[-1]
    inputs: list[dict[str, Any]] = [
        {
            "name": "adjusted_close_history",
            "kind": "price",
            "source": str(latest["source_url"]),
            "availability_date": str(latest["date"]),
            "rows": int(len(price_rows)),
        }
    ]
    for artifact in research_artifacts:
        inputs.append(
            {
                "name": str(artifact["name"]),
                "kind": str(artifact["kind"]),
                "source": str(artifact["source"]),
                "source_kind": str(artifact["source_kind"]),
                "availability_date": str(artifact["availability_date"]),
            }
        )
    for index, item in enumerate(feedback):
        inputs.append(
            {
                "name": str(item.get("feedback_ref") or f"alaya_matured_feedback_{index}"),
                "kind": "alaya_feedback",
                "source": str(item.get("source_step_id") or item.get("source_run_id") or "prior_step_outcome"),
                "source_kind": str(
                    item.get("feedback_source_kind") or item.get("source_kind") or "self_feedback"
                ),
                "availability_date": item.get("availability_date") or item["outcome_availability_date"],
                "source_decision_date": item.get("source_decision_date")
                or item.get("prior_decision_date"),
                "source_horizon_end_date": item.get("source_horizon_end_date"),
            }
        )
    return inputs


def outcome_inputs(end_row: pd.Series) -> list[dict[str, Any]]:
    return v2.outcome_inputs(end_row)


def future_data_violations(step: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if step.get("future_data_allowed") is not False:
        violations.append("future_data_allowed must be false")
    decision_date = parse_date(str(step["decision_date"]))
    for item in step.get("decision_inputs") or []:
        if parse_date(str(item["availability_date"])) > decision_date:
            violations.append(f"decision input after decision_date: {item.get('name')}")
    outcome_as_of = step.get("outcome_as_of")
    if outcome_as_of:
        outcome_date = parse_date(str(outcome_as_of))
        for item in step.get("outcome_inputs") or []:
            if parse_date(str(item["availability_date"])) > outcome_date:
                violations.append(f"outcome input after outcome_as_of: {item.get('name')}")
    return violations


def research_source_leak_violations(step: dict[str, Any]) -> list[str]:
    if step.get("arm") != "ksana_formatting_only":
        return []
    violations: list[str] = []
    for artifact in step.get("research_artifacts") or []:
        source_kind = str(artifact.get("source_kind") or "")
        kind = str(artifact.get("kind") or "")
        if source_kind != "price_derived" and kind != "price":
            violations.append(f"formatting_only non-price research artifact: {artifact.get('name')}")
    return violations


def feedback_source_leak_violations(step: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    has_feedback_input = any(
        str(item.get("kind") or "") == "alaya_feedback"
        for item in step.get("decision_inputs") or []
        if isinstance(item, dict)
    )
    if has_feedback_input and step.get("arm") != "full_gotra":
        violations.append("non-full_gotra arm received alaya_feedback")
    return violations


def feedback_age_days(*, feedback: list[dict[str, Any]], decision_date: date) -> list[int]:
    ages: list[int] = []
    for item in feedback:
        if not item.get("outcome_availability_date"):
            continue
        ages.append((decision_date - parse_date(str(item["outcome_availability_date"]))).days)
    return ages


def strict_feedback_diagnostics(
    *,
    feedback: list[dict[str, Any]],
    decision_date: date,
    arm: Arm = "full_gotra",
    scoring_segment: ScoringSegment = "scored",
) -> dict[str, Any]:
    if arm != "full_gotra" or scoring_segment != "scored":
        return {
            "self_feedback_available": False,
            "visible_mature_feedback_count": 0,
            "feedback_prior_wave_count": 0,
            "feedback_real_unverified_count": 0,
            "true_independent_feedback_count": 0,
            "true_independent_feedback_prior_wave_count": 0,
            "duplicate_independent_feedback_count": 0,
            "feedback_source_kind_counts": feedback_source_kind_counts_for_feedback([]),
            "feedback_age_days_max_meets_horizon": False,
            "strict_feedback_eligible": False,
            "true_independent_feedback_eligible": False,
            "strict_feedback_insufficient_reason": "not_full_gotra_scored_segment",
        }
    ages = feedback_age_days(feedback=feedback, decision_date=decision_date)
    independent_feedback = [
        item
        for item in feedback
        if str(item.get("feedback_source_kind") or item.get("source_kind") or "")
        in TRUE_INDEPENDENT_FEEDBACK_SOURCE_KINDS
    ]
    unique_independent_feedback = unique_feedback_artifacts(independent_feedback)
    prior_waves = {
        str(item.get("prior_decision_date") or item.get("decision_date"))
        for item in feedback
        if item.get("prior_decision_date") or item.get("decision_date")
    }
    independent_prior_waves = {
        str(item.get("source_decision_date") or item.get("prior_decision_date") or item.get("decision_date"))
        for item in unique_independent_feedback
        if item.get("source_decision_date") or item.get("prior_decision_date") or item.get("decision_date")
    }
    count = len(feedback)
    independent_count = len(unique_independent_feedback)
    duplicate_independent_count = max(0, len(independent_feedback) - independent_count)
    max_age = max(ages) if ages else None
    reasons: list[str] = []
    if count < 3:
        reasons.append("visible_mature_feedback_count_lt_3")
    if independent_count < 3:
        reasons.append("true_independent_feedback_count_lt_3")
    if len(independent_prior_waves) < 2:
        reasons.append("true_independent_prior_wave_count_lt_2")
    if independent_count < 1:
        reasons.append("no_outcome_derived_independent_feedback_source_kind")
    eligible = not reasons
    return {
        "self_feedback_available": count > 0,
        "visible_mature_feedback_count": count,
        "feedback_prior_wave_count": len(prior_waves),
        "feedback_real_unverified_count": 0,
        "true_independent_feedback_count": independent_count,
        "true_independent_feedback_prior_wave_count": len(independent_prior_waves),
        "duplicate_independent_feedback_count": duplicate_independent_count,
        "feedback_source_kind_counts": feedback_source_kind_counts_for_feedback(feedback),
        "feedback_age_days_max_meets_horizon": bool(max_age is not None and max_age >= WINDOW_DAYS),
        "strict_feedback_eligible": eligible,
        "true_independent_feedback_eligible": eligible,
        "strict_feedback_insufficient_reason": ",".join(reasons),
    }


def synthetic_evidence_count(research_artifacts: list[dict[str, Any]]) -> int:
    return sum(1 for item in research_artifacts if str(item.get("source_kind")) == "synthetic")


def source_kind_counts_for_artifacts(research_artifacts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"real": 0, "synthetic": 0, "unverified": 0, "price_derived": 0, "unknown": 0}
    for item in research_artifacts:
        source_kind = str(item.get("source_kind") or "unknown")
        if source_kind not in counts:
            source_kind = "unknown"
        counts[source_kind] += 1
    return counts


def source_kind_counts_for_steps(steps: list[dict[str, Any]]) -> dict[str, int]:
    counts = source_kind_counts_for_artifacts([])
    for step in steps:
        step_counts = step.get("source_kind_counts")
        if isinstance(step_counts, dict):
            for key, value in step_counts.items():
                counts[str(key) if str(key) in counts else "unknown"] += int(value or 0)
            continue
        for artifact in step.get("research_artifacts") or []:
            source_kind = str(artifact.get("source_kind") or "unknown")
            counts[source_kind if source_kind in counts else "unknown"] += 1
    return counts


def feedback_source_kind_counts_for_feedback(feedback: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "outcome_feedback": 0,
        "realized_error_feedback": 0,
        "self_feedback": 0,
        "synthetic_feedback": 0,
        "unknown": 0,
    }
    for item in feedback:
        source_kind = str(
            item.get("feedback_source_kind") or item.get("source_kind") or "unknown"
        )
        counts[source_kind if source_kind in counts else "unknown"] += 1
    return counts


def feedback_source_kind_counts_for_steps(steps: list[dict[str, Any]]) -> dict[str, int]:
    counts = feedback_source_kind_counts_for_feedback([])
    for step in steps:
        step_counts = step.get("feedback_source_kind_counts")
        if isinstance(step_counts, dict):
            for key, value in step_counts.items():
                counts[str(key) if str(key) in counts else "unknown"] += int(value or 0)
            continue
        for item in step.get("alaya_feedback_history") or []:
            source_kind = str(
                item.get("feedback_source_kind") or item.get("source_kind") or "unknown"
            )
            counts[source_kind if source_kind in counts else "unknown"] += 1
    return counts


def available_evidence_ref_names(step: dict[str, Any]) -> set[str]:
    names = {
        str(item.get("name"))
        for item in step.get("decision_inputs") or []
        if isinstance(item, dict) and item.get("name")
    }
    if names:
        return names
    count = int(step.get("available_evidence_count") or 0)
    return {str(item) for item in step.get("evidence_refs") or []} if count else set()


def evidence_ref_coverage_diagnostics(step: dict[str, Any]) -> dict[str, int | float]:
    evidence_refs = [str(item) for item in step.get("evidence_refs") or []]
    available_refs = available_evidence_ref_names(step)
    unique_refs = set(evidence_refs)
    valid_refs = unique_refs & available_refs
    invalid_refs = unique_refs - available_refs
    duplicate_count = max(0, len(evidence_refs) - len(unique_refs))
    coverage = len(valid_refs) / len(available_refs) if available_refs else 0.0
    return {
        "evidence_coverage": round(max(0.0, min(1.0, coverage)), 6),
        "evidence_coverage_valid_ref_count": len(valid_refs),
        "evidence_coverage_available_ref_count": len(available_refs),
        "evidence_coverage_invalid_ref_count": len(invalid_refs),
        "evidence_coverage_duplicate_ref_count": duplicate_count,
    }


def product_metrics_for_step(step: dict[str, Any]) -> dict[str, float]:
    evidence_refs = [str(item) for item in step.get("evidence_refs") or []]
    reasoning = str(step.get("reasoning") or "")
    coverage = evidence_ref_coverage_diagnostics(step)
    reasoning_auditability = 0.0
    if evidence_refs and reasoning:
        matched = sum(1 for ref in evidence_refs if ref in reasoning)
        reasoning_auditability = matched / len(evidence_refs)
    feedback_count = int(step.get("feedback_used_count") or 0)
    error_attribution_quality = (
        1.0
        if step.get("arm") == "full_gotra"
        and feedback_count > 0
        and step.get("alaya_memory_refs")
        else 0.0
    )
    required_fields = (
        "schema",
        "definition_version",
        "run_id",
        "status",
        "ticker",
        "arm",
        "input_layer",
        "scoring_segment",
        "decision_date",
        "window_days",
        "direction",
        "expected_change_pct",
        "confidence",
        "reasoning",
        "evidence_refs",
        "risk_factors",
    )
    present = 0
    for field in required_fields:
        value = step.get(field)
        if value is not None and value != "":
            present += 1
    claim_specificity_parts = [
        1 if step.get("direction") else 0,
        1 if step.get("expected_change_pct") is not None else 0,
        1 if step.get("confidence") is not None else 0,
    ]
    return {
        "evidence_coverage": coverage["evidence_coverage"],
        "evidence_coverage_valid_ref_count": coverage["evidence_coverage_valid_ref_count"],
        "evidence_coverage_available_ref_count": coverage["evidence_coverage_available_ref_count"],
        "evidence_coverage_invalid_ref_count": coverage["evidence_coverage_invalid_ref_count"],
        "evidence_coverage_duplicate_ref_count": coverage["evidence_coverage_duplicate_ref_count"],
        "reasoning_auditability": round(reasoning_auditability, 6),
        "error_attribution_quality": round(error_attribution_quality, 6),
        "ledger_completeness": round(present / len(required_fields), 6),
        "claim_specificity": round(sum(claim_specificity_parts) / 3, 6),
        "risk_disclosure_quality": 1.0 if step.get("risk_factors") else 0.0,
        "explanation_consistency": 1.0 if reasoning else 0.0,
    }


def arm_base_timeout_seconds(config: RunConfig, arm: Arm) -> float:
    if arm == "direct_llm":
        return config.direct_llm_timeout_seconds
    if arm == "ksana_formatting_only":
        return config.ksana_formatting_only_timeout_seconds
    if arm == "ksana_real_research":
        return config.ksana_real_research_timeout_seconds
    return config.full_gotra_timeout_seconds


def effective_request_timeout_seconds(config: RunConfig, *, arm: Arm, prompt_bytes: int) -> float:
    complexity_seconds = math.ceil(max(0, prompt_bytes) / 1024) * config.timeout_per_kb_seconds
    return min(
        config.max_request_timeout_seconds,
        arm_base_timeout_seconds(config, arm) + complexity_seconds,
    )


def request_timeout_policy(config: RunConfig, *, arm: Arm, prompt_bytes: int) -> dict[str, Any]:
    return {
        "policy": timeout_policy_name(config),
        "arm": arm,
        "arm_base_timeout_seconds": arm_base_timeout_seconds(config, arm),
        "prompt_bytes": prompt_bytes,
        "timeout_per_kb_seconds": config.timeout_per_kb_seconds,
        "max_request_timeout_seconds": config.max_request_timeout_seconds,
    }


def timeout_policy_manifest(config: RunConfig) -> dict[str, Any]:
    return {
        "policy": timeout_policy_name(config),
        "direct_llm_timeout_seconds": config.direct_llm_timeout_seconds,
        "ksana_formatting_only_timeout_seconds": config.ksana_formatting_only_timeout_seconds,
        "ksana_real_research_timeout_seconds": config.ksana_real_research_timeout_seconds,
        "full_gotra_timeout_seconds": config.full_gotra_timeout_seconds,
        "timeout_per_kb_seconds": config.timeout_per_kb_seconds,
        "max_request_timeout_seconds": config.max_request_timeout_seconds,
    }


def timeout_policy_name(config: RunConfig) -> str:
    if config.provider_model == DEEPSEEK_FLASH_MODEL:
        return "per_arm_complexity_normalized_deepseek_flash_v3"
    return "per_arm_complexity_normalized_v3"


def provider_limit_metadata(config: RunConfig) -> dict[str, Any]:
    if config.provider == "glm_sophnet" and config.provider_model == DEEPSEEK_FLASH_MODEL:
        return dict(DEEPSEEK_RATE_LIMITS)
    return {}


def provider_max_tokens_metadata(config: RunConfig) -> dict[str, Any]:
    if config.mode == "mock":
        return {
            "provider_max_tokens_applied": False,
            "provider_max_tokens_reason": "local mock does not call provider token API",
        }
    if config.provider == CODEX_CLI_BACKEND:
        return {
            "provider_max_tokens_applied": True,
            "provider_max_tokens_reason": "prompt guidance passed to Codex CLI backend",
        }
    if config.provider in {"glm_sophnet", "kimi"}:
        return {
            "provider_max_tokens_applied": True,
            "provider_max_tokens_reason": "included in provider request path",
        }
    return {
        "provider_max_tokens_applied": False,
        "provider_max_tokens_reason": f"unsupported provider: {config.provider}",
    }


def provider_temperature_metadata(config: RunConfig) -> dict[str, Any]:
    temperature = provider_temperature_for(config.provider, config.provider_model)
    if config.provider == CODEX_CLI_BACKEND:
        return {
            "provider_temperature": None,
            "provider_temperature_applied": False,
            "provider_temperature_reason": "Codex CLI backend has prompt guidance only",
        }
    if temperature is None:
        return {
            "provider_temperature": None,
            "provider_temperature_applied": False,
            "provider_temperature_reason": f"unsupported provider: {config.provider}",
        }
    if config.mode == "mock":
        return {
            "provider_temperature": temperature,
            "provider_temperature_applied": False,
            "provider_temperature_reason": "local mock does not call provider temperature API",
        }
    return {
        "provider_temperature": temperature,
        "provider_temperature_applied": True,
        "provider_temperature_reason": "Kimi/SophNet K2.6 requires explicit temperature=1",
    }


def codex_cli_backend_metadata(config: RunConfig) -> dict[str, Any]:
    if config.provider != CODEX_CLI_BACKEND:
        return {
            "backend_name": "",
            "codex_cli_version": "",
            "codex_cli_model": "",
            "codex_cli_reasoning_setting": "",
        }
    return {
        "backend_name": CODEX_CLI_BACKEND,
        "codex_cli_version": codex_cli_version(config.codex_cli_binary),
        "codex_cli_model": config.provider_model,
        "codex_cli_reasoning_setting": config.codex_cli_reasoning_setting,
    }


def default_request_diagnostics(
    *,
    timeout_seconds: float,
    timeout_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = v2.default_request_diagnostics(
        timeout_seconds=timeout_seconds,
        timeout_policy=timeout_policy,
    )
    diagnostics["provider_max_tokens"] = 0
    diagnostics["provider_max_tokens_applied"] = False
    diagnostics["provider_max_tokens_reason"] = ""
    diagnostics["provider_temperature"] = None
    diagnostics["provider_temperature_applied"] = False
    diagnostics["provider_temperature_reason"] = ""
    diagnostics["backend_name"] = ""
    diagnostics["codex_cli_version"] = ""
    diagnostics["codex_cli_model"] = ""
    diagnostics["codex_cli_reasoning_setting"] = ""
    diagnostics["output_transcript_path"] = ""
    diagnostics["parsed_decision_hash"] = ""
    return diagnostics


def prompt_request_diagnostics(*, prompt: str, config: RunConfig, arm: Arm) -> dict[str, Any]:
    prompt_bytes = len(prompt.encode("utf-8"))
    timeout_seconds = effective_request_timeout_seconds(
        config,
        arm=arm,
        prompt_bytes=prompt_bytes,
    )
    diagnostics = default_request_diagnostics(
        timeout_seconds=timeout_seconds,
        timeout_policy=request_timeout_policy(config, arm=arm, prompt_bytes=prompt_bytes),
    )
    diagnostics["prompt_chars"] = len(prompt)
    diagnostics["prompt_bytes"] = prompt_bytes
    diagnostics["provider_max_tokens"] = config.provider_max_tokens
    diagnostics.update(provider_max_tokens_metadata(config))
    diagnostics.update(provider_temperature_metadata(config))
    diagnostics.update(codex_cli_backend_metadata(config))
    return diagnostics


def diagnostics_from_exception(
    *,
    diagnostics: dict[str, Any],
    exc: Exception,
    started_at: float | None,
) -> dict[str, Any]:
    updated = v2.diagnostics_from_exception(
        diagnostics=diagnostics,
        exc=exc,
        started_at=started_at,
    )
    last_retryable_error_type = str(getattr(exc, "last_retryable_error_type", "") or "")
    if last_retryable_error_type:
        updated["last_retryable_error_type"] = last_retryable_error_type
    for field in (
        "output_transcript_path",
        "codex_cli_version",
        "codex_cli_model",
        "codex_cli_reasoning_setting",
    ):
        value = str(getattr(exc, field, "") or "")
        if value:
            updated[field] = value
            if field != "output_transcript_path":
                updated["backend_name"] = CODEX_CLI_BACKEND
    return updated


def raw_content_artifact_fields(
    *,
    run_root: Path,
    point: DecisionPoint,
    arm: Arm,
    raw_content: str,
) -> dict[str, Any]:
    if not raw_content:
        return {}
    redacted = redact_sensitive_text(raw_content)
    raw_dir = run_root / "provider_raw" / arm
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = (
        raw_dir
        / f"raw_{point.decision_date.isoformat()}_{ticker_slug(point.ticker)}_{point.input_layer}.txt"
    )
    raw_path.write_text(redacted, encoding="utf-8")
    return {
        "provider_raw_content_path": str(raw_path),
        "provider_raw_content_chars": len(redacted),
        "provider_raw_content_sha256": hashlib.sha256(redacted.encode("utf-8")).hexdigest(),
        "provider_raw_content_excerpt": redacted[:1200],
    }


def redact_sensitive_text(value: str) -> str:
    return v2.redact_sensitive_text(value)


def complete_step(
    *,
    config: RunConfig,
    run_root: Path,
    cache: LocalJsonCache,
    client: MockDecisionClient | KimiDecisionClient | GlmSophnetDecisionClient | CodexCliBackendDecisionClient,
    point: DecisionPoint,
    arm: Arm,
    feedback: list[dict[str, Any]],
    feedback_filter_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context: PriceContext | None = None
    prompt_hash = ""
    scoring_segment = scoring_segment_for(config, point.decision_date)
    diagnostics = default_request_diagnostics(
        timeout_seconds=arm_base_timeout_seconds(config, arm),
        timeout_policy=request_timeout_policy(config, arm=arm, prompt_bytes=0),
    )
    started_at: float | None = None
    try:
        context = price_context_for(point, price_dir=config.price_dir)
        research_filter = research_artifact_filter_result(
            arm=arm,
            input_layer=point.input_layer,
            decision_date=point.decision_date,
            price_rows=context.price_rows,
            research_artifacts_path=config.research_artifacts_path,
            ticker=point.ticker,
        )
        research_artifacts = list(research_filter["accepted_artifacts"])
        payload = build_prompt_payload(
            arm=arm,
            input_layer=point.input_layer,
            ticker=point.ticker,
            decision_date=point.decision_date,
            price_rows=context.price_rows,
            feedback=feedback if arm == "full_gotra" else [],
            provider=client.provider,
            provider_model=client.provider_model,
            scoring_segment=scoring_segment,
            research_artifacts_override=research_artifacts,
        )
        prompt = render_provider_prompt(payload)
        diagnostics = prompt_request_diagnostics(prompt=prompt, config=config, arm=arm)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_key = cache_key_for(
            arm=arm,
            input_layer=point.input_layer,
            provider=client.provider,
            provider_model=client.provider_model,
            provider_base_url=client.provider_base_url,
            provider_max_tokens=config.provider_max_tokens,
            provider_temperature=provider_temperature_for(client.provider, client.provider_model),
            prompt_hash=prompt_hash,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            decision = parse_provider_decision(cached)
            validate_provider_decision_identity(decision, point=point, arm=arm)
            validate_alaya_memory_refs(decision, arm=arm, feedback=feedback)
            if config.provider == CODEX_CLI_BACKEND:
                diagnostics["parsed_decision_hash"] = stable_json_hash(cached)
            cache_hit = True
        else:
            started_at = time.monotonic()
            decision = client.complete(
                payload,
                request_timeout_seconds=float(diagnostics["request_timeout_seconds"]),
            )
            validate_provider_decision_identity(
                decision,
                point=point,
                arm=arm,
                raw_content=str(getattr(client, "last_raw_content", "") or ""),
            )
            validate_alaya_memory_refs(
                decision,
                arm=arm,
                feedback=feedback,
                raw_content=str(getattr(client, "last_raw_content", "") or ""),
            )
            diagnostics["request_duration_seconds"] = round(time.monotonic() - started_at, 6)
            diagnostics["provider_attempts"] = decision.provider_attempts
            diagnostics["provider_retry_count"] = decision.provider_retry_count
            diagnostics["provider_error_class"] = decision.provider_error_class
            if decision.provider_temperature is not None:
                diagnostics["provider_temperature"] = decision.provider_temperature
                diagnostics["provider_temperature_applied"] = True
            diagnostics["provider_temperature_fallback"] = decision.provider_temperature_fallback
            diagnostics["last_retryable_error_type"] = decision.last_retryable_error_type
            diagnostics["normalization_applied"] = decision.normalization_applied
            diagnostics["normalization_steps"] = list(decision.normalization_steps)
            diagnostics["normalization_failure_reason"] = decision.normalization_failure_reason
            diagnostics["backend_name"] = decision.backend_name
            diagnostics["codex_cli_version"] = decision.codex_cli_version
            diagnostics["codex_cli_model"] = decision.codex_cli_model
            diagnostics["codex_cli_reasoning_setting"] = decision.codex_cli_reasoning_setting
            diagnostics["output_transcript_path"] = decision.output_transcript_path
            diagnostics["parsed_decision_hash"] = decision.parsed_decision_hash
            cache.set(cache_key, decision_to_cache_payload(decision))
            cache_hit = False
        step = build_scored_step(
            run_id=config.run_id,
            point=point,
            arm=arm,
            context=context,
            decision=decision,
            prompt_hash=prompt_hash,
            cache_key=cache_key,
            cache_hit=cache_hit,
            feedback=feedback,
            research_artifacts=research_artifacts,
            scoring_segment=scoring_segment,
            provider=client.provider,
            provider_model=client.provider_model,
            provider_base_url=client.provider_base_url,
            provider_transport=client.provider_transport,
            diagnostics=diagnostics,
            feedback_filter_diagnostics=feedback_filter_diagnostics,
        )
        step.update(research_filter_diagnostics(research_filter))
        step["product_metrics"] = product_metrics_for_step(step)
    except FileNotFoundError as exc:
        step = build_error_step(
            run_id=config.run_id,
            point=point,
            arm=arm,
            provider=client.provider,
            provider_model=client.provider_model,
            provider_base_url=client.provider_base_url,
            provider_transport=client.provider_transport,
            error_type="price_missing",
            error_message=str(exc),
            context=context,
            scoring_segment=scoring_segment,
            prompt_hash=prompt_hash,
            diagnostics=diagnostics,
            feedback=feedback if arm == "full_gotra" else [],
            feedback_filter_diagnostics=feedback_filter_diagnostics,
        )
    except Exception as exc:  # noqa: BLE001 - provider and schema output are untrusted.
        diagnostics = diagnostics_from_exception(diagnostics=diagnostics, exc=exc, started_at=started_at)
        diagnostics.update(
            raw_content_artifact_fields(
                run_root=run_root,
                point=point,
                arm=arm,
                raw_content=str(getattr(exc, "raw_content", "") or ""),
            )
        )
        step = build_error_step(
            run_id=config.run_id,
            point=point,
            arm=arm,
            provider=client.provider,
            provider_model=client.provider_model,
            provider_base_url=client.provider_base_url,
            provider_transport=client.provider_transport,
            error_type=classify_exception(exc),
            error_message=str(exc),
            context=context,
            scoring_segment=scoring_segment,
            prompt_hash=prompt_hash,
            diagnostics=diagnostics,
            feedback=feedback if arm == "full_gotra" else [],
            feedback_filter_diagnostics=feedback_filter_diagnostics,
        )
    violations = future_data_violations(step)
    leak_violations = research_source_leak_violations(step)
    feedback_leak_violations = feedback_source_leak_violations(step)
    if violations:
        step["status"] = "provider_error"
        step["error_type"] = "future_data_violation"
        step["future_data_violations"] = violations
    if leak_violations:
        step["status"] = "provider_error"
        step["error_type"] = "research_source_leak"
        step["research_source_leak"] = True
        step["research_source_leak_violations"] = leak_violations
    if feedback_leak_violations:
        step["status"] = "provider_error"
        step["error_type"] = "feedback_source_leak"
        step["feedback_source_leak"] = True
        step["feedback_source_leak_violations"] = feedback_leak_violations
    write_step(run_root, step)
    append_ledger(run_root, step)
    return step


def decision_to_cache_payload(decision: ProviderDecision) -> dict[str, Any]:
    return {
        "schema": decision.schema,
        "arm": decision.arm,
        "ticker": decision.ticker,
        "decision_date": decision.decision_date,
        "horizon_days": decision.horizon_days,
        "direction": decision.direction,
        "expected_change_pct": decision.expected_change_pct,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "evidence_refs": decision.evidence_refs,
        "ksana_refs": decision.ksana_refs,
        "alaya_memory_refs": decision.alaya_memory_refs,
        "risk_factors": decision.risk_factors,
        "abstain_reason": decision.abstain_reason,
        "input_cutoff": decision.input_cutoff,
        "future_data_allowed": decision.future_data_allowed,
    }


def validate_provider_decision_identity(
    decision: ProviderDecision,
    *,
    point: DecisionPoint,
    arm: Arm,
    raw_content: str = "",
) -> None:
    mismatches: list[str] = []
    if decision.arm != arm:
        mismatches.append(f"arm expected={arm} actual={decision.arm}")
    if decision.ticker != point.ticker:
        mismatches.append(f"ticker expected={point.ticker} actual={decision.ticker}")
    if parse_date(decision.decision_date) != point.decision_date:
        mismatches.append(
            f"decision_date expected={point.decision_date.isoformat()} actual={decision.decision_date}"
        )
    if int(decision.horizon_days) != WINDOW_DAYS:
        mismatches.append(f"horizon_days expected={WINDOW_DAYS} actual={decision.horizon_days}")
    if not mismatches:
        return
    raise ProviderRequestError(
        "provider decision identity mismatch: " + "; ".join(mismatches),
        provider_error_class="SchemaContractError",
        provider_attempts=decision.provider_attempts,
        provider_retry_count=decision.provider_retry_count,
        raw_content=raw_content,
    )


def validate_alaya_memory_refs(
    decision: ProviderDecision,
    *,
    arm: Arm,
    feedback: list[dict[str, Any]],
    raw_content: str = "",
) -> None:
    if arm != "full_gotra":
        return
    refs = [str(item) for item in decision.alaya_memory_refs]
    if not refs:
        return
    allowed_refs = {str(item.get("feedback_ref")) for item in feedback if item.get("feedback_ref")}
    invalid_refs = sorted(ref for ref in refs if ref not in allowed_refs)
    if not allowed_refs or invalid_refs:
        raise ProviderRequestError(
            "invalid alaya_memory_refs: "
            + ",".join(invalid_refs or refs)
            + f"; available_feedback_refs={len(allowed_refs)}",
            provider_error_class="SchemaContractError",
            provider_attempts=decision.provider_attempts,
            provider_retry_count=decision.provider_retry_count,
            raw_content=raw_content,
        )


def run_four_arm(config: RunConfig) -> dict[str, Any]:
    validate_run_id(config.run_id)
    run_root = config.runs_root / config.run_id
    if run_root_has_artifacts(run_root):
        if not config.resume:
            return blocked_run_id_exists_summary(config=config, run_root=run_root)
        resume_error = resume_manifest_error(run_root=run_root, config=config)
        if resume_error:
            return blocked_resume_summary(config=config, run_root=run_root, reason=resume_error)
    run_root.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        (run_root / arm).mkdir(parents=True, exist_ok=True)

    if not (run_root / "manifest.json").exists():
        write_manifest(run_root, config)
    cache = LocalJsonCache(run_root / "cache.json")
    client: MockDecisionClient | KimiDecisionClient | GlmSophnetDecisionClient | CodexCliBackendDecisionClient
    if config.mode == "mock":
        client = MockDecisionClient(
            provider=config.provider,
            provider_model=config.provider_model,
            provider_base_url=config.provider_base_url,
        )
    elif config.provider == CODEX_CLI_BACKEND:
        client = CodexCliBackendDecisionClient(
            model=config.provider_model,
            reasoning_setting=config.codex_cli_reasoning_setting,
            run_root=run_root,
            provider_max_tokens=config.provider_max_tokens,
            codex_binary=config.codex_cli_binary,
            project_root=Path.cwd(),
        )
    elif config.provider == "glm_sophnet":
        client = GlmSophnetDecisionClient(
            model=config.provider_model,
            base_url=config.provider_base_url,
            request_timeout_seconds=config.max_request_timeout_seconds,
            timeout_retries=config.timeout_retries,
            timeout_retry_backoff_seconds=config.timeout_retry_backoff_seconds,
            provider_max_tokens=config.provider_max_tokens,
        )
    else:
        client = KimiDecisionClient(
            model=config.provider_model,
            request_timeout_seconds=config.max_request_timeout_seconds,
            provider_base_url=config.provider_base_url,
            provider_max_tokens=config.provider_max_tokens,
            provider_temperature=provider_temperature_for(config.provider, config.provider_model),
            timeout_retries=config.timeout_retries,
            timeout_retry_backoff_seconds=config.timeout_retry_backoff_seconds,
        )

    points = [
        DecisionPoint(ticker, value, input_layer)
        for value in config.dates
        for ticker in config.tickers
        for input_layer in config.input_layers
    ]
    steps: list[dict[str, Any]] = []
    feedback_by_key: dict[tuple[str, InputLayer], list[dict[str, Any]]] = {
        (ticker, input_layer): [] for ticker in config.tickers for input_layer in config.input_layers
    }
    provider_preflight_error = provider_preflight_blocker(config)
    concurrency_used = config.provider_concurrency
    downgrade_events: list[dict[str, Any]] = []
    stop_reason = ""
    circuit_breaker = CircuitBreakerState()

    if provider_preflight_error:
        preflight_error_type = (
            "codex_cli_backend_blocked"
            if provider_preflight_error.startswith("CODEX_CLI_BACKEND_BLOCKED")
            else "auth_missing"
        )
        preflight_transport = (
            CODEX_CLI_BACKEND
            if config.provider == CODEX_CLI_BACKEND
            else "sophnet_chat_completions"
        )
        for point in points:
            for arm in ARMS:
                context = try_price_context(point, price_dir=config.price_dir)
                scoring_segment = scoring_segment_for(config, point.decision_date)
                step = build_error_step(
                    run_id=config.run_id,
                    point=point,
                    arm=arm,
                    provider=config.provider,
                    provider_model=config.provider_model,
                    provider_base_url=config.provider_base_url,
                    provider_transport=preflight_transport,
                    error_type=preflight_error_type,
                    error_message=provider_preflight_error,
                    scoring_segment=scoring_segment,
                    context=context,
                    diagnostics={
                        **default_request_diagnostics(
                            timeout_seconds=arm_base_timeout_seconds(config, arm),
                            timeout_policy=request_timeout_policy(config, arm=arm, prompt_bytes=0),
                        ),
                        **provider_max_tokens_metadata(config),
                        **provider_temperature_metadata(config),
                        **codex_cli_backend_metadata(config),
                    },
                )
                write_step(run_root, step)
                append_ledger(run_root, step)
                steps.append(step)
        stop_reason = provider_preflight_error
    else:
        for decision_date in config.dates:
            wave_points = [point for point in points if point.decision_date == decision_date]
            wave_steps = run_date_wave(
                config=config,
                run_root=run_root,
                cache=cache,
                client=client,
                points=wave_points,
                feedback_by_key=feedback_by_key,
                concurrency=concurrency_used,
                circuit_breaker=circuit_breaker,
                prior_steps=steps,
            )
            steps.extend(wave_steps)
            if circuit_breaker.triggered:
                stop_reason = circuit_breaker.trigger_reason
                break
            stop_reason = pilot_stop_reason(steps=steps, total_points=len(points))
            if stop_reason:
                if config.mode == "provider-pilot" and concurrency_used > 1:
                    downgrade_events.append(
                        {
                            "from": concurrency_used,
                            "to": max(1, concurrency_used // 2),
                            "reason": stop_reason,
                        }
                    )
                break
            if should_increase_concurrency(config=config, wave_steps=wave_steps):
                concurrency_used = min(config.max_provider_concurrency, concurrency_used + 1)

    summary = summarize_run(
        config=config,
        steps=steps,
        total_points=len(points),
        provider_preflight_error=provider_preflight_error,
        stop_reason=stop_reason,
        max_provider_concurrency_used=concurrency_used,
        downgrade_events=downgrade_events,
        circuit_breaker=circuit_breaker,
    )
    (run_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def run_date_wave(
    *,
    config: RunConfig,
    run_root: Path,
    cache: LocalJsonCache,
    client: MockDecisionClient | KimiDecisionClient | GlmSophnetDecisionClient | CodexCliBackendDecisionClient,
    points: list[DecisionPoint],
    feedback_by_key: dict[tuple[str, InputLayer], list[dict[str, Any]]],
    concurrency: int,
    circuit_breaker: CircuitBreakerState,
    prior_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    worker_count = max(1, concurrency)
    if not points:
        return steps
    decision_date = points[0].decision_date
    feedback_snapshot_by_key: dict[tuple[str, InputLayer], tuple[list[dict[str, Any]], dict[str, Any]]] = {}
    for point in points:
        self_feedback = matured_feedback(
            feedback_by_key.get((point.ticker, point.input_layer), []),
            decision_date=decision_date,
        )
        external_filter = feedback_artifact_filter_result(
            feedback_artifacts_path=config.feedback_artifacts_path,
            decision_date=decision_date,
            ticker=point.ticker,
            input_layer=point.input_layer,
            current_run_id=config.run_id,
        )
        external_feedback = list(external_filter["accepted_feedback"])
        diagnostics = feedback_filter_diagnostics(external_filter)
        diagnostics["feedback_source_kind_counts"] = feedback_source_kind_counts_for_feedback(
            [*external_feedback, *self_feedback]
        )
        feedback_snapshot_by_key[(point.ticker, point.input_layer)] = (
            [*external_feedback, *self_feedback],
            diagnostics,
        )
    tasks: list[ArmTask] = []
    for point in points:
        feedback_snapshot, feedback_diagnostics_row = feedback_snapshot_by_key.get(
            (point.ticker, point.input_layer),
            ([], feedback_filter_diagnostics_empty()),
        )
        for arm in ARMS:
            tasks.append(
                ArmTask(
                    point=point,
                    arm=arm,
                    feedback=feedback_snapshot if arm == "full_gotra" else [],
                    feedback_filter_diagnostics=(
                        feedback_diagnostics_row if arm == "full_gotra" else feedback_filter_diagnostics_empty()
                    ),
                )
            )
    next_task_index = 0
    futures: dict[Any, ArmTask] = {}

    def submit_available(executor: ThreadPoolExecutor) -> None:
        nonlocal next_task_index
        while (
            next_task_index < len(tasks)
            and len(futures) < worker_count
            and not circuit_breaker.triggered
        ):
            task = tasks[next_task_index]
            next_task_index += 1
            futures[
                executor.submit(
                    complete_step,
                    config=config,
                    run_root=run_root,
                    cache=cache,
                    client=client,
                    point=task.point,
                    arm=task.arm,
                    feedback=task.feedback,
                    feedback_filter_diagnostics=task.feedback_filter_diagnostics,
                )
            ] = task

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        submit_available(executor)
        while futures:
            for future in as_completed(list(futures)):
                futures.pop(future)
                step = future.result()
                steps.append(step)
                maybe_trigger_circuit_breaker(
                    circuit_breaker,
                    steps=[*prior_steps, *steps],
                    attempted_steps=len(prior_steps) + len(steps),
                    inflight=len(futures),
                )
                submit_available(executor)
                break

    for step in sorted(steps, key=step_sort_key):
        if step.get("arm") == "full_gotra" and step.get("status") == "scored":
            ticker = str(step["ticker"])
            input_layer = normalize_input_layer(step["input_layer"])
            feedback_by_key.setdefault((ticker, input_layer), []).append(
                {
                    "feedback_ref": feedback_ref_for_step(step),
                    "ticker": ticker,
                    "prior_decision_date": step["decision_date"],
                    "decision_date": step["decision_date"],
                    "input_layer": input_layer,
                    "outcome_availability_date": step["outcome_as_of"],
                    "age_days": 0,
                    "source_kind": "self_feedback",
                    "feedback_source_kind": "self_feedback",
                    "error": step["error"],
                    "mse": step["mse"],
                    "actual_change_pct": step["actual_change_pct"],
                    "expected_change_pct": step["expected_change_pct"],
                    "direction": step["direction"],
                    "direction_hit": step["direction_hit"],
                }
            )
    return sorted(steps, key=step_sort_key)


def feedback_ref_for_step(step: dict[str, Any]) -> str:
    return ":".join(
        [
            "feedback",
            ticker_slug(str(step["ticker"])),
            str(step["input_layer"]),
            str(step["decision_date"]),
        ]
    )


def matured_feedback(items: list[dict[str, Any]], *, decision_date: date) -> list[dict[str, Any]]:
    matured: list[dict[str, Any]] = []
    for item in items:
        if not item.get("outcome_availability_date"):
            continue
        outcome_date = parse_date(str(item["outcome_availability_date"]))
        if outcome_date > decision_date:
            continue
        normalized = dict(item)
        normalized["age_days"] = (decision_date - outcome_date).days
        normalized.setdefault("prior_decision_date", normalized.get("decision_date"))
        normalized.setdefault("source_kind", "self_feedback")
        normalized.setdefault("feedback_source_kind", normalized.get("source_kind"))
        matured.append(normalized)
    return sorted(matured, key=lambda item: (str(item["decision_date"]), str(item.get("input_layer"))))


def maybe_trigger_circuit_breaker(
    circuit_breaker: CircuitBreakerState,
    *,
    steps: list[dict[str, Any]],
    attempted_steps: int,
    inflight: int,
) -> None:
    if circuit_breaker.triggered:
        return
    reason = circuit_breaker_reason(steps)
    if not reason:
        return
    circuit_breaker.triggered = True
    circuit_breaker.trigger_reason = reason
    circuit_breaker.attempted_steps_at_trigger = attempted_steps
    circuit_breaker.inflight_at_trigger = inflight


def circuit_breaker_reason(steps: list[dict[str, Any]]) -> str:
    if count_error_type(steps, "provider_http_429"):
        return "HTTP 429 observed"
    if count_error_type(steps, "future_data_violation"):
        return "future-data violation observed"
    if count_error_type(steps, "research_source_leak"):
        return "research source leak observed"
    if count_error_type(steps, "feedback_source_leak"):
        return "feedback source leak observed"
    if count_error_type(steps, "input_echo_error"):
        return "input echo error observed"
    if schema_error_count(steps):
        return "schema/parser error observed"
    if consecutive_error_type(steps, "provider_timeout") >= 2:
        return "consecutive provider_timeout >= 2"
    provider_errors = sum(1 for step in steps if step.get("status") == "provider_error")
    if len(steps) >= 20 and provider_errors / len(steps) > 0.05:
        return "provider_error_rate > 0.05 after 20 attempted steps"
    return ""


def should_increase_concurrency(*, config: RunConfig, wave_steps: list[dict[str, Any]]) -> bool:
    if config.mode != "provider-pilot" or not config.adaptive_concurrency:
        return False
    if not wave_steps:
        return False
    if any(step.get("status") != "scored" for step in wave_steps):
        return False
    if any(count_error_type(wave_steps, item) for item in ("provider_http_429",)):
        return False
    if schema_error_count(wave_steps):
        return False
    durations: list[float] = []
    timeout_budgets: list[float] = []
    for step in wave_steps:
        duration = step.get("request_duration_seconds")
        timeout_budget = step.get("request_timeout_seconds")
        if duration is None or timeout_budget in {None, 0}:
            continue
        durations.append(float(duration))
        timeout_budgets.append(float(timeout_budget))
    if not durations or not timeout_budgets:
        return False
    return percentile(durations, 0.95) < 0.7 * min(timeout_budgets)


def try_price_context(point: DecisionPoint, *, price_dir: Path) -> PriceContext | None:
    try:
        return price_context_for(point, price_dir=price_dir)
    except Exception:  # noqa: BLE001 - summary should preserve provider blocker first.
        return None


def provider_preflight_blocker(config: RunConfig) -> str:
    if config.mode == "mock":
        return ""
    if config.provider == CODEX_CLI_BACKEND:
        if not shutil.which(config.codex_cli_binary):
            return "CODEX_CLI_BACKEND_BLOCKED: codex_cli_executable_missing"
        if not codex_cli_version(config.codex_cli_binary):
            return "CODEX_CLI_BACKEND_BLOCKED: codex_cli_version_unavailable"
        return ""
    if config.provider not in {"glm_sophnet", "kimi"}:
        return f"unsupported provider: {config.provider}"
    if config.provider == "glm_sophnet" and not v2.sophnet_api_key():
        return "PROVIDER_BLOCKED_PRE_HTTP: SOPHNET_API_KEY/API_KEY=not_set"
    if config.provider == "kimi" and not os.getenv("SOPHNET_API_KEY", "").strip():
        return "PROVIDER_BLOCKED_PRE_HTTP: SOPHNET_API_KEY=not_set"
    return ""


def pilot_stop_reason(*, steps: list[dict[str, Any]], total_points: int) -> str:
    if not steps:
        return ""
    breaker_reason = circuit_breaker_reason(steps)
    if breaker_reason:
        return breaker_reason
    provider_errors = sum(1 for step in steps if step.get("status") == "provider_error")
    if consecutive_provider_errors(steps) >= 3:
        return "consecutive provider_error >= 3"
    if len(steps) >= 20 and provider_errors / max(1, len(steps)) > 0.05:
        return "provider_error_rate > 0.05"
    complete = paired_complete_count(steps)
    denominator = scored_point_count_from_total_steps(steps, total_points)
    if denominator <= 0:
        return ""
    attempted = attempted_scored_point_count(steps)
    remaining = max(0, denominator - attempted)
    if (complete + remaining) / denominator < 0.95:
        return "paired coverage no longer feasible"
    return ""


def scored_point_count_from_total_steps(steps: list[dict[str, Any]], total_points: int) -> int:
    if not steps:
        return total_points
    warm_points = {
        (step.get("ticker"), step.get("decision_date"), step.get("input_layer"))
        for step in steps
        if step.get("scoring_segment") == "warm_up"
    }
    return max(0, total_points - len(warm_points))


def attempted_scored_point_count(steps: list[dict[str, Any]]) -> int:
    attempted = {
        paired_key(step)
        for step in steps
        if step.get("scoring_segment") == "scored"
    }
    return len(attempted)


def consecutive_provider_errors(steps: list[dict[str, Any]]) -> int:
    count = 0
    for step in sorted(steps, key=step_sort_key):
        if step.get("status") == "provider_error":
            count += 1
        else:
            count = 0
    return count


def consecutive_error_type(steps: list[dict[str, Any]], error_type: str) -> int:
    count = 0
    for step in sorted(steps, key=step_sort_key):
        if step.get("error_type") == error_type:
            count += 1
        else:
            count = 0
    return count


def count_error_type(steps: list[dict[str, Any]], error_type: str) -> int:
    return sum(1 for step in steps if step.get("error_type") == error_type)


def schema_error_count(steps: list[dict[str, Any]]) -> int:
    return (
        count_error_type(steps, "json_decode_error")
        + count_error_type(steps, "schema_parse_error")
        + count_error_type(steps, "schema_contract_error")
        + count_error_type(steps, "input_echo_error")
    )


def summarize_run(
    *,
    config: RunConfig,
    steps: list[dict[str, Any]],
    total_points: int,
    provider_preflight_error: str,
    stop_reason: str,
    max_provider_concurrency_used: int,
    downgrade_events: list[dict[str, Any]],
    circuit_breaker: CircuitBreakerState | None = None,
) -> dict[str, Any]:
    circuit_breaker = circuit_breaker or CircuitBreakerState()
    provider_errors = sum(1 for step in steps if step.get("status") == "provider_error")
    schema_pass = sum(1 for step in steps if step.get("status") == "scored")
    timeout_count = count_error_type(steps, "provider_timeout")
    json_decode_errors = count_error_type(steps, "json_decode_error") + count_error_type(
        steps, "schema_parse_error"
    )
    schema_contract_errors = count_error_type(steps, "schema_contract_error")
    input_echo_errors = count_error_type(steps, "input_echo_error")
    http_429_count = count_error_type(steps, "provider_http_429") + sum(
        1
        for step in steps
        if step.get("error_type") != "provider_http_429" and is_http_429(step.get("error_message"))
    )
    schema_errors = schema_error_count(steps)
    future_violations = count_error_type(steps, "future_data_violation")
    research_source_leak_count = sum(
        1
        for step in steps
        if step.get("error_type") == "research_source_leak" or step.get("research_source_leak")
    )
    feedback_source_leak_count = sum(
        1
        for step in steps
        if step.get("error_type") == "feedback_source_leak" or step.get("feedback_source_leak")
    )
    auth_missing_count = count_error_type(steps, "auth_missing")
    codex_cli_backend_blocked_count = count_error_type(steps, "codex_cli_backend_blocked")
    provider_http_error_count = count_error_type(steps, "provider_http_error")
    price_missing_count = count_error_type(steps, "price_missing")
    retryable_provider_error_recovered_count = sum(
        1
        for step in steps
        if step.get("status") == "scored" and int(step.get("provider_retry_count") or 0) > 0
    )
    rejected_research_artifact_count = sum(
        int(step.get("rejected_research_artifact_count") or 0) for step in steps
    )
    rejected_research_future_data_count = sum(
        int(step.get("rejected_research_future_data_count") or 0) for step in steps
    )
    rejected_research_schema_count = sum(
        int(step.get("rejected_research_schema_count") or 0) for step in steps
    )
    rejected_feedback_artifact_count = sum(
        int(step.get("rejected_feedback_artifact_count") or 0) for step in steps
    )
    rejected_feedback_future_data_count = sum(
        int(step.get("rejected_feedback_future_data_count") or 0) for step in steps
    )
    rejected_feedback_schema_count = sum(
        int(step.get("rejected_feedback_schema_count") or 0) for step in steps
    )
    rejected_feedback_non_independent_count = sum(
        int(step.get("rejected_feedback_non_independent_count") or 0) for step in steps
    )
    rejected_feedback_current_run_count = sum(
        int(step.get("rejected_feedback_current_run_count") or 0) for step in steps
    )
    rejected_feedback_duplicate_count = sum(
        int(step.get("rejected_feedback_duplicate_count") or 0) for step in steps
    )
    source_kind_counts = source_kind_counts_for_steps(steps)
    feedback_source_kind_counts = feedback_source_kind_counts_for_steps(steps)
    strict_feedback_points = strict_feedback_eligible_count(steps)
    true_independent_feedback_points = true_independent_feedback_eligible_count(steps)
    paired = paired_complete_count(steps)
    scored_points = total_scored_points(config)
    expected_steps = total_points * len(ARMS)
    provider_error_rate = provider_errors / expected_steps if expected_steps else 0.0
    scored_step_count = schema_pass
    if config.mode == "mock":
        mock_clean = (
            provider_errors == 0
            and future_violations == 0
            and schema_errors == 0
            and research_source_leak_count == 0
            and feedback_source_leak_count == 0
            and price_missing_count == 0
            and len(steps) == expected_steps
            and scored_step_count == expected_steps
        )
        if mock_clean and scored_points > 0 and paired > 0 and paired == scored_points:
            status = "MOCK_PASS"
        elif mock_clean and (scored_points == 0 or paired == 0):
            status = "DATA_INSUFFICIENT"
        else:
            status = "HARNESS_NEEDS_FIX"
    elif config.mode == "provider-canary":
        if provider_preflight_error.startswith("PROVIDER_BLOCKED_PRE_HTTP"):
            status = "PROVIDER_BLOCKED_PRE_HTTP"
        elif provider_preflight_error.startswith("CODEX_CLI_BACKEND_BLOCKED"):
            status = "CODEX_CLI_BACKEND_BLOCKED"
        else:
            canary_passed = (
                provider_errors == 0
                and future_violations == 0
                and schema_errors == 0
                and research_source_leak_count == 0
                and feedback_source_leak_count == 0
                and price_missing_count == 0
                and schema_pass == expected_steps
            )
            status = "PROVIDER_CANARY_PASS" if canary_passed else "PROVIDER_CANARY_FAIL"
    else:
        if provider_preflight_error.startswith("CODEX_CLI_BACKEND_BLOCKED"):
            status = "CODEX_CLI_BACKEND_BLOCKED"
        elif provider_preflight_error.startswith("PROVIDER_BLOCKED_PRE_HTTP"):
            status = "PROVIDER_BLOCKED_PRE_HTTP"
        elif circuit_breaker.triggered:
            status = "STOPPED_BY_CIRCUIT_BREAKER"
        else:
            status = (
                "PROVIDER_PILOT_PASS"
                if provider_errors == 0
                and future_violations == 0
                and schema_errors == 0
                and research_source_leak_count == 0
                and feedback_source_leak_count == 0
                and price_missing_count == 0
                and paired / max(1, scored_points) >= 0.95
                else "PROVIDER_PILOT_FAIL"
            )
    provider_limits = provider_limit_metadata(config)
    provider_tokens = provider_max_tokens_metadata(config)
    provider_temperature = provider_temperature_metadata(config)
    codex_backend = codex_cli_backend_metadata(config)
    paired_diff_summary = paired_diffs(steps)
    statistical_test_summary = statistical_tests(steps)
    return {
        "schema": SUMMARY_SCHEMA,
        "definition_version": DEFINITION_VERSION,
        "decision_schema": DECISION_SCHEMA,
        "step_schema": STEP_SCHEMA,
        "run_id": config.run_id,
        "mode": config.mode,
        "status": status,
        "provider": config.provider,
        "target_provider": config.provider,
        "target_provider_model": config.provider_model,
        "provider_model": config.provider_model,
        "provider_execution_mode": provider_execution_mode(config),
        "provider_base_url": config.provider_base_url,
        "provider_max_tokens": config.provider_max_tokens,
        **provider_tokens,
        **provider_temperature,
        **codex_backend,
        "provider_call_status": provider_call_status(
            mode=config.mode,
            provider=config.provider,
            provider_preflight_error=provider_preflight_error,
        ),
        "provider_limits": provider_limits,
        **provider_limits,
        "token_budget_authorized": config.token_budget,
        "provider_preflight_error": provider_preflight_error,
        "stop_reason": stop_reason,
        "arms": list(ARMS),
        "arm_interpretation": arm_interpretation_summary(),
        "input_layers": list(config.input_layers),
        "warm_up_dates": config.warm_up_dates,
        "repeat_run_index": config.repeat_run_index,
        "research_artifacts_path": str(config.research_artifacts_path or ""),
        "feedback_artifacts_path": str(config.feedback_artifacts_path or ""),
        "expected_points": total_points,
        "expected_scored_points": scored_points,
        "expected_steps": expected_steps,
        "actual_step_files": len(steps),
        "scored_step_count": scored_step_count,
        "schema_pass_count": schema_pass,
        "schema_pass_rate": schema_pass / expected_steps if expected_steps else 0.0,
        "paired_complete_points": paired,
        "paired_coverage": paired / scored_points if scored_points else 0.0,
        "future_data_violations": future_violations,
        "research_source_leak_count": research_source_leak_count,
        "feedback_source_leak_count": feedback_source_leak_count,
        "rejected_research_artifact_count": rejected_research_artifact_count,
        "rejected_research_future_data_count": rejected_research_future_data_count,
        "rejected_research_schema_count": rejected_research_schema_count,
        "rejected_feedback_artifact_count": rejected_feedback_artifact_count,
        "rejected_feedback_future_data_count": rejected_feedback_future_data_count,
        "rejected_feedback_schema_count": rejected_feedback_schema_count,
        "rejected_feedback_non_independent_count": rejected_feedback_non_independent_count,
        "rejected_feedback_current_run_count": rejected_feedback_current_run_count,
        "rejected_feedback_duplicate_count": rejected_feedback_duplicate_count,
        "h1_research_evidence_status": h1_research_evidence_status(source_kind_counts),
        "provider_error_count": provider_errors,
        "provider_error_rate": provider_error_rate,
        "adaptive_concurrency": config.adaptive_concurrency,
        "max_provider_concurrency_requested": config.max_provider_concurrency,
        "max_provider_concurrency_used": max_provider_concurrency_used,
        "scheduler_policy": config.scheduler_policy,
        "timeout_policy": timeout_policy_manifest(config),
        "timeout_retries": config.timeout_retries,
        "timeout_retry_backoff_seconds": config.timeout_retry_backoff_seconds,
        "timeout_count": timeout_count,
        "http_429_count": http_429_count,
        "schema_error_count": schema_errors,
        "json_decode_error_count": json_decode_errors,
        "schema_contract_error_count": schema_contract_errors,
        "input_echo_error_count": input_echo_errors,
        "future_data_violation_count": future_violations,
        "auth_missing_count": auth_missing_count,
        "codex_cli_backend_blocked_count": codex_cli_backend_blocked_count,
        "provider_http_error_count": provider_http_error_count,
        "retryable_provider_error_recovered_count": retryable_provider_error_recovered_count,
        "unrecovered_provider_timeout_count": timeout_count,
        "unrecovered_provider_http_error_count": provider_http_error_count,
        "price_missing_count": price_missing_count,
        "normalization_counts": normalization_counts(steps),
        "raw_content_saved_count": sum(
            1 for step in steps if step.get("provider_raw_content_path")
        ),
        "codex_cli_transcript_path_count": sum(
            1 for step in steps if step.get("output_transcript_path")
        ),
        "parsed_decision_hash_count": sum(
            1 for step in steps if step.get("parsed_decision_hash")
        ),
        "full_gotra_scored_points": full_gotra_scored_count(steps),
        "full_gotra_feedback_available_scored_points": full_gotra_feedback_available_count(steps),
        "full_gotra_high_quality_feedback_scored_points": full_gotra_high_quality_feedback_count(steps),
        "self_feedback_available_points": self_feedback_available_count(steps),
        "strict_feedback_eligible_points": strict_feedback_points,
        "true_independent_feedback_eligible_points": true_independent_feedback_points,
        "h2_data_status": h2_data_status(true_independent_feedback_points),
        "h2_data_insufficient_reason": h2_data_insufficient_reason(steps),
        "C4_feedback_eligible_paired_points": paired_diff_summary[
            "C4_real_research_minus_full_gotra_mse"
        ]["paired_points"],
        "feedback_path_exercised": full_gotra_feedback_available_count(steps) > 0,
        "synthetic_evidence_count": sum(int(step.get("synthetic_evidence_count") or 0) for step in steps),
        "source_kind_counts": source_kind_counts,
        "feedback_source_kind_counts": feedback_source_kind_counts,
        "feedback_eligibility_diagnostics": feedback_diagnostics(steps),
        "reasoning_chars_by_arm": reasoning_chars_by_arm(steps),
        "circuit_breaker_triggered": circuit_breaker.triggered,
        "trigger_reason": circuit_breaker.trigger_reason,
        "attempted_steps_at_trigger": circuit_breaker.attempted_steps_at_trigger,
        "inflight_at_trigger": circuit_breaker.inflight_at_trigger,
        "downgrade_events": downgrade_events,
        "request_diagnostics_by_arm": request_diagnostics_by_arm(steps),
        "metrics": metrics_by_arm(steps),
        "product_metrics": product_metrics_by_arm(steps),
        "paired_diffs": paired_diff_summary,
        "statistical_tests": statistical_test_summary,
        "root_failure": root_failure(steps),
        "evidence_layer": evidence_layer_summary(),
    }


def total_scored_points(config: RunConfig) -> int:
    scored_dates = max(0, len(config.dates) - max(0, config.warm_up_dates))
    return len(config.tickers) * scored_dates * len(config.input_layers)


def provider_execution_mode(config: RunConfig) -> str:
    if config.mode == "mock":
        return "local_mock"
    if config.provider == CODEX_CLI_BACKEND:
        return CODEX_CLI_BACKEND
    return "provider_http"


def provider_call_status(*, mode: Mode, provider: str, provider_preflight_error: str) -> str:
    if mode == "mock" or provider_preflight_error.startswith("PROVIDER_BLOCKED_PRE_HTTP"):
        return "no real provider HTTP call"
    if provider_preflight_error.startswith("CODEX_CLI_BACKEND_BLOCKED"):
        return "no Codex CLI backend call"
    if provider == CODEX_CLI_BACKEND:
        if mode == "provider-pilot":
            return "Codex CLI backend pilot attempted"
        return "Codex CLI backend canary attempted"
    if mode == "provider-pilot":
        return "provider HTTP pilot attempted"
    return "provider HTTP canary attempted"


def root_failure(steps: list[dict[str, Any]]) -> str:
    for step in sorted(steps, key=step_sort_key):
        if step.get("status") == "provider_error":
            return "/".join(
                [
                    str(step.get("error_type") or "provider_error"),
                    str(step.get("arm") or ""),
                    str(step.get("input_layer") or ""),
                    str(step.get("ticker") or ""),
                    str(step.get("decision_date") or ""),
                ]
            )
    return ""


def evidence_layer_summary() -> dict[str, str]:
    return {
        "local_checks": "v3 implementation tests, lint, py_compile, and mock harness run",
        "provider_runtime_health": "not entered unless provider-canary/provider-pilot is run",
        "formal_lite_acceptance": "not entered by this implementation goal",
        "science_public_claim": "not entered",
    }


def arm_interpretation_summary() -> dict[str, str]:
    return {
        "direct_llm": (
            "direct_llm_parametric_memory_control; not a clean historical no-future baseline"
        ),
        "ksana_formatting_only": "formatting/scaffold control arm",
        "ksana_real_research": "time-bounded research packet arm when evidence is available",
        "full_gotra": "research plus eligible Alaya feedback arm",
        "clean_historical_reference": "deterministic_price_only_baseline or future-only/forward-live evidence",
    }


def metrics_by_arm(steps: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        scored = [
            step
            for step in steps
            if step.get("arm") == arm
            and step.get("status") == "scored"
            and step.get("scoring_segment") == "scored"
        ]
        if not scored:
            output[arm] = {
                "scored_steps": 0,
                "direction_hit_rate": None,
                "mse": None,
                "mae": None,
                "policy_a_cumulative_return_pct": None,
                "calibration": calibration_and_abstain_metrics([]),
            }
            continue
        direction_hits = [1 if step.get("direction_hit") else 0 for step in scored]
        output[arm] = {
            "scored_steps": len(scored),
            "direction_hit_rate": sum(direction_hits) / len(direction_hits),
            "mse": mean_float(step["mse"] for step in scored),
            "mae": mean_float(step["mae"] for step in scored),
            "policy_a_cumulative_return_pct": policy_a_cumulative_return(scored),
            "calibration": calibration_and_abstain_metrics(scored),
        }
    return output


def calibration_and_abstain_metrics(scored: list[dict[str, Any]]) -> dict[str, Any]:
    confidence_rows = [
        (float(step["confidence"]), 1.0 if step.get("direction_hit") else 0.0)
        for step in scored
        if isinstance(step.get("confidence"), (int, float))
        and not isinstance(step.get("confidence"), bool)
        and step.get("direction_hit") is not None
    ]
    brier = (
        round(mean_float((confidence - hit) ** 2 for confidence, hit in confidence_rows), 6)
        if confidence_rows
        else None
    )
    bins: list[dict[str, Any]] = []
    for index in range(5):
        lower = index / 5
        upper = (index + 1) / 5
        if index == 4:
            rows = [(confidence, hit) for confidence, hit in confidence_rows if lower <= confidence <= upper]
        else:
            rows = [(confidence, hit) for confidence, hit in confidence_rows if lower <= confidence < upper]
        bins.append(
            {
                "lower": round(lower, 2),
                "upper": round(upper, 2),
                "count": len(rows),
                "mean_confidence": mean_float(confidence for confidence, _hit in rows),
                "direction_hit_rate": mean_float(hit for _confidence, hit in rows),
            }
        )
    abstain_steps = [step for step in scored if str(step.get("abstain_reason") or "").strip()]
    non_abstain_steps = [step for step in scored if step not in abstain_steps]
    return {
        "confidence_count": len(confidence_rows),
        "brier_score_direction": brier,
        "calibration_bins": bins,
        "abstain_count": len(abstain_steps),
        "abstain_rate": round(len(abstain_steps) / len(scored), 6) if scored else 0.0,
        "abstain_realized_abs_change_mean": mean_float(
            abs(float(step["actual_change_pct"]))
            for step in abstain_steps
            if step.get("actual_change_pct") is not None
        ),
        "non_abstain_realized_abs_change_mean": mean_float(
            abs(float(step["actual_change_pct"]))
            for step in non_abstain_steps
            if step.get("actual_change_pct") is not None
        ),
    }


def request_diagnostics_by_arm(steps: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        arm_steps = [step for step in steps if step.get("arm") == arm]
        output[arm] = {
            "prompt_chars": min_max_value(arm_steps, "prompt_chars"),
            "prompt_bytes": min_max_value(arm_steps, "prompt_bytes"),
            "request_duration_seconds": distribution_value(arm_steps, "request_duration_seconds"),
            "request_timeout_seconds": min_max_value(arm_steps, "request_timeout_seconds"),
            "provider_attempts": min_max_value(arm_steps, "provider_attempts"),
            "provider_retry_count": min_max_value(arm_steps, "provider_retry_count"),
            "provider_temperature": min_max_value(arm_steps, "provider_temperature"),
            "provider_temperature_fallback_count": sum(
                1 for step in arm_steps if step.get("provider_temperature_fallback")
            ),
            "provider_error_classes": sorted(
                {
                    str(step.get("provider_error_class"))
                    for step in arm_steps
                    if step.get("provider_error_class")
                }
            ),
            "last_retryable_error_types": sorted(
                {
                    str(step.get("last_retryable_error_type"))
                    for step in arm_steps
                    if step.get("last_retryable_error_type")
                }
            ),
            "retryable_provider_error_recovered_count": sum(
                1
                for step in arm_steps
                if step.get("status") == "scored" and int(step.get("provider_retry_count") or 0) > 0
            ),
            "normalization_applied_count": sum(
                1 for step in arm_steps if step.get("normalization_applied")
            ),
            "input_echo_error_count": count_error_type(arm_steps, "input_echo_error"),
            "raw_content_saved_count": sum(
                1 for step in arm_steps if step.get("provider_raw_content_path")
            ),
            "codex_cli_transcript_path_count": sum(
                1 for step in arm_steps if step.get("output_transcript_path")
            ),
            "parsed_decision_hash_count": sum(
                1 for step in arm_steps if step.get("parsed_decision_hash")
            ),
        }
    return output


def normalization_counts(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return v2.normalization_counts(steps)


def min_max_value(steps: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    return v2.min_max_value(steps, field)


def distribution_value(steps: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    return v2.distribution_value(steps, field)


def percentile(values: list[float], quantile: float) -> float:
    return v2.percentile(values, quantile)


def product_metrics_by_arm(steps: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        scored = [
            step
            for step in steps
            if step.get("arm") == arm
            and step.get("status") == "scored"
            and step.get("scoring_segment") == "scored"
        ]
        recomputed = [product_metrics_for_step(step) for step in scored]
        metric_names = sorted(
            {
                str(name)
                for metrics in recomputed
                for name in metrics.keys()
            }
        )
        output[arm] = {
            name: mean_float(metrics.get(name) for metrics in recomputed)
            for name in metric_names
        }
        output[arm]["scored_steps"] = len(scored)
    return output


def load_scored_steps_from_run(run_root: Path) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for path in sorted(run_root.glob("*/step_*.json")):
        step = json.loads(path.read_text(encoding="utf-8"))
        if step.get("status") == "scored":
            steps.append(step)
    return steps


def feedback_diagnostics(steps: list[dict[str, Any]]) -> dict[str, Any]:
    full_scored = [
        step
        for step in steps
        if step.get("arm") == "full_gotra"
        and step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
    ]
    by_date_layer: dict[str, dict[str, Any]] = {}
    for step in full_scored:
        key = f"{step.get('decision_date')}|{step.get('input_layer')}"
        row = by_date_layer.setdefault(
            key,
            {
                "decision_date": step.get("decision_date"),
                "input_layer": step.get("input_layer"),
                "points": 0,
                "self_feedback_available_points": 0,
                "strict_feedback_eligible_points": 0,
                "true_independent_feedback_eligible_points": 0,
                "feedback_used_count_min": None,
                "feedback_used_count_max": None,
                "feedback_age_days_max_min": None,
                "feedback_age_days_max_max": None,
                "feedback_source_kind_counts": feedback_source_kind_counts_for_feedback([]),
            },
        )
        row["points"] += 1
        row["self_feedback_available_points"] += 1 if step.get("self_feedback_available") else 0
        row["strict_feedback_eligible_points"] += 1 if step.get("strict_feedback_eligible") else 0
        row["true_independent_feedback_eligible_points"] += (
            1 if step.get("true_independent_feedback_eligible") else 0
        )
        step_counts = step.get("feedback_source_kind_counts") or {}
        if isinstance(step_counts, dict):
            for key, value in step_counts.items():
                normalized_key = str(key) if str(key) in row["feedback_source_kind_counts"] else "unknown"
                row["feedback_source_kind_counts"][normalized_key] += int(value or 0)
        update_min_max(row, "feedback_used_count", step.get("feedback_used_count"))
        update_min_max(row, "feedback_age_days_max", step.get("feedback_age_days_max"))
    return {
        "full_gotra_scored_points": len(full_scored),
        "feedback_available_points": full_gotra_feedback_available_count(steps),
        "high_quality_feedback_points": full_gotra_high_quality_feedback_count(steps),
        "self_feedback_available_points": self_feedback_available_count(steps),
        "strict_feedback_eligible_points": strict_feedback_eligible_count(steps),
        "true_independent_feedback_eligible_points": true_independent_feedback_eligible_count(steps),
        "h2_data_status": h2_data_status(true_independent_feedback_eligible_count(steps)),
        "h2_data_insufficient_reason": h2_data_insufficient_reason(steps),
        "feedback_source_kind_counts": feedback_source_kind_counts_for_steps(steps),
        "rejected_feedback_artifact_count": sum(
            int(step.get("rejected_feedback_artifact_count") or 0) for step in steps
        ),
        "rejected_feedback_future_data_count": sum(
            int(step.get("rejected_feedback_future_data_count") or 0) for step in steps
        ),
        "rejected_feedback_schema_count": sum(
            int(step.get("rejected_feedback_schema_count") or 0) for step in steps
        ),
        "rejected_feedback_non_independent_count": sum(
            int(step.get("rejected_feedback_non_independent_count") or 0) for step in steps
        ),
        "rejected_feedback_current_run_count": sum(
            int(step.get("rejected_feedback_current_run_count") or 0) for step in steps
        ),
        "rejected_feedback_duplicate_count": sum(
            int(step.get("rejected_feedback_duplicate_count") or 0) for step in steps
        ),
        "feedback_source_leak_count": sum(
            1
            for step in steps
            if step.get("error_type") == "feedback_source_leak" or step.get("feedback_source_leak")
        ),
        "by_scored_date_input_layer": list(by_date_layer.values()),
    }


def update_min_max(row: dict[str, Any], field: str, value: Any) -> None:
    if value is None:
        return
    number = int(value)
    min_key = f"{field}_min"
    max_key = f"{field}_max"
    row[min_key] = number if row[min_key] is None else min(row[min_key], number)
    row[max_key] = number if row[max_key] is None else max(row[max_key], number)


def hac_table_rows(stat_tests: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in ("all", "price_only_packet", "richer_research_packet"):
        for comparison, item in (stat_tests.get(bucket) or {}).items():
            hac = item.get("hac") or {}
            cluster_results = [
                result
                for result in (hac.get("cluster_results") or {}).values()
                if isinstance(result, dict)
            ]
            z_values = [
                float(result["z_score"])
                for result in cluster_results
                if isinstance(result.get("z_score"), (int, float))
                and not isinstance(result.get("z_score"), bool)
            ]
            p_values = [
                float(result["p_value"])
                for result in cluster_results
                if isinstance(result.get("p_value"), (int, float))
                and not isinstance(result.get("p_value"), bool)
            ]
            rows.append(
                {
                    "bucket": bucket,
                    "comparison": comparison,
                    "paired_points": item.get("paired_points"),
                    "hac_status": (
                        "completed"
                        if hac.get("statistical_test_completed")
                        else str(hac.get("reason") or "insufficient")
                    ),
                    "hac_aggregation": hac.get("aggregation"),
                    "hac_mean_loss_diff": hac.get("mean_loss_diff"),
                    "hac_n": hac.get("n"),
                    "hac_n_clusters": hac.get("n_clusters"),
                    "hac_completed_cluster_count": hac.get("completed_cluster_count"),
                    "hac_reason": hac.get("reason"),
                    "hac_cluster_z_min": min(z_values) if z_values else None,
                    "hac_cluster_z_max": max(z_values) if z_values else None,
                    "hac_cluster_p_min": min(p_values) if p_values else None,
                    "hac_cluster_p_max": max(p_values) if p_values else None,
                    "hac_cluster_p_below_0_05_count": sum(1 for value in p_values if value < 0.05),
                }
            )
    return rows


def recompute_run_report(run_root: Path) -> dict[str, Any]:
    steps = load_scored_steps_from_run(run_root)
    stat_tests = statistical_tests(steps)
    return {
        "schema": "gotra.baseline_v3.recompute_report.v1",
        "run_root": str(run_root),
        "scored_step_count": len(steps),
        "product_metrics": product_metrics_by_arm(steps),
        "feedback_diagnostics": feedback_diagnostics(steps),
        "source_kind_counts": source_kind_counts_for_steps(steps),
        "paired_diffs": paired_diffs(steps),
        "hac_table": hac_table_rows(stat_tests),
        "statistical_tests": stat_tests,
    }


def reasoning_chars_by_arm(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        arm: distribution_value([step for step in steps if step.get("arm") == arm], "reasoning_chars")
        for arm in ARMS
    }


def paired_diffs(steps: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = {
        "C1_direct_minus_formatting_mse": ("direct_llm", "ksana_formatting_only"),
        "C2_formatting_minus_real_research_mse": (
            "ksana_formatting_only",
            "ksana_real_research",
        ),
        "C3_direct_minus_real_research_mse": ("direct_llm", "ksana_real_research"),
        "C4_real_research_minus_full_gotra_mse": ("ksana_real_research", "full_gotra"),
        "C5_direct_minus_full_gotra_mse": ("direct_llm", "full_gotra"),
    }
    output: dict[str, Any] = {}
    for name, (left, right) in pairs.items():
        feedback_eligible_only = name == "C4_real_research_minus_full_gotra_mse"
        eligible_steps = feedback_eligible_steps_for_c4(steps) if feedback_eligible_only else steps
        diffs_by_ticker = paired_loss_differences_v3(eligible_steps, left, right)
        flat = [value for values in diffs_by_ticker.values() for value in values]
        output[name] = {
            "paired_points": len(flat),
            "mse_delta_left_minus_right": mean_float(flat),
            "feedback_eligible_only": feedback_eligible_only,
        }
    return output


def feedback_eligible_paired_keys(steps: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        paired_key(step)
        for step in steps
        if step.get("arm") == "full_gotra"
        and step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and bool(step.get("true_independent_feedback_eligible"))
    }


def feedback_eligible_steps_for_c4(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = feedback_eligible_paired_keys(steps)
    return [step for step in steps if paired_key(step) in keys]


def statistical_tests(steps: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons = {
        "C1_direct_minus_formatting": ("direct_llm", "ksana_formatting_only"),
        "C2_formatting_minus_real_research": ("ksana_formatting_only", "ksana_real_research"),
        "C3_direct_minus_real_research": ("direct_llm", "ksana_real_research"),
        "C4_real_research_minus_full_gotra": ("ksana_real_research", "full_gotra"),
        "C5_direct_minus_full_gotra": ("direct_llm", "full_gotra"),
    }
    output: dict[str, Any] = {}
    for layer in (*INPUT_LAYERS, "all"):
        layer_name = str(layer)
        layer_filter = None if layer_name == "all" else layer_name
        layer_output: dict[str, Any] = {}
        for name, (left, right) in comparisons.items():
            eligible_steps = steps
            if name == "C4_real_research_minus_full_gotra":
                eligible_steps = feedback_eligible_steps_for_c4(steps)
            bootstrap_diffs_by_ticker = paired_loss_differences_v3(
                eligible_steps,
                left,
                right,
                input_layer=layer_filter,
            )
            hac_diffs_by_cluster = paired_loss_differences_v3(
                eligible_steps,
                left,
                right,
                input_layer=layer_filter,
                cluster_by_input_layer=layer_filter is None,
            )
            flat = [value for values in bootstrap_diffs_by_ticker.values() for value in values]
            layer_output[name] = {
                "left": left,
                "right": right,
                "loss_diff_convention": "left_mse_minus_right_mse",
                "feedback_eligible_only": name == "C4_real_research_minus_full_gotra",
                "paired_points": len(flat),
                "hac": hac_by_cluster(hac_diffs_by_cluster),
                "cluster_bootstrap": cluster_bootstrap_ci(
                    bootstrap_diffs_by_ticker,
                    iters=10000,
                    seed=20260619,
                    left_arm=left,
                    right_arm=right,
                ),
            }
        output[layer_name] = layer_output
    return output


def hac_by_cluster(loss_diffs_by_cluster: dict[str, list[float]]) -> dict[str, Any]:
    flat = [value for values in loss_diffs_by_cluster.values() for value in values]
    cluster_results: dict[str, Any] = {}
    completed_cluster_count = 0
    for cluster, values in sorted(loss_diffs_by_cluster.items()):
        result = hac_mean_test(values)
        cluster_results[cluster] = result
        if result.get("reason") != "not_enough_paired_steps":
            completed_cluster_count += 1
    if completed_cluster_count == 0:
        return {
            "statistical_test_completed": False,
            "passed": None,
            "reason": "not_enough_time_points",
            "n_clusters": len(loss_diffs_by_cluster),
            "completed_cluster_count": 0,
            "n": len(flat),
            "mean_loss_diff": mean_float(flat),
            "cluster_results": cluster_results,
            "aggregation": "within_cluster_only",
        }
    return {
        "statistical_test_completed": True,
        "passed": None,
        "reason": "cluster_level_results_only",
        "n_clusters": len(loss_diffs_by_cluster),
        "completed_cluster_count": completed_cluster_count,
        "n": len(flat),
        "mean_loss_diff": mean_float(flat),
        "cluster_results": cluster_results,
        "aggregation": "within_cluster_only",
    }


def paired_key(step: dict[str, Any]) -> tuple[str, str, str]:
    return (str(step.get("ticker")), str(step.get("decision_date")), str(step.get("input_layer")))


def policy_a_cumulative_return(steps: list[dict[str, Any]]) -> float:
    return v2.policy_a_cumulative_return(steps)


def mean_float(values: Any) -> float | None:
    return v2.mean_float(values)


def paired_complete_count(steps: list[dict[str, Any]]) -> int:
    by_key: dict[tuple[str, str, str], set[str]] = {}
    for step in steps:
        if step.get("status") != "scored" or step.get("scoring_segment") != "scored":
            continue
        by_key.setdefault(paired_key(step), set()).add(str(step.get("arm")))
    return sum(1 for arms in by_key.values() if set(ARMS).issubset(arms))


def full_gotra_feedback_available_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and step.get("arm") == "full_gotra"
        and int(step.get("feedback_used_count") or 0) > 0
    )


def full_gotra_scored_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and step.get("arm") == "full_gotra"
    )


def full_gotra_high_quality_feedback_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and step.get("arm") == "full_gotra"
        and int(step.get("feedback_used_count") or 0) >= 3
        and int(step.get("feedback_age_days_max") or 0) >= 30
    )


def self_feedback_available_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and step.get("arm") == "full_gotra"
        and bool(step.get("self_feedback_available"))
    )


def strict_feedback_eligible_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and step.get("arm") == "full_gotra"
        and bool(step.get("strict_feedback_eligible"))
    )


def true_independent_feedback_eligible_count(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for step in steps
        if step.get("status") == "scored"
        and step.get("scoring_segment") == "scored"
        and step.get("arm") == "full_gotra"
        and bool(step.get("true_independent_feedback_eligible"))
    )


def h1_research_evidence_status(source_kind_counts: dict[str, int]) -> str:
    if source_kind_counts.get("real", 0) or source_kind_counts.get("unverified", 0):
        return "RESEARCH_EVIDENCE_PRESENT_LOCAL_MOCK"
    if source_kind_counts.get("synthetic", 0):
        return "NOT_TESTED_SYNTHETIC_ONLY"
    return "NOT_TESTED_NO_RICHER_RESEARCH_EVIDENCE"


def h2_data_status(true_independent_feedback_points: int) -> str:
    if true_independent_feedback_points > 0:
        return "STRICT_FEEDBACK_ELIGIBLE_PRESENT"
    return "DATA_INSUFFICIENT_FOR_H2_TRUE_INDEPENDENT_FEEDBACK"


def h2_data_insufficient_reason(steps: list[dict[str, Any]]) -> str:
    if true_independent_feedback_eligible_count(steps) > 0:
        return ""
    reasons = sorted(
        {
            reason
            for step in steps
            if step.get("arm") == "full_gotra"
            for reason in str(step.get("strict_feedback_insufficient_reason") or "").split(",")
            if reason and reason != "not_full_gotra_scored_segment"
        }
    )
    return ",".join(reasons) or "no_full_gotra_scored_strict_feedback_points"


def run_root_has_artifacts(run_root: Path) -> bool:
    return v2.run_root_has_artifacts(run_root)


def blocked_run_id_exists_summary(*, config: RunConfig, run_root: Path) -> dict[str, Any]:
    provider_limits = provider_limit_metadata(config)
    provider_tokens = provider_max_tokens_metadata(config)
    provider_temperature = provider_temperature_metadata(config)
    codex_backend = codex_cli_backend_metadata(config)
    return {
        "schema": SUMMARY_SCHEMA,
        "definition_version": DEFINITION_VERSION,
        "run_id": config.run_id,
        "mode": config.mode,
        "status": "BLOCKED_RUN_ID_EXISTS",
        "provider": config.provider,
        "target_provider": config.provider,
        "target_provider_model": config.provider_model,
        "provider_model": config.provider_model,
        "provider_base_url": config.provider_base_url,
        "provider_max_tokens": config.provider_max_tokens,
        **provider_tokens,
        **provider_temperature,
        **codex_backend,
        "provider_call_status": "no new provider HTTP call",
        "provider_limits": provider_limits,
        **provider_limits,
        "run_root": str(run_root),
        "stop_reason": "run_root exists and contains artifacts; pass --resume only for exact manifest match",
        "existing_artifact_count": count_files(run_root),
        "scheduler_policy": config.scheduler_policy,
        "research_artifacts_path": str(config.research_artifacts_path or ""),
        "feedback_artifacts_path": str(config.feedback_artifacts_path or ""),
        "timeout_policy": timeout_policy_manifest(config),
        "circuit_breaker_triggered": False,
        "trigger_reason": "",
        "evidence_layer": evidence_layer_summary(),
    }


def blocked_resume_summary(*, config: RunConfig, run_root: Path, reason: str) -> dict[str, Any]:
    summary = blocked_run_id_exists_summary(config=config, run_root=run_root)
    summary["status"] = "BLOCKED_RESUME_MANIFEST_MISMATCH"
    summary["stop_reason"] = reason
    return summary


def count_files(path: Path) -> int:
    return v2.count_files(path)


def resume_manifest_error(*, run_root: Path, config: RunConfig) -> str:
    manifest_path = run_root / "manifest.json"
    if not manifest_path.exists():
        return "resume requested but manifest.json is missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest_identity(config)
    mismatches = [
        key
        for key, expected_value in expected.items()
        if manifest.get(key) != expected_value
    ]
    if mismatches:
        return "resume manifest mismatch: " + ",".join(sorted(mismatches))
    return ""


def manifest_identity(config: RunConfig) -> dict[str, Any]:
    return {
        "mode": config.mode,
        "target_provider": config.provider,
        "target_provider_model": config.provider_model,
        "provider_base_url": config.provider_base_url,
        "provider_max_tokens": config.provider_max_tokens,
        "provider_temperature": provider_temperature_for(config.provider, config.provider_model),
        "codex_cli_reasoning_setting": config.codex_cli_reasoning_setting,
        "codex_cli_binary": config.codex_cli_binary,
        "tickers": list(config.tickers),
        "dates": [item.isoformat() for item in config.dates],
        "input_layers": list(config.input_layers),
        "warm_up_dates": config.warm_up_dates,
        "repeat_run_index": config.repeat_run_index,
        "scheduler_policy": config.scheduler_policy,
        "timeout_policy": timeout_policy_manifest(config),
        "provider_limits": provider_limit_metadata(config),
        "research_artifacts_path": str(config.research_artifacts_path or ""),
        "feedback_artifacts_path": str(config.feedback_artifacts_path or ""),
    }


def write_manifest(run_root: Path, config: RunConfig) -> None:
    provider_limits = provider_limit_metadata(config)
    provider_tokens = provider_max_tokens_metadata(config)
    provider_temperature = provider_temperature_metadata(config)
    codex_backend = codex_cli_backend_metadata(config)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "definition_version": DEFINITION_VERSION,
        "decision_schema": DECISION_SCHEMA,
        "step_schema": STEP_SCHEMA,
        "summary_schema": SUMMARY_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": config.run_id,
        "mode": config.mode,
        "target_provider": config.provider,
        "target_provider_model": config.provider_model,
        "provider_base_url": config.provider_base_url,
        "provider_max_tokens": config.provider_max_tokens,
        **provider_tokens,
        **provider_temperature,
        **codex_backend,
        "provider_call_status": "no real provider HTTP call" if config.mode == "mock" else "pending",
        "provider_limits": provider_limits,
        **provider_limits,
        "arms": list(ARMS),
        "arm_interpretation": arm_interpretation_summary(),
        "input_layers": list(config.input_layers),
        "warm_up_dates": config.warm_up_dates,
        "repeat_run_index": config.repeat_run_index,
        "tickers": list(config.tickers),
        "dates": [item.isoformat() for item in config.dates],
        "git": git_identity(),
        "token_budget_authorized": config.token_budget,
        "adaptive_concurrency": config.adaptive_concurrency,
        "provider_concurrency": config.provider_concurrency,
        "max_provider_concurrency": config.max_provider_concurrency,
        "scheduler_policy": config.scheduler_policy,
        "research_artifacts_path": str(config.research_artifacts_path or ""),
        "feedback_artifacts_path": str(config.feedback_artifacts_path or ""),
        "timeout_policy": timeout_policy_manifest(config),
        "timeout_retries": config.timeout_retries,
        "timeout_retry_backoff_seconds": config.timeout_retry_backoff_seconds,
        "codex_cli_reasoning_setting": config.codex_cli_reasoning_setting,
        "codex_cli_binary": config.codex_cli_binary,
        "secret_values_printed": False,
    }
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_step(run_root: Path, step: dict[str, Any]) -> None:
    path = (
        run_root
        / str(step["arm"])
        / f"step_{step['decision_date']}_{ticker_slug(str(step['ticker']))}_{step['input_layer']}.json"
    )
    path.write_text(json.dumps(step, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


_LEDGER_LOCK = threading.Lock()


def append_ledger(run_root: Path, step: dict[str, Any]) -> None:
    event = {
        "created_at": datetime.now(UTC).isoformat(),
        "actor": "baseline_v3_four_arm",
        "event_type": step["status"],
        "ticker": step["ticker"],
        "arm": step["arm"],
        "input_layer": step["input_layer"],
        "scoring_segment": step["scoring_segment"],
        "decision_date": step["decision_date"],
        "provider": step["provider"],
        "provider_model": step["provider_model"],
        "cache_hit": step.get("cache_hit"),
    }
    if step.get("error_message"):
        event["error_message"] = step["error_message"]
    with _LEDGER_LOCK:
        with (run_root / "ledger.jsonl").open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(
        (RUN_ID_PREFIX, RUN_ID_PREFIX_V3_1, RUN_ID_PREFIX_V3_2, RUN_ID_PREFIX_V3_4)
    ):
        raise ValueError(
            f"run_id must start with {RUN_ID_PREFIX!r}, {RUN_ID_PREFIX_V3_1!r}, "
            f"{RUN_ID_PREFIX_V3_2!r}, or {RUN_ID_PREFIX_V3_4!r}"
        )
    if "/" in run_id or ".." in run_id:
        raise ValueError("run_id must be a single path segment")


def redact_error(message: str) -> str:
    return v2.redact_error(message)


def default_provider_base_url(provider: str) -> str:
    if provider == CODEX_CLI_BACKEND:
        return "local://codex-cli"
    return v2.default_provider_base_url(provider)


def is_http_429(message: Any) -> bool:
    return v2.is_http_429(message)


def git_identity() -> dict[str, str]:
    return v2.git_identity()


def step_sort_key(step: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(step.get("decision_date")),
        str(step.get("ticker")),
        str(step.get("input_layer")),
        str(step.get("arm")),
    )


def parse_tickers(value: str) -> tuple[str, ...]:
    return v2.parse_tickers(value)


def parse_dates_arg(value: str) -> tuple[date, ...]:
    return v2.parse_dates_arg(value)


def build_date_grid(args: argparse.Namespace) -> tuple[date, ...]:
    if int(args.step_months) <= 0:
        raise ValueError("--step-months must be a positive integer")
    if args.dates:
        return parse_dates_arg(args.dates)
    if not args.start and not args.end:
        return DEFAULT_DATES
    start = parse_date(args.start)
    end = parse_date(args.end)
    if end < start:
        raise ValueError("--end must be on or after --start")
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current = add_months(current, args.step_months)
    return tuple(dates)


def parse_input_layer_arg(value: str) -> tuple[InputLayer, ...]:
    normalized = value.strip().lower()
    if normalized == "both":
        return INPUT_LAYERS
    if normalized == "price_only":
        return ("price_only_packet",)
    if normalized == "richer":
        return ("richer_research_packet",)
    raise argparse.ArgumentTypeError("--input-layer must be one of both, price_only, richer")


def default_run_id(mode: Mode) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    normalized = mode.replace("provider-", "")
    return f"{RUN_ID_PREFIX}{normalized}_{stamp}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["mock", "provider-canary", "provider-pilot", "recompute"],
        required=True,
    )
    parser.add_argument(
        "--from-run",
        type=Path,
        default=None,
        help="Existing run directory for offline --mode recompute; never calls a provider.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Required marker for --mode recompute to make the no-provider boundary explicit.",
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--provider",
        choices=["glm_sophnet", "kimi", CODEX_CLI_BACKEND],
        default=DEFAULT_PROVIDER,
    )
    parser.add_argument("--provider-model", default=DEFAULT_GLM_MODEL)
    parser.add_argument("--provider-base-url", default="")
    parser.add_argument("--provider-max-tokens", type=int, default=1200)
    parser.add_argument("--tickers", type=parse_tickers, default=DEFAULT_TICKERS)
    parser.add_argument("--dates", default="")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--step-months", type=int, default=6)
    parser.add_argument("--input-layer", type=parse_input_layer_arg, default=INPUT_LAYERS)
    parser.add_argument("--warm-up-dates", type=int, default=3)
    parser.add_argument("--repeat-run-index", type=int, default=0)
    parser.add_argument("--provider-concurrency", type=int, default=1)
    parser.add_argument("--max-provider-concurrency", type=int, default=4)
    parser.add_argument("--adaptive-concurrency", type=parse_bool, default=True)
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=None,
        help="Deprecated compatibility: sets all arm base timeouts if v3 timeout flags are omitted.",
    )
    parser.add_argument("--direct-llm-timeout-seconds", type=float, default=None)
    parser.add_argument("--ksana-formatting-timeout-seconds", type=float, default=None)
    parser.add_argument("--ksana-real-research-timeout-seconds", type=float, default=None)
    parser.add_argument("--full-gotra-timeout-seconds", type=float, default=None)
    parser.add_argument("--timeout-per-kb-seconds", type=float, default=None)
    parser.add_argument("--max-request-timeout-seconds", type=float, default=None)
    parser.add_argument("--timeout-retries", type=int, default=None)
    parser.add_argument("--timeout-retry-backoff-seconds", type=float, default=None)
    parser.add_argument("--token-budget", type=int, default=None)
    parser.add_argument("--runs-root", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument(
        "--research-artifacts-path",
        type=Path,
        default=None,
        help="Local JSON/JSONL/CSV research artifact fixture; no network retrieval is performed.",
    )
    parser.add_argument(
        "--feedback-artifacts-path",
        type=Path,
        default=None,
        help="Local JSON/JSONL feedback artifact fixture; no network retrieval is performed.",
    )
    parser.add_argument("--env-file", default="")
    parser.add_argument("--codex-cli-reasoning-setting", default=DEFAULT_CODEX_CLI_REASONING)
    parser.add_argument("--codex-cli-binary", default="codex")
    parser.add_argument("--resume", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> RunConfig:
    if args.env_file:
        load_env_file(args.env_file)
    normalize_sophnet_api_key_env()
    mode: Mode = args.mode
    run_id = args.run_id or default_run_id(mode)
    provider_model = args.provider_model
    if args.provider == CODEX_CLI_BACKEND and provider_model == DEFAULT_GLM_MODEL:
        provider_model = (
            os.getenv("GOTRA_CODEX_CLI_MODEL")
            or os.getenv("JUDGE_LLM_MODEL")
            or os.getenv("LLM_MODEL")
            or DEFAULT_CODEX_CLI_MODEL
        )
    provider_concurrency = max(1, int(args.provider_concurrency))
    max_provider_concurrency = max(provider_concurrency, int(args.max_provider_concurrency))
    legacy_timeout = float(args.request_timeout_seconds) if args.request_timeout_seconds else None
    direct_timeout = args.direct_llm_timeout_seconds
    formatting_timeout = args.ksana_formatting_timeout_seconds
    real_research_timeout = args.ksana_real_research_timeout_seconds
    full_timeout = args.full_gotra_timeout_seconds
    deepseek_defaults = provider_model == DEEPSEEK_FLASH_MODEL
    default_direct_timeout = 90.0 if deepseek_defaults else 300.0
    default_formatting_timeout = 120.0 if deepseek_defaults else 420.0
    default_real_research_timeout = 150.0 if deepseek_defaults else 480.0
    default_full_timeout = 180.0 if deepseek_defaults else 540.0
    default_timeout_per_kb = 5.0 if deepseek_defaults else 20.0
    default_max_request_timeout = 240.0 if deepseek_defaults else 720.0
    default_timeout_retries = 0 if deepseek_defaults else 1
    default_timeout_retry_backoff = 0.0 if deepseek_defaults else 30.0
    if legacy_timeout is not None:
        direct_timeout = direct_timeout or legacy_timeout
        formatting_timeout = formatting_timeout or legacy_timeout
        real_research_timeout = real_research_timeout or legacy_timeout
        full_timeout = full_timeout or legacy_timeout
    timeout_retries = (
        default_timeout_retries if args.timeout_retries is None else int(args.timeout_retries)
    )
    timeout_retry_backoff_seconds = (
        default_timeout_retry_backoff
        if args.timeout_retry_backoff_seconds is None
        else float(args.timeout_retry_backoff_seconds)
    )
    return RunConfig(
        mode=mode,
        run_id=run_id,
        provider=args.provider,
        provider_model=provider_model,
        provider_base_url=args.provider_base_url or default_provider_base_url(args.provider),
        provider_max_tokens=max(1, int(args.provider_max_tokens)),
        tickers=args.tickers,
        dates=build_date_grid(args),
        input_layers=args.input_layer,
        warm_up_dates=max(0, int(args.warm_up_dates)),
        repeat_run_index=max(0, int(args.repeat_run_index)),
        runs_root=args.runs_root,
        price_dir=args.price_dir,
        token_budget=args.token_budget,
        provider_concurrency=provider_concurrency,
        max_provider_concurrency=max_provider_concurrency,
        adaptive_concurrency=args.adaptive_concurrency,
        direct_llm_timeout_seconds=max(1.0, float(direct_timeout or default_direct_timeout)),
        ksana_formatting_only_timeout_seconds=max(
            1.0,
            float(formatting_timeout or default_formatting_timeout),
        ),
        ksana_real_research_timeout_seconds=max(
            1.0,
            float(real_research_timeout or default_real_research_timeout),
        ),
        full_gotra_timeout_seconds=max(1.0, float(full_timeout or default_full_timeout)),
        timeout_per_kb_seconds=max(
            0.0,
            float(
                default_timeout_per_kb
                if args.timeout_per_kb_seconds is None
                else args.timeout_per_kb_seconds
            ),
        ),
        max_request_timeout_seconds=max(
            1.0,
            float(
                default_max_request_timeout
                if args.max_request_timeout_seconds is None
                else args.max_request_timeout_seconds
            ),
        ),
        timeout_retries=max(0, timeout_retries),
        timeout_retry_backoff_seconds=max(0.0, timeout_retry_backoff_seconds),
        scheduler_policy="per_date_feedback_snapshot_interleaved_point_layer_arm_v3",
        resume=bool(args.resume),
        research_artifacts_path=args.research_artifacts_path,
        feedback_artifacts_path=args.feedback_artifacts_path,
        codex_cli_reasoning_setting=str(args.codex_cli_reasoning_setting or DEFAULT_CODEX_CLI_REASONING),
        codex_cli_binary=str(args.codex_cli_binary or "codex"),
    )


def normalize_sophnet_api_key_env() -> None:
    v2.normalize_sophnet_api_key_env()


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.mode == "recompute":
        if args.from_run is None or not args.no_network:
            print("--mode recompute requires --from-run and --no-network", file=sys.stderr)
            return 2
        report = recompute_run_report(args.from_run)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    summary = run_four_arm(config_from_args(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return (
        0
        if summary["status"]
        in {"MOCK_PASS", "PROVIDER_CANARY_PASS", "PROVIDER_PILOT_PASS"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
