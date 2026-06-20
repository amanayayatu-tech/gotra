#!/usr/bin/env python3
"""Baseline v2 Direct LLM / Ksana-only / Full Gotra pilot harness."""

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
import subprocess
import threading
import time
from typing import Any, Literal

import httpx
import pandas as pd

from gotra.backtest.kimi_client import KimiCompletionClient, load_env_file
from gotra.backtest.price_cache import read_price_cache
from gotra.backtest.protocol import add_months, parse_date, ticker_slug


Arm = Literal["direct_llm", "ksana_only", "full_gotra"]
Mode = Literal["mock", "provider-canary", "provider-pilot"]

ARMS: tuple[Arm, ...] = ("direct_llm", "ksana_only", "full_gotra")
DIRECTIONS = {"long", "avoid", "neutral", "watch", "short"}
DECISION_SCHEMA = "gotra.baseline_v2.three_arm_decision.v1"
DEFINITION_VERSION = "baseline-v2-three-arm-2026-06-18"
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
    "provider",
    "provider_model",
    "definition_version",
)
DEFAULT_PROVIDER = "glm_sophnet"
DEFAULT_GLM_MODEL = "GLM-5.2"
DEEPSEEK_FLASH_MODEL = "DeepSeek-V4-Flash"
DEFAULT_GLM_BASE_URL = "https://www.sophnet.com/api/open-apis/v1/chat/completions"
SOPHNET_ENDPOINTS = (
    ("api_v1", "https://api.sophnet.com/v1/chat/completions"),
    ("www_open_apis", DEFAULT_GLM_BASE_URL),
)
DEEPSEEK_RATE_LIMITS = {
    "provider_rpm_limit": 120,
    "provider_tpm_limit": 600000,
    "provider_rpm_target": 90,
    "provider_tpm_target": 450000,
    "provider_context_length": "1000k",
    "rate_limit_source": "user_provided_sophnet_screenshot_2026-06-19",
}
V1_PILOT_TICKERS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "TSM",
    "0700.HK",
    "1211.HK",
    "1810.HK",
    "3690.HK",
    "6060.HK",
    "9988.HK",
)
V1_PILOT_DATES = (
    date(2023, 1, 3),
    date(2023, 7, 3),
    date(2024, 1, 2),
    date(2024, 7, 1),
    date(2025, 1, 2),
    date(2025, 7, 1),
)
RUN_ID_PREFIX = "baseline_v2_three_arm_"
WINDOW_DAYS = 30
SYSTEM_PROMPT = """你是 Gotra Baseline v2 三臂 pilot 的严格 JSON 决策 provider。

只使用 user payload 中 availability_date <= decision_date 的上下文。不要使用 web search、
外部市场数据、文件、工具、actual future outcome 或 decision_date 之后的信息。
返回严格 JSON，schema 必须是 gotra.baseline_v2.three_arm_decision.v1。
Return exactly one JSON object. Do not wrap in markdown fences. Do not include
prose before or after JSON. The first non-whitespace character must be { and
the last non-whitespace character must be }. If uncertain, still return the
required JSON schema and use abstain_reason. Never copy the INPUT PACKET and
never output prompt wrapper keys such as arm_contract, output_contract,
raw_inputs, input_policy, ksana_research_workflow, provider, provider_model, or
definition_version.
"""


@dataclass(frozen=True)
class DecisionPoint:
    ticker: str
    decision_date: date


@dataclass(frozen=True)
class RunConfig:
    mode: Mode
    run_id: str
    provider: str
    provider_model: str
    provider_base_url: str
    tickers: tuple[str, ...]
    dates: tuple[date, ...]
    runs_root: Path
    price_dir: Path
    token_budget: int | None
    provider_concurrency: int
    max_provider_concurrency: int
    adaptive_concurrency: bool
    direct_llm_timeout_seconds: float
    ksana_only_timeout_seconds: float
    full_gotra_timeout_seconds: float
    timeout_per_kb_seconds: float
    max_request_timeout_seconds: float
    timeout_retries: int
    timeout_retry_backoff_seconds: float
    scheduler_policy: str
    provider_max_tokens: int = 1200
    resume: bool = False


@dataclass(frozen=True)
class ArmTask:
    point: DecisionPoint
    arm: Arm
    feedback: list[dict[str, Any]]


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
    provider_temperature_fallback: bool = False
    normalization_applied: bool = False
    normalization_steps: tuple[str, ...] = ()
    normalization_failure_reason: str = ""


class ProviderRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider_error_class: str,
        provider_attempts: int = 0,
        provider_retry_count: int = 0,
        raw_content: str = "",
        normalization_metadata: dict[str, Any] | None = None,
        input_echo_detected_keys: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_error_class = provider_error_class
        self.provider_attempts = provider_attempts
        self.provider_retry_count = provider_retry_count
        self.raw_content = raw_content
        self.normalization_metadata = normalization_metadata or {}
        self.input_echo_detected_keys = tuple(input_echo_detected_keys or ())


class InputEchoError(ValueError):
    def __init__(self, detected_keys: list[str] | tuple[str, ...]) -> None:
        self.detected_keys = tuple(sorted(str(item) for item in detected_keys))
        super().__init__(
            "provider response echoed input packet keys: " + ",".join(self.detected_keys)
        )


class LocalJsonCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.values = self._load()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self.values.get(key)
            return dict(value) if isinstance(value, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self.values[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.values, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))


