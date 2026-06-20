# GOTRA v3.4b Deterministic Price-Only Reference Preregistration

Date: 2026-06-20

## Scope

Evidence layer: local/no-LLM deterministic reference integration only.

Non-claims:
- Not OOS.
- Not forward-live.
- Not science/public proof.
- Not trading or investment advice.
- Not provider/runtime health.
- Not a Codex CLI backend sampling result.

This v3.4b goal resolves the clean-reference blocker left by PR #20:
`deterministic_price_only_baseline` existed as a tested helper but was not yet
present in the formal-lite summary/result structure.

## Frozen Behavior

No Kimi/GLM/DeepSeek provider API calls are allowed.

No Codex CLI backend sampling is required or expected.

The deterministic reference must:
- call no LLM/backend/provider;
- use only price rows with `date <= decision_date` for decision construction;
- report `future_rows_excluded`;
- score outcomes only after the deterministic decision is constructed, using the
  same outcome mechanics as the existing harness;
- be counted once per unique `(ticker, decision_date, horizon)` scored point by
  default;
- report any input-layer mirrored equivalent count separately;
- not alter four-arm provider/backend step counts, transcript counts, paired
  coverage, C1-C5 definitions, or H1/H2/H3 acceptance semantics.

If a fifth arm would increase implementation risk, the reference should remain a
separate clean historical reference table/metric block.

## Required Summary Fields

The run summary must include:
- `deterministic_price_only_baseline_status`
- `deterministic_price_only_baseline_count`
- `deterministic_price_only_baseline_unique_scored_point_count`
- `deterministic_price_only_baseline_raw_mirrored_count`
- `deterministic_price_only_baseline_metrics`
- `deterministic_price_only_baseline_future_data_violations`
- `deterministic_price_only_baseline_latest_visible_price_date_max`
- `deterministic_price_only_baseline_provider_or_backend_called`
- `clean_historical_reference_status`

Reference artifacts may be written under the local ignored run directory, for
example `data/backtest/runs/<run_id>/deterministic_price_only_baseline/`, but
must not be committed.

## Interpretation Boundary

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. Metrics involving direct LLM are diagnostics only and
must not be used to prove GOTRA, ksana, or alaya success or failure.

The clean historical reference for this layer is
`deterministic_price_only_baseline`. Larger v3.4 Codex CLI or future-only plans
should wait until this reference is visible in summary/result structure.
