#!/usr/bin/env python3
"""GOTRA v3.7G provenance graph / artifact hash index validator."""

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


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as claim_scan  # noqa: E402


SUMMARY_SCHEMA = "gotra.baseline_v3_7g.provenance_graph_hash_index_summary.v1"
MANIFEST_SCHEMA = "gotra.baseline_v3_7g.provenance_graph_hash_index_manifest.v1"
GRAPH_SCHEMA_VERSION = "gotra.baseline_v3_7g.provenance_graph_hash_index.v1"
RUN_ID_PREFIX = "baseline_v3_7g_provenance_graph_hash_index_validator_"
SCRIPT_VERSION = "v3.7g-20260622"
EVIDENCE_LAYER = "engineering_internal_provenance_graph_hash_index"
ACTUAL_30D_READINESS_STATUS = "DATA_NOT_MATURED"
ACTUAL_30D_NEXT_CHECK_AFTER = "2026-07-21T00:00:00Z"
DIRECT_LLM_INTERPRETATION = claim_scan.DIRECT_LLM_INTERPRETATION

STATUS_READY = "V3_7_PROVENANCE_GRAPH_HASH_INDEX_READY"
STATUS_DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
STATUS_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
STATUS_BLOCKED_PROVENANCE = "BLOCKED_PROVENANCE"
STATUS_BLOCKED_ARTIFACT_BOUNDARY = "BLOCKED_ARTIFACT_BOUNDARY"
STATUS_BLOCKED_HASH_MISMATCH = "BLOCKED_HASH_MISMATCH"
STATUS_BLOCKED_CYCLE = "BLOCKED_CYCLE"
STATUS_BLOCKED_OVERCLAIM = "BLOCKED_OVERCLAIM"
STATUS_BLOCKED_RUN_ID_EXISTS = "PROVENANCE_GRAPH_HASH_INDEX_BLOCKED_RUN_ID_EXISTS"

CLI_SUCCESS_STATUSES = {STATUS_READY}
HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")

ALLOWED_EVIDENCE_LAYERS = {
    EVIDENCE_LAYER,
    "engineering_internal_continuous_monitor_ledger",
    "engineering_internal_evidence_dashboard",
    "engineering_claim_boundary_scan",
    "engineering/local v3.7 fixture-only harness dry-run",
    "engineering/local v3.7 verdict report schema validator",
    "engineering/local v3.7 bootstrap HAC eligibility preflight",
    "engineering/local ksana packet v2 front-half optimization fixture-only",
    "short_horizon_forward_live_canary_engineering",
}

FALSE_RUNTIME_FLAGS = (
    "provider_or_backend_called",
    "codex_cli_new_call",
    "codex_cli_called",
    "formal_lite_entered",
)
FALSE_VERDICT_FLAGS = (
    "v3_7_actual_verdict_executable",
    "v3_7_actual_verdict_executed",
    "actual_30d_verdict_executed",
)
TEXT_SCAN_KEYS = {
    "claim",
    "claims",
    "conclusion",
    "description",
    "known_blockers",
    "narrative",
    "next_safe_actions",
    "non_claims",
    "notes",
    "rationale",
    "reasoning",
    "statement",
    "summary",
    "title",
    "verdict",
    "winner",
}
PATH_KEYS = {
    "artifact_manifest_path",
    "artifact_path",
    "artifact_paths",
    "hash_index_path",
    "input_artifact_path",
    "input_artifact_paths",
    "manifest_path",
    "output_artifact_path",
    "output_artifact_paths",
    "path",
    "paths",
    "raw_artifact_path",
    "source_artifact_path",
    "source_artifact_paths",
    "source_document_path",
    "source_documents",
    "source_path",
    "source_paths",
    "source_summary_path",
    "source_summary_paths",
    "summary_path",
    "transcript_path",
}
STATUS_OVERCLAIM_PATTERNS = (
    (
        "ready_for_forward_live_verdict_status",
        re.compile(r"\bREADY_FOR_FORWARD_LIVE_VERDICT\b", re.IGNORECASE),
    ),
    (
        "actual_verdict_executable_status",
        re.compile(r"\b(actual\s+)?(?:30D\s+)?(?:v3[._-]?7\s+)?verdict\b.{0,50}\b(executable|executed|ready|allowed|pass)\b", re.IGNORECASE),
    ),
)
REQUIRED_NODE_FIELDS = (
    "node_id",
    "source_path",
    "run_id",
    "generated_at",
    "evidence_layer",
    "artifact_kind",
    "provenance",
)
REQUIRED_EDGE_FIELDS = (
    "source_node_id",
    "target_node_id",
    "relationship",
    "evidence_layer",
)


