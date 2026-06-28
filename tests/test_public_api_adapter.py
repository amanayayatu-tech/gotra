from fastapi.testclient import TestClient

from gotra.public_api.app import BOUNDARY, HKEX_SYMBOLS, NASDAQ_SYMBOLS, NYSE_SYMBOLS, app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "gotra-public-api",
        "mode": "public_safe_read_only",
    }


def test_research_universe_counts_and_shape() -> None:
    response = client.get("/api/research-universe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["count"] == 138
    assert len(payload["items"]) == 138
    assert len(HKEX_SYMBOLS) == 38
    assert len(NASDAQ_SYMBOLS) + len(NYSE_SYMBOLS) == 100

    exchanges = {item["exchange"] for item in payload["items"]}
    assert exchanges == {"HKEX", "NASDAQ", "NYSE"}
    for item in payload["items"]:
        assert set(item) == {
            "symbol",
            "exchange",
            "source",
            "source_date",
            "purpose",
            "boundary",
        }
        assert item["source"] == "科技成长赛道选股报告_美股港股_20260628.md"
        assert item["source_date"] == "2026-06-28"
        assert item["purpose"] == "research_candidate_pool"
        assert item["boundary"] == BOUNDARY


def test_public_ledger_status_boundaries() -> None:
    response = client.get("/api/public-ledger/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "gotra-public-api"
    assert payload["backend_mode"] == "public_safe_read_only"
    assert "no_env" in payload["boundaries"]
    assert "no_llm" in payload["boundaries"]
    assert "no_admin" in payload["boundaries"]
    assert "no_write_operations" in payload["boundaries"]
    assert "no_subprocess" in payload["boundaries"]


def test_private_or_unsafe_routes_are_not_exposed() -> None:
    unsafe_get_routes = [
        "/env",
        "/api/env",
        "/api/llm/health",
        "/stock-pool",
        "/api/stock-pool",
        "/api/run-stream",
        "/api/agent-stream",
        "/api/research-scan-stream",
        "/api/codex/login-stream",
        "/api/deep-research/rerun-stream",
        "/api/cleanup",
    ]
    for route in unsafe_get_routes:
        assert client.get(route).status_code == 404

    unsafe_write_routes = [
        "/api/env",
        "/api/stock-pool",
        "/api/learning/refresh",
        "/api/deep-research/fill",
        "/api/deep-research/skip",
        "/api/cleanup",
    ]
    for route in unsafe_write_routes:
        assert client.post(route, json={}).status_code == 404
