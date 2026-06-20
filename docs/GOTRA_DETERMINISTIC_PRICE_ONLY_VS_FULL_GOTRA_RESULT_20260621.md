# GOTRA Deterministic Price-Only vs Full GOTRA Result

Date: 2026-06-21

## Project

- Project: GOTRA deterministic price-only vs full_gotra verdict
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-deterministic-price-only-vs-full-gotra-verdict-20260621`
- Base: `origin/main` at `597bd9b08140907b73bb8641d3fbec0900541be3`

## Evidence Layer

Offline/internal historical deterministic evidence only.

This is not a provider run, not a Codex CLI backend experiment, not a formal-lite run, not OOS, not science/public proof, and not trading or investment advice.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not a clean no-future baseline and is not used in the verdict.

## Data Source Audit

Primary source run:

`data/backtest/runs/baseline_v3_4_scaled_reference_internal_20260620T120015Z`

Source metadata:

| Field | Value |
|---|---:|
| source_status | `PROVIDER_PILOT_PASS` |
| source_backend_name | `codex_cli_llm_backend` |
| source_expected_steps | 480 |
| source_scored_step_count | 480 |
| source_paired_coverage | 1.0 |
| deterministic_reference_status | `REFERENCE_READY` |
| deterministic_reference_count | 40 |
| clean_historical_reference_status | `PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE` |
| source_future_data_violation_count | 0 |
| source_research_source_leak_count | 0 |
| source_feedback_source_leak_count | 0 |

Source summary path:

`data/backtest/runs/baseline_v3_4_scaled_reference_internal_20260620T120015Z/summary.json`

Source summary SHA-256:

`d0962b5d26eb36c718d89d5f9a836a5c2546b67a54125d7aeaf0de56f96dd9f8`

Source audit gate after PR review hardening:

- source status must be clean (`PROVIDER_PILOT_PASS` for this source)
- deterministic reference status must be `REFERENCE_READY`
- source future-data, research leak, and feedback leak counts must all be 0
- any failed source audit reason downgrades the result to `DATA_INSUFFICIENT_FOR_DETERMINISTIC_VERDICT`

No run artifacts are committed in this PR.

## Verdict Run

Run id:

`deterministic_price_only_vs_full_gotra_verdict_reviewfix_20260620T163339Z`

Local summary path, not committed:

`data/backtest/runs/deterministic_price_only_vs_full_gotra_verdict_reviewfix_20260620T163339Z/summary.json`

Configuration:

- comparison: `deterministic_price_only_baseline_vs_full_gotra`
- primary full_gotra input layer: `richer_research_packet`
- pairing unit: one pair per unique `(ticker, decision_date, horizon_days)`
- paired_count: 40
- cluster_count: 10 tickers
- bootstrap reps: 10,000
- bootstrap seed: 20260621
- minimum paired points: 20
- minimum clusters: 2
- future_data_violation_count: 0
- excluded_reason_counts: `{}`
- provider_or_backend_called: `false`
- codex_cli_called: `false`
- formal_lite_entered: `false`
- source_audit_status: `passed`
- duplicate_deterministic_reference_key_count: 0

PR review hardening added these extra guards:

- existing output run ids are blocked with `BLOCKED_RUN_ID_EXISTS`; the CLI exits non-zero and does not overwrite source or verdict artifacts
- duplicate deterministic reference keys cannot inflate paired_count/bootstrap and force `DATA_INSUFFICIENT_FOR_DETERMINISTIC_VERDICT`
- deterministic reference artifacts must be price-only/no-backend records with the deterministic reference schema
- paired scored artifacts must be `arm=full_gotra`, use the primary `richer_research_packet` input layer, and match ticker/date/horizon identity

## Metrics

| Metric | deterministic_price_only | full_gotra |
|---|---:|---:|
| MSE | 155.341486 | 99.514081 |
| MAE | 10.078715 | 7.784812 |
| direction_hit_rate | 0.400000 | 0.300000 |
| Policy A cumulative return pct | 156.070591 | 109.265837 |

Primary clustered MSE statistic:

| Field | Value |
|---|---:|
| metric | `mse_loss_diff_det_minus_full` |
| mean | 55.827405 |
| ci_low | 24.844355 |
| ci_high | 91.693795 |
| n | 40 |
| cluster_count | 10 |
| positive_diff_semantics | positive means full_gotra lower MSE |

Secondary diagnostics:

| Metric | Mean | CI low | CI high | Interpretation |
|---|---:|---:|---:|---|
| `mae_loss_diff_det_minus_full` | 2.293903 | 1.047563 | 3.667604 | full_gotra lower MAE |
| `direction_hit_diff_full_minus_det` | -0.100000 | -0.200000 | 0.000000 | deterministic had higher hit rate in this run |
| `policy_return_diff_full_minus_det` | -1.170119 | -3.220920 | 0.421050 | policy return inconclusive / not favorable to full_gotra |

## Verdict

`FULL_GOTRA_BETTER`

Reason:

`mse_ci_excludes_zero_positive`

This verdict is only the preregistered MSE-based internal deterministic verdict. It does not mean all metrics favored `full_gotra`; direction hit rate and Policy A return did not support the same directional claim.

## Boundary

This result is an internal/offline historical comparison using existing artifacts. It is not OOS, not forward-live matured evidence, not science/public proof, and not trading or investment advice.

The clean baseline in this result is `deterministic_price_only_baseline`, not `direct_llm`.

## Next Action

After PR review/merge, use this as the first deterministic reference verdict in the evidence chain. Stronger claims require future-only/forward-live mature outcomes or a separately preregistered next evidence layer.
