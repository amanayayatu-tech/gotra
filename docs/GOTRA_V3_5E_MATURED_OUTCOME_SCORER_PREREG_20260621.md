# GOTRA v3.5E Matured Outcome Scorer Preregistration

Date: 2026-06-21

## Scope

Evidence layer: matured outcome scorer engineering/local validation only.

This stage adds a local scorer/report generator for already-resolved
forward-live outcome artifacts. It does not call Kimi/GLM/DeepSeek provider APIs,
does not call the Codex CLI backend, does not run formal-lite or OOS, and does
not make science/public, product superiority, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.5E must not use `direct_llm` to prove GOTRA, ksana,
or alaya success or failure.

## Input Contract

The scorer may read:

- v3.5B resolver output directories
- v3.5C scheduler output directories
- v3.5D operating-loop output directories whose summaries link to resolver
  outcome artifacts
- resolved outcome artifact roots

Only records with `schema=gotra.baseline_v3_5b.forward_live_outcome_resolution.v1`
and `outcome_status=RESOLVED` are eligible for scoring.

## Exclusions and Blocks

The scorer must exclude and count:

- `NOT_MATURED` / `NO_MATURED_OUTCOMES`
- `BLOCKED_DATA` / missing price outcomes
- `BLOCKED_SOURCE_FUTURE_DATA`
- records with `source_future_data_violation=true`
- records with missing outcome fields
- records with unknown direction buckets

The scorer must block the report when:

- source/outcome future-data violations are present
- required provenance cannot reverse-link to the source capture artifact

Provenance requires at least source capture run id, source decision id, source
artifact path/ref, resolver run id, and an existing source capture artifact.

## Scoring Metrics

The report is descriptive only. It may compute:

- `scored_outcome_count`
- exclusion counts by reason
- ticker/cluster/date counts
- direction hit rate using the v3/v3.5 `long` / `avoid` / `neutral` bucket
  contract
- MAE/MSE only on rows where `expected_change_pct` is available from the source
  capture decision

If `expected_change_pct` is missing, the row remains eligible for direction-hit
scoring but is counted in `metric_unavailable_count`. The scorer must not
invent predicted returns.

Policy/reference return is not computed in v3.5E. It must be reported as
`POLICY_RETURN_NOT_COMPUTED` until a later preregistered verdict stage.

## Status Semantics

- `SCORED_OUTCOMES_AVAILABLE`: mature resolved outcomes were scored
  descriptively; this is not a winner/verdict.
- `DATA_NOT_MATURED`: no resolved mature outcome exists.
- `DATA_INSUFFICIENT`: resolved/scored sample is below the preregistered minimum.
- `INSUFFICIENT_CLUSTER_COVERAGE`: ticker/cluster count is below the
  preregistered minimum.
- `BLOCKED_PROVENANCE`: reverse lookup to source capture provenance failed.
- `BLOCKED_FUTURE_DATA`: source/outcome future-data contamination was detected.
- `SCORER_FAIL`: invalid inputs or unexpected errors.

Minimum local validation thresholds:

- `min_scored_outcomes=3`
- `min_clusters=2`

These thresholds only govern whether a descriptive scorer report is produced.
They do not authorize an OOS, science/public, trading, or system superiority
claim.

## Acceptance

Local acceptance requires:

- py_compile and ruff pass for the scorer and focused tests
- focused tests cover direction buckets, direction hit rate, MAE/MSE availability,
  immature/blocked/future-contaminated exclusion, provenance blocks,
  data-insufficient states, cluster coverage, run-id collision, and no-provider
  flags
- v3.5B/v3.5C/v3.5D regression tests pass
- full pytest passes if runtime remains reasonable
- local scorer validation writes output only to `/tmp` or ignored paths
- no `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
  transcripts, `.env*`, DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or
  README changes are committed

## Next Stage Boundary

v3.5E does not produce a `full_gotra`, deterministic, or ksana winner/verdict.
Any true verdict must wait for a later v3.6 readiness gate and separate v3.7/v3.8
preregistration after sufficient mature, clean, provenance-complete outcomes
exist.
