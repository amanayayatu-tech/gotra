from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_v3_6ai_ksana_cognitive_lift_audit as audit


def test_conservative_generic_report_is_low_information_gain(tmp_path: Path) -> None:
    artifact = _artifact(
        hypotheses=[
            {
                "rank": 1,
                "confidence": 0.4,
                "why_it_matters": "Risk remains and uncertainty remains.",
                "falsification_triggers": [],
                "expected_observable_evidence": [],
            }
        ],
        counterfactuals=[],
        disagreement_with_price_only=[],
        evidence_gaps=["limited information"],
        uncertainty_decomposition={"unknown": 1.0},
        summary="This is not investment advice. It could be uncertain and may have risk.",
    )
    summary = audit.run_audit(_config(tmp_path, [artifact]))

    assert summary["overall_status"] == audit.STATUS_LOW_INFORMATION_GAIN
    assert summary["generic_caution_phrase_count"] >= 3
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_allowed"] is False


def test_forced_hypothesis_counterfactual_schema_fixture_is_ready(tmp_path: Path) -> None:
    summary = audit.run_audit(_config(tmp_path, [_artifact()]))

    assert summary["overall_status"] == audit.STATUS_READY
    assert summary["information_gain_status"] == "SUFFICIENT_FOR_FIXTURE_COMPARISON"
    assert summary["hypothesis_count"] == 2
    assert summary["ranked_hypothesis_count"] == 2
    assert summary["counterfactual_count"] >= 2
    assert summary["falsifiable_trigger_count"] >= 2
    assert summary["explicit_disagreement_count"] == 1
    assert summary["price_only_disagreement_signal"] is True
    assert summary["provenance_link_count"] == 1
    assert summary["non_claims"]["not_30d_forward_live_verdict"] is True


def test_missing_provenance_blocks(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("provenance")

    summary = audit.run_audit(_config(tmp_path, [artifact]))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_PROVENANCE
    assert any(item["rule_id"] == "missing_provenance" for item in summary["blocked_items"])


def test_missing_required_schema_field_blocks(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("hypotheses")

    summary = audit.run_audit(_config(tmp_path, [artifact]))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_SCHEMA
    assert any(
        item["rule_id"] == "missing_or_invalid_required_schema_field"
        for item in summary["blocked_items"]
    )


def test_overclaim_wording_blocks(tmp_path: Path) -> None:
    artifact = _artifact(summary="This internal packet is OOS evidence and trading advice.")

    summary = audit.run_audit(_config(tmp_path, [artifact]))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_OVERCLAIM
    assert any(item["rule_id"] == "oos_science_public_trading_claim" for item in summary["blocked_items"])


def test_direct_llm_clean_baseline_wording_blocks(tmp_path: Path) -> None:
    artifact = _artifact(summary="direct_llm is a clean no-future baseline.")

    summary = audit.run_audit(_config(tmp_path, [artifact]))

    assert summary["overall_status"] == audit.STATUS_BLOCKED_OVERCLAIM
    assert any(
        item["rule_id"] == "direct_llm_clean_no_future_baseline"
        for item in summary["blocked_items"]
    )


def test_direct_llm_parametric_boundary_is_accepted(tmp_path: Path) -> None:
    artifact = _artifact(
        summary="direct_llm_parametric_memory_control is not a clean no-future baseline."
    )

    summary = audit.run_audit(_config(tmp_path, [artifact]))

    assert summary["overall_status"] == audit.STATUS_READY
    assert summary["direct_llm_interpretation"] == audit.DIRECT_LLM_INTERPRETATION


def test_empty_manifest_is_data_insufficient(tmp_path: Path) -> None:
    summary = audit.run_audit(_config(tmp_path, []))

    assert summary["overall_status"] == audit.STATUS_DATA_INSUFFICIENT
    assert summary["input_artifact_count"] == 0


def test_ready_status_is_fixture_comparison_only(tmp_path: Path) -> None:
    summary = audit.run_audit(_config(tmp_path, [_artifact()]))

    assert summary["overall_status"] == audit.STATUS_READY
    assert summary["cognitive_lift_status"] == audit.STATUS_READY
    assert summary["evidence_layer"] == audit.EVIDENCE_LAYER
    assert summary["v3_7_allowed"] is False
    assert "winner" not in summary
    assert "verdict" not in summary


def _config(tmp_path: Path, artifacts: list[dict[str, object]]) -> audit.AuditConfig:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": f"tests/fixtures/audit_{index}.json",
                        "payload": artifact,
                    }
                    for index, artifact in enumerate(artifacts)
                ]
            }
        ),
        encoding="utf-8",
    )
    return audit.AuditConfig(
        audit_run_id=f"{audit.RUN_ID_PREFIX}test_{len(artifacts)}_{len(list(tmp_path.iterdir()))}",
        output_dir=tmp_path / "runs",
        manifest=manifest,
    )


def _artifact(
    *,
    hypotheses: list[dict[str, object]] | None = None,
    counterfactuals: list[str] | None = None,
    disagreement_with_price_only: list[str] | None = None,
    evidence_gaps: list[str] | None = None,
    uncertainty_decomposition: dict[str, float] | None = None,
    summary: str = "Fixture packet with explicit cognitive-lift structure.",
) -> dict[str, object]:
    if hypotheses is None:
        hypotheses = [
            {
                "rank": 1,
                "confidence": 0.68,
                "why_it_matters": "Margin recovery would alter the base-rate interpretation.",
                "falsification_triggers": ["next filing margin below threshold"],
                "expected_observable_evidence": ["gross margin update"],
                "counterfactuals": ["if margins compress, neutralize the hypothesis"],
            },
            {
                "rank": 2,
                "confidence": 0.52,
                "why_it_matters": "Demand mix could contradict price-only momentum.",
                "falsification_triggers": ["channel inventory rises"],
                "expected_observable_evidence": ["inventory commentary"],
            },
        ]
    source_path = "fixtures/ksana/aapl_packet.json"
    return {
        "schema": "gotra.v3_6ai.ksana_cognitive_lift_packet.v1",
        "source_run_id": "ksana-audit-fixture-run",
        "source_artifact_path": source_path,
        "ticker": "AAPL",
        "decision_date": "2026-06-21",
        "research_mode": "ksana_real_research",
        "hypotheses": hypotheses,
        "counterfactuals": counterfactuals
        if counterfactuals is not None
        else ["if demand weakens, downgrade to neutral"],
        "disagreement_with_price_only": disagreement_with_price_only
        if disagreement_with_price_only is not None
        else ["price-only momentum is positive, but margin risk reduces conviction"],
        "evidence_gaps": evidence_gaps if evidence_gaps is not None else ["supplier-side confirmation"],
        "uncertainty_decomposition": uncertainty_decomposition
        if uncertainty_decomposition is not None
        else {"demand": 0.4, "margin": 0.35, "macro": 0.25},
        "summary": summary,
        "why_it_matters": "Shows whether research adds falsifiable structure beyond price.",
        "non_claims": [
            "not OOS/science/public/trading claim",
            "not investment advice",
            "not a 30D forward-live verdict",
        ],
        "evidence_layer": audit.EVIDENCE_LAYER,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "provenance": {
            "source_run_id": "ksana-audit-fixture-run",
            "source_artifact_path": source_path,
            "adapter_path": "gotra/ksana_public_adapter.py",
        },
    }
