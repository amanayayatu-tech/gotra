"""Run an independent full-analyst pipeline pilot for public stock symbols.

This one-shot pilot is intentionally separate from the daily public stock-pool
reports. It may call a local Codex CLI runner, but public artifacts never embed
prompt text, completions, messages, raw provider responses, stdout, or stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.public_stock_pool_full_research import (  # noqa: E402
    CodexCliRunner,
    RunnerResult,
    ensure_private_dir,
    parse_model_json,
    sanitize_text,
    scrub_secret_text,
    write_private_json_atomic,
)
from scripts.public_stock_pool_report import (  # noqa: E402
    ExchangeDates,
    fetch_one,
    latest_completed_hk_session,
    latest_completed_us_session,
    trading_date_for_exchange,
    yahoo_ticker,
)
from gotra.data_sources import provider_public_policy  # noqa: E402
from gotra.judge_agent.audit_chain import (  # noqa: E402
    append_audit_event,
    read_audit_events,
    verify_audit_chain,
)
from gotra.public_api.app import research_universe_items  # noqa: E402


SCHEMA = "gotra.full_analyst.pipeline.v1"
STATUS_SCHEMA = "gotra.full_analyst.status.v1"
SYMBOL_SCHEMA_V1 = "gotra.full_analyst.symbol.v1"
SYMBOL_SCHEMA = "gotra.full_analyst.symbol.v2"
SYMBOL_SCHEMA_V3 = "gotra.full_analyst.symbol.v3"
SYMBOL_SCHEMA_V35 = "gotra.full_analyst.symbol.v3_5"
SYMBOL_SCHEMA_V40 = "gotra.full_analyst.symbol.v4"
RESEARCH_TASK_SCHEMA = "gotra.full_analyst.research_task.v1"
RESEARCH_TASK_SCHEMA_V2 = "gotra.full_analyst.research_task.v2"
EVIDENCE_PACKET_SCHEMA = "gotra.full_analyst.evidence_packet.v1"
EVIDENCE_PACKET_SCHEMA_V2 = "gotra.full_analyst.evidence_packet.v2"
MARKET_DATA_SNAPSHOT_SCHEMA = "gotra.market_data_snapshot.v1"
K_DOSSIER_SCHEMA = "gotra.full_analyst.k_deep_research_dossier.v1"
PERSPECTIVE_AGENT_SCHEMA_V4 = "gotra.full_analyst.perspective_agent.v4"
CHAIRMAN_SCHEMA_V4 = "gotra.full_analyst.chairman_synthesis.v4"
RED_TEAM_SCHEMA_V4 = "gotra.full_analyst.red_team_audit.v4"
RESEARCH_QUALITY_GATE_SCHEMA = "gotra.full_analyst.research_quality_gate.v1"
KNOWLEDGE_GATE_SCHEMA = "gotra.cognition_flywheel.knowledge_gate.v1"
RESEARCH_SIGNAL_SCHEMA = "gotra.research_signal.v1"
PUBLICATION_DECISION_SCHEMA = "gotra.publication_decision.v1"
LEDGER_ENTRY_SCHEMA = "gotra.ledger_entry.v1"
LEDGER_MANIFEST_SCHEMA = "gotra.public_research_ledger.v1"
METHODOLOGY_VERSION = "ksana_4_1_lite"
METHODOLOGY_VERSION_V3 = "ksana_4_1_independent_agents"
METHODOLOGY_VERSION_V35 = "ksana_4_1_research_task_evidence_agents"
METHODOLOGY_VERSION_V40 = "ksana_cognition_flywheel_v4"
EXECUTION_MODEL = "multi_perspective_single_call"
EXECUTION_MODEL_V3 = "independent_agent_calls"
EXECUTION_MODEL_V35 = "research_task_evidence_independent_agent_calls"
EXECUTION_MODEL_V40 = "deep_research_dossier_then_parallel_perspectives"
ALAYA_EVENT_SCHEMA = "gotra.cognition_flywheel.full_analyst_memory.v2"
ALAYA_EVENT_SCHEMA_V3 = "gotra.cognition_flywheel.full_analyst_memory.v3"
ALAYA_EVENT_SCHEMA_V35 = "gotra.cognition_flywheel.full_analyst_memory.v3_5"
ALAYA_EVENT_SCHEMA_V40 = "gotra.cognition_flywheel.full_analyst_memory.v4"
DAILY_READER_SCHEMA_V40 = "gotra.daily_reader_brief.v4"
MARKET_DATA_PROVIDER = "yahoo_chart_api_via_gotra_price_cache"
MARKET_DATA_SOURCE_NAME = "Yahoo Finance chart API via GOTRA price_cache helper"
AGENT_OUTPUT_SCHEMA_V3 = "gotra.full_analyst.agent_output.v3"
PRIVATE_ATTEMPT_SCHEMA = "gotra.full_analyst.private_attempt.v1"
MODE = "full-analyst-evening-hk-test"
LOOP_MODE = "full-analyst-production-loop"
LOOP_SMOKE_MODE = "full-analyst-loop-smoke"
LOOP_MODES = {LOOP_MODE, LOOP_SMOKE_MODE}
REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_RUN_ID = "full_analyst_evening_hk_20260629_v1"
DEFAULT_LOOP_RUN_ID = "full_analyst_10h_loop_20260629_v1"
DEFAULT_OUTPUT_DIR = Path("/opt/gotra/data/reports/full_analyst_test")
DEFAULT_LOOP_OUTPUT_DIR = Path("/opt/gotra/data/reports/full_analyst_loop")
DEFAULT_PRIVATE_AUDIT_ROOT = Path("/opt/gotra/data/private/full_analyst_runs")
DEFAULT_STATIC_DIR = Path("/var/www/gotra-public-ledger/reports")
DEFAULT_SYMBOLS = ("HKEX:0700", "HKEX:1810", "HKEX:9688", "HKEX:9969", "HKEX:0501")
PROMPT_TEMPLATE_VERSION = "gotra.full_analyst.prompt.v2.ksana_4_1_lite"
PROMPT_TEMPLATE_VERSION_V3 = "gotra.full_analyst.prompt.v3.independent_agents"
PROMPT_TEMPLATE_VERSION_V35 = "gotra.full_analyst.prompt.v3_5.research_task_evidence_agents"
PROMPT_TEMPLATE_VERSION_V40 = "gotra.full_analyst.prompt.v4.ksana_cognition_flywheel"
READER_BOUNDARY = (
    "Research content only. Not investment advice, not a trading signal, "
    "no target price, no position sizing, no return promise."
)
READER_BOUNDARY_ZH = (
    "研究内容仅供参考，不构成任何投资建议。系统可以表达研究状态和不确定性，"
    "但不提供交易指令、仓位建议、价格目标或收益承诺。"
)
BOUNDARY_LINES = (
    "research information only",
    "not investment advice",
    "not trading signal",
    "not performance proof",
    "not science/public proof",
    "no directional recommendation",
    "no price objective",
    "no allocation guidance",
    "no outcome promise",
    "no provider/model I/O is embedded",
)
REQUIRED_SYMBOL_KEYS_V1 = (
    "schema",
    "run_id",
    "symbol",
    "exchange",
    "as_of_date",
    "trading_date",
    "price_coverage_status",
    "research_summary",
    "key_updates",
    "positive_case",
    "negative_case",
    "red_team_review",
    "risk_factors",
    "watch_items",
    "source_notes",
    "boundary",
)
REQUIRED_SYMBOL_KEYS = (
    "schema",
    "prompt_template_version",
    "methodology_version",
    "execution_model",
    "symbol",
    "exchange",
    "provider_ticker",
    "as_of_date",
    "price_coverage_status",
    "research_context",
    "k_deep_research",
    "f_partner_view",
    "w_partner_view",
    "g_partner_view",
    "chairman_synthesis",
    "red_team_audit",
    "evidence_gaps",
    "watch_conditions",
    "research_status",
    "confidence_boundary",
    "source_notes",
    "reader_boundary",
)
SECTION_KEYS = {
    "research_context",
    "k_deep_research",
    "f_partner_view",
    "w_partner_view",
    "g_partner_view",
    "chairman_synthesis",
    "red_team_audit",
}
LIST_KEYS = {
    "key_updates",
    "positive_case",
    "negative_case",
    "red_team_review",
    "risk_factors",
    "watch_items",
    "source_notes",
    "boundary",
    "evidence_gaps",
    "watch_conditions",
}
FORBIDDEN_PUBLIC_RE = re.compile(
    r"OPENAI_API_KEY|sk-[A-Za-z0-9_-]+|Bearer\s+|Authorization|PRIVATE KEY|"
    r"prompt_text|\"(?:messages|completion)\"\s*:|raw_provider_response|stdout|stderr|"
    r"target price|\b(?:buy|sell|hold)\s+(?:recommendation|rating|signal)\b|position sizing|return promise|"
    r"目标价|买入|卖出|持有建议|仓位|收益承诺",
    re.IGNORECASE,
)
FORBIDDEN_OUTPUT_KEY_RE = re.compile(r"^(prompt_text|prompt|completion|messages|raw_provider_response|stdout|stderr)$", re.I)
V3_AGENT_IDS = (
    "k_deep_research",
    "f_partner_view",
    "w_partner_view",
    "g_partner_view",
    "chairman_synthesis",
    "red_team_audit",
)
V3_KFWG_AGENT_IDS = V3_AGENT_IDS[:4]
V40_PERSPECTIVE_AGENT_IDS = ("f_partner_view", "w_partner_view", "g_partner_view")
V3_AGENT_TIMING_KEYS = {
    "k_deep_research": "k_deep_research_seconds",
    "f_partner_view": "f_partner_seconds",
    "w_partner_view": "w_partner_seconds",
    "g_partner_view": "g_partner_seconds",
    "chairman_synthesis": "chairman_seconds",
    "red_team_audit": "red_team_seconds",
}
V3_AGENT_ROLE_LABELS = {
    "k_deep_research": "K deep research agent; upstream facts and evidence boundary",
    "f_partner_view": "F partner agent; constructive research view",
    "w_partner_view": "W partner agent; skeptical research view",
    "g_partner_view": "G partner agent; structure, cycle, market environment, and portfolio context without allocation advice",
    "chairman_synthesis": "Chairman synthesis agent; integrates independent public-safe agent outputs without action instructions",
    "red_team_audit": "Independent red-team audit agent; attacks assumptions and reports reliability risks",
}

V35_REQUIRED_SOURCE_PURPOSES = {
    "exchange_filing": "Review exchange-hosted issuer filings, announcements, circulars, financial reports, disclosure records, and other official documents needed to establish issuer-specific public facts.",
    "company_report": "Review official issuer annual reports, interim reports, results materials, presentations, sustainability reports, and investor-relations releases when publicly available.",
    "price_data": "Confirm trading-date price coverage, close availability, daily movement, volume if available, and any missing market-data fields from allowed public market-data sources.",
    "regulator": "Review public regulator notices, enforcement actions, consultation papers, policy documents, and disclosure records relevant to the issuer or sector.",
    "macro": "Review public central-bank, statistics-agency, government, or reputable macro sources for operating regions, demand conditions, rates, inflation, FX, and sector-level macro context.",
    "industry": "Review public industry reports, trade-body publications, regulator sector reports, and reputable market-research summaries while separating sector context from issuer-specific evidence.",
    "news": "Review reputable public news sources to corroborate events, announcement interpretation, and market-context claims without converting commentary into advice.",
    "prior_alaya_memory": "Review GOTRA internal Alaya unresolved questions only as continuity and gap context; do not treat memory as public proof unless independently corroborated.",
    "public_stock_pool_metadata": "Review public stock-pool metadata to confirm why the symbol entered the bounded research candidate set and preserve its research-only boundary.",
    "current_public_status": "Review current GOTRA public coverage, freshness status, missing fields, unresolved constraints, and needs_review flags for this symbol.",
}


def default_v35_required_sources() -> list[dict[str, Any]]:
    return [{"source_type": source_type, "purpose": purpose, "required": True} for source_type, purpose in V35_REQUIRED_SOURCE_PURPOSES.items()]


@dataclass(frozen=True)
class FullAnalystConfig:
    run_id: str
    mode: str
    output_dir: Path
    private_audit_root: Path
    static_dir: Path
    publish_static: bool
    as_of_date: date
    trading_date: date
    universe_url: str
    symbols: tuple[str, ...]
    llm_runner: str
    alaya_mode: str
    max_concurrency: int
    per_symbol_timeout_seconds: int
    retries: int
    codex_bin: str
    model: str
    reasoning_effort: str
    heartbeat_interval_seconds: int
    loop_duration_seconds: int
    sample_cadence_seconds: int
    all_symbols: bool = False
    candidate_service: str | None = None
    candidate_timer: str | None = None
    loop_current_cycle: int = 1
    loop_last_successful_cycle: int = 0
    v3_independent_agents: bool = False
    execution_model: str = EXECUTION_MODEL
    requested_execution_model: str = EXECUTION_MODEL
    agent_concurrency: int = 4
    explicit_v2_fallback: bool = False
    v35_research_system: bool = False
    v40_cognition_flywheel: bool = False


class AnalystRunner(Protocol):
    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        """Return final model text without persisting provider I/O."""


class AlayaSyncClient(Protocol):
    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a public-safe sync result."""


class ConfigurationBlocker(RuntimeError):
    """Raised for public-safe hard blockers that must stop the run."""


class PublicScanError(RuntimeError):
    """Raised when a public artifact fails the safety scanner."""


class FixtureAnalystRunner:
    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        del timeout_seconds
        payload = prompt_input_payload(prompt_text)
        if payload.get("required_schema") in {RESEARCH_TASK_SCHEMA, RESEARCH_TASK_SCHEMA_V2}:
            response = fixture_research_task_output(payload)
            return RunnerResult(True, text=json.dumps(response, ensure_ascii=False), elapsed_seconds=0.001, returncode=0)
        if payload.get("required_schema") == K_DOSSIER_SCHEMA:
            response = fixture_k_dossier_output(payload)
            return RunnerResult(True, text=json.dumps(response, ensure_ascii=False), elapsed_seconds=0.001, returncode=0)
        if payload.get("required_schema") in {
            AGENT_OUTPUT_SCHEMA_V3,
            PERSPECTIVE_AGENT_SCHEMA_V4,
            CHAIRMAN_SCHEMA_V4,
            RED_TEAM_SCHEMA_V4,
        }:
            response = fixture_v3_agent_output(payload)
            return RunnerResult(True, text=json.dumps(response, ensure_ascii=False), elapsed_seconds=0.001, returncode=0)
        symbol = str(payload["symbol"])
        exchange = str(payload["exchange"])
        price_gap = payload["price_coverage_status"] == "data_gap"
        response = {
            "schema": SYMBOL_SCHEMA,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            "methodology_version": METHODOLOGY_VERSION,
            "execution_model": EXECUTION_MODEL,
            "symbol": symbol,
            "exchange": exchange,
            "provider_ticker": payload["provider_ticker"],
            "as_of_date": payload["as_of_date"],
            "price_coverage_status": payload["price_coverage_status"],
            "research_context": {
                "scope": f"Ksana 4.1-lite public research frame for {exchange}:{symbol}.",
                "price_context": payload["price_context"],
                "source_freshness": "Fixture uses bounded public inputs and must be refreshed before stronger claims.",
            },
            "k_deep_research": {
                "summary": "Map upstream drivers, business quality, and source freshness before forming a view.",
                "evidence_focus": ["public filings", "verified market data", "industry structure"],
                "uncertainty": "Fixture evidence is limited and must remain reviewable.",
            },
            "f_partner_view": {
                "summary": "The constructive case depends on durable business quality and verified public updates.",
                "supporting_questions": ["What changed in filings?", "Which demand signals are fresh?"],
            },
            "w_partner_view": {
                "summary": "The cautious case emphasizes valuation, competition, and execution sensitivity.",
                "pressure_points": ["source freshness", "margin pressure", "market structure"],
            },
            "g_partner_view": {
                "summary": "The governance view keeps incomplete coverage visible and separates facts from scenarios.",
                "quality_controls": ["data gap handling", "public-safe wording", "judge gate"],
            },
            "chairman_synthesis": {
                "summary": f"{exchange}:{symbol} remains a public research candidate for continued monitoring.",
                "decision_frame": "Use this as research context, not as an action instruction.",
            },
            "red_team_audit": {
                "summary": "Do not compress uncertainty into a false answer.",
                "overclaim_risks": ["stale data", "single-source interpretation", "action-like wording"],
            },
            "evidence_gaps": [
                "Fixture output does not include independent source refresh.",
                "Price coverage requires review." if price_gap else "No material price coverage gap in fixture input.",
            ],
            "watch_conditions": ["Next verified public filing or market-data refresh."],
            "research_status": "data_gap" if price_gap else "watch",
            "confidence_boundary": "Confidence is bounded by public source freshness and data coverage.",
            "source_notes": ["Fixture runner; replace with real public-source research before stronger claims."],
            "reader_boundary": READER_BOUNDARY,
        }
        return RunnerResult(True, text=json.dumps(response, ensure_ascii=False), elapsed_seconds=0.001, returncode=0)


class MockAlayaSyncClient:
    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        public_payload = build_alaya_public_payload(payload)
        event_schema = alaya_event_schema_for_payload(payload)
        stable = stable_hash(
            {
                "run_id": payload["run_id"],
                "symbol": payload["symbol"],
                "exchange": payload["exchange"],
                "judge_status": payload["judge_status"],
                "public_payload_hash": public_payload["public_payload_hash"],
                "agent_hashes": payload.get("agent_hashes", {}),
            }
        )
        return {
            "status": "synced",
            "mode": "mock",
            "event_schema": event_schema,
            "event_id": f"mock-alaya-{stable[:16]}",
            "event_hash": stable,
            "public_payload_hash": public_payload["public_payload_hash"],
            "readback_status": "not_applicable",
            "write_seconds": 0.0,
            "readback_seconds": 0.0,
            "total_seconds": round(time.monotonic() - started, 3),
        }


@dataclass(frozen=True)
class GotraInternalAlayaSyncClient:
    state_path: Path
    actor: str

    @classmethod
    def from_config(cls, config: FullAnalystConfig) -> "GotraInternalAlayaSyncClient":
        default_state_path = (
            config.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"
        )
        state_path = Path(os.getenv("GOTRA_FULL_ANALYST_ALAYA_STATE_PATH", str(default_state_path)))
        actor = os.getenv("GOTRA_FULL_ANALYST_ALAYA_ACTOR") or "gotra/full_analyst_pipeline"
        return cls(
            state_path=state_path,
            actor=actor,
        )

    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        public_payload = build_alaya_public_payload(payload)
        public_payload_hash = str(public_payload["public_payload_hash"])
        is_v40_payload = payload.get("schema") == SYMBOL_SCHEMA_V40
        is_v35_payload = payload.get("schema") == SYMBOL_SCHEMA_V35
        is_v3_payload = payload.get("schema") in {SYMBOL_SCHEMA_V3, SYMBOL_SCHEMA_V35, SYMBOL_SCHEMA_V40}
        event_schema = alaya_event_schema_for_payload(payload)
        event = {
            "event_type": "full_analyst_memory_sync",
            "event_schema": event_schema,
            "audit_actor": self.actor,
            "run_id": payload["run_id"],
            "cognition_flywheel_layer": (
                "ksana_cognition_flywheel_v4"
                if is_v40_payload
                else "full_analyst_research_task_evidence_agents"
                if is_v35_payload
                else "full_analyst_independent_agents" if is_v3_payload else "full_analyst_ksana_4_1_lite"
            ),
            "feedback_ref": f"full_analyst:{payload['run_id']}:{payload['exchange']}:{payload['symbol']}",
            "knowledge_id": f"full_analyst:{payload['exchange']}:{payload['symbol']}",
            "knowledge_flag": "full_analyst_candidate",
            "symbol": payload["symbol"],
            "exchange": payload["exchange"],
            "methodology_version": payload["methodology_version"],
            "prompt_template_version": payload["prompt_template_version"],
            "research_task_hash": payload.get("research_task_hash", ""),
            "evidence_packet_hash": payload.get("evidence_packet_hash", ""),
            "market_data_snapshot_hash": payload.get("market_data_snapshot_hash", ""),
            "k_dossier_hash": payload.get("k_dossier_hash", ""),
            "research_quality_gate_hash": payload.get("research_quality_gate_hash", ""),
            "knowledge_gate_hash": payload.get("knowledge_gate_hash", ""),
            "research_signal_hash": payload.get("research_signal_hash", ""),
            "publication_decision_hash": payload.get("publication_decision_hash", ""),
            "prompt_hash": payload.get("prompt_hash", ""),
            "research_packet_hash": payload.get("research_packet_hash", ""),
            "public_payload_hash": public_payload_hash,
            "judge_status": payload["judge_status"],
            "price_coverage_status": payload["price_coverage_status"],
            "execution_model": payload["execution_model"],
            "evidence_gaps": payload["evidence_gaps"],
            "watch_conditions": payload["watch_conditions"],
            "knowledge_persistence": payload.get("knowledge_persistence", ""),
            "unresolved_questions": payload.get("unresolved_questions", []),
            "boundary_policy": public_payload["boundary_policy"],
            "readback_status": "pending",
            "source_payload_hash": public_payload_hash,
            "public_payload": public_payload,
        }
        if is_v3_payload:
            event.update(
                {
                    "agent_hashes": payload["agent_hashes"],
                    "agent_timings": payload["agent_timings"],
                    "agent_statuses": agent_statuses(payload),
                    "chairman_hash": payload["agent_hashes"].get("chairman_synthesis", ""),
                    "red_team_hash": payload["agent_hashes"].get("red_team_audit", ""),
                    "red_team_verdict": red_team_verdict(payload),
                    "missing_required_sources": payload.get("missing_required_sources", []),
                    "failure_records": payload.get("failure_records", []),
                }
            )
            if is_v40_payload:
                event.update(
                    {
                        "research_quality_gate": payload.get("research_quality_gate", {}),
                        "knowledge_gate": payload.get("knowledge_gate", {}),
                        "k_deep_research_dossier": payload.get("k_deep_research_dossier", {}),
                    }
                )
        else:
            event["agent_outputs"] = {
                "k_deep_research": payload["k_deep_research"],
                "f_partner_view": payload["f_partner_view"],
                "w_partner_view": payload["w_partner_view"],
                "g_partner_view": payload["g_partner_view"],
                "chairman_synthesis": payload["chairman_synthesis"],
                "red_team_audit": payload["red_team_audit"],
            }
        write_seconds = 0.0
        readback_seconds = 0.0
        try:
            write_started = time.monotonic()
            written = append_audit_event(self.state_path, event)
            write_seconds = time.monotonic() - write_started
        except OSError:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_write_failed",
                "readback_status": "skipped",
                "write_seconds": round(write_seconds, 3),
                "readback_seconds": 0.0,
                "total_seconds": round(time.monotonic() - started, 3),
            }
        readback_started = time.monotonic()
        verification = verify_audit_chain(self.state_path)
        if not verification.ok:
            readback_seconds = time.monotonic() - readback_started
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_hash_chain_invalid",
                "event_id": str(written.get("event_hash") or ""),
                "event_hash": str(written.get("event_hash") or ""),
                "readback_status": "failed",
                "write_seconds": round(write_seconds, 3),
                "readback_seconds": round(readback_seconds, 3),
                "total_seconds": round(time.monotonic() - started, 3),
            }
        event_hash = str(written.get("event_hash") or "")
        readback = [
            record
            for record in read_audit_events(self.state_path)
            if str(record.get("event_hash") or "") == event_hash
        ]
        readback_seconds = time.monotonic() - readback_started
        if not readback:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_readback_missing",
                "event_id": event_hash,
                "event_hash": event_hash,
                "readback_status": "failed",
                "write_seconds": round(write_seconds, 3),
                "readback_seconds": round(readback_seconds, 3),
                "total_seconds": round(time.monotonic() - started, 3),
            }
        readback_payload_hash = str(readback[0].get("source_payload_hash") or "")
        readback_knowledge_id = str(readback[0].get("knowledge_id") or "")
        if readback_knowledge_id != event["knowledge_id"]:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_readback_mismatch",
                "event_id": event_hash,
                "event_hash": event_hash,
                "public_payload_hash": public_payload_hash,
                "readback_status": "mismatch",
                "write_seconds": round(write_seconds, 3),
                "readback_seconds": round(readback_seconds, 3),
                "total_seconds": round(time.monotonic() - started, 3),
            }
        if readback_payload_hash != public_payload_hash:
            return {
                "status": "failed",
                "mode": "real",
                "reason": "gotra_internal_state_readback_mismatch",
                "event_id": event_hash,
                "event_hash": event_hash,
                "public_payload_hash": public_payload_hash,
                "readback_status": "mismatch",
                "write_seconds": round(write_seconds, 3),
                "readback_seconds": round(readback_seconds, 3),
                "total_seconds": round(time.monotonic() - started, 3),
            }
        if is_v3_payload:
            readback_agent_hashes = readback[0].get("agent_hashes") if isinstance(readback[0].get("agent_hashes"), dict) else {}
            if readback_agent_hashes != payload.get("agent_hashes"):
                return {
                    "status": "failed",
                    "mode": "real",
                    "reason": "gotra_internal_state_agent_hash_readback_mismatch",
                    "event_id": event_hash,
                    "event_hash": event_hash,
                    "public_payload_hash": public_payload_hash,
                    "readback_status": "mismatch",
                    "write_seconds": round(write_seconds, 3),
                    "readback_seconds": round(readback_seconds, 3),
                    "total_seconds": round(time.monotonic() - started, 3),
                }
            failure_records = readback[0].get("failure_records") if isinstance(readback[0].get("failure_records"), list) else []
            if payload.get("failure_records") and not failure_records:
                return {
                    "status": "failed",
                    "mode": "real",
                    "reason": "gotra_internal_state_failure_record_readback_missing",
                    "event_id": event_hash,
                    "event_hash": event_hash,
                    "public_payload_hash": public_payload_hash,
                    "readback_status": "mismatch",
                    "write_seconds": round(write_seconds, 3),
                    "readback_seconds": round(readback_seconds, 3),
                    "total_seconds": round(time.monotonic() - started, 3),
                }
            if is_v35_payload or is_v40_payload:
                hash_keys = ["research_task_hash", "evidence_packet_hash", "market_data_snapshot_hash", "chairman_hash", "red_team_hash"]
                if is_v40_payload:
                    hash_keys.extend(
                        [
                            "k_dossier_hash",
                            "research_quality_gate_hash",
                            "knowledge_gate_hash",
                            "research_signal_hash",
                            "publication_decision_hash",
                        ]
                    )
                for hash_key in hash_keys:
                    expected_hash = (
                        payload["agent_hashes"].get("chairman_synthesis", "")
                        if hash_key == "chairman_hash"
                        else payload["agent_hashes"].get("red_team_audit", "")
                        if hash_key == "red_team_hash"
                        else payload.get(hash_key, "")
                    )
                    if str(readback[0].get(hash_key) or "") != str(expected_hash or ""):
                        return {
                            "status": "failed",
                            "mode": "real",
                            "reason": f"gotra_internal_state_{hash_key}_readback_mismatch",
                            "event_id": event_hash,
                            "event_hash": event_hash,
                            "public_payload_hash": public_payload_hash,
                            "readback_status": "mismatch",
                            "write_seconds": round(write_seconds, 3),
                            "readback_seconds": round(readback_seconds, 3),
                            "total_seconds": round(time.monotonic() - started, 3),
                        }
                if is_v40_payload:
                    for value_key in ("knowledge_persistence", "unresolved_questions"):
                        if readback[0].get(value_key) != payload.get(value_key):
                            return {
                                "status": "failed",
                                "mode": "real",
                                "reason": f"gotra_internal_state_{value_key}_readback_mismatch",
                                "event_id": event_hash,
                                "event_hash": event_hash,
                                "public_payload_hash": public_payload_hash,
                                "readback_status": "mismatch",
                                "write_seconds": round(write_seconds, 3),
                                "readback_seconds": round(readback_seconds, 3),
                                "total_seconds": round(time.monotonic() - started, 3),
                            }
        return {
            "status": "synced",
            "mode": "real",
            "event_schema": event_schema,
            "event_id": event_hash,
            "event_hash": event_hash,
            "public_payload_hash": public_payload_hash,
            "readback_status": "verified",
            "write_seconds": round(write_seconds, 3),
            "readback_seconds": round(readback_seconds, 3),
            "total_seconds": round(time.monotonic() - started, 3),
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a GOTRA full analyst one-shot pilot.")
    parser.add_argument("--mode", choices=(MODE, LOOP_MODE, LOOP_SMOKE_MODE), required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--private-audit-root", type=Path, default=DEFAULT_PRIVATE_AUDIT_ROOT)
    parser.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR)
    parser.add_argument("--publish-static", action="store_true")
    parser.add_argument("--as-of-date", default=datetime.now(REPORT_TIMEZONE).date().isoformat())
    parser.add_argument("--trading-date", default="")
    parser.add_argument("--universe-url", default="local")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--all-symbols", action="store_true", help="Run every symbol from the public research universe.")
    parser.add_argument("--llm-runner", choices=("codex-cli", "fixture"), default=os.getenv("GOTRA_FULL_ANALYST_LLM_RUNNER", "codex-cli"))
    parser.add_argument("--alaya-mode", choices=("mock", "off", "real"), default="mock")
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--v3-independent-agents", action="store_true", help="run v3 as true independent per-agent calls")
    parser.add_argument(
        "--v35-research-system",
        action="store_true",
        help="run v3.5 research task + evidence packet + independent-agent calls",
    )
    parser.add_argument(
        "--v40-cognition-flywheel",
        action="store_true",
        help="run v4 Ksana cognition flywheel: research task, evidence packet, K dossier, F/W/G perspectives, gates, and Alaya readback",
    )
    parser.add_argument(
        "--execution-model",
        choices=(EXECUTION_MODEL, EXECUTION_MODEL_V3, EXECUTION_MODEL_V35, EXECUTION_MODEL_V40),
        default=EXECUTION_MODEL,
        help="explicit execution model for public artifacts",
    )
    parser.add_argument("--agent-concurrency", type=int, default=4, help="per-symbol K/F/W/G agent concurrency for v3")
    parser.add_argument("--fallback-to-v2", action="store_true", help="explicitly request v2 fallback instead of v3")
    parser.add_argument("--per-symbol-timeout-seconds", type=int, default=int(os.getenv("GOTRA_FULL_ANALYST_TIMEOUT_SECONDS", "300")))
    parser.add_argument("--retries", type=int, default=int(os.getenv("GOTRA_FULL_ANALYST_RETRIES", "0")))
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default=os.getenv("GOTRA_FULL_ANALYST_LLM_MODEL", "gpt-5.5"))
    parser.add_argument("--reasoning-effort", default=os.getenv("GOTRA_FULL_ANALYST_REASONING_EFFORT", "high"))
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=300)
    parser.add_argument("--loop-duration-seconds", type=int, default=36000)
    parser.add_argument("--sample-cadence-seconds", type=int, default=1800)
    parser.add_argument("--candidate-service", default=os.getenv("GOTRA_FULL_ANALYST_CANDIDATE_SERVICE", ""))
    parser.add_argument("--candidate-timer", default=os.getenv("GOTRA_FULL_ANALYST_CANDIDATE_TIMER", ""))
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> FullAnalystConfig:
    as_of_date = date.fromisoformat(str(args.as_of_date))
    trading_date = date.fromisoformat(str(args.trading_date)) if args.trading_date else latest_completed_hk_session(as_of_date)
    is_loop = str(args.mode) in LOOP_MODES
    output_dir = args.output_dir if args.output_dir is not None else (DEFAULT_LOOP_OUTPUT_DIR if is_loop else DEFAULT_OUTPUT_DIR)
    run_id = str(args.run_id or (DEFAULT_LOOP_RUN_ID if is_loop else DEFAULT_RUN_ID))
    selected_symbols = () if bool(args.all_symbols) else tuple(normalize_symbol_key(value) for value in (args.symbol or list(DEFAULT_SYMBOLS)))
    requested_execution_model = (
        EXECUTION_MODEL_V40
        if bool(args.v40_cognition_flywheel)
        else EXECUTION_MODEL_V35
        if bool(args.v35_research_system)
        else EXECUTION_MODEL_V3
        if bool(args.v3_independent_agents)
        else str(args.execution_model)
    )
    v40_requested = bool(args.v40_cognition_flywheel) or str(args.execution_model) == EXECUTION_MODEL_V40
    v35_requested = bool(args.v35_research_system) or str(args.execution_model) == EXECUTION_MODEL_V35
    v3_requested = bool(args.v3_independent_agents) or str(args.execution_model) == EXECUTION_MODEL_V3 or v35_requested or v40_requested
    explicit_v2_fallback = bool(args.fallback_to_v2 and v3_requested)
    active_execution_model = (
        EXECUTION_MODEL
        if explicit_v2_fallback
        else EXECUTION_MODEL_V40
        if v40_requested
        else EXECUTION_MODEL_V35
        if v35_requested
        else EXECUTION_MODEL_V3
        if v3_requested
        else EXECUTION_MODEL
    )
    return FullAnalystConfig(
        run_id=run_id,
        mode=str(args.mode),
        output_dir=output_dir,
        private_audit_root=args.private_audit_root,
        static_dir=args.static_dir,
        publish_static=bool(args.publish_static),
        as_of_date=as_of_date,
        trading_date=trading_date,
        universe_url=str(args.universe_url),
        symbols=selected_symbols,
        llm_runner=str(args.llm_runner),
        alaya_mode=str(args.alaya_mode),
        max_concurrency=max(1, int(args.max_concurrency)),
        per_symbol_timeout_seconds=max(30, int(args.per_symbol_timeout_seconds)),
        retries=max(0, int(args.retries)),
        codex_bin=str(args.codex_bin),
        model=str(args.model),
        reasoning_effort=str(args.reasoning_effort),
        heartbeat_interval_seconds=max(60, int(args.heartbeat_interval_seconds)),
        loop_duration_seconds=max(0, int(args.loop_duration_seconds)),
        sample_cadence_seconds=max(60, int(args.sample_cadence_seconds)),
        all_symbols=bool(args.all_symbols),
        candidate_service=str(args.candidate_service or "") or None,
        candidate_timer=str(args.candidate_timer or "") or None,
        v3_independent_agents=active_execution_model in {EXECUTION_MODEL_V3, EXECUTION_MODEL_V35, EXECUTION_MODEL_V40},
        execution_model=active_execution_model,
        requested_execution_model=requested_execution_model,
        agent_concurrency=max(1, int(args.agent_concurrency)),
        explicit_v2_fallback=explicit_v2_fallback,
        v35_research_system=active_execution_model == EXECUTION_MODEL_V35,
        v40_cognition_flywheel=active_execution_model == EXECUTION_MODEL_V40,
    )


