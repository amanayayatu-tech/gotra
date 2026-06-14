"""Materialize resolved Alaya investment gates back into ksana local files."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from gotra.judge_agent.alaya_client import AlayaClient


FILLED_STATUSES = {"approved", "approve", "resolved", "filled"}
SKIPPED_STATUSES = {"rejected", "reject", "skipped"}


class GateSyncClient(Protocol):
    """Alaya API subset needed by sync_gates."""

    def list_human_gates(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
        gate_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return human gates from Alaya."""


@dataclass(frozen=True)
class GateSyncWrite:
    """One local materialization written by sync_gates."""

    gate_id: str
    prompt_id: str
    status: str
    path: Path


@dataclass(frozen=True)
class GateSyncResult:
    """Summary for one sync pass."""

    writes: tuple[GateSyncWrite, ...]
    skipped_existing: int
    ignored: int


def sync_gates(
    client: GateSyncClient,
    *,
    data_dir: str | Path,
    project_id: str | None = None,
    state_path: str | Path | None = None,
) -> GateSyncResult:
    """Read resolved Alaya gates and write `_filled.yaml` / `_skipped.yaml` files."""

    root = Path(data_dir)
    state = GateSyncState(Path(state_path) if state_path else root / "state" / "id_map.sqlite")
    gates = client.list_human_gates(project_id=project_id, status=None, gate_type=None)
    writes: list[GateSyncWrite] = []
    skipped_existing = 0
    ignored = 0
    for gate in gates:
        record = gate_to_materialization(gate)
        if record is None:
            ignored += 1
            continue
        gate_id, prompt_id, payload, kind = record
        if state.is_synced(gate_id, prompt_id):
            skipped_existing += 1
            continue
        result_dir = root / "perplexity_results"
        result_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_filled.yaml" if kind == "filled" else "_skipped.yaml"
        path = result_dir / f"{prompt_id}{suffix}"
        write_yaml_atomic(path, payload)
        state.mark_synced(gate_id, prompt_id, path)
        writes.append(GateSyncWrite(gate_id=gate_id, prompt_id=prompt_id, status=kind, path=path))
    return GateSyncResult(writes=tuple(writes), skipped_existing=skipped_existing, ignored=ignored)


def gate_to_materialization(
    gate: dict[str, Any],
) -> tuple[str, str, dict[str, Any], str] | None:
    """Convert one resolved Alaya gate into a ksana local result payload."""

    status = str(gate.get("status") or gate.get("decision") or "").lower()
    decision = str(gate.get("decision") or "").lower()
    payload = decode_payload(gate.get("payload"))
    prompt_id = str(
        payload.get("pr_id")
        or payload.get("prompt_id")
        or payload.get("promptId")
        or gate.get("promptId")
        or ""
    )
    gate_id = str(gate.get("id") or "")
    if not gate_id or not prompt_id:
        return None
    if status in FILLED_STATUSES or decision == "approve":
        answer_text = str(
            payload.get("answer_text")
            or payload.get("answerText")
            or payload.get("result")
            or payload.get("rationale")
            or gate.get("decisionRationale")
            or gate.get("title")
            or ""
        ).strip()
        if not answer_text:
            return None
        return (
            gate_id,
            prompt_id,
            {
                "prompt_id": prompt_id,
                "related_signal_id": payload.get("related_signal_id") or payload.get("relatedSignalId") or "",
                "status": "filled",
                "source": "alaya_gate_sync",
                "filled_at": now_iso(),
                "prompt_text": payload.get("prompt_text") or payload.get("promptText") or "",
                "answer_text": answer_text,
                "alaya_gate_id": gate_id,
            },
            "filled",
        )
    if status in SKIPPED_STATUSES or decision == "reject":
        return (
            gate_id,
            prompt_id,
            {
                "prompt_id": prompt_id,
                "related_signal_id": payload.get("related_signal_id") or payload.get("relatedSignalId") or "",
                "status": "skipped",
                "source": "alaya_gate_sync",
                "skipped_at": now_iso(),
                "prompt_text": payload.get("prompt_text") or payload.get("promptText") or "",
                "reason": gate.get("rejectReasonCode") or payload.get("reason") or payload.get("skip_reason") or "",
                "alaya_gate_id": gate_id,
            },
            "skipped",
        )
    return None


class GateSyncState:
    """Small local idempotency map for gate materialization."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS synced_gates (
                    gate_id TEXT NOT NULL,
                    prompt_id TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    synced_at TEXT NOT NULL,
                    PRIMARY KEY (gate_id, prompt_id)
                )
                """
            )

    def is_synced(self, gate_id: str, prompt_id: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT 1 FROM synced_gates WHERE gate_id=? AND prompt_id=?",
                (gate_id, prompt_id),
            ).fetchone()
        return row is not None

    def mark_synced(self, gate_id: str, prompt_id: str, output_path: Path) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO synced_gates (gate_id, prompt_id, output_path, synced_at)
                VALUES (?, ?, ?, ?)
                """,
                (gate_id, prompt_id, str(output_path), now_iso()),
            )


def decode_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def write_yaml_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync resolved Alaya gates into ksana files.")
    parser.add_argument("--alaya-url", default="http://localhost:5000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--data-dir", default="engine/ksana/data")
    args = parser.parse_args(argv)

    result = sync_gates(
        AlayaClient(base_url=args.alaya_url, api_key=args.api_key),
        data_dir=args.data_dir,
        project_id=args.project_id,
    )
    print(json.dumps({"writes": len(result.writes), "skipped_existing": result.skipped_existing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
