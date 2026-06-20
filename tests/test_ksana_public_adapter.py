from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from gotra.ksana_public_adapter import (
    KSANA_PUBLIC_ADAPTER_SCHEMA,
    adapt_ksana_public_research_artifacts,
)
from scripts import baseline_v3_four_arm as v3


def test_valid_public_research_packet_normalizes_with_provenance(tmp_path: Path) -> None:
    source_path = tmp_path / "research.json"
    artifact = _artifact(schema="gotra.ksana_public_research_packet.v1", source_run_id="run-1")
    source_path.write_text(json.dumps({"artifacts": [artifact]}), encoding="utf-8")

    result = adapt_ksana_public_research_artifacts(
        [artifact],
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
        source_artifact_path=source_path,
        fixture_id="fixture-a",
    )

    assert result["accepted_artifacts"]
    normalized = result["accepted_artifacts"][0]
    assert normalized["adapter_schema"] == KSANA_PUBLIC_ADAPTER_SCHEMA
    assert normalized["adapter_validation_status"] == "VALID"
    assert normalized["source_kind"] == "real"
    assert normalized["source_run_id"] == "run-1"
    assert normalized["source_artifact_path"] == str(source_path)
    assert normalized["source_artifact_hash"]
    assert normalized["source_fixture_id"] == "fixture-a"
    assert normalized["provenance_hash"]
    assert result["rejected_research_artifact_count"] == 0


def test_missing_required_field_blocks_packet() -> None:
    artifact = _artifact()
    del artifact["summary"]

    result = adapt_ksana_public_research_artifacts(
        [artifact],
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
    )

    assert result["accepted_artifacts"] == []
    assert result["rejected_research_schema_count"] == 1
    assert result["ksana_public_adapter_issues"][0]["code"] == "missing_or_invalid_required_field"


def test_unknown_schema_version_blocks_packet() -> None:
    result = adapt_ksana_public_research_artifacts(
        [_artifact(schema="ksana.internal.future_schema.v99")],
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
    )

    assert result["accepted_artifacts"] == []
    assert result["rejected_research_schema_count"] == 1
    assert result["ksana_public_adapter_issues"][0]["code"] == "unknown_schema_version"


def test_future_metadata_leak_blocks_packet() -> None:
    result = adapt_ksana_public_research_artifacts(
        [
            _artifact(
                availability_date="2024-01-03",
                latest_visible_price_date="2024-01-03",
            )
        ],
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
    )

    assert result["accepted_artifacts"] == []
    assert result["rejected_research_future_data_count"] == 1
    issue = result["ksana_public_adapter_issues"][0]
    assert issue["code"] == "future_data_metadata_leak"
    assert "availability_date" in issue["fields"]
    assert "latest_visible_price_date" in issue["fields"]


def test_synthetic_packet_cannot_masquerade_as_real_ksana_research() -> None:
    result = adapt_ksana_public_research_artifacts(
        [
            _artifact(
                source_kind="synthetic",
                artifact_role="ksana_real_research",
                evidence_ref="synthetic:aapl:masquerade",
            )
        ],
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
    )

    assert result["accepted_artifacts"] == []
    assert result["rejected_research_identity_count"] == 1
    assert result["ksana_public_adapter_issues"][0]["code"] == "artifact_identity_mismatch"


def test_reference_packet_cannot_enter_ksana_real_research_packet() -> None:
    result = adapt_ksana_public_research_artifacts(
        [_artifact(source_kind="reference", evidence_ref="reference:aapl:price-only")],
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
    )

    assert result["accepted_artifacts"] == []
    assert result["rejected_research_identity_count"] == 1
    assert result["ksana_public_adapter_issues"][0]["code"] == "source_kind_not_ksana_research"


def test_baseline_v3_filter_uses_adapter_and_preserves_legacy_fixture_counts() -> None:
    fixture = Path("tests/fixtures/baseline_v3_1_research_artifacts.json")

    result = v3.filter_external_research_artifacts(
        v3.load_research_artifact_fixture(fixture),
        decision_date=date(2024, 1, 2),
        ticker="AAPL",
        source_artifact_path=fixture,
    )

    assert result["accepted_artifacts"]
    assert result["accepted_artifacts"][0]["adapter_schema"] == KSANA_PUBLIC_ADAPTER_SCHEMA
    assert result["accepted_artifacts"][0]["adapter_legacy_unverified"] is True
    assert result["accepted_artifacts"][0]["source_artifact_path"] == str(fixture)
    assert result["legacy_unverified_research_artifact_count"] == 4
    assert result["rejected_research_future_data_count"] == 1


def _artifact(
    *,
    schema: str = "gotra.ksana_public_research_packet.v1",
    ticker: str = "AAPL",
    source_kind: str = "real",
    evidence_ref: str = "real:aapl:fixture",
    availability_date: str = "2023-12-20",
    latest_visible_price_date: str = "2023-12-20",
    source_run_id: str = "",
    artifact_role: str = "",
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema": schema,
        "ticker": ticker,
        "source_name": "Fixture source",
        "source_url_or_id": "fixture://source/aapl",
        "publish_timestamp": "2023-12-20T00:00:00Z",
        "availability_date": availability_date,
        "latest_visible_price_date": latest_visible_price_date,
        "source_kind": source_kind,
        "retrieval_method": "local_fixture",
        "evidence_ref": evidence_ref,
        "summary": "Time-bounded public research adapter fixture.",
        "citations": ["fixture://source/aapl"],
        "claims": [{"claim": "fixture claim"}],
        "features": {"quality": "fixture"},
    }
    if source_run_id:
        artifact["source_run_id"] = source_run_id
    if artifact_role:
        artifact["artifact_role"] = artifact_role
    return artifact
