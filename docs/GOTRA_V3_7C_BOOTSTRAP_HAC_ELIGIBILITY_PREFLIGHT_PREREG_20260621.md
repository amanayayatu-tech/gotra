# GOTRA v3.7C Bootstrap/HAC Eligibility Preflight Prereg

Date: 2026-06-21

## Evidence Layer

This stage is `engineering/local v3.7 bootstrap HAC eligibility preflight`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- The preflight must not emit a deterministic / `full_gotra` / ksana winner.
- The preflight must not compute bootstrap/HAC estimates, p-values, confidence
  intervals, or winner claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Goal

Define and validate the future v3.7 bootstrap/HAC eligibility preflight using
local/synthetic fixture rows only. `V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY` means the
statistical eligibility checker is runnable at fixture level. It does not mean
the actual v3.7 verdict can execute.

Actual 30D readiness remains `DATA_NOT_MATURED`, so
`v3_7_actual_verdict_executable=false`.

## Fixture Contract

Each fixture row must represent one mature, resolved synthetic observation for
one arm and include:

- `fixture_kind` or `kind`: `deterministic_reference`,
  `deterministic_price_only`, `price_only_reference`, or `full_gotra`
- `ticker`
- `decision_date`
- `horizon_days`
- `outcome_status=RESOLVED` or `SCORED`
- `source_run_id`
- `source_artifact_path`
- `source_artifact_sha256`
- `provenance.source_run_id`
- `provenance.source_artifact_path`
- `provenance.source_artifact_sha256`
- `future_data_violation_count=0`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `evidence_layer=engineering/local v3.7 bootstrap HAC eligibility preflight`

The preflight pairs deterministic reference rows with `full_gotra` rows by
`(ticker, decision_date, horizon_days)`.

`horizon_days` must be exactly `30`; short-horizon canary rows are not valid
inputs for this v3.7 30D eligibility preflight.

Top-level source fields do not satisfy the nested provenance contract. The
nested `provenance.source_run_id`, `provenance.source_artifact_path`, and
`provenance.source_artifact_sha256` fields must be present and must match the
top-level source fields.

Path-only manifest entries such as `{"path": "fixture.json"}` are supported
and are resolved relative to the manifest file. Forbidden paths are blocked
before loading.

## Eligibility Checks

The preflight checks:

- sample count
- paired clean count
- ticker cluster count
- date cluster count
- date coverage count
- ticker coverage count
- deterministic reference availability
- `full_gotra` availability
- paired coverage consistency
- bootstrap eligibility
- HAC eligibility
- cluster eligibility
- future-data violation count
- provenance blocker count
- schema blocker count

It does not compute bootstrap/HAC estimates and does not output p-values,
confidence intervals, or a winner.

## Blockers

Allowed statuses:

- `V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY`
- `DATA_INSUFFICIENT`
- `INSUFFICIENT_SAMPLE_COUNT`
- `INSUFFICIENT_CLUSTER_COVERAGE`
- `INSUFFICIENT_DATE_COVERAGE`
- `INSUFFICIENT_TICKER_COVERAGE`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_FUTURE_DATA`
- `BLOCKED_PAIRING`
- `BLOCKED_OVERCLAIM`

The preflight must block:

- missing or malformed fixture schema
- negative or non-integer count fields
- missing or mismatched provenance
- forbidden source artifact paths
- missing `future_data_violation_count`
- future-data violations
- non-30D horizons
- duplicate pair keys
- missing deterministic reference or `full_gotra` pair members
- insufficient sample, paired-clean, date, ticker, or cluster coverage
- winner/verdict/OOS/science/public/trading overclaim wording

The CLI exits `0` only for `V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY`. All other
statuses, including data-insufficient and insufficient-coverage statuses, exit
non-zero for shell/CI callers.

## Digest Convention

The final `summary.json` digest is recorded in `manifest.json` as
`summary_sha256`; the summary does not store a self-invalidating digest field.

## Next Action

If this stage merges later, the safe follow-up is continued actual maturity
monitoring or additional fixture/report hardening. A real v3.7 deterministic
reference vs `full_gotra` verdict requires actual readiness
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
