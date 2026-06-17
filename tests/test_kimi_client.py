from __future__ import annotations

import json

import httpx
import pytest

from gotra.backtest.kimi_client import KimiCompletionClient, strip_markdown_json_fence


def test_kimi_complete_sends_temperature_zero_and_strips_json_fence(monkeypatch) -> None:
    monkeypatch.setenv("SOPHNET_API_KEY", "test-secret")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n"
                                '{"direction":"long","expected_change_pct":1.2,'
                                '"confidence":0.6,"reasoning":"ok"}\n'
                                "```"
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 42},
            },
        )

    client = KimiCompletionClient(
        base_url="https://api.sophnet.com/v1/chat/completions",
        model="Kimi-K2.6",
        transport=httpx.MockTransport(handler),
    )

    result = client.complete(
        system_prompt="system",
        user_prompt="user",
        max_tokens=700,
        timeout_seconds=30,
        temperature=0.0,
    )

    body = captured["body"]
    headers = captured["headers"]
    assert captured["url"] == "https://api.sophnet.com/v1/chat/completions"
    assert headers["authorization"] == "Bearer test-secret"
    assert body["model"] == "Kimi-K2.6"
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 700
    assert body["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]
    assert result["content"].startswith('{"direction":"long"')
    assert result["usage"] == {"total_tokens": 42}
    assert result["response_metadata"]["markdown_json_fence_stripped"] is True


def test_kimi_complete_requires_env_key(monkeypatch) -> None:
    monkeypatch.delenv("SOPHNET_API_KEY", raising=False)
    client = KimiCompletionClient(transport=httpx.MockTransport(lambda _request: httpx.Response(200)))

    with pytest.raises(RuntimeError, match="SOPHNET_API_KEY"):
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=1,
            timeout_seconds=1,
            temperature=0.0,
        )


def test_kimi_error_redacts_secret(monkeypatch) -> None:
    monkeypatch.setenv("SOPHNET_API_KEY", "test-secret")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key test-secret")

    client = KimiCompletionClient(transport=httpx.MockTransport(handler))

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(
            system_prompt="system",
            user_prompt="user",
            max_tokens=1,
            timeout_seconds=1,
            temperature=0.0,
        )

    assert "test-secret" not in str(exc_info.value)
    assert "[redacted]" in str(exc_info.value)


def test_strip_markdown_json_fence_leaves_non_fence_text() -> None:
    assert strip_markdown_json_fence('{"ok":true}') == ('{"ok":true}', False)
    assert strip_markdown_json_fence('```text\n{"ok":true}\n```')[1] is False
