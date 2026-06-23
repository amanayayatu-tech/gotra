# GOTRA v3.8R Rubric-Anchored Reasoning-Quality Prereg

## Scope

This prereg defines the first local-only schema validator for rubric-anchored reasoning-quality evaluation.

Evidence layer: `local_checks_rubric_anchored_reasoning_quality_prereg_schema`.

Success status is limited to `RUBRIC_ANCHORED_REASONING_QUALITY_PREREG_READY`.

## Preserved Verdict Fields

- `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `direct_llm_clean_baseline=false`

## Local-Only Runtime Boundary

- `provider_or_backend_called_for_prereg=false`
- `provider_canary_executed_for_prereg=false`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `real_calls_count=0`
- `token_usage_total=0`
- `raw_output_boundary=/tmp only`
- `no_raw_repo=true`

## Locked Inputs

The prereg package requires:

- `rubric_sha256`
- `source_artifact_sha256`
- `probe_rule_sha256`
- `rubric_lock_status=LOCKED_AT_T0`
- `scoring_mode=paired_blind_locked_rubric`

## Direct-Control Boundary

`direct_llm_parametric_memory_control` is retained only as a diagnostic/control arm. It is not eligible as the only clean comparator for a bounded claim, and it is not a clean baseline.

## Eligibility Boundary

Effect fields are forbidden before all statistical eligibility flags are true. Raw work-unit counts cannot be used as independent N; `effective_independent_pair_count` must be derived through the preregistered clustered policy.

## Claim Boundary

Allowed conclusion for this phase: local prereg/schema readiness for later rubric-anchored scoring work.

Permanent non-claims:

- `not_market_edge_verdict`
- `not_realized_pnl_verdict`
- `not_actual_30d_verdict`
- `not_forward_live_outcome_superiority`
- `not_public_science_proof`
- `not_trading_or_investment_advice`
- `direct_llm_is_parametric_memory_control_only`