def private_run_dir(config: FullAnalystConfig) -> Path:
    return config.private_audit_root / config.run_id


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_public_universe(config: FullAnalystConfig) -> list[dict[str, str]]:
    if config.universe_url == "local":
        return [
            {
                "symbol": str(item["symbol"]).strip().upper(),
                "exchange": str(item["exchange"]).strip().upper(),
                "provider_ticker": yahoo_ticker(str(item["symbol"]).strip().upper(), str(item["exchange"]).strip().upper()),
                "source": str(item.get("source") or ""),
                "source_date": str(item.get("source_date") or ""),
                "purpose": str(item.get("purpose") or ""),
                "boundary": str(item.get("boundary") or ""),
            }
            for item in research_universe_items()
        ]
    from scripts.public_stock_pool_full_research import load_universe

    return load_universe(config.universe_url)


def selected_universe(universe: list[dict[str, str]], symbols: tuple[str, ...]) -> list[dict[str, str]]:
    if not symbols:
        return list(universe)
    by_key = {f"{item['exchange']}:{item['symbol']}": item for item in universe}
    selected: list[dict[str, str]] = []
    missing: list[str] = []
    for key in symbols:
        item = by_key.get(key)
        if item is None:
            missing.append(key)
            continue
        selected.append(item)
    if missing:
        raise RuntimeError(f"requested symbols not in public universe: {','.join(missing)}")
    if len({f'{item["exchange"]}:{item["symbol"]}' for item in selected}) != len(selected):
        raise RuntimeError("duplicate selected symbols")
    return selected


def normalize_symbol_key(value: str) -> str:
    raw = str(value).strip().upper()
    if ":" not in raw:
        if raw.endswith(".HK"):
            return f"HKEX:{raw.removesuffix('.HK')}"
        raise ValueError(f"symbol must be EXCHANGE:SYMBOL: {value}")
    exchange, symbol = raw.split(":", 1)
    exchange = exchange.strip()
    symbol = symbol.strip()
    if exchange not in {"HKEX", "NASDAQ", "NYSE"} or not symbol:
        raise ValueError(f"unsupported symbol key: {value}")
    return f"{exchange}:{symbol}"


def exchange_dates_for_config(config: FullAnalystConfig) -> ExchangeDates:
    us_date = latest_completed_us_session(config.as_of_date)
    return ExchangeDates(
        primary_trading_date=config.trading_date,
        hkex_trading_date=config.trading_date,
        nasdaq_trading_date=us_date,
        nyse_trading_date=us_date,
        reason="full analyst evening HK pilot; HKEX uses latest completed HK session",
    )


def fetch_price_rows(
    items: list[dict[str, str]],
    config: FullAnalystConfig,
    price_rows: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if price_rows is not None:
        return price_rows
    dates = exchange_dates_for_config(config)
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        rows[f"{item['exchange']}:{item['symbol']}"] = fetch_one(item, dates, fetch_retries=2)
    return rows


def build_prompt(item: dict[str, str], price_row: dict[str, Any], config: FullAnalystConfig, *, attempt: int, last_error: str) -> str:
    payload = {
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat(),
        "price_coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "price_context": public_price_context(price_row),
        "required_schema": SYMBOL_SCHEMA,
        "required_keys": list(REQUIRED_SYMBOL_KEYS),
        "methodology_version": METHODOLOGY_VERSION,
        "execution_model": EXECUTION_MODEL,
        "boundary": list(BOUNDARY_LINES),
        "reader_boundary": READER_BOUNDARY,
    }
    retry_note = ""
    if attempt > 1:
        retry_note = f"\nRetry attempt {attempt}. Previous failure: {sanitize_text(last_error)[:160]}."
        if last_error.startswith("forbidden_public_content_detected"):
            retry_note += (
                " Remove the public-safety trigger and rewrite it as neutral research boundary language. "
                "Use price objective instead of target-price wording, and avoid action-like buy/sell/hold phrases."
            )
        if last_error.startswith("forbidden_public_content_detected:"):
            retry_note += (
                " Remove the named public-safety trigger and rewrite that clause as neutral research context "
                "without advice, target-price, trading-signal, raw-I/O, or secret wording."
            )
    return (
        "Return STRICT JSON only. No markdown, no code fences, no commentary.\n"
        "Produce a GOTRA Full Analyst v2 public-safe research object using Ksana 4.1-lite methodology.\n"
        "This is one LLM call that returns multiple research perspectives. Set execution_model exactly to "
        f"{EXECUTION_MODEL}; do not claim independent agents or separate processes.\n"
        "Use these perspectives: k_deep_research, f_partner_view, w_partner_view, g_partner_view, "
        "chairman_synthesis, and red_team_audit. Treat K as deep upstream research, F/W/G as partner views, "
        "chairman_synthesis as the bounded integrated view, and red_team_audit as risk/overclaim review.\n"
        "Preserve evidence gaps, stale data, data gaps, source freshness, watch conditions, waiting conditions, "
        "and uncertainty boundary. Do not fill missing evidence with invented facts.\n"
        "Allowed research_status values: candidate, watch, avoid, needs_review, data_gap. If price_coverage_status "
        "is data_gap, set research_status to data_gap or needs_review and explain the gap.\n"
        "Do not provide investment advice, trading signal, directional recommendation, price objective, "
        "allocation guidance, outcome promise, performance proof, or science/public proof.\n"
        "Avoid action-like recommendation language, stdout, stderr, completion, messages, and raw_provider_response "
        "in all JSON values.\n"
        "Set reader_boundary exactly from the Input JSON.\n"
        "Do not include prompt_text, completion, messages, raw_provider_response, stdout, stderr, "
        "Authorization, Bearer, API keys, or secrets.\n"
        "Use objects for research_context, k_deep_research, f_partner_view, w_partner_view, g_partner_view, "
        "chairman_synthesis, and red_team_audit. Use arrays for evidence_gaps, watch_conditions, and source_notes.\n"
        f"Input JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}{retry_note}"
    )


def build_research_task_prompt(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    *,
    attempt: int,
    last_error: str,
) -> str:
    task_schema = research_task_schema_for_config(config)
    market_data_snapshot = build_market_data_snapshot(item, price_row, config)
    trigger_context = {
        "price_move": public_price_context(price_row),
        "market_data_snapshot": market_data_snapshot,
        "market_data_snapshot_hash": market_data_snapshot["snapshot_hash"],
        "coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "freshness": f"as_of_date={config.as_of_date.isoformat()}; trading_date={trading_date_for_exchange(item['exchange'], exchange_dates_for_config(config)).isoformat()}",
        "prior_alaya_unresolved_questions": prior_alaya_unresolved_questions(item, config),
    }
    payload = {
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "required_schema": task_schema,
        "required_keys": [
            "schema",
            "run_id",
            "symbol",
            "exchange",
            "provider_ticker",
            "as_of_date",
            "selection_reason",
            "trigger_context",
            "research_mission",
            "core_questions",
            "required_sources",
            "must_not_conclude_without",
            "evidence_gap_policy",
            "k_dossier_objectives",
            "agent_briefs",
            "reader_boundary",
        ],
        "trigger_context": trigger_context,
        "universe_metadata": {
            "source": item.get("source", ""),
            "source_date": item.get("source_date", ""),
            "purpose": item.get("purpose", ""),
            "boundary": item.get("boundary", ""),
        },
        "allowed_source_types": [
            "exchange_filing",
            "company_report",
            "price_data",
            "regulator",
            "macro",
            "industry",
            "news",
            "prior_alaya_memory",
            "public_stock_pool_metadata",
            "current_public_status",
        ],
        "agent_ids": list(V3_AGENT_IDS),
        "reader_boundary": READER_BOUNDARY,
        "boundary": list(BOUNDARY_LINES),
    }
    retry_note = ""
    if attempt > 1:
        retry_note = f"\nRetry attempt {attempt}. Previous failure: {sanitize_text(last_error)[:160]}."
    return (
        "Return STRICT JSON only. No markdown, no code fences, no commentary.\n"
        f"Produce a GOTRA Full Analyst {'v4.0 Ksana cognition flywheel' if is_v40_config(config) else 'v3.5'} research task object before any analyst agents run.\n"
        "The task must explain why this symbol is researched today, the 3-6 concrete research questions, "
        "the required public sources, what cannot be concluded without those sources, and specific briefs for "
        "K dossier, F/W/G, Chairman, and Red Team.\n"
        "For v4, K is a deep research dossier that runs before F/W/G; F/W/G briefs must assume they consume research_task, "
        "evidence_packet, k_deep_research_dossier, prior_alaya_readback, and must_not_conclude_without.\n"
        "Do not provide investment advice, trading signals, price objectives, allocation guidance, outcome promises, "
        "performance proof, science/public proof, raw provider/model I/O, prompts, credentials, or secrets.\n"
        "Use data_gap or needs_review language when coverage or sources are incomplete. Do not invent unavailable sources.\n"
        f"Input JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}{retry_note}"
    )


def build_v3_agent_prompt(
    agent_id: str,
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    *,
    dependencies: dict[str, Any] | None = None,
    attempt: int = 1,
    last_error: str = "",
) -> tuple[str, str]:
    if agent_id not in V3_AGENT_IDS:
        raise ValueError(f"unsupported_v3_agent:{agent_id}")
    market_data_snapshot = build_market_data_snapshot(item, price_row, config)
    dependency_packet = (
        public_v35_dependency_packet(dependencies or {}, agent_id)
        if has_research_task_system(config)
        else public_dependency_packet(dependencies or {})
    )
    public_context = {
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat(),
        "price_coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "price_context": public_price_context(price_row),
        "market_data_snapshot_hash": market_data_snapshot["snapshot_hash"],
        "agent_id": agent_id,
        "agent_role": V3_AGENT_ROLE_LABELS[agent_id],
        "dependencies": dependency_packet.get("agent_outputs", dependency_packet) if has_research_task_system(config) else dependency_packet,
        "alaya_readback_summary": (
            "current-symbol v4 memory write occurs after research quality and knowledge gates; no external Alaya service is used"
            if is_v40_config(config)
            else "current-symbol v3.5 memory write occurs after judge gate; no external Alaya service is used"
            if is_v35_config(config)
            else "current-symbol v3 memory write occurs after judge gate; no external Alaya service is used"
        ),
    }
    if has_research_task_system(config):
        public_context.update(
            {
                "research_task": dependency_packet.get("research_task", {}),
                "evidence_packet": dependency_packet.get("evidence_packet", {}),
                "prior_alaya_readback": dependency_packet.get("prior_alaya_readback", {}),
                "k_deep_research_dossier": dependency_packet.get("k_deep_research_dossier", {}),
                "k_dossier_hash": dependency_packet.get("k_dossier_hash", ""),
                "agent_brief": dependency_packet.get("agent_brief", ""),
                "required_questions": dependency_packet.get("required_questions", []),
                "must_not_conclude_without": dependency_packet.get("must_not_conclude_without", []),
            }
        )
    input_context_hash = stable_hash(public_context)
    payload = {
        **public_context,
        "required_schema": agent_output_schema_for_config(config, agent_id),
        "required_keys": [
            "agent_id",
            "agent_role",
            "schema",
            "symbol",
            "exchange",
            "run_id",
            "started_at",
            "finished_at",
            "duration_seconds",
            "model",
            "prompt_template_version",
            "input_context_hash",
            "output_hash",
            "status",
            "findings",
            "evidence_refs",
            "evidence_gaps",
            "uncertainties",
            "watch_conditions",
            "boundary",
        ],
        "model": config.model,
        "prompt_template_version": prompt_template_for_config(config),
        "input_context_hash": input_context_hash,
        "methodology_version": methodology_for_config(config),
        "execution_model": execution_model_for_config(config),
        "allowed_status": ["ok", "needs_review", "failed"],
        "allowed_research_status": ["candidate", "watch", "avoid", "needs_review", "data_gap", "high_uncertainty"],
        "boundary": "research content only; does not constitute investment advice",
    }
    role_instruction = {
        "k_deep_research": (
            "K goal: establish company/ticker identity, latest public context, price/data coverage, business/sector/event frame, "
            "known evidence, missing evidence, stale/data_gap handling, and next verification steps."
        ),
        "f_partner_view": (
            "F goal: constructive view. Include positive thesis, what improved or may be improving, supporting evidence, "
            "conditions required for the thesis to remain valid, and risks to that thesis."
        ),
        "w_partner_view": (
            "W goal: skeptical view. Include bear case, what worsened or may be weakening, evidence for negative view, "
            "fragility points, and what would invalidate the bear case."
        ),
        "g_partner_view": (
            "G goal: macro/sector/liquidity/market-structure and scenario context. Do not provide allocation, position, "
            "or action advice. Keep output as non-actionable research status."
        ),
        "chairman_synthesis": (
            "Chairman goal: read only K/F/W/G public-safe outputs, hashes, evidence gaps, price/data context, and Alaya readback summary. "
            "Return consensus points, conflicts, strongest evidence, weakest assumptions, research_status, confidence_boundary, "
            "watch_conditions, and next verification steps. Do not turn this into a trading instruction."
        ),
        "red_team_audit": (
            "Red Team goal: independently audit K dossier, F/W/G, and Chairman. Include weak assumptions, unsupported checks, "
            "counter-evidence needed, over-certainty risks, public-boundary risks, contradiction list, data_gap impact, "
            "what would make report unreliable, and final_red_team_verdict. Red Team is an audit input and is not the Judge."
        ),
    }[agent_id]
    retry_note = ""
    if attempt > 1:
        retry_note = f"\nRetry attempt {attempt}. Previous failure: {sanitize_text(last_error)[:160]}."
    research_system_instruction = (
        (
            "Your input includes a research_task, evidence_packet, k_deep_research_dossier, k_dossier_hash, "
            "prior_alaya_readback, agent_brief, required_questions, and must_not_conclude_without. "
            "F/W/G must consume the K dossier and must not conclude without it. Chairman must synthesize K plus F/W/G. "
            "Red Team audits Chairman and the upstream evidence but is not Judge. Preserve data_gap or needs_review.\n"
        )
        if is_v40_config(config)
        else (
            "Your input includes a research_task, evidence_packet, prior_alaya_readback, required_questions, "
            "and must_not_conclude_without. Base findings on those objects and cite evidence_refs using evidence_id values. "
            "If the packet is missing a required source, preserve that as data_gap or needs_review.\n"
        )
        if is_v35_config(config)
        else ""
    )
    prompt = (
        "Return STRICT JSON only. No markdown, no code fences, no commentary.\n"
        f"This is GOTRA Full Analyst {'v4.0 Ksana cognition flywheel' if is_v40_config(config) else 'v3.5' if is_v35_config(config) else 'v3'}. "
        "You are one independent agent call, not a field inside a shared prompt.\n"
        f"{research_system_instruction}"
        f"{role_instruction}\n"
        "Public safety: research content only; no investment advice, trading signal, directional recommendation, price objective, "
        "allocation guidance, outcome promise, performance proof, or science/public proof. Do not include raw provider/model I/O, "
        "prompt text, stdout, stderr, credentials, Authorization, Bearer, or secret material.\n"
        "If evidence is missing, mark data_gap or needs_review and make the gap specific. Do not invent facts.\n"
        f"Input JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}{retry_note}"
    )
    return prompt, input_context_hash


def prompt_input_payload(prompt_text: str) -> dict[str, Any]:
    marker = "Input JSON:"
    index = prompt_text.find(marker)
    if index < 0:
        raise ValueError("prompt missing Input JSON payload")
    payload = prompt_text[index + len(marker):].strip()
    if "\nRetry attempt" in payload:
        payload = payload.split("\nRetry attempt", 1)[0].strip()
    return json.loads(payload)


def fixture_research_task_output(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = sanitize_text(str(payload.get("symbol") or ""))
    exchange = sanitize_text(str(payload.get("exchange") or ""))
    provider_ticker = sanitize_text(str(payload.get("provider_ticker") or ""))
    coverage = str((payload.get("trigger_context") or {}).get("coverage_status") or "unknown")
    price_gap = coverage == "data_gap"
    agent_briefs = {
        "k_deep_research": "Map identity, public-source freshness, required filings/reports, and unresolved evidence gaps.",
        "f_partner_view": "Use only packet evidence and K dossier to state the constructive research case and its required proof points.",
        "w_partner_view": "Use only packet evidence and K dossier to state the cautious case, weak assumptions, and fragility points.",
        "g_partner_view": "Use packet evidence and K dossier to map macro/sector/liquidity context without action or allocation language.",
        "chairman_synthesis": "Integrate K dossier plus F/W/G conflicts, evidence strength, missing sources, and waiting conditions.",
        "red_team_audit": "Audit unsupported claims, hallucination risk, weak source coverage, overconfidence, and boundary drift; do not act as Judge.",
    }
    return {
        "schema": sanitize_text(str(payload.get("required_schema") or RESEARCH_TASK_SCHEMA)),
        "run_id": sanitize_text(str(payload.get("run_id") or "")),
        "symbol": symbol,
        "exchange": exchange,
        "provider_ticker": provider_ticker,
        "as_of_date": sanitize_text(str(payload.get("as_of_date") or "")),
        "selection_reason": (
            f"{exchange}:{symbol} is selected because the public stock-pool candidate needs a bounded daily research task; "
            f"coverage_status={coverage}."
        ),
        "trigger_context": sanitize_record(payload.get("trigger_context") or {}),
        "research_mission": (
            f"Build a public-safe, evidence-bounded research view for {exchange}:{symbol}; preserve missing sources before synthesis."
        ),
        "core_questions": [
            "What changed in the latest public price/coverage context?",
            "Which public filings, reports, or official updates are required before stronger claims?",
            "Where do constructive and cautious views disagree?",
            "Which evidence gaps must remain visible to readers?",
        ],
        "required_sources": [
            {"source_type": "price_data", "purpose": "confirm latest public price/coverage state", "required": True},
            {"source_type": "public_stock_pool_metadata", "purpose": "confirm symbol identity and selection context", "required": True},
            {"source_type": "current_public_status", "purpose": "connect the task to the latest public GOTRA report state", "required": True},
            {"source_type": "prior_alaya_memory", "purpose": "read unresolved internal cognition flywheel questions", "required": False},
            {"source_type": "company_report", "purpose": "refresh issuer fundamentals from official reports when available", "required": True},
            {"source_type": "exchange_filing", "purpose": "verify material announcements and filing freshness", "required": True},
        ],
        "must_not_conclude_without": [
            "fresh public price/coverage context",
            "official issuer or exchange evidence for material claims",
            "explicit treatment of stale or missing required sources",
            "red-team review of the strongest assumption",
        ],
        "evidence_gap_policy": [
            "If an official source is missing, keep it in missing_required_sources.",
            "Do not convert stale or missing evidence into confident language.",
            "Use needs_review or data_gap when source coverage is insufficient.",
        ],
        "k_dossier_objectives": [
            "Build a source-grounded upstream dossier before F/W/G start.",
            "Name key uncertainties, must-verify next items, and evidence gaps.",
            "Produce a dossier_hash that F/W/G, Chairman, Red Team, and Alaya readback can verify.",
        ],
        "agent_briefs": agent_briefs,
        "perspective_agent_briefs": {key: agent_briefs[key] for key in V40_PERSPECTIVE_AGENT_IDS},
        "reader_boundary": READER_BOUNDARY,
        "task_status": "needs_review" if price_gap else "ok",
    }


def fixture_v3_agent_output(payload: dict[str, Any]) -> dict[str, Any]:
    agent_id = sanitize_text(str(payload.get("agent_id") or "unknown_agent"))
    symbol = sanitize_text(str(payload.get("symbol") or ""))
    exchange = sanitize_text(str(payload.get("exchange") or ""))
    price_gap = str(payload.get("price_coverage_status") or "") == "data_gap"
    is_v40_payload = str(payload.get("execution_model") or "") == EXECUTION_MODEL_V40
    evidence_packet = payload.get("evidence_packet") if isinstance(payload.get("evidence_packet"), dict) else {}
    evidence_items = evidence_packet.get("evidence_items") if isinstance(evidence_packet.get("evidence_items"), list) else []
    packet_gaps = evidence_packet.get("data_gaps") if isinstance(evidence_packet.get("data_gaps"), list) else []
    evidence_refs = [
        sanitize_text(str((item or {}).get("evidence_id") or ""))
        for item in evidence_items
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    ][:4] or ["fixture_public_context"]
    role_specific: dict[str, dict[str, Any]] = {
        "k_deep_research": {
            "findings": [
                f"{exchange}:{symbol} identity and public-source frame are established from supplied context.",
                "Latest public context must be refreshed before stronger conclusions.",
                "Price coverage is explicitly marked as a data gap." if price_gap else "Price coverage is available in the supplied public context.",
            ],
            "evidence_gaps": [
                "Independent issuer filing refresh is not present in fixture mode.",
                "Latest news/event verification is required before stronger claims.",
            ],
            "watch_conditions": ["Next public filing, exchange announcement, or verified market-data refresh."],
        },
        "f_partner_view": {
            "findings": [
                "Constructive thesis depends on durable business quality and verifiable operating improvement.",
                "Positive view remains conditional on fresh public evidence rather than model confidence.",
            ],
            "evidence_gaps": ["Need current evidence for demand, margin, and competitive-position improvement."],
            "watch_conditions": ["Observable improvement in next public operating update."],
        },
        "w_partner_view": {
            "findings": [
                "Bear case focuses on valuation sensitivity, competition, and execution risk.",
                "The cautious view is invalidated only by fresh evidence that reduces those pressure points.",
            ],
            "evidence_gaps": ["Need current evidence on margin pressure, regulation, and peer competition."],
            "watch_conditions": ["Watch whether public updates weaken or confirm the bear-case pressure points."],
        },
        "g_partner_view": {
            "findings": [
                "Macro, liquidity, sector cycle, and market-structure context must stay separated from allocation advice.",
                "Scenario map remains non-actionable and bounded by evidence freshness.",
            ],
            "evidence_gaps": ["Need current sector, liquidity, and sentiment evidence before stronger environment claims."],
            "watch_conditions": ["Monitor sector-cycle and market-structure changes through public sources."],
        },
        "chairman_synthesis": {
            "findings": [
                "Consensus: evidence freshness and data coverage are the key constraints.",
                "Conflict: constructive durability arguments remain contested by valuation and execution fragility.",
                "Weakest assumption is that fixture context represents current public reality.",
            ],
            "evidence_gaps": ["Chairman requires refreshed K/F/W/G evidence before stronger synthesis."],
            "watch_conditions": ["Verify public filings, market data, and agent conflicts in the next run."],
            "research_status": "data_gap" if price_gap else "watch",
            "consensus": ["Evidence freshness is the controlling constraint."],
            "conflicts": ["Constructive durability and cautious fragility remain unresolved."],
            "evidence_strength": "limited_fixture_packet_with_visible_gaps",
            "unresolved_questions": ["Which required public sources can be refreshed next?"],
            "research_status_proposal": "data_gap" if price_gap else "needs_review" if packet_gaps else "watch",
        },
        "red_team_audit": {
            "findings": [
                "Possible hallucination risk: stale or missing public evidence may be over-read.",
                "Overconfidence risk: independent-agent structure does not by itself validate the research conclusion.",
                "Contradictions must remain visible when K/F/W/G disagree.",
            ],
            "evidence_gaps": ["Missing external public-source refresh can make the report unreliable."],
            "watch_conditions": ["Block promotion if evidence gaps remain vague or action-like language appears."],
            "final_red_team_verdict": (
                "data_gap"
                if price_gap
                else "pass_with_review_items"
                if is_v40_payload
                else "pass"
            ),
            "weak_assumptions": ["Fixture context may not represent current public reality."],
            "over_certainty_risks": ["Agent agreement could be mistaken for evidence strength."],
            "counter_evidence_needed": ["Fresh issuer disclosures and public market-data corroboration."],
            "public_boundary_risks": ["Reader may over-read research status as an action answer."],
            "unsupported_checks": ["No raw external source refresh is present in fixture mode."],
            "red_team_role": "audit_not_judge",
        },
    }
    details = role_specific.get(agent_id, {})
    return {
        "agent_id": agent_id,
        "agent_role": V3_AGENT_ROLE_LABELS.get(agent_id, agent_id),
        "schema": sanitize_text(str(payload.get("required_schema") or AGENT_OUTPUT_SCHEMA_V3)),
        "symbol": symbol,
        "exchange": exchange,
        "run_id": sanitize_text(str(payload.get("run_id") or "")),
        "started_at": "",
        "finished_at": "",
        "duration_seconds": 0,
        "model": sanitize_text(str(payload.get("model") or "fixture")),
        "prompt_template_version": sanitize_text(str(payload.get("prompt_template_version") or PROMPT_TEMPLATE_VERSION_V3)),
        "input_context_hash": sanitize_text(str(payload.get("input_context_hash") or "")),
        "output_hash": "",
        "status": "needs_review" if price_gap and agent_id in {"k_deep_research", "chairman_synthesis", "red_team_audit"} else "ok",
        "findings": details.get("findings", ["Fixture agent output remains public-safe and bounded."]),
        "evidence_refs": evidence_refs,
        "evidence_gaps": details.get("evidence_gaps", ["Fixture evidence requires public refresh."]),
        "uncertainties": ["Fixture mode is not a live-source refresh.", "This is research content only."],
        "watch_conditions": details.get("watch_conditions", ["Next verified public update."]),
        "boundary": "research content only; does not constitute investment advice",
        **({"research_status": details["research_status"]} if "research_status" in details else {}),
        **({"final_red_team_verdict": details["final_red_team_verdict"]} if "final_red_team_verdict" in details else {}),
        **({"consensus": details["consensus"]} if "consensus" in details else {}),
        **({"conflicts": details["conflicts"]} if "conflicts" in details else {}),
        **({"evidence_strength": details["evidence_strength"]} if "evidence_strength" in details else {}),
        **({"unresolved_questions": details["unresolved_questions"]} if "unresolved_questions" in details else {}),
        **({"research_status_proposal": details["research_status_proposal"]} if "research_status_proposal" in details else {}),
        **({"weak_assumptions": details["weak_assumptions"]} if "weak_assumptions" in details else {}),
        **({"over_certainty_risks": details["over_certainty_risks"]} if "over_certainty_risks" in details else {}),
        **({"counter_evidence_needed": details["counter_evidence_needed"]} if "counter_evidence_needed" in details else {}),
        **({"public_boundary_risks": details["public_boundary_risks"]} if "public_boundary_risks" in details else {}),
        **({"unsupported_checks": details["unsupported_checks"]} if "unsupported_checks" in details else {}),
        **({"red_team_role": details["red_team_role"]} if "red_team_role" in details else {}),
    }


def public_price_context(price_row: dict[str, Any]) -> dict[str, Any]:
    if price_row.get("ok"):
        return {
            "status": "ok",
            "close_date": price_row.get("close_date"),
            "one_session_change_pct": price_row.get("one_session_change_pct"),
        }
    return {
        "status": "data_gap",
        "close_date": price_row.get("close_date"),
        "reason": sanitize_text(str(price_row.get("reason") or "unknown")),
    }


def market_currency_for_exchange(exchange: str) -> str:
    return {"HKEX": "HKD", "NASDAQ": "USD", "NYSE": "USD"}.get(str(exchange).upper(), "UNKNOWN")


def market_name_for_exchange(exchange: str) -> str:
    return {
        "HKEX": "Hong Kong public equity market",
        "NASDAQ": "United States public equity market",
        "NYSE": "United States public equity market",
    }.get(str(exchange).upper(), "unknown public equity market")


def parse_optional_date(value: Any) -> date | None:
    text = sanitize_text(str(value or ""))
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def build_market_data_snapshot(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
) -> dict[str, Any]:
    trading_date = trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config))
    close_date = parse_optional_date(price_row.get("close_date"))
    quality_flags = [
        "bounded_public_pipeline_context",
        "adjusted_close_price" if price_row.get("ok") else "price_data_missing",
        "currency_inferred_from_exchange",
    ]
    if not price_row.get("ok"):
        quality_flags.append(f"missing_reason:{sanitize_text(str(price_row.get('reason') or 'unknown'))[:120]}")
    if price_row.get("ok") and price_row.get("adj_close") is None:
        quality_flags.append("latest_price_not_present")
    if price_row.get("ok") and price_row.get("previous_adj_close") is None:
        quality_flags.append("previous_price_not_present")
    future_data_risk = bool(close_date and (close_date > trading_date or close_date > config.as_of_date))
    if future_data_risk:
        quality_flags.append("future_data_risk")
    provider_policy = provider_public_policy(MARKET_DATA_PROVIDER)
    snapshot = {
        "schema": MARKET_DATA_SNAPSHOT_SCHEMA,
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": trading_date.isoformat(),
        "source_type": "price_data",
        "source_name": MARKET_DATA_SOURCE_NAME,
        "source_url_or_id": f"price:{MARKET_DATA_PROVIDER}:{item['exchange']}:{item['symbol']}:{trading_date.isoformat()}",
        "provider": MARKET_DATA_PROVIDER,
        "market": market_name_for_exchange(item["exchange"]),
        "currency": market_currency_for_exchange(item["exchange"]),
        "availability_date": sanitize_text(str(price_row.get("close_date") or trading_date.isoformat())),
        "price_status": "ok" if price_row.get("ok") else "missing",
        "latest_price": price_row.get("adj_close") if price_row.get("ok") else None,
        "latest_price_date": sanitize_text(str(price_row.get("close_date") or "")),
        "previous_price": price_row.get("previous_adj_close") if price_row.get("ok") else None,
        "previous_price_date": sanitize_text(str(price_row.get("previous_date") or "")),
        "one_session_change_pct": price_row.get("one_session_change_pct") if price_row.get("ok") else None,
        "quality_flags": dedupe_preserve_order(quality_flags),
        "provider_policy": provider_policy,
        "future_data_risk": future_data_risk,
        "public_safe": True,
    }
    snapshot["snapshot_hash"] = stable_hash({key: value for key, value in snapshot.items() if key != "snapshot_hash"})
    assert_public_safe(snapshot)
    return snapshot