class MockDecisionClient:
    provider_transport = "local_mock"

    def __init__(self, *, provider: str, provider_model: str, provider_base_url: str) -> None:
        self.provider = provider
        self.provider_model = provider_model
        self.provider_base_url = provider_base_url

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        features = payload["raw_inputs"]["price_features"]
        arm = normalize_arm(payload["arm"])
        expected = 0.35 * features["return_21d_pct"] + 0.25 * features["return_63d_pct"]
        if arm in {"ksana_only", "full_gotra"}:
            expected = 0.45 * features["return_21d_pct"] + 0.45 * features["return_63d_pct"]
        if arm == "full_gotra":
            feedback = payload.get("alaya_feedback_history") or []
            errors = [float(item["error"]) for item in feedback if item.get("error") is not None]
            if errors:
                expected += 0.20 * sum(errors[-3:]) / min(3, len(errors))
        expected = round(max(min(expected, 25.0), -25.0), 4)
        direction = "long" if expected >= 2.0 else "avoid" if expected <= -2.0 else "neutral"
        confidence = round(min(0.85, 0.45 + abs(expected) / 60), 4)
        return ProviderDecision(
            schema=DECISION_SCHEMA,
            arm=arm,
            ticker=str(payload["ticker"]),
            decision_date=str(payload["decision_date"]),
            horizon_days=int(payload["horizon_days"]),
            direction=direction,
            expected_change_pct=expected,
            confidence=confidence,
            reasoning=f"deterministic {arm} baseline-v2 mock decision",
            evidence_refs=["adjusted_close_history"],
            ksana_refs=["ksana_research_workflow"] if arm in {"ksana_only", "full_gotra"} else [],
            alaya_memory_refs=["matured_feedback"] if arm == "full_gotra" and feedback else [],
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
    ) -> None:
        self.provider_model = model
        self.provider_base_url = provider_base_url
        self.provider_max_tokens = provider_max_tokens
        self.request_timeout_seconds = request_timeout_seconds
        self.client = KimiCompletionClient(model=model, base_url=provider_base_url)

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        prompt = render_provider_prompt(payload)
        try:
            completion = self.client.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=self.provider_max_tokens,
                timeout_seconds=int(request_timeout_seconds or self.request_timeout_seconds),
                temperature=0.0,
            )
        except RuntimeError as exc:
            message = str(exc)
            provider_error_class = "HTTP_429" if "HTTP 429" in message else "provider_http_error"
            if "timed out" in message.lower():
                provider_error_class = "TimeoutException"
            elif "not valid JSON" in message or "did not contain message content" in message:
                provider_error_class = "InvalidResponse"
            raise ProviderRequestError(
                message,
                provider_error_class=provider_error_class,
                provider_attempts=1,
            ) from exc
        raw_content = str(completion.get("content", ""))
        try:
            decision = parse_provider_decision(raw_content)
        except InputEchoError as exc:
            _normalized, metadata = normalize_provider_decision_content(raw_content)
            raise ProviderRequestError(
                "Kimi SophNet response echoed the input packet instead of decision JSON",
                provider_error_class="InputEchoError",
                provider_attempts=1,
                raw_content=raw_content,
                normalization_metadata=metadata,
                input_echo_detected_keys=exc.detected_keys,
            ) from exc
        except json.JSONDecodeError as exc:
            _normalized, metadata = normalize_provider_decision_content(raw_content)
            raise ProviderRequestError(
                "Kimi SophNet response content was not valid decision JSON",
                provider_error_class="JSONDecodeError",
                provider_attempts=1,
                raw_content=raw_content,
                normalization_metadata=metadata,
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            _normalized, metadata = normalize_provider_decision_content(raw_content)
            raise ProviderRequestError(
                str(exc),
                provider_error_class="SchemaContractError",
                provider_attempts=1,
                raw_content=raw_content,
                normalization_metadata=metadata,
            ) from exc
        return replace(decision, provider_attempts=1)


class GlmSophnetDecisionClient:
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
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.provider_model = model
        self.base_url = base_url
        self.provider_base_url = base_url
        self.request_timeout_seconds = request_timeout_seconds
        self.timeout_retries = max(0, timeout_retries)
        self.timeout_retry_backoff_seconds = max(0.0, timeout_retry_backoff_seconds)
        self.transport = transport

    def complete(
        self,
        payload: dict[str, Any],
        *,
        request_timeout_seconds: float | None = None,
    ) -> ProviderDecision:
        api_key = sophnet_api_key()
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
        raw_content = extract_chat_content(body)
        try:
            decision = parse_provider_decision(raw_content)
        except InputEchoError as exc:
            _normalized, metadata = normalize_provider_decision_content(raw_content)
            raise ProviderRequestError(
                "GLM SophNet response echoed the input packet instead of decision JSON",
                provider_error_class="InputEchoError",
                provider_attempts=provider_attempts,
                provider_retry_count=provider_retry_count,
                raw_content=raw_content,
                normalization_metadata=metadata,
                input_echo_detected_keys=exc.detected_keys,
            ) from exc
        except json.JSONDecodeError as exc:
            raise ProviderRequestError(
                "GLM SophNet response content was not valid decision JSON",
                provider_error_class="JSONDecodeError",
                provider_attempts=provider_attempts,
                provider_retry_count=provider_retry_count,
                raw_content=raw_content,
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderRequestError(
                f"GLM SophNet response failed decision schema contract: {exc}",
                provider_error_class="SchemaContractError",
                provider_attempts=provider_attempts,
                provider_retry_count=provider_retry_count,
                raw_content=raw_content,
            ) from exc
        return replace(
            decision,
            provider_attempts=provider_attempts,
            provider_retry_count=provider_retry_count,
            provider_temperature_fallback=provider_temperature_fallback,
        )

    def _post_with_timeout_retry(
        self,
        *,
        prompt: str,
        api_key: str,
        request_timeout_seconds: float,
    ) -> tuple[dict[str, Any], int, int, bool]:
        total_attempts = 0
        timeout_retries_used = 0
        temperature_fallback_used = False
        for timeout_attempt in range(self.timeout_retries + 1):
            try:
                body, attempts, temperature_fallback = self._post_with_temperature_fallback(
                    prompt=prompt,
                    api_key=api_key,
                    request_timeout_seconds=request_timeout_seconds,
                )
                temperature_fallback_used = temperature_fallback_used or temperature_fallback
                return (
                    body,
                    total_attempts + attempts,
                    timeout_retries_used,
                    temperature_fallback_used,
                )
            except httpx.TimeoutException as exc:
                total_attempts += 1
                if timeout_attempt >= self.timeout_retries:
                    raise ProviderRequestError(
                        "GLM SophNet request timed out",
                        provider_error_class="TimeoutException",
                        provider_attempts=total_attempts,
                        provider_retry_count=timeout_retries_used,
                    ) from exc
                timeout_retries_used += 1
                if self.timeout_retry_backoff_seconds:
                    time.sleep(self.timeout_retry_backoff_seconds)
        raise ProviderRequestError(
            "GLM SophNet request timed out",
            provider_error_class="TimeoutException",
            provider_attempts=total_attempts,
            provider_retry_count=timeout_retries_used,
        )

    def _post_with_temperature_fallback(
        self,
        *,
        prompt: str,
        api_key: str,
        request_timeout_seconds: float,
    ) -> tuple[dict[str, Any], int, bool]:
        response = self._send(
            prompt=prompt,
            api_key=api_key,
            include_temperature=True,
            request_timeout_seconds=request_timeout_seconds,
        )
        attempts = 1
        temperature_fallback = False
        if response.status_code >= 400:
            detail = response_error_detail(response=response, secret=api_key)
            if "temperature" in detail.lower():
                response = self._send(
                    prompt=prompt,
                    api_key=api_key,
                    include_temperature=False,
                    request_timeout_seconds=request_timeout_seconds,
                )
                attempts += 1
                temperature_fallback = True
            else:
                raise ProviderRequestError(
                    f"GLM SophNet request failed with HTTP {response.status_code}{detail}",
                    provider_error_class=f"HTTP_{response.status_code}",
                    provider_attempts=attempts,
                    provider_retry_count=0,
                )
        if response.status_code >= 400:
            detail = response_error_detail(response=response, secret=api_key)
            raise ProviderRequestError(
                f"GLM SophNet request failed with HTTP {response.status_code}{detail}",
                provider_error_class=f"HTTP_{response.status_code}",
                provider_attempts=attempts,
                provider_retry_count=0,
            )
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderRequestError(
                "GLM SophNet response was not valid JSON",
                provider_error_class="JSONDecodeError",
                provider_attempts=attempts,
                provider_retry_count=0,
            ) from exc
        if not isinstance(body, dict):
            raise ProviderRequestError(
                "GLM SophNet response JSON was not an object",
                provider_error_class="InvalidResponse",
                provider_attempts=attempts,
                provider_retry_count=0,
            )
        return body, attempts, temperature_fallback

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


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid bool: {value}")


def normalize_arm(value: Any) -> Arm:
    normalized = str(value or "").strip()
    if normalized not in ARMS:
        raise ValueError(f"invalid arm: {value!r}")
    return normalized  # type: ignore[return-value]


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
    input_echo_keys = detect_input_echo_payload(payload)
    if input_echo_keys:
        raise InputEchoError(input_echo_keys)
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
    expected = float(payload["expected_change_pct"])
    confidence = float(payload["confidence"])
    if confidence > 1.0:
        confidence = confidence / 100.0
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
    if arm == "ksana_only" and alaya_memory_refs:
        raise ValueError("ksana_only must not include alaya_memory_refs")
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
    return {
        "normalization_applied": False,
        "normalization_steps": [],
        "normalization_failure_reason": "",
    }


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
    original = str(content)
    current = original.strip()
    steps: list[str] = []
    failure_reason = ""
    if current != original:
        steps.append("trim_outer_whitespace")

    fence_stripped = strip_markdown_fence_lines(current)
    if fence_stripped != current:
        current = fence_stripped.strip()
        steps.append("strip_markdown_fence_lines")

    extracted, extract_step, failure_reason = extract_balanced_json_object(current)
    if extracted is not None:
        if extracted != current:
            steps.append(extract_step)
        current = extracted

    metadata = {
        "normalization_applied": bool(steps),
        "normalization_steps": steps,
        "normalization_failure_reason": failure_reason,
    }
    return current, metadata


def strip_markdown_fence_lines(content: str) -> str:
    lines = content.splitlines()
    stripped_lines = [
        line for line in lines if line.strip().lower() not in {"```", "```json"}
    ]
    return "\n".join(stripped_lines)


def extract_balanced_json_object(content: str) -> tuple[str | None, str, str]:
    start = content.find("{")
    if start < 0:
        return None, "", "no_json_object_start"
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(content)):
        char = content[index]
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1], "extract_first_balanced_json_object", ""
    return content[start:], "", "no_complete_balanced_json_object"


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


