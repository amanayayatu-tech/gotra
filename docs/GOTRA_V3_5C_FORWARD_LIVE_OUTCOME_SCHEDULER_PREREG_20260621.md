# GOTRA v3.5C Forward-Live Outcome Scheduler Prereg

Date: 2026-06-21

## Scope

v3.5C adds a local maturity/scoring scheduler for already captured v3.5A
forward-live decisions.

Evidence layer: forward-live scheduler engineering/local validation only.

This stage does not call Kimi/GLM/DeepSeek provider APIs, does not call the
Codex CLI backend, does not run formal-lite, and does not make OOS,
science/public proof, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.5C does not use it to interpret any success/failure
claim.

## Goal

The scheduler scans a v3.5A capture run, determines whether each decision is
mature, and delegates outcome resolution to the v3.5B resolver logic.

Required statuses:

- `NOT_MATURED`: horizon has not matured; no realized outcome fields are
  populated.
- `BLOCKED_DATA`: horizon is mature, but required price data is unavailable
  under the preregistered window/availability rules.
- `BLOCKED_SOURCE_FUTURE_DATA`: source capture artifact is contaminated by
  decision-side future data and must not be scored.
- `RESOLVED`: horizon is mature and required decision/outcome prices are
  available under the v3.5B no-future-data rule.

Already resolved decisions are idempotent: a later scheduler run must detect the
existing resolved `source_decision_id`, count it as
`duplicate_or_existing_outcome_count`, and skip rewriting or duplicating the
outcome.

## Inputs

The scheduler supports:

- `--capture-run-dir`
- `--scheduler-run-id`
- `--as-of-timestamp-utc`
- `--price-dir`
- `--output-dir`
- `--outcome-window-days`
- `--allow-overwrite`

`scheduler_run_id` must start with:

`baseline_v3_5c_outcome_scheduler_`

## Summary Schema

The scheduler summary must include:

- `scheduler_run_id`
- `source_capture_run_id`
- `source_capture_path`
- `resolver_run_ids`
- `scanned_decision_count`
- `not_matured_count`
- `resolved_count`
- `blocked_data_count`
- `blocked_future_data_count`
- `duplicate_or_existing_outcome_count`
- `future_data_violation_count`
- `provenance_link_count`
- `started_at`
- `completed_at`
- `evidence_layer = forward-live scheduler engineering/local validation only`

## Future-Data Guard

The scheduler inherits v3.5B resolver rules:

- It must not resolve if `as_of` is before `horizon_end_date`.
- Daily close row D is visible only at D+1 `00:00:00Z` or later.
- Missing price data remains `BLOCKED_DATA`; prices are never fabricated.
- Outcome prices beyond the allowed outcome window are not used.
- Source capture future-data contamination is blocked and counted.

`OUTCOME_SCHEDULER_PASS` requires at least one scanned decision, no scheduler
errors, zero source/future-data violations, and valid provenance links for any
newly written resolver records. `BLOCKED_DATA` and `NOT_MATURED` are valid
engineering statuses and do not by themselves imply an OOS/trading verdict.

## Provenance

Each newly written resolver outcome artifact must preserve reverse lookup to:

- `scheduler_run_id`
- `resolver_run_id`
- `source_decision_id`
- `source_decision_artifact`
- source capture run id
- source artifact path/ref
- price source path and row dates used

The existing audit event chain is not updated in v3.5C. This scheduler writes
local run artifacts under ignored output directories, not Judge/Gate knowledge
transition events. Audit-chain wiring can be added later if scheduler execution
becomes part of the live Judge/Gate control plane.

## Non-Claims

v3.5C is a scheduler/maturity engineering layer. It does not prove outcome
performance, OOS validity, science/public claims, product superiority, trading
value, or investment value. Only after future decisions mature and are scored
under preregistered rules can later evidence layers be evaluated.