@dataclass(frozen=True)
class GraphConfig:
    graph_run_id: str
    output_dir: Path
    graph_fixture: Path
    allow_overwrite: bool = False


class GraphError(Exception):
    def __init__(self, status: str, rule_id: str, reason: str, path: str = "") -> None:
        super().__init__(reason)
        self.status = status
        self.rule_id = rule_id
        self.reason = reason
        self.path = path


def utc_timestamp_slug(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(now: datetime | None = None) -> str:
    return f"{RUN_ID_PREFIX}{utc_timestamp_slug(now)}"


def validate_run_id(run_id: str) -> None:
    if not run_id.startswith(RUN_ID_PREFIX):
        raise ValueError(f"graph_run_id must start with {RUN_ID_PREFIX!r}")
    if not run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("graph_run_id may contain only letters, numbers, '_' and '-'")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def normalize_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    return claim_scan.normalize_scan_path(path)


def blocker(path: Path | str, rule_id: str, reason: str) -> dict[str, Any]:
    return {"path": normalize_path(path), "rule_id": rule_id, "reason": reason}


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def hash_is_valid(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value.strip()))


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_json_object(path: Path) -> dict[str, Any]:
    if claim_scan.forbidden_path(normalize_path(path)):
        raise GraphError(
            STATUS_BLOCKED_ARTIFACT_BOUNDARY,
            "forbidden_graph_fixture_path",
            "graph fixture path is forbidden",
            str(path),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GraphError(STATUS_BLOCKED_SCHEMA, "graph_fixture_read_error", str(exc), str(path)) from exc
    except json.JSONDecodeError as exc:
        raise GraphError(STATUS_BLOCKED_SCHEMA, "graph_fixture_json_decode_error", str(exc), str(path)) from exc
    if not isinstance(payload, dict):
        raise GraphError(STATUS_BLOCKED_SCHEMA, "graph_fixture_root_not_object", "graph fixture must be a JSON object", str(path))
    return payload


def resolve_source_file(path_value: str, *, fixture_path: Path) -> Path:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate
    fixture_relative = (fixture_path.parent / candidate).resolve()
    if fixture_relative.exists():
        return fixture_relative
    repo_relative = (REPO_ROOT / candidate).resolve()
    if repo_relative.exists():
        return repo_relative
    return fixture_relative


def recursive_sources(value: Any, *, path: str, key_hint: str = "") -> list[claim_scan.ScanSource]:
    sources: list[claim_scan.ScanSource] = []
    if isinstance(value, str):
        if is_claim_scan_key(key_hint) or not key_hint:
            sources.append(claim_scan.ScanSource(path=path, text=value, origin="v3_7g_graph"))
    elif isinstance(value, dict):
        for key, item in sorted(value.items()):
            sources.extend(recursive_sources(item, path=f"{path}.{key}", key_hint=key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            sources.extend(recursive_sources(item, path=f"{path}[{index}]", key_hint=key_hint))
    return sources


def is_claim_scan_key(key: str) -> bool:
    return (
        key in TEXT_SCAN_KEYS
        or key.endswith("_status")
        or key
        in {
            "actual_30d_readiness_status",
            "readiness_status",
            "status",
            "verdict_status",
            "v3_7_actual_verdict_status",
        }
    )


def recursive_paths(value: Any, *, key_hint: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, str) and key_hint in PATH_KEYS:
        paths.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(recursive_paths(item, key_hint=key))
    elif isinstance(value, list):
        for item in value:
            paths.extend(recursive_paths(item, key_hint=key_hint))
    return paths


def claim_blockers(payload: dict[str, Any], *, path: Path) -> list[dict[str, Any]]:
    scan = claim_scan.scan_sources(recursive_sources(payload, path=normalize_path(path)))
    return (
        scan["overclaim"]
        + scan["direct_llm"]
        + scan["maturity_gate"]
        + scan["short_horizon_as_30d"]
        + status_text_blockers(payload, path=normalize_path(path))
    )


def status_text_blockers(value: Any, *, path: str, key_hint: str = "") -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if isinstance(value, str):
        if is_claim_scan_key(key_hint):
            for rule_id, pattern in STATUS_OVERCLAIM_PATTERNS:
                if pattern.search(value):
                    blockers.append(
                        {
                            "path": path,
                            "line_number": 0,
                            "rule_id": rule_id,
                            "reason": "status-like field cannot assert readiness or actual verdict execution",
                        }
                    )
    elif isinstance(value, dict):
        for key, item in value.items():
            blockers.extend(status_text_blockers(item, path=f"{path}.{key}", key_hint=key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            blockers.extend(status_text_blockers(item, path=f"{path}[{index}]", key_hint=key_hint))
    return blockers


def path_blockers(payload: dict[str, Any], *, path: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if claim_scan.forbidden_path(normalize_path(path)):
        blockers.append(blocker(path, "forbidden_graph_fixture_path", "graph fixture path is forbidden"))
    for candidate in recursive_paths(payload):
        if claim_scan.forbidden_path(candidate):
            blockers.append(blocker(candidate, "forbidden_graph_artifact_path", "graph references a forbidden artifact path"))
    return blockers


def runtime_and_verdict_flag_blockers(value: Any, *, path: str = "$") -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key in FALSE_RUNTIME_FLAGS and item is not False:
                blockers.append(blocker(item_path, f"{key}_not_false", f"{key} must be false"))
            if key in FALSE_VERDICT_FLAGS and item is not False:
                blockers.append(blocker(item_path, f"{key}_not_false", f"{key} must be false"))
            blockers.extend(runtime_and_verdict_flag_blockers(item, path=item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            blockers.extend(runtime_and_verdict_flag_blockers(item, path=f"{path}[{index}]"))
    return blockers


def required_false_flag_blockers(value: dict[str, Any], *, path: Path | str, required_flags: tuple[str, ...]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for flag in required_flags:
        if flag not in value:
            blockers.append(blocker(path, f"missing_{flag}", f"{flag} must be explicitly present and false"))
        elif value.get(flag) is not False:
            blockers.append(blocker(path, f"{flag}_not_false", f"{flag} must be false"))
    return blockers


def validate_root(payload: dict[str, Any], *, path: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blockers.extend(required_false_flag_blockers(payload, path=path, required_flags=FALSE_RUNTIME_FLAGS + FALSE_VERDICT_FLAGS))
    if payload.get("graph_schema_version") != GRAPH_SCHEMA_VERSION:
        blockers.append(blocker(path, "graph_schema_version_mismatch", f"graph_schema_version must be {GRAPH_SCHEMA_VERSION}"))
    if parse_generated_at(payload.get("generated_at")) is None:
        blockers.append(blocker(path, "generated_at_invalid", "generated_at must be an ISO timestamp"))
    if payload.get("evidence_layer") != EVIDENCE_LAYER:
        blockers.append(blocker(path, "evidence_layer_mismatch", f"evidence_layer must be {EVIDENCE_LAYER}"))
    if payload.get("actual_30d_readiness_status") != ACTUAL_30D_READINESS_STATUS:
        blockers.append(blocker(path, "actual_30d_readiness_status_not_data_not_matured", "actual 30D readiness must remain DATA_NOT_MATURED"))
    if payload.get("actual_30d_next_check_after") != ACTUAL_30D_NEXT_CHECK_AFTER:
        blockers.append(blocker(path, "actual_30d_next_check_after_mismatch", "actual 30D next_check_after must match the maturity gate"))
    if payload.get("direct_llm_interpretation") != DIRECT_LLM_INTERPRETATION:
        blockers.append(blocker(path, "direct_llm_interpretation_mismatch", "direct_llm_interpretation must be direct_llm_parametric_memory_control"))
    if not isinstance(payload.get("nodes"), list):
        blockers.append(blocker(path, "nodes_not_list", "nodes must be a list"))
    if not isinstance(payload.get("edges"), list):
        blockers.append(blocker(path, "edges_not_list", "edges must be a list"))
    if "required_source_node_ids" in payload:
        required = payload.get("required_source_node_ids")
        if not isinstance(required, list) or not all(is_non_empty_string(item) for item in required):
            blockers.append(blocker(path, "required_source_node_ids_invalid", "required_source_node_ids must be a list of non-empty strings"))
    return blockers


def validate_node(
    node: Any,
    *,
    index: int,
    fixture_path: Path,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    schema_blockers: list[dict[str, Any]] = []
    provenance_blockers: list[dict[str, Any]] = []
    hash_blockers: list[dict[str, Any]] = []
    path = f"{fixture_path}#nodes[{index}]"
    if not isinstance(node, dict):
        schema_blockers.append(blocker(path, "node_not_object", "node entry must be an object"))
        return None, schema_blockers, provenance_blockers, hash_blockers

    for key in REQUIRED_NODE_FIELDS:
        if key == "provenance":
            if not isinstance(node.get(key), dict):
                provenance_blockers.append(blocker(path, "missing_provenance", "node provenance must be an object"))
        elif not is_non_empty_string(node.get(key)):
            schema_blockers.append(blocker(path, f"missing_{key}", f"{key} is required"))
    if parse_generated_at(node.get("generated_at")) is None:
        schema_blockers.append(blocker(path, "node_generated_at_invalid", "node generated_at must be an ISO timestamp"))

    node_hash_value = node.get("source_sha256") or node.get("summary_sha256")
    hash_key = "source_sha256" if node.get("source_sha256") else "summary_sha256"
    if not hash_is_valid(node_hash_value):
        schema_blockers.append(blocker(path, "missing_or_invalid_node_hash", "node must include a valid source_sha256 or summary_sha256"))

    evidence_layer = node.get("evidence_layer")
    if evidence_layer not in ALLOWED_EVIDENCE_LAYERS:
        schema_blockers.append(blocker(path, "node_evidence_layer_not_allowed", "node evidence_layer is not allowed for v3.7G graph validation"))

    provenance = node.get("provenance") if isinstance(node.get("provenance"), dict) else {}
    schema_blockers.extend(required_false_flag_blockers(node, path=path, required_flags=FALSE_RUNTIME_FLAGS + FALSE_VERDICT_FLAGS))
    if provenance:
        provenance_blockers.extend(required_false_flag_blockers(provenance, path=f"{path}.provenance", required_flags=FALSE_RUNTIME_FLAGS + FALSE_VERDICT_FLAGS))
        if not is_non_empty_string(provenance.get("source_run_id")):
            provenance_blockers.append(blocker(path, "missing_provenance_source_run_id", "provenance.source_run_id is required"))
        if not is_non_empty_string(provenance.get("source_artifact_path")):
            provenance_blockers.append(blocker(path, "missing_provenance_source_artifact_path", "provenance.source_artifact_path is required"))
        provenance_hash = provenance.get("source_sha256") or provenance.get("summary_sha256")
        if not hash_is_valid(provenance_hash):
            provenance_blockers.append(blocker(path, "missing_provenance_hash", "provenance must include a valid source_sha256 or summary_sha256"))
        if is_non_empty_string(node.get("run_id")) and provenance.get("source_run_id") != node.get("run_id"):
            provenance_blockers.append(blocker(path, "node_run_id_provenance_mismatch", "node run_id must match provenance.source_run_id"))
        if node_hash_value and provenance_hash and str(node_hash_value).lower() != str(provenance_hash).lower():
            provenance_blockers.append(blocker(path, "node_hash_provenance_hash_mismatch", "node hash must match provenance hash"))
        if is_non_empty_string(node.get("source_path")) and provenance.get("source_artifact_path") != node.get("source_path"):
            provenance_blockers.append(blocker(path, "node_source_path_provenance_mismatch", "node source_path must match provenance.source_artifact_path"))

    source_path_forbidden = bool(is_non_empty_string(node.get("source_path")) and claim_scan.forbidden_path(str(node.get("source_path"))))
    provenance_path_forbidden = bool(
        is_non_empty_string(provenance.get("source_artifact_path"))
        and claim_scan.forbidden_path(str(provenance.get("source_artifact_path")))
    )
    if (
        is_non_empty_string(node.get("source_path"))
        and hash_is_valid(node_hash_value)
        and not source_path_forbidden
        and not provenance_path_forbidden
    ):
        source_file = resolve_source_file(str(node["source_path"]), fixture_path=fixture_path)
        if not source_file.exists() or not source_file.is_file():
            provenance_blockers.append(blocker(path, "source_path_not_readable", "node source_path must point to a readable file for hash validation"))
        else:
            actual_hash = sha256_file(source_file)
            if actual_hash.lower() != str(node_hash_value).lower():
                hash_blockers.append(
                    blocker(path, f"{hash_key}_mismatch", "node hash does not match source_path final bytes")
                )

    if schema_blockers or provenance_blockers or hash_blockers:
        return None, schema_blockers, provenance_blockers, hash_blockers

    return dict(node), [], [], []


def validate_edge(edge: Any, *, index: int, fixture_path: Path, node_ids: set[str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    schema_blockers: list[dict[str, Any]] = []
    provenance_blockers: list[dict[str, Any]] = []
    path = f"{fixture_path}#edges[{index}]"
    if not isinstance(edge, dict):
        schema_blockers.append(blocker(path, "edge_not_object", "edge entry must be an object"))
        return None, schema_blockers, provenance_blockers
    for key in REQUIRED_EDGE_FIELDS:
        if not is_non_empty_string(edge.get(key)):
            schema_blockers.append(blocker(path, f"missing_{key}", f"{key} is required"))
    if edge.get("evidence_layer") not in ALLOWED_EVIDENCE_LAYERS:
        schema_blockers.append(blocker(path, "edge_evidence_layer_not_allowed", "edge evidence_layer is not allowed for v3.7G graph validation"))
    if is_non_empty_string(edge.get("source_node_id")) and edge.get("source_node_id") not in node_ids:
        provenance_blockers.append(blocker(path, "edge_source_node_missing", "edge source_node_id must reference an existing node"))
    if is_non_empty_string(edge.get("target_node_id")) and edge.get("target_node_id") not in node_ids:
        provenance_blockers.append(blocker(path, "edge_target_node_missing", "edge target_node_id must reference an existing node"))
    if schema_blockers or provenance_blockers:
        return None, schema_blockers, provenance_blockers
    return dict(edge), [], []


def duplicate_node_blockers(nodes: list[Any], *, fixture_path: Path) -> list[dict[str, Any]]:
    seen: set[str] = set()
    blockers: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not is_non_empty_string(node.get("node_id")):
            continue
        node_id = str(node["node_id"])
        if node_id in seen:
            blockers.append(blocker(f"{fixture_path}#nodes[{index}]", "duplicate_node_id", "node_id must be unique"))
        seen.add(node_id)
    return blockers


def cycle_blockers(edges: list[dict[str, Any]], *, fixture_path: Path) -> list[dict[str, Any]]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(str(edge["source_node_id"]), []).append(str(edge["target_node_id"]))

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, stack: list[str]) -> list[str] | None:
        if node_id in visiting:
            start = stack.index(node_id) if node_id in stack else 0
            return stack[start:] + [node_id]
        if node_id in visited:
            return None
        visiting.add(node_id)
        stack.append(node_id)
        for child in adjacency.get(node_id, []):
            cycle = visit(child, stack)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node_id)
        visited.add(node_id)
        return None

    for node_id in sorted(adjacency):
        cycle = visit(node_id, [])
        if cycle:
            return [blocker(fixture_path, "provenance_graph_cycle", f"provenance graph contains a cycle: {' -> '.join(cycle)}")]
    return []


def unreachable_source_blockers(
    payload: dict[str, Any],
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    fixture_path: Path,
) -> list[dict[str, Any]]:
    required = payload.get("required_source_node_ids")
    if not isinstance(required, list):
        return []
    node_ids = {str(node["node_id"]) for node in nodes}
    adjacency: dict[str, list[str]] = {}
    outdegree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        source = str(edge["source_node_id"])
        target = str(edge["target_node_id"])
        adjacency.setdefault(source, []).append(target)
        outdegree[source] = outdegree.get(source, 0) + 1
        outdegree.setdefault(target, 0)
    terminal_nodes = {node_id for node_id, degree in outdegree.items() if degree == 0}
    blockers: list[dict[str, Any]] = []
    for source_id in required:
        if not is_non_empty_string(source_id) or source_id not in node_ids:
            blockers.append(blocker(fixture_path, "required_source_node_missing", "required source node must exist"))
            continue
        seen: set[str] = set()
        stack = [str(source_id)]
        reachable_terminal = False
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in terminal_nodes and current != source_id:
                reachable_terminal = True
                break
            stack.extend(adjacency.get(current, []))
        if not reachable_terminal:
            blockers.append(blocker(fixture_path, "required_source_node_unreachable", "required source node must reach a terminal derived node"))
    return blockers


def choose_status(
    *,
    data_insufficient: bool,
    schema_blockers: list[dict[str, Any]],
    provenance_blockers: list[dict[str, Any]],
    artifact_blockers: list[dict[str, Any]],
    hash_blockers: list[dict[str, Any]],
    cycle_blockers_: list[dict[str, Any]],
    overclaim_blockers: list[dict[str, Any]],
) -> str:
    if artifact_blockers:
        return STATUS_BLOCKED_ARTIFACT_BOUNDARY
    if hash_blockers:
        return STATUS_BLOCKED_HASH_MISMATCH
    if cycle_blockers_:
        return STATUS_BLOCKED_CYCLE
    if overclaim_blockers:
        return STATUS_BLOCKED_OVERCLAIM
    if schema_blockers:
        return STATUS_BLOCKED_SCHEMA
    if provenance_blockers:
        return STATUS_BLOCKED_PROVENANCE
    if data_insufficient:
        return STATUS_DATA_INSUFFICIENT
    return STATUS_READY


def base_summary(*, config: GraphConfig, run_root: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "graph_run_id": config.graph_run_id,
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "manifest_path": str(run_root / "manifest.json"),
        "summary_digest_target": "manifest.summary_sha256",
        "validator_status": status,
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "graph_fixture": str(config.graph_fixture),
        "graph_generated_at": "",
        "graph_content_sha256": "",
        "node_count": 0,
        "edge_count": 0,
        "required_source_node_count": 0,
        "reachable_required_source_count": 0,
        "hash_checked_count": 0,
        "hash_mismatch_count": 0,
        "missing_hash_count": 0,
        "duplicate_node_id_count": 0,
        "cycle_count": 0,
        "unreachable_source_count": 0,
        "forbidden_path_count": 0,
        "provenance_blocker_count": 0,
        "schema_blocker_count": 0,
        "overclaim_blocker_count": 0,
        "runtime_flag_blocker_count": 0,
        "artifact_boundary_status": "clean",
        "hash_boundary_status": "clean",
        "provenance_boundary_status": "clean",
        "schema_boundary_status": "clean",
        "claim_boundary_status": "clean",
        "cycle_boundary_status": "clean",
        "blocker_reasons": [],
        "blocked_items": [],
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "actual_30d_readiness_status": ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "actual_30d_verdict_executed": False,
        "direct_llm_interpretation": DIRECT_LLM_INTERPRETATION,
        "evidence_layer": EVIDENCE_LAYER,
        "non_claims": {
            "not_actual_30d_verdict": True,
            "not_oos_science_public_proof": True,
            "not_trading_or_investment_advice": True,
            "not_provider_run": True,
        },
    }


def build_summary(config: GraphConfig) -> dict[str, Any]:
    validate_run_id(config.graph_run_id)
    run_root = config.output_dir / config.graph_run_id
    if run_root.exists() and any(run_root.iterdir()) and not config.allow_overwrite:
        summary = base_summary(config=config, run_root=run_root, status=STATUS_BLOCKED_RUN_ID_EXISTS)
        summary["schema_boundary_status"] = "blocked"
        summary["schema_blocker_count"] = 1
        summary["blocker_reasons"] = ["output_run_id_exists"]
        return summary
    if run_root.exists() and config.allow_overwrite:
        shutil.rmtree(run_root)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    schema_blockers: list[dict[str, Any]] = []
    provenance_blockers: list[dict[str, Any]] = []
    artifact_blockers: list[dict[str, Any]] = []
    hash_blockers: list[dict[str, Any]] = []
    cycle_blockers_: list[dict[str, Any]] = []
    overclaim_blockers: list[dict[str, Any]] = []
    runtime_blockers: list[dict[str, Any]] = []
    graph_content_sha256 = ""
    graph_generated_at = ""
    required_source_count = 0
    reachable_required_source_count = 0
    hash_checked_count = 0

    try:
        payload = load_json_object(config.graph_fixture)
        graph_generated_at = str(payload.get("generated_at") or "")
        artifact_blockers = path_blockers(payload, path=config.graph_fixture)
        schema_blockers.extend(validate_root(payload, path=config.graph_fixture))
        runtime_blockers = runtime_and_verdict_flag_blockers(payload)
        schema_blockers.extend(runtime_blockers)
        if not artifact_blockers:
            overclaim_blockers = claim_blockers(payload, path=config.graph_fixture)

        raw_nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
        raw_edges = payload.get("edges") if isinstance(payload.get("edges"), list) else []
        schema_blockers.extend(duplicate_node_blockers(raw_nodes, fixture_path=config.graph_fixture))

        for index, node in enumerate(raw_nodes):
            validated, node_schema, node_provenance, node_hash = validate_node(node, index=index, fixture_path=config.graph_fixture)
            schema_blockers.extend(node_schema)
            provenance_blockers.extend(node_provenance)
            hash_blockers.extend(node_hash)
            if isinstance(node, dict) and (node.get("source_sha256") or node.get("summary_sha256")):
                if hash_is_valid(node.get("source_sha256") or node.get("summary_sha256")):
                    hash_checked_count += 1
            if validated:
                nodes.append(validated)

        node_ids = {str(node["node_id"]) for node in nodes}
        for index, edge in enumerate(raw_edges):
            validated, edge_schema, edge_provenance = validate_edge(edge, index=index, fixture_path=config.graph_fixture, node_ids=node_ids)
            schema_blockers.extend(edge_schema)
            provenance_blockers.extend(edge_provenance)
            if validated:
                edges.append(validated)

        if nodes and edges:
            cycle_blockers_ = cycle_blockers(edges, fixture_path=config.graph_fixture)
            required_source_count = len(payload.get("required_source_node_ids", [])) if isinstance(payload.get("required_source_node_ids"), list) else 0
            unreachable = unreachable_source_blockers(payload, nodes=nodes, edges=edges, fixture_path=config.graph_fixture)
            provenance_blockers.extend(unreachable)
            reachable_required_source_count = max(0, required_source_count - len(unreachable))
        graph_content_sha256 = stable_sha256_json(payload)
    except GraphError as exc:
        if exc.status == STATUS_BLOCKED_ARTIFACT_BOUNDARY:
            artifact_blockers = [blocker(exc.path or config.graph_fixture, exc.rule_id, exc.reason)]
        elif exc.status == STATUS_BLOCKED_PROVENANCE:
            provenance_blockers = [blocker(exc.path or config.graph_fixture, exc.rule_id, exc.reason)]
        else:
            schema_blockers = [blocker(exc.path or config.graph_fixture, exc.rule_id, exc.reason)]

    data_insufficient = not nodes or not edges
    status = choose_status(
        data_insufficient=data_insufficient,
        schema_blockers=schema_blockers,
        provenance_blockers=provenance_blockers,
        artifact_blockers=artifact_blockers,
        hash_blockers=hash_blockers,
        cycle_blockers_=cycle_blockers_,
        overclaim_blockers=overclaim_blockers,
    )
    summary = base_summary(config=config, run_root=run_root, status=status)
    blocked_items = artifact_blockers + hash_blockers + cycle_blockers_ + overclaim_blockers + provenance_blockers + schema_blockers
    summary.update(
        {
            "validator_status": status,
            "graph_generated_at": graph_generated_at,
            "graph_content_sha256": graph_content_sha256,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "required_source_node_count": required_source_count,
            "reachable_required_source_count": reachable_required_source_count,
            "hash_checked_count": hash_checked_count,
            "hash_mismatch_count": len(hash_blockers),
            "missing_hash_count": sum(1 for item in schema_blockers if item["rule_id"] == "missing_or_invalid_node_hash"),
            "duplicate_node_id_count": sum(1 for item in schema_blockers if item["rule_id"] == "duplicate_node_id"),
            "cycle_count": len(cycle_blockers_),
            "unreachable_source_count": sum(1 for item in provenance_blockers if item["rule_id"] == "required_source_node_unreachable"),
            "forbidden_path_count": len(artifact_blockers),
            "provenance_blocker_count": len(provenance_blockers),
            "schema_blocker_count": len(schema_blockers),
            "overclaim_blocker_count": len(overclaim_blockers),
            "runtime_flag_blocker_count": len(runtime_blockers),
            "artifact_boundary_status": "blocked" if artifact_blockers else "clean",
            "hash_boundary_status": "blocked" if hash_blockers else "clean",
            "provenance_boundary_status": "blocked" if provenance_blockers else "clean",
            "schema_boundary_status": "blocked" if schema_blockers else "clean",
            "claim_boundary_status": "blocked" if overclaim_blockers else "clean",
            "cycle_boundary_status": "blocked" if cycle_blockers_ else "clean",
            "blocker_reasons": [str(item["rule_id"]) for item in blocked_items],
            "blocked_items": blocked_items[:50],
        }
    )
    if status != STATUS_BLOCKED_RUN_ID_EXISTS:
        write_outputs(config, summary, run_root=run_root)
    return summary


def write_outputs(config: GraphConfig, summary: dict[str, Any], *, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    manifest_path = run_root / "manifest.json"
    summary["summary_path"] = str(summary_path)
    summary["manifest_path"] = str(manifest_path)
    summary["summary_digest_target"] = "manifest.summary_sha256"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "graph_run_id": config.graph_run_id,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_digest_target": "summary.json final payload",
        "graph_fixture": str(config.graph_fixture),
        "validator_status": summary.get("validator_status"),
        "graph_content_sha256": summary.get("graph_content_sha256"),
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-run-id", default=default_run_id())
    parser.add_argument("--graph-fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/gotra_v3_7g_provenance_graph_hash_index/runs"))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> GraphConfig:
    return GraphConfig(
        graph_run_id=str(args.graph_run_id),
        output_dir=args.output_dir,
        graph_fixture=args.graph_fixture,
        allow_overwrite=bool(args.allow_overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        summary = build_summary(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - CLI should fail closed with a redacted error.
        print(f"provenance graph hash index validator failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("validator_status") in CLI_SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