def sophnet_api_key() -> str:
    return os.getenv("SOPHNET_API_KEY", "").strip() or os.getenv("API_KEY", "").strip()


def extract_chat_content(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("GLM SophNet response did not contain choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("GLM SophNet first choice was not an object")
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    text = first.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise RuntimeError("GLM SophNet response did not contain message content")


def classify_endpoint_discovery_result(
    *,
    label: str,
    url: str,
    http_status: str | int,
    body_text: str,
    curl_error: str = "",
) -> dict[str, Any]:
    status = str(http_status)
    body_bytes = len(body_text.encode("utf-8"))
    valid_json = False
    content = ""
    error_payload: Any = None
    try:
        body = json.loads(body_text) if body_text.strip() else {}
        valid_json = isinstance(body, dict)
        if valid_json:
            error_payload = body.get("error")
            try:
                content = extract_chat_content(body)
            except RuntimeError:
                content = ""
    except json.JSONDecodeError:
        body = {}
    content_extracted = bool(content.strip())
    if status == "200" and valid_json and content_extracted:
        result = "success"
    elif status in {"401", "403"}:
        result = "auth_denied"
    elif status == "429":
        result = "rate_limited"
    elif status == "404" or "model" in json.dumps(error_payload, ensure_ascii=False).lower():
        result = "model_unavailable"
    elif status == "000":
        result = "timeout_or_unreachable"
    elif status == "200" and valid_json:
        result = "incompatible_response"
    else:
        result = "invalid_json_or_http_error"
    return {
        "label": label,
        "url": url,
        "http_status": status,
        "body_bytes": body_bytes,
        "valid_json": valid_json,
        "content_extracted": content_extracted,
        "success": result == "success",
        "result": result,
        "error": error_payload,
        "curl_error": redact_error(curl_error),
    }


def select_endpoint_or_blocker(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_label = {str(item.get("label")): item for item in results}
    for label, _url in SOPHNET_ENDPOINTS:
        candidate = by_label.get(label)
        if candidate and candidate.get("success"):
            return {
                "selected_base_url": candidate["url"],
                "selected_label": label,
                "blocker": "",
            }
    result_types = {str(item.get("result")) for item in results}
    if result_types and result_types <= {"auth_denied"}:
        blocker = "BLOCKED_AUTH_MISSING_OR_DENIED"
    elif result_types and result_types <= {"model_unavailable"}:
        blocker = "BLOCKED_MODEL_UNAVAILABLE"
    elif "rate_limited" in result_types:
        blocker = "STOPPED_BY_CIRCUIT_BREAKER"
    elif result_types and result_types <= {"timeout_or_unreachable"}:
        blocker = "PROVIDER_ENDPOINTS_UNREACHABLE"
    else:
        blocker = "PROVIDER_ENDPOINTS_UNREACHABLE"
    return {"selected_base_url": "", "selected_label": "", "blocker": blocker}


def response_error_detail(*, response: httpx.Response, secret: str) -> str:
    text = response.text.strip()
    if not text:
        return ""
    redacted = text.replace(secret, "[redacted]")
    if len(redacted) > 500:
        redacted = redacted[:497] + "..."
    return f": {redacted}"


def cache_key_for(
    *,
    arm: Arm,
    provider: str,
    provider_model: str,
    provider_base_url: str,
    provider_max_tokens: int,
    prompt_hash: str,
    definition_version: str = DEFINITION_VERSION,
) -> str:
    return ":".join(
        [
            "baseline_v2",
            definition_version,
            provider,
            provider_model,
            provider_base_url,
            f"max_tokens={int(provider_max_tokens)}",
            arm,
            prompt_hash,
        ]
    )


def build_prompt_payload(
    *,
    arm: Arm,
    ticker: str,
    decision_date: date,
    price_rows: pd.DataFrame,
    feedback: list[dict[str, Any]],
    provider: str,
    provider_model: str,
) -> dict[str, Any]:
    latest = price_rows.iloc[-1]
    payload: dict[str, Any] = {
        "schema": "gotra.baseline_v2_three_arm.prompt.v1",
        "definition_version": DEFINITION_VERSION,
        "arm": arm,
        "ticker": ticker,
        "decision_date": decision_date.isoformat(),
        "horizon_days": WINDOW_DAYS,
        "provider": provider,
        "provider_model": provider_model,
        "input_policy": {
            "decision_inputs_available_on_or_before": decision_date.isoformat(),
            "fundamentals_enabled": False,
            "network_research_enabled": False,
            "actual_outcome_visible": False,
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
            "ksana_refs": "list; direct_llm must be empty",
            "alaya_memory_refs": "list; direct_llm and ksana_only must be empty",
            "risk_factors": "list",
            "abstain_reason": "string|null",
            "input_cutoff": decision_date.isoformat(),
            "future_data_allowed": False,
        },
    }
    if arm in {"ksana_only", "full_gotra"}:
        payload["ksana_research_workflow"] = {
            "F_partner": "Use only included price-derived evidence.",
            "W_partner": "Use only included market psychology and momentum evidence.",
            "G_partner": "Use only included governance/risk proxy evidence.",
            "Chairman": "Reconcile F/W/G into one decision.",
        }
    if arm == "full_gotra":
        payload["alaya_feedback_history"] = feedback
        payload["alaya_knowledge_state"] = {
            "history_feedback_allowed": True,
            "strong_knowledge_auto_approval_allowed": False,
            "human_gate_required_for_strong": True,
        }
    return payload


def render_provider_prompt(payload: dict[str, Any]) -> str:
    arm = normalize_arm(payload.get("arm"))
    arm_contract = payload.get("arm_contract") if isinstance(payload.get("arm_contract"), dict) else {}
    task = str(arm_contract.get("task") or "Make one time-bounded decision for this arm.")
    input_packet = {
        key: value
        for key, value in payload.items()
        if key not in {"schema", "definition_version", "provider", "provider_model", "arm_contract", "output_contract"}
    }
    forbidden_keys = ", ".join(INPUT_ECHO_FORBIDDEN_KEYS)
    allowed_keys = json.dumps(list(DECISION_JSON_ALLOWED_KEYS), ensure_ascii=False)
    arm_contract_text = json.dumps(arm_contract, ensure_ascii=False, sort_keys=True, indent=2)
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
            "- If uncertain, still return the required decision schema and use abstain_reason.",
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
            "- Do not use direction synonyms such as up, down, buy, sell, bullish, or bearish.",
            "- For positive/upside decisions use long; for downside/risk decisions use avoid or short.",
            "- expected_change_pct must be a JSON number, not a string.",
            "- confidence must be a JSON number in [0, 1], not a word, label, or percentage.",
            "- Use numeric confidence examples like 0.35, 0.50, or 0.72; never use \"medium\".",
            "- future_data_allowed must be false.",
            "- ksana_refs must be empty for direct_llm.",
            "- alaya_memory_refs must be empty for direct_llm and ksana_only.",
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


def arm_prompt_contract(arm: Arm) -> dict[str, Any]:
    if arm == "direct_llm":
        return {
            "task": (
                "你是一个单次股票判断模型。只基于截至 decision_date 的 time-bounded "
                "market packet，对 ticker 未来 horizon_days 的方向和幅度做判断。你不能使用 "
                "ksana 研究流程，不能使用 alaya 历史记忆，不能引用未来结果。请输出严格 JSON。"
            ),
            "allowed_context": [
                "ticker",
                "decision_date",
                "horizon_days",
                "price/history features where availability_date <= decision_date",
            ],
            "forbidden_context": [
                "ksana output",
                "alaya memory",
                "historical error feedback",
                "actual future outcome",
            ],
        }
    if arm == "ksana_only":
        return {
            "task": (
                "你是 gotra/ksana 研究流程的最终裁决器。你可以使用 ksana 基于同一 "
                "time-bounded packet 生成的研究/委员会/风险输出，但不能使用 alaya 的历史知识反馈、"
                "错题本、置信度状态或 strong knowledge 候选。请输出严格 JSON。"
            ),
            "allowed_context": [
                "same raw packet as direct_llm",
                "ksana research/committee/risk artifacts from <= decision_date inputs",
            ],
            "forbidden_context": [
                "alaya historical prediction ledger",
                "alaya resolved error feedback",
                "alaya confidence state",
                "future outcomes",
            ],
        }
    return {
        "task": (
            "你是完整 gotra 系统的最终裁决器。你可以使用 ksana 研究流程输出，也可以使用截至 "
            "decision_date 已经可用的 alaya 知识状态、历史错误归因、置信度更新和 quarantine "
            "过滤结果。strong knowledge 只能使用已由人类批准或当前规则允许的状态；不得使用未来 "
            "outcome。请输出严格 JSON，并列出使用了哪些 memory/knowledge refs。"
        ),
        "allowed_context": [
            "same raw packet",
            "same ksana artifacts",
            "alaya memory/knowledge/error feedback where availability_date <= decision_date",
            "quarantined/conflict/stale knowledge excluded",
        ],
        "forbidden_context": [
            "decision_date 后才 resolved 的 outcome",
            "未经允许的 strong 自动晋级",
            "future price / actual_change_pct as signal input",
        ],
    }


def price_features(price_rows: pd.DataFrame) -> dict[str, float]:
    closes = [float(value) for value in price_rows["adj_close"].tolist()]
    latest = closes[-1]

    def pct(days: int) -> float:
        if len(closes) <= days:
            return 0.0
        previous = closes[-days - 1]
        if previous == 0:
            return 0.0
        return round((latest / previous - 1) * 100, 6)

    peak = max(closes[-126:]) if closes else latest
    drawdown = round((latest / peak - 1) * 100, 6) if peak else 0.0
    return {
        "return_21d_pct": pct(21),
        "return_63d_pct": pct(63),
        "return_126d_pct": pct(126),
        "drawdown_126d_pct": drawdown,
    }


def compact_price_rows(price_rows: pd.DataFrame, *, max_rows: int = 32) -> list[dict[str, Any]]:
    compact = price_rows.tail(max_rows)[["date", "adj_close"]].copy()
    return [
        {
            "date": str(row["date"]),
            "adj_close": round(float(row["adj_close"]), 6),
        }
        for row in compact.to_dict("records")
    ]


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
    dates = pd.to_datetime(frame["date"]).dt.date
    return frame.loc[dates <= value].copy().reset_index(drop=True)


def row_on_or_after(frame: pd.DataFrame, value: date) -> pd.Series | None:
    dates = pd.to_datetime(frame["date"]).dt.date
    rows = frame.loc[dates >= value].copy()
    if rows.empty:
        return None
    rows = rows.sort_values("date")
    return rows.iloc[0]


def change_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return round((end / start - 1) * 100, 6)


def actual_direction(actual_change_pct: float) -> str:
    if actual_change_pct >= 2:
        return "long"
    if actual_change_pct <= -2:
        return "avoid"
    return "neutral"


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
    provider: str,
    provider_model: str,
    provider_base_url: str,
    provider_transport: str,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    actual = change_pct(float(context.start_row["adj_close"]), float(context.end_row["adj_close"]))
    error = round(actual - decision.expected_change_pct, 6)
    decision_hit = decision.direction == actual_direction(actual)
    return {
        "schema": "gotra.baseline_v2_three_arm.step.v1",
        "definition_version": DEFINITION_VERSION,
        "run_id": run_id,
        "status": "scored",
        "ticker": point.ticker,
        "arm": arm,
        "decision_date": point.decision_date.isoformat(),
        "window_days": WINDOW_DAYS,
        "window_end_date": context.outcome_date.isoformat(),
        "outcome_as_of": str(context.end_row["date"]),
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
        "ksana_workflow_enabled": arm in {"ksana_only", "full_gotra"},
        "alaya_feedback_enabled": arm == "full_gotra",
        "feedback_used_count": len(feedback) if arm == "full_gotra" else 0,
        "strong_knowledge_auto_approved": False,
        "prompt_hash": prompt_hash,
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "decision_inputs": decision_inputs(context.price_rows, feedback if arm == "full_gotra" else []),
        "outcome_inputs": outcome_inputs(context.end_row),
        "future_data_allowed": False,
        "audit_actor": "baseline_v2_three_arm_pilot",
        **diagnostics,
    }


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
    context: PriceContext | None = None,
    prompt_hash: str = "",
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = diagnostics or default_request_diagnostics(timeout_seconds=0)
    provider_error_types = {
        "provider_timeout",
        "provider_http_429",
        "provider_http_error",
        "json_decode_error",
        "schema_parse_error",
        "schema_contract_error",
        "input_echo_error",
        "future_data_violation",
        "auth_missing",
    }
    step: dict[str, Any] = {
        "schema": "gotra.baseline_v2_three_arm.step.v1",
        "definition_version": DEFINITION_VERSION,
        "run_id": run_id,
        "status": "provider_error" if error_type in provider_error_types else "skipped",
        "error_type": error_type,
        "error_message": redact_error(error_message),
        "ticker": point.ticker,
        "arm": arm,
        "decision_date": point.decision_date.isoformat(),
        "window_days": WINDOW_DAYS,
        "direction": None,
        "expected_change_pct": None,
        "confidence": None,
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
        "ksana_workflow_enabled": arm in {"ksana_only", "full_gotra"},
        "alaya_feedback_enabled": arm == "full_gotra",
        "feedback_used_count": 0,
        "strong_knowledge_auto_approved": False,
        "prompt_hash": prompt_hash,
        "cache_key": "",
        "cache_hit": False,
        "future_data_allowed": False,
        "audit_actor": "baseline_v2_three_arm_pilot",
        **diagnostics,
    }
    if context is not None:
        actual = change_pct(float(context.start_row["adj_close"]), float(context.end_row["adj_close"]))
        step.update(
            {
                "window_end_date": context.outcome_date.isoformat(),
                "outcome_as_of": str(context.end_row["date"]),
                "actual_change_pct": actual,
                "decision_inputs": decision_inputs(context.price_rows, []),
                "outcome_inputs": outcome_inputs(context.end_row),
            }
        )
    else:
        step.update({"decision_inputs": [], "outcome_inputs": []})
    return step


def classify_exception(exc: Exception) -> str:
    provider_error_class = str(getattr(exc, "provider_error_class", "") or "")
    if provider_error_class == "AuthMissing":
        return "auth_missing"
    if provider_error_class == "TimeoutException":
        return "provider_timeout"
    if provider_error_class == "HTTP_429":
        return "provider_http_429"
    if provider_error_class == "InputEchoError":
        return "input_echo_error"
    if detect_input_echo_raw_content(str(getattr(exc, "raw_content", "") or "")):
        return "input_echo_error"
    if provider_error_class.startswith("HTTP_"):
        return "provider_http_error"
    if provider_error_class in {"JSONDecodeError", "InvalidResponse"}:
        return "json_decode_error"
    if provider_error_class == "SchemaContractError":
        return "schema_contract_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    if isinstance(exc, ValueError):
        return "schema_contract_error"
    if isinstance(exc, RuntimeError) and "response" in str(exc).lower():
        return "schema_parse_error"
    return "provider_http_error"


def decision_inputs(price_rows: pd.DataFrame, feedback: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    for index, item in enumerate(feedback):
        inputs.append(
            {
                "name": f"alaya_matured_feedback_{index}",
                "kind": "alaya_feedback",
                "source": "prior_step_outcome",
                "availability_date": item["outcome_availability_date"],
            }
        )
    return inputs


def outcome_inputs(end_row: pd.Series) -> list[dict[str, Any]]:
    return [
        {
            "name": "outcome_adjusted_close",
            "kind": "price",
            "source": str(end_row["source_url"]),
            "availability_date": str(end_row["date"]),
        }
    ]


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


def arm_base_timeout_seconds(config: RunConfig, arm: Arm) -> float:
    if arm == "direct_llm":
        return config.direct_llm_timeout_seconds
    if arm == "ksana_only":
        return config.ksana_only_timeout_seconds
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
        "ksana_only_timeout_seconds": config.ksana_only_timeout_seconds,
        "full_gotra_timeout_seconds": config.full_gotra_timeout_seconds,
        "timeout_per_kb_seconds": config.timeout_per_kb_seconds,
        "max_request_timeout_seconds": config.max_request_timeout_seconds,
    }


def timeout_policy_name(config: RunConfig) -> str:
    if config.provider_model == DEEPSEEK_FLASH_MODEL:
        return "per_arm_complexity_normalized_deepseek_flash_v2"
    return "per_arm_complexity_normalized_v2"


def provider_limit_metadata(config: RunConfig) -> dict[str, Any]:
    if config.provider == "glm_sophnet" and config.provider_model == DEEPSEEK_FLASH_MODEL:
        return dict(DEEPSEEK_RATE_LIMITS)
    return {}


def default_request_diagnostics(
    *,
    timeout_seconds: float,
    timeout_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "prompt_chars": 0,
        "prompt_bytes": 0,
        "request_timeout_seconds": timeout_seconds,
        "request_timeout_policy": timeout_policy or {},
        "request_duration_seconds": 0.0,
        "provider_attempts": 0,
        "provider_retry_count": 0,
        "provider_error_class": "",
        "provider_temperature_fallback": False,
        "provider_max_tokens": 0,
        "normalization_applied": False,
        "normalization_steps": [],
        "normalization_failure_reason": "",
        "input_echo_detected_keys": [],
        "provider_raw_content_path": "",
        "provider_raw_content_chars": 0,
        "provider_raw_content_sha256": "",
        "provider_raw_content_excerpt": "",
    }


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
    return diagnostics


def diagnostics_from_exception(
    *,
    diagnostics: dict[str, Any],
    exc: Exception,
    started_at: float | None,
) -> dict[str, Any]:
    updated = dict(diagnostics)
    if started_at is not None:
        updated["request_duration_seconds"] = round(time.monotonic() - started_at, 6)
    updated["provider_attempts"] = int(getattr(exc, "provider_attempts", 0) or 0)
    updated["provider_retry_count"] = int(getattr(exc, "provider_retry_count", 0) or 0)
    updated["provider_error_class"] = str(
        getattr(exc, "provider_error_class", "") or type(exc).__name__
    )
    metadata = getattr(exc, "normalization_metadata", {}) or {}
    if metadata:
        updated["normalization_applied"] = bool(metadata.get("normalization_applied"))
        updated["normalization_steps"] = list(metadata.get("normalization_steps") or [])
        updated["normalization_failure_reason"] = str(
            metadata.get("normalization_failure_reason") or ""
        )
    input_echo_keys = list(getattr(exc, "input_echo_detected_keys", ()) or [])
    if not input_echo_keys:
        input_echo_keys = detect_input_echo_raw_content(str(getattr(exc, "raw_content", "") or ""))
    if input_echo_keys:
        updated["input_echo_detected_keys"] = sorted(input_echo_keys)
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
    raw_path = raw_dir / f"raw_{point.decision_date.isoformat()}_{ticker_slug(point.ticker)}.txt"
    raw_path.write_text(redacted, encoding="utf-8")
    return {
        "provider_raw_content_path": str(raw_path),
        "provider_raw_content_chars": len(redacted),
        "provider_raw_content_sha256": hashlib.sha256(redacted.encode("utf-8")).hexdigest(),
        "provider_raw_content_excerpt": redacted[:1200],
    }


def redact_sensitive_text(value: str) -> str:
    redacted = str(value)
    for key in ("SOPHNET_API_KEY", "API_KEY", "OPENAI_API_KEY", "PERPLEXITY_API_KEY"):
        secret = os.getenv(key)
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def complete_step(
    *,
    config: RunConfig,
    run_root: Path,
    cache: LocalJsonCache,
    client: MockDecisionClient | KimiDecisionClient | GlmSophnetDecisionClient,
    point: DecisionPoint,
    arm: Arm,
    feedback: list[dict[str, Any]],
) -> dict[str, Any]:
    context: PriceContext | None = None
    prompt_hash = ""
    diagnostics = default_request_diagnostics(
        timeout_seconds=arm_base_timeout_seconds(config, arm),
        timeout_policy=request_timeout_policy(config, arm=arm, prompt_bytes=0),
    )
    started_at: float | None = None
    try:
        context = price_context_for(point, price_dir=config.price_dir)
        payload = build_prompt_payload(
            arm=arm,
            ticker=point.ticker,
            decision_date=point.decision_date,
            price_rows=context.price_rows,
            feedback=feedback if arm == "full_gotra" else [],
            provider=client.provider,
            provider_model=client.provider_model,
        )
        prompt = render_provider_prompt(payload)
        diagnostics = prompt_request_diagnostics(prompt=prompt, config=config, arm=arm)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cache_key = cache_key_for(
            arm=arm,
            provider=client.provider,
            provider_model=client.provider_model,
            provider_base_url=client.provider_base_url,
            provider_max_tokens=config.provider_max_tokens,
            prompt_hash=prompt_hash,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            decision = parse_provider_decision(cached)
            cache_hit = True
        else:
            started_at = time.monotonic()
            decision = client.complete(
                payload,
                request_timeout_seconds=float(diagnostics["request_timeout_seconds"]),
            )
            diagnostics["request_duration_seconds"] = round(time.monotonic() - started_at, 6)
            diagnostics["provider_attempts"] = decision.provider_attempts
            diagnostics["provider_retry_count"] = decision.provider_retry_count
            diagnostics["provider_error_class"] = decision.provider_error_class
            diagnostics["provider_temperature_fallback"] = decision.provider_temperature_fallback
            diagnostics["normalization_applied"] = decision.normalization_applied
            diagnostics["normalization_steps"] = list(decision.normalization_steps)
            diagnostics["normalization_failure_reason"] = decision.normalization_failure_reason
            cache.set(
                cache_key,
                {
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
                },
            )
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
            provider=client.provider,
            provider_model=client.provider_model,
            provider_base_url=client.provider_base_url,
            provider_transport=client.provider_transport,
            diagnostics=diagnostics,
        )
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
            prompt_hash=prompt_hash,
            diagnostics=diagnostics,
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
            prompt_hash=prompt_hash,
            diagnostics=diagnostics,
        )
    violations = future_data_violations(step)
    if violations:
        step["status"] = "provider_error"
        step["error_type"] = "future_data_violation"
        step["future_data_violations"] = violations
    write_step(run_root, step)
    append_ledger(run_root, step)
    return step


def run_three_arm(config: RunConfig) -> dict[str, Any]:
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
    client: MockDecisionClient | KimiDecisionClient | GlmSophnetDecisionClient
    if config.mode == "mock":
        client = MockDecisionClient(
            provider=config.provider,
            provider_model=config.provider_model,
            provider_base_url=config.provider_base_url,
        )
    elif config.provider == "glm_sophnet":
        client = GlmSophnetDecisionClient(
            model=config.provider_model,
            base_url=config.provider_base_url,
            request_timeout_seconds=config.max_request_timeout_seconds,
            timeout_retries=config.timeout_retries,
            timeout_retry_backoff_seconds=config.timeout_retry_backoff_seconds,
        )
    else:
        client = KimiDecisionClient(
            model=config.provider_model,
            request_timeout_seconds=config.max_request_timeout_seconds,
            provider_base_url=config.provider_base_url,
            provider_max_tokens=config.provider_max_tokens,
        )

    points = [DecisionPoint(ticker, value) for value in config.dates for ticker in config.tickers]
    steps: list[dict[str, Any]] = []
    feedback_by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in config.tickers}
    provider_preflight_error = provider_preflight_blocker(config)
    concurrency_used = config.provider_concurrency
    downgrade_events: list[dict[str, Any]] = []
    stop_reason = ""
    circuit_breaker = CircuitBreakerState()

    if provider_preflight_error:
        for point in points:
            for arm in ARMS:
                context = try_price_context(point, price_dir=config.price_dir)
                step = build_error_step(
                    run_id=config.run_id,
                    point=point,
                    arm=arm,
                    provider=config.provider,
                    provider_model=config.provider_model,
                    provider_base_url=config.provider_base_url,
                    provider_transport="sophnet_chat_completions",
                    error_type="auth_missing",
                    error_message=provider_preflight_error,
                    context=context,
                    diagnostics=default_request_diagnostics(
                        timeout_seconds=arm_base_timeout_seconds(config, arm),
                        timeout_policy=request_timeout_policy(config, arm=arm, prompt_bytes=0),
                    ),
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
                feedback_by_ticker=feedback_by_ticker,
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
    client: MockDecisionClient | KimiDecisionClient | GlmSophnetDecisionClient,
    points: list[DecisionPoint],
    feedback_by_ticker: dict[str, list[dict[str, Any]]],
    concurrency: int,
    circuit_breaker: CircuitBreakerState,
    prior_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    worker_count = max(1, concurrency)
    if not points:
        return steps
    decision_date = points[0].decision_date
    feedback_snapshot_by_ticker = {
        point.ticker: matured_feedback(
            feedback_by_ticker.get(point.ticker, []),
            decision_date=decision_date,
        )
        for point in points
    }
    tasks = [
        ArmTask(
            point=point,
            arm=arm,
            feedback=feedback_snapshot_by_ticker.get(point.ticker, []) if arm == "full_gotra" else [],
        )
        for point in points
        for arm in ARMS
    ]
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
            feedback_by_ticker.setdefault(str(step["ticker"]), []).append(
                {
                    "decision_date": step["decision_date"],
                    "outcome_availability_date": step["outcome_as_of"],
                    "error": step["error"],
                    "mse": step["mse"],
                    "actual_change_pct": step["actual_change_pct"],
                    "expected_change_pct": step["expected_change_pct"],
                    "direction": step["direction"],
                    "direction_hit": step["direction_hit"],
                }
            )
    return sorted(steps, key=step_sort_key)


def matured_feedback(items: list[dict[str, Any]], *, decision_date: date) -> list[dict[str, Any]]:
    matured = [
        dict(item)
        for item in items
        if item.get("outcome_availability_date")
        and parse_date(str(item["outcome_availability_date"])) <= decision_date
    ]
    return sorted(matured, key=lambda item: str(item["decision_date"]))


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
    if config.provider not in {"glm_sophnet", "kimi"}:
        return f"unsupported provider: {config.provider}"
    if config.provider == "glm_sophnet" and not sophnet_api_key():
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
    seen_keys = {(step.get("ticker"), step.get("decision_date")) for step in steps}
    remaining = max(0, total_points - len(seen_keys))
    if (complete + remaining) / max(1, total_points) < 0.95:
        return "paired coverage no longer feasible"
    return ""


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
    auth_missing_count = count_error_type(steps, "auth_missing")
    provider_http_error_count = count_error_type(steps, "provider_http_error")
    price_missing_count = count_error_type(steps, "price_missing")
    paired = paired_complete_count(steps)
    expected_steps = total_points * len(ARMS)
    provider_error_rate = provider_errors / expected_steps if expected_steps else 0.0
    full_gotra_feedback_used = full_gotra_feedback_used_in_later_date(steps)
    if config.mode == "mock":
        status = (
            "MOCK_PASS"
            if provider_errors == 0 and future_violations == 0 and schema_errors == 0
            else "HARNESS_NEEDS_FIX"
        )
    elif config.mode == "provider-canary":
        if provider_preflight_error.startswith("PROVIDER_BLOCKED_PRE_HTTP"):
            status = "PROVIDER_BLOCKED_PRE_HTTP"
        else:
            canary_passed = (
                provider_errors == 0
                and future_violations == 0
                and schema_errors == 0
                and schema_pass == expected_steps
                and paired == total_points
                and full_gotra_feedback_used
            )
            status = "PROVIDER_CANARY_PASS" if canary_passed else "PROVIDER_CANARY_FAIL"
    else:
        if circuit_breaker.triggered:
            status = "STOPPED_BY_CIRCUIT_BREAKER"
        else:
            status = (
                "PROVIDER_PILOT_PASS"
                if provider_errors == 0
                and future_violations == 0
                and schema_errors == 0
                and paired / max(1, total_points) >= 0.95
                else "PROVIDER_PILOT_FAIL"
            )
    provider_limits = provider_limit_metadata(config)
    return {
        "schema": "gotra.baseline_v2_three_arm.summary.v1",
        "definition_version": DEFINITION_VERSION,
        "run_id": config.run_id,
        "mode": config.mode,
        "status": status,
        "provider": config.provider,
        "target_provider": config.provider,
        "target_provider_model": config.provider_model,
        "provider_model": config.provider_model,
        "provider_execution_mode": "local_mock" if config.mode == "mock" else "provider_http",
        "provider_base_url": config.provider_base_url,
        "provider_max_tokens": config.provider_max_tokens,
        "provider_call_status": provider_call_status(
            mode=config.mode,
            provider_preflight_error=provider_preflight_error,
        ),
        "provider_limits": provider_limits,
        **provider_limits,
        "token_budget_authorized": config.token_budget,
        "provider_preflight_error": provider_preflight_error,
        "stop_reason": stop_reason,
        "expected_points": total_points,
        "expected_steps": expected_steps,
        "actual_step_files": len(steps),
        "schema_pass_count": schema_pass,
        "schema_pass_rate": schema_pass / expected_steps if expected_steps else 0.0,
        "paired_complete_points": paired,
        "paired_coverage": paired / total_points if total_points else 0.0,
        "future_data_violations": future_violations,
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
        "provider_http_error_count": provider_http_error_count,
        "price_missing_count": price_missing_count,
        "normalization_counts": normalization_counts(steps),
        "raw_content_saved_count": sum(
            1 for step in steps if step.get("provider_raw_content_path")
        ),
        "full_gotra_feedback_used_in_later_date": full_gotra_feedback_used,
        "circuit_breaker_triggered": circuit_breaker.triggered,
        "trigger_reason": circuit_breaker.trigger_reason,
        "attempted_steps_at_trigger": circuit_breaker.attempted_steps_at_trigger,
        "inflight_at_trigger": circuit_breaker.inflight_at_trigger,
        "downgrade_events": downgrade_events,
        "request_diagnostics_by_arm": request_diagnostics_by_arm(steps),
        "metrics": metrics_by_arm(steps),
        "paired_diffs": paired_diffs(steps),
        "root_failure": root_failure(steps),
        "evidence_layer": evidence_layer_summary(),
    }


def provider_call_status(*, mode: Mode, provider_preflight_error: str) -> str:
    if mode == "mock" or provider_preflight_error.startswith("PROVIDER_BLOCKED_PRE_HTTP"):
        return "no real provider HTTP call"
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
                    str(step.get("ticker") or ""),
                    str(step.get("decision_date") or ""),
                ]
            )
    return ""


