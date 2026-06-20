# GOTRA Baseline v3.1 Formal-Lite Provider Result

## Project

- Project: GOTRA Baseline v3.1 Formal-Lite Provider Run
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/baseline-v3-1-formal-lite-run-20260620`
- PR: https://github.com/amanayayatu-tech/gotra/pull/12
- Evidence layer: formal-lite internal research evidence only
- Non-claims: not OOS, not forward-live, not science/public evidence, not trading or investment advice

## Anchors

- v3.1 prereg anchor: `docs/GOTRA_BASELINE_V3_1_REAL_EVIDENCE_PREREG_2026-06-19.md`
- Prereg implementation anchor commit: `4679211`
- Run plan: `docs/GOTRA_BASELINE_V3_1_FORMAL_LITE_RUN_PLAN_2026-06-20.md`
- Run plan commit: `9e0538d`
- Audit chain: `4679211` is an ancestor of `9e0538d`; this result document is committed after the frozen run plan.

## Frozen Config

- Provider: `kimi`
- Model: `Kimi-K2.6`
- Base URL: `https://api.sophnet.com/v1/chat/completions`
- Provider max tokens: `2000`
- Research artifacts path: `tests/fixtures/baseline_v3_1_research_artifacts.json`
- Arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- Input layer: `both`
- Warm-up dates: `3`
- Horizon days: `30`
- Timeout: request/max `900` seconds
- Timeout retries: `1`; retry backoff: `30` seconds
- Provider concurrency: `1`; max provider concurrency: `2`
- Frozen grid: 30 tickers x 12 dates x 4 arms x 2 input layers = 2880 provider steps
- Expected scored paired groups: 30 tickers x 9 scored dates x 2 input layers = 540

## Local Checks

All local deterministic gates passed before provider formal-lite:

- `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py`: PASS
- `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py`: PASS
- `uv run pytest -q tests/test_baseline_v3_four_arm.py`: PASS, `32 passed`
- `git diff --check`: PASS

## Mock Gate

- Run ID: `baseline_v3_1_formal_lite_mock_20260619T161100Z`
- Status: `MOCK_PASS`
- Provider HTTP: no real provider call
- Expected/actual steps: `2880/2880`
- Scored step count: `2880`
- Paired complete points: `540`
- Paired coverage: `1.0`
- Future-data violations: `0`
- Research source leak count: `0`
- Rejected future-data research artifacts: `36`
- Source kind counts: `real=36`, `unverified=1116`, `synthetic=36`, `price_derived=0`, `unknown=0`
- Strict feedback eligible points: `0`
- True independent feedback eligible points: `0`
- H2 data status: `DATA_INSUFFICIENT_FOR_H2_TRUE_INDEPENDENT_FEEDBACK`

## Canary Gate

- Run ID: `baseline_v3_1_formal_lite_canary_kimi26_20260619T161239Z`
- Status: `PROVIDER_CANARY_PASS`
- Expected/actual steps: `96/96`
- Paired coverage: `1.0`
- Provider errors: `0`
- Schema/input_echo/429/timeout/future-data/raw errors: all `0`
- Recovered retryable provider errors: `3`
- Source kind counts: `real=12`, `unverified=48`, `synthetic=12`, `price_derived=0`, `unknown=0`
- Strict feedback eligible points: `0`
- True independent feedback eligible points: `0`
- H2 data status: `DATA_INSUFFICIENT_FOR_H2_TRUE_INDEPENDENT_FEEDBACK`

## Formal-Lite Run

- Run ID: `baseline_v3_1_formal_lite_kimi26_min30x12_20260619T163236Z`
- Run dir: `data/backtest/runs/baseline_v3_1_formal_lite_kimi26_min30x12_20260619T163236Z`
- Run-level provider status: `PROVIDER_PILOT_PASS`
- Expected/actual steps: `2880/2880`
- Scored step count: `2880`
- Expected scored points: `540`
- Paired complete points: `540`
- Paired coverage: `1.0`
- Provider error rate: `0.0`
- Provider/schema/input_echo/429/timeout/future-data/raw final errors: all `0`
- Recovered retryable provider errors: `7`
- Unrecovered provider timeout/http errors: `0/0`
- Circuit breaker: not triggered

## Completion Classification

`FORMAL_LITE_INCONCLUSIVE`.

