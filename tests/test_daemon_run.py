from __future__ import annotations

from pathlib import Path

from gotra.daemon_orchestration.run import (
    DaemonRunContext,
    DaemonRunConfig,
    DaemonStepResult,
    GotraDaemonRunner,
    build_llm_enabled_pipeline_steps,
    load_stock_pool_counts,
    main,
    render_and_notify,
)


def test_stock_pool_counts_read_ksana_master_pool() -> None:
    counts = load_stock_pool_counts(Path("engine/ksana/data"))

    assert counts["trading"] == 12
    assert counts["watchlist"] == 1
    assert counts["a_reference"] == 1


def test_llm_enabled_pipeline_removes_no_llm_flags() -> None:
    steps = build_llm_enabled_pipeline_steps(
        date="2026-06-14",
        brief_type="morning",
        data_dir="engine/ksana/data",
    )

    commands = {step.name: step.command for step in steps}
    assert "--no-llm" not in commands["chairman"]
    assert "--no-llm" not in commands["red_team"]
    assert commands["perplexity_wait"][:2] == ["orchestrator", "wait-for-perplexity-fill"]


def test_daemon_runner_dry_run_isolated_steps_and_report_flags(tmp_path: Path) -> None:
    seen: list[str] = []

    def ok_step(config: DaemonRunConfig, context: DaemonRunContext) -> DaemonStepResult:
        seen.append(f"ok:{config.brief_type}:{config.dry_run}")
        assert context.pipeline_failed is False
        return DaemonStepResult("ok_step", "success", "dry_run")

    def bad_step(_config: DaemonRunConfig, _context: DaemonRunContext) -> DaemonStepResult:
        seen.append("bad")
        raise RuntimeError("boom")

    def after_step(_config: DaemonRunConfig, context: DaemonRunContext) -> DaemonStepResult:
        seen.append("after")
        assert context.pipeline_failed is True
        return DaemonStepResult("after_step", "success")

    result = GotraDaemonRunner((ok_step, bad_step, after_step)).run_once(
        DaemonRunConfig(
            brief_type="evening",
            data_dir=Path("engine/ksana/data"),
            dry_run=True,
            lock_path=tmp_path / "gotra.lock",
        )
    )

    assert seen == ["ok:evening:True", "bad", "after"]
    assert result.pipeline_failed is True
    assert [step.name for step in result.steps] == ["ok_step", "bad_step", "after_step"]
    assert result.steps[1].status == "failed"
    assert result.system_health["skipped"] is False


def test_daemon_runner_skips_alaya_push_after_pipeline_failure(tmp_path: Path) -> None:
    seen: list[str] = []

    def run_ksana_pipeline(
        _config: DaemonRunConfig,
        _context: DaemonRunContext,
    ) -> DaemonStepResult:
        seen.append("ksana")
        raise RuntimeError("pipeline failed")

    def export_events(
        _config: DaemonRunConfig,
        _context: DaemonRunContext,
    ) -> DaemonStepResult:
        seen.append("export")
        return DaemonStepResult("export_events", "success")

    def push_to_alaya(
        _config: DaemonRunConfig,
        _context: DaemonRunContext,
    ) -> DaemonStepResult:
        seen.append("push")
        return DaemonStepResult("push_to_alaya", "success")

    def judge_gate_poll(
        _config: DaemonRunConfig,
        _context: DaemonRunContext,
    ) -> DaemonStepResult:
        seen.append("judge")
        return DaemonStepResult("judge_gate_poll", "success")

    result = GotraDaemonRunner(
        (run_ksana_pipeline, export_events, push_to_alaya, judge_gate_poll)
    ).run_once(
        DaemonRunConfig(
            brief_type="morning",
            data_dir=Path("engine/ksana/data"),
            dry_run=True,
            lock_path=tmp_path / "gotra.lock",
        )
    )

    assert seen == ["ksana", "judge"]
    assert result.pipeline_failed is True
    assert result.system_health["failed_steps"] == ["ksana_pipeline"]
    assert [(step.name, step.status) for step in result.steps] == [
        ("ksana_pipeline", "failed"),
        ("export_events", "skipped"),
        ("push_to_alaya", "skipped"),
        ("judge_gate_poll", "success"),
    ]
    assert result.steps[1].detail == "blocked_by=ksana_pipeline"
    assert result.steps[2].detail == "blocked_by=ksana_pipeline"


def test_daemon_runner_lock_skip(tmp_path: Path) -> None:
    lock_path = tmp_path / "gotra.lock"
    lock_path.write_text("held", encoding="utf-8")

    result = GotraDaemonRunner(()).run_once(
        DaemonRunConfig(
            brief_type="morning",
            data_dir=tmp_path / "missing-data",
            dry_run=True,
            lock_path=lock_path,
        )
    )

    assert result.system_health == {"skipped": True, "reason": "lockfile_exists"}
    assert result.stock_pool == {}
    assert result.steps == ()


def test_daemon_cli_dry_run_once(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "--once",
            "--dry-run",
            "--type",
            "morning",
            "--data-dir",
            "engine/ksana/data",
            "--lock-path",
            str(tmp_path / "gotra.lock"),
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"dry_run": true' in output
    assert '"brief_type": "morning"' in output


def test_render_and_notify_writes_local_report_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOTIFIER_CHANNELS", "telegram")
    monkeypatch.delenv("GOTRA_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    data_dir = tmp_path / "data"

    result = render_and_notify(
        DaemonRunConfig(
            brief_type="evening",
            data_dir=data_dir,
            run_date="2026-06-14",
            lock_path=tmp_path / "gotra.lock",
        ),
        DaemonRunContext(pipeline_failed=True, system_health={"skipped": False}),
    )

    assert result.status == "success"
    assert "telegram notifier unavailable" in result.error
    markdown = data_dir / "reports" / "2026-06-14_evening.md"
    html = data_dir / "reports" / "2026-06-14_evening.html"
    assert markdown.exists()
    assert html.exists()
    markdown_text = markdown.read_text(encoding="utf-8")
    assert "- pipeline_failed: True" in markdown_text
    assert "## Strong Pending Approval" in markdown_text
