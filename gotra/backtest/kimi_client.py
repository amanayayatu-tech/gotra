"""SophNet Kimi chat-completions client for diagnostic BT probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_SOPHNET_BASE_URL = "https://api.sophnet.com/v1/chat/completions"
DEFAULT_KIMI_MODEL = "Kimi-K2.6"


class KimiCompletionClient:
    """CompletionClient-compatible adapter for SophNet Kimi chat completions."""

    def __init__(
        self,
        *,
        api_key_env: str = "SOPHNET_API_KEY",
        base_url: str = DEFAULT_SOPHNET_BASE_URL,
        model: str = DEFAULT_KIMI_MODEL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.model = model
        self.transport = transport

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        timeout_seconds: int,
        temperature: float,
    ) -> dict[str, Any]:
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"{self.api_key_env} is required for KimiCompletionClient")

        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(transport=self.transport, timeout=timeout_seconds) as client:
                response = client.post(self.base_url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise RuntimeError("SophNet Kimi request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"SophNet Kimi request failed: {type(exc).__name__}") from exc

        if response.status_code >= 400:
            detail = _response_error_detail(response=response, secret=api_key)
            raise RuntimeError(f"SophNet Kimi request failed with HTTP {response.status_code}{detail}")

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError("SophNet Kimi response was not valid JSON") from exc

        content = _extract_chat_content(body)
        if not content:
            raise RuntimeError("SophNet Kimi response did not contain message content")
        stripped, fence_stripped = strip_markdown_json_fence(content)
        return {
            "content": stripped,
            "usage": body.get("usage") if isinstance(body, dict) else None,
            "response_metadata": {
                "model": self.model,
                "base_url": self.base_url,
                "markdown_json_fence_stripped": fence_stripped,
            },
        }


def strip_markdown_json_fence(text: str) -> tuple[str, bool]:
    """Strip a top-level ```json fenced block before downstream JSON parsing."""

    candidate = text.strip()
    if not candidate.startswith("```"):
        return candidate, False

    lines = candidate.splitlines()
    if len(lines) < 2:
        return candidate, False
    first = lines[0].strip().lower()
    if first not in {"```", "```json"}:
        return candidate, False
    if lines[-1].strip() != "```":
        return candidate, False
    return "\n".join(lines[1:-1]).strip(), True


def _extract_chat_content(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks = [
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") in {None, "text"}
            ]
            return "".join(chunks).strip()
    text = first_choice.get("text")
    return text.strip() if isinstance(text, str) else ""


def _response_error_detail(*, response: httpx.Response, secret: str) -> str:
    text = response.text.strip()
    if not text:
        return ""
    redacted = text.replace(secret, "[redacted]")
    if len(redacted) > 500:
        redacted = redacted[:497] + "..."
    return f": {redacted}"


def load_env_file(path: str | Path) -> None:
    """Load simple KEY=VALUE lines into os.environ without printing secrets."""

    env_path = Path(path)
    if not env_path.exists():
        raise RuntimeError(f"env file not found: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")
