from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import baseline_v3_6aj_cognitive_lift_fixture_comparison as comparison


def test_conservative_baseline_and_structured_candidate_improves_fixture_metrics(
    tmp_path: Path,
) -> None:
    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=_artifact())
    )

    assert summary["comparison_status"] == comparison.STATUS_IMPROVED
    assert summary["baseline_information_gain_status"] == comparison.LOW_INFORMATION_GAIN
    assert summary["candidate_information_gain_status"] == comparison.SUFFICIENT
    assert summary["delta_ranked_hypothesis_count"] > 0
    assert summary["delta_counterfactual_count"] > 0
    assert summary["delta_falsifiable_trigger_count"] > 0
    assert summary["delta_generic_caution_phrase_count"] < 0
    assert summary["structural_improvement_met"] is True
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["v3_7_allowed"] is False


def test_low_information_baseline_without_positive_structural_deltas_not_improved(
    tmp_path: Path,
) -> None:
    summary = comparison.run_comparison(
        _config(
            tmp_path,
            baseline=_low_information_structurally_rich_artifact(),
            candidate=_artifact(),
        )
    )

    assert summary["baseline_information_gain_status"] == comparison.LOW_INFORMATION_GAIN
    assert summary["candidate_information_gain_status"] == comparison.SUFFICIENT
    assert summary["comparison_status"] == comparison.STATUS_READY
    assert summary["comparison_status"] != comparison.STATUS_IMPROVED
    assert summary["delta_ranked_hypothesis_count"] <= 0
    assert summary["delta_counterfactual_count"] <= 0
    assert summary["delta_falsifiable_trigger_count"] <= 0
    assert summary["structural_improvement_met"] is False


def test_contract_candidate_is_schema_and_provenance_clean(tmp_path: Path) -> None:
    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_artifact(source_suffix="baseline"), candidate=_artifact())
    )

    assert summary["comparison_status"] == comparison.STATUS_READY
    assert summary["baseline_information_gain_status"] == comparison.SUFFICIENT
    assert summary["candidate_information_gain_status"] == comparison.SUFFICIENT
    assert summary["provenance_link_count"] == 2
    assert summary["schema_blocker_count"] == 0
    assert summary["overclaim_blocker_count"] == 0


def test_malformed_candidate_blocks_schema(tmp_path: Path) -> None:
    candidate = _artifact()
    candidate.pop("hypotheses")

    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=candidate)
    )

    assert summary["comparison_status"] == comparison.STATUS_BLOCKED_SCHEMA
    assert summary["schema_blocker_count"] >= 1


def test_missing_candidate_provenance_blocks(tmp_path: Path) -> None:
    candidate = _artifact()
    candidate.pop("provenance")

    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=candidate)
    )

    assert summary["comparison_status"] == comparison.STATUS_BLOCKED_PROVENANCE
    assert summary["provenance_blocker_count"] >= 1


def test_overclaim_candidate_blocks(tmp_path: Path) -> None:
    candidate = _artifact(summary="This fixture is OOS evidence and public proof.")

    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=candidate)
    )

    assert summary["comparison_status"] == comparison.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] >= 1


def test_direct_llm_clean_baseline_wording_blocks(tmp_path: Path) -> None:
    candidate = _artifact(summary="direct_llm is a clean no-future baseline.")

    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=candidate)
    )

    assert summary["comparison_status"] == comparison.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] >= 1


def test_direct_llm_parametric_memory_control_boundary_is_allowed(tmp_path: Path) -> None:
    candidate = _artifact(
        summary="direct_llm_parametric_memory_control is not a clean no-future baseline."
    )

    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=candidate)
    )

    assert summary["comparison_status"] == comparison.STATUS_IMPROVED
    assert summary["direct_llm_interpretation"] == comparison.DIRECT_LLM_INTERPRETATION


