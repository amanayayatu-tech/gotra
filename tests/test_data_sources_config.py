from __future__ import annotations

from pathlib import Path

import yaml

from gotra.data_sources import (
    DATA_SOURCE_SCHEMA,
    DEFAULT_DATA_SOURCES_PATH,
    load_data_source_config,
    price_source_priority,
    provider_public_policy,
    sec_edgar_min_interval_seconds,
    sec_edgar_request_headers,
)


def test_data_sources_config_declares_required_stage3_fields() -> None:
    config = load_data_source_config()
    assert config["schema"] == DATA_SOURCE_SCHEMA
    providers = config["providers"]
    for provider_id in (
        "yahoo_chart_api_via_gotra_price_cache",
        "stooq",
        "alpha_vantage",
        "sec_edgar",
        "fred",
        "hkexnews",
    ):
        provider = providers[provider_id]
        for field in ("purpose", "markets", "license_note", "rate_limit_note"):
            assert provider[field], f"{provider_id}.{field} must be populated"
        assert provider["production_realtime_authorized"] is False
        assert provider["allow_as_sole_paid_market_data_source"] is False


def test_price_source_priority_is_explicit_and_research_limited() -> None:
    config = load_data_source_config()
    for exchange in ("HKEX", "NASDAQ", "NYSE"):
        priority = price_source_priority(exchange, config=config)
        assert priority[0] == "yahoo_chart_api_via_gotra_price_cache"
        assert "alpha_vantage" in priority
        for provider_id in priority:
            provider = config["providers"][provider_id]
            assert "price_data" in provider["source_types"]
            assert provider["allow_as_sole_paid_market_data_source"] is False

    yahoo = config["providers"]["yahoo_chart_api_via_gotra_price_cache"]
    assert "research/prototype" in yahoo["license_note"]
    assert "not a licensed production realtime" in yahoo["license_note"]
    assert "not used for realtime" in yahoo["rate_limit_note"]


def test_sec_edgar_and_alpha_vantage_limits_are_encoded() -> None:
    config = load_data_source_config()
    sec = config["providers"]["sec_edgar"]
    assert "User-Agent" in sec["required_headers"]
    assert sec["max_requests_per_second"] <= 10
    assert sec_edgar_min_interval_seconds(config=config) >= 0.1
    assert sec_edgar_request_headers("GOTRA research contact research-ops@example.invalid") == {
        "User-Agent": "GOTRA research contact research-ops@example.invalid"
    }

    alpha = config["providers"]["alpha_vantage"]
    assert alpha["max_requests_per_minute"] <= 5
    assert alpha["max_requests_per_day"] <= 500
    assert "Low-frequency fallback" in alpha["purpose"]


def test_fred_and_hkexnews_are_not_price_authorization_sources() -> None:
    config = load_data_source_config()
    fred = config["providers"]["fred"]
    hkexnews = config["providers"]["hkexnews"]
    assert fred["source_types"] == ["macro"]
    assert "individual-stock price conclusions" in fred["commercial_use_note"]
    assert "price_data" not in fred["source_types"]
    assert "exchange_filing" in hkexnews["source_types"]
    assert "not a realtime quote service" in hkexnews["rate_limit_note"]
    assert "price_data" not in hkexnews["source_types"]


def test_provider_public_policy_is_safe_for_public_artifacts() -> None:
    policy = provider_public_policy("yahoo_chart_api_via_gotra_price_cache")
    assert policy["provider_id"] == "yahoo_chart_api_via_gotra_price_cache"
    assert policy["production_realtime_authorized"] is False
    assert policy["allow_as_sole_paid_market_data_source"] is False
    assert policy["purpose_tag"] == "research_prototype_evidence"
    assert policy["license_boundary"] == "research_prototype_only"
    assert policy["rate_limit_boundary"] == "low_frequency_cached"
    serialized = yaml.safe_dump(policy, allow_unicode=True)
    assert "sk-" not in serialized
    assert "Bearer " not in serialized
    assert "buy" not in serialized.lower()
    assert "sell" not in serialized.lower()
    assert "hold recommendation" not in serialized.lower()


def test_data_sources_config_lives_under_repository_config() -> None:
    assert DEFAULT_DATA_SOURCES_PATH == Path(__file__).resolve().parents[1] / "config" / "data_sources.yml"
    assert DEFAULT_DATA_SOURCES_PATH.exists()
