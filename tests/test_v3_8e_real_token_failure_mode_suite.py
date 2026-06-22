from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_8e_real_token_failure_mode_suite as suite


def test_controlled_failure_suite_passes_without_real_calls(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))

    assert summary["suite_status"] == suite.STATUS_PASS
    assert summary["total_cases"] >= 10
    assert summary["passed_cases"] == summary["total_cases"]
    assert summary["blocked_cases"] == 0
    assert summary["real_calls_count"] == 0
    assert summary["token_usage_total"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert summary["case_status_counts"][suite.STATUS_PROVIDER_BLOCKED_PRE_HTTP] == 1
    assert summary["case_status_counts"][suite.STATUS_PROVIDER_AUTH_FAILED] == 1
    assert summary["case_status_counts"][suite.STATUS_PROVIDER_TIMEOUT_HANDLED] == 1
    assert summary["case_status_counts"][suite.STATUS_PROVIDER_ERROR_HANDLED] == 1
    assert summary["case_status_counts"][suite.STATUS_BLOCKED_METADATA] == 1


def test_auth_failure_is_redacted_and_no_secret_leaks(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))
    auth_case = _case(summary, "auth_failure_redacted")

    assert auth_case["observed_status"] == suite.STATUS_PROVIDER_AUTH_FAILED
    assert auth_case["secret_redaction_status"] == "clean"
    assert "[REDACTED]" in auth_case["error_message_redacted"]
    assert suite.SECRET_RE.search(json.dumps(summary, sort_keys=True)) is None


def test_timeout_handled_without_retry_storm(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))
    timeout_case = _case(summary, "timeout_no_retry_storm")

    assert timeout_case["observed_status"] == suite.STATUS_PROVIDER_TIMEOUT_HANDLED
    assert timeout_case["retry_count"] <= suite.MAX_RETRY_COUNT
    assert summary["retry_count_total"] <= suite.MAX_RETRY_COUNT


def test_malformed_empty_and_usage_missing_are_handled(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))

    assert _case(summary, "malformed_response")["observed_status"] == suite.STATUS_BLOCKED_SCHEMA
    assert _case(summary, "empty_response")["observed_status"] == suite.STATUS_BLOCKED_SCHEMA
    assert _case(summary, "usage_missing")["observed_status"] == suite.STATUS_BLOCKED_METADATA
    assert summary["suite_status"] == suite.STATUS_PASS


def test_provider_error_payloads_stay_under_tmp(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))
    provider_case = _case(summary, "provider_error")

    assert provider_case["observed_status"] == suite.STATUS_PROVIDER_ERROR_HANDLED
    assert suite.under_tmp(provider_case["raw_tmp_path"])
    assert suite.HEX64_RE.match(provider_case["raw_sha256"])
    assert summary["raw_tmp_paths"]
    assert all(suite.under_tmp(path) for path in summary["raw_tmp_paths"])


def test_output_dir_outside_tmp_does_not_write_summary_or_manifest(tmp_path: Path) -> None:
    output_dir = tmp_path / "outside_tmp_runs"
    run_id = "baseline_v3_8e_real_token_failure_mode_suite_outside_tmp"

    summary = suite.build_summary(
        suite.FailureSuiteConfig(
            failure_suite_run_id=run_id,
            output_dir=output_dir,
            allow_overwrite=True,
        )
    )

    run_root = output_dir / run_id
    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "output_dir_not_tmp" in summary["blocker_reasons"]
    assert not run_root.exists()
    assert not (run_root / "summary.json").exists()
    assert not (run_root / "manifest.json").exists()


