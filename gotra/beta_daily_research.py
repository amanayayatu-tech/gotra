"""Fail-closed Stage 15B daily research orchestration.

The candidate pipeline always runs inside an isolated staging directory first.
Nothing here changes the beta clock or rewrites prior daily events.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PIPELINE = Path(__file__).resolve().parents[1] / "scripts" / "public_stock_pool_full_analyst_pipeline.py"
DEFAULT_SYMBOLS = ("HKEX:0700", "HKEX:1810", "HKEX:9688")
ENABLEMENT_PATH = Path("/opt/gotra/config/stage15b_daily_research_enablement.json")
STATUS_FILE = "status_full_analyst_evening_hk.json"
REQUIRED_EXECUTION_MODEL = "deep_research_dossier_then_parallel_perspectives"
REQUIRED_SYMBOL_SCHEMA = "gotra.full_analyst.symbol.v4"
REQUIRED_STATUS_KEYS = {
    "run_id", "run_status", "failed_count", "blocked_count", "publish_count",
    "publish_with_boundary_count",
    "needs_review_count", "data_gap_count", "public_scan_status",
    "alaya_readback_status", "ledger_integrity_status", "execution_model", "symbol_schema",
}
REQUIRED_SYMBOL_HASH_KEYS = {
    "research_task_hash", "evidence_packet_hash", "market_data_snapshot_hash",
    "k_dossier_hash", "research_quality_gate_hash", "knowledge_gate_hash",
    "research_signal_hash", "publication_decision_hash", "public_payload_hash",
}
FIXTURE_RE = re.compile(r"\bfixture(?: context| runner| output)?\b", re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_stamp(value: datetime | None = None) -> str:
    return (value or utc_now()).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@dataclass(frozen=True)
class DailyResearchStaging:
    root: Path
    output_dir: Path
    private_dir: Path
    static_dir: Path
    run_id: str


def staging_layout(root: Path, *, run_id: str) -> DailyResearchStaging:
    return DailyResearchStaging(root, root / "output", root / "private", root / "static", run_id)


def enablement_manifest(path: Path = ENABLEMENT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"enabled": False, "reason": "reviewed enablement manifest absent", "path": str(path)}
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"enabled": False, "reason": f"enablement manifest invalid:{type(exc).__name__}", "path": str(path)}
    required = {
        "enabled": True,
        "history_backfilled": False,
        "fixture_allowed": False,
        "start_from_next_scheduled_run_only": True,
    }
    mismatches = [key for key, value in required.items() if payload.get(key) != value]
    if not payload.get("reviewed_canary_manifest_sha256"):
        mismatches.append("reviewed_canary_manifest_sha256")
    return {
        **payload,
        "enabled": not mismatches,
        "reason": "reviewed enablement manifest accepted" if not mismatches else f"enablement contract mismatch:{','.join(mismatches)}",
        "path": str(path),
    }


def build_pipeline_command(
    staging: DailyResearchStaging,
    *,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    python: str | None = None,
) -> list[str]:
    command = [
        python or os.environ.get("GOTRA_PYTHON", "/opt/gotra/.venv/bin/python"),
        str(PIPELINE), "--mode", "full-analyst-evening-hk-test", "--run-id", staging.run_id,
        "--output-dir", str(staging.output_dir),
        "--private-audit-root", str(staging.private_dir),
        "--static-dir", str(staging.static_dir), "--publish-static",
        "--llm-runner", "codex-cli", "--alaya-mode", "real",
        "--v40-cognition-flywheel", "--execution-model", REQUIRED_EXECUTION_MODEL,
        "--max-concurrency", str(min(3, len(symbols))), "--agent-concurrency", "3",
        "--per-symbol-timeout-seconds", "900", "--retries", "2",
    ]
    for symbol in symbols:
        command.extend(("--symbol", symbol))
    return command


def seed_staging_ledger(staging: DailyResearchStaging, production_reports: Path) -> None:
    staging.static_dir.mkdir(parents=True, exist_ok=True)
    source = production_reports / "research_ledger.json"
    if source.exists():
        shutil.copy2(source, staging.static_dir / source.name)


def _normalized_block(payload: dict[str, Any], key: str) -> str:
    outputs = payload.get("agent_outputs") if isinstance(payload.get("agent_outputs"), dict) else {}
    return re.sub(
        r"\s+",
        " ",
        json.dumps(outputs.get(key), ensure_ascii=False, sort_keys=True),
    ).strip().lower()


def validate_staged_run(staging: DailyResearchStaging, *, symbols: tuple[str, ...]) -> dict[str, Any]:
    status_path = staging.output_dir / STATUS_FILE
    errors: list[str] = []
    if not status_path.exists():
        return {"ok": False, "errors": ["status artifact missing"], "status_path": str(status_path)}
    status = read_json(status_path)
    missing_status = sorted(REQUIRED_STATUS_KEYS - set(status))
    if missing_status:
        errors.append(f"status required fields missing:{','.join(missing_status)}")
    checks = {
        "status run_id mismatch": status.get("run_id") != staging.run_id,
        "non-live llm runner": status.get("llm_runner") != "codex-cli",
        "execution model mismatch": status.get("execution_model") != REQUIRED_EXECUTION_MODEL,
        "symbol schema mismatch": status.get("symbol_schema") != REQUIRED_SYMBOL_SCHEMA,
        "failed symbols present": int(status.get("failed_count") or 0) != 0,
        "blocked symbols present": int(status.get("blocked_count") or 0) != 0,
        "public safety scan failed": status.get("public_scan_status") != "ok",
        "internal Alaya readback not verified": status.get("alaya_readback_status") != "verified",
        "ledger integrity not verified": status.get("ledger_integrity_status") != "ok",
    }
    errors.extend(message for message, failed in checks.items() if failed)

    symbol_payloads: list[dict[str, Any]] = []
    real_market_rows = 0
    fixture_hits: list[str] = []
    block_values: dict[str, list[str]] = {key: [] for key in ("f_partner_view", "w_partner_view", "g_partner_view", "chairman_synthesis", "red_team_audit")}
    for symbol_key in symbols:
        exchange, symbol = symbol_key.split(":", 1)
        path = staging.output_dir / "symbols" / f"{exchange}_{symbol}.json"
        if not path.exists():
            errors.append(f"symbol artifact missing:{symbol_key}")
            continue
        payload = read_json(path)
        symbol_payloads.append(payload)
        if payload.get("schema") != REQUIRED_SYMBOL_SCHEMA:
            errors.append(f"symbol schema mismatch:{symbol_key}")
        missing_hashes = sorted(key for key in REQUIRED_SYMBOL_HASH_KEYS if not payload.get(key))
        if missing_hashes:
            errors.append(f"symbol hashes missing:{symbol_key}:{','.join(missing_hashes)}")
        snapshot = payload.get("market_data_snapshot") if isinstance(payload.get("market_data_snapshot"), dict) else {}
        if snapshot.get("price_status") == "ok" and snapshot.get("provider") and not snapshot.get("future_data_risk"):
            real_market_rows += 1
        if FIXTURE_RE.search(json.dumps(payload, ensure_ascii=False, sort_keys=True)):
            fixture_hits.append(symbol_key)
        for key in block_values:
            block_values[key].append(_normalized_block(payload, key))
    if real_market_rows == 0:
        errors.append("no verified real market-data input")
    if fixture_hits:
        errors.append(f"fixture wording detected:{','.join(fixture_hits)}")
    duplicate_blocks = [key for key, values in block_values.items() if len(values) > 1 and len(set(values)) == 1]
    if duplicate_blocks:
        errors.append(f"all-symbol duplicate research blocks:{','.join(duplicate_blocks)}")
    publication_count = int(status.get("publish_with_boundary_count") or 0)
    if publication_count <= 0:
        errors.append("no publishable research artifact")
    return {
        "ok": not errors, "run_id": staging.run_id, "status_path": str(status_path),
        "symbols_requested": list(symbols), "symbols_validated": len(symbol_payloads),
        "real_data_input": real_market_rows > 0, "real_market_rows": real_market_rows,
        "fixture_used": bool(fixture_hits), "fixture_hits": fixture_hits,
        "duplicate_blocks": duplicate_blocks,
        "public_safety_status": status.get("public_scan_status"),
        "alaya_internal_readback_status": status.get("alaya_readback_status"),
        "ledger_integrity": status.get("ledger_integrity_status"),
        "publication_count": publication_count,
        "needs_review_count": int(status.get("needs_review_count") or 0),
        "data_gap_count": int(status.get("data_gap_count") or 0),
        "blocked_count": int(status.get("blocked_count") or 0),
        "failed_count": int(status.get("failed_count") or 0), "errors": errors,
    }


def run_staged_daily_research(
    *,
    evidence_root: Path,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    production_reports: Path = Path("/var/www/gotra-public-ledger/reports"),
    python: str | None = None,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    run_id = f"gotra_stage15b_daily_canary_{utc_stamp()}"
    staging = staging_layout(evidence_root / run_id, run_id=run_id)
    staging.root.mkdir(parents=True, exist_ok=False)
    seed_staging_ledger(staging, production_reports)
    command = build_pipeline_command(staging, symbols=symbols, python=python)
    completed = subprocess.run(command, cwd=str(PIPELINE.parent.parent), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout_seconds)
    (staging.root / "pipeline.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (staging.root / "pipeline.stderr.log").write_text(completed.stderr, encoding="utf-8")
    validation = validate_staged_run(staging, symbols=symbols)
    manifest = {
        "schema": "gotra.launch.beta_daily_research_canary.v1", "run_id": run_id,
        "dry_run": True, "side_effect_free_production": True,
        "public_artifact_written": False, "production_ledger_written": False,
        "history_backfilled": False, "beta_clock_changed": False, "fixture_allowed": False,
        "command": command, "returncode": completed.returncode, "validation": validation,
        "safe_to_enable_from_next_run": completed.returncode == 0 and validation["ok"],
        "staging_root": str(staging.root),
    }
    write_json(staging.root / "canary-manifest.json", manifest)
    return manifest


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.stage15b.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(target)
    target.chmod(0o644)


def production_smoke(*, run_id: str, reports_dir: Path, base_url: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    routes = ("/", "/beta", "/today/", "/track-record", "/monthly-reports", "/reports/status_full_analyst_evening_hk.json")
    for route in routes:
        url = base_url.rstrip("/") + route
        try:
            with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - fixed operator URL.
                body = response.read(2_000_000).decode("utf-8", errors="replace")
                status = response.status
        except (OSError, urllib.error.URLError) as exc:
            checks.append({"route": route, "ok": False, "error": type(exc).__name__})
            continue
        forbidden = any(token in body for token in ("[object Object]", "Traceback (most recent call last)", "sk-"))
        checks.append({"route": route, "ok": status == 200 and not forbidden, "http_status": status, "forbidden_rendering": forbidden})
    deployed_status = read_json(reports_dir / STATUS_FILE) if (reports_dir / STATUS_FILE).exists() else {}
    same_run = deployed_status.get("run_id") == run_id
    return {"ok": bool(checks) and all(item["ok"] for item in checks) and same_run, "same_run_id": same_run, "checks": checks}


def promote_staged_run(
    staging: DailyResearchStaging,
    *,
    production_reports: Path,
    base_url: str = "https://gotra.me",
) -> dict[str, Any]:
    validation = validate_staged_run(staging, symbols=tuple(read_json(staging.root / "canary-manifest.json")["validation"]["symbols_requested"]))
    if not validation["ok"]:
        return {"ok": False, "promoted": False, "reason": "staged validation failed", "validation": validation}
    sources = [path for path in staging.static_dir.iterdir() if path.is_file()]
    symbol_dir = staging.output_dir / "symbols"
    sources.extend(path for path in symbol_dir.iterdir() if path.is_file())
    backup_dir = staging.root / "production-backup"
    promoted: list[str] = []
    backups: dict[Path, Path] = {}
    try:
        for source in sources:
            target = production_reports / ("symbols" if source.parent == symbol_dir else "") / source.name
            if target.exists():
                backup = backup_dir / target.relative_to(production_reports)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backups[target] = backup
            _atomic_copy(source, target)
            promoted.append(str(target))
        smoke = production_smoke(run_id=staging.run_id, reports_dir=production_reports, base_url=base_url)
        if not smoke["ok"]:
            raise RuntimeError("same-run production smoke failed")
    except Exception as exc:  # noqa: BLE001 - rollback must cover every promotion failure.
        for target in [Path(value) for value in promoted]:
            backup = backups.get(target)
            if backup and backup.exists():
                _atomic_copy(backup, target)
            elif target.exists():
                target.unlink()
        return {"ok": False, "promoted": False, "rolled_back": True, "reason": type(exc).__name__, "backup_dir": str(backup_dir)}
    result = {"ok": True, "promoted": True, "rolled_back": False, "files": promoted, "backup_dir": str(backup_dir), "smoke": smoke}
    write_json(staging.root / "promotion-result.json", result)
    return result


def run_live_daily_research(
    *,
    evidence_root: Path,
    production_reports: Path = Path("/var/www/gotra-public-ledger/reports"),
    base_url: str = "https://gotra.me",
) -> dict[str, Any]:
    manifest = run_staged_daily_research(evidence_root=evidence_root, production_reports=production_reports)
    if not manifest["safe_to_enable_from_next_run"]:
        return {**manifest, "production_promotion": {"ok": False, "promoted": False, "reason": "canary validation failed"}}
    staging = staging_layout(Path(manifest["staging_root"]), run_id=str(manifest["run_id"]))
    promotion = promote_staged_run(staging, production_reports=production_reports, base_url=base_url)
    return {**manifest, "dry_run": False, "public_artifact_written": bool(promotion.get("promoted")), "production_ledger_written": bool(promotion.get("promoted")), "production_promotion": promotion}
