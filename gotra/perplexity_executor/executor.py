"""Read ksana Perplexity PR records and write filled result files."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import yaml

from business_agents._common.knowledge_store import ingest_filled_result
from business_agents._common.output_validator import PerplexityPrompt
from business_agents._common.perplexity_results import (
    MAX_PERPLEXITY_ANSWER_CHARS,
    load_result_status,
    sync_signal_file_perplexity_status,
)
from gotra.perplexity_executor.pplx_client import PerplexityApiClient
from gotra.perplexity_executor.pplx_client import DEFAULT_MODEL as DEFAULT_PERPLEXITY_MODEL

DEFAULT_MODEL = DEFAULT_PERPLEXITY_MODEL
DEFAULT_CONCURRENCY_LIMIT = 2
CLOSED_RESULT_STATUSES = {"filled", "skipped", "skip_cold_start"}


class PerplexityClient(Protocol):
    """Client interface used by PerplexityExecutor."""

    def complete(self, prompt_text: str, *, model: str) -> str | Awaitable[str]:
        """Return answer text for prompt_text."""


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome for one PR prompt record."""

    prompt_id: str
    status: str
    prompt_path: Path
    result_path: Path | None = None
    error: str | None = None
    answer_text_original_chars: int = 0
    synced_research_signals: tuple[Path, ...] = ()
    knowledge_entry_id: str = ""
    postprocess_error: str | None = None


@dataclass(frozen=True)
class PromptRecord:
    """Validated prompt plus original values needed for ksana matching."""

    prompt: PerplexityPrompt
    prompt_payload: dict[str, Any]
    prompt_path: Path

    @property
    def prompt_id(self) -> str:
        return str(self.prompt.prompt_id)

    @property
    def prompt_text(self) -> str:
        return str(self.prompt_payload.get("prompt_text") or self.prompt.prompt_text or "")

    @property
    def related_signal_id(self) -> Any:
        return self.prompt_payload.get("related_signal_id", self.prompt.related_signal_id)


class PerplexityExecutor:
    """Execute gotra-owned Perplexity pull requests."""

    def __init__(
        self,
        *,
        data_dir: str | Path = "data",
        client: PerplexityClient | None = None,
        model: str = DEFAULT_MODEL,
        concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
        overwrite: bool = False,
    ) -> None:
        if concurrency_limit < 1:
            raise ValueError("concurrency_limit must be >= 1")
        self.data_dir = Path(data_dir)
        self.client = client or PerplexityApiClient()
        self.model = model
        self.concurrency_limit = min(concurrency_limit, DEFAULT_CONCURRENCY_LIMIT)
        self.overwrite = overwrite

    def run(self) -> list[ExecutionResult]:
        """Synchronously execute all PR prompt records."""

        return asyncio.run(self.arun())

    async def arun(self) -> list[ExecutionResult]:
        """Execute all PR prompt records with the configured concurrency limit."""

        records = self.load_prompt_records()
        semaphore = asyncio.Semaphore(self.concurrency_limit)

        async def guarded(record: PromptRecord) -> ExecutionResult:
            async with semaphore:
                return await self.execute_record(record)

        return list(await asyncio.gather(*(guarded(record) for record in records)))

    def load_prompt_records(self) -> list[PromptRecord]:
        """Load and validate data/pull_requests/PR-*.yaml records."""

        prompt_dir = self.data_dir / "pull_requests"
        records: list[PromptRecord] = []
        for path in sorted(prompt_dir.glob("PR-*.y*ml")):
            data = read_yaml(path)
            prompt_payload = data.get("prompt", data) if isinstance(data, dict) else {}
            if not isinstance(prompt_payload, dict):
                continue
            records.append(
                PromptRecord(
                    prompt=PerplexityPrompt.model_validate(prompt_payload),
                    prompt_payload=prompt_payload,
                    prompt_path=path,
                )
            )
        return records

    async def execute_record(self, record: PromptRecord) -> ExecutionResult:
        """Call Perplexity for one validated prompt and write its filled result."""

        result_path = self.result_path(record.prompt_id)
        existing = load_result_status(
            self.data_dir,
            {
                "prompt_id": record.prompt_id,
                "related_signal_id": ""
                if record.related_signal_id is None
                else str(record.related_signal_id),
                "prompt_text_for_match": record.prompt_text,
            },
        )
        existing_status = str(existing.get("status") or "pending")
        if existing_status in CLOSED_RESULT_STATUSES and not self.overwrite:
            return ExecutionResult(
                prompt_id=record.prompt_id,
                status="skipped_existing",
                prompt_path=record.prompt_path,
                result_path=Path(str(existing.get("result_path") or result_path)),
            )
        if not record.prompt_text.strip():
            return ExecutionResult(
                prompt_id=record.prompt_id,
                status="failed",
                prompt_path=record.prompt_path,
                error="prompt_text is empty",
            )

        try:
            response = self.client.complete(record.prompt_text, model=self.model)
            answer_text = await response if inspect.isawaitable(response) else response
        except Exception as exc:  # noqa: BLE001 - failures must degrade to manual fallback.
            return ExecutionResult(
                prompt_id=record.prompt_id,
                status="failed",
                prompt_path=record.prompt_path,
                error=str(exc),
            )

        if not str(answer_text).strip():
            return ExecutionResult(
                prompt_id=record.prompt_id,
                status="failed",
                prompt_path=record.prompt_path,
                error="client returned empty answer_text",
            )

        payload = self.build_filled_payload(record, str(answer_text).strip())
        write_yaml_atomic(result_path, payload)
        skipped_path = self.data_dir / "perplexity_results" / f"{record.prompt_id}_skipped.yaml"
        if skipped_path.exists():
            skipped_path.unlink()

        synced: list[Path] = []
        knowledge_entry_id = ""
        postprocess_error = None
        try:
            synced = sync_signal_file_perplexity_status(self.data_dir, record.prompt_id)
            entry = ingest_filled_result(self.data_dir, record.prompt_id, result_path=result_path)
            knowledge_entry_id = entry.entry_id if entry else ""
        except Exception as exc:  # noqa: BLE001 - result file remains ksana-readable.
            postprocess_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        return ExecutionResult(
            prompt_id=record.prompt_id,
            status="filled",
            prompt_path=record.prompt_path,
            result_path=result_path,
            answer_text_original_chars=len(str(answer_text).strip()),
            synced_research_signals=tuple(synced),
            knowledge_entry_id=knowledge_entry_id,
            postprocess_error=postprocess_error,
        )

    def result_path(self, prompt_id: str) -> Path:
        return self.data_dir / "perplexity_results" / f"{prompt_id}_filled.yaml"

    def build_filled_payload(self, record: PromptRecord, answer_text: str) -> dict[str, Any]:
        """Build the YAML shape expected by ksana load_result_status."""

        return {
            "prompt_id": record.prompt_id,
            "related_signal_id": record.related_signal_id,
            "status": "filled",
            "source": "perplexity",
            "filled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "prompt_text": record.prompt_text,
            "model": self.model,
            "answer_text": answer_text,
            "answer_text_original_chars": len(answer_text),
            "answer_text_prompt_limit": MAX_PERPLEXITY_ANSWER_CHARS,
        }


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def validate_prompt_file(path: str | Path) -> PerplexityPrompt:
    """Validate one PR file and return ksana's PerplexityPrompt model."""

    data = read_yaml(Path(path))
    prompt_payload = data.get("prompt", data) if isinstance(data, dict) else {}
    return PerplexityPrompt.model_validate(prompt_payload)
