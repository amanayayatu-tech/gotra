# GOTRA Baseline v3 Formal-Lite Provider Run Plan

UTC frozen at: 2026-06-19T09:24:12Z

## Purpose

Run the Baseline v3 four-arm formal-lite provider experiment under the
preregistered minimum publishable configuration. This is an internal research
formal-lite run. It is not OOS acceptance, not a science/public claim, not a
trading claim, and not investment advice.

## Preregistration Anchor

- Preregistration/design spec:
  `docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md`
- Implementation branch used as base:
  `codex/baseline-v3-four-arm-impl-20260619`
- Implementation anchor commit:
  `d63bbf1b7b4e4771f3b885b3c5f2208e0a20fe15`
- Formal-lite run branch:
  `codex/baseline-v3-formal-lite-run-20260619`
- Upstream implementation PR:
  `https://github.com/amanayayatu-tech/gotra/pull/9`

## Frozen Provider Configuration

```text
provider: kimi
provider_model: Kimi-K2.6
provider_base_url: https://api.sophnet.com/v1/chat/completions
provider_max_tokens: 2000
provider_concurrency: 1
max_provider_concurrency: 2
adaptive_concurrency: existing harness behavior only; never above 2
input_layer: both
arms: direct_llm,ksana_formatting_only,ksana_real_research,full_gotra
horizon_days: 30
warm_up_dates: 3
request_timeout_seconds: 900
max_request_timeout_seconds: 900
timeout_retries: 1
timeout_retry_backoff_seconds: 30
token_budget_authorized: 500000000
env_file: .env.sophnet
```

The provider/model/base URL/max tokens/timeouts/grid/arms/input layers/warm-up
settings are frozen before provider execution. They must not be changed based on
intermediate results.

## Frozen Ticker Universe

Use exactly this order:

```text
AAPL,MSFT,NVDA,TSM,AMD,AMZN,AVGO,GOOGL,META,JPM,V,WMT,COST,UNH,JNJ,XOM,MCD,NVO,0700.HK,9988.HK,3690.HK,1211.HK,1810.HK,6060.HK,0005.HK,0388.HK,0941.HK,2318.HK,1299.HK,0883.HK
```

## Frozen Decision Dates

Use exactly this order:

```text
2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03,2024-07-02,2024-08-01,2024-09-03,2024-10-02,2024-11-01,2024-12-02
```

## Expected Size

```text
provider_steps: 30 tickers x 12 dates x 4 arms x 2 input_layers = 2880
scored_paired_groups: 30 tickers x 9 scored dates x 2 input_layers = 540
warm_up_dates: first 3 dates are warm_up and excluded from final scoring
```

## Acceptance Gate

Completion status may be classified as `FORMAL_LITE_PASS` only if all are true:

```text
minimum grid reached: 30 tickers x 12 dates x 4 arms x 2 input_layers
paired_coverage >= 0.95
future_data_violation_count = 0
provider_error_rate <= 0.05
H1/H2/H3 statistics computed
C1-C5 statistics computed
```

If the provider/canary/formal run fails under the bounded retry/resume rules,
the status is `PROVIDER_BLOCKED` or the exact exposed terminal runtime failure.
If the feedback-eligible subset is too small for H2, report
`DATA_INSUFFICIENT_FOR_H2`, not alaya failure.

## Run IDs

These run IDs are frozen before provider execution:

```text
mock: baseline_v3_four_arm_formal_lite_mock_20260619T092412Z
canary: baseline_v3_four_arm_formal_lite_canary_kimi26_20260619T092412Z
formal_lite: baseline_v3_four_arm_formal_lite_kimi26_min30x12_20260619T092412Z
```

## Execution Ladder

1. Local deterministic checks:
   - `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py`
   - `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py`
   - `uv run pytest -q tests/test_baseline_v3_four_arm.py`
   - `git diff --check`
2. Mock gate on the frozen full grid. No provider HTTP.
3. Fresh Kimi canary gate on a small frozen canary grid.
4. Exactly one formal-lite provider run on the frozen full grid, with bounded
   retry and at most one resume if the local process crashes without summary.

## Forbidden Changes

- Do not read, print, or commit API keys or `.env` contents.
- Do not commit `data/backtest/runs/*`, provider raw files, `.env*`, DB files,
  bundles, tar/zip files, `data/paper_trading/*`, or Stage8/Stage9 artifacts.
- Do not merge PR #9 or any formal-lite PR from this run.
- Do not change v2 results/definitions or write back Stage8/Stage9.
- Do not remove ticker/date/arm/input_layer rows based on results.
- Do not tune schema, metrics, warm-up length, high-quality feedback threshold,
  tau, provider/model/base URL/max tokens, timeout, or concurrency to improve
  gotra/ksana/alaya outcomes.
- Do not hide direct_llm or ksana_formatting_only.
- Do not interpret directional metrics as OOS/science/public/trading evidence.

## Non-Claims

This run can support only a bounded Baseline v3 formal-lite internal research
verdict under the preregistered grid. It cannot support OOS acceptance,
science/public claims, trading claims, or investment advice.
