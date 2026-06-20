# GOTRA Baseline v3.2 Evidence + Feedback Substrate Prereg

## Scope

Baseline v3.2 is an implementation substrate layer for evidence provenance and
true independent mature feedback eligibility. This goal is limited to
local/mock implementation evidence.

This document does not authorize provider runs, canaries, micro-pilots,
scale-smokes, formal-lite provider runs, OOS, forward-live, paper trading, or
science/public claims.

## Evidence Layer

- Evidence layer: local checks + mock implementation evidence only.
- Provider/runtime health: not entered.
- Formal-lite acceptance: not entered.
- OOS/forward-live: not entered.
- Science/public claim: not entered.
- Trading/investment advice: not entered.

## Preserved v3.1 Result Boundary

PR #12 remains an internal formal-lite evidence freeze:

- Run-level status: `PROVIDER_PILOT_PASS`.
- Completion classification: `FORMAL_LITE_INCONCLUSIVE`.
- H1 remains inconclusive because the richer evidence path used committed local
  fixture evidence, not a production-grade multi-source research pipeline.
- H2 remains `DATA_INSUFFICIENT_FOR_H2_TRUE_INDEPENDENT_FEEDBACK` because
  `true_independent_feedback_eligible_points=0`.

v3.2 must not rewrite PR #12 metrics, thresholds, run artifacts, or historical
conclusions.

## H1 Substrate Target

`richer_research_packet` must be able to carry auditable `real` and
`unverified` research artifacts with provenance fields, including at minimum:

- `source_kind`
- `source_family`
- `source_url` or `source_id`
- `captured_at`
- `availability_date`
- `ticker`
- `decision_date_max`
- `text`
- provenance checksum or hash when feasible

The loader must reject future-leaking or malformed artifacts and continue to
report source-kind and rejection diagnostics. If production multi-source
ingestion is not implemented, the result must be labeled schema/provenance
substrate evidence, not production research value.

## H2 Substrate Target

`full_gotra` must be able to receive eligible true independent mature feedback
artifacts. Self-feedback, same-date feedback, current-step feedback, malformed
feedback, synthetic feedback, and future outcome feedback must not count as true
independent mature feedback.

## Strict H2 Eligibility Definition

A feedback artifact may count toward
`true_independent_feedback_eligible_points` only if all conditions below hold:

1. `feedback_source_kind` is independent outcome-derived feedback, such as
   `outcome_feedback` or `realized_error_feedback`.
2. `feedback_source_kind` is not `self_feedback` and not
   `synthetic_feedback`.
3. The feedback is derived from a prior decision whose
   `source_horizon_end_date <= current_decision_date`.
4. `availability_date <= current_decision_date`.
5. The feedback is not generated from the current step, current ticker/date/arm
   prediction, or same-date future outcome.
6. The feedback carries auditable provenance fields such as `source_run_id`,
   `source_step_id`, `source_decision_date`, `source_horizon_end_date`,
   `actual_return`, and `prior_prediction`.
7. The current scored point has at least two prior mature waves.
8. The current scored point has at least three eligible feedback artifacts.

Any future-leaking or malformed feedback artifact must be rejected and counted.
Rejected artifacts must not enter prompts or eligibility counts.

## Prompt Separation

- `full_gotra` may receive eligible feedback artifacts.
- `ksana_real_research` may receive research artifacts but no alaya feedback.
- `ksana_formatting_only` must not receive research content or feedback content
  beyond the formatting scaffold.
- `direct_llm` remains the direct baseline. If a richer input layer includes
  raw research context by harness design, that behavior must be documented and
  symmetric rather than hidden.
- No arm may receive rejected or future feedback artifacts.

## Required Diagnostics

Mock and later provider summaries must expose:

- `feedback_source_kind_counts`
- `rejected_feedback_artifact_count`
- `rejected_feedback_future_data_count`
- `feedback_source_leak_count`
- `strict_feedback_eligible_points`
- `true_independent_feedback_eligible_points`
- `h2_data_status`
- `h2_data_insufficient_reason`
- per-date or per-wave feedback eligibility diagnostics where practical

## Graduation Criteria

Before any future provider/formal-lite goal, v3.2 must show local/mock evidence
that:

- local deterministic checks pass;
- mock run does not call a provider;
- future-data violations are zero for accepted artifacts;
- research source leak count is zero;
- feedback source leak count is zero;
- rejected future feedback artifacts are counted;
- at least one later scored point has
  `true_independent_feedback_eligible_points > 0`;
- earlier waves remain data-insufficient under the strict H2 definition;
- H2 status distinguishes eligible evidence from data insufficiency and never
  treats self-feedback as true independent mature alaya feedback.

## Non-Claims

This document and its local/mock proof do not claim gotra, ksana, or alaya
superiority. They do not support OOS, forward-live, science/public, trading, or
investment conclusions.
