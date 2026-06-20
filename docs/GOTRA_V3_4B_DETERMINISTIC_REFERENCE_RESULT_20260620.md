# GOTRA v3.4b Deterministic Price-Only Reference Result

Date: 2026-06-20

## Scope

Project: GOTRA v3.4b deterministic price-only reference integration.

Repo/root: `/Users/peachy/Documents/gotra`

Base PR: PR #20 `codex/gotra-v3-4-codex-cli-formal-lite-20260620 @ 904bea5`

Branch: `codex/gotra-v3-4b-deterministic-reference-20260620`

Prereg anchor:
`docs/GOTRA_V3_4B_DETERMINISTIC_REFERENCE_PREREG_20260620.md`

Evidence layer reached: local/no-LLM deterministic reference integration and
mock validation only.

Non-claims:
- Not OOS.
- Not forward-live.
- Not science/public proof.
- Not trading or investment advice.
- Not equivalent to Kimi/GLM/DeepSeek provider API runs.

## LLM / Provider Status

No Kimi/GLM/DeepSeek provider API was called.

No Codex CLI backend sampling was run for this v3.4b goal.

The validation command used `--mode mock` only to exercise the existing harness
and summary structure. Codex CLI transcript/hash counts were `0`.

## Implementation Summary

Added a deterministic reference path that:
- generates one `deterministic_price_only_baseline` record per unique scored
  `(ticker, decision_date, horizon)` point;
- writes local reference artifacts under the run directory;
- computes MSE, MAE, direction hit rate, Policy A return, and calibration fields;
- reports future-data audit fields;
- reports both unique count and input-layer mirrored equivalent count;
- does not change four-arm step counts, paired coverage, Codex CLI metadata, or
  C1-C5 definitions.

Summary fields now include:
- `deterministic_price_only_baseline_status`
- `deterministic_price_only_baseline_count`
- `deterministic_price_only_baseline_unique_scored_point_count`
- `deterministic_price_only_baseline_raw_mirrored_count`
- `deterministic_price_only_baseline_metrics`
- `deterministic_price_only_baseline_future_data_violations`
- `deterministic_price_only_baseline_latest_visible_price_date_max`
- `deterministic_price_only_baseline_provider_or_backend_called`
- `clean_historical_reference_status`

## Mock Validation

Run id:
`baseline_v3_4_det_reference_mock_20260620T112640Z`

Terminal status: `MOCK_PASS`

Four-arm harness:
- expected steps: `96`
- actual step files: `96`
- scored step count: `96`
- paired complete points: `18`
- paired coverage: `1.0`
- provider call status: `no real provider HTTP call`
- provider execution mode: `local_mock`
- Codex CLI transcript path count: `0`
- parsed decision hash count: `0`

Deterministic reference:
- status: `REFERENCE_READY`
- clean historical reference status:
  `PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE`
- unique scored count: `9`
- raw mirrored equivalent count: `18`
- future-data violations: `0`
- latest visible price date max: `2024-04-02`
- provider/backend called: `false`
- artifact count: `9`

Reference metrics:
- scored steps: `9`
- direction hit rate: `0.5555555555555556`
- MSE: `150.067558`
- MAE: `9.900762`
- Policy A cumulative return pct: `11.395365`
- Brier score direction: `0.239481`
- abstain rate: `0.0`

Example audit row:
- ticker: `AAPL`
- decision_date: `2024-02-01`
- latest_visible_price_date: `2024-02-01`
- future_rows_excluded: `596`
- llm_used: `false`
- provider_or_backend_called: `false`

## Interpretation Boundary

This resolves PR #20's clean-reference blocker at the engineering/result
structure level: the clean deterministic reference is now present in summary
and local run artifacts, not only as a helper function.

Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline. C1/C3/C5,
MSE, returns, and direction hit metrics involving direct LLM are diagnostics only
and must not be used to prove GOTRA, ksana, or alaya success or failure.

The deterministic reference is a local historical reference. It is not OOS,
forward-live, science/public proof, or trading advice.

## Artifact Boundary

Committed artifacts should include only code, tests, preregistration, and this
result document.

Not committed:
- `data/backtest/runs/*`
- deterministic reference runtime artifacts
- Codex CLI transcripts
- raw provider/API outputs
- `.env*` or secrets
- DB/bundle/tar/zip artifacts
- `data/paper_trading/*`
- Stage8/Stage9 artifacts

## Next Action

Review the v3.4b deterministic reference integration PR. Only after this clean
reference is accepted should a larger v3.4 Codex CLI experiment or a
future-only/forward-live plan be considered.