The engineering/provider run completed validly as `PROVIDER_PILOT_PASS`, with full paired coverage and no final provider/schema/input_echo/429/timeout/future-data/raw failures. The formal-lite research classification is inconclusive because H2 true independent mature feedback eligibility is `0`, so one key hypothesis is data-insufficient under the v3.1 preregistered strict feedback rule.

## Research Verdicts

- H1, ksana real-evidence research value: inconclusive internal/formal-lite evidence. The richer packet included local fixture `real` and `unverified` evidence paths, but this is still committed fixture evidence, not a production multi-source research pipeline. On richer packets, C3 `direct_minus_real_research` MSE delta was `1.573541` with bootstrap p=`0.3578`, not statistically significant.
- H2, true independent mature alaya feedback value: `DATA_INSUFFICIENT_FOR_H2_TRUE_INDEPENDENT_FEEDBACK`. `true_independent_feedback_eligible_points=0`; current self-feedback availability must not be interpreted as a fair test of true mature alaya feedback.
- H3, product metrics: computed and bounded separately from prediction metrics. Product diagnostics are internal product-surface evidence only and do not support OOS/science/public/trading claims.

## C1-C5 Summary

Loss diff convention: `left_mse_minus_right_mse`. Negative means left arm lower MSE; positive means right arm lower MSE. `right_sig` is the preregistered right-arm-better significant flag from clustered bootstrap. HAC is reported as within-cluster-only diagnostics; aggregate `passed` is intentionally `null` with reason `cluster_level_results_only`.

| Layer | Comparison | Paired | Feedback-only | Mean diff | CI low | CI high | Bootstrap p | Winner | right_sig | HAC n | HAC clusters | HAC status |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- |
| all | C1 direct-formatting | 540 | false | -0.834960 | -3.348846 | 1.545323 | 0.5030 | direct_llm | false | 540 | 60 | cluster_level_results_only |
| all | C2 formatting-real_research | 540 | false | 0.728821 | -1.576297 | 3.083781 | 0.5434 | ksana_real_research | false | 540 | 60 | cluster_level_results_only |
| all | C3 direct-real_research | 540 | false | -0.106138 | -2.609342 | 2.435809 | 0.9184 | direct_llm | false | 540 | 60 | cluster_level_results_only |
| all | C4 real_research-full_gotra | 540 | true | -1.782776 | -5.645012 | 2.198440 | 0.3724 | ksana_real_research | false | 540 | 60 | cluster_level_results_only |
| all | C5 direct-full_gotra | 540 | false | -1.888914 | -6.091322 | 2.379795 | 0.3784 | direct_llm | false | 540 | 60 | cluster_level_results_only |
| price_only_packet | C1 direct-formatting | 270 | false | -1.053909 | -3.717690 | 1.482079 | 0.4200 | direct_llm | false | 270 | 30 | cluster_level_results_only |
| price_only_packet | C2 formatting-real_research | 270 | false | -0.731910 | -5.954397 | 4.062812 | 0.7914 | ksana_formatting_only | false | 270 | 30 | cluster_level_results_only |
| price_only_packet | C3 direct-real_research | 270 | false | -1.785818 | -6.354847 | 2.178045 | 0.4236 | direct_llm | false | 270 | 30 | cluster_level_results_only |
| price_only_packet | C4 real_research-full_gotra | 270 | true | -2.485844 | -8.486091 | 3.540081 | 0.4196 | ksana_real_research | false | 270 | 30 | cluster_level_results_only |
| price_only_packet | C5 direct-full_gotra | 270 | false | -4.271663 | -9.231451 | 0.365931 | 0.0716 | direct_llm | false | 270 | 30 | cluster_level_results_only |
| richer_research_packet | C1 direct-formatting | 270 | false | -0.616011 | -4.342457 | 2.939706 | 0.7408 | direct_llm | false | 270 | 30 | cluster_level_results_only |
| richer_research_packet | C2 formatting-real_research | 270 | false | 2.189552 | -2.068170 | 6.481709 | 0.3152 | ksana_real_research | false | 270 | 30 | cluster_level_results_only |
| richer_research_packet | C3 direct-real_research | 270 | false | 1.573541 | -1.751496 | 4.960886 | 0.3578 | ksana_real_research | false | 270 | 30 | cluster_level_results_only |
| richer_research_packet | C4 real_research-full_gotra | 270 | true | -1.079707 | -4.658423 | 2.870650 | 0.5580 | ksana_real_research | false | 270 | 30 | cluster_level_results_only |
| richer_research_packet | C5 direct-full_gotra | 270 | false | 0.493834 | -4.281020 | 5.561821 | 0.8534 | full_gotra | false | 270 | 30 | cluster_level_results_only |

