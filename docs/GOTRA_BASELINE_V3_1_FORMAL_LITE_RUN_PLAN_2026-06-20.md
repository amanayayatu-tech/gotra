# GOTRA Baseline v3.1 Formal-Lite Run Plan

Date: 2026-06-20

## Scope

This plan freezes the Baseline v3.1 formal-lite provider run before any provider formal-lite call.

Evidence layer: formal-lite internal research evidence only.

This run is not OOS evidence, not forward-live evidence, not a science/public claim, not a trading claim, and not investment advice.

The v3.1 real-evidence path uses the committed local fixture `tests/fixtures/baseline_v3_1_research_artifacts.json`. This fixture validates real/unverified evidence plumbing, source-kind accounting, and future-data rejection, but it is not a production-grade multi-source research retrieval pipeline.

## Prereg Anchor

- v3.1 prereg/design anchor: `docs/GOTRA_BASELINE_V3_1_REAL_EVIDENCE_PREREG_2026-06-19.md`
- Anchor commit: `4679211 Implement Baseline v3.1 real-evidence gates`
- Starting branch: `codex/baseline-v3-1-real-evidence-impl-20260619`
- Run branch: `codex/baseline-v3-1-formal-lite-run-20260620`

## Frozen Provider Config

- provider: `kimi`
- provider_model: `Kimi-K2.6`
- provider_base_url: `https://api.sophnet.com/v1/chat/completions`
- provider_max_tokens: `2000`
- provider_concurrency: `1`
- max_provider_concurrency: `2`
- request/max timeout: `900` seconds where supported
- timeout_retries: `1`
- timeout_retry_backoff_seconds: `30`
- env source: `.env.sophnet`, loaded only by CLI; secret values must not be read, printed, or committed

## Frozen Evidence Config

- research_artifacts_path: `tests/fixtures/baseline_v3_1_research_artifacts.json`
- accepted artifacts must satisfy `availability_date <= decision_date`
- artifacts containing future-leak fields must be rejected and counted
- `source_kind_counts` must be reported
- strict feedback diagnostics must be reported
- H2 must not be interpreted unless `true_independent_feedback_eligible_points > 0`

## Frozen Arms And Inputs

Arms:

- `direct_llm`
- `ksana_formatting_only`
- `ksana_real_research`
- `full_gotra`

Input layer: `both`

Input layers retained:

- `price_only_packet`
- `richer_research_packet`

No arm or input layer may be hidden or removed.

## Frozen Grid

Tickers, exact order:

```text
AAPL,MSFT,NVDA,TSM,AMD,AMZN,AVGO,GOOGL,META,JPM,V,WMT,COST,UNH,JNJ,XOM,MCD,NVO,0700.HK,9988.HK,3690.HK,1211.HK,1810.HK,6060.HK,0005.HK,0388.HK,0941.HK,2318.HK,1299.HK,0883.HK
```

Decision dates, exact order:

```text
2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03,2024-07-02,2024-08-01,2024-09-03,2024-10-02,2024-11-01,2024-12-02
```

Warm-up dates: `3`

Horizon days: `30`

Expected provider steps:

```text
30 tickers x 12 dates x 4 arms x 2 input layers = 2880
```

Expected scored paired groups:

```text
30 tickers x 9 scored dates x 2 input layers = 540
```

## Planned Run IDs

- full-grid mock: `baseline_v3_1_formal_lite_mock_20260620T<UTC>Z`
- provider canary: `baseline_v3_1_formal_lite_canary_kimi26_20260620T<UTC>Z`
- formal-lite provider run: `baseline_v3_1_formal_lite_kimi26_min30x12_20260620T<UTC>Z`

## Gates

Local deterministic checks must pass before any provider run:

- `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py`
- `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py`
- `uv run pytest -q tests/test_baseline_v3_four_arm.py`
- `git diff --check`

Full-grid mock must pass before provider canary:

- no provider HTTP call
- `MOCK_PASS`
- paired coverage at least `0.95`
- accepted-artifact future-data violations: `0`
- rejected future/leak fixture artifacts counted
- `research_source_leak_count = 0`
- `source_kind_counts` reported
- strict/H2 diagnostics present
- H2 reports data insufficiency if no true independent feedback is available

Provider canary must pass before formal-lite provider run:

- `PROVIDER_CANARY_PASS`
- provider/schema/input_echo/429/timeout/future-data/raw errors all `0`
- source-kind and strict/H2 diagnostics present

Minimum formal-lite completion gate:

- paired coverage at least `0.95`
- `future_data_violation_count = 0`
- `provider_error_rate < 0.05`
- `research_source_leak_count = 0`
- `source_kind_counts` reported
- strict feedback diagnostics reported
- H1/H2/H3 statistics and product layers computed, or explicitly `DATA_INSUFFICIENT` where applicable

## Status And Interpretation Rules

Completion status is separate from research verdict.

- `FORMAL_LITE_PASS`: engineering/provider gates pass and H1/H2/H3 layers are computed where data is sufficient.
- `FORMAL_LITE_INCONCLUSIVE`: provider run completed but H1/H2/H3 directional criteria are not satisfied or key hypotheses are data-insufficient.
- `DATA_INSUFFICIENT_FOR_H2_TRUE_INDEPENDENT_FEEDBACK`: true independent feedback eligibility is absent or insufficient.
- `PROVIDER_BLOCKED`, `MOCK_BLOCKED`, or exact failure status: gate failed.

H1 can be interpreted only as internal/formal-lite evidence and only with source-kind and fixture limitations disclosed.

H2 cannot be interpreted unless `true_independent_feedback_eligible_points > 0`.

H3 product metrics and prediction metrics must be reported separately. Product value does not support trading, OOS, or science/public claims.

If `direct_llm` wins or the result is mixed, report it honestly. Do not tune the grid, thresholds, provider settings, prompt contract, arms, input layers, or strict eligibility definition.

## Forbidden Changes

- Do not modify provider/model/max_tokens to chase a directional result.
- Do not modify ticker/date/universe/arms/input_layer/warm_up/threshold/tau/strict eligibility definitions to chase a directional result.
- Do not submit `.env*`, secrets, `data/backtest/runs/*`, `provider_raw`, DB files, bundles, tar/zip files, `data/paper_trading/*`, Stage8/Stage9 artifacts, or unrelated v2 files.
- Do not merge PR #10, PR #11, or the formal-lite PR.

## Non-Claims

This plan does not authorize:

- OOS claims
- forward-live claims
- science/public claims
- trading or investment claims
- production-grade real research pipeline claims