def prior_alaya_unresolved_questions(item: dict[str, str], config: FullAnalystConfig) -> list[str]:
    state_path = config.private_audit_root / "cognition_flywheel" / "full_analyst_memory_events.jsonl"
    if not state_path.exists():
        return ["No prior internal Alaya readback was found for this symbol in the configured state path."]
    knowledge_id = f"full_analyst:{item['exchange']}:{item['symbol']}"
    questions: list[str] = []
    try:
        for record in read_audit_events(state_path):
            if str(record.get("knowledge_id") or "") != knowledge_id:
                continue
            for field in ("evidence_gaps", "watch_conditions", "missing_required_sources"):
                values = record.get(field)
                if isinstance(values, list):
                    questions.extend(sanitize_public_text_value(value, max_chars=260) for value in values if sanitize_public_text_value(value, max_chars=260))
    except Exception:  # noqa: BLE001 - prior memory is helpful but not required for public packet construction.
        return ["Prior internal Alaya readback exists but could not be summarized safely."]
    return dedupe_preserve_order(questions)[-6:] or ["Prior internal Alaya readback had no unresolved public-safe questions."]


def run_research_task_planner(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, config.retries + 2):
        prompt = build_research_task_prompt(item, price_row, config, attempt=attempt, last_error=last_error)
        result = runner.complete(prompt, timeout_seconds=config.per_symbol_timeout_seconds)
        if not result.ok:
            last_error = result.reason or "research_task_runner_failed"
            continue
        try:
            task = sanitize_research_task(parse_model_json(result.text), item=item, price_row=price_row, config=config)
            write_private_json_atomic(
                private_run_dir(config) / "research_tasks" / f"{item['exchange']}_{item['symbol']}.json",
                {
                    "schema": "gotra.full_analyst.private_research_task_attempt.v1",
                    "run_id": config.run_id,
                    "symbol": item["symbol"],
                    "exchange": item["exchange"],
                    "prompt_template_version": prompt_template_for_config(config),
                    "task_hash": task["task_hash"],
                    "public_task": task,
                },
            )
            return task
        except Exception as exc:  # noqa: BLE001 - retry then surface public-safe category.
            last_error = normalize_failure_reason(exc)
    raise RuntimeError(f"research_task_planner_failed:{public_safe_failure_category(last_error)}")


def sanitize_research_task(
    payload: dict[str, Any],
    *,
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
) -> dict[str, Any]:
    forbidden_keys = [key for key in payload if FORBIDDEN_OUTPUT_KEY_RE.match(str(key))]
    if forbidden_keys:
        raise ValueError(f"forbidden_raw_io_keys: {','.join(sorted(forbidden_keys))}")
    required = (
        "schema",
        "selection_reason",
        "trigger_context",
        "research_mission",
        "core_questions",
        "required_sources",
        "must_not_conclude_without",
        "evidence_gap_policy",
        "agent_briefs",
        "reader_boundary",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"missing_required_fields: {','.join(missing)}")
    required_sources = []
    for source in payload.get("required_sources") if isinstance(payload.get("required_sources"), list) else []:
        if not isinstance(source, dict):
            continue
        source_type = sanitize_text(str(source.get("source_type") or "unknown")).lower().replace(" ", "_").replace("-", "_")[:80]
        purpose = sanitize_public_text_value(
            source.get("purpose") or "",
            preferred_keys=("purpose", "summary", "reason", "source_type"),
            max_chars=300,
        )
        if not purpose:
            purpose = V35_REQUIRED_SOURCE_PURPOSES.get(
                source_type,
                f"Review public {source_type} sources needed to resolve the bounded research task or preserve the related evidence gap.",
            )
        required_sources.append(
            {
                "source_type": source_type,
                "purpose": purpose,
                "required": bool(source.get("required", True)),
            }
        )
    if not required_sources:
        required_sources = default_v35_required_sources()
    agent_briefs_raw = payload.get("agent_briefs") if isinstance(payload.get("agent_briefs"), dict) else {}
    agent_briefs = {
        agent_id: sanitize_public_text_value(agent_briefs_raw.get(agent_id) or V3_AGENT_ROLE_LABELS[agent_id], max_chars=500)
        for agent_id in V3_AGENT_IDS
    }
    k_dossier_objectives = sanitize_list(payload.get("k_dossier_objectives"))[:8]
    if is_v40_config(config) and not k_dossier_objectives:
        raise ValueError("research_task_missing_k_dossier_objectives")
    task = {
        "schema": research_task_schema_for_config(config),
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "selection_reason": sanitize_public_text_value(
            payload.get("selection_reason") or "",
            preferred_keys=("why_today", "selection_reason", "reason", "summary", "data_gap"),
            max_chars=700,
        ),
        "trigger_context": sanitize_record(
            payload.get("trigger_context")
            or {
                "price_move": public_price_context(price_row),
                "coverage_status": "ok" if price_row.get("ok") else "data_gap",
            }
        ),
        "research_mission": sanitize_public_text_value(payload.get("research_mission") or "", max_chars=700),
        "core_questions": sanitize_list(payload.get("core_questions"))[:6],
        "required_sources": required_sources[:10],
        "must_not_conclude_without": sanitize_list(payload.get("must_not_conclude_without"))[:8],
        "evidence_gap_policy": sanitize_list(payload.get("evidence_gap_policy"))[:8],
        "k_dossier_objectives": k_dossier_objectives,
        "agent_briefs": agent_briefs,
        "perspective_agent_briefs": {
            agent_id: agent_briefs[agent_id]
            for agent_id in V40_PERSPECTIVE_AGENT_IDS
        },
        "reader_boundary": READER_BOUNDARY,
        "task_status": sanitize_text(str(payload.get("task_status") or "ok"))[:80],
    }
    if len(task["core_questions"]) < 3:
        raise ValueError("research_task_too_generic:core_questions")
    if not task["required_sources"]:
        raise ValueError("research_task_too_generic:required_sources")
    task = neutralize_public_boundary_terms(task)
    task["task_hash"] = stable_hash({key: value for key, value in task.items() if key != "task_hash"})
    assert_public_safe(task)
    return task


