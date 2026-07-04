"""Launch-roadmap operational status, release bundle, and rollback helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HEARTBEAT_SCHEMA = "gotra.launch_ops.heartbeat.v1"
STATUS_SUMMARY_SCHEMA = "gotra.launch_ops.status_summary.v1"
RELEASE_BUNDLE_MANIFEST_SCHEMA = "gotra.launch_ops.release_bundle_manifest.v1"
ROLLBACK_DRY_RUN_SCHEMA = "gotra.launch_ops.rollback_dry_run.v1"

REQUIRED_HEARTBEAT_FIELDS = ("run_id", "started_at", "updated_at", "status", "current_step")
STATUS_CATEGORIES = ("frontend", "backend", "data", "release", "review")
RELEASE_BUNDLE_FILES = ("EVIDENCE_MANIFEST.json", "CHECKSUMS.sha256", "PUBLIC_SAFE_SUMMARY.md")

SECRET_OR_RAW_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"Authorization:", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{8,}"),
    re.compile(r"\b(?:OPENAI|ANTHROPIC|GITHUB)_API_KEY\b", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\s*[:=]", re.IGNORECASE),
    re.compile(r"/Users/peachy/Documents/alaya"),
    re.compile(r"\bprovider raw\b|\braw provider\b", re.IGNORECASE),
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assert_public_safe_text(text: str) -> None:
    for pattern in SECRET_OR_RAW_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"public_safe_summary_forbidden_pattern:{pattern.pattern}")


def heartbeat_payload(
    *,
    run_id: str,
    status: str,
    current_step: str,
    started_at: str | None = None,
    updated_at: str | None = None,
    evidence_layer: str = "local checks",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    payload = {
        "schema": HEARTBEAT_SCHEMA,
        "run_id": run_id,
        "started_at": started_at or now,
        "updated_at": updated_at or now,
        "status": status,
        "current_step": current_step,
        "evidence_layer": evidence_layer,
        "metadata": metadata or {},
    }
    validate_heartbeat(payload)
    return payload


def validate_heartbeat(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_HEARTBEAT_FIELDS if not payload.get(field)]
    if missing:
        raise ValueError(f"heartbeat_missing_required_fields:{','.join(missing)}")
    if payload.get("schema") != HEARTBEAT_SCHEMA:
        raise ValueError("heartbeat_invalid_schema")
    if "10h" in str(payload.get("status", "")).lower() and payload.get("evidence_layer") != "long-run/formal acceptance":
        raise ValueError("heartbeat_10h_status_requires_long_run_evidence_layer")


def write_heartbeat(path: Path, payload: dict[str, Any]) -> None:
    validate_heartbeat(payload)
    write_json(path, payload)


def status_summary(
    *,
    run_id: str,
    frontend: dict[str, Any],
    backend: dict[str, Any],
    data: dict[str, Any],
    release: dict[str, Any],
    review: dict[str, Any],
    evidence_layer: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    summary = {
        "schema": STATUS_SUMMARY_SCHEMA,
        "run_id": run_id,
        "generated_at": generated_at or utc_now_iso(),
        "evidence_layer": evidence_layer,
        "frontend": frontend,
        "backend": backend,
        "data": data,
        "release": release,
        "review": review,
        "boundary": {
            "not_investment_advice": True,
            "not_trading_signal": True,
            "no_target_price": True,
            "no_position_sizing": True,
            "no_return_promise": True,
            "no_performance_proof": True,
            "no_science_public_proof": True,
            "alaya_internal_only": True,
        },
    }
    validate_status_summary(summary)
    return summary


def validate_status_summary(summary: dict[str, Any]) -> None:
    if summary.get("schema") != STATUS_SUMMARY_SCHEMA:
        raise ValueError("status_summary_invalid_schema")
    missing = [category for category in STATUS_CATEGORIES if not isinstance(summary.get(category), dict)]
    if missing:
        raise ValueError(f"status_summary_missing_categories:{','.join(missing)}")
    if not summary.get("evidence_layer"):
        raise ValueError("status_summary_missing_evidence_layer")


def evidence_manifest_entry(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return {
        "path": str(resolved),
        "name": resolved.name,
        "type": "file" if resolved.is_file() else "directory",
        "bytes": resolved.stat().st_size if resolved.is_file() else None,
        "sha256": sha256_file(resolved) if resolved.is_file() else None,
    }


def build_release_bundle(
    *,
    output_dir: Path,
    run_id: str,
    evidence_paths: list[Path],
    public_safe_summary: str,
    status: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    assert_public_safe_text(public_safe_summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_entries = [evidence_manifest_entry(path) for path in evidence_paths]
    manifest = {
        "schema": RELEASE_BUNDLE_MANIFEST_SCHEMA,
        "run_id": run_id,
        "generated_at": generated_at or utc_now_iso(),
        "bundle_files": list(RELEASE_BUNDLE_FILES),
        "evidence": evidence_entries,
        "status_summary": status or {},
        "boundary": {
            "evidence_layer_required": True,
            "not_10h_formal_acceptance_unless_long_run_verified": True,
            "not_performance_proof": True,
            "not_investment_advice": True,
            "not_trading_signal": True,
            "alaya_internal_only": True,
        },
    }
    manifest_path = output_dir / "EVIDENCE_MANIFEST.json"
    public_summary_path = output_dir / "PUBLIC_SAFE_SUMMARY.md"
    checksums_path = output_dir / "CHECKSUMS.sha256"
    public_summary_path.write_text(public_safe_summary.rstrip() + "\n", encoding="utf-8")
    write_json(manifest_path, manifest)
    checksum_rows = [
        f"{sha256_file(manifest_path)}  EVIDENCE_MANIFEST.json",
        f"{sha256_file(public_summary_path)}  PUBLIC_SAFE_SUMMARY.md",
    ]
    checksums_path.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    verification = verify_release_bundle(output_dir)
    manifest["checksums_verified"] = verification["ok"]
    write_json(manifest_path, manifest)
    checksum_rows[0] = f"{sha256_file(manifest_path)}  EVIDENCE_MANIFEST.json"
    checksums_path.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    verification = verify_release_bundle(output_dir)
    return {
        "schema": RELEASE_BUNDLE_MANIFEST_SCHEMA,
        "run_id": run_id,
        "output_dir": str(output_dir.resolve()),
        "files": {name: str((output_dir / name).resolve()) for name in RELEASE_BUNDLE_FILES},
        "checksums_verified": verification["ok"],
        "verification": verification,
    }


def verify_release_bundle(bundle_dir: Path) -> dict[str, Any]:
    checksum_file = bundle_dir / "CHECKSUMS.sha256"
    if not checksum_file.exists():
        return {"ok": False, "failures": ["missing_CHECKSUMS.sha256"], "checked": []}
    checked: list[dict[str, Any]] = []
    failures: list[str] = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = bundle_dir / relative.strip()
        if not target.exists():
            failures.append(f"missing:{relative.strip()}")
            continue
        actual = sha256_file(target)
        checked.append({"file": relative.strip(), "expected": expected, "actual": actual, "ok": expected == actual})
        if expected != actual:
            failures.append(f"checksum_mismatch:{relative.strip()}")
    return {"ok": not failures, "failures": failures, "checked": checked}


def rollback_dry_run(
    *,
    static_dir: Path,
    backup_dir: Path,
    required_routes: list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    routes = required_routes or ["/today", "/track-record", "/methodology", "/audit"]
    static_parent = static_dir.parent
    backup_parent = backup_dir.parent
    checks = {
        "static_dir_exists": static_dir.exists() and static_dir.is_dir(),
        "static_parent_writable": os.access(static_parent, os.W_OK),
        "backup_parent_writable": backup_parent.exists() and os.access(backup_parent, os.W_OK),
        "would_backup_current_static": True,
        "would_restore_backup_to_static": True,
        "would_run_smoke_after_restore": True,
        "required_routes": routes,
    }
    ok = bool(checks["static_dir_exists"] and checks["static_parent_writable"] and checks["backup_parent_writable"])
    return {
        "schema": ROLLBACK_DRY_RUN_SCHEMA,
        "generated_at": generated_at or utc_now_iso(),
        "mode": "dry_run",
        "status": "pass" if ok else "blocked",
        "static_dir": str(static_dir.resolve()),
        "backup_dir": str(backup_dir.resolve()),
        "checks": checks,
        "boundary": "rollback dry-run only; no files were restored or deployed",
    }

