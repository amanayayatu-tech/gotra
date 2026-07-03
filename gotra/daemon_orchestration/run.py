"""Gotra daemon run entrypoint for Phase C orchestration."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from business_agents._common.stock_pool import StockPool
from orchestrator.core.pipeline import build_full_pipeline_steps, run_full_pipeline
from orchestrator.core.models import PipelineStep

from gotra.judge_agent.alaya_client import AlayaClient
from gotra.judge_agent.auto_quarantine import HttpAlayaAutoQuarantineClient, run_auto_quarantine
from gotra.perplexity_executor.executor import PerplexityExecutor
from integrations.alaya.sync_gates import sync_gates


BriefType = Literal["morning", "evening"]
DEFAULT_LOCK_PATH = Path("/tmp/gotra_run.lock")


@dataclass(frozen=True)
class DaemonRunConfig:
    """Configuration for one gotra daemon pass."""

    brief_type: BriefType
    data_dir: Path = Path("engine/ksana/data")
    dry_run: bool = False
    run_date: str = field(default_factory=lambda: datetime.now().date().isoformat())
    lock_path: Path = DEFAULT_LOCK_PATH
    project_id: str | None = None


@dataclass(frozen=True)
class DaemonStepResult:
    """One daemon step outcome."""

    name: str
    status: str
    detail: str = ""
    skipped: bool = False
    error: str = ""


@dataclass
class DaemonRunContext:
    """Mutable state shared by one daemon pass."""

    pipeline_failed: bool = False
    system_health: dict[str, Any] = field(default_factory=lambda: {"skipped": False})
    failed_steps: set[str] = field(default_factory=set)
    steps: list[DaemonStepResult] = field(default_factory=list)


@dataclass(frozen=True)
class DaemonRunResult:
    """Summary of one gotra daemon pass."""

    brief_type: BriefType
    run_date: str
    dry_run: bool
    pipeline_failed: bool
    system_health: dict[str, Any]
    stock_pool: dict[str, int]
    steps: tuple[DaemonStepResult, ...]
    report_paths: tuple[str, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True)


StepFunction = Callable[[DaemonRunConfig, DaemonRunContext], DaemonStepResult]

STEP_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "export_events": ("ksana_pipeline",),
    "push_to_alaya": ("ksana_pipeline", "export_events"),
}

STEP_RESULT_NAMES: dict[str, str] = {
    "run_ksana_pipeline": "ksana_pipeline",
    "materialize_gates": "sync_gates",
    "outcome_and_auto_quarantine": "auto_quarantine",
    "render_and_notify": "report_render",
}


class FileLock:
    """Simple non-blocking lockfile guard for daemon runs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.acquired = False

    def __enter__(self) -> FileLock:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            self.acquired = False
            return self
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            file_obj.write(f"{os.getpid()}\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


class GotraDaemonRunner:
    """Run Phase C orchestration with step-level failure isolation."""

    def __init__(self, steps: Sequence[StepFunction] | None = None) -> None:
        self.steps = tuple(steps or default_step_functions())

    def run_once(self, config: DaemonRunConfig) -> DaemonRunResult:
        with FileLock(config.lock_path) as lock:
            if not lock.acquired:
                return DaemonRunResult(
                    brief_type=config.brief_type,
                    run_date=config.run_date,
                    dry_run=config.dry_run,
                    pipeline_failed=False,
                    system_health={"skipped": True, "reason": "lockfile_exists"},
                    stock_pool={},
                    steps=(),
                )

            stock_counts = load_stock_pool_counts(config.data_dir)
            context = DaemonRunContext(system_health={"skipped": False})
            results: list[DaemonStepResult] = []
            for step in self.steps:
                result = dependent_step_skip_result(step, context)
                if result is None:
                    try:
                        result = step(config, context)
                    except Exception as exc:  # noqa: BLE001 - daemon must isolate failures.
                        result = DaemonStepResult(
                            name=step_result_name(step),
                            status="failed",
                            error=f"{type(exc).__name__}: {str(exc)[:500]}",
                        )
                if result.status == "failed":
                    context.pipeline_failed = True
                    context.failed_steps.add(result.name)
                context.steps.append(result)
                results.append(result)

            system_health = system_health_snapshot(context)
            report_paths = tuple(
                result.detail
                for result in results
                if result.name == "report_render" and result.detail and result.detail != "dry_run"
            )
            return DaemonRunResult(
                brief_type=config.brief_type,
                run_date=config.run_date,
                dry_run=config.dry_run,
                pipeline_failed=context.pipeline_failed,
                system_health=system_health,
                stock_pool=stock_counts,
                steps=tuple(results),
                report_paths=report_paths,
            )


def default_step_functions() -> tuple[StepFunction, ...]:
    return (
        perplexity_prefill,
        run_ksana_pipeline,
        export_events,
        push_to_alaya,
        judge_gate_poll,
        materialize_gates,
        outcome_and_auto_quarantine,
        export_outcome_events,
        render_and_notify,
    )


def load_stock_pool_counts(data_dir: str | Path) -> dict[str, int]:
    pool = StockPool.load(data_dir)
    return {
        "trading": len(pool.trading_tickers()),
        "watchlist": len(pool.watchlist_tickers()),
        "a_reference": len(pool.a_share_tickers()),
    }


def dependent_step_skip_result(
    step: StepFunction,
    context: DaemonRunContext,
) -> DaemonStepResult | None:
    step_name = getattr(step, "__name__", "unknown")
    blockers = [name for name in STEP_DEPENDENCIES.get(step_name, ()) if name in context.failed_steps]
    if not blockers:
        return None
    return DaemonStepResult(
        step_result_name(step),
        "skipped",
        detail=f"blocked_by={','.join(blockers)}",
        skipped=True,
    )


def step_result_name(step: StepFunction) -> str:
    step_name = getattr(step, "__name__", "unknown")
    return STEP_RESULT_NAMES.get(step_name, step_name)


def system_health_snapshot(context: DaemonRunContext) -> dict[str, Any]:
    system_health = dict(context.system_health)
    system_health["pipeline_failed"] = context.pipeline_failed
    system_health["failed_steps"] = sorted(context.failed_steps)
    return system_health


def build_llm_enabled_pipeline_steps(
    *,
    date: str,
    brief_type: BriefType,
    data_dir: str | Path,
) -> list[PipelineStep]:
    """Build ksana pipeline steps while removing gotra-disallowed no-LLM flags."""

    steps = build_full_pipeline_steps(date=date, brief_type=brief_type, data_dir=data_dir)
    for step in steps:
        if step.name in {"chairman", "red_team"}:
            step.command = [part for part in step.command if part != "--no-llm"]
    return steps


def perplexity_prefill(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    if config.dry_run:
        return DaemonStepResult("perplexity_prefill", "success", "dry_run")
    results = PerplexityExecutor(data_dir=config.data_dir).run()
    failed = [result for result in results if result.status == "failed"]
    return DaemonStepResult(
        "perplexity_prefill",
        "failed" if failed else "success",
        detail=f"filled={sum(1 for result in results if result.status == 'filled')}",
        error="; ".join(result.error or result.prompt_id for result in failed[:3]),
    )


def run_ksana_pipeline(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    if config.dry_run:
        return DaemonStepResult("ksana_pipeline", "success", "dry_run")
    result = run_full_pipeline(
        brief_type=config.brief_type,
        date=config.run_date,
        data_dir=config.data_dir,
        trigger_source="gotra_daemon",
        steps=build_llm_enabled_pipeline_steps(
            date=config.run_date,
            brief_type=config.brief_type,
            data_dir=config.data_dir,
        ),
    )
    return DaemonStepResult(
        "ksana_pipeline",
        "success" if result.status == "completed" else "failed",
        detail=result.run_id,
        error="" if result.status == "completed" else result.status,
    )


def export_events(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    return run_optional_module(
        "export_events",
        ["integrations.alaya.export_events", "--data-dir", str(config.data_dir)],
        dry_run=config.dry_run,
    )


def push_to_alaya(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    return run_optional_module(
        "push_to_alaya",
        ["integrations.alaya.push_to_alaya", "--data-dir", str(config.data_dir)],
        dry_run=config.dry_run,
    )


def judge_gate_poll(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    return run_required_module(
        "judge_gate_poll",
        ["gotra.judge_agent.gate_poller", "--once", "--data-dir", str(config.data_dir)],
        dry_run=config.dry_run,
    )


def materialize_gates(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    if config.dry_run:
        return DaemonStepResult("sync_gates", "success", "dry_run")
    result = sync_gates(AlayaClient.from_env(), data_dir=config.data_dir, project_id=config.project_id)
    return DaemonStepResult("sync_gates", "success", f"writes={len(result.writes)}")


def outcome_and_auto_quarantine(
    config: DaemonRunConfig,
    _context: DaemonRunContext,
) -> DaemonStepResult:
    if config.brief_type != "evening":
        return DaemonStepResult("auto_quarantine", "skipped", "morning", skipped=True)
    if config.dry_run:
        return DaemonStepResult("auto_quarantine", "success", "dry_run")
    client = HttpAlayaAutoQuarantineClient(
        base_url=os.getenv("GOTRA_INTERNAL_COGNITION_BASE_URL", "http://localhost:5000"),
        project_id=config.project_id,
        api_key=os.getenv("ALAYA_AUTOMATION_API_KEY") or os.getenv("ALAYA_API_KEY"),
    )
    result = run_auto_quarantine(client, data_dir=config.data_dir)
    return DaemonStepResult("auto_quarantine", "success", str(result.report_path))


def export_outcome_events(config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
    if config.brief_type != "evening":
        return DaemonStepResult("export_outcome_events", "skipped", "morning", skipped=True)
    return run_optional_module(
        "export_outcome_events",
        ["integrations.alaya.export_events", "--data-dir", str(config.data_dir), "--snapshots"],
        dry_run=config.dry_run,
    )


def render_and_notify(config: DaemonRunConfig, context: DaemonRunContext) -> DaemonStepResult:
    if config.dry_run:
        return DaemonStepResult("report_render", "success", "dry_run")
    from gotra.reporting_ext import publish_report

    result = publish_report(
        data_dir=config.data_dir,
        report_date=config.run_date,
        report_type=config.brief_type,
        sections={
            "System Health": system_health_snapshot(context),
            "Research Signals": [],
            "Judge Decisions": [],
            "Active Predictions": [],
            "Knowledge Additions": [],
        },
    )
    status = "success" if result.nonfatal else "failed"
    detail = ",".join(str(path) for path in (result.report.markdown_path, result.report.html_path))
    degraded = "; ".join(
        f"{item.channel}:{item.error}" for item in result.statuses if not item.sent and item.error
    )
    return DaemonStepResult("report_render", status, detail=detail, error=degraded)


def run_optional_module(name: str, args: list[str], *, dry_run: bool) -> DaemonStepResult:
    if dry_run:
        return DaemonStepResult(name, "success", "dry_run")
    try:
        return run_module(name, args)
    except ModuleNotFoundError as exc:
        return DaemonStepResult(name, "failed", error=f"missing module: {exc.name}")


def run_required_module(name: str, args: list[str], *, dry_run: bool) -> DaemonStepResult:
    if dry_run:
        return DaemonStepResult(name, "success", "dry_run")
    return run_module(name, args)


def run_module(name: str, args: list[str]) -> DaemonStepResult:
    command = [sys.executable, "-m", *args]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return DaemonStepResult(
        name,
        "success" if completed.returncode == 0 else "failed",
        detail=(completed.stdout or "").strip()[:500],
        error=(completed.stderr or "").strip()[:500],
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one gotra daemon window.")
    parser.add_argument("--once", action="store_true", help="run one window and exit")
    parser.add_argument("--type", choices=["morning", "evening"], default="morning")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--data-dir", default="engine/ksana/data")
    parser.add_argument("--lock-path", default=str(DEFAULT_LOCK_PATH))
    parser.add_argument("--project-id", default=os.getenv("GOTRA_INTERNAL_COGNITION_PROJECT_ID"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.once:
        raise SystemExit("--once is required in Phase C")
    config = DaemonRunConfig(
        brief_type=args.type,
        data_dir=Path(args.data_dir),
        dry_run=args.dry_run,
        run_date=args.date,
        lock_path=Path(args.lock_path),
        project_id=args.project_id,
    )
    result = GotraDaemonRunner().run_once(config)
    print(result.to_json())
    return 0 if not result.pipeline_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