def evidence_layer_summary() -> dict[str, str]:
    return {
        "local_checks": "script outputs plus tests",
        "provider_runtime_health": "provider canary/pilot provider errors only",
        "pilot_evidence": "small three-arm paired run only",
        "long_run_formal_acceptance": "not entered",
        "science_public_claim": "not entered",
    }


def metrics_by_arm(steps: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        scored = [step for step in steps if step.get("arm") == arm and step.get("status") == "scored"]
        if not scored:
            output[arm] = {
                "scored_steps": 0,
                "direction_hit_rate": None,
                "mse": None,
                "mae": None,
                "policy_a_cumulative_return_pct": None,
            }
            continue
        direction_hits = [1 if step.get("direction_hit") else 0 for step in scored]
        output[arm] = {
            "scored_steps": len(scored),
            "direction_hit_rate": sum(direction_hits) / len(direction_hits),
            "mse": mean_float(step["mse"] for step in scored),
            "mae": mean_float(step["mae"] for step in scored),
            "policy_a_cumulative_return_pct": policy_a_cumulative_return(scored),
        }
    return output


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
            "normalization_applied_count": sum(
                1 for step in arm_steps if step.get("normalization_applied")
            ),
            "input_echo_error_count": count_error_type(arm_steps, "input_echo_error"),
            "raw_content_saved_count": sum(
                1 for step in arm_steps if step.get("provider_raw_content_path")
            ),
        }
    return output


