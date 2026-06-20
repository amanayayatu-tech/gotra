# GOTRA Baseline v3.2 Formal-Lite Run Plan

Date: 2026-06-20

## Scope

This plan freezes the Baseline v3.2 provider ramp and formal-lite run before
any v3.2 provider call is made from this branch.

Evidence ladder:

1. local deterministic checks;
2. no-provider mock recheck;
3. Kimi provider canary;
4. tiny provider smoke;
5. formal-lite internal research run only if prior gates pass.

This plan does not authorize OOS, forward-live, science/public, trading, or
investment claims. Run completion, provider health, and H1/H2/H3 research
verdicts must be reported separately.

## Branch and Prereg Anchors

- Base implementation PR: PR #13,
  `codex/baseline-v3-2-evidence-feedback-impl-20260620`.
- Starting implementation commit: `8db9217`.
- v3.2 substrate prereg:
  `docs/GOTRA_BASELINE_V3_2_EVIDENCE_FEEDBACK_PREREG_2026-06-20.md`.
- This run branch: `codex/baseline-v3-2-formal-lite-run-20260620`.

## Locked Provider Configuration

- Provider: `kimi`
- Model: `Kimi-K2.6`
- Base URL: `https://api.sophnet.com/v1/chat/completions`
- Provider max tokens: `2000`
- Request timeout: current harness per-arm timeout policy with
  `--max-request-timeout-seconds 900`
- Timeout retries: `1`
- Timeout retry backoff seconds: `30`
- Provider auth: use ignored project env file via `--env-file .env.sophnet`
  when provider commands run. Secret values must not be printed.

## Locked Harness Configuration

- Arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`,
  `full_gotra`
- Input layers: `price_only_packet`, `richer_research_packet`
- Horizon days: `30`
- Warm-up dates for formal-lite: `3`
- Research artifact path:
  `tests/fixtures/baseline_v3_1_research_artifacts.json`
- Feedback artifact path:
  `tests/fixtures/baseline_v3_2_feedback_artifacts.json`

The research fixture exercises the real/unverified/synthetic schema and
future-data gate, but it is not production-grade multi-source research
ingestion. Product metrics and prediction metrics remain separate.

The feedback fixture exercises true independent mature feedback eligibility.
Self-feedback, same-date/current-run feedback, malformed rows, duplicates, and
future feedback must not count toward true independent H2 eligibility.

## Formal-Lite Grid

Frozen ticker universe, in order:

`AAPL,MSFT,NVDA,TSM,AMD,AMZN,AVGO,GOOGL,META,JPM,V,WMT,COST,UNH,JNJ,XOM,MCD,NVO,0700.HK,9988.HK,3690.HK,1211.HK,1810.HK,6060.HK,0005.HK,0388.HK,0941.HK,2318.HK,1299.HK,0883.HK`

Frozen decision dates, in order:

`2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03,2024-07-02,2024-08-01,2024-09-03,2024-10-02,2024-11-01,2024-12-02`

Expected formal-lite provider steps:

`30 tickers x 12 dates x 4 arms x 2 input layers = 2880`

Expected scored paired groups:

`30 tickers x 9 scored dates x 2 input layers = 540`

## Gate Sequence

### Local Checks

Required pass:

- `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py`
- `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py`
- `uv run pytest -q tests/test_baseline_v3_four_arm.py`
- `git diff --check`

### Mock Recheck

Run id prefix: `baseline_v3_2_formal_lite_mock_20260620T`

Use the full formal-lite grid if feasible, with both research and feedback
fixtures. Required gate:

- `MOCK_PASS`
- no provider HTTP
- paired coverage `1.0`
- future-data violations `0`
- research source leak count `0`
- feedback source leak count `0`
- rejected feedback schema count greater than `0`
- rejected feedback future-data count greater than `0`
- true independent feedback eligible points greater than `0`

### Kimi Provider Canary

Run id prefix: `baseline_v3_2_formal_lite_canary_kimi26_20260620T`

Grid:

- tickers: `AAPL,MSFT`
- dates:
  `2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03`
- all four arms
- both input layers
- warm-up dates: `2`
- provider concurrency: `1`
- max provider concurrency: `1`

Required gate:

- `PROVIDER_CANARY_PASS`
- expected step files complete
- paired coverage `1.0`
- provider/schema/input_echo/429/timeout/future-data/raw terminal errors `0`
- research source leak count `0`
- feedback source leak count `0`
- true independent feedback eligible points greater than `0`

### Tiny Provider Smoke

Run id prefix: `baseline_v3_2_formal_lite_tiny_smoke_kimi26_20260620T`

Grid:

- tickers: `AAPL,MSFT,NVDA`
- dates:
  `2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03`
- all four arms
- both input layers
- warm-up dates: `2`
- provider concurrency: `1`
- max provider concurrency: `2`

Required gate:

- provider pilot/smoke pass
- expected steps complete
- paired coverage `1.0`
- provider/schema/input_echo/429/timeout/future-data/raw terminal errors `0`
- research source leak count `0`
- feedback source leak count `0`
- true independent feedback eligible points greater than `0`

### Formal-Lite Provider Run

Run id prefix: `baseline_v3_2_formal_lite_kimi26_min30x12_20260620T`

Run only if local checks, mock, canary, and tiny smoke pass.

- Use the full frozen formal-lite grid above.
- Warm-up dates: `3`
- Provider concurrency: `2`
- Max provider concurrency: `4`
- Adaptive concurrency: existing harness conservative behavior.

Completion gates:

- expected steps complete or terminal blocked state honestly reported;
- paired coverage meets preregistered threshold;
- provider error rate below preregistered threshold;
- future-data violation count `0`;
- research source leak count `0`;
- feedback source leak count `0`;
- unrecovered provider/schema/input_echo/429/timeout/raw terminal errors within
  the preregistered gate;
- true independent feedback eligible point count and H2 denominator reported.

## Completion and Verdict Mapping

Run-level provider status may be `PROVIDER_PILOT_PASS`.

Canonical completion classification:

- `FORMAL_LITE_PASS` only if engineering/provider gates pass and H1/H2/H3
  layers are computed where data is sufficient;
- `FORMAL_LITE_INCONCLUSIVE` if the run completes but directional criteria are
  mixed or key hypothesis data remains insufficient;
- `PROVIDER_BLOCKED`, `MOCK_BLOCKED`, or a more specific terminal blocker if a
  gate fails.

H1/H2/H3 verdicts must be reported separately from run completion:

- H1 must disclose that research artifacts are committed local fixture
  real/unverified/synthetic evidence, not production-grade multi-source
  ingestion.
- H2 must use only true independent mature feedback eligibility; self-feedback
  cannot be merged into that denominator.
- H3 product metrics do not imply OOS, science/public, or trading value.

## Artifact Boundary

Allowed committed files for this run layer:

- this run plan;
- final v3.2 formal-lite result document;
- strictly necessary harness/tests only if a genuine provider-output contract
  bug is discovered and fixed with tests.

Forbidden committed files:

- `data/backtest/runs/*`
- provider raw files
- `.env*` or secrets
- DB, bundle, tar, zip artifacts
- `data/paper_trading/*`
- Stage8/Stage9 artifacts
- unrelated v2 docs/scripts
