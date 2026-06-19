# GOTRA Baseline v3 Formal-Lite Provider Result

Generated: 2026-06-19T15:00:47Z

## Project

- Project: GOTRA Baseline v3 Formal-Lite Provider Run
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/baseline-v3-formal-lite-run-20260619`
- Result HEAD at write time: `3e500d0a48ebf0589cb6947eba67f5f8186f92be`
- Upstream PR: https://github.com/amanayayatu-tech/gotra/pull/9
- Base branch for this result PR: `codex/baseline-v3-four-arm-impl-20260619`
- Prereg anchor: `docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md`
- Run plan: `docs/GOTRA_BASELINE_V3_FORMAL_LITE_RUN_PLAN_20260619.md`
- Run plan commit: `3e500d0 Preregister Baseline v3 formal-lite run plan`

## Evidence Layer

This result is formal-lite internal research evidence on the frozen Baseline v3 four-arm harness.

It is not OOS evidence, not forward-live evidence, not a science/public claim, not a trading claim, and not investment advice. Directional arm metrics below are reported to satisfy the preregistered internal research record only.

## Frozen Configuration

- Provider/model: `kimi` / `Kimi-K2.6`
- Provider base URL: `https://api.sophnet.com/v1/chat/completions`
- Provider max tokens: `2000`
- Provider concurrency: `1`
- Max provider concurrency: `2`
- Input layers: `price_only_packet`, `richer_research_packet`
- Arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- Warm-up dates: `3`
- Horizon days: `30`
- Request/max timeout: `900` seconds
- Timeout retries: `1`
- Timeout retry backoff: `30` seconds
- Expected provider steps: `30 tickers * 12 dates * 4 arms * 2 input_layers = 2880`
- Expected scored paired groups: `30 tickers * 9 scored dates * 2 input_layers = 540`

Tickers:

```text
AAPL,MSFT,NVDA,TSM,AMD,AMZN,AVGO,GOOGL,META,JPM,V,WMT,COST,UNH,JNJ,XOM,MCD,NVO,0700.HK,9988.HK,3690.HK,1211.HK,1810.HK,6060.HK,0005.HK,0388.HK,0941.HK,2318.HK,1299.HK,0883.HK
```

Decision dates:

```text
2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03,2024-07-02,2024-08-01,2024-09-03,2024-10-02,2024-11-01,2024-12-02
```

## Validation

- `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py` -> PASS
- `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py` -> PASS
- `uv run pytest -q tests/test_baseline_v3_four_arm.py` -> PASS (`26 passed in 0.61s`)
- `git diff --check` -> PASS before provider run

## Mock Gate

- Run id: `baseline_v3_four_arm_formal_lite_mock_20260619T092412Z`
- Status: `MOCK_PASS`
- Expected steps / actual step files: `2880 / 2880`
- Expected scored points / paired complete points: `540 / 540`
- Paired coverage: `1.0`
- Provider errors / schema contract errors / input echo / future-data / research source leak / 429 / timeout / raw saved: all `0`
- No provider HTTP was entered.

## Fresh Provider Canary Gate

- Run id: `baseline_v3_four_arm_formal_lite_canary_kimi26_20260619T092412Z`
- Status: `PROVIDER_CANARY_PASS`
- Expected steps / actual step files: `96 / 96`
- Expected scored points / paired complete points: `18 / 18`
- Paired coverage: `1.0`
- Provider errors / schema contract errors / input echo / future-data / research source leak / 429 / timeout / raw saved: all `0`
- Recovered retry count: `0`

## Formal-Lite Provider Run

- Run id: `baseline_v3_four_arm_formal_lite_kimi26_min30x12_20260619T092412Z`
- Run dir: `data/backtest/runs/baseline_v3_four_arm_formal_lite_kimi26_min30x12_20260619T092412Z`
- Status: `PROVIDER_PILOT_PASS`
- Expected steps / actual step files: `2880 / 2880`
- Expected scored points / paired complete points: `540 / 540`
- Paired coverage: `1.0`
- Provider error rate: `0.0`
- Provider errors / schema contract errors / input echo / future-data / research source leak / 429 / timeout / raw saved: all `0`
- Recovered retry count: `7`
- Recovered retry type: `provider_http_error`
- Unrecovered provider HTTP errors: `0`
- Unrecovered provider timeouts: `0`
- Request timeout applied: `900` seconds for all arms

