from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_8_ksana_comparison_prereg_schema as prereg


def test_valid_ksana_full_gotra_prereg_is_ready(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture())

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_READY
    assert summary["primary_comparison_arms"] == ["full_gotra", "ksana_real_research"]
    assert summary["has_direct_llm_parametric_memory_control_metadata"] is True
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["evidence_layer"] == prereg.EVIDENCE_LAYER


def test_missing_ksana_or_full_gotra_arm_blocks_schema(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["arms"] = [payload["arms"][0]]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_SCHEMA
    assert "required_arms_missing" in summary["blocker_reasons"]


def test_direct_llm_clean_baseline_or_primary_comparator_blocks(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["arms"].append({"arm_id": "direct_llm", "role": "primary_comparator"})
    payload["summary"] = "direct_llm is the clean no-future baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_SCHEMA
    assert "direct_llm_as_primary_or_clean_baseline" in summary["blocker_reasons"]


def test_runtime_flags_missing_or_true_block_runtime_boundary(tmp_path: Path) -> None:
    payload = _valid_fixture(provider_or_backend_called=True)
    payload.pop("formal_lite_entered")
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "missing_formal_lite_entered" in summary["blocker_reasons"]


def test_actual_verdict_executable_true_blocks_runtime(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture(v3_7_actual_verdict_executable=True))

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_short_horizon_status_used_as_30d_readiness_blocks_overclaim(tmp_path: Path) -> None:
    payload = _valid_fixture(readiness_status="short-horizon canary is equivalent to actual 30D v3.7 verdict ready")
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_OVERCLAIM
    assert "short_horizon_or_prep_as_actual_30d_verdict" in summary["blocker_reasons"]


def test_missing_or_wrong_source_hash_or_run_id_blocks_provenance(tmp_path: Path) -> None:
    payload = _valid_fixture()
    payload["arms"][0]["source_summary_sha256"] = "not-a-sha"
    payload["provenance"]["arms"]["ksana_real_research"]["source_run_id"] = "different-run"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_PROVENANCE
    assert "source_summary_sha256_invalid" in summary["blocker_reasons"]
    assert "source_run_id_mismatch" in summary["blocker_reasons"]


def test_forbidden_artifact_path_blocks_without_reading_content(tmp_path: Path, monkeypatch) -> None:
    payload = _valid_fixture()
    payload["arms"][0]["source_artifact_path"] = "data/backtest/runs/raw.json"
    payload["provenance"]["arms"]["ksana_real_research"]["source_artifact_path"] = "data/backtest/runs/raw.json"
    fixture = _write_fixture(tmp_path, payload)
    original_read_text = Path.read_text

    def fail_read(path: Path, *args: object, **kwargs: object) -> str:
        if "data/backtest/runs" in str(path):
            raise AssertionError("forbidden artifact content should not be read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_public_science_trading_winner_claim_blocks_overclaim(tmp_path: Path) -> None:
    payload = _valid_fixture(narrative="This is OOS public science proof and trading advice with a winner claim.")
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture))

    assert summary["validator_status"] == prereg.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_digest_stable_and_changes_for_boundary_fields(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture())
    summary_a = prereg.build_summary(_config(tmp_path / "a", fixture, "baseline_v3_8_ksana_comparison_prereg_schema_a"))
    summary_b = prereg.build_summary(_config(tmp_path / "b", fixture, "baseline_v3_8_ksana_comparison_prereg_schema_b"))
    changed = _valid_fixture(v3_7_actual_verdict_executable=True)
    changed_fixture = _write_fixture(tmp_path / "changed", changed)
    summary_c = prereg.build_summary(_config(tmp_path / "c", changed_fixture, "baseline_v3_8_ksana_comparison_prereg_schema_c"))
    manifest = json.loads(Path(summary_a["manifest_path"]).read_text(encoding="utf-8"))

    assert summary_a["validator_status"] == prereg.STATUS_READY
    assert summary_a["prereg_content_sha256"] == summary_b["prereg_content_sha256"]
    assert summary_a["prereg_content_sha256"] != summary_c["prereg_content_sha256"]
    assert manifest["summary_sha256"] == prereg.sha256_file(Path(summary_a["summary_path"]))


def test_cli_returns_nonzero_for_blockers(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, _valid_fixture(provider_or_backend_called=True))

    status = prereg.main(
        [
            "--validator-run-id",
            "baseline_v3_8_ksana_comparison_prereg_schema_cli_blocked",
            "--fixture",
            str(fixture),
            "--output-dir",
            str(tmp_path / "runs"),
            "--allow-overwrite",
        ]
    )

    assert status == 1


def _valid_fixture(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "comparison_id": "v3_8_ksana_real_research_vs_full_gotra_fixture",
        "prereg_id": "gotra_v3_8_ksana_comparison_fixture_prereg",
        "schema_version": prereg.PREREG_SCHEMA_VERSION,
        "arms": [
            _arm("ksana_real_research", "research_arm"),
            _arm("full_gotra", "comparison_arm"),
            {
                "arm_id": prereg.OPTIONAL_DIRECT_LLM,
                "role": "historical_diagnostic",
                "notes": "metadata only; not a clean baseline",
            },
        ],
        "paired_design": {
            "pairing_keys": ["ticker", "decision_date", "horizon"],
            "future_execution_requires": "READY_FOR_FORWARD_LIVE_VERDICT with matching provenance; not executable in this fixture",
        },
        "provenance": {
            "arms": {
                "ksana_real_research": _provenance("ksana_real_research"),
                "full_gotra": _provenance("full_gotra"),
            }
        },
        "actual_30d_readiness_status": prereg.ACTUAL_30D_READINESS_STATUS,
        "actual_30d_next_check_after": prereg.ACTUAL_30D_NEXT_CHECK_AFTER,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "v3_7_actual_verdict_executable": False,
        "v3_7_actual_verdict_executed": False,
        "direct_llm_interpretation": prereg.DIRECT_LLM_INTERPRETATION,
        "evidence_layer": prereg.EVIDENCE_LAYER,
        "non_claims": "not provider run; not actual comparison verdict; not OOS/science/public/trading claim; not investment advice",
        "summary": "Fixture-only prereg/schema prep. v3_7_actual_verdict_executable=false.",
    }
    payload.update(updates)
    return payload


def _arm(arm_id: str, role: str) -> dict[str, object]:
    return {
        "arm_id": arm_id,
        "role": role,
        "source_run_id": f"{arm_id}_fixture_run",
        "source_artifact_path": f"fixtures/v3_8/{arm_id}.json",
        "source_summary_sha256": "a" * 64 if arm_id == "ksana_real_research" else "b" * 64,
        "source_artifact_sha256": "c" * 64 if arm_id == "ksana_real_research" else "d" * 64,
        "generated_at": "2026-06-22T00:00:00Z",
    }


def _provenance(arm_id: str) -> dict[str, object]:
    return {
        "source_run_id": f"{arm_id}_fixture_run",
        "source_artifact_path": f"fixtures/v3_8/{arm_id}.json",
        "source_summary_sha256": "a" * 64 if arm_id == "ksana_real_research" else "b" * 64,
    }


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "v3_8_ksana_comparison_prereg_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(
    tmp_path: Path,
    fixture: Path,
    run_id: str = "baseline_v3_8_ksana_comparison_prereg_schema_unit",
) -> prereg.PreregConfig:
    return prereg.PreregConfig(
        validator_run_id=run_id,
        output_dir=tmp_path / "runs",
        fixture=fixture,
        allow_overwrite=True,
    )
