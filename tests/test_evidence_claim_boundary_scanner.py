from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6ab_evidence_claim_boundary_scanner as scanner


def test_clean_engineering_local_manifest_is_clean(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/good.md",
                "text": (
                    "engineering/local only; historical/internal only; "
                    "not OOS/science/public/trading claim; not investment advice; "
                    "v3_7_allowed=false; direct_llm_parametric_memory_control."
                ),
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_CLEAN
    assert summary["forbidden_path_count"] == 0
    assert summary["evidence_overclaim_count"] == 0
    assert summary["direct_llm_mislabel_count"] == 0
    assert summary["maturity_gate_bypass_count"] == 0
    assert summary["short_horizon_as_30d_count"] == 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_allowed"] is False


def test_negative_boundary_statements_do_not_block(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/non_claims.md",
                "text": (
                    "This is not OOS proof, not science/public proof, "
                    "not trading advice, not investment advice, and "
                    "not a 30D forward-live verdict. "
                    "direct_llm_parametric_memory_control remains diagnostic."
                ),
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_CLEAN


def test_oos_science_public_trading_overclaim_blocks(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/bad.md", "text": "This is an OOS pass and trading advice."}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_OVERCLAIM
    assert summary["evidence_overclaim_count"] >= 1


def test_oos_public_evidence_overclaim_blocks(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/bad.md", "text": "This is OOS evidence and public evidence."}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_OVERCLAIM
    assert summary["evidence_overclaim_count"] >= 1


def test_negation_must_apply_to_matched_boundary_term(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/bad_negation.md", "text": "not engineering/local only; this is an OOS proof"}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_OVERCLAIM
    assert summary["evidence_overclaim_count"] >= 1


def test_direct_llm_without_parametric_memory_control_blocks(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/direct_bad.md", "text": "direct_llm is a clean no-future baseline."}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_DIRECT_LLM
    assert summary["direct_llm_mislabel_count"] >= 1
    assert any(item["rule_id"].startswith("direct_llm") for item in summary["blocked_items"])


def test_direct_llm_negated_clean_baseline_caveat_is_allowed(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/direct_good.md",
                "text": (
                    "direct_llm_parametric_memory_control is not a clean "
                    "no-future baseline."
                ),
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_CLEAN
    assert summary["direct_llm_mislabel_count"] == 0


def test_direct_llm_parametric_memory_control_is_allowed(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/direct_good.md", "text": "direct_llm_parametric_memory_control diagnostic only."}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_CLEAN
    assert summary["direct_llm_mislabel_count"] == 0


def test_direct_llm_boundary_status_field_is_allowed(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/fields.md", "text": "- `direct_llm_boundary_status`"}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_CLEAN
    assert summary["direct_llm_mislabel_count"] == 0


def test_direct_llm_technical_field_does_not_exempt_same_line_claim(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/fields_bad.md", "text": "direct_llm_boundary_status: direct_llm verdict accepted"}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_DIRECT_LLM
    assert summary["direct_llm_mislabel_count"] >= 1


def test_short_horizon_canary_as_30d_verdict_blocks_maturity_gate(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/short_bad.md",
                "text": "SHORT_HORIZON_READY means the 30D verdict is ready and v3.7 allowed.",
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_MATURITY_GATE
    assert summary["short_horizon_as_30d_count"] >= 1


def test_caveats_do_not_mask_maturity_gate_claims(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/v37_bad.md",
                "text": (
                    "direct_llm_parametric_memory_control; 30D forward-live verdict pass\n"
                    "not OOS; v3.7 verdict ready"
                ),
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_bypass_count"] >= 2


def test_30d_verdict_pass_while_readiness_not_ready_blocks(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/v37_bad.md", "text": "30D forward-live verdict pass and v3_7_allowed=true."}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_bypass_count"] >= 1


def test_quoted_v3_7_allowed_true_blocks(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/v37_bad.md", "text": '"v3_7_allowed": true\n\'v3_7_allowed\': true'}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_bypass_count"] == 2


def test_v3_7_verdict_spellings_block(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/v37_bad.md",
                "text": "v3_7 verdict ready\nv3.7 verdict allowed\nv37 verdict pass",
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_bypass_count"] == 3


def test_plain_v3_7_allowed_claim_blocks(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/v37_bad.md", "text": "v3.7 is allowed\nv3.7 pass"}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_MATURITY_GATE
    assert summary["maturity_gate_bypass_count"] == 2


def test_explicit_false_v3_7_allowed_is_clean(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "path": "docs/v37_false.md",
                "text": "v3.7 verdict allowed: false\nv3_7_allowed=false",
            }
        ],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_CLEAN
    assert summary["maturity_gate_bypass_count"] == 0


def test_forbidden_manifest_paths_block_artifact_boundary(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/good.md", "text": "engineering/local only."}],
        changed_files=["data/backtest/runs/raw.json"],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_ARTIFACT
    assert summary["forbidden_path_count"] == 1
    assert summary["blocked_items"][0]["rule_id"] == "forbidden_artifact_path"


def test_absolute_forbidden_file_path_blocks_without_reading(tmp_path: Path) -> None:
    forbidden = tmp_path / "data" / "backtest" / "runs" / "raw.json"

    summary = scanner.run_scan(
        scanner.ScanConfig(
            scan_run_id="baseline_v3_6ab_evidence_claim_boundary_scan_unit",
            output_dir=tmp_path / "runs",
            files=(forbidden,),
        )
    )

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_ARTIFACT
    assert summary["forbidden_path_count"] == 1


def test_forbidden_manifest_path_blocks_without_reading(tmp_path: Path) -> None:
    forbidden = tmp_path / "data" / "backtest" / "runs" / "manifest.json"
    forbidden.parent.mkdir(parents=True)
    forbidden.write_text("not json", encoding="utf-8")

    summary = scanner.run_scan(_config(tmp_path, forbidden))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_ARTIFACT
    assert summary["forbidden_path_count"] == 1
    assert summary["manifest_sha256"] == ""


def test_provider_canary_as_public_claim_blocks_overclaim(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/provider_bad.md", "text": "Provider canary is public proof."}],
    )

    summary = scanner.run_scan(_config(tmp_path, manifest))

    assert summary["overall_status"] == scanner.STATUS_BLOCKED_OVERCLAIM
    assert summary["evidence_overclaim_count"] >= 1


def test_cli_returns_nonzero_for_blocked_scan(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [{"path": "docs/bad.md", "text": "This is science proof."}],
    )

    rc = scanner.main(
        [
            "--scan-run-id",
            "baseline_v3_6ab_evidence_claim_boundary_scan_cli_blocked",
            "--manifest",
            str(manifest),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert rc == 1


def _config(tmp_path: Path, manifest: Path) -> scanner.ScanConfig:
    return scanner.ScanConfig(
        scan_run_id="baseline_v3_6ab_evidence_claim_boundary_scan_unit",
        output_dir=tmp_path / "runs",
        manifest=manifest,
    )


def _write_manifest(
    tmp_path: Path,
    files: list[dict[str, str]],
    changed_files: list[str] | None = None,
) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": "gotra.test.claim_boundary_manifest.v1",
                "files": files,
                "changed_files": changed_files or [file["path"] for file in files],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path
