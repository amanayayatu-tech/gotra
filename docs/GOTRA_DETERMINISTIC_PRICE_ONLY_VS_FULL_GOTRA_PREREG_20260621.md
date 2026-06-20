# GOTRA Deterministic Price-Only vs Full GOTRA Prereg

Date: 2026-06-21

## Scope

Goal: produce an offline/internal deterministic verdict comparing `deterministic_price_only_baseline` against `full_gotra` on already-resolved historical artifacts.

Evidence layer: internal/offline historical deterministic evidence only.

This is not a provider run, not a Codex CLI backend experiment, not a formal-lite run, not OOS, not science/public proof, and not trading or investment advice.

Historical `direct_llm` is `direct_llm_parametric_memory_control`, not a clean no-future baseline. This verdict does not use `direct_llm` as evidence for GOTRA/ksana/alaya success or failure.

## Source Data

Primary source:

`data/backtest/runs/baseline_v3_4_scaled_reference_internal_20260620T120015Z`

This source is used only as an existing local artifact. The verdict harness does not call provider APIs, Codex CLI, or any LLM backend. Run artifacts are not committed.

Required source conditions:

- deterministic reference status is `REFERENCE_READY`
- `future_data_violation_count = 0`
- `research_source_leak_count = 0`
- `feedback_source_leak_count = 0`
- full_gotra step artifacts and deterministic reference artifacts have stable provenance paths

If these conditions fail or paired points are insufficient, the result must be `DATA_INSUFFICIENT_FOR_DETERMINISTIC_VERDICT`.

## Deterministic Baseline Rule

Baseline: existing v3.4 `deterministic_price_only_baseline`.

Rules:

- no LLM
- no provider/backend call
- no parameter memory
- decision features use price rows visible at or before `decision_date`
- outcome scoring may use the existing resolved outcome after decision construction
- `future_data_violation` must be false for every included reference record

## Pairing Rule

Primary comparison pairs each deterministic reference record with exactly one `full_gotra` record:

- same ticker
- same decision_date
- same horizon_days
- same resolved outcome (`actual_change_pct` and `actual_direction`)
- `full_gotra` primary input layer: `richer_research_packet`

The primary verdict uses one pair per unique `(ticker, decision_date, horizon_days)` and does not duplicate the deterministic reference across input layers.

Excluded points include:

- missing deterministic or full_gotra artifact
- non-scored records
- warm-up records
- future-data violation
- research/feedback source leak
- missing metrics
- missing provenance
- mismatched outcome

## Metrics

The harness reports:

- paired_count
- ticker cluster_count
- deterministic and full_gotra MSE
- deterministic and full_gotra MAE
- deterministic and full_gotra direction hit rate
- deterministic and full_gotra Policy A cumulative return
- excluded reason counts
- source artifact metadata and source summary hash

## Cluster-Aware Uncertainty

Primary statistic:

`mse_loss_diff_det_minus_full = deterministic_mse - full_gotra_mse`

Positive values mean `full_gotra` has lower MSE on the paired point.

The harness uses ticker-cluster bootstrap:

- bootstrap reps: 10,000
- seed: 20260621
- minimum paired points: 20
- minimum clusters: 2
- 95% CI over clustered paired mean differences

Secondary diagnostics report clustered CIs for:

- `mae_loss_diff_det_minus_full`
- `direction_hit_diff_full_minus_det`
- `policy_return_diff_full_minus_det`

## Verdict Rule

If paired_count or cluster_count is below the preregistered minimum, verdict is:

`DATA_INSUFFICIENT_FOR_DETERMINISTIC_VERDICT`

If primary MSE CI lower bound is above zero:

`FULL_GOTRA_BETTER`

If primary MSE CI upper bound is below zero:

`DETERMINISTIC_BETTER`

Otherwise:

`INCONCLUSIVE`

All four outcomes are valid. Do not fabricate samples or loosen gates to force a conclusion.

## Artifact Boundary

Allowed PR files:

- verdict harness script
- focused tests
- prereg/result docs

Forbidden PR files:

- `data/backtest/runs/**`
- transcripts/raw outputs/provider raw
- `.env*`
- DB/bundle/tar/zip
- `data/paper_trading/**`
- Stage8/Stage9 local artifacts
- README
