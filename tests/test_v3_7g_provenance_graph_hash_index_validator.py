from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_7g_provenance_graph_hash_index_validator as graph


def test_valid_graph_index_is_ready(tmp_path: Path) -> None:
    fixture = _write_graph_fixture(tmp_path, _valid_graph(tmp_path))

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_READY
    assert summary["node_count"] == 2
    assert summary["edge_count"] == 1
    assert summary["hash_checked_count"] == 2
    assert summary["artifact_boundary_status"] == "clean"
    assert summary["claim_boundary_status"] == "clean"
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["codex_cli_called"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["actual_30d_readiness_status"] == graph.ACTUAL_30D_READINESS_STATUS
    assert summary["evidence_layer"] == graph.EVIDENCE_LAYER


def test_missing_hash_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][0].pop("source_sha256")
    payload["nodes"][0]["provenance"].pop("source_sha256")
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_SCHEMA
    assert "missing_or_invalid_node_hash" in summary["blocker_reasons"]


def test_hash_mismatch_blocks_hash_boundary(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][0]["source_sha256"] = "0" * 64
    payload["nodes"][0]["provenance"]["source_sha256"] = "0" * 64
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_HASH_MISMATCH
    assert "source_sha256_mismatch" in summary["blocker_reasons"]


def test_forbidden_raw_path_blocks_artifact_boundary(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][0]["source_path"] = "data/backtest/runs/raw_summary.json"
    payload["nodes"][0]["provenance"]["source_artifact_path"] = "data/backtest/runs/raw_summary.json"
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_graph_artifact_path" in summary["blocker_reasons"]


def test_invalid_generated_at_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path, generated_at="zzzz")
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_SCHEMA
    assert "generated_at_invalid" in summary["blocker_reasons"]


def test_duplicate_node_id_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][1]["node_id"] = payload["nodes"][0]["node_id"]
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_SCHEMA
    assert "duplicate_node_id" in summary["blocker_reasons"]


def test_cycle_blocks_graph(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["edges"].append(
        {
            "source_node_id": "node:v3_7f_ledger",
            "target_node_id": "node:v3_7e_dashboard",
            "relationship": "derived_from",
            "evidence_layer": graph.EVIDENCE_LAYER,
        }
    )
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_CYCLE
    assert "provenance_graph_cycle" in summary["blocker_reasons"]


def test_unreachable_required_source_blocks_provenance(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["required_source_node_ids"] = ["node:v3_7f_ledger"]
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_PROVENANCE
    assert "required_source_node_unreachable" in summary["blocker_reasons"]


def test_runtime_flags_true_block_boundary(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][0]["provider_or_backend_called"] = True
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_SCHEMA
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]


def test_claim_overreach_blocks_graph(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][0]["statement"] = "This is public science proof and trading advice."
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] > 0


def test_short_horizon_cannot_enable_actual_30d_verdict(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["nodes"][0]["artifact_kind"] = "short_horizon_canary"
    payload["nodes"][0]["v3_7_actual_verdict_executable"] = True
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_BLOCKED_SCHEMA
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_deterministic_graph_digest_and_manifest_are_verifiable(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    fixture = _write_graph_fixture(tmp_path, payload)
    first = graph.build_summary(_config(tmp_path / "first", fixture))
    second = graph.build_summary(_config(tmp_path / "second", fixture))
    manifest = json.loads(Path(first["manifest_path"]).read_text(encoding="utf-8"))

    assert first["validator_status"] == graph.STATUS_READY
    assert first["graph_content_sha256"] == second["graph_content_sha256"]
    assert manifest["summary_sha256"] == graph.sha256_file(Path(first["summary_path"]))
    assert manifest["v3_7_actual_verdict_executable"] is False


def test_data_insufficient_when_graph_has_no_edges(tmp_path: Path) -> None:
    payload = _valid_graph(tmp_path)
    payload["edges"] = []
    fixture = _write_graph_fixture(tmp_path, payload)

    summary = graph.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == graph.STATUS_DATA_INSUFFICIENT


def _valid_graph(tmp_path: Path, **updates: object) -> dict[str, object]:
    dashboard_path = tmp_path / "source_v3_7e_dashboard.json"
    ledger_path = tmp_path / "source_v3_7f_ledger.json"
    dashboard_path.write_text("dashboard fixture evidence\n", encoding="utf-8")
    ledger_path.write_text("ledger fixture evidence\n", encoding="utf-8")
    dashboard_hash = graph.sha256_file(dashboard_path)
    ledger_hash = graph.sha256_file(ledger_path)
    payload: dict[str, object] = {
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "generated_at": "2026-06-22T00:00:00Z",
        "actual_30d_readiness_status": graph.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": graph.ACTUAL_30D_NEXT_CHECK_AFTER,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "codex_cli_called": False,
        "formal_lite_entered": False,
        "direct_llm_interpretation": graph.DIRECT_LLM_INTERPRETATION,
        "evidence_layer": graph.EVIDENCE_LAYER,
        "required_source_node_ids": ["node:v3_7e_dashboard"],
        "nodes": [
            {
                "node_id": "node:v3_7e_dashboard",
                "source_path": dashboard_path.name,
                "source_sha256": dashboard_hash,
                "run_id": "baseline_v3_7e_evidence_dashboard_hardening_unit",
                "generated_at": "2026-06-22T00:00:00Z",
                "evidence_layer": "engineering_internal_evidence_dashboard",
                "artifact_kind": "v3_7e_dashboard_summary",
                "provider_or_backend_called": False,
                "codex_cli_new_call": False,
                "codex_cli_called": False,
                "formal_lite_entered": False,
                "provenance": {
                    "source_run_id": "baseline_v3_7e_evidence_dashboard_hardening_unit",
                    "source_artifact_path": dashboard_path.name,
                    "source_sha256": dashboard_hash,
                },
            },
            {
                "node_id": "node:v3_7f_ledger",
                "source_path": ledger_path.name,
                "source_sha256": ledger_hash,
                "run_id": "baseline_v3_7f_continuous_monitor_ledger_unit",
                "generated_at": "2026-06-22T00:00:00Z",
                "evidence_layer": "engineering_internal_continuous_monitor_ledger",
                "artifact_kind": "v3_7f_monitor_ledger_summary",
                "provider_or_backend_called": False,
                "codex_cli_new_call": False,
                "codex_cli_called": False,
                "formal_lite_entered": False,
                "provenance": {
                    "source_run_id": "baseline_v3_7f_continuous_monitor_ledger_unit",
                    "source_artifact_path": ledger_path.name,
                    "source_sha256": ledger_hash,
                },
            },
        ],
        "edges": [
            {
                "source_node_id": "node:v3_7e_dashboard",
                "target_node_id": "node:v3_7f_ledger",
                "relationship": "derived_from",
                "evidence_layer": graph.EVIDENCE_LAYER,
            }
        ],
    }
    payload.update(updates)
    return payload


def _write_graph_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "graph_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, fixture: Path) -> graph.GraphConfig:
    return graph.GraphConfig(
        graph_run_id="baseline_v3_7g_provenance_graph_hash_index_validator_unit",
        output_dir=tmp_path / "runs",
        graph_fixture=fixture,
        allow_overwrite=True,
    )