## Completion Status

`FORMAL_LITE_PASS`

Rationale: the run met the frozen minimum size, `paired_coverage >= 0.95`, `future_data_violation_count = 0`, `provider_error_rate = 0.0`, and H1/H2/H3 statistical/product layers were computed. This completion status means the formal-lite internal experiment completed validly; it does not imply any favorable arm direction.

## H1/H2/H3 Research Verdict

- H1, ksana research value: not supported / inconclusive. On `richer_research_packet` C3, `ksana_real_research` did not significantly reduce MSE versus `direct_llm`; bootstrap CI crossed 0 and p-value was `0.7486`.
- H2, alaya feedback value: not supported / inconclusive. C4 was computed only on feedback-eligible points (`540` all, `270` per input layer), but `full_gotra` did not significantly reduce MSE versus `ksana_real_research`; all-layer p-value was `0.22` and CI crossed 0.
- H3, content product value: mixed / not fully established under the preregistered H3 wording. Prediction tolerance versus `ksana_real_research` was satisfied (`full_gotra` MSE +`1.87187%`, direction hit rate +`4.444444` pp), but product metrics were mixed versus `direct_llm`: stronger `error_attribution_quality` and `reasoning_auditability`, equal ledger/claim/risk/explanation fields, and lower `evidence_coverage`.

## C1-C5 Summary

Convention: `mean_loss_diff = left_arm MSE - right_arm MSE`. Negative values favor the left arm; positive values favor the right arm. This table is an internal statistical record only.

| Bucket | Comparison | Left | Right | Feedback eligible only | Paired points | Mean loss diff | 95% CI | p-value | Right arm better significant |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- |
| all | C1_direct_minus_formatting | direct_llm | ksana_formatting_only | false | 540 | -2.901093 | [-4.949623, -0.904668] | 0.0052 | false |
| all | C2_formatting_minus_real_research | ksana_formatting_only | ksana_real_research | false | 540 | 2.112668 | [-0.173986, 4.442294] | 0.0680 | false |
| all | C3_direct_minus_real_research | direct_llm | ksana_real_research | false | 540 | -0.788425 | [-3.232351, 1.873034] | 0.5272 | false |
| all | C4_real_research_minus_full_gotra | ksana_real_research | full_gotra | true | 540 | -2.981027 | [-7.904557, 1.668763] | 0.2200 | false |
| all | C5_direct_minus_full_gotra | direct_llm | full_gotra | false | 540 | -3.769452 | [-7.026786, -0.360152] | 0.0300 | false |
| price_only_packet | C1_direct_minus_formatting | direct_llm | ksana_formatting_only | false | 270 | -3.629540 | [-8.007369, 0.431022] | 0.0782 | false |
| price_only_packet | C2_formatting_minus_real_research | ksana_formatting_only | ksana_real_research | false | 270 | 2.514765 | [0.016609, 5.441571] | 0.0480 | true |
| price_only_packet | C3_direct_minus_real_research | direct_llm | ksana_real_research | false | 270 | -1.114775 | [-5.693407, 2.992562] | 0.6250 | false |
| price_only_packet | C4_real_research_minus_full_gotra | ksana_real_research | full_gotra | true | 270 | -2.920156 | [-9.030959, 2.677239] | 0.3318 | false |
| price_only_packet | C5_direct_minus_full_gotra | direct_llm | full_gotra | false | 270 | -4.034931 | [-8.880034, 0.642100] | 0.0938 | false |
| richer_research_packet | C1_direct_minus_formatting | direct_llm | ksana_formatting_only | false | 270 | -2.172646 | [-5.305965, 1.901447] | 0.2456 | false |
| richer_research_packet | C2_formatting_minus_real_research | ksana_formatting_only | ksana_real_research | false | 270 | 1.710572 | [-2.245191, 5.542079] | 0.3816 | false |
| richer_research_packet | C3_direct_minus_real_research | direct_llm | ksana_real_research | false | 270 | -0.462075 | [-3.365119, 2.692705] | 0.7486 | false |
| richer_research_packet | C4_real_research_minus_full_gotra | ksana_real_research | full_gotra | true | 270 | -3.041899 | [-8.710421, 2.507802] | 0.2880 | false |
| richer_research_packet | C5_direct_minus_full_gotra | direct_llm | full_gotra | false | 270 | -3.503973 | [-8.625598, 1.653527] | 0.1830 | false |

