from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from gotra.backtest.codex_responses_client import CodexResponsesCompletionClient


def test_codex_responses_complete_sends_expected_headers_and_body(tmp_path: Path) -> None:
    auth_path = _write_auth(tmp_path)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            content=_sse_content(
                {"type": "response.created", "response": {"id": "resp_fixture"}},
                {"type": "response.output_text.delta", "text": '{"direction":"'},
                {"type": "response.output_text.delta", "delta": 'long",'},
                {"type": "response.output_text.delta", "text": '"expected_change_pct":1.5}'},
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_fixture",
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 4,
                            "total_tokens": 14,
                        },
                    },
                },
                "[DONE]",
            ),
        )

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://chatgpt.com/backend-api/codex/responses",
        model="gpt-5.5",
        reasoning_effort="xhigh",
        transport=httpx.MockTransport(handler),
    )

    result = client.complete(
        system_prompt="system",
        user_prompt="user",
        max_tokens=123,
        timeout_seconds=30,
        temperature=0.0,
    )

    headers = captured["headers"]
    body = captured["body"]
    assert captured["url"] == "https://chatgpt.com/backend-api/codex/responses"
    assert headers["authorization"] == "Bearer test-access-token"
    assert headers["chatgpt-account-id"] == "test-account-id"
    assert headers["openai-beta"] == "responses=experimental"
    assert headers["originator"] == "codex_cli_rs"
    assert "codex_cli_rs" in headers["user-agent"]
    UUID(str(headers["session_id"]))
    assert body == {
        "model": "gpt-5.5",
        "instructions": "system",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "user"}],
            }
        ],
        "store": False,
        "stream": True,
        "reasoning": {"effort": "xhigh"},
    }
    assert "max_output_tokens" not in body
    assert "temperature" not in body
    assert result == {
        "content": '{"direction":"long","expected_change_pct":1.5}',
        "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
    }


def test_codex_responses_complete_can_fall_back_to_completed_response_text(tmp_path: Path) -> None:
    auth_path = _write_auth(tmp_path)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse_content(
                {
                    "type": "response.completed",
                    "response": {"output_text": '{"ok": true}', "usage": {"total": 3}},
                },
                "[DONE]",
            ),
        )

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    assert client.complete(
        system_prompt="system",
        user_prompt="user",
        max_tokens=8,
        timeout_seconds=30,
        temperature=0.0,
    ) == {"content": '{"ok": true}', "usage": {"total": 3}}


def test_codex_responses_complete_accepts_account_id_from_accounts_map(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "tokens": {"access_token": "test-access-token"},
                "accounts": {"mapped-account-id": {"label": "fixture"}},
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["account_id"] = request.headers["chatgpt-account-id"]
        return httpx.Response(
            200,
            content=_sse_content(
                {"type": "response.output_text.delta", "text": '{"ok": true}'},
                {"type": "response.completed", "response": {}},
                "[DONE]",
            ),
        )

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    client.complete(
        system_prompt="system",
        user_prompt="user",
        max_tokens=8,
        timeout_seconds=30,
        temperature=0.0,
    )

    assert captured["account_id"] == "mapped-account-id"


def test_codex_responses_complete_auth_failure_is_sanitized(tmp_path: Path) -> None:
    auth_path = _write_auth(tmp_path)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b'{"error":"expired secret test-access-token"}')

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=8,
            timeout_seconds=30,
            temperature=0.0,
        )

    message = str(exc_info.value)
    assert "HTTP 401" in message
    assert "codex login" in message
    assert "test-access-token" not in message


def test_codex_responses_complete_request_format_error_reports_body(tmp_path: Path) -> None:
    auth_path = _write_auth(tmp_path)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(400, content=b'{"detail":"Stream must be set to true"}')

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=8,
            timeout_seconds=30,
            temperature=0.0,
        )

    body = captured["body"]
    assert body["stream"] is True
    assert body["store"] is False
    assert "max_output_tokens" not in body
    assert "temperature" not in body
    assert "HTTP 400" in str(exc_info.value)
    assert "request format" in str(exc_info.value)
    assert "Stream must be set to true" in str(exc_info.value)


def test_codex_responses_complete_does_not_send_unsupported_max_output_tokens(
    tmp_path: Path,
) -> None:
    auth_path = _write_auth(tmp_path)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            400,
            content=b'{"detail":"Unsupported parameter: max_output_tokens"}',
        )

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=8,
            timeout_seconds=30,
            temperature=0.0,
        )

    body = captured["body"]
    assert "max_output_tokens" not in body
    assert "temperature" not in body
    assert body["stream"] is True
    assert body["store"] is False
    assert "Unsupported parameter: max_output_tokens" in str(exc_info.value)


def test_codex_responses_complete_does_not_send_unsupported_temperature(
    tmp_path: Path,
) -> None:
    auth_path = _write_auth(tmp_path)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            400,
            content=b'{"detail":"Unsupported parameter: temperature"}',
        )

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=8,
            timeout_seconds=30,
            temperature=0.0,
        )

    body = captured["body"]
    assert "temperature" not in body
    assert "max_output_tokens" not in body
    assert body["stream"] is True
    assert body["store"] is False
    assert "Unsupported parameter: temperature" in str(exc_info.value)


def test_codex_responses_complete_forbidden_failure_is_sanitized(tmp_path: Path) -> None:
    auth_path = _write_auth(tmp_path)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b'{"error":"forbidden test-access-token"}')

    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=8,
            timeout_seconds=30,
            temperature=0.0,
        )

    message = str(exc_info.value)
    assert "HTTP 403" in message
    assert "codex login" in message
    assert "test-access-token" not in message


def test_codex_responses_complete_rejects_missing_auth_fields(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"tokens": {}}), encoding="utf-8")
    client = CodexResponsesCompletionClient(
        auth_json_path=auth_path,
        base_url="https://example.test/responses",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200)),
    )

    with pytest.raises(RuntimeError, match="missing an access token"):
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=8,
            timeout_seconds=30,
            temperature=0.0,
        )


def _write_auth(tmp_path: Path) -> Path:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "tokens": {"access_token": "test-access-token"},
                "chatgpt_account_id": "test-account-id",
            }
        ),
        encoding="utf-8",
    )
    return auth_path


def _sse_content(*events: object) -> bytes:
    lines: list[str] = []
    for event in events:
        if event == "[DONE]":
            lines.append("data: [DONE]\n\n")
        else:
            lines.append(f"data: {json.dumps(event)}\n\n")
    return "".join(lines).encode("utf-8")
