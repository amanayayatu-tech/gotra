from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import baseline_v3_7k_ksana_packet_v2_front_half_optimization as packet_v2


def test_conservative_packet_is_low_information_gain(tmp_path: Path) -> None:
    summary = packet_v2.run_validator(_config(tmp_path, packet=_conservative_packet()))

    assert summary["validator_status"] == packet_v2.STATUS_LOW_INFORMATION_GAIN
    assert summary["generic_caution_phrase_count"] > (
        summary["hypothesis_count"] + summary["counterfactual_count"]
    )
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["v3_7_actual_verdict_executable"] is False


def test_valid_packet_v2_ready_for_provider_canary_fixture_only(tmp_path: Path) -> None:
    summary = packet_v2.run_validator(
        _config(tmp_path, packet=_packet(), baseline=_conservative_packet(source_suffix="baseline"))
    )

    assert summary["validator_status"] == packet_v2.STATUS_READY
    assert summary["packet_schema_valid"] is True
    assert summary["hypothesis_count"] == 2
    assert summary["ranked_hypothesis_count"] == 2
    assert summary["counterfactual_count"] >= 2
    assert summary["falsifiable_trigger_count"] >= 2
    assert summary["explicit_disagreement_count"] >= 1
    assert summary["evidence_gap_count"] >= 1
    assert summary["uncertainty_decomposition_count"] >= 1
    assert summary["information_gain_delta"] > 0
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["v3_7_actual_verdict_executable"] is False


def test_missing_ranked_hypotheses_blocks_schema(tmp_path: Path) -> None:
    packet = _packet()
    packet.pop("ranked_hypotheses")

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert "missing_or_invalid_packet_v2_schema_field" in summary["blocker_reasons"]


def test_invalid_evidence_layer_blocks_before_ready(tmp_path: Path) -> None:
    packet = _packet()
    packet["evidence_layer"] = "OOS science public proof trading advice provider run"

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert any("evidence_layer" in item["reason"] for item in summary["blocked_items"])


def test_non_positive_baseline_lift_is_low_information_gain(tmp_path: Path) -> None:
    summary = packet_v2.run_validator(
        _config(tmp_path, packet=_packet(), baseline=_richer_packet(source_suffix="baseline"))
    )

    assert summary["validator_status"] == packet_v2.STATUS_LOW_INFORMATION_GAIN
    assert summary["information_gain_delta"] <= 0


def test_missing_counterfactuals_blocks_schema(tmp_path: Path) -> None:
    packet = _packet()
    packet.pop("counterfactuals")

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert any("counterfactuals" in item["reason"] for item in summary["blocked_items"])


def test_missing_falsification_trigger_blocks_schema(tmp_path: Path) -> None:
    packet = _packet()
    packet["falsification_triggers"] = []

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert any("falsification_triggers" in item["reason"] for item in summary["blocked_items"])


def test_placeholder_required_list_entries_block_schema(tmp_path: Path) -> None:
    packet = _packet()
    packet["counterfactuals"] = [None]
    packet["falsification_triggers"] = [{}]
    packet["expected_observable_evidence"] = [""]
    packet["disagreement_with_price_only"] = ["  "]
    packet["evidence_gaps"] = [None]

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    reason = ",".join(item["reason"] for item in summary["blocked_items"])
    assert "counterfactuals" in reason
    assert "falsification_triggers" in reason
    assert "expected_observable_evidence" in reason
    assert "disagreement_with_price_only" in reason
    assert "evidence_gaps" in reason


def test_ranked_hypothesis_requires_non_empty_text(tmp_path: Path) -> None:
    packet = _packet()
    packet["ranked_hypotheses"][0]["hypothesis"] = ""

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert any("ranked_hypotheses[0].hypothesis" in item["reason"] for item in summary["blocked_items"])


def test_scalar_disagreement_with_price_only_blocks_schema(tmp_path: Path) -> None:
    packet = _packet()
    packet["disagreement_with_price_only"] = "price-only disagreement"

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert any(
        "disagreement_with_price_only" in item["reason"]
        for item in summary["blocked_items"]
    )


