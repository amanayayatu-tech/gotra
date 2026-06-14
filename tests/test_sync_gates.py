from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from integrations.alaya.sync_gates import sync_gates


class FakeGateClient:
    def __init__(self, gates: list[dict[str, Any]]) -> None:
        self.gates = gates
        self.calls: list[dict[str, Any]] = []

    def list_human_gates(self, **kwargs) -> list[dict[str, Any]]:
        self.calls.append(kwargs)
        return self.gates


def test_sync_gates_materializes_filled_and_skipped_results_idempotently(tmp_path: Path) -> None:
    client = FakeGateClient(
        [
            {
                "id": "gate-fill",
                "status": "approved",
                "payload": {
                    "pr_id": "PR-FILL",
                    "related_signal_id": "RS-FILL",
                    "prompt_text": "Research fill",
                    "answer_text": "Filled by Alaya human gate.",
                },
            },
            {
                "id": "gate-skip",
                "status": "rejected",
                "rejectReasonCode": "too_risky",
                "payload": {
                    "prompt_id": "PR-SKIP",
                    "related_signal_id": "RS-SKIP",
                    "prompt_text": "Research skip",
                },
            },
            {"id": "gate-pending", "status": "pending", "payload": {"pr_id": "PR-PENDING"}},
        ]
    )
    data_dir = tmp_path / "data"

    first = sync_gates(client, data_dir=data_dir, project_id="proj_1")
    second = sync_gates(client, data_dir=data_dir, project_id="proj_1")

    assert len(first.writes) == 2
    assert second.writes == ()
    assert second.skipped_existing == 2
    assert client.calls[0] == {"project_id": "proj_1", "status": None, "gate_type": None}

    filled = yaml.safe_load((data_dir / "perplexity_results" / "PR-FILL_filled.yaml").read_text())
    skipped = yaml.safe_load((data_dir / "perplexity_results" / "PR-SKIP_skipped.yaml").read_text())
    assert filled["status"] == "filled"
    assert filled["source"] == "alaya_gate_sync"
    assert filled["answer_text"] == "Filled by Alaya human gate."
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "too_risky"


def test_sync_gates_ignores_approved_gate_without_result_text(tmp_path: Path) -> None:
    client = FakeGateClient(
        [
            {
                "id": "gate-empty",
                "status": "approved",
                "payload": {"pr_id": "PR-EMPTY", "prompt_text": "Research empty"},
            }
        ]
    )

    result = sync_gates(client, data_dir=tmp_path / "data")

    assert result.writes == ()
    assert result.ignored == 1
