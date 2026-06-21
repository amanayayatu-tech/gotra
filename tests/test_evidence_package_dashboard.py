from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6x_evidence_package_dashboard as dashboard


def test_dashboard_builds_boundary_clean_summary(tmp_path: Path) -> None:
    docs = _write_required_docs(tmp_path)
    config = dashboard.DashboardConfig(
        package_run_id="baseline_v3_6x_evidence_package_dashboard_test",
        output_dir=tmp_path / "runs",
        source_docs=docs,
    )

    summary = dashboard.run_dashboard(config)

    assert summary["status"] == dashboard.STATUS_READY
    assert summary["thirty_day_forward_live_maturity_status"] == "DATA_NOT_MATURED"
    assert summary["next_check_after"] == "2026-07-21T00:00:00Z"
    assert summary["v3_7_allowed"] is False
    assert summary["v3_7_verdict_executed"] is False
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["direct_llm_interpretation"] == (
        dashboard.DIRECT_LLM_INTERPRETATION
    )
    assert summary["historical_internal_verdict"]["status"] == "FULL_GOTRA_BETTER"
    assert summary["historical_internal_verdict"]["scope"] == (
        "historical_internal_mse_specific_only"
    )
    assert "OOS pass" in summary["cannot_say"]
    assert "30D forward-live verdict" in summary["cannot_say"]
    assert "30D actual forward-live outcomes are not mature" in summary["can_say"]

    saved = json.loads(
        (tmp_path / "runs" / config.package_run_id / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["schema"] == dashboard.SUMMARY_SCHEMA
    assert saved["source_document_missing_count"] == 0
    assert saved["source_document_required_snippet_missing_count"] == 0


def test_dashboard_blocks_missing_required_boundary_snippet(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text("missing the important boundaries\n", encoding="utf-8")
    config = dashboard.DashboardConfig(
        package_run_id="baseline_v3_6x_evidence_package_dashboard_missing",
        output_dir=tmp_path / "runs",
        source_docs=(
            dashboard.SourceDocConfig(
                doc_id="bad",
                path=doc,
                required_snippets=("DATA_NOT_MATURED",),
            ),
        ),
    )

    summary = dashboard.run_dashboard(config)

    assert summary["status"] == dashboard.STATUS_BLOCKED_SOURCE_DOCS
    assert summary["source_document_required_snippet_missing_count"] == 1
    assert summary["active_blockers"] == [
        "source_document_missing_or_missing_required_boundary"
    ]


def test_dashboard_blocks_existing_run_id_without_overwrite(tmp_path: Path) -> None:
    docs = _write_required_docs(tmp_path)
    run_id = "baseline_v3_6x_evidence_package_dashboard_collision"
    config = dashboard.DashboardConfig(
        package_run_id=run_id,
        output_dir=tmp_path / "runs",
        source_docs=docs,
    )
    dashboard.run_dashboard(config)
    summary_path = tmp_path / "runs" / run_id / "summary.json"
    original_text = summary_path.read_text(encoding="utf-8")

    blocked = dashboard.run_dashboard(config)

    assert blocked["status"] == dashboard.STATUS_BLOCKED_RUN_ID_EXISTS
    assert blocked["active_blockers"] == ["output_run_id_exists"]
    assert summary_path.read_text(encoding="utf-8") == original_text


def test_dashboard_cli_returns_nonzero_for_blocked_run_id(tmp_path: Path) -> None:
    docs = _write_required_docs(tmp_path)
    run_id = "baseline_v3_6x_evidence_package_dashboard_cli_collision"
    config = dashboard.DashboardConfig(
        package_run_id=run_id,
        output_dir=tmp_path / "runs",
        source_docs=docs,
    )
    dashboard.run_dashboard(config)

    rc = dashboard.main(
        [
            "--package-run-id",
            run_id,
            "--output-dir",
            str(tmp_path / "runs"),
            "--source-doc",
            f"v3_6s={docs[0].path}",
        ]
    )

    assert rc == 1


def _write_required_docs(tmp_path: Path) -> tuple[dashboard.SourceDocConfig, ...]:
    direct = dashboard.DIRECT_LLM_INTERPRETATION
    return (
        _write_doc(
            tmp_path,
            "v3_6s.md",
            (
                "DATA_NOT_MATURED",
                "2026-07-21T00:00:00Z",
                direct,
                "Provider/backend called: `false`",
                "Codex CLI called: `false`",
                "Formal-lite entered: `false`",
            ),
        ),
        _write_doc(
            tmp_path,
            "v3_6t.md",
            (
                "DATA_NOT_MATURED",
                "WAIT_UNTIL_NEXT_CHECK",
                "v3.7 verdict allowed: `false`",
                direct,
            ),
        ),
        _write_doc(
            tmp_path,
            "v3_6u.md",
            (
                "FULL_GOTRA_BETTER",
                "mse_ci_excludes_zero_positive",
                "historical/internal",
                direct,
            ),
        ),
        _write_doc(
            tmp_path,
            "v3_6v.md",
            (
                "SHORT_HORIZON_COHORT_PLAN_READY",
                "equivalent to 30D outcomes",
                "gpt-5.5",
                "high",
                direct,
            ),
        ),
    )


def _write_doc(
    tmp_path: Path,
    filename: str,
    snippets: tuple[str, ...],
) -> dashboard.SourceDocConfig:
    path = tmp_path / filename
    path.write_text("\n".join(snippets) + "\n", encoding="utf-8")
    return dashboard.SourceDocConfig(
        doc_id=filename.removesuffix(".md"),
        path=path,
        required_snippets=snippets,
    )