def build_evidence_packet(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    research_task: dict[str, Any],
) -> dict[str, Any]:
    trading_date = trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat()
    retrieved_at = utc_now_iso()
    market_data_snapshot = build_market_data_snapshot(item, price_row, config)
    price_status = "fresh" if price_row.get("ok") else "missing"
    evidence_items = [
        {
            "evidence_id": "price_context",
            "source_type": "price_data",
            "source_name": "GOTRA public price coverage row",
            "source_url_or_id": f"price:{item['exchange']}:{item['symbol']}:{trading_date}",
            "publish_timestamp": str(price_row.get("close_date") or trading_date),
            "availability_date": str(price_row.get("close_date") or trading_date),
            "retrieved_at": retrieved_at,
            "retrieval_method": "bounded_public_pipeline_context",
            "freshness_status": price_status,
            "summary": json.dumps(public_price_context(price_row), ensure_ascii=False, sort_keys=True),
            "supports_questions": research_task.get("core_questions", [])[:3],
            "limitations": [] if price_row.get("ok") else [sanitize_text(str(price_row.get("reason") or "price_data_missing"))],
            "public_safe": True,
        },
        {
            "evidence_id": "market_data_snapshot",
            "source_type": "price_data",
            "source_name": MARKET_DATA_SOURCE_NAME,
            "source_url_or_id": market_data_snapshot["source_url_or_id"],
            "publish_timestamp": market_data_snapshot["availability_date"],
            "availability_date": market_data_snapshot["availability_date"],
            "retrieved_at": retrieved_at,
            "retrieval_method": "bounded_public_market_data_snapshot",
            "freshness_status": price_status,
            "summary": json.dumps(
                {
                    "market_data_snapshot_hash": market_data_snapshot["snapshot_hash"],
                    "provider": market_data_snapshot["provider"],
                    "market": market_data_snapshot["market"],
                    "currency": market_data_snapshot["currency"],
                    "price_status": market_data_snapshot["price_status"],
                    "quality_flags": market_data_snapshot["quality_flags"],
                    "future_data_risk": market_data_snapshot["future_data_risk"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            "supports_questions": research_task.get("core_questions", [])[:3],
            "limitations": market_data_snapshot["quality_flags"],
            "public_safe": True,
        },
        {
            "evidence_id": "public_stock_pool_metadata",
            "source_type": "public_stock_pool_metadata",
            "source_name": "GOTRA public research universe",
            "source_url_or_id": "gotra_public_api.research_universe_items",
            "publish_timestamp": sanitize_text(str(item.get("source_date") or config.as_of_date.isoformat())),
            "availability_date": sanitize_text(str(item.get("source_date") or config.as_of_date.isoformat())),
            "retrieved_at": retrieved_at,
            "retrieval_method": "local_public_universe_read",
            "freshness_status": "fresh" if item.get("source_date") else "unknown",
            "summary": sanitize_text(str(item.get("purpose") or f"{item['exchange']}:{item['symbol']} public stock-pool candidate."))[:500],
            "supports_questions": research_task.get("core_questions", [])[:2],
            "limitations": ["Universe metadata is selection context, not issuer fundamental evidence."],
            "public_safe": True,
        },
    ]
    status_path = DEFAULT_STATIC_DIR / "status_full_analyst_evening_hk.json"
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            evidence_items.append(
                {
                    "evidence_id": "current_public_full_analyst_status",
                    "source_type": "current_public_status",
                    "source_name": "public status_full_analyst_evening_hk.json",
                    "source_url_or_id": "/reports/status_full_analyst_evening_hk.json",
                    "publish_timestamp": sanitize_text(str(status.get("finished_at_utc") or status.get("last_heartbeat_utc") or "")),
                    "availability_date": config.as_of_date.isoformat(),
                    "retrieved_at": retrieved_at,
                    "retrieval_method": "public_static_status_read",
                    "freshness_status": "fresh" if status.get("as_of_date") == config.as_of_date.isoformat() else "stale",
                    "summary": json.dumps(
                        {
                            "run_id": status.get("run_id"),
                            "run_status": status.get("run_status"),
                            "symbol_schema": status.get("symbol_schema"),
                            "execution_model": status.get("execution_model"),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "supports_questions": research_task.get("core_questions", [])[:2],
                    "limitations": ["Status artifact is runtime evidence, not issuer-source evidence."],
                    "public_safe": True,
                }
            )
        except Exception:
            pass
    prior_questions = prior_alaya_unresolved_questions(item, config)
    evidence_items.append(
        {
            "evidence_id": "prior_alaya_readback_summary",
            "source_type": "prior_alaya_memory",
            "source_name": "GOTRA internal cognition flywheel readback summary",
            "source_url_or_id": "gotra_internal_cognition_flywheel_readback",
            "publish_timestamp": config.as_of_date.isoformat(),
            "availability_date": config.as_of_date.isoformat(),
            "retrieved_at": retrieved_at,
            "retrieval_method": "internal_public_safe_summary",
            "freshness_status": "unknown",
            "summary": "; ".join(prior_questions[:4]),
            "supports_questions": research_task.get("core_questions", [])[:4],
            "limitations": ["Internal memory summary is audit context, not external issuer evidence."],
            "public_safe": True,
        }
    )
    available_source_types = {str(item.get("source_type") or "") for item in evidence_items}
    required_sources = research_task.get("required_sources") if isinstance(research_task.get("required_sources"), list) else []
    missing_required_sources = [
        {
            "source_type": str(source.get("source_type") or "unknown"),
            "purpose": sanitize_text(str(source.get("purpose") or ""))[:300],
            "reason": "not_available_in_bounded_public_packet",
        }
        for source in required_sources
        if source.get("required") and str(source.get("source_type") or "") not in available_source_types
    ]
    stale_sources = [
        {"evidence_id": str(source.get("evidence_id")), "source_type": str(source.get("source_type"))}
        for source in evidence_items
        if source.get("freshness_status") == "stale"
    ]
    data_gaps = []
    if not price_row.get("ok"):
        data_gaps.append(f"price_data gap: {sanitize_text(str(price_row.get('reason') or 'unknown'))}")
    if market_data_snapshot["future_data_risk"]:
        data_gaps.append("market_data_snapshot future_data_risk: close_date is later than the configured trading/as-of date")
    data_gaps.extend(
        f"missing required {source['source_type']}: {source['purpose']}"
        for source in missing_required_sources
    )
    sources = [
        {
            "source_id": str(source["evidence_id"]),
            "source_type": str(source["source_type"]),
            "source_name": str(source["source_name"]),
            "source_url_or_id": str(source["source_url_or_id"]),
            "retrieved_at": str(source["retrieved_at"]),
            "publish_timestamp": str(source["publish_timestamp"]),
            "availability_date": str(source["availability_date"]),
            "market": item["exchange"],
            "freshness_status": str(source["freshness_status"]),
            "usage_limitations": sanitize_list(source.get("limitations")),
            "public_safe": bool(source.get("public_safe")),
        }
        for source in evidence_items
    ]
    missing_items = [
        {
            "item_type": str(source["source_type"]),
            "purpose": str(source["purpose"]),
            "reason": str(source["reason"]),
        }
        for source in missing_required_sources
    ]
    missing_items.extend(
        {"item_type": "data_gap", "purpose": str(gap), "reason": "recorded_data_gap"}
        for gap in dedupe_preserve_order(data_gaps)[:12]
    )
    future_data_check = not bool(market_data_snapshot["future_data_risk"])
    packet = {
        "schema": evidence_packet_schema_for_config(config),
        "packet_id": f"{config.run_id}:{item['exchange']}:{item['symbol']}:evidence_packet",
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of": config.as_of_date.isoformat(),
        "as_of_date": config.as_of_date.isoformat(),
        "task_hash": research_task["task_hash"],
        "sources": sources,
        "missing_items": missing_items,
        "future_data_check": future_data_check,
        "future_data_check_details": {
            "passed": future_data_check,
            "market_data_snapshot_hash": market_data_snapshot["snapshot_hash"],
            "quality_flags": market_data_snapshot["quality_flags"],
        },
        "market_data_snapshot": market_data_snapshot,
        "market_data_snapshot_hash": market_data_snapshot["snapshot_hash"],
        "evidence_items": evidence_items,
        "missing_required_sources": missing_required_sources,
        "stale_sources": stale_sources,
        "data_gaps": dedupe_preserve_order(data_gaps)[:12],
        "prior_alaya_readback": {"unresolved_questions": prior_questions[:6], "source": "gotra_internal_cognition_flywheel"},
    }
    validate_evidence_packet_contract(packet)
    packet["evidence_packet_hash"] = stable_hash({key: value for key, value in packet.items() if key != "evidence_packet_hash"})
    assert_public_safe(packet)
    return packet


def validate_evidence_packet_contract(packet: dict[str, Any]) -> None:
    required = ("packet_id", "symbol", "as_of", "sources", "missing_items", "future_data_check")
    missing = [field for field in required if field not in packet]
    if missing:
        raise ValueError(f"evidence_packet_missing_required_fields:{','.join(missing)}")
    if not isinstance(packet["sources"], list) or not packet["sources"]:
        raise ValueError("evidence_packet_sources_empty")
    for index, source in enumerate(packet["sources"]):
        if not isinstance(source, dict):
            raise ValueError(f"evidence_packet_source_not_object:{index}")
        for field in ("source_id", "source_type", "source_name", "source_url_or_id", "retrieved_at"):
            if not source.get(field):
                raise ValueError(f"evidence_packet_source_missing_{field}:{index}")
    if not isinstance(packet["missing_items"], list):
        raise ValueError("evidence_packet_missing_items_not_list")
    if not isinstance(packet["future_data_check"], bool):
        raise ValueError("evidence_packet_future_data_check_not_bool")


def build_k_dossier_prompt(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    research_task: dict[str, Any],
    evidence_packet: dict[str, Any],
    *,
    attempt: int,
    last_error: str,
) -> str:
    payload = {
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "required_schema": K_DOSSIER_SCHEMA,
        "required_keys": [
            "schema",
            "run_id",
            "symbol",
            "task_hash",
            "evidence_packet_hash",
            "dossier_summary",
            "deep_findings",
            "source_grounded_observations",
            "key_uncertainties",
            "must_verify_next",
            "evidence_gaps",
            "dossier_hash",
        ],
        "price_coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "research_task": public_v35_dependency_packet({"research_task": research_task}, "k_deep_research")["research_task"],
        "evidence_packet": public_v35_dependency_packet({"evidence_packet": evidence_packet}, "k_deep_research")["evidence_packet"],
        "k_dossier_objectives": research_task.get("k_dossier_objectives", []),
        "must_not_conclude_without": research_task.get("must_not_conclude_without", []),
        "boundary": list(BOUNDARY_LINES),
        "reader_boundary": READER_BOUNDARY,
    }
    retry_note = ""
    if attempt > 1:
        retry_note = f"\nRetry attempt {attempt}. Previous failure: {sanitize_text(last_error)[:160]}."
    return (
        "Return STRICT JSON only. No markdown, no code fences, no commentary.\n"
        "Produce the GOTRA Full Analyst v4 K deep research dossier before F/W/G perspective agents start. "
        "The dossier must be source-grounded to the research_task and evidence_packet, must preserve data_gap and needs_review, "
        "and must not make action, allocation, price-objective, return, performance-proof, or science/public-proof claims.\n"
        f"Input JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}{retry_note}"
    )


def fixture_k_dossier_output(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = sanitize_text(str(payload.get("symbol") or ""))
    exchange = sanitize_text(str(payload.get("exchange") or ""))
    evidence_packet = payload.get("evidence_packet") if isinstance(payload.get("evidence_packet"), dict) else {}
    data_gaps = evidence_packet.get("data_gaps") if isinstance(evidence_packet.get("data_gaps"), list) else []
    return {
        "schema": K_DOSSIER_SCHEMA,
        "run_id": sanitize_text(str(payload.get("run_id") or "")),
        "symbol": symbol,
        "exchange": exchange,
        "task_hash": sanitize_text(str((payload.get("research_task") or {}).get("task_hash") or "")),
        "evidence_packet_hash": sanitize_text(str(evidence_packet.get("evidence_packet_hash") or "")),
        "dossier_summary": f"K dossier for {exchange}:{symbol} maps identity, public-source coverage, missing evidence, and next verification before F/W/G.",
        "deep_findings": [
            "Public stock-pool identity and price coverage are established from supplied bounded context.",
            "Issuer-source and exchange-source freshness must remain visible before stronger research status.",
            "Fixture mode provides structure and hashability but not an external public-source refresh.",
        ],
        "source_grounded_observations": [
            "price_context and public_stock_pool_metadata are present in the evidence packet.",
            "prior_alaya_readback_summary is internal continuity context, not external issuer evidence.",
        ],
        "key_uncertainties": [
            "Required issuer and exchange sources may still be missing from the bounded packet.",
            "Current public events need verification outside fixture mode.",
        ],
        "must_verify_next": [
            "Refresh official issuer reports and exchange announcements.",
            "Confirm whether missing_required_sources can be resolved in the next run.",
        ],
        "evidence_gaps": sanitize_list(data_gaps) or ["K dossier fixture has no live external source refresh."],
        "dossier_hash": "",
    }


def sanitize_k_dossier(
    payload: dict[str, Any],
    *,
    item: dict[str, str],
    config: FullAnalystConfig,
    research_task: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_keys = [key for key in payload if FORBIDDEN_OUTPUT_KEY_RE.match(str(key))]
    if forbidden_keys:
        raise ValueError(f"forbidden_raw_io_keys: {','.join(sorted(forbidden_keys))}")
    required = (
        "schema",
        "dossier_summary",
        "deep_findings",
        "source_grounded_observations",
        "key_uncertainties",
        "must_verify_next",
        "evidence_gaps",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"k_dossier_missing_required_fields:{','.join(missing)}")
    dossier = {
        "schema": K_DOSSIER_SCHEMA,
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "task_hash": research_task["task_hash"],
        "evidence_packet_hash": evidence_packet["evidence_packet_hash"],
        "dossier_summary": sanitize_public_text_value(payload.get("dossier_summary"), max_chars=900),
        "deep_findings": sanitize_list(payload.get("deep_findings"))[:10],
        "source_grounded_observations": sanitize_list(payload.get("source_grounded_observations"))[:10],
        "key_uncertainties": sanitize_list(payload.get("key_uncertainties"))[:10],
        "must_verify_next": sanitize_list(payload.get("must_verify_next"))[:10],
        "evidence_gaps": sanitize_list(payload.get("evidence_gaps"))[:10],
    }
    if not dossier["deep_findings"] or not dossier["must_verify_next"]:
        raise ValueError("k_dossier_too_generic")
    dossier = neutralize_public_boundary_terms(dossier)
    dossier["dossier_hash"] = stable_hash({key: value for key, value in dossier.items() if key != "dossier_hash"})
    assert_public_safe(dossier)
    return dossier


def run_k_dossier(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    research_task: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, config.retries + 2):
        prompt = build_k_dossier_prompt(
            item,
            price_row,
            config,
            research_task,
            evidence_packet,
            attempt=attempt,
            last_error=last_error,
        )
        result = runner.complete(prompt, timeout_seconds=config.per_symbol_timeout_seconds)
        if not result.ok:
            last_error = result.reason or "k_dossier_runner_failed"
            continue
        try:
            dossier = sanitize_k_dossier(
                parse_model_json(result.text),
                item=item,
                config=config,
                research_task=research_task,
                evidence_packet=evidence_packet,
            )
            write_private_json_atomic(
                private_run_dir(config) / "k_dossiers" / f"{item['exchange']}_{item['symbol']}.json",
                dossier,
            )
            return dossier
        except Exception as exc:  # noqa: BLE001 - retry then surface public-safe category.
            last_error = normalize_failure_reason(exc)
    raise RuntimeError(f"k_dossier_failed:{public_safe_failure_category(last_error)}")


def k_dossier_to_agent_output(
    dossier: dict[str, Any],
    *,
    item: dict[str, str],
    config: FullAnalystConfig,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
) -> dict[str, Any]:
    output = {
        "agent_id": "k_deep_research",
        "agent_role": "K deep research dossier; upstream source-grounded research before F/W/G",
        "schema": K_DOSSIER_SCHEMA,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "run_id": config.run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "model": config.model,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION_V40,
        "input_context_hash": stable_hash(
            {
                "task_hash": dossier.get("task_hash"),
                "evidence_packet_hash": dossier.get("evidence_packet_hash"),
            }
        ),
        "output_hash": dossier["dossier_hash"],
        "status": "needs_review" if dossier.get("evidence_gaps") else "ok",
        "findings": [dossier["dossier_summary"], *sanitize_list(dossier.get("deep_findings"))[:6]],
        "evidence_refs": ["price_context", "public_stock_pool_metadata", "prior_alaya_readback_summary"],
        "evidence_gaps": sanitize_list(dossier.get("evidence_gaps")) or ["K dossier reported no evidence gap."],
        "uncertainties": sanitize_list(dossier.get("key_uncertainties")) or ["K dossier uncertainty not specified."],
        "watch_conditions": sanitize_list(dossier.get("must_verify_next")) or ["Next verified public update."],
        "boundary": "research content only; does not constitute investment advice",
        "k_deep_research_dossier": dossier,
    }
    assert_public_safe(output)
    return output


def is_v35_config(config: FullAnalystConfig) -> bool:
    return bool(config.v35_research_system or config.execution_model == EXECUTION_MODEL_V35)


def is_v40_config(config: FullAnalystConfig) -> bool:
    return bool(config.v40_cognition_flywheel or config.execution_model == EXECUTION_MODEL_V40)


def has_research_task_system(config: FullAnalystConfig) -> bool:
    return is_v35_config(config) or is_v40_config(config)


def is_v3_config(config: FullAnalystConfig) -> bool:
    return bool(
        config.v3_independent_agents
        or config.execution_model in {EXECUTION_MODEL_V3, EXECUTION_MODEL_V35, EXECUTION_MODEL_V40}
    )


def symbol_schema_for_config(config: FullAnalystConfig) -> str:
    if is_v40_config(config):
        return SYMBOL_SCHEMA_V40
    if is_v35_config(config):
        return SYMBOL_SCHEMA_V35
    return SYMBOL_SCHEMA_V3 if is_v3_config(config) else SYMBOL_SCHEMA


def prompt_template_for_config(config: FullAnalystConfig) -> str:
    if is_v40_config(config):
        return PROMPT_TEMPLATE_VERSION_V40
    if is_v35_config(config):
        return PROMPT_TEMPLATE_VERSION_V35
    return PROMPT_TEMPLATE_VERSION_V3 if is_v3_config(config) else PROMPT_TEMPLATE_VERSION


def methodology_for_config(config: FullAnalystConfig) -> str:
    if is_v40_config(config):
        return METHODOLOGY_VERSION_V40
    if is_v35_config(config):
        return METHODOLOGY_VERSION_V35
    return METHODOLOGY_VERSION_V3 if is_v3_config(config) else METHODOLOGY_VERSION


def execution_model_for_config(config: FullAnalystConfig) -> str:
    if is_v40_config(config):
        return EXECUTION_MODEL_V40
    if is_v35_config(config):
        return EXECUTION_MODEL_V35
    return EXECUTION_MODEL_V3 if is_v3_config(config) else EXECUTION_MODEL


def research_task_schema_for_config(config: FullAnalystConfig) -> str:
    return RESEARCH_TASK_SCHEMA_V2 if is_v40_config(config) else RESEARCH_TASK_SCHEMA


def evidence_packet_schema_for_config(config: FullAnalystConfig) -> str:
    return EVIDENCE_PACKET_SCHEMA_V2 if is_v40_config(config) else EVIDENCE_PACKET_SCHEMA


def agent_output_schema_for_config(config: FullAnalystConfig, agent_id: str) -> str:
    if is_v40_config(config):
        if agent_id in V40_PERSPECTIVE_AGENT_IDS:
            return PERSPECTIVE_AGENT_SCHEMA_V4
        if agent_id == "chairman_synthesis":
            return CHAIRMAN_SCHEMA_V4
        if agent_id == "red_team_audit":
            return RED_TEAM_SCHEMA_V4
        if agent_id == "k_deep_research":
            return K_DOSSIER_SCHEMA
    return AGENT_OUTPUT_SCHEMA_V3


def alaya_event_schema_for_payload(payload: dict[str, Any]) -> str:
    if payload.get("schema") == SYMBOL_SCHEMA_V40:
        return ALAYA_EVENT_SCHEMA_V40
    if payload.get("schema") == SYMBOL_SCHEMA_V35:
        return ALAYA_EVENT_SCHEMA_V35
    return ALAYA_EVENT_SCHEMA_V3 if payload.get("schema") == SYMBOL_SCHEMA_V3 else ALAYA_EVENT_SCHEMA


def agent_statuses(payload: dict[str, Any]) -> dict[str, str]:
    outputs = payload.get("agent_outputs") if isinstance(payload.get("agent_outputs"), dict) else {}
    return {
        agent_id: sanitize_text(str((outputs.get(agent_id) or {}).get("status") or "not_reported"))[:80]
        for agent_id in V3_AGENT_IDS
    }


def red_team_verdict(payload: dict[str, Any]) -> str:
    red_team = (payload.get("agent_outputs") or {}).get("red_team_audit") if isinstance(payload.get("agent_outputs"), dict) else {}
    verdict = ""
    if isinstance(red_team, dict):
        verdict = sanitize_text(str(red_team.get("final_red_team_verdict") or red_team.get("red_team_verdict") or ""))[:80]
    allowed = {"pass", "needs_review", "blocked", "pass_with_review_items", "data_gap", "blocked_engineering_only_if_real"}
    return verdict if verdict in allowed else "needs_review"


def sanitize_public_value(value: Any, *, max_text_length: int = 900) -> Any:
    if isinstance(value, dict):
        return {
            sanitize_text(str(key))[:80]: sanitize_public_value(item, max_text_length=max_text_length)
            for key, item in value.items()
            if str(key).strip()
        }
    if isinstance(value, list):
        return [sanitize_public_value(item, max_text_length=max_text_length) for item in value if str(item).strip()][:12]
    if value is None:
        return ""
    return sanitize_text(str(value))[:max_text_length]


def sanitize_record(value: Any) -> dict[str, Any]:
    sanitized = sanitize_public_value(value)
    return sanitized if isinstance(sanitized, dict) else {"summary": sanitize_text(str(sanitized or ""))[:900]}


def section_summary(section: Any, fallback: str) -> str:
    if isinstance(section, dict):
        for key in ("summary", "thesis", "view", "decision_frame", "uncertainty"):
            value = section.get(key)
            if value:
                return sanitize_text(str(value))[:500]
        values = [sanitize_text(str(value))[:220] for value in section.values() if str(value).strip()]
        if values:
            return "; ".join(values)[:500]
    if isinstance(section, list) and section:
        return sanitize_text(str(section[0]))[:500]
    if section:
        return sanitize_text(str(section))[:500]
    return fallback


def section_list(section: Any, fallback: str) -> list[str]:
    if isinstance(section, dict):
        values: list[str] = []
        for key, value in section.items():
            if isinstance(value, list):
                values.extend(sanitize_text(str(item))[:320] for item in value if str(item).strip())
            elif isinstance(value, dict):
                values.append(section_summary(value, ""))
            elif str(value).strip():
                label = str(key).replace("_", " ")
                values.append(f"{label}: {sanitize_text(str(value))[:260]}")
        return [value for value in values if value][:8] or [fallback]
    if isinstance(section, list):
        return sanitize_list(section) or [fallback]
    if section:
        return [sanitize_text(str(section))[:500]]
    return [fallback]


def normalize_research_status(value: Any, *, price_coverage_status: str) -> str:
    raw = sanitize_text(str(value or "")).lower()
    allowed = {"candidate", "watch", "avoid", "needs_review", "data_gap", "high_uncertainty"}
    if price_coverage_status == "data_gap":
        return raw if raw in {"needs_review", "data_gap"} else "data_gap"
    return raw if raw in allowed else "watch"


def v1_payload_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SYMBOL_SCHEMA,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "execution_model": EXECUTION_MODEL,
        "symbol": payload.get("symbol", ""),
        "exchange": payload.get("exchange", ""),
        "provider_ticker": payload.get("provider_ticker", ""),
        "as_of_date": payload.get("as_of_date", ""),
        "price_coverage_status": payload.get("price_coverage_status", "data_gap"),
        "research_context": {
            "scope": payload.get("research_summary", ""),
            "key_updates": payload.get("key_updates", []),
        },
        "k_deep_research": {"summary": payload.get("research_summary", "")},
        "f_partner_view": {"summary": "; ".join(sanitize_list(payload.get("positive_case")))},
        "w_partner_view": {"summary": "; ".join(sanitize_list(payload.get("negative_case")))},
        "g_partner_view": {"summary": "; ".join(sanitize_list(payload.get("risk_factors")))},
        "chairman_synthesis": {"summary": payload.get("research_summary", "")},
        "red_team_audit": {"summary": "; ".join(sanitize_list(payload.get("red_team_review")))},
        "evidence_gaps": sanitize_list(payload.get("risk_factors")),
        "watch_conditions": sanitize_list(payload.get("watch_items")),
        "research_status": "data_gap" if payload.get("price_coverage_status") == "data_gap" else "watch",
        "confidence_boundary": "Converted from v1 public-safe summary; confidence remains bounded by source freshness.",
        "source_notes": sanitize_list(payload.get("source_notes")),
        "reader_boundary": READER_BOUNDARY,
    }


def build_alaya_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") in {SYMBOL_SCHEMA_V3, SYMBOL_SCHEMA_V35, SYMBOL_SCHEMA_V40}:
        is_v40_payload = payload.get("schema") == SYMBOL_SCHEMA_V40
        is_v35_payload = payload.get("schema") == SYMBOL_SCHEMA_V35
        public_payload_hash_basis = {
            "schema": payload["schema"],
            "run_id": payload["run_id"],
            "symbol": payload["symbol"],
            "exchange": payload["exchange"],
            "as_of_date": payload["as_of_date"],
            "research_status": payload["research_status"],
            "judge_status": payload["judge_status"],
            "research_task_hash": payload.get("research_task_hash", ""),
            "evidence_packet_hash": payload.get("evidence_packet_hash", ""),
            "market_data_snapshot_hash": payload.get("market_data_snapshot_hash", ""),
            "k_dossier_hash": payload.get("k_dossier_hash", ""),
            "agent_hashes": payload["agent_hashes"],
            "agent_statuses": agent_statuses(payload),
            "research_quality_gate_hash": payload.get("research_quality_gate_hash", ""),
            "knowledge_gate_hash": payload.get("knowledge_gate_hash", ""),
            "research_signal_hash": payload.get("research_signal_hash", ""),
            "publication_decision_hash": payload.get("publication_decision_hash", ""),
            "evidence_gaps": payload["evidence_gaps"],
            "watch_conditions": payload["watch_conditions"],
        }
        public_payload = {
            "schema": ALAYA_EVENT_SCHEMA_V40 if is_v40_payload else ALAYA_EVENT_SCHEMA_V35 if is_v35_payload else ALAYA_EVENT_SCHEMA_V3,
            "event_schema": ALAYA_EVENT_SCHEMA_V40 if is_v40_payload else ALAYA_EVENT_SCHEMA_V35 if is_v35_payload else ALAYA_EVENT_SCHEMA_V3,
            "gotra_schema": payload["schema"],
            "run_id": payload["run_id"],
            "symbol": payload["symbol"],
            "exchange": payload["exchange"],
            "as_of_date": payload["as_of_date"],
            "trading_date": payload["trading_date"],
            "methodology_version": payload["methodology_version"],
            "prompt_template_version": payload["prompt_template_version"],
            "research_task_hash": payload.get("research_task_hash", ""),
            "evidence_packet_hash": payload.get("evidence_packet_hash", ""),
            "market_data_snapshot_hash": payload.get("market_data_snapshot_hash", ""),
            "k_dossier_hash": payload.get("k_dossier_hash", ""),
            "research_packet_hash": payload.get("research_packet_hash", ""),
            "public_payload_hash": stable_hash(public_payload_hash_basis),
            "judge_status": payload["judge_status"],
            "price_coverage_status": payload["price_coverage_status"],
            "execution_model": payload["execution_model"],
            "agent_hashes": payload["agent_hashes"],
            "agent_timings": payload["agent_timings"],
            "agent_statuses": public_payload_hash_basis["agent_statuses"],
            "chairman_hash": payload["agent_hashes"].get("chairman_synthesis", ""),
            "red_team_hash": payload["agent_hashes"].get("red_team_audit", ""),
            "red_team_verdict": red_team_verdict(payload),
            "research_quality_gate_hash": payload.get("research_quality_gate_hash", ""),
            "knowledge_gate_hash": payload.get("knowledge_gate_hash", ""),
            "research_signal_hash": payload.get("research_signal_hash", ""),
            "publication_decision_hash": payload.get("publication_decision_hash", ""),
            "knowledge_persistence": payload.get("knowledge_persistence", ""),
            "unresolved_questions": payload.get("unresolved_questions", []),
            "missing_required_sources": payload.get("missing_required_sources", []),
            "evidence_gaps": payload["evidence_gaps"],
            "watch_conditions": payload["watch_conditions"],
            "research_status": payload["research_status"],
            "public_summary": payload["public_summary"],
            "reader_boundary": payload["reader_boundary"],
            "boundary_policy": "public-safe research only; no trade instruction, allocation guidance, price objective, promised outcome, raw provider I/O, or secrets",
            "boundary": payload["boundary"],
        }
        if is_v40_payload:
            public_payload["cognition_flywheel_layer"] = METHODOLOGY_VERSION_V40
            public_payload["reader_boundary_gate_hash"] = payload.get("reader_boundary_gate_hash", "")
            public_payload["research_quality_gate"] = payload.get("research_quality_gate", {})
            public_payload["knowledge_gate"] = payload.get("knowledge_gate", {})
            public_payload["research_signal"] = payload.get("research_signal", {})
            public_payload["publication_decision"] = payload.get("publication_decision", {})
            public_payload["agent_research_signal_hashes"] = payload.get("agent_research_signal_hashes", {})
            public_payload["k_dossier_schema"] = K_DOSSIER_SCHEMA
            public_payload["perspective_agent_schema"] = PERSPECTIVE_AGENT_SCHEMA_V4
            public_payload["chairman_schema"] = CHAIRMAN_SCHEMA_V4
            public_payload["red_team_schema"] = RED_TEAM_SCHEMA_V4
            public_payload["research_signal_schema"] = RESEARCH_SIGNAL_SCHEMA
            public_payload["publication_decision_schema"] = PUBLICATION_DECISION_SCHEMA
        if is_v35_payload:
            public_payload["cognition_flywheel_layer"] = "full_analyst_research_task_evidence_agents"
        assert_public_safe(public_payload)
        return public_payload
    public_payload_hash_basis = {
        "schema": SYMBOL_SCHEMA,
        "run_id": payload["run_id"],
        "symbol": payload["symbol"],
        "exchange": payload["exchange"],
        "as_of_date": payload["as_of_date"],
        "research_status": payload["research_status"],
        "market_data_snapshot_hash": payload.get("market_data_snapshot_hash", ""),
        "agent_outputs": {
            "k_deep_research": payload["k_deep_research"],
            "f_partner_view": payload["f_partner_view"],
            "w_partner_view": payload["w_partner_view"],
            "g_partner_view": payload["g_partner_view"],
            "chairman_synthesis": payload["chairman_synthesis"],
            "red_team_audit": payload["red_team_audit"],
        },
        "evidence_gaps": payload["evidence_gaps"],
        "watch_conditions": payload["watch_conditions"],
    }
    public_payload = {
        "schema": ALAYA_EVENT_SCHEMA,
        "event_schema": ALAYA_EVENT_SCHEMA,
        "gotra_schema": SYMBOL_SCHEMA,
        "run_id": payload["run_id"],
        "symbol": payload["symbol"],
        "exchange": payload["exchange"],
        "as_of_date": payload["as_of_date"],
        "trading_date": payload["trading_date"],
        "methodology_version": payload["methodology_version"],
        "prompt_template_version": payload["prompt_template_version"],
        "prompt_hash": payload.get("prompt_hash", ""),
        "market_data_snapshot_hash": payload.get("market_data_snapshot_hash", ""),
        "research_packet_hash": payload.get("research_packet_hash", ""),
        "public_payload_hash": stable_hash(public_payload_hash_basis),
        "judge_status": payload["judge_status"],
        "price_coverage_status": payload["price_coverage_status"],
        "execution_model": payload["execution_model"],
        "agent_outputs": public_payload_hash_basis["agent_outputs"],
        "evidence_gaps": payload["evidence_gaps"],
        "watch_conditions": payload["watch_conditions"],
        "research_status": payload["research_status"],
        "confidence_boundary": payload["confidence_boundary"],
        "source_notes": payload["source_notes"],
        "reader_boundary": payload["reader_boundary"],
        "boundary_policy": "public-safe research only; no trade instruction, allocation guidance, price objective, promised outcome, raw provider I/O, or secrets",
        "boundary": payload["boundary"],
    }
    assert_public_safe(public_payload)
    return public_payload


def public_dependency_packet(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        agent_id: {
            "status": output.get("status"),
            "output_hash": output.get("output_hash"),
            "findings": output.get("findings", [])[:4],
            "evidence_gaps": output.get("evidence_gaps", [])[:4],
            "watch_conditions": output.get("watch_conditions", [])[:4],
            **({"research_status": output.get("research_status")} if output.get("research_status") else {}),
            **({"final_red_team_verdict": output.get("final_red_team_verdict")} if output.get("final_red_team_verdict") else {}),
        }
        for agent_id, output in outputs.items()
    }


def public_v35_dependency_packet(dependencies: dict[str, Any], agent_id: str) -> dict[str, Any]:
    research_task = dependencies.get("research_task") if isinstance(dependencies.get("research_task"), dict) else {}
    evidence_packet = dependencies.get("evidence_packet") if isinstance(dependencies.get("evidence_packet"), dict) else {}
    k_dossier = (
        dependencies.get("k_deep_research_dossier")
        if isinstance(dependencies.get("k_deep_research_dossier"), dict)
        else {}
    )
    prior_alaya = dependencies.get("prior_alaya_readback") if isinstance(dependencies.get("prior_alaya_readback"), dict) else {}
    agent_outputs = dependencies.get("agent_outputs") if isinstance(dependencies.get("agent_outputs"), dict) else {
        key: value for key, value in dependencies.items() if key in V3_AGENT_IDS and isinstance(value, dict)
    }
    agent_briefs = research_task.get("agent_briefs") if isinstance(research_task.get("agent_briefs"), dict) else {}
    evidence_items = evidence_packet.get("evidence_items") if isinstance(evidence_packet.get("evidence_items"), list) else []
    public_task = {
        "schema": research_task.get("schema"),
        "task_hash": research_task.get("task_hash"),
        "selection_reason": research_task.get("selection_reason"),
        "research_mission": research_task.get("research_mission"),
        "core_questions": research_task.get("core_questions", [])[:6],
        "required_sources": research_task.get("required_sources", [])[:10],
        "must_not_conclude_without": research_task.get("must_not_conclude_without", [])[:8],
        "evidence_gap_policy": research_task.get("evidence_gap_policy", [])[:8],
    }
    public_packet = {
        "schema": evidence_packet.get("schema"),
        "task_hash": evidence_packet.get("task_hash"),
        "evidence_packet_hash": evidence_packet.get("evidence_packet_hash"),
        "market_data_snapshot_hash": evidence_packet.get("market_data_snapshot_hash", ""),
        "market_data_snapshot": evidence_packet.get("market_data_snapshot", {}),
        "evidence_items": [
            {
                "evidence_id": item.get("evidence_id"),
                "source_type": item.get("source_type"),
                "source_name": item.get("source_name"),
                "freshness_status": item.get("freshness_status"),
                "summary": item.get("summary"),
                "limitations": item.get("limitations", [])[:4],
            }
            for item in evidence_items[:8]
            if isinstance(item, dict)
        ],
        "missing_required_sources": evidence_packet.get("missing_required_sources", [])[:8],
        "stale_sources": evidence_packet.get("stale_sources", [])[:8],
        "data_gaps": evidence_packet.get("data_gaps", [])[:8],
    }
    public_k_dossier = {
        "schema": k_dossier.get("schema"),
        "dossier_hash": k_dossier.get("dossier_hash"),
        "task_hash": k_dossier.get("task_hash"),
        "evidence_packet_hash": k_dossier.get("evidence_packet_hash"),
        "dossier_summary": k_dossier.get("dossier_summary"),
        "deep_findings": k_dossier.get("deep_findings", [])[:8],
        "source_grounded_observations": k_dossier.get("source_grounded_observations", [])[:8],
        "key_uncertainties": k_dossier.get("key_uncertainties", [])[:8],
        "must_verify_next": k_dossier.get("must_verify_next", [])[:8],
        "evidence_gaps": k_dossier.get("evidence_gaps", [])[:8],
    }
    output = {
        "research_task": sanitize_public_value(public_task, max_text_length=700),
        "evidence_packet": sanitize_public_value(public_packet, max_text_length=700),
        "k_deep_research_dossier": sanitize_public_value(public_k_dossier, max_text_length=700) if k_dossier else {},
        "k_dossier_hash": k_dossier.get("dossier_hash", ""),
        "prior_alaya_readback": sanitize_public_value(prior_alaya, max_text_length=500),
        "agent_brief": sanitize_text(str(agent_briefs.get(agent_id) or V3_AGENT_ROLE_LABELS.get(agent_id, agent_id)))[:500],
        "required_questions": research_task.get("core_questions", [])[:6],
        "must_not_conclude_without": research_task.get("must_not_conclude_without", [])[:8],
    }
    if agent_outputs:
        output["agent_outputs"] = public_dependency_packet(agent_outputs)
    return output


def run_v3_agent(
    agent_id: str,
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    *,
    dependencies: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    last_error = ""
    last_output: dict[str, Any] | None = None
    public_safety_triggers: list[str] = []
    for attempt in range(1, config.retries + 2):
        started_at = utc_now_iso()
        started = time.monotonic()
        prompt, input_context_hash = build_v3_agent_prompt(
            agent_id,
            item,
            price_row,
            config,
            dependencies=dependencies or {},
            attempt=attempt,
            last_error=last_error,
        )
        prompt_hash = stable_hash({"prompt": prompt})
        private_record: dict[str, Any] = {
            "schema": "gotra.full_analyst.private_agent_attempt.v3",
            "run_id": config.run_id,
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "agent_id": agent_id,
            "attempt": attempt,
            "prompt_template_version": prompt_template_for_config(config),
            "prompt_hash": prompt_hash,
            "prompt_text": scrub_secret_text(prompt),
            "input_context_hash": input_context_hash,
            "model": config.model,
            "reasoning_effort": config.reasoning_effort,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "status": "failed",
            "failure_reason": "",
        }
        result = runner.complete(prompt, timeout_seconds=config.per_symbol_timeout_seconds)
        finished_at = utc_now_iso()
        duration = time.monotonic() - started
        private_record["stdout_bytes"] = result.stdout_bytes
        private_record["stderr_bytes"] = result.stderr_bytes
        private_record["returncode"] = result.returncode
        if not result.ok:
            last_error = result.reason or "runner_failed"
            trigger = public_safe_trigger_label(last_error)
            if trigger and trigger not in public_safety_triggers:
                public_safety_triggers.append(trigger)
            last_output = v3_agent_failure_record(
                agent_id=agent_id,
                item=item,
                config=config,
                input_context_hash=input_context_hash,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                reason=last_error,
                retry_count=max(0, attempt - 1),
                public_safety_triggers=public_safety_triggers,
            )
            private_record["failure_reason"] = public_safe_failure_category(last_error)
            private_record["retry_count"] = max(0, attempt - 1)
            private_record["public_safety_triggers"] = public_safety_triggers
            private_record["public_output"] = last_output
            write_v3_agent_attempt_private_record(config, item, agent_id, attempt, private_record)
            write_v3_agent_private_record(config, item, agent_id, private_record)
            continue
        try:
            output = sanitize_v3_agent_output(
                parse_model_json(result.text),
                agent_id=agent_id,
                item=item,
                config=config,
                input_context_hash=input_context_hash,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
            )
            output["retry_count"] = max(0, attempt - 1)
            output["public_safety_triggers"] = list(public_safety_triggers)
            output["output_hash"] = v3_agent_output_hash(output)
            assert_public_safe(output)
            private_record["status"] = "success"
            private_record["retry_count"] = max(0, attempt - 1)
            private_record["public_safety_triggers"] = public_safety_triggers
            private_record["public_output"] = output
            write_v3_agent_attempt_private_record(config, item, agent_id, attempt, private_record)
            write_v3_agent_private_record(config, item, agent_id, private_record)
            return output
        except Exception as exc:  # noqa: BLE001 - retry then preserve failed independent agent record.
            last_error = normalize_failure_reason(exc)
            trigger = public_safe_trigger_label(last_error)
            if trigger and trigger not in public_safety_triggers:
                public_safety_triggers.append(trigger)
            last_output = v3_agent_failure_record(
                agent_id=agent_id,
                item=item,
                config=config,
                input_context_hash=input_context_hash,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                reason=last_error,
                retry_count=max(0, attempt - 1),
                public_safety_triggers=public_safety_triggers,
            )
            private_record["failure_reason"] = last_output["failure_reason"]
            private_record["retry_count"] = max(0, attempt - 1)
            private_record["public_safety_triggers"] = public_safety_triggers
            private_record["public_output"] = last_output
            write_v3_agent_attempt_private_record(config, item, agent_id, attempt, private_record)
            write_v3_agent_private_record(config, item, agent_id, private_record)
            continue
    if last_output is None:
        raise RuntimeError("v3_agent_retry_loop_exhausted_without_output")
    return last_output


def run_v3_kfwg_agents(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    *,
    base_dependencies: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    dependencies = base_dependencies or {}
    if config.agent_concurrency == 1:
        return {
            agent_id: run_v3_agent(agent_id, item, price_row, config, runner, dependencies=dependencies)
            for agent_id in V3_KFWG_AGENT_IDS
        }
    outputs: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(config.agent_concurrency, len(V3_KFWG_AGENT_IDS))) as executor:
        futures = {
            executor.submit(run_v3_agent, agent_id, item, price_row, config, runner, dependencies=dependencies): agent_id
            for agent_id in V3_KFWG_AGENT_IDS
        }
        for future in as_completed(futures):
            agent_id = futures[future]
            outputs[agent_id] = future.result()
    return {agent_id: outputs[agent_id] for agent_id in V3_KFWG_AGENT_IDS}


def run_v40_perspective_agents(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    *,
    base_dependencies: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if config.agent_concurrency == 1:
        return {
            agent_id: run_v3_agent(agent_id, item, price_row, config, runner, dependencies=base_dependencies)
            for agent_id in V40_PERSPECTIVE_AGENT_IDS
        }
    outputs: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(config.agent_concurrency, len(V40_PERSPECTIVE_AGENT_IDS))) as executor:
        futures = {
            executor.submit(run_v3_agent, agent_id, item, price_row, config, runner, dependencies=base_dependencies): agent_id
            for agent_id in V40_PERSPECTIVE_AGENT_IDS
        }
        for future in as_completed(futures):
            agent_id = futures[future]
            outputs[agent_id] = future.result()
    return {agent_id: outputs[agent_id] for agent_id in V40_PERSPECTIVE_AGENT_IDS}


def v3_section_list(output: dict[str, Any], fallback: str) -> list[str]:
    values = []
    values.extend(sanitize_list(output.get("findings")))
    values.extend([f"evidence gap: {item}" for item in sanitize_list(output.get("evidence_gaps"))[:3]])
    return values[:8] or [fallback]


def build_research_quality_gate(
    *,
    price_coverage_status: str,
    missing_required_sources: list[dict[str, Any]],
    failed_agents: list[str],
    chairman: dict[str, Any],
    red_team: dict[str, Any],
    evidence_gaps: list[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    if failed_agents:
        reasons.append(f"engineering agent failures: {','.join(failed_agents)}")
    if price_coverage_status == "data_gap":
        reasons.append("price coverage is data_gap")
    if missing_required_sources:
        reasons.append("missing required public sources remain visible")
    red_verdict = sanitize_text(str(red_team.get("final_red_team_verdict") or "needs_review")).lower()
    if red_verdict in {"data_gap", "needs_review", "pass_with_review_items"}:
        reasons.append(f"red-team audit verdict is {red_verdict}; audit is input, not Judge")
    if evidence_gaps:
        reasons.append("evidence gaps remain visible to reader")
    engineering_blocker = bool(failed_agents or red_verdict == "blocked_engineering_only_if_real")
    if engineering_blocker:
        research_status = "high_uncertainty"
        quality_verdict = "blocked"
        publish_with_boundary = False
    elif price_coverage_status == "data_gap":
        research_status = "data_gap"
        quality_verdict = "needs_review"
        publish_with_boundary = True
    elif missing_required_sources or red_verdict in {"needs_review", "pass_with_review_items", "data_gap"}:
        research_status = "needs_review"
        quality_verdict = "pass_with_review_items"
        publish_with_boundary = True
    else:
        research_status = normalize_research_status(
            chairman.get("research_status_proposal") or chairman.get("research_status") or "watch",
            price_coverage_status=price_coverage_status,
        )
        quality_verdict = "pass"
        publish_with_boundary = True
    gate = {
        "schema": RESEARCH_QUALITY_GATE_SCHEMA,
        "research_status": research_status,
        "quality_verdict": quality_verdict,
        "reasons": dedupe_preserve_order(reasons)[:10] or ["research object passed with public boundary"],
        "publish_with_boundary": publish_with_boundary,
        "engineering_blocker": engineering_blocker,
        "red_team_is_judge": False,
    }
    gate["gate_hash"] = stable_hash({key: value for key, value in gate.items() if key != "gate_hash"})
    assert_public_safe(gate)
    return gate


def build_knowledge_gate(
    *,
    research_quality_gate: dict[str, Any],
    evidence_gaps: list[str],
    watch_conditions: list[str],
    chairman: dict[str, Any],
    red_team: dict[str, Any],
) -> dict[str, Any]:
    quality_verdict = str(research_quality_gate.get("quality_verdict") or "needs_review")
    research_status = str(research_quality_gate.get("research_status") or "needs_review")
    if research_quality_gate.get("engineering_blocker") or quality_verdict == "blocked":
        persistence = "do_not_persist"
    elif research_status == "data_gap":
        persistence = "temporary_observation"
    elif quality_verdict == "pass_with_review_items":
        persistence = "persist_with_limitations"
    elif quality_verdict == "pass":
        persistence = "persist"
    else:
        persistence = "temporary_observation"
    unresolved = dedupe_preserve_order(
        sanitize_list(chairman.get("unresolved_questions"))
        + sanitize_list(red_team.get("counter_evidence_needed"))
        + evidence_gaps
    )[:12]
    future_tasks = dedupe_preserve_order(sanitize_list(chairman.get("next_verification_steps")) + watch_conditions)[:12]
    gate = {
        "schema": KNOWLEDGE_GATE_SCHEMA,
        "knowledge_persistence": persistence,
        "knowledge_items_to_persist": [
            "research_status",
            "evidence_gap_memory",
            "chairman_unresolved_questions",
            "red_team_counter_evidence_needed",
        ]
        if persistence != "do_not_persist"
        else [],
        "unresolved_questions": unresolved or ["No unresolved question was reported."],
        "future_research_tasks": future_tasks or ["Re-run with refreshed public evidence."],
        "evidence_gap_memory": evidence_gaps[:12],
        "confidence_boundary": sanitize_public_text_value(
            chairman.get("confidence_boundary") or "Knowledge persistence is bounded by public evidence freshness.",
            max_chars=500,
        ),
    }
    gate = neutralize_public_boundary_terms(gate)
    gate["gate_hash"] = stable_hash({key: value for key, value in gate.items() if key != "gate_hash"})
    assert_public_safe(gate)
    return gate


def build_reader_boundary_gate(*, research_quality_gate: dict[str, Any], red_team: dict[str, Any]) -> dict[str, Any]:
    gate = {
        "status": "pass",
        "visible_boundary": [
            "research only",
            "not investment advice",
            "not trading signal",
            "no target price",
            "no position sizing",
            "no return promise",
        ],
        "does_not_hide_research_content": True,
        "data_gap_visible": True,
        "needs_review_visible": True,
        "red_team_visible": True,
        "red_team_role": red_team.get("red_team_role") or "audit_not_judge",
        "research_quality_verdict": research_quality_gate.get("quality_verdict"),
    }
    gate = neutralize_public_boundary_terms(gate)
    gate["gate_hash"] = stable_hash({key: value for key, value in gate.items() if key != "gate_hash"})
    assert_public_safe(gate)
    return gate


RESEARCH_SIGNAL_FORBIDDEN_FRAGMENTS = (
    "b" + "uy recommendation",
    "s" + "ell recommendation",
    "h" + "old recommendation",
    "target " + "price",
    "price " + "target",
    "position " + "sizing",
    "return " + "promise",
    "\u5efa\u8bae\u4e70\u5165",
    "\u5efa\u8bae\u5356\u51fa",
    "\u5fc5\u6da8",
    "\u7a33\u8d5a",
)


def research_signal_review_due_at(config: FullAnalystConfig, window_days: int) -> str:
    return (config.as_of_date + timedelta(days=window_days)).isoformat()


def research_signal_confidence(research_quality_gate: dict[str, Any] | None, evidence_gaps: list[str]) -> str:
    verdict = str((research_quality_gate or {}).get("quality_verdict") or "").lower()
    status = str((research_quality_gate or {}).get("research_status") or "").lower()
    if verdict == "pass" and not evidence_gaps:
        return "medium"
    if status in {"data_gap", "high_uncertainty"}:
        return "low"
    return "needs_review"


def research_signal_evidence_ids(evidence_packet: dict[str, Any]) -> list[str]:
    ids = [
        sanitize_text(str(item.get("evidence_id") or item.get("source_id") or ""))[:160]
        for item in evidence_packet.get("evidence_items", [])
        if isinstance(item, dict)
    ]
    return dedupe_preserve_order(ids)[:12]


def assert_research_signal_no_forbidden_terms(signal: dict[str, Any]) -> None:
    text = normalize_negated_boundary_text(json.dumps(signal, ensure_ascii=False, sort_keys=True)).lower()
    for fragment in RESEARCH_SIGNAL_FORBIDDEN_FRAGMENTS:
        if fragment.lower() in text:
            raise ValueError("[BLOCKED: 合规禁词] research_signal_forbidden_wording")
    assert_public_safe(signal)


def validate_research_signal_contract(signal: dict[str, Any]) -> None:
    required = (
        "signal_id",
        "symbol",
        "hypothesis",
        "confidence",
        "evidence_ids",
        "counter_evidence",
        "uncertainty",
        "window_days",
        "review_due_at",
    )
    missing = [field for field in required if field not in signal]
    if missing:
        raise ValueError(f"research_signal_missing_required_fields:{','.join(missing)}")
    if not sanitize_text(str(signal.get("signal_id") or "")):
        raise ValueError("research_signal_missing_signal_id")
    if not sanitize_text(str(signal.get("symbol") or "")):
        raise ValueError("research_signal_missing_symbol")
    if not sanitize_text(str(signal.get("hypothesis") or "")):
        raise ValueError("research_signal_missing_hypothesis")
    if not isinstance(signal.get("evidence_ids"), list) or not signal["evidence_ids"]:
        raise ValueError("research_signal_empty_evidence_ids")
    if not isinstance(signal.get("counter_evidence"), list) or not signal["counter_evidence"]:
        raise ValueError("research_signal_empty_counter_evidence")
    if not isinstance(signal.get("uncertainty"), list) or not signal["uncertainty"]:
        raise ValueError("research_signal_empty_uncertainty")
    if not isinstance(signal.get("window_days"), int) or int(signal["window_days"]) <= 0:
        raise ValueError("research_signal_invalid_window_days")
    try:
        date.fromisoformat(str(signal.get("review_due_at") or ""))
    except ValueError as exc:
        raise ValueError("research_signal_invalid_review_due_at") from exc
    for field in ("evidence_packet_hash", "market_data_snapshot_hash", "evidence_packet_id"):
        if not sanitize_text(str(signal.get(field) or "")):
            raise ValueError(f"research_signal_missing_{field}")
    assert_research_signal_no_forbidden_terms(signal)


def build_research_signal(
    *,
    item: dict[str, str],
    config: FullAnalystConfig,
    source_id: str,
    hypothesis: str,
    evidence_packet: dict[str, Any],
    market_data_snapshot: dict[str, Any],
    counter_evidence: list[str],
    uncertainty: list[str],
    research_quality_gate: dict[str, Any] | None,
    window_days: int = 30,
) -> dict[str, Any]:
    evidence_ids = research_signal_evidence_ids(evidence_packet)
    signal = {
        "schema": RESEARCH_SIGNAL_SCHEMA,
        "signal_id": f"{config.run_id}:{item['exchange']}:{item['symbol']}:{source_id}:research_signal",
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "source_id": source_id,
        "hypothesis": sanitize_public_text_value(hypothesis, max_chars=900)
        or f"{item['exchange']}:{item['symbol']} remains a bounded public research object.",
        "confidence": research_signal_confidence(research_quality_gate, sanitize_list(uncertainty)),
        "evidence_ids": evidence_ids,
        "counter_evidence": sanitize_list(counter_evidence)[:8],
        "uncertainty": sanitize_list(uncertainty)[:8],
        "window_days": window_days,
        "review_due_at": research_signal_review_due_at(config, window_days),
        "evidence_packet_id": sanitize_text(str(evidence_packet.get("packet_id") or ""))[:240],
        "evidence_packet_hash": sanitize_text(str(evidence_packet.get("evidence_packet_hash") or ""))[:120],
        "market_data_snapshot_hash": sanitize_text(str(market_data_snapshot.get("snapshot_hash") or ""))[:120],
        "market_data_snapshot_schema": sanitize_text(str(market_data_snapshot.get("schema") or MARKET_DATA_SNAPSHOT_SCHEMA))[:120],
        "research_status": sanitize_text(str((research_quality_gate or {}).get("research_status") or "needs_review"))[:80],
        "boundary": "research-only structured signal; not a trading instruction",
    }
    if not signal["counter_evidence"]:
        signal["counter_evidence"] = ["Counter-evidence remains unresolved and must stay visible before stronger synthesis."]
    if not signal["uncertainty"]:
        signal["uncertainty"] = ["Uncertainty remains bounded by public evidence freshness and missing sources."]
    validate_research_signal_contract(signal)
    signal["signal_hash"] = stable_hash({key: value for key, value in signal.items() if key != "signal_hash"})
    return signal


def build_symbol_research_signal(
    *,
    item: dict[str, str],
    config: FullAnalystConfig,
    evidence_packet: dict[str, Any],
    market_data_snapshot: dict[str, Any],
    chairman: dict[str, Any],
    red_team: dict[str, Any],
    research_quality_gate: dict[str, Any],
    evidence_gaps: list[str],
    watch_conditions: list[str],
    public_summary: str,
) -> dict[str, Any]:
    hypothesis = public_summary or "; ".join(sanitize_list(chairman.get("findings"))[:3])
    counter_evidence = (
        sanitize_list(red_team.get("counter_evidence_needed"))
        + sanitize_list(red_team.get("weak_assumptions"))
        + sanitize_list(red_team.get("contradiction_list"))
        + evidence_gaps
    )
    uncertainty = (
        sanitize_list(chairman.get("unresolved_questions"))
        + sanitize_list(chairman.get("conflicts"))
        + sanitize_list(red_team.get("over_certainty_risks"))
        + watch_conditions
    )
    return build_research_signal(
        item=item,
        config=config,
        source_id="symbol",
        hypothesis=hypothesis,
        evidence_packet=evidence_packet,
        market_data_snapshot=market_data_snapshot,
        counter_evidence=counter_evidence,
        uncertainty=uncertainty,
        research_quality_gate=research_quality_gate,
    )


def build_agent_research_signals(
    *,
    item: dict[str, str],
    config: FullAnalystConfig,
    evidence_packet: dict[str, Any],
    market_data_snapshot: dict[str, Any],
    agent_outputs: dict[str, dict[str, Any]],
    research_quality_gate: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    signals: dict[str, dict[str, Any]] = {}
    for agent_id, output in agent_outputs.items():
        signals[agent_id] = build_research_signal(
            item=item,
            config=config,
            source_id=agent_id,
            hypothesis="; ".join(sanitize_list(output.get("findings"))[:3]),
            evidence_packet=evidence_packet,
            market_data_snapshot=market_data_snapshot,
            counter_evidence=sanitize_list(output.get("evidence_gaps")) + sanitize_list(output.get("counter_evidence_needed")),
            uncertainty=sanitize_list(output.get("uncertainties")) + sanitize_list(output.get("watch_conditions")),
            research_quality_gate=research_quality_gate,
        )
    return signals


def validate_symbol_research_signal_contract(symbol_payload: dict[str, Any]) -> None:
    validate_research_signal_contract(symbol_payload.get("research_signal") if isinstance(symbol_payload.get("research_signal"), dict) else {})
    agent_signals = symbol_payload.get("agent_research_signals")
    if not isinstance(agent_signals, dict):
        raise ValueError("agent_research_signals_missing")
    missing = [agent_id for agent_id in V3_AGENT_IDS if agent_id not in agent_signals]
    if missing:
        raise ValueError(f"agent_research_signals_missing_agents:{','.join(missing)}")
    for agent_id in V3_AGENT_IDS:
        validate_research_signal_contract(agent_signals[agent_id])


def publication_gate(name: str, status: str, reason: str) -> dict[str, str]:
    return {
        "gate": name,
        "status": status,
        "reader_safe_reason": sanitize_public_text_value(reason, max_chars=500) or "gate result not reported",
    }


def publication_public_safety_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    try:
        assert_public_safe(symbol_payload)
    except Exception as exc:  # noqa: BLE001 - gate must collapse scanner details to public-safe category.
        return publication_gate("public_safety_scan", "blocked", public_safe_failure_category(str(exc)))
    return publication_gate("public_safety_scan", "pass", "public safety scan reported no public expression blocker")


def publication_secret_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    text = json.dumps(symbol_payload, ensure_ascii=False, sort_keys=True)
    if re.search(
        r"OPENAI_API_KEY|sk-[A-Za-z0-9_-]+|Bearer\s+|Authorization|PRIVATE KEY|"
        r"prompt_text|\"(?:messages|completion)\"\s*:|raw_provider_response|stdout|stderr",
        text,
        re.IGNORECASE,
    ):
        return publication_gate("secret_scan", "blocked", "secret_or_raw_io_public_payload_risk")
    return publication_gate("secret_scan", "pass", "no secret or raw provider I/O marker detected in public payload")


def publication_forbidden_wording_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    signal = symbol_payload.get("research_signal") if isinstance(symbol_payload.get("research_signal"), dict) else {}
    text = normalize_negated_boundary_text(json.dumps(signal, ensure_ascii=False, sort_keys=True)).lower()
    for fragment in RESEARCH_SIGNAL_FORBIDDEN_FRAGMENTS:
        if fragment.lower() in text:
            return publication_gate("forbidden_wording_scan", "blocked", "[BLOCKED: 合规禁词] research signal wording gate failed")
    return publication_gate("forbidden_wording_scan", "pass", "no restricted research-signal wording detected")


def publication_evidence_packet_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    packet = symbol_payload.get("evidence_packet") if isinstance(symbol_payload.get("evidence_packet"), dict) else {}
    if not packet:
        return publication_gate("evidence_packet_contract", "blocked", "missing EvidencePacket; no public judgment may be generated")
    try:
        validate_evidence_packet_contract(packet)
    except Exception as exc:  # noqa: BLE001 - validation detail is reduced to a reader-safe category.
        return publication_gate("evidence_packet_contract", "blocked", public_safe_failure_category(str(exc)))
    if packet.get("missing_required_sources") or packet.get("data_gaps") or packet.get("stale_sources"):
        return publication_gate("evidence_packet_contract", "needs_review", "EvidencePacket reports missing, stale, or gap sources that must stay visible")
    return publication_gate("evidence_packet_contract", "pass", "EvidencePacket contract is complete for publication review")


def publication_future_data_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    packet = symbol_payload.get("evidence_packet") if isinstance(symbol_payload.get("evidence_packet"), dict) else {}
    snapshot = symbol_payload.get("market_data_snapshot") if isinstance(symbol_payload.get("market_data_snapshot"), dict) else {}
    if packet.get("future_data_check") is False or snapshot.get("future_data_risk"):
        return publication_gate("future_data_check", "blocked", "future-data guard failed")
    return publication_gate("future_data_check", "pass", "future-data guard passed")


def publication_research_signal_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    try:
        validate_symbol_research_signal_contract(symbol_payload)
    except ValueError as exc:
        if "[BLOCKED: 合规禁词]" in str(exc):
            return publication_gate("research_signal_contract", "blocked", "[BLOCKED: 合规禁词] research signal compliance gate failed")
        return publication_gate("research_signal_contract", "blocked", f"research_signal_contract_failed:{normalize_failure_reason(exc)}")
    return publication_gate("research_signal_contract", "pass", "every ResearchSignal is present and bound to evidence")


def publication_data_completeness_gate(symbol_payload: dict[str, Any]) -> dict[str, str]:
    if symbol_payload.get("price_coverage_status") == "data_gap":
        return publication_gate("data_completeness_gate", "needs_review", "price coverage is data_gap")
    if symbol_payload.get("missing_required_sources"):
        return publication_gate("data_completeness_gate", "needs_review", "required public sources are missing")
    evidence_gaps = sanitize_list(symbol_payload.get("evidence_gaps"))
    if evidence_gaps and evidence_gaps != ["No specific evidence gap was reported."]:
        return publication_gate("data_completeness_gate", "needs_review", "evidence gaps remain visible")
    return publication_gate("data_completeness_gate", "pass", "data completeness gate passed for public research status")


def publication_blocker_type(gates: dict[str, dict[str, str]], judge_status: str, judge_reasons: list[str]) -> str:
    blocked = [name for name, gate in gates.items() if gate.get("status") == "blocked"]
    if "secret_scan" in blocked:
        return "secret_or_raw_io"
    if "forbidden_wording_scan" in blocked or any("[BLOCKED: 合规禁词]" in reason for reason in judge_reasons):
        return "forbidden_wording"
    if "public_safety_scan" in blocked:
        return "public_safety"
    if "future_data_check" in blocked:
        return "future_data"
    if "evidence_packet_contract" in blocked:
        return "evidence_packet_contract"
    if "research_signal_contract" in blocked:
        return "research_signal_contract"
    if judge_status == "blocked":
        return "judge_gate"
    return ""


def validate_publication_decision_contract(decision: dict[str, Any]) -> None:
    required = (
        "schema",
        "decision_id",
        "run_id",
        "symbol",
        "signal_id",
        "research_signal_hash",
        "decision",
        "reader_safe_reasons",
        "gates",
        "publish_with_boundary",
    )
    missing = [field for field in required if field not in decision]
    if missing:
        raise ValueError(f"publication_decision_missing_required_fields:{','.join(missing)}")
    if decision.get("schema") != PUBLICATION_DECISION_SCHEMA:
        raise ValueError("publication_decision_invalid_schema")
    if decision.get("decision") not in {"publish", "needs_review", "blocked"}:
        raise ValueError("publication_decision_invalid_decision")
    if not sanitize_text(str(decision.get("signal_id") or "")):
        raise ValueError("publication_decision_missing_signal_id")
    if not sanitize_text(str(decision.get("research_signal_hash") or "")):
        raise ValueError("publication_decision_missing_research_signal_hash")
    if decision["decision"] != "publish" and not sanitize_list(decision.get("reader_safe_reasons")):
        raise ValueError("publication_decision_missing_reader_safe_reasons")
    if decision["decision"] == "blocked" and not sanitize_text(str(decision.get("blocker_type") or "")):
        raise ValueError("publication_decision_missing_blocker_type")
    gates = decision.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("publication_decision_missing_gates")
    if decision["decision"] == "publish":
        failed = [name for name, gate in gates.items() if not isinstance(gate, dict) or gate.get("status") != "pass"]
        if failed:
            raise ValueError(f"publication_decision_publish_with_failed_gates:{','.join(failed)}")
    for gate_name in ("public_safety_scan", "secret_scan", "forbidden_wording_scan"):
        gate = gates.get(gate_name)
        if isinstance(gate, dict) and gate.get("status") == "blocked" and decision["decision"] == "publish":
            raise ValueError(f"publication_decision_publish_with_blocked_{gate_name}")
    assert_public_safe(decision)


def build_publication_decision(
    symbol_payload: dict[str, Any],
    *,
    judge_status: str,
    judge_reasons: list[str],
) -> dict[str, Any]:
    signal = symbol_payload.get("research_signal") if isinstance(symbol_payload.get("research_signal"), dict) else {}
    gates = {
        "public_safety_scan": publication_public_safety_gate(symbol_payload),
        "secret_scan": publication_secret_gate(symbol_payload),
        "forbidden_wording_scan": publication_forbidden_wording_gate(symbol_payload),
        "evidence_packet_contract": publication_evidence_packet_gate(symbol_payload),
        "future_data_check": publication_future_data_gate(symbol_payload),
        "research_signal_contract": publication_research_signal_gate(symbol_payload),
        "data_completeness_gate": publication_data_completeness_gate(symbol_payload),
    }
    gate_statuses = {name: gate["status"] for name, gate in gates.items()}
    blocked = any(status == "blocked" for status in gate_statuses.values()) or judge_status == "blocked"
    needs_review = any(status == "needs_review" for status in gate_statuses.values()) or judge_status == "needs_review"
    decision_value = "blocked" if blocked else "needs_review" if needs_review else "publish"
    reader_safe_reasons = dedupe_preserve_order(
        sanitize_list(judge_reasons)
        + [
            gate["reader_safe_reason"]
            for gate in gates.values()
            if gate["status"] != "pass"
        ]
    )[:10]
    if decision_value == "publish":
        reader_safe_reasons = ["All publication gates passed with research-only boundary."]
    elif not reader_safe_reasons:
        reader_safe_reasons = ["Publication gate requires visible reader review."]
    decision = {
        "schema": PUBLICATION_DECISION_SCHEMA,
        "decision_id": f"{symbol_payload['run_id']}:{symbol_payload['exchange']}:{symbol_payload['symbol']}:publication_decision",
        "run_id": symbol_payload["run_id"],
        "symbol": symbol_payload["symbol"],
        "exchange": symbol_payload["exchange"],
        "as_of_date": symbol_payload["as_of_date"],
        "signal_id": sanitize_text(str(signal.get("signal_id") or ""))[:260],
        "research_signal_hash": sanitize_text(str(signal.get("signal_hash") or symbol_payload.get("research_signal_hash") or ""))[:120],
        "decision": decision_value,
        "reader_safe_reasons": reader_safe_reasons,
        "blocker_type": publication_blocker_type(gates, judge_status, reader_safe_reasons) if decision_value == "blocked" else "",
        "gates": gates,
        "publish_with_boundary": decision_value in {"publish", "needs_review"},
        "evidence_layer": "local checks + smoke evidence",
        "boundary": "research-only publication decision; not an action instruction",
    }
    validate_publication_decision_contract(decision)
    decision["decision_hash"] = stable_hash({key: value for key, value in decision.items() if key != "decision_hash"})
    return decision


def ledger_base_entry_id(symbol_payload: dict[str, Any]) -> str:
    signal = symbol_payload.get("research_signal") if isinstance(symbol_payload.get("research_signal"), dict) else {}
    window_days = int(signal.get("window_days") or 0)
    return ":".join(
        [
            "gotra",
            "ledger",
            sanitize_text(str(symbol_payload.get("exchange") or "")),
            sanitize_text(str(symbol_payload.get("symbol") or "")),
            sanitize_text(str(symbol_payload.get("as_of_date") or "")),
            str(window_days),
        ]
    )


def ledger_entry_hash_basis(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "hash"}


def validate_ledger_entry_contract(entry: dict[str, Any]) -> None:
    required = (
        "schema",
        "entry_id",
        "base_entry_id",
        "version",
        "signal_id",
        "published_at",
        "window_days",
        "review_due_at",
        "hash",
        "previous_hash",
        "status",
        "symbol",
        "exchange",
        "research_signal_hash",
        "publication_decision_hash",
        "evidence_packet_hash",
    )
    missing = [field for field in required if field not in entry]
    if missing:
        raise ValueError(f"ledger_entry_missing_required_fields:{','.join(missing)}")
    if entry.get("schema") != LEDGER_ENTRY_SCHEMA:
        raise ValueError("ledger_entry_invalid_schema")
    if not sanitize_text(str(entry.get("entry_id") or "")):
        raise ValueError("ledger_entry_missing_entry_id")
    if not sanitize_text(str(entry.get("signal_id") or "")):
        raise ValueError("ledger_entry_missing_signal_id")
    if entry.get("status") not in {"publish", "needs_review", "blocked"}:
        raise ValueError("ledger_entry_invalid_status")
    if not isinstance(entry.get("version"), int) or int(entry["version"]) <= 0:
        raise ValueError("ledger_entry_invalid_version")
    if not isinstance(entry.get("window_days"), int) or int(entry["window_days"]) <= 0:
        raise ValueError("ledger_entry_invalid_window_days")
    try:
        datetime.fromisoformat(str(entry.get("published_at") or "").replace("Z", "+00:00"))
        date.fromisoformat(str(entry.get("review_due_at") or ""))
    except ValueError as exc:
        raise ValueError("ledger_entry_invalid_dates") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("previous_hash") or "")):
        raise ValueError("ledger_entry_invalid_previous_hash")
    expected_hash = stable_hash(ledger_entry_hash_basis(entry))
    if entry.get("hash") != expected_hash:
        raise ValueError("ledger_entry_hash_mismatch")
    assert_public_safe(entry)


def build_ledger_entry(
    symbol_payload: dict[str, Any],
    *,
    previous_hash: str,
    version: int,
    published_at: str,
    previous_version_hash: str = "",
) -> dict[str, Any]:
    signal = symbol_payload.get("research_signal") if isinstance(symbol_payload.get("research_signal"), dict) else {}
    decision = symbol_payload.get("publication_decision") if isinstance(symbol_payload.get("publication_decision"), dict) else {}
    packet = symbol_payload.get("evidence_packet") if isinstance(symbol_payload.get("evidence_packet"), dict) else {}
    base_entry_id = ledger_base_entry_id(symbol_payload)
    entry = {
        "schema": LEDGER_ENTRY_SCHEMA,
        "entry_id": f"{base_entry_id}:v{version}",
        "base_entry_id": base_entry_id,
        "version": version,
        "previous_version_hash": sanitize_text(previous_version_hash)[:120],
        "signal_id": sanitize_text(str(signal.get("signal_id") or decision.get("signal_id") or ""))[:260],
        "published_at": sanitize_text(published_at)[:80],
        "as_of_date": sanitize_text(str(symbol_payload.get("as_of_date") or signal.get("as_of_date") or ""))[:40],
        "window_days": int(signal.get("window_days") or 0),
        "review_due_at": sanitize_text(str(signal.get("review_due_at") or ""))[:40],
        "status": sanitize_text(str(decision.get("decision") or "needs_review"))[:40],
        "symbol": sanitize_text(str(symbol_payload.get("symbol") or signal.get("symbol") or ""))[:80],
        "exchange": sanitize_text(str(symbol_payload.get("exchange") or signal.get("exchange") or ""))[:40],
        "provider_ticker": sanitize_text(str(symbol_payload.get("provider_ticker") or signal.get("provider_ticker") or ""))[:80],
        "research_status": sanitize_text(str(symbol_payload.get("research_status") or signal.get("research_status") or ""))[:80],
        "methodology_version": sanitize_text(str(symbol_payload.get("methodology_version") or METHODOLOGY_VERSION_V40))[:120],
        "execution_model": sanitize_text(str(symbol_payload.get("execution_model") or EXECUTION_MODEL_V40))[:120],
        "research_signal_hash": sanitize_text(str(symbol_payload.get("research_signal_hash") or signal.get("signal_hash") or ""))[:120],
        "publication_decision_hash": sanitize_text(str(symbol_payload.get("publication_decision_hash") or decision.get("decision_hash") or ""))[:120],
        "evidence_packet_hash": sanitize_text(str(symbol_payload.get("evidence_packet_hash") or packet.get("evidence_packet_hash") or ""))[:120],
        "evidence_packet_link": f"/reports/symbols/{symbol_payload.get('exchange')}_{symbol_payload.get('symbol')}.json#audit-evidence-packet",
        "publication_decision": {
            "decision": decision.get("decision"),
            "reader_safe_reasons": sanitize_list(decision.get("reader_safe_reasons")),
            "publish_with_boundary": bool(decision.get("publish_with_boundary")),
            "gates": decision.get("gates") if isinstance(decision.get("gates"), dict) else {},
        },
        "research_signal": {
            "hypothesis": signal.get("hypothesis"),
            "confidence": signal.get("confidence"),
            "evidence_ids": sanitize_list(signal.get("evidence_ids")),
            "counter_evidence": sanitize_list(signal.get("counter_evidence")),
            "uncertainty": sanitize_list(signal.get("uncertainty")),
            "boundary": signal.get("boundary"),
        },
        "boundary": "research ledger entry only; not investment advice, not a trading signal, not performance proof",
        "previous_hash": previous_hash,
    }
    entry["hash"] = stable_hash(ledger_entry_hash_basis(entry))
    validate_ledger_entry_contract(entry)
    return entry


def verify_ledger_chain(entries: list[dict[str, Any]]) -> dict[str, Any]:
    previous_hash = "0" * 64
    for index, entry in enumerate(entries):
        try:
            validate_ledger_entry_contract(entry)
        except ValueError as exc:
            return {
                "ok": False,
                "reason": str(exc),
                "entry_index": index,
                "entry_id": entry.get("entry_id"),
            }
        if entry.get("previous_hash") != previous_hash:
            return {
                "ok": False,
                "reason": "ledger_previous_hash_mismatch",
                "entry_index": index,
                "entry_id": entry.get("entry_id"),
                "expected_previous_hash": previous_hash,
                "actual_previous_hash": entry.get("previous_hash"),
            }
        previous_hash = str(entry.get("hash") or "")
    return {
        "ok": True,
        "entry_count": len(entries),
        "latest_hash": previous_hash,
    }


def load_existing_research_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("ledger_existing_read_failed") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("ledger_existing_json_invalid") from exc
    entries = payload.get("entries") if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        raise ValueError("ledger_existing_entries_not_list")
    chain = verify_ledger_chain([entry for entry in entries if isinstance(entry, dict)])
    if not chain.get("ok"):
        raise ValueError(f"ledger_existing_integrity_failed:{chain.get('reason')}")
    return [entry for entry in entries if isinstance(entry, dict)]


def merge_research_ledger(
    existing_entries: list[dict[str, Any]],
    symbol_payloads: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    entries = list(existing_entries)
    previous_hash = entries[-1]["hash"] if entries else "0" * 64
    by_base: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_base.setdefault(str(entry.get("base_entry_id") or ""), []).append(entry)

    appended = 0
    for payload in sorted(symbol_payloads, key=lambda item: (str(item.get("exchange")), str(item.get("symbol")))):
        decision = payload.get("publication_decision") if isinstance(payload.get("publication_decision"), dict) else {}
        signal = payload.get("research_signal") if isinstance(payload.get("research_signal"), dict) else {}
        if decision.get("decision") != "publish" or not signal:
            continue
        base_entry_id = ledger_base_entry_id(payload)
        versions = sorted(by_base.get(base_entry_id, []), key=lambda entry: int(entry.get("version") or 0))
        previous_version_hash = str(versions[-1].get("hash") or "") if versions else ""
        version = int(versions[-1].get("version") or 0) + 1 if versions else 1
        candidate = build_ledger_entry(
            payload,
            previous_hash=previous_hash,
            version=version,
            published_at=generated_at,
            previous_version_hash=previous_version_hash,
        )
        candidate_identity = {
            key: value
            for key, value in ledger_entry_hash_basis(candidate).items()
            if key not in {"previous_hash", "previous_version_hash", "version", "entry_id", "published_at"}
        }
        duplicate = any(
            {
                key: value
                for key, value in ledger_entry_hash_basis(entry).items()
                if key not in {"previous_hash", "previous_version_hash", "version", "entry_id", "published_at"}
            }
            == candidate_identity
            for entry in versions
        )
        if duplicate:
            continue
        entries.append(candidate)
        by_base.setdefault(base_entry_id, []).append(candidate)
        previous_hash = candidate["hash"]
        appended += 1

    integrity = verify_ledger_chain(entries)
    manifest = {
        "schema": LEDGER_MANIFEST_SCHEMA,
        "generated_at": generated_at,
        "entry_count": len(entries),
        "appended_count": appended,
        "integrity": integrity,
        "query_fields": ["symbol", "as_of_date", "window_days", "status"],
        "boundary": "append-only public research ledger; research information only; not investment advice or trading signal",
        "entries": entries,
    }
    assert_public_safe(manifest)
    return manifest


def write_research_ledger(
    config: FullAnalystConfig,
    *,
    symbol_payloads: list[dict[str, Any]],
    status: dict[str, Any],
) -> dict[str, Any]:
    ledger_name = "research_ledger.json"
    output_path = config.output_dir / ledger_name
    existing_path = config.static_dir / ledger_name if config.publish_static and (config.static_dir / ledger_name).exists() else output_path
    generated_at = sanitize_text(str(status.get("finished_at_utc") or utc_now_iso()))
    existing_entries = load_existing_research_ledger(existing_path)
    manifest = merge_research_ledger(existing_entries, symbol_payloads, generated_at=generated_at)
    write_public_json(output_path, manifest)
    return {
        "path": output_path,
        "file": ledger_name,
        "schema": manifest["schema"],
        "entry_count": manifest["entry_count"],
        "appended_count": manifest["appended_count"],
        "integrity": manifest["integrity"],
    }


def aggregate_v3_symbol_payload(
    *,
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    agent_outputs: dict[str, dict[str, Any]],
    started_at_utc: str,
    wall_clock_seconds: float,
    research_task: dict[str, Any] | None = None,
    evidence_packet: dict[str, Any] | None = None,
    k_dossier: dict[str, Any] | None = None,
    research_task_seconds: float = 0.0,
    evidence_packet_seconds: float = 0.0,
    k_dossier_seconds: float = 0.0,
) -> dict[str, Any]:
    price_coverage_status = "ok" if price_row.get("ok") else "data_gap"
    market_data_snapshot = build_market_data_snapshot(item, price_row, config)
    agent_hashes = {agent_id: str(agent_outputs[agent_id].get("output_hash") or "") for agent_id in V3_AGENT_IDS}
    agent_timings = {
        V3_AGENT_TIMING_KEYS[agent_id]: float(agent_outputs[agent_id].get("duration_seconds") or 0.0)
        for agent_id in V3_AGENT_IDS
    }
    agent_timings["total_wall_clock_seconds"] = round(wall_clock_seconds, 3)
    if has_research_task_system(config):
        agent_timings["research_task_seconds"] = round(research_task_seconds, 3)
        agent_timings["evidence_packet_seconds"] = round(evidence_packet_seconds, 3)
    if is_v40_config(config):
        agent_timings["k_dossier_seconds"] = round(k_dossier_seconds, 3)
    statuses = {agent_id: str(agent_outputs[agent_id].get("status") or "") for agent_id in V3_AGENT_IDS}
    agent_retry_counts = {agent_id: int(agent_outputs[agent_id].get("retry_count") or 0) for agent_id in V3_AGENT_IDS}
    agent_public_safety_triggers = {
        agent_id: sanitize_list(agent_outputs[agent_id].get("public_safety_triggers"))
        for agent_id in V3_AGENT_IDS
    }
    all_gaps: list[str] = []
    all_watch: list[str] = []
    for output in agent_outputs.values():
        all_gaps.extend(sanitize_list(output.get("evidence_gaps")))
        all_watch.extend(sanitize_list(output.get("watch_conditions")))
    packet_gaps = sanitize_list((evidence_packet or {}).get("data_gaps")) if evidence_packet else []
    evidence_gaps = dedupe_preserve_order(packet_gaps + all_gaps)[:12] or ["No specific evidence gap was reported."]
    watch_conditions = dedupe_preserve_order(all_watch)[:12] or ["Next verified public update."]
    chairman = agent_outputs["chairman_synthesis"]
    red_team = agent_outputs["red_team_audit"]
    failed_agents = [agent_id for agent_id, status in statuses.items() if status == "failed"]
    red_verdict = str(red_team.get("final_red_team_verdict") or "needs_review")
    research_status = str(chairman.get("research_status") or "")
    research_quality_gate: dict[str, Any] | None = None
    knowledge_gate: dict[str, Any] | None = None
    reader_boundary_gate: dict[str, Any] | None = None
    if is_v40_config(config):
        research_quality_gate = build_research_quality_gate(
            price_coverage_status=price_coverage_status,
            missing_required_sources=(evidence_packet or {}).get("missing_required_sources", []),
            failed_agents=failed_agents,
            chairman=chairman,
            red_team=red_team,
            evidence_gaps=evidence_gaps,
        )
        knowledge_gate = build_knowledge_gate(
            research_quality_gate=research_quality_gate,
            evidence_gaps=evidence_gaps,
            watch_conditions=watch_conditions,
            chairman=chairman,
            red_team=red_team,
        )
        reader_boundary_gate = build_reader_boundary_gate(
            research_quality_gate=research_quality_gate,
            red_team=red_team,
        )
        research_status = str(research_quality_gate["research_status"])
    elif price_coverage_status == "data_gap":
        research_status = "data_gap"
    elif is_v35_config(config) and (evidence_packet or {}).get("missing_required_sources"):
        research_status = "needs_review"
    elif failed_agents or red_verdict in {"needs_review", "blocked"}:
        research_status = "needs_review" if red_verdict != "blocked" else "high_uncertainty"
    elif research_status not in {"candidate", "watch", "avoid", "needs_review", "data_gap", "high_uncertainty"}:
        research_status = "watch"
    public_summary = section_summary(
        {"summary": "; ".join(sanitize_list(chairman.get("findings"))[:3])},
        f"Independent-agent research synthesis for {item['exchange']}:{item['symbol']}.",
    )
    research_signal: dict[str, Any] | None = None
    agent_research_signals: dict[str, dict[str, Any]] = {}
    agent_research_signal_hashes: dict[str, str] = {}
    if is_v40_config(config):
        if not evidence_packet or not research_quality_gate:
            raise ValueError("v40_missing_evidence_packet_or_research_quality_gate_for_research_signal")
        research_signal = build_symbol_research_signal(
            item=item,
            config=config,
            evidence_packet=evidence_packet,
            market_data_snapshot=market_data_snapshot,
            chairman=chairman,
            red_team=red_team,
            research_quality_gate=research_quality_gate,
            evidence_gaps=evidence_gaps,
            watch_conditions=watch_conditions,
            public_summary=public_summary,
        )
        agent_research_signals = build_agent_research_signals(
            item=item,
            config=config,
            evidence_packet=evidence_packet,
            market_data_snapshot=market_data_snapshot,
            agent_outputs=agent_outputs,
            research_quality_gate=research_quality_gate,
        )
        agent_research_signal_hashes = {
            agent_id: signal["signal_hash"] for agent_id, signal in agent_research_signals.items()
        }
    payload = {
        "schema": symbol_schema_for_config(config),
        "prompt_template_version": prompt_template_for_config(config),
        "methodology_version": methodology_for_config(config),
        "execution_model": execution_model_for_config(config),
        "run_id": config.run_id,
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat(),
        "price_coverage_status": price_coverage_status,
        "price_context": public_price_context(price_row),
        "market_data_snapshot": market_data_snapshot,
        "market_data_snapshot_hash": market_data_snapshot["snapshot_hash"],
        "agent_outputs": agent_outputs,
        "agent_hashes": agent_hashes,
        "agent_timings": agent_timings,
        "parallelism": {
            "symbol_parallelism": config.max_concurrency,
            "agent_parallelism": config.agent_concurrency,
            "kfwg_ran_in_parallel": config.agent_concurrency > 1 and not is_v40_config(config),
            **(
                {
                    "k_dossier_first": True,
                    "perspective_parallelism": min(config.agent_concurrency, len(V40_PERSPECTIVE_AGENT_IDS)),
                    "fwg_ran_in_parallel": config.agent_concurrency > 1,
                }
                if is_v40_config(config)
                else {}
            ),
        },
        "research_status": research_status,
        "judge_status": "pending",
        "evidence_gaps": evidence_gaps,
        "missing_required_sources": (evidence_packet or {}).get("missing_required_sources", []),
        "watch_conditions": watch_conditions,
        "public_summary": public_summary,
        "reader_boundary": READER_BOUNDARY,
        "reader_boundary_zh": READER_BOUNDARY_ZH,
        "boundary": list(BOUNDARY_LINES),
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "red_team_verdict": red_verdict,
        "agent_statuses": statuses,
        "agent_retry_counts": agent_retry_counts,
        "agent_public_safety_triggers": agent_public_safety_triggers,
        "failure_records": [
            {
                "agent_id": agent_id,
                "status": "failed",
                "failure_reason": agent_outputs[agent_id].get("failure_reason", "agent_failed"),
                "output_hash": agent_hashes[agent_id],
            }
            for agent_id in failed_agents
        ],
        # v2-compatible summary fields for public readers that consume Markdown-derived sections.
        "research_summary": public_summary,
        "key_updates": v3_section_list(agent_outputs["k_deep_research"], "K agent did not report findings."),
        "research_context": {"summary": public_summary, "price_context": public_price_context(price_row)},
        "k_deep_research": {"summary": "; ".join(v3_section_list(agent_outputs["k_deep_research"], "K agent unavailable."))},
        "f_partner_view": {"summary": "; ".join(v3_section_list(agent_outputs["f_partner_view"], "F agent unavailable."))},
        "w_partner_view": {"summary": "; ".join(v3_section_list(agent_outputs["w_partner_view"], "W agent unavailable."))},
        "g_partner_view": {"summary": "; ".join(v3_section_list(agent_outputs["g_partner_view"], "G agent unavailable."))},
        "chairman_synthesis": {"summary": "; ".join(v3_section_list(chairman, "Chairman unavailable."))},
        "red_team_audit": {"summary": "; ".join(v3_section_list(red_team, "Red-team unavailable."))},
        "positive_case": v3_section_list(agent_outputs["f_partner_view"], "F agent unavailable."),
        "negative_case": v3_section_list(agent_outputs["w_partner_view"], "W agent unavailable."),
        "red_team_review": v3_section_list(red_team, "Red-team unavailable."),
        "risk_factors": v3_section_list(agent_outputs["g_partner_view"], "G agent unavailable."),
        "watch_items": watch_conditions,
        "source_notes": ["Public-safe independent-agent outputs; raw provider I/O is not embedded."],
        "confidence_boundary": str(chairman.get("confidence_boundary") or "Confidence is bounded by evidence freshness, data coverage, and red-team verdict."),
    }
    if has_research_task_system(config):
        if not research_task or not evidence_packet:
            raise ValueError("research_system_missing_research_task_or_evidence_packet")
        payload.update(
            {
                "research_task": research_task,
                "research_task_hash": research_task["task_hash"],
                "evidence_packet": evidence_packet,
                "evidence_packet_hash": evidence_packet["evidence_packet_hash"],
            }
        )
    if is_v40_config(config):
        if not k_dossier or not research_quality_gate or not knowledge_gate or not reader_boundary_gate:
            raise ValueError("v40_missing_k_dossier_or_gates")
        payload.update(
            {
                "k_deep_research_dossier": k_dossier,
                "k_dossier_hash": k_dossier["dossier_hash"],
                "research_quality_gate": research_quality_gate,
                "research_quality_gate_hash": research_quality_gate["gate_hash"],
                "knowledge_gate": knowledge_gate,
                "knowledge_gate_hash": knowledge_gate["gate_hash"],
                "knowledge_persistence": knowledge_gate["knowledge_persistence"],
                "unresolved_questions": knowledge_gate["unresolved_questions"],
                "future_research_tasks": knowledge_gate["future_research_tasks"],
                "evidence_gap_memory": knowledge_gate["evidence_gap_memory"],
                "reader_boundary_gate": reader_boundary_gate,
                "reader_boundary_gate_hash": reader_boundary_gate["gate_hash"],
                "research_signal": research_signal,
                "research_signal_hash": research_signal["signal_hash"] if research_signal else "",
                "research_signal_schema": RESEARCH_SIGNAL_SCHEMA,
                "agent_research_signals": agent_research_signals,
                "agent_research_signal_hashes": agent_research_signal_hashes,
            }
        )
    payload["research_packet_hash"] = stable_hash(
        {
            "schema": payload["schema"],
            "run_id": config.run_id,
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "research_task_hash": payload.get("research_task_hash", ""),
            "evidence_packet_hash": payload.get("evidence_packet_hash", ""),
            "market_data_snapshot_hash": payload.get("market_data_snapshot_hash", ""),
            "k_dossier_hash": payload.get("k_dossier_hash", ""),
            "agent_hashes": agent_hashes,
            "research_quality_gate_hash": payload.get("research_quality_gate_hash", ""),
            "knowledge_gate_hash": payload.get("knowledge_gate_hash", ""),
            "research_signal_hash": payload.get("research_signal_hash", ""),
            "research_status": research_status,
        }
    )
    assert_public_safe(payload)
    return payload


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = sanitize_text(str(value))[:500]
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def judge_symbol_v3(symbol_payload: dict[str, Any]) -> tuple[str, list[str]]:
    assert_public_safe(symbol_payload)
    market_data_snapshot = symbol_payload.get("market_data_snapshot") if isinstance(symbol_payload.get("market_data_snapshot"), dict) else {}
    if symbol_payload.get("schema") != SYMBOL_SCHEMA_V40 and market_data_snapshot.get("future_data_risk"):
        return "blocked", ["market data snapshot reports future_data_risk"]
    statuses = agent_statuses(symbol_payload)
    failed_agents = [agent_id for agent_id, status in statuses.items() if status == "failed"]
    if failed_agents:
        return "blocked", [f"independent agent failure: {','.join(failed_agents)}"]
    if symbol_payload.get("schema") == SYMBOL_SCHEMA_V40:
        evidence_packet = symbol_payload.get("evidence_packet") if isinstance(symbol_payload.get("evidence_packet"), dict) else {}
        if not evidence_packet:
            return "blocked", ["missing EvidencePacket; no public judgment may be generated"]
        validate_evidence_packet_contract(evidence_packet)
        if evidence_packet.get("future_data_check") is False:
            return "blocked", ["evidence packet future_data_check failed"]
        if market_data_snapshot.get("future_data_risk"):
            return "blocked", ["market data snapshot reports future_data_risk"]
        try:
            validate_symbol_research_signal_contract(symbol_payload)
        except ValueError as exc:
            reason = normalize_failure_reason(exc)
            if "[BLOCKED: 合规禁词]" in str(exc):
                return "blocked", ["[BLOCKED: 合规禁词] research signal compliance gate failed"]
            return "blocked", [f"research signal contract failed: {reason}"]
        gate = symbol_payload.get("research_quality_gate") if isinstance(symbol_payload.get("research_quality_gate"), dict) else {}
        if gate.get("engineering_blocker") or gate.get("quality_verdict") == "blocked":
            return "blocked", ["v4 research quality gate reported an engineering blocker"]
        empty_hashes = [agent_id for agent_id, value in symbol_payload["agent_hashes"].items() if not value]
        if empty_hashes:
            return "blocked", [f"missing independent agent hash: {','.join(empty_hashes)}"]
        if not symbol_payload.get("k_dossier_hash"):
            return "blocked", ["missing K dossier hash"]
        if not symbol_payload.get("knowledge_gate_hash"):
            return "blocked", ["missing Knowledge Gate hash"]
        if gate.get("quality_verdict") in {"pass_with_review_items", "needs_review"}:
            return "needs_review", ["v4 research quality gate requires visible review items"]
        if symbol_payload["price_coverage_status"] == "data_gap" or gate.get("research_status") == "data_gap":
            return "needs_review", ["v4 research quality gate preserves data_gap"]
        return "publish", ["public-safe v4 cognition flywheel research object passed local judge gate"]
    if symbol_payload["price_coverage_status"] == "data_gap":
        return "needs_review", ["price coverage is data_gap; v3 cannot promote this symbol"]
    if symbol_payload.get("schema") == SYMBOL_SCHEMA_V35 and symbol_payload.get("missing_required_sources"):
        return "needs_review", ["v3.5 evidence packet is missing required public sources; preserve research limitation"]
    verdict = red_team_verdict(symbol_payload)
    if verdict == "blocked":
        return "blocked", ["red-team verdict blocked"]
    if verdict == "needs_review":
        return "needs_review", ["red-team verdict needs_review"]
    empty_hashes = [agent_id for agent_id, value in symbol_payload["agent_hashes"].items() if not value]
    if empty_hashes:
        return "blocked", [f"missing independent agent hash: {','.join(empty_hashes)}"]
    return "publish", ["public-safe v3 independent-agent research object passed local judge gate"]


def run_symbol_v3(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    alaya_client: AlayaSyncClient,
) -> dict[str, Any]:
    started_at = utc_now_iso()
    started = time.monotonic()
    research_task: dict[str, Any] | None = None
    evidence_packet: dict[str, Any] | None = None
    k_dossier: dict[str, Any] | None = None
    research_task_seconds = 0.0
    evidence_packet_seconds = 0.0
    k_dossier_seconds = 0.0
    base_dependencies: dict[str, Any] = {}
    if has_research_task_system(config):
        task_started = time.monotonic()
        research_task = run_research_task_planner(item, price_row, config, runner)
        research_task_seconds = time.monotonic() - task_started
        packet_started = time.monotonic()
        evidence_packet = build_evidence_packet(item, price_row, config, research_task)
        evidence_packet_seconds = time.monotonic() - packet_started
        write_private_json_atomic(
            private_run_dir(config) / "evidence_packets" / f"{item['exchange']}_{item['symbol']}.json",
            evidence_packet,
        )
        base_dependencies = {
            "research_task": research_task,
            "evidence_packet": evidence_packet,
            "prior_alaya_readback": evidence_packet.get("prior_alaya_readback", {}),
        }
    if is_v40_config(config):
        k_started_at = utc_now_iso()
        k_started = time.monotonic()
        if research_task is None or evidence_packet is None:
            raise RuntimeError("v40_missing_research_task_or_evidence_packet")
        k_dossier = run_k_dossier(item, price_row, config, runner, research_task, evidence_packet)
        k_dossier_seconds = time.monotonic() - k_started
        k_finished_at = utc_now_iso()
        base_dependencies = {
            **base_dependencies,
            "k_deep_research_dossier": k_dossier,
        }
        k_output = k_dossier_to_agent_output(
            k_dossier,
            item=item,
            config=config,
            started_at=k_started_at,
            finished_at=k_finished_at,
            duration_seconds=k_dossier_seconds,
        )
        perspective_outputs = run_v40_perspective_agents(
            item,
            price_row,
            config,
            runner,
            base_dependencies=base_dependencies,
        )
        kfwg_outputs = {"k_deep_research": k_output, **perspective_outputs}
    else:
        kfwg_outputs = run_v3_kfwg_agents(item, price_row, config, runner, base_dependencies=base_dependencies)
    chairman_dependencies = {"agent_outputs": kfwg_outputs, **base_dependencies} if has_research_task_system(config) else kfwg_outputs
    chairman_output = run_v3_agent(
        "chairman_synthesis",
        item,
        price_row,
        config,
        runner,
        dependencies=chairman_dependencies,
    )
    outputs_for_red_team = {**kfwg_outputs, "chairman_synthesis": chairman_output}
    red_team_dependencies = {"agent_outputs": outputs_for_red_team, **base_dependencies} if has_research_task_system(config) else outputs_for_red_team
    red_team_output = run_v3_agent(
        "red_team_audit",
        item,
        price_row,
        config,
        runner,
        dependencies=red_team_dependencies,
    )
    agent_outputs = {**outputs_for_red_team, "red_team_audit": red_team_output}
    symbol_payload = aggregate_v3_symbol_payload(
        item=item,
        price_row=price_row,
        config=config,
        agent_outputs=agent_outputs,
        started_at_utc=started_at,
        wall_clock_seconds=time.monotonic() - started,
        research_task=research_task,
        evidence_packet=evidence_packet,
        k_dossier=k_dossier,
        research_task_seconds=research_task_seconds,
        evidence_packet_seconds=evidence_packet_seconds,
        k_dossier_seconds=k_dossier_seconds,
    )
    judge_status, judge_reasons = judge_symbol_v3(symbol_payload)
    symbol_payload["judge_status"] = judge_status
    symbol_payload["judge_reasons"] = judge_reasons
    if is_v40_config(config):
        publication_decision = build_publication_decision(
            symbol_payload,
            judge_status=judge_status,
            judge_reasons=judge_reasons,
        )
        symbol_payload["publication_decision"] = publication_decision
        symbol_payload["publication_decision_hash"] = publication_decision["decision_hash"]
        symbol_payload["publication_decision_schema"] = PUBLICATION_DECISION_SCHEMA
        symbol_payload["research_packet_hash"] = stable_hash(
            {
                "schema": symbol_payload["schema"],
                "run_id": config.run_id,
                "symbol": item["symbol"],
                "exchange": item["exchange"],
                "research_task_hash": symbol_payload.get("research_task_hash", ""),
                "evidence_packet_hash": symbol_payload.get("evidence_packet_hash", ""),
                "market_data_snapshot_hash": symbol_payload.get("market_data_snapshot_hash", ""),
                "k_dossier_hash": symbol_payload.get("k_dossier_hash", ""),
                "agent_hashes": symbol_payload["agent_hashes"],
                "research_quality_gate_hash": symbol_payload.get("research_quality_gate_hash", ""),
                "knowledge_gate_hash": symbol_payload.get("knowledge_gate_hash", ""),
                "research_signal_hash": symbol_payload.get("research_signal_hash", ""),
                "publication_decision_hash": symbol_payload.get("publication_decision_hash", ""),
                "research_status": symbol_payload["research_status"],
                "judge_status": judge_status,
            }
        )
    alaya_result = alaya_sync(symbol_payload, alaya_client, config)
    symbol_payload["alaya_sync_status"] = alaya_result["status"]
    symbol_payload["alaya_sync_ref"] = alaya_result.get("event_id", "")
    symbol_payload["alaya_event_hash"] = alaya_result.get("event_hash", "")
    symbol_payload["alaya_event_schema"] = alaya_result.get("event_schema", alaya_event_schema_for_payload(symbol_payload))
    symbol_payload["public_payload_hash"] = alaya_result.get("public_payload_hash", "")
    symbol_payload["alaya_readback_status"] = alaya_result.get("readback_status", "not_applicable")
    symbol_payload["alaya_failure_reason"] = alaya_result.get("reason", "")
    symbol_payload["alaya_write_seconds"] = float(alaya_result.get("write_seconds") or 0.0)
    symbol_payload["alaya_readback_seconds"] = float(alaya_result.get("readback_seconds") or 0.0)
    symbol_payload["alaya_total_seconds"] = float(alaya_result.get("total_seconds") or 0.0)
    return {
        "status": "success",
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "price_coverage_status": symbol_payload["price_coverage_status"],
        "judge_status": judge_status,
        "judge_reasons": judge_reasons,
        "alaya_sync_status": alaya_result["status"],
        "alaya_sync_ref": alaya_result.get("event_id", ""),
        "alaya_event_hash": alaya_result.get("event_hash", ""),
        "alaya_event_schema": alaya_result.get("event_schema", alaya_event_schema_for_payload(symbol_payload)),
        "public_payload_hash": alaya_result.get("public_payload_hash", ""),
        "alaya_readback_status": alaya_result.get("readback_status", "not_applicable"),
        "alaya_failure_reason": alaya_result.get("reason", ""),
        "alaya_write_seconds": float(alaya_result.get("write_seconds") or 0.0),
        "alaya_readback_seconds": float(alaya_result.get("readback_seconds") or 0.0),
        "alaya_total_seconds": float(alaya_result.get("total_seconds") or 0.0),
        "attempts": 1,
        "attempt_metrics": [],
        "started_at_utc": started_at,
        "finished_at_utc": utc_now_iso(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "agent_calls_total": len(V3_AGENT_IDS) + (1 if has_research_task_system(config) else 0),
        "research_task_seconds": round(research_task_seconds, 3),
        "evidence_packet_seconds": round(evidence_packet_seconds, 3),
        "k_dossier_seconds": round(k_dossier_seconds, 3),
        "research": symbol_payload,
    }


def run_symbol(
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    alaya_client: AlayaSyncClient,
) -> dict[str, Any]:
    if is_v3_config(config):
        return run_symbol_v3(item, price_row, config, runner, alaya_client)
    started_at = utc_now_iso()
    started = time.monotonic()
    attempts: list[dict[str, Any]] = []
    last_error = ""
    for attempt in range(1, config.retries + 2):
        prompt = build_prompt(item, price_row, config, attempt=attempt, last_error=last_error)
        prompt_hash = stable_hash({"prompt": prompt})
        attempt_record = {
            "schema": PRIVATE_ATTEMPT_SCHEMA,
            "run_id": config.run_id,
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "attempt": attempt,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            "prompt_hash": prompt_hash,
            "prompt_text": scrub_secret_text(prompt),
            "model": config.model,
            "reasoning_effort": config.reasoning_effort,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "status": "failed",
            "failure_reason": "",
        }
        result = runner.complete(prompt, timeout_seconds=config.per_symbol_timeout_seconds)
        attempt_record["stdout_bytes"] = result.stdout_bytes
        attempt_record["stderr_bytes"] = result.stderr_bytes
        attempt_record["returncode"] = result.returncode
        if not result.ok:
            last_error = result.reason or "runner_failed"
            attempt_record["failure_reason"] = last_error
            attempts.append(public_attempt(attempt, last_error))
            write_private_attempt(config, item, attempt_record)
            continue
        try:
            symbol_payload = sanitize_symbol_payload(
                parse_model_json(result.text),
                item=item,
                price_row=price_row,
                config=config,
            )
            symbol_payload["prompt_hash"] = prompt_hash
            symbol_payload["research_packet_hash"] = stable_hash(
                {
                    "run_id": config.run_id,
                    "symbol": item["symbol"],
                    "exchange": item["exchange"],
                    "provider_ticker": item["provider_ticker"],
                    "as_of_date": config.as_of_date.isoformat(),
                    "trading_date": symbol_payload["trading_date"],
                    "price_context": symbol_payload["price_context"],
                    "methodology_version": METHODOLOGY_VERSION,
                    "execution_model": EXECUTION_MODEL,
                }
            )
            judge_status, judge_reasons = judge_symbol(symbol_payload)
            symbol_payload["judge_status"] = judge_status
            symbol_payload["judge_reasons"] = judge_reasons
            alaya_result = alaya_sync(symbol_payload, alaya_client, config)
            symbol_payload["alaya_sync_status"] = alaya_result["status"]
            symbol_payload["alaya_sync_ref"] = alaya_result.get("event_id", "")
            symbol_payload["alaya_event_hash"] = alaya_result.get("event_hash", "")
            symbol_payload["alaya_event_schema"] = alaya_result.get("event_schema", ALAYA_EVENT_SCHEMA)
            symbol_payload["public_payload_hash"] = alaya_result.get("public_payload_hash", "")
            symbol_payload["alaya_readback_status"] = alaya_result.get("readback_status", "not_applicable")
            symbol_payload["alaya_failure_reason"] = alaya_result.get("reason", "")
            symbol_payload["alaya_write_seconds"] = float(alaya_result.get("write_seconds") or 0.0)
            symbol_payload["alaya_readback_seconds"] = float(alaya_result.get("readback_seconds") or 0.0)
            symbol_payload["alaya_total_seconds"] = float(alaya_result.get("total_seconds") or 0.0)
            attempt_record["status"] = "success"
            attempt_record["parsed_structured_output"] = symbol_payload
            write_private_attempt(config, item, attempt_record)
            return {
                "status": "success",
                "symbol": item["symbol"],
                "exchange": item["exchange"],
                "provider_ticker": item["provider_ticker"],
                "price_coverage_status": symbol_payload["price_coverage_status"],
                "judge_status": judge_status,
                "judge_reasons": judge_reasons,
                "alaya_sync_status": alaya_result["status"],
                "alaya_sync_ref": alaya_result.get("event_id", ""),
                "alaya_event_hash": alaya_result.get("event_hash", ""),
                "alaya_event_schema": alaya_result.get("event_schema", ALAYA_EVENT_SCHEMA),
                "public_payload_hash": alaya_result.get("public_payload_hash", ""),
                "alaya_readback_status": alaya_result.get("readback_status", "not_applicable"),
                "alaya_failure_reason": alaya_result.get("reason", ""),
                "alaya_write_seconds": float(alaya_result.get("write_seconds") or 0.0),
                "alaya_readback_seconds": float(alaya_result.get("readback_seconds") or 0.0),
                "alaya_total_seconds": float(alaya_result.get("total_seconds") or 0.0),
                "attempts": attempt,
                "attempt_metrics": attempts,
                "started_at_utc": started_at,
                "finished_at_utc": utc_now_iso(),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "research": symbol_payload,
            }
        except Exception as exc:  # noqa: BLE001 - keep per-symbol failure visible.
            last_error = normalize_failure_reason(exc)
            attempt_record["failure_reason"] = last_error
            attempts.append(public_attempt(attempt, last_error))
            write_private_attempt(config, item, attempt_record)
    public_failure_category = public_safe_failure_category(last_error or "unknown_failure")
    return {
        "status": "failed",
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "price_coverage_status": "ok" if price_row.get("ok") else "data_gap",
        "judge_status": "blocked",
        "judge_reasons": [public_failure_category],
        "alaya_sync_status": "skipped",
        "alaya_sync_ref": "",
        "alaya_event_hash": "",
        "alaya_readback_status": "skipped",
        "alaya_failure_reason": "",
        "alaya_write_seconds": 0.0,
        "alaya_readback_seconds": 0.0,
        "alaya_total_seconds": 0.0,
        "attempts": len(attempts),
        "attempt_metrics": attempts,
        "started_at_utc": started_at,
        "finished_at_utc": utc_now_iso(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "research": None,
        "failure_reason": last_error or "unknown_failure",
    }


def public_attempt(attempt: int, reason: str) -> dict[str, Any]:
    return {"attempt": attempt, "failure_reason": sanitize_text(reason)[:240]}


def normalize_failure_reason(exc: Exception) -> str:
    text = str(exc)
    if text.startswith("missing_required_fields"):
        return "missing_required_fields"
    if text.startswith("forbidden_raw_io_keys"):
        return "forbidden_raw_io_keys_detected"
    if text.startswith("forbidden_public_content_detected"):
        category, _, token = text.partition(":")
        token = public_safe_failure_category(token) if token else ""
        return f"{category}:{token}" if token else category
    return f"{type(exc).__name__}: {text[:180]}"


def write_private_attempt(config: FullAnalystConfig, item: dict[str, str], payload: dict[str, Any]) -> None:
    path = private_run_dir(config) / "attempts" / f"{item['exchange']}_{item['symbol']}_attempt_{payload['attempt']}.json"
    write_private_json_atomic(path, payload)




PUBLIC_BOUNDARY_TERM_REPLACEMENTS = (
    (
        re.compile(r"\btarget\s+prices?\b|\bprice\s+targets?\b|\bprice\s+objectives?\b", re.IGNORECASE),
        "price-objective wording",
    ),
    (
        re.compile(
            r"\b(?:buy|sell|hold)\s+(?:recommendation|rating|signal|instruction)s?\b|"
            r"\bbuy\s*/\s*sell\s*/\s*hold\b|\bbuy,\s*sell,\s*(?:or\s*)?hold\b",
            re.IGNORECASE,
        ),
        "directional-action wording",
    ),
    (re.compile(r"\bposition\s+sizing\b", re.IGNORECASE), "allocation-guidance wording"),
    (re.compile(r"\breturn\s+promise\b", re.IGNORECASE), "outcome-promise wording"),
    (re.compile(r"目标价"), "price-objective wording"),
    (re.compile(r"买入|卖出|持有建议|交易信号"), "directional-action wording"),
    (re.compile(r"仓位"), "allocation-guidance wording"),
    (re.compile(r"收益承诺"), "outcome-promise wording"),
)


def neutralize_public_boundary_terms(value: Any) -> Any:
    """Let boundary/audit documents name policy categories without publishing trigger words."""

    if isinstance(value, str):
        text = value
        for pattern, replacement in PUBLIC_BOUNDARY_TERM_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        return text
    if isinstance(value, list):
        return [neutralize_public_boundary_terms(item) for item in value]
    if isinstance(value, dict):
        return {sanitize_text(str(key))[:120]: neutralize_public_boundary_terms(item) for key, item in value.items()}
    return value


def neutralize_red_team_public_terms(value: Any) -> Any:
    """Backward-compatible wrapper for red-team public output neutralization."""

    return neutralize_public_boundary_terms(value)

def sanitize_symbol_payload(
    payload: dict[str, Any],
    *,
    item: dict[str, str],
    price_row: dict[str, Any],
    config: FullAnalystConfig,
) -> dict[str, Any]:
    forbidden_keys = [key for key in payload if FORBIDDEN_OUTPUT_KEY_RE.match(str(key))]
    if forbidden_keys:
        raise ValueError(f"forbidden_raw_io_keys: {','.join(sorted(forbidden_keys))}")
    if payload.get("schema") == SYMBOL_SCHEMA_V1:
        missing_v1 = [key for key in REQUIRED_SYMBOL_KEYS_V1 if key not in payload]
        if missing_v1:
            raise ValueError(f"missing_required_fields: {','.join(missing_v1)}")
        payload = v1_payload_to_v2(payload)
    missing = [key for key in REQUIRED_SYMBOL_KEYS if key not in payload]
    if missing:
        raise ValueError(f"missing_required_fields: {','.join(missing)}")
    sanitized: dict[str, Any] = {}
    for key in REQUIRED_SYMBOL_KEYS:
        value = payload.get(key)
        if key in LIST_KEYS:
            sanitized[key] = sanitize_list(value)
        elif key in SECTION_KEYS:
            sanitized[key] = sanitize_record(value)
        else:
            sanitized[key] = sanitize_text(str(value or ""))
    sanitized["schema"] = SYMBOL_SCHEMA
    sanitized["run_id"] = config.run_id
    sanitized["symbol"] = item["symbol"]
    sanitized["exchange"] = item["exchange"]
    sanitized["provider_ticker"] = item["provider_ticker"]
    sanitized["as_of_date"] = config.as_of_date.isoformat()
    sanitized["trading_date"] = trading_date_for_exchange(item["exchange"], exchange_dates_for_config(config)).isoformat()
    sanitized["price_coverage_status"] = "ok" if price_row.get("ok") else "data_gap"
    sanitized["price_context"] = public_price_context(price_row)
    market_data_snapshot = build_market_data_snapshot(item, price_row, config)
    sanitized["market_data_snapshot"] = market_data_snapshot
    sanitized["market_data_snapshot_hash"] = market_data_snapshot["snapshot_hash"]
    sanitized["prompt_template_version"] = PROMPT_TEMPLATE_VERSION
    sanitized["methodology_version"] = METHODOLOGY_VERSION
    sanitized["execution_model"] = EXECUTION_MODEL
    sanitized["research_status"] = normalize_research_status(
        sanitized.get("research_status"),
        price_coverage_status=sanitized["price_coverage_status"],
    )
    sanitized["reader_boundary"] = READER_BOUNDARY
    sanitized["reader_boundary_zh"] = READER_BOUNDARY_ZH
    sanitized["boundary"] = list(BOUNDARY_LINES)
    sanitized["research_summary"] = section_summary(
        sanitized["chairman_synthesis"],
        f"Public-safe Ksana 4.1-lite research synthesis for {item['exchange']}:{item['symbol']}.",
    )
    sanitized["key_updates"] = section_list(
        sanitized["research_context"],
        "Review public-source freshness before using this research context.",
    )
    sanitized["positive_case"] = section_list(sanitized["f_partner_view"], "Constructive case requires fresh public evidence.")
    sanitized["negative_case"] = section_list(sanitized["w_partner_view"], "Cautious case remains under review.")
    sanitized["red_team_review"] = section_list(sanitized["red_team_audit"], "Red-team review keeps uncertainty visible.")
    sanitized["risk_factors"] = section_list(sanitized["g_partner_view"], "Governance and data-quality risks remain visible.")
    sanitized["watch_items"] = sanitized["watch_conditions"] or ["Next verified public update."]
    if not sanitized["source_notes"]:
        sanitized["source_notes"] = ["Public-safe source freshness must be checked before stronger claims."]
    if not sanitized["evidence_gaps"]:
        sanitized["evidence_gaps"] = ["No material public evidence gap was reported by this run."]
    if not sanitized["watch_conditions"]:
        sanitized["watch_conditions"] = ["Next verified public update."]
    assert_public_safe(sanitized)
    return sanitized


def sanitize_v3_agent_output(
    payload: dict[str, Any],
    *,
    agent_id: str,
    item: dict[str, str],
    config: FullAnalystConfig,
    input_context_hash: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
) -> dict[str, Any]:
    forbidden_keys = [key for key in payload if FORBIDDEN_OUTPUT_KEY_RE.match(str(key))]
    if forbidden_keys:
        raise ValueError(f"forbidden_raw_io_keys: {','.join(sorted(forbidden_keys))}")
    status = sanitize_text(str(payload.get("status") or "")).lower()
    if status not in {"ok", "needs_review", "failed"}:
        status = "needs_review"
    output: dict[str, Any] = {
        "agent_id": agent_id,
        "agent_role": sanitize_text(str(payload.get("agent_role") or V3_AGENT_ROLE_LABELS[agent_id]))[:240],
        "schema": agent_output_schema_for_config(config, agent_id),
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "run_id": config.run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "model": sanitize_text(str(payload.get("model") or config.model))[:120],
        "prompt_template_version": prompt_template_for_config(config),
        "input_context_hash": input_context_hash,
        "output_hash": "",
        "status": status,
        "findings": sanitize_list(payload.get("findings")) or ["No public-safe findings were returned."],
        "evidence_refs": sanitize_evidence_refs(payload.get("evidence_refs")),
        "evidence_gaps": sanitize_list(payload.get("evidence_gaps")) or ["Evidence gap not specified."],
        "uncertainties": sanitize_list(payload.get("uncertainties")) or ["Uncertainty not specified."],
        "watch_conditions": sanitize_list(payload.get("watch_conditions")) or ["Next verified public update."],
        "boundary": "research content only; does not constitute investment advice",
    }
    if agent_id == "chairman_synthesis":
        output["research_status"] = normalize_research_status(
            payload.get("research_status"),
            price_coverage_status="data_gap" if "data_gap" in " ".join(output["evidence_gaps"]).lower() else "ok",
        )
        output["confidence_boundary"] = sanitize_public_text_value(
            payload.get("confidence_boundary") or "Confidence is bounded by evidence freshness and data coverage.",
            preferred_keys=("overall", "supported", "not_supported", "summary", "reason"),
            max_chars=500,
        )
        output["next_verification_steps"] = sanitize_list(payload.get("next_verification_steps")) or output["watch_conditions"]
        if is_v40_config(config):
            output["consensus"] = sanitize_list(payload.get("consensus")) or output["findings"][:2]
            output["conflicts"] = sanitize_list(payload.get("conflicts")) or output["uncertainties"][:2]
            output["evidence_strength"] = sanitize_public_text_value(
                payload.get("evidence_strength") or "Evidence strength is bounded by missing required sources.",
                max_chars=500,
            )
            output["unresolved_questions"] = sanitize_list(payload.get("unresolved_questions")) or output["next_verification_steps"]
            output["research_status_proposal"] = normalize_research_status(
                payload.get("research_status_proposal") or output["research_status"],
                price_coverage_status="data_gap" if "data_gap" in " ".join(output["evidence_gaps"]).lower() else "ok",
            )
    if agent_id == "red_team_audit":
        verdict = sanitize_text(str(payload.get("final_red_team_verdict") or payload.get("red_team_verdict") or "needs_review")).lower()
        allowed_verdicts = (
            {"pass_with_review_items", "needs_review", "data_gap", "blocked_engineering_only_if_real"}
            if is_v40_config(config)
            else {"pass", "needs_review", "blocked"}
        )
        output["final_red_team_verdict"] = verdict if verdict in allowed_verdicts else "needs_review"
        output["contradiction_list"] = sanitize_list(payload.get("contradiction_list"))
        output["possible_hallucinations"] = sanitize_list(payload.get("possible_hallucinations"))
        output["overconfidence_risks"] = sanitize_list(payload.get("overconfidence_risks"))
        if is_v40_config(config):
            output["weak_assumptions"] = sanitize_list(payload.get("weak_assumptions")) or output["uncertainties"]
            output["over_certainty_risks"] = sanitize_list(payload.get("over_certainty_risks")) or output["overconfidence_risks"]
            output["counter_evidence_needed"] = sanitize_list(payload.get("counter_evidence_needed")) or output["watch_conditions"]
            output["public_boundary_risks"] = sanitize_list(payload.get("public_boundary_risks"))
            output["unsupported_checks"] = sanitize_list(payload.get("unsupported_checks")) or output["possible_hallucinations"]
            output["red_team_role"] = "audit_not_judge"
        for key in (
            "findings",
            "evidence_gaps",
            "uncertainties",
            "watch_conditions",
            "contradiction_list",
            "possible_hallucinations",
            "overconfidence_risks",
            "weak_assumptions",
            "over_certainty_risks",
            "counter_evidence_needed",
            "public_boundary_risks",
            "unsupported_checks",
        ):
            if key in output:
                output[key] = neutralize_red_team_public_terms(output.get(key))
        output = neutralize_red_team_public_terms(output)
    output["output_hash"] = v3_agent_output_hash(output)
    assert_public_safe(output)
    return output


def v3_agent_output_hash(output: dict[str, Any]) -> str:
    hash_basis = {
        key: value
        for key, value in output.items()
        if key not in {"started_at", "finished_at", "duration_seconds", "output_hash"}
    }
    return stable_hash(hash_basis)


def v3_agent_failure_record(
    *,
    agent_id: str,
    item: dict[str, str],
    config: FullAnalystConfig,
    input_context_hash: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    reason: str,
    retry_count: int = 0,
    public_safety_triggers: list[str] | None = None,
) -> dict[str, Any]:
    public_reason = public_safe_failure_category(reason)
    safe_triggers = dedupe_preserve_order(sanitize_list(public_safety_triggers or []))
    output = {
        "agent_id": agent_id,
        "agent_role": V3_AGENT_ROLE_LABELS.get(agent_id, agent_id),
        "schema": agent_output_schema_for_config(config, agent_id),
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "run_id": config.run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "model": config.model,
        "prompt_template_version": prompt_template_for_config(config),
        "input_context_hash": input_context_hash,
        "output_hash": "",
        "status": "failed",
        "failure_reason": public_reason,
        "retry_count": max(0, int(retry_count)),
        "public_safety_triggers": safe_triggers,
        "findings": [f"{agent_id} failed with public-safe category {public_reason}."],
        "evidence_refs": [],
        "evidence_gaps": [f"{agent_id} output unavailable; failure record preserved."],
        "uncertainties": ["The symbol cannot be promoted without reviewing this failed independent agent call."],
        "watch_conditions": ["Review the independent agent failure record and rerun after fixing the blocker."],
        "boundary": "research content only; does not constitute investment advice",
    }
    if agent_id == "red_team_audit":
        output["final_red_team_verdict"] = "blocked_engineering_only_if_real" if is_v40_config(config) else "blocked"
        if is_v40_config(config):
            output["red_team_role"] = "audit_not_judge"
    output["output_hash"] = v3_agent_output_hash(output)
    assert_public_safe(output)
    return output


def write_v3_agent_private_record(
    config: FullAnalystConfig,
    item: dict[str, str],
    agent_id: str,
    payload: dict[str, Any],
) -> None:
    path = private_run_dir(config) / "agents" / f"{item['exchange']}_{item['symbol']}_{agent_id}.json"
    write_private_json_atomic(path, payload)


def write_v3_agent_attempt_private_record(
    config: FullAnalystConfig,
    item: dict[str, str],
    agent_id: str,
    attempt: int,
    payload: dict[str, Any],
) -> None:
    path = private_run_dir(config) / "agents" / f"{item['exchange']}_{item['symbol']}_{agent_id}_attempt_{attempt}.json"
    write_private_json_atomic(path, payload)


def sanitize_public_text_value(
    value: Any,
    *,
    preferred_keys: tuple[str, ...] = (
        "summary",
        "text",
        "description",
        "why_today",
        "selection_reason",
        "reason",
        "purpose",
        "data_gap",
        "evidence_id",
        "source_type",
        "source_name",
    ),
    max_chars: int = 500,
) -> str:
    if isinstance(value, dict):
        parts: list[str] = []
        for key in preferred_keys:
            if key not in value:
                continue
            child = sanitize_public_text_value(value.get(key), preferred_keys=preferred_keys, max_chars=max_chars)
            if child:
                parts.append(child)
        if not parts:
            for key, child_value in list(value.items())[:4]:
                child = sanitize_public_text_value(child_value, preferred_keys=preferred_keys, max_chars=max_chars)
                if child:
                    parts.append(f"{sanitize_text(str(key))[:80]}: {child}")
        return sanitize_text("; ".join(parts))[:max_chars]
    if isinstance(value, list):
        parts = [
            sanitize_public_text_value(item, preferred_keys=preferred_keys, max_chars=max_chars)
            for item in value
        ]
        return sanitize_text("; ".join(part for part in parts if part))[:max_chars]
    if value in (None, ""):
        return ""
    return sanitize_text(str(value))[:max_chars]


def sanitize_evidence_refs(value: Any) -> list[str]:
    raw_items = value if isinstance(value, list) else ([] if value in (None, "") else [value])
    refs: list[str] = []
    for item in raw_items:
        candidate = ""
        if isinstance(item, dict):
            candidate = str(
                item.get("evidence_id")
                or item.get("source_id")
                or item.get("source_name")
                or item.get("source_type")
                or ""
            )
        else:
            candidate = str(item)
            match = re.search(r"['\"]evidence_id['\"]\s*:\s*['\"]([^'\"]+)['\"]", candidate)
            if match:
                candidate = match.group(1)
        candidate = sanitize_text(candidate)[:160]
        if candidate:
            refs.append(candidate)
    return dedupe_preserve_order(refs)[:12]


def sanitize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [sanitize_public_text_value(item, max_chars=500) for item in value if sanitize_public_text_value(item, max_chars=500)][:12]
    if value in (None, ""):
        return []
    text = sanitize_public_text_value(value, max_chars=500)
    return [text] if text else []


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    scan_text = normalize_negated_boundary_text(text)
    match = FORBIDDEN_PUBLIC_RE.search(scan_text)
    if match:
        token = re.sub(r"[^a-z0-9_ -]+", "", match.group(0).lower()).strip().replace(" ", "_")
        raise ValueError(f"forbidden_public_content_detected:{token[:80] or 'unknown'}")


def normalize_negated_boundary_text(text: str) -> str:
    """Keep public scans strict while avoiding blocks on explicit no-advice disclaimers."""

    replacements = (
        (
            re.compile(
                r"\b(?:not\s+(?:a|an)\s+|no\s+)(?:buy|sell|hold)\s+"
                r"(?:recommendation|rating|signal|instruction)s?\b",
                re.IGNORECASE,
            ),
            "no_directional_action",
        ),
        (
            re.compile(
                r"\b(?:not\s+(?:a|an)\s+|no\s+)(?:buy\s*/\s*sell\s*/\s*hold|buy,\s*sell,\s*(?:or\s*)?hold)\s+"
                r"(?:recommendation|rating|signal|instruction)s?\b",
                re.IGNORECASE,
            ),
            "no_directional_action",
        ),
        (
            re.compile(
                r"\b(?:no|not|without|do\s+not\s+(?:include|provide|constitute)|"
                r"does\s+not\s+(?:include|provide|constitute|contain)|is\s+not)"
                r"[^.。;；]{0,140}(?:target\s+prices?|target\s+price|price\s+targets?|investment\s+advice|"
                r"trading\s+signals?|directional\s+recommendations?|allocation\s+guidance|"
                r"position\s+sizing|return\s+promises?|outcome\s+promises?|performance\s+proof|science/public\s+proof|"
                r"(?:buy|sell|hold)\s+(?:recommendation|rating|signal|instruction)s?)\b",
                re.IGNORECASE,
            ),
            "no_research_boundary_claim",
        ),
        (
            re.compile(
                r"\b(?:(?:target\s+prices?|target\s+price|price\s+targets?)|"
                r"(?:buy|sell|hold)\s+(?:recommendation|rating|signal|instruction)s?)"
                r"[^.。;；]{0,40}(?:absent|missing|not\s+present|not\s+included|not\s+found)\b",
                re.IGNORECASE,
            ),
            "boundary_term_absent",
        ),
        (
            re.compile(
                r"\b(?:not\s+(?:a|an)\s+|no\s+)(?:target\s+prices?|target\s+price|price\s+targets?|position\s+sizing|return\s+promises?)\b",
                re.IGNORECASE,
            ),
            "no_price_objective",
        ),
        (
            re.compile(
                r"\b(?:without|does\s+not\s+(?:include|provide|constitute)|is\s+not\s+(?:a|an)\s+)"
                r"[^.。;；]{0,80}(?:target\s+prices?|target\s+price|price\s+targets?|position\s+sizing|return\s+promises?)\b",
                re.IGNORECASE,
            ),
            "no_price_objective",
        ),
        (
            re.compile(r"不(?:提供|构成)[^。；;]{0,30}(?:仓位|目标价|收益承诺)"),
            "no_trading_instruction_zh",
        ),
        (
            re.compile(r"不(?:输出|提供|构成)[^。；;]{0,30}(?:买入|卖出|持有建议)"),
            "no_directional_action_zh",
        ),
    )
    normalized = text
    for pattern, replacement in replacements:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def judge_symbol(symbol_payload: dict[str, Any]) -> tuple[str, list[str]]:
    market_data_snapshot = symbol_payload.get("market_data_snapshot") if isinstance(symbol_payload.get("market_data_snapshot"), dict) else {}
    if market_data_snapshot.get("future_data_risk"):
        return "blocked", ["market data snapshot reports future_data_risk"]
    if symbol_payload["price_coverage_status"] == "data_gap":
        return "needs_review", ["price coverage is data_gap; do not promote to publish"]
    assert_public_safe(symbol_payload)
    required_sections = (
        "research_context",
        "k_deep_research",
        "f_partner_view",
        "w_partner_view",
        "g_partner_view",
        "chairman_synthesis",
        "red_team_audit",
    )
    empty_sections = [key for key in required_sections if not section_summary(symbol_payload.get(key), "")]
    required_lists = ("evidence_gaps", "watch_conditions", "source_notes")
    empty_lists = [key for key in required_lists if not symbol_payload.get(key)]
    empty = empty_sections + empty_lists
    if empty:
        return "blocked", [f"empty required analyst sections: {','.join(empty)}"]
    if symbol_payload["execution_model"] != EXECUTION_MODEL:
        return "blocked", ["execution_model must be multi_perspective_single_call for v2"]
    return "publish", ["public-safe Ksana 4.1-lite research object passed local judge gate"]


def alaya_sync(symbol_payload: dict[str, Any], alaya_client: AlayaSyncClient, config: FullAnalystConfig) -> dict[str, Any]:
    if symbol_payload["judge_status"] != "publish" and symbol_payload.get("schema") not in {SYMBOL_SCHEMA_V3, SYMBOL_SCHEMA_V35, SYMBOL_SCHEMA_V40}:
        return {
            "status": "skipped",
            "reason": "judge_status_not_publish",
            "readback_status": "skipped",
            "write_seconds": 0.0,
            "readback_seconds": 0.0,
            "total_seconds": 0.0,
        }
    if config.alaya_mode == "off":
        return {
            "status": "skipped",
            "reason": "alaya_mode_off",
            "readback_status": "skipped",
            "write_seconds": 0.0,
            "readback_seconds": 0.0,
            "total_seconds": 0.0,
        }
    result = alaya_client.sync(symbol_payload)
    if result.get("status") != "synced":
        return {
            "status": "failed",
            "reason": public_safe_failure_category(str(result.get("reason") or "unknown")),
            "event_id": sanitize_text(str(result.get("event_id") or ""))[:160],
            "event_hash": sanitize_text(str(result.get("event_hash") or ""))[:160],
            "readback_status": sanitize_text(str(result.get("readback_status") or "failed"))[:80],
            "write_seconds": float(result.get("write_seconds") or 0.0),
            "readback_seconds": float(result.get("readback_seconds") or 0.0),
            "total_seconds": float(result.get("total_seconds") or 0.0),
        }
    write_private_json_atomic(
        private_run_dir(config) / "alaya_events" / f"{symbol_payload['exchange']}_{symbol_payload['symbol']}.json",
        sanitize_private_metadata(result),
    )
    return result


def run_jobs(
    items: list[dict[str, str]],
    price_rows: dict[str, dict[str, Any]],
    config: FullAnalystConfig,
    runner: AnalystRunner,
    alaya_client: AlayaSyncClient,
    *,
    started_at_utc: str,
) -> list[dict[str, Any]]:
    sample_symbols = tuple(f"{item['exchange']}:{item['symbol']}" for item in items)
    if config.max_concurrency == 1:
        results = []
        for item in items:
            refresh_loop_runtime_heartbeat(
                config,
                phase="llm",
                started_at_utc=started_at_utc,
                sample_symbols=sample_symbols,
            )
            results.append(
                run_symbol(
                    item,
                    price_rows[f"{item['exchange']}:{item['symbol']}"],
                    config,
                    runner,
                    alaya_client,
                )
            )
        return results
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=config.max_concurrency) as executor:
        refresh_loop_runtime_heartbeat(
            config,
            phase="llm",
            started_at_utc=started_at_utc,
            sample_symbols=sample_symbols,
        )
        futures = {
            executor.submit(run_symbol, item, price_rows[f"{item['exchange']}:{item['symbol']}"], config, runner, alaya_client): item
            for item in items
        }
        for future in as_completed(futures):
            refresh_loop_runtime_heartbeat(
                config,
                phase="llm",
                started_at_utc=started_at_utc,
                sample_symbols=sample_symbols,
            )
            results.append(future.result())
    return sorted(results, key=lambda row: (str(row["exchange"]), str(row["symbol"])))


def build_status(
    *,
    config: FullAnalystConfig,
    results: list[dict[str, Any]],
    started_at_utc: str,
    elapsed_seconds: float,
    report_path: Path,
    status_path: Path,
) -> dict[str, Any]:
    active_schema = symbol_schema_for_config(config)
    active_prompt_template = prompt_template_for_config(config)
    active_methodology = methodology_for_config(config)
    active_execution_model = execution_model_for_config(config)
    failed = [row for row in results if row["status"] != "success"]
    blocked = [row for row in results if row["judge_status"] == "blocked"]
    needs_review = [row for row in results if row["judge_status"] == "needs_review"]
    publish = [row for row in results if row["judge_status"] == "publish"]
    alaya_failed = [row for row in results if row["alaya_sync_status"] == "failed"]
    alaya_synced = [row for row in results if row["alaya_sync_status"] == "synced"]
    alaya_readback_failed = [
        row for row in results if row.get("alaya_readback_status") in {"failed", "mismatch"}
    ]
    alaya_verified = [row for row in results if row.get("alaya_readback_status") == "verified"]
    run_status = "completed"
    if failed or blocked or alaya_failed or alaya_readback_failed:
        run_status = "completed_with_blockers"
    elif needs_review:
        run_status = "completed_with_review_items"
    exit_status = 0 if not failed and not blocked and not alaya_failed and not alaya_readback_failed else 2
    alaya_sync_status = "ok"
    if config.alaya_mode == "off":
        alaya_sync_status = "skipped"
    elif alaya_failed:
        alaya_sync_status = "failed"
    elif not publish and not alaya_synced:
        alaya_sync_status = "skipped"
    alaya_readback_status = "not_applicable"
    if config.alaya_mode == "real":
        if alaya_readback_failed:
            alaya_readback_status = "failed"
        elif alaya_verified:
            alaya_readback_status = "verified"
        elif publish:
            alaya_readback_status = "missing"
    last_error_category = first_error_category(failed, blocked, alaya_failed, alaya_readback_failed)
    current_cycle = max(1, config.loop_current_cycle)
    last_successful_cycle = current_cycle if exit_status == 0 else config.loop_last_successful_cycle
    selected_symbol_keys = symbol_keys_from_results(results)
    exchange_counts = exchange_counts_from_results(results)
    status = {
        "schema": STATUS_SCHEMA,
        "ok": exit_status == 0,
        "run_status": run_status,
        "mode": config.mode,
        "run_id": config.run_id,
        "status": "completed" if exit_status == 0 else "failed",
        "phase": "artifact",
        "current_cycle": current_cycle,
        "last_successful_cycle": last_successful_cycle,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "sample_symbols": selected_symbol_keys,
        "universe_count": len(results),
        "symbol_count": len(results),
        "exchange_counts": exchange_counts,
        "symbol_hash": stable_hash(selected_symbol_keys),
        "success_count": sum(1 for row in results if row["status"] == "success"),
        "failed_count": len(failed),
        "publish_count": len(publish),
        "needs_review_count": len(needs_review),
        "blocked_count": len(blocked),
        "data_gap_count": sum(1 for row in results if row["price_coverage_status"] == "data_gap"),
        "alaya_synced_count": sum(1 for row in results if row["alaya_sync_status"] == "synced"),
        "alaya_failed_count": len(alaya_failed),
        "alaya_readback_verified_count": len(alaya_verified),
        "alaya_readback_failed_count": len(alaya_readback_failed),
        "alaya_write_seconds": round(sum(float(row.get("alaya_write_seconds") or 0.0) for row in results), 3),
        "alaya_readback_seconds": round(
            sum(float(row.get("alaya_readback_seconds") or 0.0) for row in results),
            3,
        ),
        "alaya_total_seconds": round(sum(float(row.get("alaya_total_seconds") or 0.0) for row in results), 3),
        "alaya_sync_status": alaya_sync_status,
        "alaya_readback_status": alaya_readback_status,
        "failed_symbols": failure_rows(failed),
        "blocked_symbols": failure_rows(blocked),
        "needs_review_symbols": failure_rows(needs_review),
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "last_heartbeat_utc": utc_now_iso(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "remaining_seconds": 0,
        "consecutive_failures": 1 if exit_status else 0,
        "llm_runner": config.llm_runner,
        "llm_model": config.model,
        "max_concurrency": config.max_concurrency,
        "agent_concurrency": config.agent_concurrency if is_v3_config(config) else None,
        "agent_parallelism": config.agent_concurrency if is_v3_config(config) else None,
        "v3_independent_agents": is_v3_config(config),
        "requested_execution_model": config.requested_execution_model,
        "explicit_v2_fallback": config.explicit_v2_fallback,
        "agent_calls_total": sum(int(row.get("agent_calls_total") or 0) for row in results),
        "research_task_seconds": round(sum(float(row.get("research_task_seconds") or 0.0) for row in results), 3),
        "evidence_packet_seconds": round(sum(float(row.get("evidence_packet_seconds") or 0.0) for row in results), 3),
        "k_dossier_seconds": round(sum(float(row.get("k_dossier_seconds") or 0.0) for row in results), 3),
        "reasoning_effort": config.reasoning_effort,
        "timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "alaya_mode": config.alaya_mode,
        "candidate_service": config.candidate_service,
        "candidate_timer": config.candidate_timer,
        "rollback_hint": rollback_hint(config),
        "prompt_template_version": active_prompt_template,
        "symbol_schema": active_schema,
        "market_data_snapshot_schema": MARKET_DATA_SNAPSHOT_SCHEMA,
        "research_task_schema": research_task_schema_for_config(config) if has_research_task_system(config) else None,
        "evidence_packet_schema": evidence_packet_schema_for_config(config) if has_research_task_system(config) else None,
        "k_dossier_schema": K_DOSSIER_SCHEMA if is_v40_config(config) else None,
        "perspective_agent_schema": PERSPECTIVE_AGENT_SCHEMA_V4 if is_v40_config(config) else None,
        "chairman_schema": CHAIRMAN_SCHEMA_V4 if is_v40_config(config) else None,
        "red_team_schema": RED_TEAM_SCHEMA_V4 if is_v40_config(config) else None,
        "research_quality_gate_schema": RESEARCH_QUALITY_GATE_SCHEMA if is_v40_config(config) else None,
        "knowledge_gate_schema": KNOWLEDGE_GATE_SCHEMA if is_v40_config(config) else None,
        "research_signal_schema": RESEARCH_SIGNAL_SCHEMA if is_v40_config(config) else None,
        "publication_decision_schema": PUBLICATION_DECISION_SCHEMA if is_v40_config(config) else None,
        "daily_reader_schema": DAILY_READER_SCHEMA_V40 if is_v40_config(config) else None,
        "methodology_version": active_methodology,
        "execution_model": active_execution_model,
        "alaya_event_schema": ALAYA_EVENT_SCHEMA_V40 if is_v40_config(config) else ALAYA_EVENT_SCHEMA_V35 if is_v35_config(config) else ALAYA_EVENT_SCHEMA_V3 if is_v3_config(config) else ALAYA_EVENT_SCHEMA,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "latest_public_report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "ok",
        "artifact_write_failure_reason": None,
        "public_scan_status": "ok",
        "last_error_category": last_error_category,
        "last_error_public_message": public_error_message(last_error_category),
        "heartbeat_stale": False,
        "provider_model_io_embedded": False,
        "evidence_layer": evidence_layer_for_mode(config.mode),
        "limitations": [
            "not 10h evidence" if config.mode == LOOP_SMOKE_MODE else "not formal acceptance",
            "not science/public proof",
            "not performance proof",
            "not a trading signal",
            "not investment advice",
        ],
    }
    status["stage_statuses"] = stage_statuses_for_status(status, publish_static=config.publish_static)
    status["exit_status"] = exit_status
    return status


def symbol_keys_from_results(results: list[dict[str, Any]]) -> list[str]:
    return [
        f"{row['exchange']}:{row['symbol']}"
        for row in sorted(results, key=lambda row: (str(row["exchange"]), str(row["symbol"])))
    ]


def exchange_counts_from_results(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in results:
        exchange = str(row["exchange"])
        counts[exchange] = counts.get(exchange, 0) + 1
    return dict(sorted(counts.items()))


def exchange_counts_from_symbol_keys(symbols: tuple[str, ...] | list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in symbols:
        exchange, _, _symbol = str(key).partition(":")
        if not exchange:
            continue
        counts[exchange] = counts.get(exchange, 0) + 1
    return dict(sorted(counts.items()))


def stage_statuses_for_status(status: dict[str, Any], *, publish_static: bool) -> dict[str, str]:
    data_gap_count = int(status.get("data_gap_count") or 0)
    failed_count = int(status.get("failed_count") or 0)
    blocked_count = int(status.get("blocked_count") or 0)
    needs_review_count = int(status.get("needs_review_count") or 0)
    return {
        "data_fetch": "data_gap" if data_gap_count else "ok",
        "llm_analyst": "failed" if failed_count else "ok",
        "judge_gate": "blocked" if blocked_count else "needs_review" if needs_review_count else "ok",
        "alaya_sync": str(status.get("alaya_sync_status") or "not_reported"),
        "alaya_readback": str(status.get("alaya_readback_status") or "not_reported"),
        "public_safety_scan": str(status.get("public_scan_status") or "not_reported"),
        "artifact_write": str(status.get("artifact_write_status") or "not_reported"),
        "public_publish": "published" if publish_static else "local_only",
    }


def rollback_hint(config: FullAnalystConfig) -> str | None:
    if not config.candidate_service and not config.candidate_timer:
        return None
    service = config.candidate_service or "gotra-full-analyst-evening-hk-candidate.service"
    timer = config.candidate_timer or "gotra-full-analyst-evening-hk-candidate.timer"
    return f"disable {timer}/{service}, or edit the candidate service to max_concurrency=1 and daemon-reload"


def failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "exchange": row["exchange"],
            "symbol": row["symbol"],
            "provider_ticker": row["provider_ticker"],
            "judge_status": row["judge_status"],
            "reason": "; ".join(row.get("judge_reasons") or [row.get("failure_reason", "")]),
        }
        for row in rows
    ]


def first_error_category(*groups: list[dict[str, Any]]) -> str | None:
    for rows in groups:
        for row in rows:
            if row.get("alaya_sync_status") == "failed":
                return public_safe_failure_category(
                    str(row.get("alaya_failure_reason") or row.get("alaya_readback_status") or "alaya_sync_failed")
                )
            reasons = row.get("judge_reasons") or [row.get("failure_reason") or row.get("alaya_sync_status")]
            if reasons:
                return public_safe_failure_category(str(reasons[0]))
    return None


def public_error_message(category: str | None) -> str | None:
    if not category:
        return None
    return f"Public-safe blocker category: {category}"


def public_safe_failure_category(reason: str) -> str:
    text = sanitize_text(str(reason or "unknown")).lower()
    if "readback_mismatch" in text or "mismatch" in text:
        return "alaya_readback_mismatch"
    if "readback" in text:
        return "alaya_readback_failed"
    if "gotra_internal_state" in text:
        return "gotra_internal_state_sync_failed"
    if "alaya" in text and ("http" in text or "write" in text or "sync" in text):
        return "alaya_sync_failed"
    if "missing_required_fields" in text:
        return "missing_required_fields"
    if "forbidden_raw_io_keys" in text:
        return "forbidden_raw_io_keys_detected"
    if "forbidden_public_content_detected" in text:
        return "forbidden_public_content_detected"
    if "artifact" in text or "permission" in text:
        return "artifact_write_failed"
    return re.sub(r"[^a-z0-9_]+", "_", text)[:80].strip("_") or "unknown_failure"


def public_safe_trigger_label(reason: str) -> str:
    """Expose retry trigger classes without republishing unsafe terms."""

    text = sanitize_text(str(reason or "")).lower()
    if not text:
        return ""
    token = text.rsplit(":", 1)[-1] if "forbidden_public_content_detected" in text else text
    if "target" in token or "price_objective" in token:
        return "price_objective_wording"
    if any(term in token for term in ("buy", "sell", "hold", "directional", "trading_signal", "trading signal")):
        return "directional_action_wording"
    if "position" in token or "allocation" in token or "仓位" in token:
        return "allocation_guidance_wording"
    if "return" in token or "outcome" in token or "收益" in token:
        return "outcome_promise_wording"
    if (
        "raw" in token
        or "stdout" in token
        or "stderr" in token
        or "prompt" in token
        or "completion" in token
        or "message" in token
        or "secret" in token
    ):
        return "raw_io_or_secret_wording"
    if "forbidden_public_content_detected" in text:
        return "public_boundary_wording"
    return ""


def evidence_layer_for_mode(mode: str) -> str:
    if mode == LOOP_SMOKE_MODE:
        return "local checks + short loop smoke + public-safe artifact smoke"
    if mode == LOOP_MODE:
        return "local checks + server runtime loop evidence + public-safe artifact smoke"
    return "local checks + one-shot runtime smoke + public-safe artifact smoke"


def report_paths(config: FullAnalystConfig) -> tuple[Path, Path]:
    if config.mode in LOOP_MODES:
        return config.output_dir / "full_analyst_loop_latest.md", config.output_dir / "status_full_analyst_loop.json"
    report_path = config.output_dir / f"full_analyst_evening_hk_{config.as_of_date.isoformat()}.md"
    status_path = config.output_dir / "status_full_analyst_evening_hk.json"
    return report_path, status_path


def write_outputs(config: FullAnalystConfig, results: list[dict[str, Any]], status: dict[str, Any]) -> dict[str, str]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "symbols").mkdir(parents=True, exist_ok=True)
    report_path, status_path = report_paths(config)
    symbol_payloads = [row["research"] for row in results if row.get("research")]
    ledger_result: dict[str, Any] | None = None
    if is_v40_config(config):
        ledger_result = write_research_ledger(config, symbol_payloads=symbol_payloads, status=status)
        status["ledger_schema"] = ledger_result["schema"]
        status["ledger_file"] = ledger_result["file"]
        status["ledger_entry_count"] = ledger_result["entry_count"]
        status["ledger_appended_count"] = ledger_result["appended_count"]
        status["ledger_integrity_status"] = "ok" if ledger_result["integrity"].get("ok") else "failed"
        status["ledger_latest_hash"] = ledger_result["integrity"].get("latest_hash", "")
    scan_public_artifacts(status=status, results=results, symbol_payloads=symbol_payloads)
    for row in results:
        if row.get("research"):
            write_public_json(config.output_dir / "symbols" / f"{row['exchange']}_{row['symbol']}.json", row["research"])
    markdown = render_markdown(status, results)
    scan_public_text(markdown)
    write_public_text(report_path, markdown)
    write_public_json(status_path, status)
    if config.publish_static:
        publish_static(report_path, status_path, config.static_dir, ledger_path=ledger_result["path"] if ledger_result else None)
    paths = {"report_path": str(report_path.resolve()), "status_path": str(status_path.resolve())}
    if ledger_result:
        paths["ledger_path"] = str(ledger_result["path"].resolve())
    return paths


def write_public_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    path.chmod(0o644)


def write_public_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    scan_public_text(text)
    write_public_text(path, text)


def scan_public_artifacts(*, status: dict[str, Any], results: list[dict[str, Any]], symbol_payloads: list[dict[str, Any]]) -> None:
    del results
    scan_public_text(json.dumps(status, ensure_ascii=False, sort_keys=True))
    for payload in symbol_payloads:
        scan_public_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def scan_public_text(text: str) -> None:
    try:
        assert_public_safe(text)
    except Exception as exc:  # noqa: BLE001 - collapse scanner details to a public-safe category.
        raise PublicScanError(public_safe_failure_category(str(exc))) from exc


def publish_static(report_path: Path, status_path: Path, static_dir: Path, *, ledger_path: Path | None = None) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    paths = [report_path, status_path]
    if ledger_path is not None:
        paths.append(ledger_path)
    for path in paths:
        target = static_dir / path.name
        shutil.copy2(path, target)
        target.chmod(0o644)


def render_markdown(status: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        f"# GOTRA Full Analyst Pipeline - {status['as_of_date']}",
        "",
        "## Evidence Layer",
        "",
        f"- {status['evidence_layer']}",
        "- not formal acceptance",
        "- not science/public proof",
        "- not performance proof",
        "- not a trading signal",
        "- not investment advice",
        "",
        "## Status",
        "",
        f"- mode: {status['mode']}",
        f"- run_id: {status['run_id']}",
        f"- run_status: {status['run_status']}",
        f"- phase: {status['phase']}",
        f"- last_heartbeat_utc: {status['last_heartbeat_utc']}",
        f"- trading_date: {status['trading_date']}",
        f"- universe_count: {status['universe_count']}",
        f"- exchange_counts: {json.dumps(status.get('exchange_counts', {}), sort_keys=True)}",
        f"- symbol_hash: {status.get('symbol_hash')}",
        f"- llm_runner: {status['llm_runner']}",
        f"- llm_model: {status['llm_model']}",
        f"- max_concurrency: {status.get('max_concurrency')}",
        f"- agent_concurrency: {status.get('agent_concurrency') if status.get('agent_concurrency') is not None else 'not_applicable'}",
        f"- v3_independent_agents: {status.get('v3_independent_agents')}",
        f"- requested_execution_model: {status.get('requested_execution_model')}",
        f"- explicit_v2_fallback: {status.get('explicit_v2_fallback')}",
        f"- agent_calls_total: {status.get('agent_calls_total')}",
        f"- research_task_seconds: {status.get('research_task_seconds', 0)}",
        f"- evidence_packet_seconds: {status.get('evidence_packet_seconds', 0)}",
        f"- k_dossier_seconds: {status.get('k_dossier_seconds', 0)}",
        f"- prompt_template_version: {status.get('prompt_template_version')}",
        f"- symbol_schema: {status.get('symbol_schema')}",
        f"- research_task_schema: {status.get('research_task_schema') or 'not_applicable'}",
        f"- evidence_packet_schema: {status.get('evidence_packet_schema') or 'not_applicable'}",
        f"- k_dossier_schema: {status.get('k_dossier_schema') or 'not_applicable'}",
        f"- perspective_agent_schema: {status.get('perspective_agent_schema') or 'not_applicable'}",
        f"- chairman_schema: {status.get('chairman_schema') or 'not_applicable'}",
        f"- red_team_schema: {status.get('red_team_schema') or 'not_applicable'}",
        f"- research_quality_gate_schema: {status.get('research_quality_gate_schema') or 'not_applicable'}",
        f"- knowledge_gate_schema: {status.get('knowledge_gate_schema') or 'not_applicable'}",
        f"- research_signal_schema: {status.get('research_signal_schema') or 'not_applicable'}",
        f"- publication_decision_schema: {status.get('publication_decision_schema') or 'not_applicable'}",
        f"- daily_reader_schema: {status.get('daily_reader_schema') or 'not_applicable'}",
        f"- methodology_version: {status.get('methodology_version')}",
        f"- execution_model: {status.get('execution_model')}",
        f"- alaya_event_schema: {status.get('alaya_event_schema')}",
        f"- candidate_service: {status.get('candidate_service') or 'not_reported'}",
        f"- candidate_timer: {status.get('candidate_timer') or 'not_reported'}",
        f"- publish_count: {status['publish_count']}",
        f"- needs_review_count: {status['needs_review_count']}",
        f"- blocked_count: {status['blocked_count']}",
        f"- failed_count: {status['failed_count']}",
        f"- data_gap_count: {status['data_gap_count']}",
        f"- alaya_synced_count: {status['alaya_synced_count']}",
        f"- alaya_failed_count: {status['alaya_failed_count']}",
        f"- alaya_readback_verified_count: {status['alaya_readback_verified_count']}",
        f"- alaya_readback_failed_count: {status['alaya_readback_failed_count']}",
        f"- alaya_write_seconds: {status['alaya_write_seconds']}",
        f"- alaya_readback_seconds: {status['alaya_readback_seconds']}",
        f"- alaya_total_seconds: {status['alaya_total_seconds']}",
        f"- alaya_mode: {status['alaya_mode']}",
        f"- alaya_sync_status: {status['alaya_sync_status']}",
        f"- alaya_readback_status: {status['alaya_readback_status']}",
        f"- public_scan_status: {status['public_scan_status']}",
        "",
        "## Stage Statuses",
        "",
        *[f"- {key}: {value}" for key, value in status.get("stage_statuses", {}).items()],
        "",
        "## Boundary",
        "",
        *[f"- {line}" for line in BOUNDARY_LINES],
        "",
        "## Symbol Results",
        "",
    ]
    for row in results:
        research = row.get("research") or {}
        lines.extend(
            [
                f"### {row['exchange']}:{row['symbol']}",
                "",
                f"- execution_model: {research.get('execution_model', status.get('execution_model', 'not_reported')) if research else status.get('execution_model', 'not_reported')}",
                f"- prompt_template_version: {research.get('prompt_template_version', status.get('prompt_template_version', 'not_reported')) if research else status.get('prompt_template_version', 'not_reported')}",
                f"- methodology_version: {research.get('methodology_version', status.get('methodology_version', 'not_reported')) if research else status.get('methodology_version', 'not_reported')}",
                f"- price_coverage_status: {row['price_coverage_status']}",
                f"- judge_status: {row['judge_status']}",
                f"- research_status: {research.get('research_status', 'not_reported') if research else 'not_reported'}",
                f"- alaya_sync_status: {row['alaya_sync_status']}",
                f"- alaya_readback_status: {row.get('alaya_readback_status', 'not_applicable')}",
                f"- judge_reasons: {'; '.join(row.get('judge_reasons') or [])}",
            ]
        )
        if row["judge_status"] == "blocked" or not research:
            lines.extend(["- public_summary: blocked from public publish summary", ""])
            continue
        lines.extend(
            [
                f"- chairman_synthesis: {section_summary(research['chairman_synthesis'], research['research_summary'])}",
                "- k_deep_research:",
                *[f"  - {item}" for item in section_list(research["k_deep_research"], "No K research summary reported.")],
                "- f_partner_view:",
                *[f"  - {item}" for item in section_list(research["f_partner_view"], "No F partner view reported.")],
                "- w_partner_view:",
                *[f"  - {item}" for item in section_list(research["w_partner_view"], "No W partner view reported.")],
                "- g_partner_view:",
                *[f"  - {item}" for item in section_list(research["g_partner_view"], "No G partner view reported.")],
                "- red_team_audit:",
                *[f"  - {item}" for item in section_list(research["red_team_audit"], "No red-team audit reported.")],
                "- evidence_gaps:",
                *[f"  - {item}" for item in research["evidence_gaps"]],
                "- watch_conditions:",
                *[f"  - {item}" for item in research["watch_conditions"]],
                f"- confidence_boundary: {research['confidence_boundary']}",
                "- source_notes:",
                *[f"  - {item}" for item in research["source_notes"]],
                "",
            ]
        )
        if research.get("schema") in {SYMBOL_SCHEMA_V35, SYMBOL_SCHEMA_V40}:
            task = research.get("research_task") if isinstance(research.get("research_task"), dict) else {}
            packet = research.get("evidence_packet") if isinstance(research.get("evidence_packet"), dict) else {}
            evidence_items = packet.get("evidence_items") if isinstance(packet.get("evidence_items"), list) else []
            lines.extend(
                [
                    "- research_task:",
                    f"  - task_hash: {research.get('research_task_hash', '')}",
                    f"  - selection_reason: {task.get('selection_reason', 'not_reported')}",
                    f"  - research_mission: {task.get('research_mission', 'not_reported')}",
                    "  - core_questions:",
                    *[f"    - {item}" for item in sanitize_list(task.get("core_questions"))[:6]],
                    "  - must_not_conclude_without:",
                    *[f"    - {item}" for item in sanitize_list(task.get("must_not_conclude_without"))[:8]],
                    "- evidence_packet:",
                    f"  - evidence_packet_hash: {research.get('evidence_packet_hash', '')}",
                    f"  - evidence_items_count: {len(evidence_items)}",
                    "  - missing_required_sources:",
                    *[
                        f"    - {source.get('source_type', 'unknown')}: {source.get('purpose', '')}"
                        for source in (packet.get("missing_required_sources") if isinstance(packet.get("missing_required_sources"), list) else [])[:8]
                        if isinstance(source, dict)
                    ],
                    "  - data_gaps:",
                    *[f"    - {item}" for item in sanitize_list(packet.get("data_gaps"))[:8]],
                    "",
                ]
            )
        if research.get("schema") == SYMBOL_SCHEMA_V40:
            signal = research.get("research_signal") if isinstance(research.get("research_signal"), dict) else {}
            decision = research.get("publication_decision") if isinstance(research.get("publication_decision"), dict) else {}
            dossier = research.get("k_deep_research_dossier") if isinstance(research.get("k_deep_research_dossier"), dict) else {}
            quality_gate = research.get("research_quality_gate") if isinstance(research.get("research_quality_gate"), dict) else {}
            knowledge_gate = research.get("knowledge_gate") if isinstance(research.get("knowledge_gate"), dict) else {}
            boundary_gate = research.get("reader_boundary_gate") if isinstance(research.get("reader_boundary_gate"), dict) else {}
            lines.extend(
                [
                    "- research_signal:",
                    f"  - research_signal_hash: {research.get('research_signal_hash', '')}",
                    f"  - hypothesis: {signal.get('hypothesis', 'not_reported')}",
                    f"  - confidence: {signal.get('confidence', 'not_reported')}",
                    f"  - window_days: {signal.get('window_days', 'not_reported')}",
                    f"  - review_due_at: {signal.get('review_due_at', 'not_reported')}",
                    "  - evidence_ids:",
                    *[f"    - {item}" for item in sanitize_list(signal.get("evidence_ids"))[:8]],
                    "  - counter_evidence:",
                    *[f"    - {item}" for item in sanitize_list(signal.get("counter_evidence"))[:8]],
                    "  - uncertainty:",
                    *[f"    - {item}" for item in sanitize_list(signal.get("uncertainty"))[:8]],
                    "- publication_decision:",
                    f"  - publication_decision_hash: {research.get('publication_decision_hash', '')}",
                    f"  - decision: {decision.get('decision', 'not_reported')}",
                    f"  - blocker_type: {decision.get('blocker_type', '')}",
                    "  - reader_safe_reasons:",
                    *[f"    - {item}" for item in sanitize_list(decision.get("reader_safe_reasons"))[:8]],
                    "- k_deep_research_dossier:",
                    f"  - k_dossier_hash: {research.get('k_dossier_hash', '')}",
                    f"  - dossier_summary: {dossier.get('dossier_summary', 'not_reported')}",
                    "  - deep_findings:",
                    *[f"    - {item}" for item in sanitize_list(dossier.get("deep_findings"))[:8]],
                    "  - key_uncertainties:",
                    *[f"    - {item}" for item in sanitize_list(dossier.get("key_uncertainties"))[:8]],
                    "  - must_verify_next:",
                    *[f"    - {item}" for item in sanitize_list(dossier.get("must_verify_next"))[:8]],
                    "- research_quality_gate:",
                    f"  - research_quality_gate_hash: {research.get('research_quality_gate_hash', '')}",
                    f"  - research_status: {quality_gate.get('research_status', 'not_reported')}",
                    f"  - quality_verdict: {quality_gate.get('quality_verdict', 'not_reported')}",
                    f"  - publish_with_boundary: {quality_gate.get('publish_with_boundary', 'not_reported')}",
                    f"  - engineering_blocker: {quality_gate.get('engineering_blocker', 'not_reported')}",
                    f"  - red_team_is_judge: {quality_gate.get('red_team_is_judge', 'not_reported')}",
                    "  - reasons:",
                    *[f"    - {item}" for item in sanitize_list(quality_gate.get("reasons"))[:8]],
                    "- knowledge_gate:",
                    f"  - knowledge_gate_hash: {research.get('knowledge_gate_hash', '')}",
                    f"  - knowledge_persistence: {knowledge_gate.get('knowledge_persistence', 'not_reported')}",
                    "  - knowledge_items_to_persist:",
                    *[f"    - {item}" for item in sanitize_list(knowledge_gate.get("knowledge_items_to_persist"))[:8]],
                    "  - unresolved_questions:",
                    *[f"    - {item}" for item in sanitize_list(knowledge_gate.get("unresolved_questions"))[:8]],
                    "  - future_research_tasks:",
                    *[f"    - {item}" for item in sanitize_list(knowledge_gate.get("future_research_tasks"))[:8]],
                    "- reader_boundary_gate:",
                    f"  - reader_boundary_gate_hash: {research.get('reader_boundary_gate_hash', '')}",
                    f"  - status: {boundary_gate.get('status', 'not_reported')}",
                    f"  - does_not_hide_research_content: {boundary_gate.get('does_not_hide_research_content', 'not_reported')}",
                    f"  - data_gap_visible: {boundary_gate.get('data_gap_visible', 'not_reported')}",
                    f"  - needs_review_visible: {boundary_gate.get('needs_review_visible', 'not_reported')}",
                    f"  - red_team_visible: {boundary_gate.get('red_team_visible', 'not_reported')}",
                    "",
                ]
            )
        if research.get("schema") in {SYMBOL_SCHEMA_V3, SYMBOL_SCHEMA_V35, SYMBOL_SCHEMA_V40}:
            lines.extend(
                [
                    "- agent_statuses:",
                    *[
                        f"  - {agent_id}: {research.get('agent_statuses', {}).get(agent_id, 'not_reported')}"
                        for agent_id in V3_AGENT_IDS
                    ],
                    "- agent_hashes:",
                    *[
                        f"  - {agent_id}: {research.get('agent_hashes', {}).get(agent_id, '')}"
                        for agent_id in V3_AGENT_IDS
                    ],
                    "- agent_timings:",
                    *[
                        f"  - {key}: {value}"
                        for key, value in research.get("agent_timings", {}).items()
                    ],
                    "- parallelism:",
                    *[
                        f"  - {key}: {value}"
                        for key, value in research.get("parallelism", {}).items()
                    ],
                    f"- red_team_verdict: {research.get('red_team_verdict', 'not_reported')}",
                    f"- public_payload_hash: {research.get('public_payload_hash', row.get('public_payload_hash', ''))}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_private_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    allowed = {
        "status",
        "mode",
        "event_schema",
        "event_id",
        "event_hash",
        "knowledge_id",
        "feedback_ref",
        "research_task_hash",
        "evidence_packet_hash",
        "k_dossier_hash",
        "research_quality_gate_hash",
        "knowledge_gate_hash",
        "reader_boundary_gate_hash",
        "research_signal_hash",
        "publication_decision_hash",
        "prompt_hash",
        "research_packet_hash",
        "public_payload_hash",
        "knowledge_persistence",
        "readback_status",
        "reason",
        "schema",
        "project_id",
        "actor",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = sanitize_text(str(value))[:500] if isinstance(value, str) else value
    return sanitized


def runner_from_config(config: FullAnalystConfig) -> AnalystRunner:
    if config.llm_runner == "fixture":
        return FixtureAnalystRunner()
    return CodexCliRunner(
        codex_bin=config.codex_bin,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        cwd=REPO_ROOT,
    )


def alaya_client_from_config(config: FullAnalystConfig) -> AlayaSyncClient:
    if config.alaya_mode == "real":
        return GotraInternalAlayaSyncClient.from_config(config)
    return MockAlayaSyncClient()


def preflight_llm_config(config: FullAnalystConfig, runner: AnalystRunner | None) -> None:
    if config.llm_runner != "codex-cli" or runner is not None:
        return
    if config.model != "gpt-5.5":
        raise ConfigurationBlocker("codex_model_must_be_gpt_5_5")


def write_heartbeat(config: FullAnalystConfig, *, status: str, phase: str, current_cycle: int, last_successful_cycle: int, started_at_utc: str, last_error_category: str | None = None) -> None:
    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    elapsed = max(0, int((datetime.now(UTC) - started).total_seconds()))
    remaining = max(0, int(config.loop_duration_seconds - elapsed)) if config.mode in LOOP_MODES else 0
    payload = {
        "run_id": config.run_id,
        "status": status,
        "phase": phase,
        "current_cycle": current_cycle,
        "last_heartbeat_utc": utc_now_iso(),
        "last_successful_cycle": last_successful_cycle,
        "last_error_category": last_error_category,
        "consecutive_failures": 1 if last_error_category else 0,
        "elapsed_seconds": elapsed,
        "remaining_seconds": remaining,
    }
    write_private_json_atomic(private_run_dir(config) / "heartbeat.json", payload)


def append_event(config: FullAnalystConfig, event_type: str, payload: dict[str, Any]) -> None:
    event = {
        "run_id": config.run_id,
        "event_type": event_type,
        "created_at_utc": utc_now_iso(),
        "payload": sanitize_private_metadata(payload),
    }
    path = private_run_dir(config) / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_failure_records(config: FullAnalystConfig, results: list[dict[str, Any]], status: dict[str, Any]) -> None:
    failures = []
    for row in results:
        research = row.get("research") if isinstance(row.get("research"), dict) else {}
        for failure in research.get("failure_records", []) if isinstance(research.get("failure_records"), list) else []:
            failures.append(
                {
                    "run_id": config.run_id,
                    "created_at_utc": utc_now_iso(),
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "agent_id": failure.get("agent_id", "unknown_agent"),
                    "agent_output_hash": failure.get("output_hash", ""),
                    "category": public_safe_failure_category(str(failure.get("failure_reason") or "agent_failed")),
                    "stage": "independent_agent_call",
                }
            )
        if row["status"] == "success" and row["judge_status"] != "blocked" and row["alaya_sync_status"] != "failed":
            continue
        failures.append(
            {
                "run_id": config.run_id,
                "created_at_utc": utc_now_iso(),
                "exchange": row["exchange"],
                "symbol": row["symbol"],
                "category": public_safe_failure_category(";".join(row.get("judge_reasons") or [row.get("failure_reason", "")])),
                "stage": row["judge_status"],
            }
        )
    path = private_run_dir(config) / "failures.jsonl"
    if failures:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for failure in failures:
                handle.write(json.dumps(failure, ensure_ascii=False, sort_keys=True) + "\n")
    cycle_index = max(1, config.loop_current_cycle)
    write_private_json_atomic(
        private_run_dir(config) / f"cycle_{cycle_index:03d}_summary.json",
        sanitize_private_metadata(status)
        | {
            "run_id": config.run_id,
            "cycle_id": f"cycle_{cycle_index:03d}",
            "current_cycle": status["current_cycle"],
            "last_successful_cycle": status["last_successful_cycle"],
            "sample_symbols": list(config.symbols),
            "publish_count": status["publish_count"],
            "needs_review_count": status["needs_review_count"],
            "blocked_count": status["blocked_count"],
            "data_gap_count": status["data_gap_count"],
            "alaya_synced_count": status["alaya_synced_count"],
            "alaya_readback_verified_count": status["alaya_readback_verified_count"],
            "alaya_write_seconds": status["alaya_write_seconds"],
            "alaya_readback_seconds": status["alaya_readback_seconds"],
            "alaya_total_seconds": status["alaya_total_seconds"],
            "artifact_write_status": status["artifact_write_status"],
            "public_scan_status": status["public_scan_status"],
            "exit_status": status["exit_status"],
            "duration_seconds": status["elapsed_seconds"],
        },
    )


def write_blocker_status(config: FullAnalystConfig, *, started_at_utc: str, reason: str, report_path: Path, status_path: Path) -> int:
    category = public_safe_failure_category(reason)
    failed = {
        "schema": STATUS_SCHEMA,
        "ok": False,
        "run_status": "blocked",
        "status": "failed",
        "mode": config.mode,
        "run_id": config.run_id,
        "phase": "preflight",
        "current_cycle": 0,
        "last_successful_cycle": 0,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "sample_symbols": list(config.symbols),
        "universe_count": 0,
        "symbol_count": 0,
        "exchange_counts": {},
        "symbol_hash": stable_hash(list(config.symbols)),
        "success_count": 0,
        "failed_count": 0,
        "publish_count": 0,
        "needs_review_count": 0,
        "blocked_count": 1,
        "data_gap_count": 0,
        "alaya_synced_count": 0,
        "alaya_failed_count": 0,
        "alaya_readback_verified_count": 0,
        "alaya_readback_failed_count": 0,
        "alaya_write_seconds": 0.0,
        "alaya_readback_seconds": 0.0,
        "alaya_total_seconds": 0.0,
        "alaya_sync_status": "blocked" if config.alaya_mode == "real" else "skipped",
        "alaya_readback_status": "blocked" if config.alaya_mode == "real" else "skipped",
        "failed_symbols": [],
        "blocked_symbols": [{"exchange": "RUN", "symbol": "PREFLIGHT", "provider_ticker": "PREFLIGHT", "judge_status": "blocked", "reason": category}],
        "needs_review_symbols": [],
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "last_heartbeat_utc": utc_now_iso(),
        "elapsed_seconds": 0,
        "remaining_seconds": 0,
        "consecutive_failures": 1,
        "llm_runner": config.llm_runner,
        "llm_model": config.model,
        "max_concurrency": config.max_concurrency,
        "reasoning_effort": config.reasoning_effort,
        "timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "alaya_mode": config.alaya_mode,
        "candidate_service": config.candidate_service,
        "candidate_timer": config.candidate_timer,
        "rollback_hint": rollback_hint(config),
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "latest_public_report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "ok",
        "artifact_write_failure_reason": None,
        "public_scan_status": "ok",
        "last_error_category": category,
        "last_error_public_message": public_error_message(category),
        "heartbeat_stale": False,
        "provider_model_io_embedded": False,
        "evidence_layer": evidence_layer_for_mode(config.mode),
        "limitations": ["not 10h evidence", "not formal acceptance", "not science/public proof", "not performance proof", "not a trading signal", "not investment advice"],
        "exit_status": 2,
    }
    failed["stage_statuses"] = stage_statuses_for_status(failed, publish_static=config.publish_static)
    write_heartbeat(config, status="failed", phase="preflight", current_cycle=0, last_successful_cycle=0, started_at_utc=started_at_utc, last_error_category=category)
    append_event(config, "blocker", {"status": "failed", "reason": category})
    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_public_text(report_path, render_blocker_markdown(failed))
    write_public_json(status_path, failed)
    if config.publish_static:
        publish_static(report_path, status_path, config.static_dir)
    print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
    return 2


def render_blocker_markdown(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# GOTRA Full Analyst Pipeline - {status['as_of_date']}",
            "",
            "## Status",
            "",
            f"- run_status: {status['run_status']}",
            f"- last_error_category: {status['last_error_category']}",
            "",
            "## Evidence Layer",
            "",
            f"- {status['evidence_layer']}",
            "- not 10h evidence",
            "- not formal acceptance",
            "- not science/public proof",
            "- not performance proof",
            "- not a trading signal",
            "- not investment advice",
        ]
    ) + "\n"


def sample_symbols_for_cycle(symbols: tuple[str, ...], successful_cycles: int) -> tuple[str, ...]:
    sample_size = 3
    if successful_cycles >= 4:
        sample_size = 10
    elif successful_cycles >= 2:
        sample_size = 5
    return tuple(symbols[: min(sample_size, len(symbols))])


def build_loop_running_status(
    config: FullAnalystConfig,
    *,
    current_cycle: int,
    last_successful_cycle: int,
    loop_status: str,
    phase: str,
    started_at_utc: str,
    sample_symbols: tuple[str, ...],
    last_error_category: str | None = None,
) -> dict[str, Any]:
    report_path, status_path = report_paths(config)
    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    elapsed = max(0, int((datetime.now(UTC) - started).total_seconds()))
    status = {
        "schema": STATUS_SCHEMA,
        "ok": True,
        "run_status": "running" if loop_status == "running" else loop_status,
        "mode": config.mode,
        "run_id": config.run_id,
        "status": loop_status,
        "phase": phase,
        "current_cycle": current_cycle,
        "last_successful_cycle": last_successful_cycle,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "sample_symbols": list(sample_symbols),
        "universe_count": len(sample_symbols),
        "symbol_count": len(sample_symbols),
        "exchange_counts": exchange_counts_from_symbol_keys(sample_symbols),
        "symbol_hash": stable_hash(list(sample_symbols)),
        "success_count": 0,
        "failed_count": 0,
        "publish_count": 0,
        "needs_review_count": 0,
        "blocked_count": 0,
        "data_gap_count": 0,
        "alaya_synced_count": 0,
        "alaya_failed_count": 0,
        "alaya_readback_verified_count": 0,
        "alaya_readback_failed_count": 0,
        "alaya_write_seconds": 0.0,
        "alaya_readback_seconds": 0.0,
        "alaya_total_seconds": 0.0,
        "alaya_sync_status": "pending" if config.alaya_mode == "real" else "skipped",
        "alaya_readback_status": "pending" if config.alaya_mode == "real" else "not_applicable",
        "failed_symbols": [],
        "blocked_symbols": [],
        "needs_review_symbols": [],
        "started_at_utc": started_at_utc,
        "finished_at_utc": None,
        "last_heartbeat_utc": utc_now_iso(),
        "elapsed_seconds": elapsed,
        "remaining_seconds": max(0, int(config.loop_duration_seconds - elapsed)),
        "consecutive_failures": 1 if last_error_category else 0,
        "llm_runner": config.llm_runner,
        "llm_model": config.model,
        "max_concurrency": config.max_concurrency,
        "reasoning_effort": config.reasoning_effort,
        "timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "alaya_mode": config.alaya_mode,
        "candidate_service": config.candidate_service,
        "candidate_timer": config.candidate_timer,
        "rollback_hint": rollback_hint(config),
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "boundary": list(BOUNDARY_LINES),
        "report_file": report_path.name,
        "latest_public_report_file": report_path.name,
        "status_file": status_path.name,
        "artifact_write_status": "pending",
        "artifact_write_failure_reason": None,
        "public_scan_status": "pending",
        "last_error_category": last_error_category,
        "last_error_public_message": public_error_message(last_error_category),
        "heartbeat_stale": False,
        "provider_model_io_embedded": False,
        "evidence_layer": evidence_layer_for_mode(config.mode),
        "limitations": [
            "not formal acceptance",
            "not science/public proof",
            "not performance proof",
            "not a trading signal",
            "not investment advice",
        ],
        "exit_status": None,
    }
    status["stage_statuses"] = stage_statuses_for_status(status, publish_static=config.publish_static)
    return status


def render_loop_running_markdown(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# GOTRA Full Analyst Pipeline - {status['as_of_date']}",
            "",
            "## Evidence Layer",
            "",
            f"- {status['evidence_layer']}",
            "- not formal acceptance",
            "- not science/public proof",
            "- not performance proof",
            "- not a trading signal",
            "- not investment advice",
            "",
            "## Status",
            "",
            f"- mode: {status['mode']}",
            f"- run_id: {status['run_id']}",
            f"- status: {status['status']}",
            f"- phase: {status['phase']}",
            f"- last_heartbeat_utc: {status['last_heartbeat_utc']}",
            f"- current_cycle: {status['current_cycle']}",
            f"- last_successful_cycle: {status['last_successful_cycle']}",
            f"- alaya_mode: {status['alaya_mode']}",
            f"- alaya_sync_status: {status['alaya_sync_status']}",
            f"- alaya_readback_status: {status['alaya_readback_status']}",
        ]
    ) + "\n"


def sync_loop_markdown_status(report_path: Path, status: dict[str, Any]) -> None:
    if not report_path.exists():
        return
    markdown = report_path.read_text(encoding="utf-8")
    replacements = {
        "status": status.get("status"),
        "run_status": status.get("run_status"),
        "phase": status.get("phase"),
        "last_heartbeat_utc": status.get("last_heartbeat_utc"),
        "current_cycle": status.get("current_cycle"),
        "last_successful_cycle": status.get("last_successful_cycle"),
    }
    for key, value in replacements.items():
        if value is None:
            continue
        line = f"- {key}: {value}"
        pattern = re.compile(rf"^- {re.escape(key)}: .*$", re.MULTILINE)
        if pattern.search(markdown):
            markdown = pattern.sub(line, markdown, count=1)
        elif key == "status":
            markdown = re.sub(r"(^## Status\n\n)", rf"\1{line}\n", markdown, count=1, flags=re.MULTILINE)
    scan_public_text(markdown)
    write_public_text(report_path, markdown)


def update_loop_public_status(
    config: FullAnalystConfig,
    *,
    current_cycle: int,
    last_successful_cycle: int,
    loop_status: str,
    phase: str,
    started_at_utc: str,
    sample_symbols: tuple[str, ...] | None = None,
    last_error_category: str | None = None,
) -> None:
    report_path, status_path = report_paths(config)
    status: dict[str, Any] | None = None
    should_bootstrap = not status_path.exists()
    if not should_bootstrap:
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        should_bootstrap = status.get("run_id") != config.run_id or status.get("mode") != config.mode
    if should_bootstrap:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        status = build_loop_running_status(
            config,
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            loop_status=loop_status,
            phase=phase,
            started_at_utc=started_at_utc,
            sample_symbols=sample_symbols or (),
            last_error_category=last_error_category,
        )
        markdown = render_loop_running_markdown(status)
        scan_public_text(markdown)
        write_public_text(report_path, markdown)
    if status is None:
        return
    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    elapsed = max(0, int((datetime.now(UTC) - started).total_seconds()))
    status["status"] = loop_status
    status["run_status"] = "running" if loop_status == "running" else loop_status
    status["phase"] = phase
    status["current_cycle"] = current_cycle
    status["last_successful_cycle"] = last_successful_cycle
    if sample_symbols is not None:
        status["sample_symbols"] = list(sample_symbols)
        status["universe_count"] = len(sample_symbols)
    status["last_heartbeat_utc"] = utc_now_iso()
    status["elapsed_seconds"] = elapsed
    status["remaining_seconds"] = max(0, int(config.loop_duration_seconds - elapsed))
    status["heartbeat_stale"] = False
    if last_error_category:
        status["last_error_category"] = last_error_category
        status["last_error_public_message"] = public_error_message(last_error_category)
    if loop_status != "running":
        sync_loop_markdown_status(report_path, status)
    write_public_json(status_path, status)
    if config.publish_static:
        publish_static(report_path, status_path, config.static_dir)


def refresh_loop_runtime_heartbeat(
    config: FullAnalystConfig,
    *,
    phase: str,
    started_at_utc: str,
    sample_symbols: tuple[str, ...] | None = None,
) -> None:
    write_heartbeat(
        config,
        status="running",
        phase=phase,
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=started_at_utc,
    )
    if config.mode in LOOP_MODES:
        update_loop_public_status(
            config,
            current_cycle=config.loop_current_cycle,
            last_successful_cycle=config.loop_last_successful_cycle,
            loop_status="running",
            phase=phase,
            started_at_utc=started_at_utc,
            sample_symbols=sample_symbols,
        )


def run_loop(config: FullAnalystConfig) -> int:
    loop_started = time.monotonic()
    loop_started_at_utc = utc_now_iso()
    current_cycle = 0
    last_successful_cycle = 0
    last_exit = 0
    write_heartbeat(
        config,
        status="running",
        phase="preflight",
        current_cycle=0,
        last_successful_cycle=0,
        started_at_utc=loop_started_at_utc,
    )
    update_loop_public_status(
        config,
        current_cycle=0,
        last_successful_cycle=0,
        loop_status="running",
        phase="preflight",
        started_at_utc=loop_started_at_utc,
        sample_symbols=(),
    )
    while time.monotonic() - loop_started < config.loop_duration_seconds:
        current_cycle += 1
        cycle_symbols = sample_symbols_for_cycle(config.symbols, last_successful_cycle)
        cycle_config = replace(
            config,
            symbols=cycle_symbols,
            loop_current_cycle=current_cycle,
            loop_last_successful_cycle=last_successful_cycle,
        )
        append_event(
            config,
            "cycle_started",
            {"status": "running", "event_hash": stable_hash({"cycle": current_cycle})},
        )
        write_heartbeat(
            config,
            status="running",
            phase="llm",
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            started_at_utc=loop_started_at_utc,
        )
        update_loop_public_status(
            config,
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            loop_status="running",
            phase="llm",
            started_at_utc=loop_started_at_utc,
            sample_symbols=cycle_symbols,
        )
        last_exit = run(cycle_config, loop_started_at_utc=loop_started_at_utc)
        if last_exit == 0:
            last_successful_cycle = current_cycle
        category = None if last_exit == 0 else "cycle_failed"
        update_loop_public_status(
            config,
            current_cycle=current_cycle,
            last_successful_cycle=last_successful_cycle,
            loop_status="running" if last_exit == 0 else "repairing",
            phase="sleep" if last_exit == 0 else "repairing",
            started_at_utc=loop_started_at_utc,
            sample_symbols=cycle_symbols,
            last_error_category=category,
        )
        if last_exit != 0:
            return last_exit
        next_cycle_at = time.monotonic() + config.sample_cadence_seconds
        while time.monotonic() < next_cycle_at and time.monotonic() - loop_started < config.loop_duration_seconds:
            write_heartbeat(
                config,
                status="running",
                phase="sleep",
                current_cycle=current_cycle,
                last_successful_cycle=last_successful_cycle,
                started_at_utc=loop_started_at_utc,
            )
            update_loop_public_status(
                config,
                current_cycle=current_cycle,
                last_successful_cycle=last_successful_cycle,
                loop_status="running",
                phase="sleep",
                started_at_utc=loop_started_at_utc,
            )
            time.sleep(min(config.heartbeat_interval_seconds, max(1, int(next_cycle_at - time.monotonic()))))
    update_loop_public_status(
        config,
        current_cycle=current_cycle,
        last_successful_cycle=last_successful_cycle,
        loop_status="completed",
        phase="completed",
        started_at_utc=loop_started_at_utc,
    )
    write_heartbeat(
        config,
        status="completed",
        phase="completed",
        current_cycle=current_cycle,
        last_successful_cycle=last_successful_cycle,
        started_at_utc=loop_started_at_utc,
    )
    return last_exit


def run(
    config: FullAnalystConfig,
    *,
    universe_items: list[dict[str, str]] | None = None,
    runner: AnalystRunner | None = None,
    alaya_client: AlayaSyncClient | None = None,
    price_rows: dict[str, dict[str, Any]] | None = None,
    loop_started_at_utc: str | None = None,
) -> int:
    started = time.monotonic()
    started_at_utc = utc_now_iso()
    heartbeat_started_at_utc = loop_started_at_utc or started_at_utc
    ensure_private_dir(private_run_dir(config))
    report_path, status_path = report_paths(config)
    write_heartbeat(
        config,
        status="running",
        phase="preflight",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
    )
    append_event(config, "run_started", {"status": "running", "mode": config.mode})
    try:
        preflight_llm_config(config, runner)
        active_alaya = alaya_client or alaya_client_from_config(config)
    except ConfigurationBlocker as exc:
        return write_blocker_status(config, started_at_utc=started_at_utc, reason=str(exc), report_path=report_path, status_path=status_path)
    universe = universe_items if universe_items is not None else load_public_universe(config)
    items = selected_universe(universe, config.symbols)
    write_heartbeat(
        config,
        status="running",
        phase="cycle",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
    )
    resolved_price_rows = fetch_price_rows(items, config, price_rows)
    write_heartbeat(
        config,
        status="running",
        phase="llm",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=config.loop_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
    )
    active_runner = runner or runner_from_config(config)
    results = run_jobs(
        items,
        resolved_price_rows,
        config,
        active_runner,
        active_alaya,
        started_at_utc=heartbeat_started_at_utc,
    )
    status = build_status(
        config=config,
        results=results,
        started_at_utc=started_at_utc,
        elapsed_seconds=time.monotonic() - started,
        report_path=report_path,
        status_path=status_path,
    )
    write_failure_records(config, results, status)
    try:
        paths = write_outputs(config, results, status)
    except PublicScanError as exc:
        category = public_safe_failure_category(str(exc))
        failed = dict(status)
        failed["ok"] = False
        failed["run_status"] = "failed"
        failed["status"] = "failed"
        failed["public_scan_status"] = "failed"
        failed["last_error_category"] = category
        failed["last_error_public_message"] = public_error_message(category)
        failed["exit_status"] = 2
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_public_json(status_path, failed)
        write_heartbeat(
            config,
            status="failed",
            phase="scan",
            current_cycle=config.loop_current_cycle,
            last_successful_cycle=config.loop_last_successful_cycle,
            started_at_utc=heartbeat_started_at_utc,
            last_error_category=category,
        )
        append_event(config, "public_scan_failed", {"status": "failed", "reason": category})
        print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    except Exception as exc:  # noqa: BLE001 - preserve failure in status file when possible.
        category = public_safe_failure_category(str(exc))
        failed = dict(status)
        failed["ok"] = False
        failed["run_status"] = "failed"
        failed["status"] = "failed"
        failed["artifact_write_status"] = "failed"
        failed["artifact_write_failure_reason"] = category
        failed["last_error_category"] = category
        failed["last_error_public_message"] = public_error_message(category)
        failed["exit_status"] = 2
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_public_json(status_path, failed)
        write_heartbeat(
            config,
            status="failed",
            phase="artifact",
            current_cycle=config.loop_current_cycle,
            last_successful_cycle=config.loop_last_successful_cycle,
            started_at_utc=heartbeat_started_at_utc,
            last_error_category=category,
        )
        append_event(config, "artifact_write_failed", {"status": "failed", "reason": category})
        print(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    runtime_summary = dict(status)
    runtime_summary["local_output_paths"] = paths
    heartbeat_last_successful_cycle = (
        config.loop_current_cycle if status["exit_status"] == 0 else config.loop_last_successful_cycle
    )
    write_heartbeat(
        config,
        status="completed" if status["exit_status"] == 0 else "failed",
        phase="completed",
        current_cycle=config.loop_current_cycle,
        last_successful_cycle=heartbeat_last_successful_cycle,
        started_at_utc=heartbeat_started_at_utc,
        last_error_category=status.get("last_error_category"),
    )
    append_event(config, "run_finished", {"status": runtime_summary["status"], "event_hash": stable_hash(runtime_summary)})
    print(json.dumps(runtime_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return int(status["exit_status"])


def main(argv: list[str] | None = None) -> int:
    try:
        config = config_from_args(parse_args(argv))
        if config.mode == LOOP_MODE:
            return run_loop(config)
        return run(config)
    except Exception as exc:  # noqa: BLE001 - fail closed without secrets.
        print(f"full analyst pipeline failed: {sanitize_text(type(exc).__name__ + ': ' + str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
