# GOTRA v3.6U Historical/Internal Large Regression Verdict

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: historical/internal offline regression evidence only.

This document records a fast-feedback historical/internal route while the 30D
actual forward-live cohort remains immature. It does not run Kimi/GLM/DeepSeek
provider APIs, does not call the Codex CLI backend, does not run formal-lite,
does not execute v3.7, and does not create a forward-live/OOS verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline, and is
not used as the clean baseline for this verdict.

## Source Artifact Audit

Primary source run:

`data/backtest/runs/baseline_v3_4_scaled_reference_internal_20260620T120015Z`

Source summary:

`data/backtest/runs/baseline_v3_4_scaled_reference_internal_20260620T120015Z/summary.json`

Source metadata from the existing deterministic verdict audit:

- Source status: `PROVIDER_PILOT_PASS`
- Backend family in source artifacts: `codex_cli_llm_backend`
- Expected/scored steps: `480 / 480`
- Paired coverage: `1.0`
- Deterministic reference status: `REFERENCE_READY`
- Deterministic reference count: `40`
- Clean historical reference status: `PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE`
- Source future-data violation count: `0`
- Source research source leak count: `0`
- Source feedback source leak count: `0`

The source run artifacts are local/internal artifacts and are not committed by
this stage.

## v3.6U Primary Run

Command:

```bash
uv run python scripts/baseline_v3_deterministic_price_only_verdict.py \
  --run-id deterministic_price_only_vs_full_gotra_verdict_v36u_20260621T034446Z \
  --output-dir /tmp/gotra_v3_6u_v_parallel_feedback_20260621T034446Z/v36u/runs
```

Output summary, not committed:

`/tmp/gotra_v3_6u_v_parallel_feedback_20260621T034446Z/v36u/runs/deterministic_price_only_vs_full_gotra_verdict_v36u_20260621T034446Z/summary.json`

Summary sha256:

`c28fc01cf12e1ce43c0ecaefb8dbfb8cb57363bbc1d33883500b2dd5df8f0283`

Configuration:

- Primary comparison: `deterministic_price_only_baseline` vs `full_gotra`
- Primary `full_gotra` input layer: `richer_research_packet`
- Pairing unit: unique `(ticker, decision_date, horizon_days)`
- Paired count: `40`
- Cluster count: `10` tickers
- Bootstrap reps: `10000`
- Bootstrap seed: `20260621`
- Minimum paired points: `20`
- Minimum clusters: `2`
- Future-data violation count: `0`
- Source audit status: `passed`
- Provider/backend called in this v3.6U run: `false`
- Codex CLI called in this v3.6U run: `false`
- Formal-lite entered in this v3.6U run: `false`

## Primary Metrics

| Metric | deterministic_price_only | full_gotra |
|---|---:|---:|
| MSE | 155.341486 | 99.514081 |
| MAE | 10.078715 | 7.784812 |
| Direction hit rate | 0.400000 | 0.300000 |
| Policy A cumulative return pct | 156.070591 | 109.265837 |

Primary preregistered bootstrap statistic:

| Field | Value |
|---|---:|
| metric | `mse_loss_diff_det_minus_full` |
| mean | 55.827405 |
| CI low | 24.844355 |
| CI high | 91.693795 |
| n | 40 |
| cluster_count | 10 |
| interpretation | positive means `full_gotra` lower MSE |

## Primary Verdict

`FULL_GOTRA_BETTER`

Reason: `mse_ci_excludes_zero_positive`

This is a metric-specific historical/internal conclusion: on the preregistered
MSE criterion, `full_gotra` beat the deterministic price-only reference in this
local historical source run.

It is not a broad superiority claim. Direction hit rate and Policy A cumulative
return did not support the same direction in this run, so the conclusion must
remain MSE-specific and historical/internal.

## Secondary Diagnostic: ksana_real_research vs full_gotra

Secondary output, not committed:

`/tmp/gotra_v3_6u_v_parallel_feedback_20260621T034446Z/v36u/ksana_vs_full_secondary.json`

Summary sha256:

`36f729404f134cdf32601d5f1ebd2e7e9a912ceb35faf064569707d5029ef84c`

Configuration:

- Comparison: `ksana_real_research` vs `full_gotra`
- Input layer: `richer_research_packet`
- Paired count: `40`
- Cluster count: `10`
- Excluded warm-up / non-scored rows: `20` per arm
- Future/source leak blockers: none in scored pairs

| Metric | ksana_real_research | full_gotra |
|---|---:|---:|
| MSE | 92.417199 | 99.514081 |
| MAE | 7.393958 | 7.784812 |
| Direction hit rate | 0.150000 | 0.300000 |
| Policy A cumulative return pct | 61.528747 | 109.265837 |

Cluster bootstrap diagnostics:

| Metric | Mean | CI low | CI high | Direction |
|---|---:|---:|---:|---|
| `mse_loss_diff_ksana_minus_full` | -7.096881 | -14.912847 | 0.182791 | mixed / inconclusive |
| `mae_loss_diff_ksana_minus_full` | -0.390854 | -0.747500 | -0.068354 | lower MAE for `ksana_real_research` |
| `direction_hit_diff_full_minus_ksana` | 0.150000 | 0.075000 | 0.225000 | higher hit rate for `full_gotra` |
| `policy_return_diff_full_minus_ksana` | 1.193427 | 0.339247 | 2.162433 | higher policy return for `full_gotra` |

Secondary interpretation: mixed diagnostics. This secondary comparison does
not justify a single superiority verdict. It is useful for fast feedback and
error analysis only.

## What This Gives Today

Today, GOTRA has one historical/internal fast-feedback conclusion:

- `full_gotra` beats `deterministic_price_only_baseline` on the preregistered
  MSE criterion in the v3.4 scaled/reference source run.
- This conclusion is internal, historical, and metric-specific.
- It cannot be used as a 30D forward-live verdict, OOS evidence,
  science/public proof, or trading/investment advice.

## What This Does Not Give

- It does not mature the v3.5A 30D forward-live cohort.
- It does not allow v3.7.
- It does not make `direct_llm` a clean no-future baseline.
- It does not prove `full_gotra` is better on all metrics.
- It does not prove GOTRA/ksana/alaya superiority in public/science/trading
  terms.

## Next Action

Use this as an internal historical regression signal while continuing the
actual 30D maturity monitor. The separate v3.6V short-horizon cohort plan can
provide faster future-only feedback, but its results must remain a distinct
experiment family and must not be treated as equivalent to 30D outcomes.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6v_short_horizon_cohort_plan.py scripts/baseline_v3_deterministic_price_only_verdict.py
uv run ruff check --no-cache scripts/baseline_v3_6v_short_horizon_cohort_plan.py tests/test_short_horizon_cohort_plan.py scripts/baseline_v3_deterministic_price_only_verdict.py tests/test_deterministic_price_only_verdict.py
uv run pytest -q tests/test_short_horizon_cohort_plan.py tests/test_deterministic_price_only_verdict.py tests/test_forward_live_monitor_ops.py
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused tests: `35 passed`
- Full test suite: `386 passed`
- `git diff --check`: pass