HAC diagnostics were computed with `aggregation=within_cluster_only`; cluster-level results were recorded for each comparison.

## Primary Metrics And Calibration

| Arm | Scored steps | Direction hit rate | MSE | MAE | Policy A cumulative return pct | Brier direction | Confidence count | Abstain count | Abstain rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 540 | 0.216667 | 158.465560 | 7.756775 | 5.329968 | 0.231134 | 540 | 2 | 0.003704 |
| ksana_formatting_only | 540 | 0.175926 | 161.366654 | 7.921973 | 2.934333 | 0.219700 | 540 | 0 | 0.000000 |
| ksana_real_research | 540 | 0.137037 | 159.253985 | 7.825368 | 3.370018 | 0.220957 | 540 | 39 | 0.072222 |
| full_gotra | 540 | 0.181481 | 162.235013 | 7.895449 | 5.170432 | 0.220943 | 540 | 0 | 0.000000 |

Abstain quality:

- `direct_llm`: abstain realized abs change mean `5.968205`; non-abstain realized abs change mean `7.763737`.
- `ksana_real_research`: abstain realized abs change mean `7.830032`; non-abstain realized abs change mean `7.751408`.
- `ksana_formatting_only` and `full_gotra`: no abstains.

Policy A return is an internal long-only, no-cost comparison metric only; it is not a return claim.

## Product Metrics

| Arm | Evidence coverage | Reasoning auditability | Error attribution quality | Ledger completeness | Claim specificity | Risk disclosure quality | Explanation consistency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 2.262963 | 0.001235 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| ksana_formatting_only | 4.901852 | 0.000741 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| ksana_real_research | 2.562346 | 0.001235 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| full_gotra | 0.499382 | 0.002037 | 0.990741 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

## Feedback Denominators

- `full_gotra_scored_points`: `540`
- `full_gotra_feedback_available_scored_points`: `540`
- `full_gotra_high_quality_feedback_scored_points`: `540`
- `C4_feedback_eligible_paired_points`: `540`
- C4 all-layer paired points: `540`
- C4 `price_only_packet` paired points: `270`
- C4 `richer_research_packet` paired points: `270`

## Provider And Runtime Diagnostics

- `provider_call_status`: `provider HTTP pilot attempted`
- `provider_execution_mode`: `provider_http`
- `schema_pass_count`: `2880`
- `schema_pass_rate`: `1.0`
- `normalization_applied_count`: `0`
- `normalization_failure_count`: `0`
- `provider_temperature_fallback_count`: `0` for all arms
- Per-arm recovered retry counts:
  - `direct_llm`: `2`
  - `ksana_formatting_only`: `2`
  - `ksana_real_research`: `2`
  - `full_gotra`: `1`
- Per-arm max provider attempts: `2`
- Per-arm max provider retry count: `1`
- Per-arm raw content saved count: `0`

## Future-Data And Source Audit

- `future_data_violation_count`: `0`
- `research_source_leak_count`: `0`
- `source_kind_counts`: `synthetic=2160`, `real=0`, `unverified=0`, `price_derived=0`, `unknown=0`
- `synthetic_evidence_count`: `2160`

## Non-Claims

- This does not support an OOS claim.
- This does not support a forward-live claim.
- This does not support a science/public claim.
- This does not support a trading or investment claim.
- This does not merge or supersede PR #9.
- No provider raw response, secret, environment-file content, DB, bundle, paper-trading, Stage8, or Stage9 artifact is included in this commit.

## Remaining Blockers

- H1/H2 are not supported by this formal-lite run under preregistered statistical criteria.
- H3 is mixed: prediction tolerance was satisfied, but product metrics were not uniformly superior versus `direct_llm`.
- Evidence remains limited to formal-lite internal research. OOS/forward-live/science/public/trading layers require separately preregistered work.

## Next Action

Open a dedicated review PR for this formal-lite result branch against `codex/baseline-v3-four-arm-impl-20260619`, keeping PR #9 unmerged and preserving the artifact boundary.
