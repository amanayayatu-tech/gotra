# GOTRA Baseline v3 Formal-Lite Provider Result

Generated: 2026-06-19T15:00:47Z

## Project

- Project: GOTRA Baseline v3 Formal-Lite Provider Run
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/baseline-v3-formal-lite-run-20260619`
- Initial result commit: `05a896c Record Baseline v3 formal-lite provider result`
- Layer 1 evidence-freeze fix: this commit
- Upstream PR: https://github.com/amanayayatu-tech/gotra/pull/9
- Base branch for this result PR: `codex/baseline-v3-four-arm-impl-20260619`
- Prereg anchor: `docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md`
- Run plan: `docs/GOTRA_BASELINE_V3_FORMAL_LITE_RUN_PLAN_20260619.md`
- Run plan commit: `3e500d0 Preregister Baseline v3 formal-lite run plan`
- Audit-chain rechecked: `git merge-base --is-ancestor 3e500d0 05a896c` returned `0`; the frozen run plan commit is an ancestor of the initial result commit, and the run plan timestamp precedes the provider result commit.

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
- `uv run pytest -q tests/test_baseline_v3_four_arm.py` -> PASS (`28 passed`)
- `git diff --check` -> PASS before provider run
- Layer 1 offline recompute command: `uv run python scripts/baseline_v3_four_arm.py --mode recompute --from-run data/backtest/runs/baseline_v3_four_arm_formal_lite_kimi26_min30x12_20260619T092412Z --no-network`

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

Run-level provider status: `PROVIDER_PILOT_PASS`.

Canonical completion classification: `FORMAL_LITE_INCONCLUSIVE`.

Rationale: the provider run completed validly and met the frozen engineering gates (`2880/2880`, `paired_coverage = 1.0`, `future_data_violation_count = 0`, `provider_error_rate = 0.0`). The directional research layer is inconclusive because H1 real research value was not tested with real evidence, H2 true independent alaya feedback was not tested, and the measured C1-C5 bootstrap CIs do not establish the preregistered H1/H2/H3 positive conditions.

## H1/H2/H3 Research Verdict

Evidence-source caveat: all richer-packet artifacts in this run are synthetic (`source_kind_counts: synthetic=2160, real=0, unverified=0`). H1 is therefore an engineering-path validation, not a real-research test.

- H1, ksana research value: NOT TESTED in this run for real research value. The `richer_research_packet` research artifacts were 100% synthetic, so this run cannot evaluate real multi-source ksana research value. The measured C3-on-richer result (`ksana_real_research` vs `direct_llm`: mean_loss_diff `-0.462075`, bootstrap 95% CI `[-3.365119, 2.692705]`, bootstrap p=`0.7486`, HAC status `completed` at cluster level) shows only that synthetic research artifacts produced no measurable MSE reduction; it is neither support nor refutation of the real-research hypothesis.
- H2, alaya feedback value: TRUE INDEPENDENT ALAYA FEEDBACK NOT TESTED in this run. Under the current self-feedback definition, C4 was computed on `540` feedback-available paired points and was not significant (`mean_loss_diff=-2.981027`, bootstrap 95% CI `[-7.904557, 1.668763]`, p=`0.2200`). However, the feedback is full_gotra's self-generated prior prediction/outcome history, not independent external mature alaya knowledge. Therefore this is not a fair negative test of true mature alaya feedback value; it should be treated as `DATA_INSUFFICIENT_FOR_H2_FOR_TRUE_ALAYA_FEEDBACK`.
- H3, content product value: mixed / not fully established. After offline recomputation with bounded `evidence_coverage`, prediction tolerance versus `ksana_real_research` was satisfied (`full_gotra` MSE +`1.87187%`, direction hit rate +`4.444444` pp), but product metrics remain mixed versus `direct_llm`: stronger `error_attribution_quality` and `reasoning_auditability`, equal ledger/claim/risk/explanation fields, and lower bounded `evidence_coverage`.

## C1-C5 Summary

Convention: `mean_loss_diff = left_arm MSE - right_arm MSE`. Negative values favor the left arm; positive values favor the right arm. This table is an internal statistical record only.

| Bucket | Comparison | Left | Right | Feedback eligible only | Paired points | Bootstrap mean diff | Bootstrap 95% CI | Bootstrap p | Right arm better significant | HAC status | HAC mean diff | HAC clusters | HAC z range | HAC p range | HAC p<0.05 clusters |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- | ---: | ---: | --- | --- | ---: |
| all | C1_direct_minus_formatting | direct_llm | ksana_formatting_only | false | 540 | -2.901093 | [-4.949623, -0.904668] | 0.0052 | false | completed | -2.901093 | 60/60 | [-2.729067, 1.707887] | [0.006351, 1.000000] | 2 |
| all | C2_formatting_minus_real_research | ksana_formatting_only | ksana_real_research | false | 540 | 2.112668 | [-0.173986, 4.442294] | 0.0680 | false | completed | 2.112668 | 60/60 | [-2.670891, 2.197430] | [0.007565, 1.000000] | 3 |
| all | C3_direct_minus_real_research | direct_llm | ksana_real_research | false | 540 | -0.788425 | [-3.232351, 1.873034] | 0.5272 | false | completed | -0.788425 | 60/60 | [-2.480938, 1.924401] | [0.013104, 0.987948] | 2 |
| all | C4_real_research_minus_full_gotra | ksana_real_research | full_gotra | true | 540 | -2.981027 | [-7.904557, 1.668763] | 0.2200 | false | completed | -2.981027 | 60/60 | [-1.908964, 2.293953] | [0.021793, 0.977106] | 1 |
| all | C5_direct_minus_full_gotra | direct_llm | full_gotra | false | 540 | -3.769452 | [-7.026786, -0.360152] | 0.0300 | false | completed | -3.769452 | 60/60 | [-2.723887, 3.267222] | [0.001086, 0.977922] | 4 |
| price_only_packet | C1_direct_minus_formatting | direct_llm | ksana_formatting_only | false | 270 | -3.629540 | [-8.007369, 0.431022] | 0.0782 | false | completed | -3.629540 | 30/30 | [-2.001595, 1.707887] | [0.045328, 0.999390] | 1 |
| price_only_packet | C2_formatting_minus_real_research | ksana_formatting_only | ksana_real_research | false | 270 | 2.514765 | [0.016609, 5.441571] | 0.0480 | true | completed | 2.514765 | 30/30 | [-1.326615, 2.044820] | [0.040873, 1.000000] | 1 |
| price_only_packet | C3_direct_minus_real_research | direct_llm | ksana_real_research | false | 270 | -1.114775 | [-5.693407, 2.992562] | 0.6250 | false | completed | -1.114775 | 30/30 | [-2.282509, 1.924401] | [0.022459, 0.987948] | 1 |
| price_only_packet | C4_real_research_minus_full_gotra | ksana_real_research | full_gotra | true | 270 | -2.920156 | [-9.030959, 2.677239] | 0.3318 | false | completed | -2.920156 | 30/30 | [-1.699047, 2.293953] | [0.021793, 0.977106] | 1 |
| price_only_packet | C5_direct_minus_full_gotra | direct_llm | full_gotra | false | 270 | -4.034931 | [-8.880034, 0.642100] | 0.0938 | false | completed | -4.034931 | 30/30 | [-1.987276, 3.267222] | [0.001086, 0.973504] | 2 |
| richer_research_packet | C1_direct_minus_formatting | direct_llm | ksana_formatting_only | false | 270 | -2.172646 | [-5.305965, 1.901447] | 0.2456 | false | completed | -2.172646 | 30/30 | [-2.729067, 1.337845] | [0.006351, 1.000000] | 1 |
| richer_research_packet | C2_formatting_minus_real_research | ksana_formatting_only | ksana_real_research | false | 270 | 1.710572 | [-2.245191, 5.542079] | 0.3816 | false | completed | 1.710572 | 30/30 | [-2.670891, 2.197430] | [0.007565, 1.000000] | 2 |
| richer_research_packet | C3_direct_minus_real_research | direct_llm | ksana_real_research | false | 270 | -0.462075 | [-3.365119, 2.692705] | 0.7486 | false | completed | -0.462075 | 30/30 | [-2.480938, 1.769001] | [0.013104, 0.914079] | 1 |
| richer_research_packet | C4_real_research_minus_full_gotra | ksana_real_research | full_gotra | true | 270 | -3.041899 | [-8.710421, 2.507802] | 0.2880 | false | completed | -3.041899 | 30/30 | [-1.908964, 1.814155] | [0.056267, 0.962504] | 0 |
| richer_research_packet | C5_direct_minus_full_gotra | direct_llm | full_gotra | false | 270 | -3.503973 | [-8.625598, 1.653527] | 0.1830 | false | completed | -3.503973 | 30/30 | [-2.723887, 2.510139] | [0.006452, 0.977922] | 2 |

HAC diagnostics were computed with `aggregation=within_cluster_only`; there is no single aggregate HAC z/p field in the run summary, so the table reports the cluster-level z/p ranges, completed cluster counts, and status rather than inventing an aggregate p-value.

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

These product metrics were recomputed offline from the existing run artifacts with bounded `evidence_coverage`. The denominator is the available evidence names in `decision_inputs`; duplicate cited refs are deduplicated and unavailable refs are counted as invalid rather than improving coverage.

| Arm | Evidence coverage | Valid refs | Available refs | Invalid refs | Duplicate refs | Reasoning auditability | Error attribution quality | Ledger completeness | Claim specificity | Risk disclosure quality | Explanation consistency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 0.983951 | 1.951852 | 2.000000 | 1.337037 | 0.000000 | 0.001235 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| ksana_formatting_only | 0.988889 | 0.988889 | 1.000000 | 3.912963 | 0.000000 | 0.000741 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| ksana_real_research | 0.896296 | 1.751852 | 2.000000 | 2.072222 | 0.000000 | 0.001235 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| full_gotra | 0.104063 | 0.792593 | 8.777778 | 3.185185 | 0.000000 | 0.002037 | 0.990741 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

## Feedback Denominators

- `full_gotra_scored_points`: `540`
- `full_gotra_feedback_available_scored_points`: `540`
- `full_gotra_high_quality_feedback_scored_points`: `540`
- `C4_feedback_eligible_paired_points`: `540`
- C4 all-layer paired points: `540`
- C4 `price_only_packet` paired points: `270`
- C4 `richer_research_packet` paired points: `270`

Interpretation caveat: the current implementation's feedback is full_gotra self-generated prediction/outcome history keyed by `(ticker, input_layer)`. It is not independent, external, mature alaya knowledge. The `540/540` eligibility is implementation-consistent because `warm_up_dates=3` and the monthly grid mean the first scored wave already sees three matured self-feedback records, but this should not be read as true independent alaya feedback coverage.

Offline feedback distribution for `full_gotra` scored points:

| Scored date | Input layer | Points | feedback_used_count min | feedback_used_count max | feedback_age_days_max min | feedback_age_days_max max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2024-04-02 | price_only_packet | 30 | 3 | 3 | 61 | 61 |
| 2024-04-02 | richer_research_packet | 30 | 3 | 3 | 61 | 61 |
| 2024-05-02 | price_only_packet | 30 | 4 | 4 | 91 | 91 |
| 2024-05-02 | richer_research_packet | 30 | 4 | 4 | 91 | 91 |
| 2024-06-03 | price_only_packet | 30 | 5 | 5 | 123 | 123 |
| 2024-06-03 | richer_research_packet | 30 | 5 | 5 | 123 | 123 |
| 2024-07-02 | price_only_packet | 30 | 5 | 5 | 152 | 152 |
| 2024-07-02 | richer_research_packet | 30 | 5 | 5 | 152 | 152 |
| 2024-08-01 | price_only_packet | 30 | 7 | 7 | 182 | 182 |
| 2024-08-01 | richer_research_packet | 30 | 7 | 7 | 182 | 182 |
| 2024-09-03 | price_only_packet | 30 | 8 | 8 | 215 | 215 |
| 2024-09-03 | richer_research_packet | 30 | 8 | 8 | 215 | 215 |
| 2024-10-02 | price_only_packet | 30 | 8 | 8 | 244 | 244 |
| 2024-10-02 | richer_research_packet | 30 | 8 | 8 | 244 | 244 |
| 2024-11-01 | price_only_packet | 30 | 10 | 10 | 274 | 274 |
| 2024-11-01 | richer_research_packet | 30 | 10 | 10 | 274 | 274 |
| 2024-12-02 | price_only_packet | 30 | 11 | 11 | 305 | 305 |
| 2024-12-02 | richer_research_packet | 30 | 11 | 11 | 305 | 305 |

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

- H1 real ksana research value remains not tested because richer evidence was synthetic-only.
- H2 true independent mature alaya feedback value remains not tested because this run used full_gotra self-feedback history.
- H3 remains mixed: prediction tolerance was satisfied, but bounded product metrics were not uniformly superior versus `direct_llm`.
- Evidence remains limited to formal-lite internal research. OOS/forward-live/science/public/trading layers require separately preregistered work.

## Next Action

Review this PR as a Layer 1 evidence-freeze fix only. Do not enter Layer 2 v3.1 real-evidence work or any new provider run from this result branch without a separate preregistered goal.
