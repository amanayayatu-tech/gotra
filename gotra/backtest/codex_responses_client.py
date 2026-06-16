"""Codex OAuth Responses API completion client for Phase BT."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

import httpx
from dotenv import dotenv_values


DEFAULT_CODEX_RESPONSES_BASE_URL = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_CODEX_RESPONSES_USER_AGENT = "codex_cli_rs/0.0.0"


class CodexResponsesCompletionClient:
    """CompletionClient implementation backed by the Codex Responses API route."""

    def __init__(
        self,
        *,
        auth_json_path: str | Path | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.auth_json_path = (
            Path(auth_json_path).expanduser()
            if auth_json_path is not None
            else Path(_config_value("CODEX_AUTH_JSON", "") or "~/.codex/auth.json").expanduser()
        )
        self.base_url = (
            base_url
            or _config_value("CODEX_RESPONSES_BASE_URL", "")
            or DEFAULT_CODEX_RESPONSES_BASE_URL
        )
        self.model = model or _config_value("JUDGE_LLM_MODEL", "") or _config_value("LLM_MODEL", "") or "gpt-5.5"
        self.reasoning_effort = (
            reasoning_effort
            or _config_value("CODEX_PROVIDER_REASONING_EFFORT", "")
            or _config_value("JUDGE_CODEX_REASONING_EFFORT", "")
            or "xhigh"
        )
        self.user_agent = user_agent or DEFAULT_CODEX_RESPONSES_USER_AGENT
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
        """Return model text plus provider usage without exposing credentials."""

        auth = _load_codex_auth(self.auth_json_path)
        # The Codex OAuth backend rejects the official Responses API
        # max_output_tokens field; keep max_tokens only for the shared caller
        # contract. Output length is controlled by the prompt and reasoning effort.
        del max_tokens
        # This route also rejects explicit temperature. Sampling follows the
        # backend default behavior; callers keep passing temperature via the
        # shared CompletionClient protocol, but it is not a wire parameter here.
        del temperature
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                }
            ],
            "store": False,
            "stream": True,
            "reasoning": {"effort": self.reasoning_effort},
        }
        headers = {
            "Authorization": f"Bearer {auth.access_token}",
            "chatgpt-account-id": auth.account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": "codex_cli_rs",
            "session_id": str(uuid4()),
            "User-Agent": self.user_agent,
        }
        deadline = time.monotonic() + timeout_seconds

        try:
            with httpx.Client(transport=self.transport, timeout=timeout_seconds) as client:
                with client.stream("POST", self.base_url, headers=headers, json=payload) as response:
                    if response.status_code in {401, 403}:
                        response.read()
                        raise RuntimeError(
                            f"Codex Responses API authentication failed with HTTP {response.status_code}; "
                            "run codex login to refresh the Codex OAuth session"
                        )
                    if response.status_code >= 400:
                        detail = _response_error_detail(response, auth=auth)
                        if response.status_code == 400:
                            raise RuntimeError(
                                "Codex Responses API request format failed with HTTP 400"
                                f"{detail}"
                            )
                        raise RuntimeError(
                            f"Codex Responses API request failed with HTTP {response.status_code}"
                            f"{detail}"
                        )
                    content, usage = _parse_sse_response(response.iter_lines(), deadline=deadline)
        except httpx.TimeoutException as exc:
            raise RuntimeError("Codex Responses API request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Codex Responses API request failed: {type(exc).__name__}") from exc
        except TimeoutError as exc:
            raise RuntimeError("Codex Responses API request timed out") from exc

        if not content:
            raise RuntimeError("Codex Responses API response did not contain output text")
        return {"content": content, "usage": usage}


class _CodexAuth:
    def __init__(self, *, access_token: str, account_id: str) -> None:
        self.access_token = access_token
        self.account_id = account_id


def _load_codex_auth(path: Path) -> _CodexAuth:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Codex auth file not found at {path}; run codex login") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Codex auth file at {path} is not valid JSON; run codex login") from exc

    access_token = _find_string_by_keys(raw, ("access_token", "accessToken"))
    account_id = _find_account_id(raw)
    if not access_token:
        raise RuntimeError(f"Codex auth file at {path} is missing an access token; run codex login")
    if not account_id:
        raise RuntimeError(f"Codex auth file at {path} is missing an account id; run codex login")
    return _CodexAuth(access_token=access_token, account_id=account_id)


def _find_string_by_keys(value: Any, keys: tuple[str, ...]) -> str:
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if isinstance(found, str) and found.strip():
                return found.strip()
        for item in value.values():
            found = _find_string_by_keys(item, keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_string_by_keys(item, keys)
            if found:
                return found
    return ""


def _find_account_id(value: Any) -> str:
    found = _find_string_by_keys(
        value,
        (
            "account_id",
            "accountId",
            "chatgpt_account_id",
            "chatgptAccountId",
            "active_account_id",
            "last_account_id",
        ),
    )
    if found:
        return found
    if isinstance(value, dict):
        accounts = value.get("accounts")
        if isinstance(accounts, dict):
            for key in accounts:
                if isinstance(key, str) and key.strip():
                    return key.strip()
    return ""


def _extract_response_text(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    direct = body.get("output_text") or body.get("content") or body.get("text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text") or part.get("content")
                        if isinstance(text, str):
                            chunks.append(text)
                    elif isinstance(part, str):
                        chunks.append(part)
            elif isinstance(content, str):
                chunks.append(content)
            item_text = item.get("text")
            if isinstance(item_text, str):
                chunks.append(item_text)
    if chunks:
        return "".join(chunks).strip()

    choices = body.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                text = message.get("content")
                if isinstance(text, str) and text.strip():
                    return text.strip()
            text = choice.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def _parse_sse_response(lines: Any, *, deadline: float | None = None) -> tuple[str, dict[str, Any] | None]:
    chunks: list[str] = []
    usage: dict[str, Any] | None = None
    completed_response: Any = None

    for raw_line in lines:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Codex Responses API SSE stream exceeded timeout")
        line = _decode_sse_line(raw_line)
        if not line or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            text = _event_delta_text(event)
            if text:
                chunks.append(text)
        elif event_type == "response.completed":
            completed_response = event.get("response")
            event_usage = _event_usage(event)
            if event_usage is not None:
                usage = event_usage

    content = "".join(chunks).strip()
    if not content and completed_response is not None:
        content = _extract_response_text(completed_response)
    return content, usage


def _decode_sse_line(raw_line: Any) -> str:
    if isinstance(raw_line, bytes):
        return raw_line.decode("utf-8", errors="replace").strip()
    if isinstance(raw_line, str):
        return raw_line.strip()
    return ""


def _event_delta_text(event: dict[str, Any]) -> str:
    for key in ("delta", "text"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    output_text = event.get("output_text")
    if isinstance(output_text, str):
        return output_text
    return ""


def _event_usage(event: dict[str, Any]) -> dict[str, Any] | None:
    response = event.get("response")
    if isinstance(response, dict):
        usage = response.get("usage")
        if isinstance(usage, dict):
            return usage
    usage = event.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def _response_error_detail(response: httpx.Response, *, auth: _CodexAuth) -> str:
    body = response.read()
    if not body:
        return ""
    text = body.decode(response.encoding or "utf-8", errors="replace").strip()
    if not text:
        return ""
    redacted = text.replace(auth.access_token, "[redacted]").replace(auth.account_id, "[redacted]")
    if len(redacted) > 500:
        redacted = redacted[:497] + "..."
    return f": {redacted}"


def _config_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    env_path = Path(".env")
    if not env_path.exists():
        return default
    parsed = dotenv_values(env_path)
    parsed_value = parsed.get(name)
    if parsed_value is None:
        return default
    return parsed_value
