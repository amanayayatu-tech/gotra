from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_8w_codex_cli_rubric_reasoning_scoring_smoke as smoke


def test_valid_codex_cli_smoke_summary_passes_with_usage_metadata(tmp_path: Path) -> None:
    raw_dir = _raw_dir(tmp_path)
    stream = raw_dir / "stream.jsonl"
    last = raw_dir / "last_message.txt"
    stderr = raw_dir / "stderr.txt"
    stream.write_text(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 8,
                    "total_tokens": 20,
                },
                "model": "codex-cli-test-model",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    last.write_text('{"status":"SMOKE_OK"}\n', encoding="utf-8")
    stderr.write_text("", encoding="utf-8")

    summary = smoke.build_summary(
        _config(tmp_path, stream=stream, last=last, stderr=stderr, latency_ms=1234)
    )

    assert summary["status"] == smoke.STATUS_PASS
    assert summary["run_mode"] == "smoke"
    assert summary["run_scope"] == "minimal_codex_cli_json_smoke"
    assert summary["real_calls_count"] == 1
    assert summary["token_usage_total"] == 20
    assert summary["usage_metadata_available"] is True
    assert summary["latency_summary_ms"]["median"] == 1234
    assert set(summary["raw_tmp_sha256s"]) == {str(stream), str(last), str(stderr)}
    assert summary["repo_raw_artifacts"] == []
    assert summary["actual_30d_readiness_status"] == smoke.ACTUAL_30D_READINESS_STATUS
    assert summary["cognitive_lift_superiority_verdict_status"] == smoke.SUPERIORITY_STATUS
    assert summary["direct_llm_interpretation"] == smoke.DIRECT_INTERPRETATION
    assert summary["direct_llm_clean_baseline"] is False
    assert summary["bounded_batch_executed"] is False
    assert Path(summary["manifest_path"]).exists()


def test_missing_usage_metadata_blocks_expansion(tmp_path: Path) -> None:
    raw_dir = _raw_dir(tmp_path)
    stream = raw_dir / "stream.jsonl"
    last = raw_dir / "last_message.txt"
    stream.write_text(json.dumps({"type": "message", "text": "metadata absent"}) + "\n", encoding="utf-8")
    last.write_text('{"status":"SMOKE_OK"}\n', encoding="utf-8")

    summary = smoke.build_summary(_config(tmp_path, stream=stream, last=last))

    assert summary["status"] == smoke.STATUS_BLOCKED_USAGE_METADATA
    assert summary["usage_metadata_available"] is False
    assert summary["token_usage_total"] == 0
    assert "usage_metadata_unavailable" in summary["blocker_reasons"]
    assert summary["bounded_batch_executed"] is False


def test_synthetic_batch_metadata_is_explicit_and_matches_manifest(tmp_path: Path) -> None:
    raw_dir = _raw_dir(tmp_path)
    stream = raw_dir / "stream.jsonl"
    last = raw_dir / "last_message.txt"
    stream.write_text(json.dumps({"usage": {"total_tokens": 42}}) + "\n", encoding="utf-8")
    last.write_text('{"status":"BATCH_SMOKE_OK"}\n', encoding="utf-8")

    summary = smoke.build_summary(
        _config(
            tmp_path,
            stream=stream,
            last=last,
            run_mode="synthetic_batch",
            run_scope="synthetic/local two-record rubric fixture",
        )
    )
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == smoke.STATUS_PASS
    assert summary["run_mode"] == "synthetic_batch"
    assert summary["run_scope"] == "synthetic/local two-record rubric fixture"
    assert summary["bounded_batch_executed"] is True
    assert "synthetic/local bounded batch" in summary["bounded_batch_reason"]
    assert manifest["run_mode"] == summary["run_mode"]
    assert manifest["run_scope"] == summary["run_scope"]
    assert manifest["bounded_batch_executed"] is True


def test_raw_path_outside_boundary_blocks(tmp_path: Path) -> None:
    raw_dir = tmp_path / "outside"
    raw_dir.mkdir()
    stream = raw_dir / "stream.jsonl"
    last = raw_dir / "last_message.txt"
    stream.write_text(json.dumps({"usage": {"total_tokens": 1}}) + "\n", encoding="utf-8")
    last.write_text('{"status":"SMOKE_OK"}\n', encoding="utf-8")

    summary = smoke.build_summary(_config(tmp_path, stream=stream, last=last))

    assert summary["status"] == smoke.STATUS_BLOCKED_RAW_BOUNDARY
    assert "raw_tmp_path_not_under_boundary" in summary["blocker_reasons"]


def test_observed_cost_over_cap_blocks(tmp_path: Path) -> None:
    raw_dir = _raw_dir(tmp_path)
    stream = raw_dir / "stream.jsonl"
    last = raw_dir / "last_message.txt"
    stream.write_text(
        json.dumps({"usage": {"total_tokens": 10}, "cost_usd": smoke.COST_CAP_USD + 1})
        + "\n",
        encoding="utf-8",
    )
    last.write_text('{"status":"SMOKE_OK"}\n', encoding="utf-8")

    summary = smoke.build_summary(_config(tmp_path, stream=stream, last=last))

    assert summary["status"] == smoke.STATUS_BLOCKED_COST_CAP_EXHAUSTED
    assert "cost_cap_exhausted" in summary["blocker_reasons"]


def test_preserved_boundary_mutation_needs_repair(tmp_path: Path) -> None:
    raw_dir = _raw_dir(tmp_path)
    stream = raw_dir / "stream.jsonl"
    last = raw_dir / "last_message.txt"
    stream.write_text(json.dumps({"usage": {"total_tokens": 10}}) + "\n", encoding="utf-8")
    last.write_text('{"status":"SMOKE_OK"}\n', encoding="utf-8")

    summary = smoke.build_summary(_config(tmp_path, stream=stream, last=last))
    summary["direct_llm_clean_baseline"] = True
    blockers = smoke.validate_summary_payload(summary)

    assert any(item["rule_id"] == "direct_llm_clean_baseline_not_false" for item in blockers)


def _raw_dir(tmp_path: Path) -> Path:
    raw_dir = smoke.RAW_ROOT / "pytest" / tmp_path.name
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def _config(
    tmp_path: Path,
    *,
    stream: Path,
    last: Path,
    stderr: Path | None = None,
    latency_ms: int | None = None,
    run_mode: str = "smoke",
    run_scope: str = "minimal_codex_cli_json_smoke",
) -> smoke.SmokeConfig:
    return smoke.SmokeConfig(
        smoke_id="gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260622T000000Z",
        output_dir=smoke.RAW_ROOT / "pytest_summaries" / tmp_path.name,
        stream_jsonl_path=stream,
        last_message_path=last,
        stderr_path=stderr,
        command="codex exec --json ...",
        latency_ms=latency_ms,
        run_mode=run_mode,
        run_scope=run_scope,
        allow_overwrite=True,
    )
