import json
from pathlib import Path

from fastapi.testclient import TestClient

from gotra.public_api.app import (
    BOUNDARY,
    HKEX_SYMBOLS,
    LEDGER_ENTRY_SCHEMA,
    LEDGER_MANIFEST_SCHEMA,
    NASDAQ_SYMBOLS,
    NYSE_SYMBOLS,
    REVIEW_RESULT_SCHEMA,
    app,
    ledger_entry_hash_basis,
    stable_hash,
)


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


def _ledger_entry(*, symbol: str = "0700", previous_hash: str = "0" * 64) -> dict[str, object]:
    entry: dict[str, object] = {
        "schema": LEDGER_ENTRY_SCHEMA,
        "entry_id": f"gotra:ledger:HKEX:{symbol}:2026-06-29:30:v1",
        "base_entry_id": f"gotra:ledger:HKEX:{symbol}:2026-06-29:30",
        "version": 1,
        "previous_version_hash": "",
        "signal_id": f"run:HKEX:{symbol}:symbol:research_signal",
        "published_at": "2026-06-29T10:00:00+00:00",
        "as_of_date": "2026-06-29",
        "window_days": 30,
        "review_due_at": "2026-07-29",
        "status": "publish",
        "symbol": symbol,
        "exchange": "HKEX",
        "provider_ticker": f"{symbol}.HK",
        "research_status": "candidate",
        "methodology_version": "ksana_cognition_flywheel_v4",
        "execution_model": "deep_research_dossier_then_parallel_perspectives",
        "research_signal_hash": f"signal-hash-{symbol}",
        "publication_decision_hash": f"decision-hash-{symbol}",
        "evidence_packet_hash": f"evidence-hash-{symbol}",
        "evidence_packet_link": f"/reports/symbols/HKEX_{symbol}.json#audit-evidence-packet",
        "publication_decision": {
            "decision": "publish",
            "reader_safe_reasons": ["All publication gates passed with research-only boundary."],
            "publish_with_boundary": True,
            "gates": {},
        },
        "research_signal": {
            "hypothesis": "Research state remains bounded by verified public evidence.",
            "confidence": "medium",
            "evidence_ids": ["market_data_snapshot"],
            "counter_evidence": ["Counter evidence remains visible."],
            "uncertainty": ["Review window remains bounded."],
            "boundary": "research-only structured signal; not a trading instruction",
        },
        "boundary": "research ledger entry only; not investment advice, not a trading signal, not performance proof",
        "previous_hash": previous_hash,
    }
    entry["hash"] = stable_hash(ledger_entry_hash_basis(entry))
    return entry


def _write_ledger(
    tmp_path: Path,
    entries: list[dict[str, object]],
    *,
    review_results: list[dict[str, object]] | None = None,
    review_unavailable: list[dict[str, object]] | None = None,
    review_coverage: dict[str, object] | None = None,
) -> None:
    payload = {
        "schema": LEDGER_MANIFEST_SCHEMA,
        "generated_at": "2026-06-29T10:00:00+00:00",
        "entry_count": len(entries),
        "integrity": {"ok": True, "entry_count": len(entries), "latest_hash": entries[-1]["hash"] if entries else "0" * 64},
        "review_results": review_results or [],
        "review_unavailable": review_unavailable or [],
        "review_coverage": review_coverage
        or {
            "supported_windows_days": [1, 7, 30, 90],
            "total_count": len(entries),
            "due_count": 0,
            "reviewed_count": 0,
            "not_due_count": len(entries),
            "unavailable_count": 0,
            "missing_due_entry_ids": [],
            "by_window_days": [],
            "boundary": "review coverage is audit completeness, not performance proof",
        },
        "entries": entries,
    }
    (tmp_path / "research_ledger.json").write_text(json.dumps(payload), encoding="utf-8")


def test_track_record_filters_public_ledger(tmp_path: Path, monkeypatch) -> None:
    first = _ledger_entry(symbol="0700")
    second = _ledger_entry(symbol="1810", previous_hash=str(first["hash"]))
    _write_ledger(tmp_path, [first, second])
    monkeypatch.setenv("GOTRA_PUBLIC_REPORTS_DIR", str(tmp_path))

    response = client.get("/api/track-record", params={"symbol": "HKEX:0700", "status": "publish", "window_days": 30})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["items"][0]["symbol"] == "0700"
    assert payload["items"][0]["evidence_packet_link"].endswith("#audit-evidence-packet")
    assert payload["items"][0]["publication_decision"]["decision"] == "publish"


def test_track_record_returns_integrity_error(tmp_path: Path, monkeypatch) -> None:
    entry = _ledger_entry(symbol="0700")
    entry["previous_hash"] = "1" * 64
    _write_ledger(tmp_path, [entry])
    monkeypatch.setenv("GOTRA_PUBLIC_REPORTS_DIR", str(tmp_path))

    response = client.get("/api/track-record")

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "integrity_error"


def test_review_coverage_api_returns_review_counts(tmp_path: Path, monkeypatch) -> None:
    entry = _ledger_entry(symbol="0700")
    review_result = {
        "schema": REVIEW_RESULT_SCHEMA,
        "entry_id": entry["entry_id"],
        "window_days": 30,
        "reviewed_at": "2026-07-30T10:00:00+00:00",
        "raw_return": 4.0,
        "benchmark_return": 3.0,
        "attribution": {
            "classification": "above_benchmark",
            "relative_return_pp": 1.0,
            "quality_flags": ["fixture_public_price_observation"],
            "explanation": "Arithmetic review only; not performance proof.",
        },
    }
    _write_ledger(
        tmp_path,
        [entry],
        review_results=[review_result],
        review_coverage={
            "supported_windows_days": [1, 7, 30, 90],
            "total_count": 1,
            "due_count": 1,
            "reviewed_count": 1,
            "not_due_count": 0,
            "unavailable_count": 0,
            "missing_due_entry_ids": [],
            "by_window_days": [{"window_days": 30, "total_count": 1, "reviewed_count": 1, "unavailable_count": 0, "not_due_count": 0}],
            "boundary": "review coverage is audit completeness, not performance proof",
        },
    )
    monkeypatch.setenv("GOTRA_PUBLIC_REPORTS_DIR", str(tmp_path))

    response = client.get("/api/track-record/review-coverage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["review_coverage"]["reviewed_count"] == 1
    assert payload["review_coverage"]["unavailable_count"] == 0
    assert payload["boundary"] == BOUNDARY


def test_track_record_entry_includes_review_result(tmp_path: Path, monkeypatch) -> None:
    entry = _ledger_entry(symbol="0700")
    review_result = {
        "schema": REVIEW_RESULT_SCHEMA,
        "entry_id": entry["entry_id"],
        "window_days": 30,
        "reviewed_at": "2026-07-30T10:00:00+00:00",
        "raw_return": 4.0,
        "benchmark_return": 3.0,
        "attribution": {
            "classification": "above_benchmark",
            "relative_return_pp": 1.0,
            "quality_flags": ["fixture_public_price_observation"],
            "explanation": "Arithmetic review only; not performance proof.",
        },
    }
    _write_ledger(tmp_path, [entry], review_results=[review_result])
    monkeypatch.setenv("GOTRA_PUBLIC_REPORTS_DIR", str(tmp_path))

    response = client.get(f"/api/track-record/{entry['entry_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["review_status"] == "reviewed"
    assert payload["review_result"]["raw_return"] == 4.0
    assert payload["review_unavailable_reason"] is None
