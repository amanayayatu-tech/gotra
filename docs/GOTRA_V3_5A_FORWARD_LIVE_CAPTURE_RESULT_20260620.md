# GOTRA v3.5A Forward-Live / Future-Only Decision Capture Result

Date: 2026-06-20

## Project

- Project: GOTRA v3.5A forward-live / future-only decision capture path
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-v3-5a-forward-live-capture-20260620`
- Base PR: PR #22, `codex/gotra-v3-4c-codex-cli-scaled-reference-20260620`
- Prereg: `docs/GOTRA_V3_5A_FORWARD_LIVE_CAPTURE_PREREG_20260620.md`

## Evidence Layer

Reached evidence layer:

1. Local checks and focused tests.
2. No-LLM/mock forward-live capture validation.
3. First Codex CLI backend capture smoke on a smaller canary subset.

This is forward-live capture engineering evidence only. Outcomes are not matured and no outcome scoring was performed. This is not an OOS pass, not scientific/public proof, and not trading or investment advice.

## Boundary

- Kimi/GLM/DeepSeek provider APIs were not called.
- Old provider API parser/formal-lite reruns were not entered.
- Codex CLI backend results are part of a new experiment family and are not equivalent to old provider API results.
- Run directories, Codex CLI transcripts, raw outputs, and generated capture artifacts remain local under ignored `data/backtest/runs/*` paths and are not committed.
- No `.env` or API key content was read, printed, or committed.

## Capture Configuration

- Backend family: `codex_cli_llm_backend` for real capture smoke.
- Model: `gpt-5.5`
- Reasoning setting: `low`
- Horizon: 30 calendar days
- Local timezone: `Asia/Shanghai`
- Capture date: 2026-06-20 Asia/Shanghai
- Calendar caveat: 2026-06-20 Asia/Shanghai is a Saturday, so the real capture smoke is a weekend/pre-market future-only decision capture, not a regular market-session decision.
- Arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- Input layers: `price_only_packet`, `richer_research_packet`
- Deterministic reference: `deterministic_price_only_baseline`, one reference per unique `(ticker, capture_decision_date, horizon)`

Historical `direct_llm` is reported as `direct_llm_parametric_memory_control`, not a clean no-future baseline. In this forward-live path the future outcome has not happened yet, but direct LLM still remains a control/diagnostic arm and does not prove GOTRA/ksana/alaya success or failure.

## Local Validation

Commands passed:

```bash
uv run python -m py_compile scripts/baseline_v3_four_arm.py scripts/baseline_v3_5_forward_live_capture.py gotra/backtest/statistics.py
uv run ruff check --no-cache scripts/baseline_v3_four_arm.py scripts/baseline_v3_5_forward_live_capture.py tests/test_baseline_v3_four_arm.py tests/test_forward_live_capture.py gotra/backtest/statistics.py
uv run pytest -q tests/test_forward_live_capture.py tests/test_baseline_v3_four_arm.py
```

Focused result: `54 passed`.

## Mock Capture

- Run id: `baseline_v3_5a_forward_live_mock_20260620T131950Z`
- Mode: `mock`
- Run root: `data/backtest/runs/baseline_v3_5a_forward_live_mock_20260620T131950Z`
- Capture timestamp UTC: `2026-06-20T13:19:50Z`
- Grid: 5 tickers x 2 input layers x 4 arms = 40 capture decisions
- Status: `FORWARD_LIVE_CAPTURE_PASS`
- Expected capture decisions: 40
- Actual capture artifacts: 40
- Future outcome status: `not_matured`
- Future outcome scoring status: `NOT_MATURED`
- Outcome matured/scored counts: 0 / 0
- Future-data violation count: 0
- Prompt hash count: 40
- Codex CLI transcript path count: 0
- Parsed decision hash count: 0
- Deterministic reference count: 5
- Deterministic reference latest visible price date max: `2026-06-18`
- Deterministic reference future-data violations: 0
- Deterministic reference provider/backend called: false
- Clean historical reference status: `PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE`

## Codex CLI First Capture Smoke

- Run id: `baseline_v3_5a_forward_live_codex_smoke_20260620T132011Z`
- Mode: `codex-cli-capture`
- Run root: `data/backtest/runs/baseline_v3_5a_forward_live_codex_smoke_20260620T132011Z`
- Capture timestamp UTC: `2026-06-20T13:20:11Z`
- Grid: AAPL x 2 input layers x 4 arms = 8 capture decisions
- Backend: `codex_cli_llm_backend`
- Codex CLI version: `codex-cli 0.139.0`
- Model: `gpt-5.5`
- Reasoning: `low`
- Status: `FORWARD_LIVE_CAPTURE_PASS`
- Expected capture decisions: 8
- Actual capture artifacts: 8
- Future outcome status: `not_matured`
- Future outcome scoring status: `NOT_MATURED`
- Outcome matured/scored counts: 0 / 0
- Future-data violation count: 0
- Prompt hash count: 8
- Output transcript path count: 8
- Parsed decision hash count: 8
- Deterministic reference count: 1
- Deterministic reference latest visible price date max: `2026-06-18`
- Deterministic reference future-data violations: 0
- Deterministic reference provider/backend called: false
- Clean historical reference status: `PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE`

Transcript paths and raw outputs are local artifacts only and are intentionally not included in this document.

## Outcome Maturity

- Current outcome maturity status: `NOT_MATURED`
- Return/MSE/direction-hit/OOS scoring: not entered
- H1/H2/H3 verdicts: not available from v3.5A capture

The horizon end date for the captured local date is `2026-07-20`. Scoring should wait for a later v3.5B outcome maturity/scoring job with explicit future-data and artifact-boundary checks.

## Deterministic Reference Status

The v3.5A capture path records deterministic price-only reference captures without calling any backend/provider. This preserves the clean historical reference role introduced in v3.4b while keeping outcome scoring disabled until future outcomes mature.

## Remaining Blockers

- No outcome can be scored until the horizon outcome has matured.
- v3.5B needs an outcome maturity/scoring job that reads captured decisions, verifies no future-data contamination, and computes results only after maturity.
- A scheduler/automation spec may be useful before running repeated future-live captures.

## Next Action

Plan v3.5B as an outcome maturity/scoring and/or scheduler automation layer. Do not revive old provider API parser/formal-lite reruns as the main blocker.