## Prediction Metrics

These are internal prediction diagnostics only, not trading evidence.

| Arm | Scored | MSE | MAE | Direction hit rate | Policy A cumulative return pct | Brier direction | Abstain count | Abstain rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 540 | 159.485752 | 7.805459 | 0.214815 | 4.814720 | 0.232924 | 0 | 0.000000 |
| ksana_formatting_only | 540 | 160.320712 | 7.835293 | 0.183333 | 4.088337 | 0.220417 | 0 | 0.000000 |
| ksana_real_research | 540 | 159.591891 | 7.817733 | 0.135185 | 3.246012 | 0.225138 | 5 | 0.009259 |
| full_gotra | 540 | 161.374667 | 7.920522 | 0.168519 | 5.621171 | 0.218710 | 1 | 0.001852 |

## Product Metrics

Evidence coverage is bounded in `[0,1]`; invalid refs remain auditable and are not counted as valid coverage.

| Arm | Scored | Evidence coverage | Available refs avg | Valid refs avg | Invalid refs avg | Duplicate refs avg | Ledger completeness | Reasoning auditability | Error attribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 540 | 0.922037 | 1.550000 | 1.379630 | 1.664815 | 0.000000 | 1.000000 | 0.000000 | 0.000000 |
| ksana_formatting_only | 540 | 0.987037 | 1.000000 | 0.987037 | 3.898148 | 0.000000 | 1.000000 | 0.004074 | 0.000000 |
| ksana_real_research | 540 | 0.901852 | 1.550000 | 1.394444 | 2.148148 | 0.000000 | 1.000000 | 0.001543 | 0.000000 |
| full_gotra | 540 | 0.142314 | 8.327778 | 1.103704 | 2.944444 | 0.000000 | 1.000000 | 0.003287 | 0.987037 |

## Source And Feedback Diagnostics

- `source_kind_counts`: `real=36`, `unverified=1116`, `synthetic=36`, `price_derived=0`, `unknown=0`
- Rejected research artifacts: `36`
- Rejected future-data research artifacts: `36`
- Research source leak count: `0`
- Future-data violations: `0`
- Self-feedback available points: `540`
- Strict feedback eligible points: `0`
- True independent feedback eligible points: `0`
- H2 data insufficient reason: `no_real_or_unverified_feedback_source_kind`

The run exercises the v3.1 real/unverified research artifact path via committed local fixture evidence. It does not establish production-grade multi-source research ingestion. The full_gotra feedback path is exercised with self-feedback availability, but true independent mature feedback remains absent under the strict v3.1 definition.

## Provider Runtime Diagnostics

| Arm | Recovered retryable errors | Last retryable types | Max attempts | Max retries | Max duration seconds | P95 duration seconds | Raw saved | Input echo errors |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 3 | provider_http_error | 2 | 1 | 44.685137 | 11.029807 | 0 | 0 |
| ksana_formatting_only | 2 | TimeoutException; provider_http_error | 2 | 1 | 938.996336 | 11.169490 | 0 | 0 |
| ksana_real_research | 1 | provider_http_error | 2 | 1 | 43.989519 | 11.635303 | 0 | 0 |
| full_gotra | 1 | provider_http_error | 2 | 1 | 47.429080 | 15.545191 | 0 | 0 |

Final unrecovered provider timeout/http errors were `0/0`. The long ksana_formatting_only max duration reflects a recovered timeout path under the frozen one-retry policy, not an unrecovered terminal failure.

## Remaining Blockers

- H2 remains data-insufficient for true independent mature alaya feedback: `true_independent_feedback_eligible_points=0`.
- The research evidence path uses a committed local fixture. This validates schema/provenance/future-data gating and provider prompt/runtime behavior, but it is not a production multi-source real research pipeline.
- Directional arm metrics are internal formal-lite diagnostics only and must not be promoted to OOS/science/public/trading claims.

## Next Action

Review PR #12 as a formal-lite internal evidence-freeze PR. Do not enter provider reruns, OOS, forward-live, science/public, or trading interpretation without a separate preregistered goal.
