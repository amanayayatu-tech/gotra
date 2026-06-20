# GOTRA v3.6 Forward-Live Verdict Readiness Gate Preregistration

Date: 2026-06-21

## Scope

Evidence layer: readiness-gate engineering/local validation only.

v3.6 decides whether the forward-live artifact chain is ready for a later
verdict stage. It does not compute a `full_gotra`, deterministic, ksana, alaya,
OOS, science/public, product superiority, trading, or investment verdict.

This stage does not call Kimi/GLM/DeepSeek provider APIs, does not call the Codex
CLI backend, does not run formal-lite, and does not start a forward-live
experiment. It only reads local artifacts and writes ignored/local readiness
outputs.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.6 must not use it to prove GOTRA, ksana, or alaya
success or failure.

## Inputs

The readiness gate may read:

- v3.5A deterministic price-only reference capture artifacts
- v3.5B resolved outcome artifacts
- v3.5C scheduler outcome/provenance artifacts
- v3.5D operating-loop summaries with provenance links
- v3.5E matured outcome scorer summaries

The clean pairing target is one deterministic price-only reference and one
`full_gotra` resolved outcome for the same `(ticker, decision_date, horizon)`.
The primary `full_gotra` input layer is `richer_research_packet`.

## Required Checks

The gate must check and report:

- matured resolved outcome count
- scored/usable clean `full_gotra` outcome count
- ticker/cluster count
- decision date coverage
- deterministic reference availability
- `full_gotra` availability
- deterministic/full pair coverage
- source/capture/outcome/scorer future-data violation count
- provenance completeness from source capture to scheduler/resolver outcome and
  v3.5E scorer summary
- bootstrap/HAC eligibility flags only; no bootstrap/HAC verdict is computed

The v3.5E scorer prerequisite is satisfied only by a successful
`SCORED_OUTCOMES_AVAILABLE` summary with enough scored outcomes for the v3.6
minimum, zero future-data blockers, zero provenance failures, and clean execution
boundary fields: `provider_or_backend_called=false`, `codex_cli_called=false`,
`formal_lite_entered=false`, and
`direct_llm_interpretation=direct_llm_parametric_memory_control`. A stale,
blocked, `DATA_NOT_MATURED`, `DATA_INSUFFICIENT`, or boundary-contaminated
scorer summary cannot make the readiness gate ready.

Deterministic references must be local price-only artifacts with:

- `schema=gotra.baseline_v3_5a.deterministic_price_only_capture_reference.v1`
- `baseline=deterministic_price_only_baseline`
- `llm_used=false`
- `provider_or_backend_called=false`
- `future_data_violation=false`

Clean `full_gotra` outcomes must be `RESOLVED`, use the primary input layer, and
reverse-link to a valid source capture. The loaded source capture is rechecked
with the v3.5B future-data guard. The source prediction direction must be one of
the v3/v3.5 scoreable buckets: `long`, `avoid`, or `neutral`.

Readiness must block ambiguous provenance. Duplicate `full_gotra` pairing keys
and duplicate deterministic reference keys for the same
`(ticker, decision_date, horizon)` are not silently deduplicated. The
outcome-level `scheduler_run_id` must match the nested
`provenance.scheduler_run_id`.

## Status Semantics

- `READY_FOR_FORWARD_LIVE_VERDICT`: readiness conditions are satisfied. This is
  not a verdict.
- `DATA_NOT_MATURED`: no matured resolved outcomes exist.
- `DATA_INSUFFICIENT`: mature/paired/date sample is below preregistered
  readiness thresholds.
- `INSUFFICIENT_CLUSTER_COVERAGE`: ticker/cluster coverage is below threshold.
- `BLOCKED_PROVENANCE`: required source/scheduler/resolver/scorer provenance is
  incomplete.
- `BLOCKED_FUTURE_DATA`: source/capture/outcome/scorer future-data contamination
  is detected.
- `BLOCKED_PAIRING`: deterministic reference and `full_gotra` cannot be paired.

Default local thresholds:

- `min_matured_outcomes=3`
- `min_paired_points=3`
- `min_clusters=2`
- `min_dates=2`

`bootstrap_eligible` requires paired points and cluster coverage. `hac_eligible`
requires paired points and date coverage. These are eligibility flags only.

## Acceptance

Local acceptance requires:

- py_compile and Ruff pass for the v3.6 script and tests
- focused tests cover not-matured, insufficient samples, insufficient clusters,
  missing deterministic reference, missing `full_gotra`, future-data blocker,
  missing provenance, successful scorer-summary prerequisite, unscorable source
  decisions, duplicate deterministic reference keys, duplicate `full_gotra`
  keys, scheduler provenance mismatch, scorer summary boundary flags,
  clean-ready fixture, direct_llm caveat, and run-id collision
- v3.5B/v3.5C/v3.5D/v3.5E regression tests pass
- full pytest passes if runtime remains reasonable
- a local readiness validation run writes output only to `/tmp` or ignored paths
- no `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
  transcripts, `.env*`, DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or
  README changes are committed

## Next Stage Boundary

v3.6 can only unblock planning for v3.7. A later v3.7/v3.8 stage must be
separately preregistered before any deterministic-reference-vs-`full_gotra`
verdict, bootstrap/HAC analysis, or public-facing interpretation.
