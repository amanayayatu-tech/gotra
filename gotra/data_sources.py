"""Public data-source registry for GOTRA research artifacts.

The registry is a policy layer, not a data-fetching layer. It records what each
public/free source may be used for, where it has limits, and which claims must not
be made from that source alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DATA_SOURCE_SCHEMA = "gotra.data_sources.v1"
DEFAULT_DATA_SOURCES_PATH = Path(__file__).resolve().parents[1] / "config" / "data_sources.yml"
REQUIRED_PROVIDER_FIELDS = (
    "purpose",
    "markets",
    "license_note",
    "rate_limit_note",
    "source_types",
    "commercial_use_note",
    "production_realtime_authorized",
    "allow_as_sole_paid_market_data_source",
    "public_summary",
)


def load_data_source_config(path: str | Path = DEFAULT_DATA_SOURCES_PATH) -> dict[str, Any]:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("data source config must be a mapping")
    validate_data_source_config(data)
    return data


def validate_data_source_config(config: dict[str, Any]) -> None:
    if config.get("schema") != DATA_SOURCE_SCHEMA:
        raise ValueError(f"unexpected data source schema: {config.get('schema')!r}")
    providers = config.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("data source config requires providers")
    for provider_id, provider in providers.items():
        if not isinstance(provider, dict):
            raise ValueError(f"provider {provider_id} must be a mapping")
        missing = [field for field in REQUIRED_PROVIDER_FIELDS if field not in provider]
        if missing:
            raise ValueError(f"provider {provider_id} missing fields: {', '.join(missing)}")
        if not isinstance(provider.get("markets"), list) or not provider["markets"]:
            raise ValueError(f"provider {provider_id} markets must be a non-empty list")
        if not isinstance(provider.get("source_types"), list) or not provider["source_types"]:
            raise ValueError(f"provider {provider_id} source_types must be a non-empty list")
        if provider.get("allow_as_sole_paid_market_data_source") is True:
            raise ValueError(f"provider {provider_id} cannot be sole paid-product market data source")
        if provider.get("production_realtime_authorized") is True:
            raise ValueError(f"provider {provider_id} cannot be marked as production realtime authorized")
    priorities = config.get("price_source_priority")
    if not isinstance(priorities, dict) or not priorities:
        raise ValueError("data source config requires price_source_priority")
    for exchange, priority in priorities.items():
        if not isinstance(priority, list) or not priority:
            raise ValueError(f"price_source_priority.{exchange} must be a non-empty list")
        for provider_id in priority:
            provider = providers.get(provider_id)
            if not isinstance(provider, dict):
                raise ValueError(f"price_source_priority.{exchange} references unknown provider {provider_id}")
            if "price_data" not in provider.get("source_types", []):
                raise ValueError(f"price_source_priority.{exchange}.{provider_id} is not a price_data source")
            if provider.get("allow_as_sole_paid_market_data_source") is True:
                raise ValueError(f"price source {provider_id} cannot be sole paid-product market data source")


def provider_config(provider_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = config or load_data_source_config()
    provider = (resolved.get("providers") or {}).get(provider_id)
    if not isinstance(provider, dict):
        raise KeyError(f"unknown data source provider: {provider_id}")
    return provider


def price_source_priority(exchange: str, config: dict[str, Any] | None = None) -> list[str]:
    resolved = config or load_data_source_config()
    priority = (resolved.get("price_source_priority") or {}).get(exchange)
    if not isinstance(priority, list) or not priority:
        raise KeyError(f"missing price source priority for exchange: {exchange}")
    return [str(provider_id) for provider_id in priority]


def provider_public_policy(provider_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    provider = provider_config(provider_id, config=config)
    return {
        "provider_id": provider_id,
        "display_name": str(provider.get("display_name") or provider_id),
        "markets": list(provider["markets"]),
        "source_types": list(provider["source_types"]),
        "purpose_tag": "research_prototype_evidence",
        "license_boundary": "research_prototype_only",
        "rate_limit_boundary": "low_frequency_cached",
        "commercial_release_boundary": "separate_permission_review_required",
        "production_realtime_authorized": bool(provider["production_realtime_authorized"]),
        "allow_as_sole_paid_market_data_source": bool(provider["allow_as_sole_paid_market_data_source"]),
    }


def sec_edgar_request_headers(user_agent: str) -> dict[str, str]:
    user_agent = user_agent.strip()
    if not user_agent:
        raise ValueError("SEC EDGAR requests require an identifying User-Agent")
    return {"User-Agent": user_agent}


def sec_edgar_min_interval_seconds(config: dict[str, Any] | None = None) -> float:
    provider = provider_config("sec_edgar", config=config)
    max_requests = float(provider.get("max_requests_per_second") or 0)
    if max_requests <= 0 or max_requests > 10:
        raise ValueError("SEC EDGAR max_requests_per_second must be within 1..10")
    return 1.0 / max_requests
