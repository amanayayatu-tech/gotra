from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

from scripts import baseline_v3_8h_provider_canary_authorization_gate as gate


def test_valid_not_executed_gate_fixture_is_ready(tmp_path: Path) -> None:
    summary = gate.build_summary(_config(tmp_path))

    assert summary["gate_status"] == gate.STATUS_READY
    assert summary["provider_or_backend_called"] is False
    assert summary["provider_canary_executed"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["actual_30d_readiness_status"] == gate.ACTUAL_30D_READINESS_STATUS
    assert summary["next_check_after"] == gate.ACTUAL_30D_NEXT_CHECK_AFTER
    assert summary["evidence_layer"] == gate.EVIDENCE_LAYER


def test_executed_provider_canary_without_authorization_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["observed_provider_canary_executed"] = True
    payload["observed_provider_or_backend_called"] = True
    payload["observed_call_count"] = 1
    payload["observed_token_usage_total"] = 42
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    assert "provider_execution_without_authorization_packet" in summary["blocker_reasons"]


def test_provider_or_backend_called_true_without_authorization_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    payload["runtime_flags"]["provider_or_backend_called"] = True  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    assert "provider_execution_without_authorization_packet" in summary["blocker_reasons"]
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]


def test_legacy_provider_without_explicit_named_authorization_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["observed_backend_family"] = "deep" + "seek_legacy_backend"
    payload["observed_backend"] = "deep" + "seek_legacy_backend"
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    assert "legacy_provider_without_authorization_packet" in summary["blocker_reasons"]


def test_missing_or_over_budget_caps_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload.pop("max_calls")
    payload["max_tokens"] = gate.DEFAULT_MAX_TOKENS + 1
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_SCHEMA
    assert "summary_missing_field" in summary["blocker_reasons"]
    assert "max_tokens_over_cap" in summary["blocker_reasons"]


def test_usage_metadata_missing_for_recorded_call_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["authorization_packet"] = _authorization_packet()
    payload["observed_provider_or_backend_called"] = True
    payload["observed_provider_canary_executed"] = True
    payload["observed_call_count"] = 1
    payload["observed_token_usage_total"] = 42
    payload["observed_calls"] = [
        {
            "call_count": 1,
            "token_usage_total": 42,
            "usage_metadata_available": False,
            "raw_tmp_path": "/tmp/gotra_v3_8h/call.json",
        }
    ]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_METADATA
    assert "usage_metadata_missing" in summary["blocker_reasons"]


def test_raw_path_outside_tmp_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["raw_tmp_paths"] = ["/Users/peachy/Documents/gotra/provider_raw.json"]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "raw_tmp_path_not_tmp" in summary["blocker_reasons"]


def test_committed_forbidden_paths_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["changed_files"] = [
        "data/backtest/" + "runs/provider_canary_raw.json",
        "data/paper_" + "trading/provider_canary.json",
        "." + "env.provider_canary",
    ]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_actual_verdict_executable_or_ready_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["v3_7_actual_verdict_executable"] = True
    payload["runtime_flags"]["v3_7_actual_verdict_executable"] = True  # type: ignore[index]
    payload["notes"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] in {
        gate.STATUS_BLOCKED_RUNTIME_BOUNDARY,
        gate.STATUS_BLOCKED_OVERCLAIM,
    }
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_benchmark_winner_public_trading_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "This provider benchmark has a winner and public science proof with trading advice."
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_direct_llm_mislabel_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "direct_llm is a clean baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_authorized_execution_with_metadata_stays_ready(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["authorization_packet"] = _authorization_packet()
    payload["observed_provider_or_backend_called"] = True
    payload["observed_provider_canary_executed"] = True
    payload["observed_call_count"] = 1
    payload["observed_token_usage_total"] = 42
    payload["observed_calls"] = [
        {
            "call_count": 1,
            "token_usage_total": 42,
            "usage_metadata_available": True,
            "raw_tmp_path": "/tmp/gotra_v3_8h/call.json",
        }
    ]
    fixture = _write_fixture(tmp_path, payload)

    summary = gate.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["gate_status"] == gate.STATUS_READY
    assert summary["authorization_boundary_status"] == "clean"
    assert summary["metadata_status"] == "clean"


def test_output_dir_outside_tmp_does_not_write(tmp_path: Path) -> None:
    output_dir = Path("/var/tmp") / f"gotra_v3_8h_outside_tmp_{tmp_path.name}"
    run_id = "baseline_v3_8h_provider_canary_authorization_gate_outside_tmp"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    summary = gate.build_summary(
        gate.GateConfig(
            gate_run_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["gate_status"] == gate.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["runtime_boundary_status"] == "blocked"
    assert not run_root.exists()


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = gate.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == gate.sha256_file(Path(summary["summary_path"]))
    assert manifest["gate_status"] == gate.STATUS_READY
    assert manifest["provider_or_backend_called"] is False
    assert manifest["provider_canary_executed"] is False


def test_cli_blocked_status_exits_nonzero(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    fixture = _write_fixture(tmp_path, payload)

    rc = gate.main(
        [
            "--gate-run-id",
            "baseline_v3_8h_provider_canary_authorization_gate_cli_blocked",
            "--output-dir",
            str(tmp_path / "runs"),
            "--summary-fixture",
            str(fixture),
            "--allow-overwrite",
        ]
    )

    assert rc == 1


def _authorization_packet() -> dict[str, object]:
    return {
        "user_authorization_present": True,
        "authorization_id": "user_future_canary_authorization_fixture",
        "authorized_at": "2026-06-22T00:00:00Z",
        "provider_family": gate.DEFAULT_BACKEND_FAMILY,
        "backend": gate.DEFAULT_BACKEND_FAMILY,
        "model": gate.DEFAULT_MODEL,
        "max_calls": 1,
        "max_tokens": 1000,
        "raw_tmp_only": True,
        "no_raw_repo": True,
        "usage_metadata_required": True,
    }


def _ready_fixture() -> dict[str, object]:
    config = gate.GateConfig(
        gate_run_id="baseline_v3_8h_provider_canary_authorization_gate_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8h_fixture_source"),
        allow_overwrite=True,
    )
    summary = gate.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("gate_run_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "gate_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, fixture: Path | None = None) -> gate.GateConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8h_unit_{tmp_path.name}" / "runs"
    return gate.GateConfig(
        gate_run_id="baseline_v3_8h_provider_canary_authorization_gate_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        summary_fixture=fixture,
    )
