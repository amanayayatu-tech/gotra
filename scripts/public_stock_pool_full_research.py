"""Run a public-safe full research smoke over the public stock universe.

This entrypoint is intentionally separate from the public EOD report. It can
call a local Codex CLI session, but it never writes prompts, completions,
messages, or provider response bodies to report artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.public_stock_pool_report import latest_completed_us_session, yahoo_ticker  # noqa: E402


SCHEMA = "gotra.public_stock_pool_full_research.v1"
STATUS_SCHEMA = "gotra.public_stock_pool_full_research.status.v1"
PER_SYMBOL_SCHEMA = "gotra.public_stock_pool_full_research.per_symbol_status.v1"
MODE = "full-research-test"
DEFAULT_OUTPUT_DIR = Path("/opt/gotra/data/reports/full_research_test")
DEFAULT_UNIVERSE_URL = "http://127.0.0.1:3000/api/research-universe"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_PRIVATE_AUDIT_ROOT = Path("/opt/gotra/data/private/full_research_runs")
PROMPT_TEMPLATE_VERSION = "gotra.full_research_test.prompt.v1"
REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")

BOUNDARY_LINES = (
    "research information only",
    "not investment advice",
    "not trading signal",
    "not performance proof",
    "not science/public proof",
    "no buy/sell/hold recommendation",
    "no target price",
    "no position sizing",
    "no return promise",
    "no provider/model I/O is embedded",
)
REQUIRED_RESEARCH_KEYS = (
    "symbol",
    "exchange",
    "as_of_date",
    "research_summary",
    "key_updates",
    "price_context",
    "risk_factors",
    "watch_items",
    "boundary",
    "source_notes",
    "status",
)
LIST_KEYS = {"key_updates", "risk_factors", "watch_items", "boundary", "source_notes"}
SECRET_RE = re.compile(
    r"OPENAI_API_KEY|ANTHROPIC_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY|"
    r"GROQ_API_KEY|PERPLEXITY_API_KEY|PPLX_API_KEY|ALAYA_API_KEY|"
    r"ALAYA_AUTOMATION_API_KEY|sk-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9_.=-]+|"
    r"Authorization\s*:?\s*[A-Za-z0-9_.= -]+|BEGIN PRIVATE KEY|PRIVATE KEY|"
    r"access_key_secret\s*[:=]\s*\S+|secret\s*[:=]\s*\S+|password\s*[:=]\s*\S+",
    re.IGNORECASE,
)
FORBIDDEN_OUTPUT_KEY_RE = re.compile(r"^(prompt|completion|messages|raw_provider_response)$", re.IGNORECASE)
ADVICE_RE = re.compile(
    r"\b(buy|sell|hold)\s+(recommendation|rating|signal)\b|"
    r"\btarget price\b|\bposition sizing\b|\breturn promise\b|"
    r"\bguaranteed return\b|\bperformance proof\b|\bscience/public proof\b|"
    r"买入|卖出|持有建议|目标价|仓位建议|收益承诺",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    mode: str
    output_dir: Path
    private_audit_root: Path
    as_of_date: date
    trading_date: date
    universe_url: str
    max_concurrency: int
    continue_on_failure: bool
    llm_runner: str
    model: str
    reasoning_effort: str
    per_symbol_timeout_seconds: int
    retries: int
    resume: bool
    codex_bin: str


@dataclass(frozen=True)
class RunnerResult:
    ok: bool
    text: str = ""
    reason: str = ""
    elapsed_seconds: float = 0.0
    returncode: int | None = None
    stdout_bytes: int = 0
    stderr_bytes: int = 0


class LlmRunner(Protocol):
    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        """Return final model text without persisting provider I/O."""


class CodexCliRunner:
    def __init__(
        self,
        *,
        codex_bin: str,
        model: str,
        reasoning_effort: str,
        cwd: Path,
    ) -> None:
        self.codex_bin = codex_bin
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.cwd = cwd

    def complete(self, prompt_text: str, *, timeout_seconds: int) -> RunnerResult:
        started = time.monotonic()
        fd, out_path_text = tempfile.mkstemp(prefix="gotra-codex-final-", suffix=".json")
        os.close(fd)
        out_path = Path(out_path_text)
        command = [
            self.codex_bin,
            "exec",
            "-m",
            self.model,
            "-c",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "-c",
            'approval_policy="never"',
            "-s",
            "read-only",
            "--ephemeral",
            "--output-last-message",
            str(out_path),
            prompt_text,
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=self.cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                return RunnerResult(
                    False,
                    reason="timeout",
                    elapsed_seconds=time.monotonic() - started,
                    returncode=process.returncode,
                    stdout_bytes=len((stdout or "").encode("utf-8")),
                    stderr_bytes=len((stderr or "").encode("utf-8")),
                )
            elapsed = time.monotonic() - started
            stdout_bytes = len((stdout or "").encode("utf-8"))
            stderr_bytes = len((stderr or "").encode("utf-8"))
            if process.returncode != 0:
                return RunnerResult(
                    False,
                    reason="nonzero_exit",
                    elapsed_seconds=elapsed,
                    returncode=process.returncode,
                    stdout_bytes=stdout_bytes,
                    stderr_bytes=stderr_bytes,
                )
            try:
                text = out_path.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                return RunnerResult(
                    False,
                    reason="missing_final_message",
                    elapsed_seconds=elapsed,
                    returncode=process.returncode,
                    stdout_bytes=stdout_bytes,
                    stderr_bytes=stderr_bytes,
                )
            if not text:
                return RunnerResult(
                    False,
                    reason="empty_final_message",
                    elapsed_seconds=elapsed,
                    returncode=process.returncode,
                    stdout_bytes=stdout_bytes,
                    stderr_bytes=stderr_bytes,
                )
            return RunnerResult(
                True,
                text=text,
                elapsed_seconds=elapsed,
                returncode=process.returncode,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
            )
        finally:
            try:
                out_path.unlink()
            except FileNotFoundError:
                pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run public stock-pool full research test.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mode", choices=(MODE,), required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--private-audit-root", type=Path, default=DEFAULT_PRIVATE_AUDIT_ROOT)
    parser.add_argument("--as-of-date", default=datetime.now(REPORT_TIMEZONE).date().isoformat())
    parser.add_argument(
        "--trading-date",
        default="",
        help="Latest completed trading date, YYYY-MM-DD. Defaults to the previous completed US session.",
    )
    parser.add_argument("--universe-url", default=DEFAULT_UNIVERSE_URL)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--llm-runner", choices=("codex-cli",), default="codex-cli")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument(
        "--per-symbol-timeout-seconds",
        "--timeout-seconds",
        dest="per_symbol_timeout_seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--codex-bin", default="codex")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RunConfig:
    if args.max_concurrency < 1:
        raise ValueError("--max-concurrency must be >= 1")
    if args.per_symbol_timeout_seconds < 30:
        raise ValueError("--per-symbol-timeout-seconds must be >= 30")
    if args.retries < 0:
        raise ValueError("--retries must be >= 0")
    as_of_date = date.fromisoformat(str(args.as_of_date))
    trading_date = date.fromisoformat(str(args.trading_date)) if args.trading_date else latest_completed_us_session(as_of_date)
    return RunConfig(
        run_id=str(args.run_id or default_run_id()),
        mode=str(args.mode),
        output_dir=args.output_dir,
        private_audit_root=args.private_audit_root,
        as_of_date=as_of_date,
        trading_date=trading_date,
        universe_url=str(args.universe_url),
        max_concurrency=int(args.max_concurrency),
        continue_on_failure=bool(args.continue_on_failure),
        llm_runner=str(args.llm_runner),
        model=str(args.model),
        reasoning_effort=str(args.reasoning_effort),
        per_symbol_timeout_seconds=int(args.per_symbol_timeout_seconds),
        retries=int(args.retries),
        resume=bool(args.resume),
        codex_bin=str(args.codex_bin),
    )


def default_run_id() -> str:
    return "full_research_test_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def private_audit_dir(config: RunConfig) -> Path:
    return config.private_audit_root / config.run_id


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_iso_precise() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def earliest_started_at(results: list[dict[str, Any]], fallback: str) -> str:
    parsed = [parse_utc_timestamp(str(result.get("started_at_utc") or "")) for result in results]
    clean = [value for value in parsed if value is not None]
    if not clean:
        return fallback
    return min(clean).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def elapsed_from_result_timestamps(results: list[dict[str, Any]]) -> float | None:
    starts = [parse_utc_timestamp(str(result.get("started_at_utc") or "")) for result in results]
    finishes = [parse_utc_timestamp(str(result.get("finished_at_utc") or "")) for result in results]
    clean_starts = [value for value in starts if value is not None]
    clean_finishes = [value for value in finishes if value is not None]
    if not clean_starts or not clean_finishes:
        return None
    return (max(clean_finishes) - min(clean_starts)).total_seconds()


def load_universe(url: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("research universe response missing items list")
    return [normalize_universe_item(item) for item in items]


def normalize_universe_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise RuntimeError("research universe item is not an object")
    symbol = str(item.get("symbol") or "").strip().upper()
    exchange = str(item.get("exchange") or "").strip().upper()
    if not symbol or exchange not in {"HKEX", "NASDAQ", "NYSE"}:
        raise RuntimeError("research universe item missing valid symbol/exchange")
    return {
        "symbol": symbol,
        "exchange": exchange,
        "provider_ticker": yahoo_ticker(symbol, exchange),
        "source": str(item.get("source") or ""),
        "source_date": str(item.get("source_date") or ""),
        "purpose": str(item.get("purpose") or ""),
        "boundary": str(item.get("boundary") or ""),
    }


def build_research_prompt(
    item: dict[str, Any],
    *,
    as_of_date: date,
    trading_date: date,
    attempt: int = 1,
    last_failure_reason: str = "",
) -> str:
    payload = {
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "as_of_date": as_of_date.isoformat(),
        "trading_date": trading_date.isoformat(),
        "task": "public-safe research summary for a full research runtime test",
        "required_keys": list(REQUIRED_RESEARCH_KEYS),
        "boundary": list(BOUNDARY_LINES),
    }
    retry_note = ""
    if attempt > 1:
        retry_note = (
            f"\nRetry attempt {attempt}. Previous failure was {sanitize_text(last_failure_reason)[:120]}. "
            "Be stricter: return exactly one JSON object with all required keys and status exactly \"ok\"."
        )
    return (
        "Return STRICT JSON only. No markdown, no code fences, no commentary.\n"
        "Do not provide investment advice, trading signal, buy/sell/hold recommendation, "
        "target price, position sizing, return promise, performance proof, or science/public proof.\n"
        "Do not include prompt, completion, messages, raw_provider_response, token, Authorization, "
        "Bearer, API keys, or secrets.\n"
        "Use arrays for key_updates, risk_factors, watch_items, boundary, and source_notes.\n"
        "Set status to exactly \"ok\" when a public-safe summary is produced.\n"
        "Do not repeat boundary phrases in research_summary, key_updates, price_context, "
        "risk_factors, watch_items, or source_notes; put boundary wording only in the boundary array.\n"
        "Use short public information summaries; if uncertain, say what to verify next.\n"
        f"Input JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        f"{retry_note}"
    )


def run_research_job(item: dict[str, Any], config: RunConfig, runner: LlmRunner) -> dict[str, Any]:
    started = utc_now_iso()
    start_monotonic = time.monotonic()
    attempts_public: list[dict[str, Any]] = []
    last_failure_reason = ""
    audit_ref = audit_ref_for(config, item)
    for attempt in range(1, config.retries + 2):
        prompt_text = build_research_prompt(
            item,
            as_of_date=config.as_of_date,
            trading_date=config.trading_date,
            attempt=attempt,
            last_failure_reason=last_failure_reason,
        )
        attempt_record = base_attempt_record(
            config=config,
            item=item,
            prompt_text=prompt_text,
            attempt=attempt,
        )
        try:
            result = runner.complete(prompt_text, timeout_seconds=config.per_symbol_timeout_seconds)
            attempt_record.update(
                {
                    "returncode": result.returncode,
                    "duration_seconds": round(result.elapsed_seconds, 3),
                    "stdout_bytes": result.stdout_bytes,
                    "stderr_bytes": result.stderr_bytes,
                }
            )
            if not result.ok:
                last_failure_reason = result.reason or "codex_cli_failed"
                attempt_record["failure_reason"] = last_failure_reason
                attempts_public.append(public_attempt_metrics(attempt_record))
                write_private_audit_attempt(config, item, attempt_record)
                continue
            parsed = parse_model_json(result.text)
            research = sanitize_research_payload(parsed, item=item, as_of_date=config.as_of_date)
            unsafe_reason = unsafe_research_reason(research)
            if unsafe_reason:
                last_failure_reason = unsafe_reason
                attempt_record["failure_reason"] = last_failure_reason
                attempts_public.append(public_attempt_metrics(attempt_record))
                write_private_audit_attempt(config, item, attempt_record)
                continue
            if str(research.get("status") or "").strip().lower() != "ok":
                last_failure_reason = "status_not_ok"
                attempt_record["failure_reason"] = last_failure_reason
                attempts_public.append(public_attempt_metrics(attempt_record))
                write_private_audit_attempt(config, item, attempt_record)
                continue
            attempt_record["status"] = "success"
            attempt_record["parsed_structured_output"] = research
            write_private_audit_attempt(config, item, attempt_record)
            return {
                "symbol": item["symbol"],
                "exchange": item["exchange"],
                "provider_ticker": item["provider_ticker"],
                "status": "success",
                "failure_reason": "",
                "last_failure_reason": "",
                "attempts": attempt,
                "attempt_metrics": attempts_public,
                "audit_ref": audit_ref,
                "started_at_utc": started,
                "finished_at_utc": utc_now_iso(),
                "elapsed_seconds": round(time.monotonic() - start_monotonic, 3),
                "research": research,
            }
        except json.JSONDecodeError:
            last_failure_reason = "invalid_json"
            attempt_record["failure_reason"] = last_failure_reason
            attempts_public.append(public_attempt_metrics(attempt_record))
            write_private_audit_attempt(config, item, attempt_record)
        except Exception as exc:  # noqa: BLE001 - full run records per-symbol failure.
            last_failure_reason = normalize_failure_reason(exc)
            attempt_record["failure_reason"] = last_failure_reason
            attempts_public.append(public_attempt_metrics(attempt_record))
            write_private_audit_attempt(config, item, attempt_record)
    return failed_symbol(
        item,
        started,
        start_monotonic,
        last_failure_reason or "unknown_failure",
        attempts=len(attempts_public),
        attempt_metrics=attempts_public,
        audit_ref=audit_ref,
    )


def normalize_failure_reason(exc: Exception) -> str:
    text = str(exc)
    if text.startswith("missing_required_fields"):
        return "missing_required_fields"
    return f"{type(exc).__name__}: {text[:160]}"


def base_attempt_record(
    *,
    config: RunConfig,
    item: dict[str, Any],
    prompt_text: str,
    attempt: int,
) -> dict[str, Any]:
    attempt_started_at_utc = utc_now_iso_precise()
    attempt_id = (
        f"{item['exchange']}_{item['symbol']}_attempt_{attempt}_"
        f"{re.sub(r'[^0-9A-Za-z]+', '', attempt_started_at_utc)}"
    )
    return {
        "schema": "gotra.public_stock_pool_full_research.private_attempt.v1",
        "run_id": config.run_id,
        "audit_ref": audit_ref_for(config, item),
        "attempt_id": attempt_id,
        "attempt_started_at_utc": attempt_started_at_utc,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_text": scrub_secret_text(prompt_text),
        "input_metadata": {
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "provider_ticker": item["provider_ticker"],
            "as_of_date": config.as_of_date.isoformat(),
            "trading_date": config.trading_date.isoformat(),
        },
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "attempt": attempt,
        "status": "failed",
        "returncode": None,
        "duration_seconds": 0.0,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "failure_reason": "",
        "parsed_structured_output": None,
    }


def public_attempt_metrics(attempt_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt": attempt_record.get("attempt"),
        "failure_reason": sanitize_text(str(attempt_record.get("failure_reason") or "")),
        "duration_seconds": attempt_record.get("duration_seconds"),
    }


def audit_ref_for(config: RunConfig, item: dict[str, Any]) -> str:
    return f"{config.run_id}:{item['exchange']}:{item['symbol']}"


def write_private_audit_attempt(config: RunConfig, item: dict[str, Any], payload: dict[str, Any]) -> None:
    audit_dir = private_audit_dir(config) / "attempts"
    ensure_private_dir(audit_dir)
    attempt_id = sanitize_filename(str(payload.get("attempt_id") or ""))
    if not attempt_id:
        attempt_id = f"{item['exchange']}_{item['symbol']}_attempt_{payload['attempt']}"
    path = audit_dir / f"{attempt_id}.json"
    write_private_json_atomic(path, payload)


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("._")


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except PermissionError:
        pass


def write_private_json_atomic(path: Path, payload: Any) -> None:
    ensure_private_dir(path.parent)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.chmod(0o600)
    tmp_path.replace(path)
    path.chmod(0o600)


def scrub_secret_text(value: str) -> str:
    return SECRET_RE.sub("[REDACTED]", value)


def legacy_single_attempt_job(item: dict[str, Any], config: RunConfig, runner: LlmRunner) -> dict[str, Any]:
    """Kept only for older tests that may import the original function name."""
    started = utc_now_iso()
    start_monotonic = time.monotonic()
    try:
        prompt_text = build_research_prompt(item, as_of_date=config.as_of_date, trading_date=config.trading_date)
        result = runner.complete(prompt_text, timeout_seconds=config.per_symbol_timeout_seconds)
        if not result.ok:
            return failed_symbol(item, started, start_monotonic, result.reason or "codex_cli_failed")
        parsed = parse_model_json(result.text)
        research = sanitize_research_payload(parsed, item=item, as_of_date=config.as_of_date)
        unsafe_reason = unsafe_research_reason(research)
        if unsafe_reason:
            return failed_symbol(item, started, start_monotonic, unsafe_reason)
        return {
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "provider_ticker": item["provider_ticker"],
            "status": "success",
            "failure_reason": "",
            "started_at_utc": started,
            "finished_at_utc": utc_now_iso(),
            "elapsed_seconds": round(time.monotonic() - start_monotonic, 3),
            "research": research,
        }
    except json.JSONDecodeError:
        return failed_symbol(item, started, start_monotonic, "non_json_response")
    except Exception as exc:  # noqa: BLE001 - full run records per-symbol failure.
        return failed_symbol(item, started, start_monotonic, f"{type(exc).__name__}: {str(exc)[:160]}")


def failed_symbol(
    item: dict[str, Any],
    started_at_utc: str,
    start_monotonic: float,
    reason: str,
    *,
    attempts: int = 1,
    attempt_metrics: list[dict[str, Any]] | None = None,
    audit_ref: str = "",
) -> dict[str, Any]:
    return {
        "symbol": item["symbol"],
        "exchange": item["exchange"],
        "provider_ticker": item["provider_ticker"],
        "status": "failed",
        "failure_reason": sanitize_text(reason)[:240],
        "last_failure_reason": sanitize_text(reason)[:240],
        "attempts": attempts,
        "attempt_metrics": attempt_metrics or [],
        "audit_ref": audit_ref,
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now_iso(),
        "elapsed_seconds": round(time.monotonic() - start_monotonic, 3),
        "research": None,
    }


def parse_model_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise json.JSONDecodeError("response is not a JSON object", stripped, 0)
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("response root is not an object", stripped, 0)
    return payload


def sanitize_research_payload(payload: dict[str, Any], *, item: dict[str, Any], as_of_date: date) -> dict[str, Any]:
    missing = [key for key in REQUIRED_RESEARCH_KEYS if key not in payload]
    if missing:
        raise ValueError(f"missing_required_fields: {','.join(missing)}")
    sanitized: dict[str, Any] = {}
    for key in REQUIRED_RESEARCH_KEYS:
        if FORBIDDEN_OUTPUT_KEY_RE.match(key):
            continue
        value = payload.get(key)
        if key in LIST_KEYS:
            sanitized[key] = sanitize_list(value)
        else:
            sanitized[key] = sanitize_text(str(value or ""))
    sanitized["symbol"] = item["symbol"]
    sanitized["exchange"] = item["exchange"]
    sanitized["as_of_date"] = as_of_date.isoformat()
    sanitized["boundary"] = list(BOUNDARY_LINES)
    sanitized["status"] = sanitize_text(str(payload.get("status") or "ok")) or "ok"
    return sanitized


def sanitize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [sanitize_text(str(item))[:500] for item in value if str(item).strip()][:12]
    if value in (None, ""):
        return []
    return [sanitize_text(str(value))[:500]]


def sanitize_text(value: str) -> str:
    cleaned = SECRET_RE.sub("[REDACTED]", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def unsafe_research_reason(research: dict[str, Any]) -> str:
    scan_payload = {
        key: value
        for key, value in research.items()
        if key not in {"boundary", "source_notes"}
    }
    text = json.dumps(scan_payload, ensure_ascii=False, sort_keys=True)
    if SECRET_RE.search(text):
        return "secret_like_content_detected"
    if ADVICE_RE.search(text):
        return "investment_or_trading_claim_detected"
    return ""


def run_jobs(
    *,
    items: list[dict[str, Any]],
    config: RunConfig,
    runner: LlmRunner,
    checkpoint_callback: Any | None = None,
    initial_results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = list(initial_results or [])
    completed_keys = {(result["exchange"], result["symbol"]) for result in results if result.get("status") == "success"}
    pending_items = [item for item in items if (item["exchange"], item["symbol"]) not in completed_keys]
    if checkpoint_callback:
        checkpoint_callback(results)
    if config.max_concurrency == 1:
        for item in pending_items:
            result = run_research_job(item, config, runner)
            results.append(result)
            print(progress_line(result), flush=True)
            if checkpoint_callback:
                checkpoint_callback(results)
            if result["status"] == "failed" and not config.continue_on_failure:
                break
        return results

    with ThreadPoolExecutor(max_workers=config.max_concurrency) as executor:
        future_to_item = {executor.submit(run_research_job, item, config, runner): item for item in pending_items}
        for future in as_completed(future_to_item):
            result = future.result()
            results.append(result)
            print(progress_line(result), flush=True)
            if checkpoint_callback:
                checkpoint_callback(results)
    return sorted(results, key=lambda row: (str(row["exchange"]), str(row["symbol"])))


def progress_line(result: dict[str, Any]) -> str:
    reason = f" reason={result['failure_reason']}" if result.get("failure_reason") else ""
    return (
        f"symbol_result exchange={result['exchange']} symbol={result['symbol']} "
        f"status={result['status']} elapsed_seconds={result['elapsed_seconds']}{reason}"
    )


def build_status(
    *,
    config: RunConfig,
    universe_count: int,
    results: list[dict[str, Any]],
    started_at_utc: str,
    finished_at_utc: str,
    elapsed_seconds: float,
    artifact_write_status: str = "ok",
    artifact_write_failure_reason: str | None = None,
) -> dict[str, Any]:
    failures = [result for result in results if result["status"] != "success"]
    failed_symbols = [
        {
            "exchange": result["exchange"],
            "symbol": result["symbol"],
            "provider_ticker": result["provider_ticker"],
            "reason": result["failure_reason"],
        }
        for result in failures
    ]
    success_count = sum(1 for result in results if result["status"] == "success")
    running_count = max(0, universe_count - len(results))
    complete = len(results) == universe_count and not failures
    timing = elapsed_summary([float(result.get("elapsed_seconds") or 0.0) for result in results])
    reason_counts = failure_reason_counts(results)
    audit_summary = audit_attempt_summary(config, results)
    if audit_summary["failure_reason_counts"]:
        reason_counts = audit_summary["failure_reason_counts"]
    total_attempts = int(audit_summary["total_attempts"] or sum(int(result.get("attempts") or 0) for result in results))
    return {
        "schema": STATUS_SCHEMA,
        "run_id": config.run_id,
        "ok": complete and artifact_write_status == "ok",
        "run_status": "completed" if complete else "running" if running_count else "partial" if results else "running",
        "mode": config.mode,
        "as_of_date": config.as_of_date.isoformat(),
        "trading_date": config.trading_date.isoformat(),
        "exchange_trading_dates": {
            "HKEX": config.trading_date.isoformat(),
            "NASDAQ": config.trading_date.isoformat(),
            "NYSE": config.trading_date.isoformat(),
        },
        "universe_count": universe_count,
        "success_count": success_count,
        "failed_count": len(failures),
        "running_count": running_count,
        "failed_symbols": failed_symbols,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "llm_runner": config.llm_runner,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "max_concurrency": config.max_concurrency,
        "per_symbol_timeout_seconds": config.per_symbol_timeout_seconds,
        "retries": config.retries,
        "total_attempts": total_attempts,
        "timeout_count": reason_counts.get("timeout", 0),
        "invalid_json_count": reason_counts.get("invalid_json", 0),
        "nonzero_exit_count": reason_counts.get("nonzero_exit", 0),
        "audit_attempt_file_count": audit_summary["attempt_file_count"],
        "audit_overwritten_resume_groups": audit_summary["overwritten_resume_groups"],
        "attempt_count_source": audit_summary["source"],
        "average_per_symbol_elapsed_seconds": timing["average"],
        "p50_per_symbol_elapsed_seconds": timing["p50"],
        "p95_per_symbol_elapsed_seconds": timing["p95"],
        "artifact_write_status": artifact_write_status,
        "artifact_write_failure_reason": artifact_write_failure_reason,
        "boundary": list(BOUNDARY_LINES),
        "private_audit_path": str(private_audit_dir(config).resolve()),
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "public_artifact_path": str(config.output_dir.resolve()),
        "audit_artifact_policy": {
            "public_outputs": "public-safe markdown/status/per-symbol status/scrubbed structured research JSON only",
            "private_outputs": "request text and attempt metadata allowed; no transcript payloads or secrets",
            "private_directory_mode": "0700",
            "private_file_mode": "0600",
            "web_root_copy": False,
            "git_commit": False,
        },
        "public_latest_written": False,
        "provider_model_io_embedded": False,
    }


def audit_attempt_summary(config: RunConfig, results: list[dict[str, Any]]) -> dict[str, Any]:
    attempts_dir = private_audit_dir(config) / "attempts"
    empty = {
        "total_attempts": 0,
        "attempt_file_count": 0,
        "overwritten_resume_groups": 0,
        "failure_reason_counts": {},
        "source": "per_symbol_status",
    }
    if not attempts_dir.exists():
        return empty
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    failure_counts: dict[str, int] = {}
    file_count = 0
    for path in sorted(attempts_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("input_metadata") if isinstance(payload.get("input_metadata"), dict) else {}
        exchange = str(metadata.get("exchange") or "")
        symbol = str(metadata.get("symbol") or "")
        if not exchange or not symbol:
            audit_ref = str(payload.get("audit_ref") or "")
            parts = audit_ref.split(":")
            if len(parts) >= 3:
                exchange, symbol = parts[-2], parts[-1]
        if not exchange or not symbol:
            continue
        attempt = int(payload.get("attempt") or 0)
        if attempt < 1:
            continue
        file_count += 1
        key = (exchange, symbol)
        group = groups.setdefault(key, {"attempts": set(), "statuses": {}})
        group["attempts"].add(attempt)
        group["statuses"][attempt] = str(payload.get("status") or "")
        reason = str(payload.get("failure_reason") or "")
        if reason:
            reason_key = reason.split(":", 1)[0]
            failure_counts[reason_key] = failure_counts.get(reason_key, 0) + 1

    result_attempts = {
        (str(result.get("exchange") or ""), str(result.get("symbol") or "")): int(result.get("attempts") or 0)
        for result in results
    }
    total_attempts = 0
    overwritten_resume_groups = 0
    for key, group in groups.items():
        attempt_numbers = sorted(group["attempts"])
        if not attempt_numbers:
            continue
        max_attempt = attempt_numbers[-1]
        final_attempts = result_attempts.get(key, 0)
        statuses = group["statuses"]
        if final_attempts == 1 and statuses.get(1) == "success" and any(
            attempt > 1 and statuses.get(attempt) != "success" for attempt in attempt_numbers
        ):
            total_attempts += max_attempt + 1
            overwritten_resume_groups += 1
        else:
            total_attempts += max(max_attempt, final_attempts)

    return {
        "total_attempts": total_attempts,
        "attempt_file_count": file_count,
        "overwritten_resume_groups": overwritten_resume_groups,
        "failure_reason_counts": failure_counts,
        "source": "private_audit_attempts",
    }


def failure_reason_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        for attempt in result.get("attempt_metrics") or []:
            reason = str(attempt.get("failure_reason") or "")
            if not reason:
                continue
            key = reason.split(":", 1)[0]
            counts[key] = counts.get(key, 0) + 1
    return counts


def elapsed_summary(values: list[float]) -> dict[str, float | None]:
    clean = sorted(value for value in values if value >= 0)
    if not clean:
        return {"average": None, "p50": None, "p95": None}
    return {
        "average": round(sum(clean) / len(clean), 3),
        "p50": round(percentile(clean, 0.50), 3),
        "p95": round(percentile(clean, 0.95), 3),
    }


def percentile(values: list[float], q: float) -> float:
    if len(values) == 1:
        return values[0]
    index = (len(values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    fraction = index - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def per_symbol_status(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": PER_SYMBOL_SCHEMA,
        "items": [
            {
                "symbol": result["symbol"],
                "exchange": result["exchange"],
                "provider_ticker": result["provider_ticker"],
                "status": result["status"],
                "attempts": int(result.get("attempts") or 0),
                "failure_reason": result["failure_reason"],
                "last_failure_reason": result.get("last_failure_reason", result["failure_reason"]),
                "audit_ref": result.get("audit_ref", ""),
                "started_at_utc": result["started_at_utc"],
                "finished_at_utc": result["finished_at_utc"],
                "elapsed_seconds": result["elapsed_seconds"],
            }
            for result in results
        ],
    }


def write_outputs(
    *,
    config: RunConfig,
    results: list[dict[str, Any]],
    status: dict[str, Any],
) -> dict[str, str]:
    output_dir = config.output_dir
    symbol_dir = output_dir / "symbols"
    ensure_public_dirs(config)
    report_path = output_dir / f"full_research_test_{config.as_of_date.isoformat()}.md"
    status_path = output_dir / "status.json"
    per_symbol_path = output_dir / "per_symbol_status.json"

    for result in results:
        if result["status"] != "success":
            continue
        symbol_path = symbol_dir / f"{result['exchange']}_{result['symbol']}.json"
        write_json_atomic(symbol_path, result["research"])

    write_text_atomic(report_path, render_markdown(status=status, results=results))
    write_json_atomic(status_path, status)
    write_json_atomic(per_symbol_path, per_symbol_status(results))
    return {
        "report_path": str(report_path.resolve()),
        "status_path": str(status_path.resolve()),
        "per_symbol_status_path": str(per_symbol_path.resolve()),
        "symbols_dir": str(symbol_dir.resolve()),
    }


def ensure_public_dirs(config: RunConfig) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "symbols").mkdir(parents=True, exist_ok=True)


def write_checkpoint(
    *,
    config: RunConfig,
    universe_count: int,
    results: list[dict[str, Any]],
    started_at_utc: str,
    started_monotonic: float,
) -> None:
    ensure_public_dirs(config)
    for result in results:
        if result.get("status") != "success" or not result.get("research"):
            continue
        symbol_path = config.output_dir / "symbols" / f"{result['exchange']}_{result['symbol']}.json"
        write_json_atomic(symbol_path, result["research"])
    status = build_status(
        config=config,
        universe_count=universe_count,
        results=sorted(results, key=lambda row: (str(row["exchange"]), str(row["symbol"]))),
        started_at_utc=started_at_utc,
        finished_at_utc=utc_now_iso(),
        elapsed_seconds=time.monotonic() - started_monotonic,
    )
    write_json_atomic(config.output_dir / "status.json", status)
    write_json_atomic(config.output_dir / "per_symbol_status.json", per_symbol_status(results))


def load_resume_results(config: RunConfig, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not config.resume:
        return []
    per_symbol_path = config.output_dir / "per_symbol_status.json"
    if not per_symbol_path.exists():
        return []
    try:
        payload = json.loads(per_symbol_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    rows = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    item_by_key = {(item["exchange"], item["symbol"]): item for item in items}
    results: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "success":
            continue
        key = (str(row.get("exchange") or ""), str(row.get("symbol") or ""))
        item = item_by_key.get(key)
        if not item:
            continue
        symbol_path = config.output_dir / "symbols" / f"{item['exchange']}_{item['symbol']}.json"
        try:
            research = json.loads(symbol_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        results.append(
            {
                "symbol": item["symbol"],
                "exchange": item["exchange"],
                "provider_ticker": item["provider_ticker"],
                "status": "success",
                "failure_reason": "",
                "last_failure_reason": "",
                "attempts": int(row.get("attempts") or 0),
                "attempt_metrics": [],
                "audit_ref": str(row.get("audit_ref") or ""),
                "started_at_utc": str(row.get("started_at_utc") or ""),
                "finished_at_utc": str(row.get("finished_at_utc") or ""),
                "elapsed_seconds": float(row.get("elapsed_seconds") or 0.0),
                "research": research,
            }
        )
    return results


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_text_atomic(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def render_markdown(*, status: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        f"# GOTRA Public Stock-Pool Full Research Test - {status['as_of_date']}",
        "",
        "## Boundary",
        "",
        *[f"- {line}" for line in BOUNDARY_LINES],
        "",
        "## Run Status",
        "",
        f"- mode: {status['mode']}",
        f"- run_status: {status['run_status']}",
        f"- trading_date: {status['trading_date']}",
        f"- universe_count: {status['universe_count']}",
        f"- success_count: {status['success_count']}",
        f"- failed_count: {status['failed_count']}",
        f"- started_at_utc: {status['started_at_utc']}",
        f"- finished_at_utc: {status['finished_at_utc']}",
        f"- elapsed_seconds: {status['elapsed_seconds']}",
        f"- llm_runner: {status['llm_runner']}",
        f"- model: {status['model']}",
        f"- reasoning_effort: {status['reasoning_effort']}",
        "",
        "## Failed Symbols",
        "",
    ]
    if status["failed_symbols"]:
        lines.extend(["| Exchange | Symbol | Provider Ticker | Reason |", "|---|---|---|---|"])
        for item in status["failed_symbols"]:
            lines.append(
                f"| {item['exchange']} | {item['symbol']} | {item['provider_ticker']} | {item['reason']} |"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Research Summaries", ""])
    for result in results:
        if result["status"] != "success":
            continue
        research = result["research"]
        lines.extend(
            [
                f"### {research['exchange']}:{research['symbol']}",
                "",
                f"- status: {research['status']}",
                f"- as_of_date: {research['as_of_date']}",
                f"- research_summary: {research['research_summary']}",
                f"- price_context: {research['price_context']}",
                "- key_updates:",
                *[f"  - {item}" for item in research["key_updates"]],
                "- risk_factors:",
                *[f"  - {item}" for item in research["risk_factors"]],
                "- watch_items:",
                *[f"  - {item}" for item in research["watch_items"]],
                "- source_notes:",
                *[f"  - {item}" for item in research["source_notes"]],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def run(config: RunConfig, *, universe_items: list[dict[str, Any]] | None = None, runner: LlmRunner | None = None) -> int:
    invocation_started_at_utc = utc_now_iso()
    started = time.monotonic()
    ensure_public_dirs(config)
    ensure_private_dir(private_audit_dir(config))
    items = universe_items if universe_items is not None else load_universe(config.universe_url)
    if config.llm_runner != "codex-cli":
        raise RuntimeError(f"unsupported llm runner: {config.llm_runner}")
    active_runner = runner or CodexCliRunner(
        codex_bin=config.codex_bin,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        cwd=REPO_ROOT,
    )
    resumed_results = load_resume_results(config, items)
    started_at_utc = earliest_started_at(resumed_results, invocation_started_at_utc)

    def checkpoint(current_results: list[dict[str, Any]]) -> None:
        write_checkpoint(
            config=config,
            universe_count=len(items),
            results=current_results,
            started_at_utc=started_at_utc,
            started_monotonic=started,
        )

    results = run_jobs(
        items=items,
        config=config,
        runner=active_runner,
        checkpoint_callback=checkpoint,
        initial_results=resumed_results,
    )
    finished_at_utc = utc_now_iso()
    elapsed = elapsed_from_result_timestamps(results) if config.resume else None
    if elapsed is None:
        elapsed = time.monotonic() - started
    status = build_status(
        config=config,
        universe_count=len(items),
        results=results,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        elapsed_seconds=elapsed,
    )
    try:
        paths = write_outputs(config=config, results=results, status=status)
    except Exception as exc:  # noqa: BLE001 - preserve failure in status.json when possible.
        failure_status = dict(status)
        failure_status["ok"] = False
        failure_status["run_status"] = "failed"
        failure_status["artifact_write_status"] = "failed"
        failure_status["artifact_write_failure_reason"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(config.output_dir / "status.json", failure_status)
        print(json.dumps(failure_status, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    status_with_paths = dict(status)
    status_with_paths["output_paths"] = paths
    write_json_atomic(config.output_dir / "status.json", status_with_paths)
    print(json.dumps(status_with_paths, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status_with_paths["ok"] else 2


def main(argv: list[str] | None = None) -> int:
    try:
        return run(config_from_args(parse_args(argv)))
    except Exception as exc:  # noqa: BLE001 - fail closed without secret values.
        print(f"full research test failed: {sanitize_text(type(exc).__name__ + ': ' + str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