def normalization_counts(steps: list[dict[str, Any]]) -> dict[str, Any]:
    step_counts: dict[str, int] = {}
    for step in steps:
        for item in step.get("normalization_steps") or []:
            step_counts[str(item)] = step_counts.get(str(item), 0) + 1
    return {
        "normalization_applied_count": sum(
            1 for step in steps if step.get("normalization_applied")
        ),
        "normalization_failure_count": sum(
            1 for step in steps if step.get("normalization_failure_reason")
        ),
        "normalization_steps": dict(sorted(step_counts.items())),
    }


def min_max_value(steps: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    values = [
        float(step[field])
        for step in steps
        if step.get(field) is not None and not math.isnan(float(step[field]))
    ]
    if not values:
        return {"min": None, "max": None}
    return {"min": min(values), "max": max(values)}


def distribution_value(steps: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    values = [
        float(step[field])
        for step in steps
        if step.get(field) is not None and not math.isnan(float(step[field]))
    ]
    if not values:
        return {"min": None, "p50": None, "p95": None, "max": None}
    return {
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return round(lower_value + (upper_value - lower_value) * (position - lower), 6)


def paired_diffs(steps: list[dict[str, Any]]) -> dict[str, Any]:
    by_key: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for step in steps:
        if step.get("status") != "scored":
            continue
        key = (str(step["ticker"]), str(step["decision_date"]))
        by_key.setdefault(key, {})[str(step["arm"])] = step
    pairs = {
        "direct_vs_ksana": ("direct_llm", "ksana_only"),
        "ksana_vs_full": ("ksana_only", "full_gotra"),
        "direct_vs_full": ("direct_llm", "full_gotra"),
    }
    output: dict[str, Any] = {}
    for name, (left, right) in pairs.items():
        left_minus_right_mse: list[float] = []
        right_minus_left_pnl: list[float] = []
        for arms in by_key.values():
            if left in arms and right in arms:
                left_minus_right_mse.append(float(arms[left]["mse"]) - float(arms[right]["mse"]))
                right_minus_left_pnl.append(
                    float(arms[right]["policy_a_return_pct"])
                    - float(arms[left]["policy_a_return_pct"])
                )
        output[name] = {
            "paired_points": len(left_minus_right_mse),
            "mse_delta_left_minus_right": mean_float(left_minus_right_mse),
            "policy_a_return_delta_right_minus_left_pct": mean_float(right_minus_left_pnl),
        }
    return output


def policy_a_cumulative_return(steps: list[dict[str, Any]]) -> float:
    by_date: dict[str, list[float]] = {}
    for step in steps:
        by_date.setdefault(str(step["decision_date"]), []).append(float(step["policy_a_return_pct"]))
    cumulative = 1.0
    for decision_date in sorted(by_date):
        returns = by_date[decision_date]
        cumulative *= 1.0 + (sum(returns) / len(returns)) / 100.0
    return round((cumulative - 1.0) * 100.0, 6)


def mean_float(values: Any) -> float | None:
    numbers = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 6)


def paired_complete_count(steps: list[dict[str, Any]]) -> int:
    by_key: dict[tuple[str, str], set[str]] = {}
    for step in steps:
        if step.get("status") != "scored":
            continue
        key = (str(step.get("ticker")), str(step.get("decision_date")))
        by_key.setdefault(key, set()).add(str(step.get("arm")))
    return sum(1 for arms in by_key.values() if set(ARMS).issubset(arms))


def full_gotra_feedback_used_in_later_date(steps: list[dict[str, Any]]) -> bool:
    scored_full_steps = [
        step
        for step in steps
        if step.get("status") == "scored" and step.get("arm") == "full_gotra"
    ]
    if not scored_full_steps:
        return False
    dates = sorted({str(step.get("decision_date")) for step in scored_full_steps})
    if len(dates) < 2:
        return False
    first_date = dates[0]
    return any(
        str(step.get("decision_date")) != first_date
        and int(step.get("feedback_used_count") or 0) > 0
        for step in scored_full_steps
    )


def run_root_has_artifacts(run_root: Path) -> bool:
    return run_root.exists() and any(run_root.iterdir())


def blocked_run_id_exists_summary(*, config: RunConfig, run_root: Path) -> dict[str, Any]:
    provider_limits = provider_limit_metadata(config)
    return {
        "schema": "gotra.baseline_v2_three_arm.summary.v1",
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
        "provider_call_status": "no new provider HTTP call",
        "provider_limits": provider_limits,
        **provider_limits,
        "run_root": str(run_root),
        "stop_reason": "run_root exists and contains artifacts; pass --resume only for exact manifest match",
        "existing_artifact_count": count_files(run_root),
        "scheduler_policy": config.scheduler_policy,
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
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


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
        "tickers": list(config.tickers),
        "dates": [item.isoformat() for item in config.dates],
        "scheduler_policy": config.scheduler_policy,
        "timeout_policy": timeout_policy_manifest(config),
        "provider_limits": provider_limit_metadata(config),
    }


def write_manifest(run_root: Path, config: RunConfig) -> None:
    provider_limits = provider_limit_metadata(config)
    manifest = {
        "schema": "gotra.baseline_v2_three_arm.manifest.v1",
        "definition_version": DEFINITION_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": config.run_id,
        "mode": config.mode,
        "target_provider": config.provider,
        "target_provider_model": config.provider_model,
        "provider_base_url": config.provider_base_url,
        "provider_max_tokens": config.provider_max_tokens,
        "provider_call_status": "no real provider HTTP call" if config.mode == "mock" else "pending",
        "provider_limits": provider_limits,
        **provider_limits,
        "arms": list(ARMS),
        "tickers": list(config.tickers),
        "dates": [item.isoformat() for item in config.dates],
        "git": git_identity(),
        "token_budget_authorized": config.token_budget,
        "adaptive_concurrency": config.adaptive_concurrency,
        "provider_concurrency": config.provider_concurrency,
        "max_provider_concurrency": config.max_provider_concurrency,
        "scheduler_policy": config.scheduler_policy,
        "timeout_policy": timeout_policy_manifest(config),
        "timeout_retries": config.timeout_retries,
        "timeout_retry_backoff_seconds": config.timeout_retry_backoff_seconds,
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
        / f"step_{step['decision_date']}_{ticker_slug(str(step['ticker']))}.json"
    )
    path.write_text(json.dumps(step, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


_LEDGER_LOCK = threading.Lock()


def append_ledger(run_root: Path, step: dict[str, Any]) -> None:
    event = {
        "created_at": datetime.now(UTC).isoformat(),
        "actor": "baseline_v2_three_arm_pilot",
        "event_type": step["status"],
        "ticker": step["ticker"],
        "arm": step["arm"],
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
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"run_id must start with {RUN_ID_PREFIX!r}")
    if "/" in run_id or ".." in run_id:
        raise ValueError("run_id must be a single path segment")


def redact_error(message: str) -> str:
    redacted = str(message)
    for key in ("SOPHNET_API_KEY", "API_KEY", "OPENAI_API_KEY", "PERPLEXITY_API_KEY"):
        value = os.getenv(key)
        if value:
            redacted = redacted.replace(value, "[redacted]")
    return redacted[:800]


def default_provider_base_url(provider: str) -> str:
    if provider == "glm_sophnet":
        return DEFAULT_GLM_BASE_URL
    if provider == "kimi":
        return "https://api.sophnet.com/v1/chat/completions"
    return ""


def is_http_429(message: Any) -> bool:
    return "HTTP 429" in str(message or "") or "429" in str(message or "Rate limit exceeded")


def git_identity() -> dict[str, str]:
    return {
        "branch": git_output(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head": git_output(["rev-parse", "--short", "HEAD"]),
        "remote": git_output(["remote", "get-url", "origin"]),
    }


def git_output(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return ""
    return result.stdout.strip()


def step_sort_key(step: dict[str, Any]) -> tuple[str, str, str]:
    return (str(step.get("decision_date")), str(step.get("ticker")), str(step.get("arm")))


def parse_tickers(value: str) -> tuple[str, ...]:
    tickers = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    if not tickers:
        raise argparse.ArgumentTypeError("--tickers must not be empty")
    return tickers


def parse_dates_arg(value: str) -> tuple[date, ...]:
    dates = tuple(parse_date(item.strip()) for item in value.split(",") if item.strip())
    if not dates:
        raise argparse.ArgumentTypeError("--dates must not be empty")
    return dates


def build_date_grid(args: argparse.Namespace) -> tuple[date, ...]:
    if args.dates:
        return parse_dates_arg(args.dates)
    if not args.start and not args.end:
        return V1_PILOT_DATES
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


def default_run_id(mode: Mode) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    normalized = mode.replace("provider-", "")
    return f"{RUN_ID_PREFIX}{normalized}_{stamp}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mock", "provider-canary", "provider-pilot"], required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--provider", choices=["glm_sophnet", "kimi"], default=DEFAULT_PROVIDER)
    parser.add_argument("--provider-model", default=DEFAULT_GLM_MODEL)
    parser.add_argument("--provider-base-url", default="")
    parser.add_argument("--provider-max-tokens", type=int, default=1200)
    parser.add_argument("--tickers", type=parse_tickers, default=V1_PILOT_TICKERS)
    parser.add_argument("--dates", default="")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--step-months", type=int, default=6)
    parser.add_argument("--provider-concurrency", type=int, default=1)
    parser.add_argument("--max-provider-concurrency", type=int, default=4)
    parser.add_argument("--adaptive-concurrency", type=parse_bool, default=True)
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=None,
        help="Deprecated v1 compatibility: sets all arm base timeouts if v2 timeout flags are omitted.",
    )
    parser.add_argument("--direct-llm-timeout-seconds", type=float, default=None)
    parser.add_argument("--ksana-only-timeout-seconds", type=float, default=None)
    parser.add_argument("--full-gotra-timeout-seconds", type=float, default=None)
    parser.add_argument("--timeout-per-kb-seconds", type=float, default=None)
    parser.add_argument("--max-request-timeout-seconds", type=float, default=None)
    parser.add_argument("--timeout-retries", type=int, default=None)
    parser.add_argument("--timeout-retry-backoff-seconds", type=float, default=None)
    parser.add_argument("--token-budget", type=int, default=None)
    parser.add_argument("--runs-root", type=Path, default=Path("data/backtest/runs"))
    parser.add_argument("--price-dir", type=Path, default=Path("data/backtest/prices"))
    parser.add_argument("--env-file", default="")
    parser.add_argument("--resume", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> RunConfig:
    if args.env_file:
        load_env_file(args.env_file)
    normalize_sophnet_api_key_env()
    mode: Mode = args.mode
    run_id = args.run_id or default_run_id(mode)
    provider_concurrency = max(1, int(args.provider_concurrency))
    max_provider_concurrency = max(provider_concurrency, int(args.max_provider_concurrency))
    legacy_timeout = float(args.request_timeout_seconds) if args.request_timeout_seconds else None
    direct_timeout = args.direct_llm_timeout_seconds
    ksana_timeout = args.ksana_only_timeout_seconds
    full_timeout = args.full_gotra_timeout_seconds
    deepseek_defaults = args.provider_model == DEEPSEEK_FLASH_MODEL
    default_direct_timeout = 90.0 if deepseek_defaults else 300.0
    default_ksana_timeout = 120.0 if deepseek_defaults else 420.0
    default_full_timeout = 180.0 if deepseek_defaults else 540.0
    default_timeout_per_kb = 5.0 if deepseek_defaults else 20.0
    default_max_request_timeout = 240.0 if deepseek_defaults else 720.0
    default_timeout_retries = 0 if deepseek_defaults else 1
    default_timeout_retry_backoff = 0.0 if deepseek_defaults else 30.0
    if legacy_timeout is not None:
        direct_timeout = direct_timeout or legacy_timeout
        ksana_timeout = ksana_timeout or legacy_timeout
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
        provider_model=args.provider_model,
        provider_base_url=args.provider_base_url or default_provider_base_url(args.provider),
        provider_max_tokens=max(1, int(args.provider_max_tokens)),
        tickers=args.tickers,
        dates=build_date_grid(args),
        runs_root=args.runs_root,
        price_dir=args.price_dir,
        token_budget=args.token_budget,
        provider_concurrency=provider_concurrency,
        max_provider_concurrency=max_provider_concurrency,
        adaptive_concurrency=args.adaptive_concurrency,
        direct_llm_timeout_seconds=max(1.0, float(direct_timeout or default_direct_timeout)),
        ksana_only_timeout_seconds=max(1.0, float(ksana_timeout or default_ksana_timeout)),
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
        scheduler_policy="per_date_feedback_snapshot_interleaved_point_arm_v2",
        resume=bool(args.resume),
    )


def normalize_sophnet_api_key_env() -> None:
    if os.getenv("SOPHNET_API_KEY", "").strip():
        return
    api_key = os.getenv("API_KEY", "").strip()
    if api_key:
        os.environ["SOPHNET_API_KEY"] = api_key


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run_three_arm(config_from_args(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return (
        0
        if summary["status"]
        in {"MOCK_PASS", "PROVIDER_CANARY_PASS", "PROVIDER_PILOT_PASS"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