def test_raw_path_outside_tmp_is_handled_as_runtime_boundary(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))
    raw_case = _case(summary, "raw_path_outside_tmp")

    assert raw_case["observed_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert raw_case["handled"] is True
    assert raw_case["raw_tmp_path"] == ""
    assert raw_case["metadata"]["unsafe_raw_path_candidate"].startswith("/Users/")


def test_malformed_fixture_token_budget_returns_structured_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["token_budget"] = "not-an-integer"
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "token_budget_invalid" in summary["blocker_reasons"]
    assert Path(summary["summary_path"]).exists()


def test_wrong_fixture_schema_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["schema"] = "gotra.wrong.schema"
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_SCHEMA
    assert "summary_schema_mismatch" in summary["blocker_reasons"]


def test_invalid_or_misaligned_raw_tmp_hashes_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["raw_tmp_sha256s"] = ["not-a-sha"]
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "raw_tmp_sha256s_count_mismatch" in summary["blocker_reasons"]
    assert "raw_tmp_sha256_invalid" in summary["blocker_reasons"]


def test_fixture_identity_mismatch_blocks_and_output_identity_uses_config(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["failure_suite_run_id"] = "baseline_v3_8e_real_token_failure_mode_suite_other"
    payload["run_root"] = "/tmp/other-root"
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "failure_suite_run_id_identity_mismatch" in summary["blocker_reasons"]
    assert "run_root_identity_mismatch" in summary["blocker_reasons"]
    assert summary["failure_suite_run_id"] == "baseline_v3_8e_real_token_failure_mode_suite_unit"
    assert summary["run_root"].startswith("/tmp/gotra_v3_8e_unit_")


def test_over_budget_call_and_retry_fixture_blocks_runtime_boundary(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["real_calls_count"] = suite.HARD_MAX_REAL_CALLS + 1
    payload["retry_count_total"] = suite.MAX_RETRY_COUNT + 1
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "real_calls_count_over_hard_limit" in summary["blocker_reasons"]
    assert "retry_count_over_limit" in summary["blocker_reasons"]


def test_case_call_token_retry_and_provider_totals_must_reconcile(tmp_path: Path) -> None:
    payload = _ready_fixture()
    first = dict(payload["failure_cases"][0])  # type: ignore[index]
    first["call_count"] = 1
    first["token_usage_total"] = 7
    first["retry_count"] = 1
    first["provider_or_backend_called"] = True
    payload["failure_cases"][0] = first  # type: ignore[index]
    payload["real_calls_count"] = 0
    payload["token_usage_total"] = 0
    payload["retry_count_total"] = 0
    payload["provider_or_backend_called"] = False
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "real_calls_count_mismatch" in summary["blocker_reasons"]
    assert "token_usage_total_mismatch" in summary["blocker_reasons"]
    assert "retry_count_total_mismatch" in summary["blocker_reasons"]
    assert "provider_or_backend_called_mismatch" in summary["blocker_reasons"]


def test_case_status_counts_must_match_observed_statuses(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["case_status_counts"] = {suite.STATUS_PASS: 999}
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "case_status_counts_mismatch" in summary["blocker_reasons"]


def test_unsafe_runtime_flags_and_future_data_metadata_block_when_unhandled(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["formal_lite_entered"] = True
    first = dict(payload["failure_cases"][0])  # type: ignore[index]
    first["future_data_violation"] = True
    first["blocker_reasons"] = []
    payload["failure_cases"][0] = first  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "formal_lite_entered_not_false" in summary["blocker_reasons"]
    assert "future_data_violation_unhandled" in summary["blocker_reasons"]


def test_arbitrary_failure_case_metadata_overclaim_blocks(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["failure_cases"][0]["metadata"] = {"notes": "This synthetic case claims public proof."}  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_OVERCLAIM
    assert "oos_science_public_trading_claim" in summary["blocker_reasons"]


def test_overclaim_status_like_wording_blocks_fixture(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["failure_cases"][0]["metadata"] = {  # type: ignore[index]
        "unsafe_status_text": "synthetic case says actual v3.7 verdict ready"
    }
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_OVERCLAIM
    assert "actual_verdict_status_claim" in summary["blocker_reasons"]


def test_old_provider_or_formal_lite_boundaries_block(tmp_path: Path) -> None:
    payload = _ready_fixture()
    payload["backend_name"] = "deepseek_legacy_backend"
    payload["failure_cases"][0]["backend_name"] = "deepseek_legacy_backend"  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    summary = suite.build_summary(_config(tmp_path, summary_fixture=fixture))

    assert summary["suite_status"] == suite.STATUS_BLOCKED_RUNTIME_BOUNDARY
    assert "backend_not_allowed" in summary["blocker_reasons"]


def test_cli_blocked_status_exits_nonzero_for_bad_fixture(tmp_path: Path, capsys) -> None:
    payload = _ready_fixture()
    payload["failure_cases"][0]["handled"] = False  # type: ignore[index]
    fixture = _write_fixture(tmp_path, payload)

    rc = suite.main(
        [
            "--failure-suite-run-id",
            "baseline_v3_8e_real_token_failure_mode_suite_cli_blocked",
            "--output-dir",
            str(tmp_path / "runs"),
            "--summary-fixture",
            str(fixture),
            "--allow-overwrite",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert suite.STATUS_BLOCKED_RUNTIME_BOUNDARY in captured.out


def test_manifest_digest_matches_final_summary(tmp_path: Path) -> None:
    summary = suite.build_summary(_config(tmp_path))
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == suite.sha256_file(Path(summary["summary_path"]))
    assert manifest["suite_status"] == suite.STATUS_PASS


def _case(summary: dict[str, object], case_id: str) -> dict[str, object]:
    for item in summary["failure_cases"]:  # type: ignore[index]
        if isinstance(item, dict) and item.get("case_id") == case_id:
            return item
    raise AssertionError(f"missing case {case_id}")


def _ready_fixture() -> dict[str, object]:
    config = suite.FailureSuiteConfig(
        failure_suite_run_id="baseline_v3_8e_real_token_failure_mode_suite_fixture_source",
        output_dir=Path("/tmp/gotra_v3_8e_fixture_source"),
        allow_overwrite=True,
    )
    summary = suite.build_summary(config)
    return json.loads(json.dumps(summary))


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "summary_fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, summary_fixture: Path | None = None) -> suite.FailureSuiteConfig:
    output_dir = Path("/tmp") / f"gotra_v3_8e_unit_{tmp_path.name}" / "runs"
    return suite.FailureSuiteConfig(
        failure_suite_run_id="baseline_v3_8e_real_token_failure_mode_suite_unit",
        output_dir=output_dir,
        allow_overwrite=True,
        summary_fixture=summary_fixture,
    )