def test_empty_disagreement_with_price_only_blocks_schema(tmp_path: Path) -> None:
    packet = _packet()
    packet["disagreement_with_price_only"] = []

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert any(
        "disagreement_with_price_only" in item["reason"]
        for item in summary["blocked_items"]
    )


def test_missing_provenance_blocks(tmp_path: Path) -> None:
    packet = _packet()
    packet.pop("provenance")

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_PROVENANCE
    assert "missing_provenance" in summary["blocker_reasons"]


def test_missing_packet_manifest_returns_structured_schema_block(tmp_path: Path) -> None:
    run_id = f"{packet_v2.RUN_ID_PREFIX}missing_manifest"
    exit_code = packet_v2.main(
        [
            "--packet-manifest",
            str(tmp_path / "missing.json"),
            "--validator-run-id",
            run_id,
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )
    summary_path = tmp_path / "runs" / run_id / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert "manifest_load_error" in summary["blocker_reasons"]


def test_invalid_json_packet_manifest_returns_structured_schema_block(tmp_path: Path) -> None:
    manifest = tmp_path / "invalid.json"
    manifest.write_text("{", encoding="utf-8")

    summary = packet_v2.run_validator(
        packet_v2.PacketV2Config(
            validator_run_id=f"{packet_v2.RUN_ID_PREFIX}invalid_manifest",
            output_dir=tmp_path / "runs",
            packet_manifest=manifest,
        )
    )

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert "manifest_load_error" in summary["blocker_reasons"]


def test_forbidden_source_artifact_path_blocks_provenance(tmp_path: Path) -> None:
    packet = _packet()
    forbidden = "data/backtest/runs/ksana_packet.json"
    packet["source_artifact_path"] = forbidden
    packet["provenance"]["source_artifact_path"] = forbidden

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_PROVENANCE
    assert "forbidden_source_artifact_path" in summary["blocker_reasons"]


def test_embedded_manifest_payload_forbidden_path_blocks_schema(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": "data/backtest/runs/embedded_packet.json",
                        "payload": _packet(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = packet_v2.run_validator(
        packet_v2.PacketV2Config(
            validator_run_id=f"{packet_v2.RUN_ID_PREFIX}forbidden_embedded_path",
            output_dir=tmp_path / "runs",
            packet_manifest=manifest,
        )
    )

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert "forbidden_artifact_path" in summary["blocker_reasons"]
    assert any("forbidden_artifact_path" in item["rule_id"] for item in summary["blocked_items"])


def test_non_object_artifact_entry_blocks_schema(tmp_path: Path) -> None:
    artifact_file = tmp_path / "artifact_array.json"
    artifact_file.write_text(json.dumps([None]), encoding="utf-8")

    summary = packet_v2.run_validator(
        packet_v2.PacketV2Config(
            validator_run_id=f"{packet_v2.RUN_ID_PREFIX}non_object_artifact",
            output_dir=tmp_path / "runs",
            packet_artifacts=(artifact_file,),
        )
    )

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_SCHEMA
    assert "non_object_artifact_entry" in summary["blocker_reasons"]
    assert any("non_object_artifact_entry" in item["rule_id"] for item in summary["blocked_items"])


def test_overclaim_blocks_packet(tmp_path: Path) -> None:
    packet = _packet(summary="This fixture is OOS evidence and trading advice.")

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_OVERCLAIM
    assert summary["overclaim_blocker_count"] >= 1


def test_direct_llm_clean_baseline_wording_blocks(tmp_path: Path) -> None:
    packet = _packet(summary="direct_llm is a clean no-future baseline.")

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_BLOCKED_OVERCLAIM
    assert any(
        item["rule_id"] == "direct_llm_clean_no_future_baseline"
        for item in summary["blocked_items"]
    )


def test_direct_llm_parametric_memory_control_boundary_is_allowed(tmp_path: Path) -> None:
    packet = _packet(
        summary="direct_llm_parametric_memory_control is not a clean no-future baseline."
    )

    summary = packet_v2.run_validator(_config(tmp_path, packet=packet))

    assert summary["validator_status"] == packet_v2.STATUS_READY
    assert summary["direct_llm_interpretation"] == packet_v2.DIRECT_LLM_INTERPRETATION


def test_manifest_records_verifiable_summary_digest(tmp_path: Path) -> None:
    summary = packet_v2.run_validator(_config(tmp_path, packet=_packet()))
    summary_path = Path(summary["summary_path"])
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["summary_sha256"] == _sha256(summary_path)
    assert summary["summary_digest_target"] == "manifest.summary_sha256"


def test_ready_does_not_emit_verdict_or_provider_run(tmp_path: Path) -> None:
    summary = packet_v2.run_validator(_config(tmp_path, packet=_packet()))

    assert summary["validator_status"] == packet_v2.STATUS_READY
    assert summary["evidence_layer"] == packet_v2.EVIDENCE_LAYER
    assert summary["provider_or_backend_called"] is False
    assert summary["codex_cli_new_call"] is False
    assert summary["formal_lite_entered"] is False
    assert summary["actual_30d_verdict_executed"] is False
    assert summary["v3_7_actual_verdict_executable"] is False
    assert "winner" not in summary
    assert "trading_advice" not in summary


def _config(
    tmp_path: Path,
    *,
    packet: dict[str, object],
    baseline: dict[str, object] | None = None,
) -> packet_v2.PacketV2Config:
    packet_manifest = _manifest(tmp_path, "packet", packet)
    baseline_manifest = _manifest(tmp_path, "baseline", baseline) if baseline else None
    return packet_v2.PacketV2Config(
        validator_run_id=f"{packet_v2.RUN_ID_PREFIX}test_{len(list(tmp_path.iterdir()))}",
        output_dir=tmp_path / "runs",
        packet_manifest=packet_manifest,
        baseline_manifest=baseline_manifest,
    )


def _manifest(tmp_path: Path, name: str, packet: dict[str, object]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps({"artifacts": [{"path": f"tests/fixtures/{name}.json", "payload": packet}]}),
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _conservative_packet(source_suffix: str = "conservative") -> dict[str, object]:
    return _packet(
        source_suffix=source_suffix,
        ranked_hypotheses=[
            {
                "rank": 1,
                "hypothesis": "Risk remains balanced under limited information.",
                "confidence": 0.35,
                "why_it_matters": "Uncertainty remains and no conclusion is available.",
                "falsification_triggers": ["generic downside risk persists"],
                "expected_observable_evidence": ["future disclosure may help"],
            }
        ],
        counterfactuals=["the thesis may not hold if information changes"],
        falsification_triggers=["generic risk remains"],
        expected_observable_evidence=["future observable evidence may clarify"],
        disagreement_with_price_only=["uncertainty remains"],
        evidence_gaps=["limited information"],
        uncertainty_decomposition={"unknown": 1.0},
        summary=(
            "This is not investment advice. It could be uncertain and may have risk. "
            "Uncertainty remains, limited information remains, and no conclusion is available. "
            "Risk remains, may not hold, might change, could change, and generic caution remains."
        ),
    )


def _richer_packet(source_suffix: str = "rich") -> dict[str, object]:
    packet = _packet(source_suffix=source_suffix)
    packet["ranked_hypotheses"] = [
        *packet["ranked_hypotheses"],
        {
            "rank": 3,
            "hypothesis": "Supply mix can invalidate the margin hypothesis.",
            "confidence": 0.48,
            "why_it_matters": "It adds a second non-price falsifier.",
            "falsification_triggers": ["supplier lead times expand"],
            "expected_observable_evidence": ["supplier-side lead-time disclosure"],
            "counterfactuals": ["if lead times expand, reduce conviction"],
        },
    ]
    packet["counterfactuals"] = [
        "if demand weakens, downgrade to neutral",
        "if lead times expand, reduce conviction",
    ]
    packet["falsification_triggers"] = [
        "margin update misses threshold",
        "supplier lead times expand",
    ]
    packet["expected_observable_evidence"] = [
        "next filing margin disclosure",
        "supplier-side lead-time disclosure",
    ]
    packet["disagreement_with_price_only"] = [
        "price-only momentum is positive, but margin risk reduces conviction",
        "price-only ignores supply mix risk",
    ]
    packet["evidence_gaps"] = ["supplier confirmation", "segment-level demand disclosure"]
    packet["uncertainty_decomposition"] = {
        "demand": 0.3,
        "margin": 0.3,
        "macro": 0.2,
        "supply": 0.2,
    }
    return packet


def _packet(
    *,
    source_suffix: str = "candidate",
    ranked_hypotheses: list[dict[str, object]] | None = None,
    counterfactuals: list[str] | None = None,
    falsification_triggers: list[str] | None = None,
    expected_observable_evidence: list[str] | None = None,
    disagreement_with_price_only: list[str] | None = None,
    evidence_gaps: list[str] | None = None,
    uncertainty_decomposition: dict[str, float] | None = None,
    summary: str = "Fixture packet with explicit cognitive-lift structure.",
) -> dict[str, object]:
    source_path = f"fixtures/ksana/v2/aapl_{source_suffix}.json"
    source_run_id = f"ksana-packet-v2-{source_suffix}"
    if ranked_hypotheses is None:
        ranked_hypotheses = [
            {
                "rank": 1,
                "hypothesis": "Margin recovery changes the base-rate interpretation.",
                "confidence": 0.68,
                "why_it_matters": "It tests whether research adds structure beyond price.",
                "falsification_triggers": ["next filing margin below threshold"],
                "expected_observable_evidence": ["gross margin update"],
                "counterfactuals": ["if margins compress, neutralize the hypothesis"],
            },
            {
                "rank": 2,
                "hypothesis": "Demand mix can contradict price-only momentum.",
                "confidence": 0.52,
                "why_it_matters": "It identifies a non-price observable to monitor.",
                "falsification_triggers": ["channel inventory rises"],
                "expected_observable_evidence": ["inventory commentary"],
                "counterfactuals": ["if inventory rises, lower confidence"],
            },
        ]
    return {
        "schema": packet_v2.PACKET_SCHEMA,
        "source_run_id": source_run_id,
        "source_artifact_path": source_path,
        "ticker": "AAPL",
        "decision_date": "2026-06-21",
        "research_mode": "ksana_packet_v2_fixture",
        "ranked_hypotheses": ranked_hypotheses,
        "why_it_matters": "Validates structured front-half cognitive-lift fields.",
        "confidence": 0.64,
        "falsification_triggers": falsification_triggers
        if falsification_triggers is not None
        else ["margin update misses threshold"],
        "expected_observable_evidence": expected_observable_evidence
        if expected_observable_evidence is not None
        else ["next filing margin disclosure"],
        "counterfactuals": counterfactuals
        if counterfactuals is not None
        else ["if demand weakens, downgrade to neutral"],
        "disagreement_with_price_only": disagreement_with_price_only
        if disagreement_with_price_only is not None
        else ["price-only momentum is positive, but margin risk reduces conviction"],
        "evidence_gaps": evidence_gaps if evidence_gaps is not None else ["supplier confirmation"],
        "uncertainty_decomposition": uncertainty_decomposition
        if uncertainty_decomposition is not None
        else {"demand": 0.4, "margin": 0.35, "macro": 0.25},
        "summary": summary,
        "non_claims": [
            "not OOS/science/public/trading claim",
            "not investment advice",
            "not a 30D forward-live verdict",
        ],
        "evidence_layer": packet_v2.EVIDENCE_LAYER,
        "provider_or_backend_called": False,
        "codex_cli_new_call": False,
        "formal_lite_entered": False,
        "provenance": {
            "source_run_id": source_run_id,
            "source_artifact_path": source_path,
            "fixture_id": f"packet-v2-{source_suffix}",
        },
    }
