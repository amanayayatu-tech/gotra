from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

from scripts import baseline_v3_8g_optional_provider_canary_prereg as prereg


def test_valid_prereg_fixture_is_ready(tmp_path: Path) -> None:
    summary = prereg.build_summary(_config(tmp_path))

    assert summary["prereg_status"] == prereg.STATUS_READY
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["actual_30d_readiness_status"] == prereg.ACTUAL_30D_READINESS_STATUS
    assert summary["explicit_user_authorization_required"] is True
    assert summary["next_step_requires_user_authorization"] is True
    assert summary["future_user_authorization_present"] is False
    assert summary["raw_tmp_only"] is True
    assert summary["no_raw_repo"] is True
    assert summary["evidence_layer"] == prereg.EVIDENCE_LAYER


def test_missing_explicit_user_authorization_requirement_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["explicit_user_authorization_required"] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    assert "explicit_user_authorization_required_not_true" in summary["blocker_reasons"]


def test_provider_called_true_blocks_prereg_only_stage(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    payload["runtime_flags"]["provider_or_backend_called"] = True  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "provider_or_backend_called_not_false" in summary["blocker_reasons"]
    assert "runtime_provider_or_backend_called_not_false" in summary["blocker_reasons"]


def test_legacy_provider_without_future_authorization_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["allowed_backend_family"] = "deep" + "seek_legacy_backend"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_AUTHORIZATION_BOUNDARY
    assert "legacy_provider_without_future_user_authorization" in summary["blocker_reasons"]


def test_call_and_token_caps_block_when_missing_or_exceeded(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload.pop("max_calls")
    payload["max_tokens"] = prereg.DEFAULT_MAX_TOKENS + 1
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_SCHEMA
    assert "summary_missing_field" in summary["blocker_reasons"]
    assert "max_tokens_over_cap" in summary["blocker_reasons"]


def test_raw_output_repo_path_or_raw_tmp_false_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["raw_tmp_only"] = False
    payload["artifact_boundary"]["allowed_raw_output_root"] = "/Users/peachy/gotra/raw"  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] in {
        prereg.STATUS_BLOCKED_ARTIFACT_BOUNDARY,
        prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY,
    }
    assert "raw_tmp_only_not_true" in summary["blocker_reasons"]
    assert "raw_output_root_not_tmp" in summary["blocker_reasons"]


def test_30d_gate_fields_must_remain_not_matured_and_not_executable(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["actual_30d_readiness_status"] = "READY_FOR_FORWARD_LIVE_VERDICT"
    payload["v3_7_actual_verdict_executable"] = True
    payload["runtime_flags"]["v3_7_actual_verdict_executable"] = True  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] in {
        prereg.STATUS_BLOCKED_SCHEMA,
        prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY,
        prereg.STATUS_BLOCKED_OVERCLAIM,
    }
    assert "actual_30d_readiness_status_invalid" in summary["blocker_reasons"]
    assert "v3_7_actual_verdict_executable_not_false" in summary["blocker_reasons"]


def test_overclaim_wording_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "This says provider canary executed and public science proof."
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_missing_usage_metadata_requirement_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["usage_metadata_required"] = False
    payload["required_metadata"] = [item for item in payload["required_metadata"] if item != "usage_metadata"]  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] in {prereg.STATUS_BLOCKED_SCHEMA, prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY}
    assert "usage_metadata_required_not_true" in summary["blocker_reasons"]
    assert "required_metadata_mismatch" in summary["blocker_reasons"]


def test_direct_llm_mislabel_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["notes"] = "direct_llm is a clean baseline"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_OVERCLAIM
    assert summary["claim_boundary_status"] == "blocked"


def test_forbidden_artifact_reference_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["artifact_note"] = "data/backtest/" + "runs/provider_raw.json"
    fixture = _write_fixture(tmp_path, payload)

    summary = prereg.build_summary(_config(tmp_path, fixture=fixture))

    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_ARTIFACT_BOUNDARY
    assert "forbidden_artifact_reference" in summary["blocker_reasons"]


def test_output_dir_outside_tmp_does_not_write(tmp_path: Path) -> None:
    output_dir = Path("/var/tmp") / f"gotra_v3_8g_outside_tmp_{tmp_path.name}"
    run_id = "baseline_v3_8g_optional_provider_canary_prereg_outside_tmp"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    summary = prereg.build_summary(
        prereg.PreregConfig(
            prereg_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["prereg_status"] == prereg.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert summary["runtime_boundary_status"] == "blocked"
    assert not run_root.exists()
    assert not (run_root / "summary.json").exists()


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = prereg.build_summary(_config(tmp_path))
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == prereg.sha256_file(Path(summary["summary_path"]))
    assert manifest["prereg_status"] == prereg.STATUS_READY
    assert manifest["provider_or_backend_called"] is False


def test_cli_blocked_status_exits_nonzero(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["provider_or_backend_called"] = True
    fixture = _write_fixture(tmp_path, payload)

    rc = prereg.main(
        [
            "--prereg-id",
            "baseline_v3_8g_optional_provider_canary_prereg_cli_blocked",
            "--output-dir",
            str(tmp_path / "runs"),
            "--prereg-fixture",
            str(fixture),
            "--allow-overwrite",
        ]
    )

    assert rc == 1


def _ready_fixture() -> dict[str, object]:
    config = prereg.PreregConfig(
        prereg_id="baseline_v3_8g_optional_provider_canary_prereg_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8g_fixture_source"),
        allow_overwrite=True,
    )
    summary = prereg.build_summary(config)
    payload = copy.deepcopy(summary)
    for key in ("prereg_id", "run_root", "summary_path", "manifest_path"):
        payload.pop(key, None)
    return payload


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "prereg_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, fixture: Path | None = None) -> prereg.PreregConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8g_unit_{tmp_path.name}" / "runs"
    return prereg.PreregConfig(
        prereg_id="baseline_v3_8g_optional_provider_canary_prereg_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        prereg_fixture=fixture,
    )
