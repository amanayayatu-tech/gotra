# GOTRA Baseline v3.1 Real-Evidence Implementation Prereg

Date: 2026-06-19

## Scope

Baseline v3.1 is a real-evidence implementation layer for the existing Baseline v3 four-arm harness. This document freezes the local/mock implementation target before any provider run.

This layer is not OOS evidence, not forward-live evidence, not a science/public claim, not a trading claim, and not investment advice. It authorizes local checks, focused tests, and a no-network mock implementation check only.

Provider canary, micro-pilot, scale-smoke, formal-lite provider runs, OOS, and forward-live are out of scope until separately authorized.

## Inherited Arms And Inputs

The v3.1 harness keeps the four Baseline v3 arms:

- `direct_llm`
- `ksana_formatting_only`
- `ksana_real_research`
- `full_gotra`

The v3.1 harness keeps both input layers:

- `price_only_packet`
- `richer_research_packet`

No arm or input layer may be hidden or removed to improve a directional result.

## H1 Real Ksana Research Value

H1 is testable only when `richer_research_packet` includes time-bounded, traceable research artifacts whose `source_kind` includes `real` or `unverified`.

Synthetic-only richer packets do not test real ksana research value. They may be used for engineering-path validation but must be labeled synthetic-only and must not be treated as real information gain.

## H2 True Independent Mature Alaya Feedback

H2 is testable only on `strict_feedback_eligible` points. Self-generated full_gotra prediction history is not independent mature alaya knowledge and must not be used to claim true alaya feedback value.

If the strict eligible subset is too small or has no real/unverified feedback source, H2 must be labeled `DATA_INSUFFICIENT_FOR_H2`, not a negative alaya verdict.

## H3 Product And Prediction Split

Product metrics and prediction metrics remain separate tracks.

Product value can support only internal content-platform auditability claims. Product metrics do not support OOS, science/public, trading, or investment claims.

Prediction metrics remain direction hit rate, MSE, MAE, Policy A comparison, calibration, and abstain-quality metrics. Policy A is a no-cost long-only diagnostic only.

## Strict Feedback Eligibility

For a point to be `strict_feedback_eligible`, all conditions must hold:

1. The candidate arm is `full_gotra` and the step is in the scored segment.
2. Visible mature feedback count is at least `3`.
3. At least one feedback item has `age_days >= horizon_days` where `horizon_days = 30`.
4. Feedback comes from at least `2` different prior `decision_date` values, treating each prior date as an independent wave.
5. At least one feedback item has `source_kind` in `{real, unverified}`.

If a local/mock fixture has no real/unverified feedback source, the implementation must report `DATA_INSUFFICIENT_FOR_H2` diagnostics rather than treating self-feedback as true independent alaya evidence.

## Real Evidence Artifact Schema

Each research artifact must include:

- `ticker`
- `source_name`
- `source_url_or_id`
- `publish_timestamp`
- `availability_date`
- `source_kind`: one of `real`, `unverified`, or `synthetic`
- `retrieval_method`
- `evidence_ref`
- `summary`
- optional `decision_date_scope`

The harness may derive internal fields such as `name`, `kind`, and `source` from these fields, but the original provenance must remain available in step artifacts and summary diagnostics.

## Future-Data Gate

For a given `decision_date`, an artifact may enter the packet only when:

```text
availability_date <= decision_date
```

Artifacts must be rejected and counted when they contain future-leak fields, including:

- `actual_change_pct`
- `future_return`
- `outcome`
- `realized_after_decision`
- `window_end_price`
- `future_price`

Rejected artifacts must not enter the prompt packet or source-kind counts for accepted evidence.

## Product Metric Legal Domain

`evidence_coverage` must remain a bounded fraction in `[0, 1]`.

The numerator is the deduplicated set of decision-cited refs that exist in the available evidence set. Duplicate cited refs and unavailable refs must be counted in diagnostics and must not increase coverage.

## Local/Mock Implementation Graduation Gate

This v3.1 implementation layer may be considered locally ready for review only if all are true:

- local checks pass;
- focused tests pass;
- no-network mock implementation check passes;
- accepted artifacts have `future_data_violations = 0`;
- rejected leak artifacts are counted and excluded;
- `research_source_leak_count = 0` for accepted prompt packets;
- `source_kind_counts` can include `real` or `unverified` from local fixtures;
- strict feedback eligibility diagnostics are present and correct;
- H2 reports data insufficiency when true independent feedback is absent;
- `evidence_coverage` is bounded and carries invalid/duplicate ref diagnostics;
- no provider HTTP path is entered.

## Explicit Non-Claims

This prereg does not authorize:

- provider/runtime health claims;
- formal-lite acceptance;
- OOS claims;
- forward-live claims;
- science/public claims;
- trading or investment claims.

The next step after this layer is Judge/Orchestrator review of the implementation and mock evidence.