def test_low_information_candidate_is_reported(tmp_path: Path) -> None:
    summary = comparison.run_comparison(
        _config(
            tmp_path,
            baseline=_artifact(source_suffix="baseline"),
            candidate=_low_information_artifact(source_suffix="candidate"),
        )
    )

    assert summary["comparison_status"] == comparison.STATUS_LOW_CANDIDATE
    assert summary["candidate_information_gain_status"] == comparison.LOW_INFORMATION_GAIN


def test_ready_or_improved_does_not_execute_verdict(tmp_path: Path) -> None:
    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=_artifact())
    )

    assert summary["comparison_status"] == comparison.STATUS_IMPROVED
    assert summary["evidence_layer"] == comparison.EVIDENCE_LAYER
    assert summary["v3_7_allowed"] is False
    assert "winner" not in summary
    assert "trading_advice" not in summary


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    summary = comparison.run_comparison(
        _config(tmp_path, baseline=_low_information_artifact(), candidate=_artifact())
    )
    summary_path = Path(summary["summary_path"])
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(summary_path)
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def _config(
    tmp_path: Path,
    *,
    baseline: dict[str, object],
    candidate: dict[str, object],
) -> comparison.ComparisonConfig:
    baseline_manifest = _manifest(tmp_path, "baseline", baseline)
    candidate_manifest = _manifest(tmp_path, "candidate", candidate)
    return comparison.ComparisonConfig(
        comparison_run_id=(
            f"{comparison.RUN_ID_PREFIX}test_"
            f"{len(list(tmp_path.iterdir()))}_{len(json.dumps(candidate, sort_keys=True))}"
        ),
        output_dir=tmp_path / "runs",
        baseline_manifest=baseline_manifest,
        candidate_manifest=candidate_manifest,
    )


def _manifest(tmp_path: Path, side: str, artifact: dict[str, object]) -> Path:
    path = tmp_path / f"{side}.json"
    path.write_text(
        json.dumps({"artifacts": [{"path": f"tests/fixtures/{side}.json", "payload": artifact}]}),
        encoding="utf-8",
    )
    return path


def _low_information_artifact(source_suffix: str = "baseline") -> dict[str, object]:
    return _artifact(
        source_suffix=source_suffix,
        hypotheses=[
            {
                "rank": 1,
                "confidence": 0.35,
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


def _low_information_structurally_rich_artifact() -> dict[str, object]:
    return _artifact(
        source_suffix="rich_baseline",
        hypotheses=[
            {
                "rank": 1,
                "confidence": 0.45,
                "why_it_matters": "Risk remains and uncertainty remains.",
                "falsification_triggers": ["trigger one"],
                "expected_observable_evidence": ["observable one"],
            },
            {
                "rank": 2,
                "confidence": 0.42,
                "why_it_matters": "Limited information means risk remains.",
                "falsification_triggers": ["trigger two"],
                "expected_observable_evidence": ["observable two"],
            },
            {
                "rank": 3,
                "confidence": 0.4,
                "why_it_matters": "Uncertainty remains and no conclusion is possible.",
                "falsification_triggers": ["trigger three"],
                "expected_observable_evidence": ["observable three"],
            },
        ],
        counterfactuals=["c1", "c2", "c3"],
        disagreement_with_price_only=["structured disagreement"],
        evidence_gaps=["gap"],
        uncertainty_decomposition={"demand": 0.4, "margin": 0.35, "macro": 0.25},
        summary=(
            "This is not investment advice. It could be uncertain and may have risk. "
            "Uncertainty remains, limited information remains, and no conclusion is available. "
            "Risk remains and generic caution remains."
        ),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(
    *,
    source_suffix: str = "candidate",
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
    source_path = f"fixtures/ksana/aapl_{source_suffix}.json"
    return {
        "schema": "gotra.v3_6ai.ksana_cognitive_lift_packet.v1",
        "source_run_id": f"ksana-fixture-{source_suffix}",
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
        "evidence_layer": "engineering/local cognitive-lift audit only",
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "provenance": {
            "source_run_id": f"ksana-fixture-{source_suffix}",
            "source_artifact_path": source_path,
            "adapter_path": "gotra/ksana_public_adapter.py",
        },
    }
