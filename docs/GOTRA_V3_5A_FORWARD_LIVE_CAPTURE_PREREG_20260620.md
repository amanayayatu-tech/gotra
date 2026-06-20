# GOTRA v3.5A Forward-Live / Future-Only Decision Capture Prereg

Date: 2026-06-20

## Scope

This preregisters the v3.5A forward-live / future-only capture path for GOTRA. The evidence layer target is engineering evidence for an auditable future-only decision ledger. This is not outcome scoring, not an OOS pass, not public/scientific proof, and not trading or investment advice.

v3.5A is stacked on the v3.4 Codex CLI experiment family and deterministic reference work:

- Base stack: PR #20 -> PR #21 -> PR #22.
- Backend family, if a real capture is run: `codex_cli_llm_backend`.
- Old Kimi/GLM/DeepSeek provider API formal-lite and parser repair lines remain frozen historical provider-runtime evidence.
- Codex CLI backend results must not be treated as equivalent to old provider API results.

## Interpretation Boundary

Historical `direct_llm` is reported as `direct_llm_parametric_memory_control`, not as a clean no-future baseline. In forward-live capture, the future outcome has not occurred yet, so direct LLM can be captured as a modern LLM parametric-memory control arm, but it still cannot prove GOTRA, ksana, or alaya success or failure by itself.

The clean reference for historical comparison is `deterministic_price_only_baseline`. Future mature interpretation should prioritize `ksana_real_research` vs `full_gotra` only after true future outcomes mature and feedback eligibility is auditable.

## First Capture Grid

The first v3.5A capture grid is intentionally small and auditable:

- Tickers: `AAPL,MSFT,NVDA,TSM,0700.HK`
- Capture timestamp policy: exact UTC timestamp recorded in the run summary and artifacts.
- Local timezone: `Asia/Shanghai`
- Local capture date for the first run: 2026-06-20
- Calendar caveat: 2026-06-20 Asia/Shanghai is a Saturday, so this is a weekend/pre-market future-only decision capture, not a regular market-session decision.
- Horizon: 30 calendar days, matching the existing v3 harness horizon.
- Arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- Input layers: `price_only_packet`, `richer_research_packet`
- Expected backend decision captures: 5 tickers x 1 capture timestamp x 2 input layers x 4 arms = 40
- Deterministic reference: one `deterministic_price_only_baseline` capture per unique `(ticker, capture_decision_date, horizon)`, expected count = 5

## Required Capture Fields

Every LLM-backed capture artifact must include:

- `decision_timestamp_utc`
- `decision_date_local`
- `horizon_end_date`
- `backend`
- `codex_cli_version`
- `model`
- `reasoning`
- `prompt_hash`
- `output_transcript_path`
- `parsed_decision_hash`
- `run_id`
- `arm`
- `input_layer`
- `ticker`
- `future_outcome_status=not_matured`
- `future_outcome_scoring_status=NOT_MATURED`

The deterministic reference must include the same future-only outcome status, the latest visible price date, visible price row count, future rows excluded, and `provider_or_backend_called=false`.

## Future-Data Rules

Decision prompts and capture artifacts may only use information available at or before the capture timestamp or latest visible market data timestamp.

Outcome fields must be absent from capture artifacts and decision payloads, or explicitly marked as not matured. Forbidden outcome fields include realized returns, actual changes, future returns, errors, MSE/MAE, direction-hit status, or any post-horizon outcome label.

Research artifacts with `availability_date`, `publish_timestamp`, `captured_at`, or `decision_date_max` after the capture timestamp/local capture date must be rejected before entering the prompt.

## Gate Sequence

1. Local checks: py_compile, ruff, focused tests.
2. No-LLM mock forward-live capture validation.
3. Optional first Codex CLI capture smoke only if local/mock gates pass and `codex_cli_llm_backend` is available.

No outcome scoring is allowed in v3.5A. Matured scoring belongs to a later v3.5B job after the horizon end date.

## Acceptance

For mock engineering pass:

- Capture summary status is `FORWARD_LIVE_CAPTURE_PASS`.
- Future outcome status is `not_matured`.
- Future outcome scoring status is `NOT_MATURED`.
- Outcome matured/scored counts are zero.
- Future-data violation count is zero.
- Deterministic reference is present with backend/provider called false.
- Transcript and parsed-decision hash counts are zero in mock mode.

For optional real Codex CLI capture smoke:

- Backend name is exactly `codex_cli_llm_backend`.
- `codex_cli_version`, model, reasoning, prompt hash, transcript path, parsed decision hash, and run id are recorded.
- Transcript/raw output artifacts remain in ignored run directories and are not committed.
- No outcome scoring is performed.

## Non-Claims

This preregistered run cannot establish OOS performance, scientific/public proof, product superiority, or trading value. It only establishes whether the future-only capture ledger path can record auditable decisions and metadata before outcomes mature.
