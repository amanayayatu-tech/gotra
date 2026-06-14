from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gotra.judge_agent.auto_quarantine import (
    DEFAULT_ERROR_THRESHOLD,
    find_prediction_triggers,
    run_auto_quarantine,
)


class FakeAlayaClient:
    def __init__(
        self,
        *,
        predictions: list[dict[str, Any]],
        knowledge: list[dict[str, Any]],
    ) -> None:
        self.predictions = predictions
        self.knowledge = knowledge
        self.list_knowledge_source_refs: list[str] | None = None
        self.quarantine_calls: list[dict[str, Any]] = []

    def list_resolved_predictions(self) -> list[dict[str, Any]]:
        return self.predictions

    def list_knowledge(self, *, source_refs: list[str]) -> list[dict[str, Any]]:
        self.list_knowledge_source_refs = list(source_refs)
        return self.knowledge

    def quarantine_knowledge(
        self,
        knowledge_id: str,
        *,
        reason: str,
        actor: str,
    ) -> dict[str, Any]:
        call = {"knowledge_id": knowledge_id, "reason": reason, "actor": actor}
        self.quarantine_calls.append(call)
        return {"ok": True, **call}


def test_auto_quarantine_targets_only_source_ref_matches_and_writes_report(
    tmp_path: Path,
) -> None:
    client = FakeAlayaClient(
        predictions=[
            {
                "id": "P-LONG",
                "status": "resolved",
                "source_pr_id": "PR-LONG",
                "direction": "buy",
                "observed_return": -0.051,
            },
            {
                "predictionId": "P-SHORT",
                "status": "observed",
                "sourceRef": "PR-SHORT",
                "side": "sell",
                "observedReturn": 0.06,
            },
            {
                "id": "P-PENDING",
                "status": "pending",
                "source_pr_id": "PR-PENDING",
                "direction": "long",
                "observed_return": -0.20,
            },
            {
                "id": "P-OK",
                "status": "resolved",
                "source_pr_id": "PR-OK",
                "direction": "long",
                "observed_return": 0.04,
            },
        ],
        knowledge=[
            {"id": "K-LONG", "source_pr_id": "PR-LONG", "status": "active"},
            {"knowledgeId": "K-SHORT", "sourceRef": "PR-SHORT", "status": "strong"},
            {"id": "K-PENDING", "source_pr_id": "PR-PENDING", "status": "active"},
            {"id": "K-UNRELATED", "source_pr_id": "PR-UNRELATED", "status": "active"},
        ],
    )

    result = run_auto_quarantine(
        client,
        data_dir=tmp_path / "data",
        now=datetime(2026, 6, 14, 20, 30, tzinfo=UTC),
    )

    assert client.list_knowledge_source_refs == ["PR-LONG", "PR-SHORT"]
    assert [call["knowledge_id"] for call in client.quarantine_calls] == ["K-LONG", "K-SHORT"]
    assert all(call["actor"] == "judge_agent/codex" for call in client.quarantine_calls)
    assert "observed_return -5.10%" in client.quarantine_calls[0]["reason"]
    assert "observed_return 6.00%" in client.quarantine_calls[1]["reason"]

    assert result.report_path == tmp_path / "data" / "judge_reports" / (
        "auto_quarantine_20260614T203000Z.json"
    )
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["error_threshold"] == DEFAULT_ERROR_THRESHOLD
    assert report["resolved_prediction_count"] == 3
    assert report["matched_knowledge_count"] == 4
    assert report["quarantined_count"] == 2
    assert [item["knowledge_id"] for item in report["quarantined"]] == ["K-LONG", "K-SHORT"]
    assert report["quarantined"][0]["prediction_ids"] == ["P-LONG"]
    assert report["quarantined"][0]["source_ref"] == "PR-LONG"


def test_auto_quarantine_uses_error_threshold_from_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUARANTINE_ERROR_THRESHOLD", "0.20")
    client = FakeAlayaClient(
        predictions=[
            {
                "id": "P-BELOW-ENV",
                "status": "resolved",
                "source_pr_id": "PR-BELOW-ENV",
                "predictionError": 0.16,
            },
            {
                "id": "P-ABOVE-ENV",
                "status": "resolved",
                "source_pr_id": "PR-ABOVE-ENV",
                "worstClaimError": -0.21,
            },
        ],
        knowledge=[
            {"id": "K-BELOW-ENV", "source_pr_id": "PR-BELOW-ENV", "status": "active"},
            {"id": "K-ABOVE-ENV", "source_pr_id": "PR-ABOVE-ENV", "status": "active"},
        ],
    )

    result = run_auto_quarantine(
        client,
        data_dir=tmp_path / "data",
        now=datetime(2026, 6, 14, 21, 0, tzinfo=UTC),
    )

    assert result.error_threshold == 0.20
    assert client.list_knowledge_source_refs == ["PR-ABOVE-ENV"]
    assert [call["knowledge_id"] for call in client.quarantine_calls] == ["K-ABOVE-ENV"]
    assert "worstClaimError abs(-21.00%) > 20.00%" in client.quarantine_calls[0]["reason"]


def test_auto_quarantine_default_threshold_is_strictly_exceeded(tmp_path: Path) -> None:
    client = FakeAlayaClient(
        predictions=[
            {
                "id": "P-AT-THRESHOLD",
                "status": "resolved",
                "source_pr_id": "PR-AT-THRESHOLD",
                "price_error": 0.15,
            },
            {
                "id": "P-OVER-THRESHOLD",
                "status": "resolved",
                "source_pr_id": "PR-OVER-THRESHOLD",
                "price_error": "16%",
            },
        ],
        knowledge=[
            {"id": "K-AT-THRESHOLD", "source_pr_id": "PR-AT-THRESHOLD", "status": "active"},
            {"id": "K-OVER-THRESHOLD", "source_pr_id": "PR-OVER-THRESHOLD", "status": "active"},
        ],
    )

    run_auto_quarantine(
        client,
        data_dir=tmp_path / "data",
        now=datetime(2026, 6, 14, 22, 0, tzinfo=UTC),
    )

    assert client.list_knowledge_source_refs == ["PR-OVER-THRESHOLD"]
    assert [call["knowledge_id"] for call in client.quarantine_calls] == ["K-OVER-THRESHOLD"]
    assert "price_error abs(16.00%) > 15.00%" in client.quarantine_calls[0]["reason"]


def test_find_prediction_triggers_supports_nested_source_ref_and_avoid() -> None:
    triggers = find_prediction_triggers(
        [
            {
                "id": "P-AVOID",
                "status": "settled",
                "payload": {"sourceRef": {"source_pr_id": "PR-AVOID"}},
                "recommendation": "avoid",
                "outcome": {"priceReturn": 5.5},
            }
        ],
        error_threshold=0.15,
    )

    assert len(triggers) == 1
    assert triggers[0].prediction_id == "P-AVOID"
    assert triggers[0].source_ref == "PR-AVOID"
    assert triggers[0].reasons == ("short/sell/avoid observed_return 5.50% >= 5.00%",)
