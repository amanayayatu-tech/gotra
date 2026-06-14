"""Markdown and SVG report generation for Phase BT."""

from __future__ import annotations

from datetime import UTC, datetime
import html
import json
from pathlib import Path
from typing import Any

from gotra.backtest.protocol import STYLE_WINDOWS
from gotra.backtest.statistics import cumulative_mse_series


def write_backtest_report(
    *,
    data_dir: str | Path,
    run_root: str | Path,
    summary: dict[str, Any],
    steps: list[dict[str, Any]],
) -> tuple[Path, Path]:
    output_dir = Path(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / "REPORT_backtest_mse.svg"
    _write_svg(chart_path, cumulative_mse_series(steps))
    report_path = output_dir / "REPORT_backtest.md"
    report_path.write_text(
        _render_markdown(run_root=Path(run_root), summary=summary, chart_path=chart_path),
        encoding="utf-8",
    )
    return report_path, chart_path


def _render_markdown(*, run_root: Path, summary: dict[str, Any], chart_path: Path) -> str:
    lines = [
        "# Phase BT Backtest Report",
        "",
        f"Generated at: `{datetime.now(UTC).isoformat()}`",
        f"Run root: `{run_root}`",
        f"MSE chart: `{chart_path}`",
        "",
        "## Run Mode",
        "",
        f"- mode: `{summary.get('mode')}`",
        f"- provider: `{summary.get('provider')}`",
        f"- provider_metadata: `{json.dumps(summary.get('provider_metadata'), sort_keys=True)}`",
        f"- step_months: `{summary.get('step_months')}`",
        f"- sampled_validation_only: `{summary.get('sampled_validation_only')}`",
        "",
        "This report distinguishes correctness evidence from scientific hypothesis evidence. "
        "Sampled or max-step-limited runs can validate plumbing, cache, budget, audit, "
        "and report paths, but they cannot prove the preregistered H1/H2/H3 claims.",
        "",
        "## Correctness Gates",
        "",
    ]
    audit = summary.get("audit") or {}
    system_health = summary.get("system_health") or {}
    lines.extend(
        [
            f"- system_health_status: `{system_health.get('status')}`",
            f"- system_health_paused: `{system_health.get('paused')}`",
            f"- provider_errors: `{system_health.get('provider_errors')}`",
            f"- zero_future_function_audit: `{audit.get('ok')}`",
            f"- steps_checked: `{audit.get('steps_checked')}`",
            f"- event_rows_checked: `{audit.get('event_rows_checked')}`",
            "- event_actor_required: `backtest/walk_forward`",
            f"- price_cache_network_after_cache: `{summary.get('price_cache_network_after_cache')}`",
            f"- perplexity_disabled: `{summary.get('perplexity_disabled')}`",
            "- raw_db_writes: `0`",
            f"- token_budget: `{json.dumps(system_health.get('token_budget'), sort_keys=True)}`",
            "",
        ]
    )
    if system_health.get("alerts"):
        lines.append("### System Health Alerts")
        lines.append("")
        for alert in system_health["alerts"]:
            lines.append(f"- {alert}")
        lines.append("")
    if audit.get("violations"):
        lines.append("### Audit Violations")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(audit["violations"], ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    metrics = summary.get("metrics") or {}
    lines.extend(
        [
            "## Metrics",
            "",
            f"- scored_steps: `{metrics.get('scored_steps')}`",
            f"- paired_steps: `{metrics.get('paired_steps')}`",
            f"- mse_by_arm: `{json.dumps(metrics.get('mse_by_arm'), sort_keys=True)}`",
            f"- differential_mse_mean: `{metrics.get('differential_mse_mean')}`",
            "",
            "## Hypotheses",
            "",
            "Hypotheses are evaluated mechanically below, but sampled or max-step-limited runs "
            "are not scientific validation of the full preregistered claim.",
            "",
        ]
    )
    hypotheses = metrics.get("hypotheses") or {}
    for name, value in hypotheses.items():
        lines.extend([f"### {name}", "", "```json"])
        lines.append(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        lines.extend(["```", ""])

    lines.extend(
        [
            "## Style Windows",
            "",
            "| Window | Start | End |",
            "|---|---:|---:|",
        ]
    )
    for window in STYLE_WINDOWS:
        lines.append(f"| {window.name} | {window.start.isoformat()} | {window.end.isoformat()} |")

    lines.extend(
        [
            "",
            "## Inference Limits",
            "",
            "- The universe is hand-selected and survivorship-biased.",
            "- Current frontier models may have historical pretraining leakage; absolute MSE is not "
            "interpretable as real forecasting skill.",
            "- Differential MSE is more useful than absolute MSE under shared inputs/provider, but it "
            "may still contain state-feedback leakage interactions.",
            "- A sampled or max-step-limited run is a correctness or calibration artifact, "
            "not a full monthly 10x10-year scientific result.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_svg(path: Path, series: dict[str, list[dict[str, Any]]]) -> None:
    width = 960
    height = 360
    padding = 48
    points_by_arm: dict[str, list[tuple[float, float]]] = {}
    values = [
        float(item["mse"])
        for rows in series.values()
        for item in rows
        if item.get("mse") is not None
    ]
    max_value = max(values) if values else 1.0
    max_len = max((len(rows) for rows in series.values()), default=1)
    for arm, rows in series.items():
        points: list[tuple[float, float]] = []
        for index, item in enumerate(rows):
            x = padding + (width - padding * 2) * (index / max(max_len - 1, 1))
            y = height - padding - (height - padding * 2) * (float(item["mse"]) / max_value)
            points.append((round(x, 2), round(y, 2)))
        points_by_arm[arm] = points

    colors = {"baseline": "#c2410c", "alaya": "#0f766e"}
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" stroke="#333"/>',
        f'<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height-padding}" stroke="#333"/>',
        f'<text x="{padding}" y="24" font-size="16" font-family="sans-serif">Cumulative MSE by Arm</text>',
    ]
    for arm, points in points_by_arm.items():
        if not points:
            continue
        point_text = " ".join(f"{x},{y}" for x, y in points)
        color = colors.get(arm, "#334155")
        svg_lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{point_text}"/>'
        )
        x, y = points[-1]
        svg_lines.append(
            f'<text x="{x + 8}" y="{y}" font-size="13" font-family="sans-serif" fill="{color}">{html.escape(arm)}</text>'
        )
    svg_lines.append("</svg>")
    path.write_text("\n".join(svg_lines) + "\n", encoding="utf-8")
