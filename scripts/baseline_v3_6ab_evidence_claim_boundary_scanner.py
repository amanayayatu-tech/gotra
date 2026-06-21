#!/usr/bin/env python3
"""GOTRA v3.6AB evidence claim boundary scanner / preflight guard."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any


SUMMARY_SCHEMA = "gotra.baseline_v3_6ab.evidence_claim_boundary_scan_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_6ab.evidence_claim_boundary_scan_manifest.v1"
RUN_ID_PREFIX = "baseline_v3_6ab_evidence_claim_boundary_scan_"
SCRIPT_VERSION = "v3.6ab-20260621"

STATUS_CLEAN = "CLAIM_BOUNDARY_CLEAN"
STATUS_BLOCKED_ARTIFACT = "CLAIM_BOUNDARY_BLOCKED_ARTIFACT"
STATUS_BLOCKED_OVERCLAIM = "CLAIM_BOUNDARY_BLOCKED_OVERCLAIM"
STATUS_BLOCKED_DIRECT_LLM = "CLAIM_BOUNDARY_BLOCKED_DIRECT_LLM"
STATUS_BLOCKED_MATURITY_GATE = "CLAIM_BOUNDARY_BLOCKED_MATURITY_GATE"
STATUS_BLOCKED_RUN_ID_EXISTS = "CLAIM_BOUNDARY_BLOCKED_RUN_ID_EXISTS"

DIRECT_LLM_INTERPRETATION = "direct_llm_parametric_memory_control"

FORBIDDEN_PATH_PATTERNS = (
    r"^data/backtest/runs/",
    r"^data/paper_trading/",
    r"(^|/)\.env",
    r"\.(sqlite|sqlite3|db)$",
    r"\.(bundle|tar|tgz|tar\.gz|zip)$",
    r"(^|/)(raw_outputs?|provider_raw|transcripts?)(/|$)",
    r"STAGE8|STAGE9|Stage8|Stage9",
)

OVERCLAIM_PATTERNS = (
    (
        "oos_science_public_trading_claim",
        re.compile(
            r"\b(OOS|science|public|trading|investment)\b.{0,40}"
            r"\b(pass|proof|claim|advice|recommendation|validated|accepted)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "provider_runtime_as_public_claim",
        re.compile(
            r"\b(provider|runtime|canary|tiny|smoke|formal-lite|formal_lite|"
            r"internal evidence|historical/internal evidence)\b"
            r".{0,60}\b(science|public|trading|investment|proof|claim|advice)\b",
            re.IGNORECASE,
        ),
    ),
)

MATURITY_GATE_PATTERNS = (
    (
        "v3_7_allowed_true",
        re.compile(r"\bv3[_ .-]?7[_ .-]?allowed\s*[:=]\s*true\b", re.IGNORECASE),
    ),
    (
        "v3_7_verdict_allowed",
        re.compile(r"\bv3\.?7\b.{0,40}\b(verdict|30D)\b.{0,40}\b(allowed|ready|pass)\b", re.IGNORECASE),
    ),
    (
        "thirty_day_forward_live_verdict",
        re.compile(r"\b(30D|thirty[- ]day)\b.{0,60}\b(forward-live\s+)?verdict\b.{0,40}\b(pass|ready|allowed)\b", re.IGNORECASE),
    ),
)

SHORT_HORIZON_AS_30D_PATTERNS = (
    (
        "short_horizon_as_30d_verdict",
        re.compile(
            r"\b(short[-_ ]horizon|SHORT_HORIZON).{0,80}"
            r"\b(30D|thirty[- ]day|v3\.?7|verdict)\b.{0,40}\b(allowed|ready|pass|equivalent)\b",
            re.IGNORECASE,
        ),
    ),
)

WARNING_PATTERNS = (
    (
        "ambiguous_ready_wording",
        re.compile(r"\bready\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True)
class ScanConfig:
    scan_run_id: str
    output_dir: Path
    files: tuple[Path, ...] = ()
    manifest: Path | None = None
    allow_overwrite: bool = False


@dataclass(frozen=True)
class ScanSource:
    path: str
    text: str
    origin: str


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"scan_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("scan_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def forbidden_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(re.search(pattern, normalized) for pattern in FORBIDDEN_PATH_PATTERNS)


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    return payload


def manifest_sources(manifest: dict[str, Any]) -> tuple[list[ScanSource], list[str]]:
    sources: list[ScanSource] = []
    paths: list[str] = []
    for key in ("changed_files", "changedFiles", "paths"):
        raw = manifest.get(key, [])
        if isinstance(raw, list):
            paths.extend(path_from_entry(entry) for entry in raw)
    raw_files = manifest.get("files", manifest.get("documents", []))
    if isinstance(raw_files, list):
        for entry in raw_files:
            source = source_from_manifest_entry(entry)
            if source.path:
                paths.append(source.path)
            sources.append(source)
    return sources, [path for path in paths if path]


def path_from_entry(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("path") or entry.get("filename") or entry.get("name") or "")
    return ""


def source_from_manifest_entry(entry: Any) -> ScanSource:
    if isinstance(entry, str):
        return ScanSource(path="", text=entry, origin="manifest_text")
    if not isinstance(entry, dict):
        return ScanSource(path="", text="", origin="manifest_invalid")
    return ScanSource(
        path=str(entry.get("path") or entry.get("filename") or ""),
        text=str(entry.get("text") or entry.get("body") or entry.get("content") or ""),
        origin="manifest",
    )


def collect_sources(config: ScanConfig) -> tuple[list[ScanSource], list[str]]:
    sources: list[ScanSource] = []
    all_paths: list[str] = []
    if config.manifest:
        manifest = load_manifest(config.manifest)
        manifest_texts, manifest_paths = manifest_sources(manifest)
        sources.extend(manifest_texts)
        all_paths.extend(manifest_paths)
    for path in config.files:
        file_path = str(path)
        all_paths.append(file_path)
        if forbidden_path(file_path):
            continue
        sources.append(
            ScanSource(
                path=file_path,
                text=path.read_text(encoding="utf-8"),
                origin="file",
            )
        )
    return sources, sorted({path for path in all_paths if path})


def make_blocked_item(path: str, line_number: int, rule_id: str, reason: str) -> dict[str, Any]:
    return {
        "path": path,
        "line_number": line_number,
        "rule_id": rule_id,
        "reason": reason,
    }


def is_negated(text: str, match_start: int) -> bool:
    prefix = text[max(0, match_start - 64) : match_start].lower()
    return any(marker in prefix for marker in ("not ", "no ", "不是", "不得", "非"))


def line_allows_boundary(line: str) -> bool:
    lowered = line.lower()
    return any(
        marker in lowered
        for marker in (
            "engineering/local only",
            "historical/internal only",
            "not oos",
            "not science",
            "not public",
            "not trading",
            "not investment",
            "v3_7_allowed=false",
            "v3.7 allowed false",
            DIRECT_LLM_INTERPRETATION,
        )
    )


def scan_source(source: ScanSource) -> dict[str, list[dict[str, Any]]]:
    result = {
        "overclaim": [],
        "direct_llm": [],
        "maturity_gate": [],
        "short_horizon_as_30d": [],
        "warnings": [],
    }
    for line_number, line in enumerate(source.text.splitlines(), start=1):
        scan_line(source, line, line_number, result)
    return result


def scan_line(
    source: ScanSource,
    line: str,
    line_number: int,
    result: dict[str, list[dict[str, Any]]],
) -> None:
    for rule_id, pattern in OVERCLAIM_PATTERNS:
        for match in pattern.finditer(line):
            if is_negated(line, match.start()):
                continue
            result["overclaim"].append(
                make_blocked_item(
                    source.path,
                    line_number,
                    rule_id,
                    "evidence claim exceeds engineering/local/internal boundary",
                )
            )
    if "direct_llm" in line and DIRECT_LLM_INTERPRETATION not in line:
        result["direct_llm"].append(
            make_blocked_item(
                source.path,
                line_number,
                "direct_llm_without_parametric_memory_control",
                "direct_llm must be labeled direct_llm_parametric_memory_control",
            )
        )
    if re.search(r"direct_llm.{0,80}clean\s+no[- ]future\s+baseline", line, re.IGNORECASE):
        result["direct_llm"].append(
            make_blocked_item(
                source.path,
                line_number,
                "direct_llm_clean_no_future_baseline",
                "direct_llm cannot be treated as a clean no-future baseline",
            )
        )
    for rule_id, pattern in MATURITY_GATE_PATTERNS:
        for match in pattern.finditer(line):
            if is_negated(line, match.start()) or line_allows_boundary(line):
                continue
            result["maturity_gate"].append(
                make_blocked_item(
                    source.path,
                    line_number,
                    rule_id,
                    "30D/v3.7 verdict wording bypasses maturity gate",
                )
            )
    for rule_id, pattern in SHORT_HORIZON_AS_30D_PATTERNS:
        for match in pattern.finditer(line):
            if is_negated(line, match.start()) or line_allows_boundary(line):
                continue
            result["short_horizon_as_30d"].append(
                make_blocked_item(
                    source.path,
                    line_number,
                    rule_id,
                    "short-horizon canary cannot authorize 30D/v3.7 verdict",
                )
            )
    if not any(result[key] for key in ("overclaim", "direct_llm", "maturity_gate")):
        for rule_id, pattern in WARNING_PATTERNS:
            if pattern.search(line) and not line_allows_boundary(line):
                result["warnings"].append(
                    make_blocked_item(
                        source.path,
                        line_number,
                        rule_id,
                        "ambiguous readiness wording requires context",
                    )
                )


def scan_sources(sources: list[ScanSource]) -> dict[str, list[dict[str, Any]]]:
    merged = {
        "overclaim": [],
        "direct_llm": [],
        "maturity_gate": [],
        "short_horizon_as_30d": [],
        "warnings": [],
    }
    for source in sources:
        source_result = scan_source(source)
        for key in merged:
            merged[key].extend(source_result[key])
    return merged


def status_for_counts(
    *,
    forbidden_path_count: int,
    overclaim_count: int,
    direct_llm_count: int,
    maturity_gate_count: int,
    short_horizon_as_30d_count: int,
) -> str:
    if forbidden_path_count:
        return STATUS_BLOCKED_ARTIFACT
    if maturity_gate_count or short_horizon_as_30d_count:
        return STATUS_BLOCKED_MATURITY_GATE
    if direct_llm_count:
        return STATUS_BLOCKED_DIRECT_LLM
    if overclaim_count:
        return STATUS_BLOCKED_OVERCLAIM
    return STATUS_CLEAN


def base_summary(config: ScanConfig, *, run_root: Path) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "scan_run_id": config.scan_run_id,
        "scan_run_root": str(run_root),
        "scan_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "scanned_file_count": 0,
        "forbidden_path_count": 0,
        "evidence_overclaim_count": 0,
        "direct_llm_mislabel_count": 0,
        "maturity_gate_bypass_count": 0,
        "short_horizon_as_30d_count": 0,
        "warning_count": 0,
        "blocked_items": [],
        "warnings": [],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_allowed": False,
        "v3_7_verdict_executed": False,
        "evidence_layer": "engineering_claim_boundary_scan",
        "overall_status": STATUS_CLEAN,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "non_claims": {
            "not_oos": True,
            "not_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_30d_forward_live_verdict": True,
        },
    }


def blocked_run_id_summary(config: ScanConfig, *, run_root: Path) -> dict[str, Any]:
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "overall_status": STATUS_BLOCKED_RUN_ID_EXISTS,
            "blocked_items": [
                make_blocked_item(str(run_root), 0, "output_run_id_exists", "output run id exists")
            ],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def run_scan(config: ScanConfig) -> dict[str, Any]:
    validate_run_id(config.scan_run_id)
    run_root = config.output_dir / config.scan_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        return blocked_run_id_summary(config, run_root=run_root)
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    sources, paths = collect_sources(config)
    forbidden_items = [
        make_blocked_item(path, 0, "forbidden_artifact_path", "path is forbidden artifact input")
        for path in paths
        if forbidden_path(path)
    ]
    scan_result = scan_sources(
        [source for source in sources if not forbidden_path(source.path)]
    )
    overclaims = scan_result["overclaim"]
    direct_llm = scan_result["direct_llm"]
    maturity = scan_result["maturity_gate"]
    short_horizon = scan_result["short_horizon_as_30d"]
    warnings = scan_result["warnings"]
    status = status_for_counts(
        forbidden_path_count=len(forbidden_items),
        overclaim_count=len(overclaims),
        direct_llm_count=len(direct_llm),
        maturity_gate_count=len(maturity),
        short_horizon_as_30d_count=len(short_horizon),
    )
    summary = base_summary(config, run_root=run_root)
    summary.update(
        {
            "scanned_file_count": len(paths),
            "forbidden_path_count": len(forbidden_items),
            "evidence_overclaim_count": len(overclaims),
            "direct_llm_mislabel_count": len(direct_llm),
            "maturity_gate_bypass_count": len(maturity),
            "short_horizon_as_30d_count": len(short_horizon),
            "warning_count": len(warnings),
            "blocked_items": forbidden_items + maturity + short_horizon + direct_llm + overclaims,
            "warnings": warnings,
            "overall_status": status,
            "scanned_paths": paths,
            "manifest_path": str(config.manifest) if config.manifest else "",
            "manifest_sha256": sha256_file(config.manifest) if config.manifest else "",
        }
    )
    write_outputs(config=config, run_root=run_root, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def write_outputs(*, config: ScanConfig, run_root: Path, summary: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "scan_run_id": config.scan_run_id,
        "summary_path": str(run_root / "summary.json"),
        "overall_status": summary["overall_status"],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
    }
    for filename, payload in (("summary.json", summary), ("manifest.json", manifest)):
        (run_root / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-run-id", default=default_run_id())
    parser.add_argument("--file", dest="files", type=Path, action="append", default=[])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/gotra_v3_6ab_evidence_claim_boundary_scan/runs"),
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ScanConfig:
    return ScanConfig(
        scan_run_id=str(args.scan_run_id),
        output_dir=args.output_dir,
        files=tuple(args.files or ()),
        manifest=args.manifest,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_scan(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI reports structured failures where possible.
        print(f"evidence claim boundary scan failed: {exc}", file=sys.stderr)
        return 2
    return 0 if summary.get("overall_status") == STATUS_CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
