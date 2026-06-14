"""Perplexity API client used by the gotra executor."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar-deep-research"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_ATTEMPTS = 3


class PerplexityClientError(RuntimeError):
    """Raised when Perplexity cannot return a usable answer."""


@dataclass(frozen=True)
class PerplexityApiClient:
    """Small async client for Perplexity chat completions."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_base_seconds: float = 1.0

    async def complete(self, prompt_text: str, *, model: str = DEFAULT_MODEL) -> str:
        """Return the assistant answer text for one prompt."""

        api_key = self.api_key or os.getenv("PPLX_API_KEY") or os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise PerplexityClientError("missing PPLX_API_KEY or PERPLEXITY_API_KEY")
        if not prompt_text.strip():
            raise PerplexityClientError("prompt_text is empty")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are filling a ksana Deep Research pull request. "
                        "Answer in Chinese, include dated evidence, source URLs, "
                        "counter-evidence, confidence, and unresolved questions."
                    ),
                },
                {"role": "user", "content": prompt_text},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        attempts = max(1, min(self.max_attempts, DEFAULT_MAX_ATTEMPTS))
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = await client.post(self.base_url, headers=headers, json=payload)
                    if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
                        response.raise_for_status()
                    if response.status_code >= 400:
                        raise PerplexityClientError(
                            f"perplexity request failed with status {response.status_code}: "
                            f"{response.text[:500]}"
                        )
                    return extract_answer_text(response.json())
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt == attempts:
                        break
                    await asyncio.sleep(self.backoff_base_seconds * (2 ** (attempt - 1)))
                except (ValueError, KeyError, TypeError) as exc:
                    raise PerplexityClientError(f"invalid Perplexity response: {exc}") from exc

        raise PerplexityClientError(f"perplexity request failed after {attempts} attempts") from last_error


def extract_answer_text(payload: dict[str, Any]) -> str:
    """Extract the text content from a Perplexity chat completion response."""

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise KeyError("choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise TypeError("choices[0]")
    message = first.get("message")
    if not isinstance(message, dict):
        raise KeyError("message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise KeyError("message.content")
    return content.strip()
