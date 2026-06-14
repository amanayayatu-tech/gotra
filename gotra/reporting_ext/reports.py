"""Daily report rendering helpers for Gotra."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import html
import json
from pathlib import Path
from typing import Any, Literal

ReportType = Literal["morning", "evening"]

BASE_REPORT_SECTIONS: tuple[str, ...] = (
    "System Health",
    "Research Signals",
    "Judge Decisions",
    "Active Predictions",
    "Knowledge Additions",
)

EVENING_EXTRA_SECTIONS: tuple[str, ...] = (
    "Outcome Updates",
    "Auto-Quarantine",
    "Strong Pending Approval",
    "Next Run Queue",
)


@dataclass(frozen=True)
class ReportSection:
    title: str
    content: Any = None


@dataclass(frozen=True)
class ReportFiles:
    report_type: ReportType
    report_date: str
    markdown_path: Path
    html_path: Path
    markdown: str
    html: str


def render_report_markdown(
    *,
    report_date: str | date | datetime,
    report_type: ReportType,
    sections: Mapping[str, Any] | Sequence[ReportSection | tuple[str, Any]] | None = None,
    title: str | None = None,
) -> str:
    """Render the canonical Gotra daily report markdown."""

    normalized_type = _normalize_report_type(report_type)
    date_label = _format_report_date(report_date)
    report_title = title or f"Gotra {normalized_type.title()} Report - {date_label}"
    lines = [f"# {report_title}", ""]

    for section in _ordered_sections(normalized_type, sections):
        lines.extend([f"## {section.title}", "", _format_section_content(section.content), ""])

    return "\n".join(lines).rstrip() + "\n"


def write_report_files(
    *,
    data_dir: str | Path = "data",
    report_date: str | date | datetime,
    report_type: ReportType,
    sections: Mapping[str, Any] | Sequence[ReportSection | tuple[str, Any]] | None = None,
    title: str | None = None,
) -> ReportFiles:
    """Write markdown and HTML report files under data/reports."""

    normalized_type = _normalize_report_type(report_type)
    date_label = _format_report_date(report_date)
    markdown = render_report_markdown(
        report_date=date_label,
        report_type=normalized_type,
        sections=sections,
        title=title,
    )

    output_dir = Path(data_dir) / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe_file_component(date_label)}_{normalized_type}"
    markdown_path = output_dir / f"{stem}.md"
    html_path = output_dir / f"{stem}.html"
    report_html = _render_html(
        markdown=markdown,
        report_date=date_label,
        report_type=normalized_type,
        source_path=str(markdown_path),
        title=title,
    )

    _write_text(markdown_path, markdown)
    _write_text(html_path, report_html)

    return ReportFiles(
        report_type=normalized_type,
        report_date=date_label,
        markdown_path=markdown_path,
        html_path=html_path,
        markdown=markdown,
        html=report_html,
    )


write_daily_report = write_report_files


def _ordered_sections(
    report_type: ReportType,
    sections: Mapping[str, Any] | Sequence[ReportSection | tuple[str, Any]] | None,
) -> tuple[ReportSection, ...]:
    section_map = _coerce_section_map(sections)
    required = BASE_REPORT_SECTIONS
    if report_type == "evening":
        required = (*BASE_REPORT_SECTIONS, *EVENING_EXTRA_SECTIONS)

    ordered = [ReportSection(title, section_map.pop(title, None)) for title in required]
    ordered.extend(ReportSection(title, content) for title, content in section_map.items())
    return tuple(ordered)


def _coerce_section_map(
    sections: Mapping[str, Any] | Sequence[ReportSection | tuple[str, Any]] | None,
) -> dict[str, Any]:
    if sections is None:
        return {}
    if isinstance(sections, Mapping):
        return dict(sections)

    section_map: dict[str, Any] = {}
    for section in sections:
        if isinstance(section, ReportSection):
            section_map[section.title] = section.content
            continue
        title, content = section
        section_map[str(title)] = content
    return section_map


def _format_section_content(content: Any) -> str:
    if content is None:
        return "_No items._"
    if isinstance(content, str):
        return content.strip() or "_No items._"
    if isinstance(content, Mapping):
        if not content:
            return "_No items._"
        return "\n".join(f"- {key}: {_format_inline_value(value)}" for key, value in content.items())
    if isinstance(content, Sequence) and not isinstance(content, bytes):
        if not content:
            return "_No items._"
        lines = []
        for item in content:
            if isinstance(item, Mapping):
                lines.append(
                    "- "
                    + ", ".join(
                        f"{key}: {_format_inline_value(value)}" for key, value in item.items()
                    )
                )
            else:
                lines.append(f"- {_format_inline_value(item)}")
        return "\n".join(lines)
    return str(content)


def _format_inline_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _render_html(
    *,
    markdown: str,
    report_date: str,
    report_type: ReportType,
    source_path: str,
    title: str | None,
) -> str:
    try:
        from orchestrator.reporting.html_renderer import ReportPresentation, render_report_html

        return render_report_html(
            markdown,
            ReportPresentation(
                title=title or f"Gotra {report_type.title()} Report - {report_date}",
                report_label=f"Gotra {report_type.title()} Report",
                eyebrow=f"{report_date} autonomous reporting",
                source_path=source_path,
            ),
        )
    except Exception:
        return _render_basic_html(markdown, title or f"Gotra {report_type.title()} Report")


def _render_basic_html(markdown: str, title: str) -> str:
    escaped_title = html.escape(title)
    escaped_markdown = html.escape(markdown)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{escaped_title}</title>",
            "</head>",
            "<body>",
            f"  <pre>{escaped_markdown}</pre>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _normalize_report_type(report_type: str) -> ReportType:
    normalized = report_type.strip().lower()
    if normalized not in {"morning", "evening"}:
        raise ValueError("report_type must be 'morning' or 'evening'")
    return normalized  # type: ignore[return-value]


def _format_report_date(report_date: str | date | datetime) -> str:
    if isinstance(report_date, datetime):
        return report_date.date().isoformat()
    if isinstance(report_date, date):
        return report_date.isoformat()
    normalized = str(report_date).strip()
    if not normalized:
        raise ValueError("report_date must not be empty")
    return normalized


def _safe_file_component(value: str) -> str:
    return value.replace("/", "-").replace("\\", "-").replace(":", "")


def _write_text(path: Path, content: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)
