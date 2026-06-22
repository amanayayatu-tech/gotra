# GOTRA v3.8M Paired Cognitive-Lift Evaluation Readiness Prereg

## Scope

This prereg defines a fixture/local readiness package for future paired cognitive-lift evaluation.
It is not paired evaluation execution, not provider canary execution, not an actual 30D verdict, and not a formal comparative conclusion.

Evidence layer: `engineering_internal_paired_cognitive_lift_evaluation_readiness`.

## Required Sections

The readiness package must include these six sections:

1. `paired_sample_identity_schema`
2. `scoring_execution_prerequisites`
3. `maturity_readiness_blockers`
4. `statistical_eligibility_checklist`
5. `claim_boundary_gate`
6. `future_provider_30d_verdict_authorization_checklist`

## Identity Boundary

Paired identity must cover `paired_sample_id`, ticker, decision date, horizon, prompt hash, input hash, visible data boundary, rubric version, source run id, source summary hash, source artifact hash, and arm identity.

Allowed arms are `ksana_real_research`, `full_gotra`, and `direct_llm_parametric_memory_control`.
`direct_llm_parametric_memory_control` is a historical diagnostic/control arm with parametric-memory boundary; it is not a clean baseline, not a no-future baseline, and not a no-memory baseline.

## Execution Boundary

v3.8M itself must remain fixture/local only:

- `real_calls_count=0`
- `token_usage_total=0`
- `provider_or_backend_called=false`
- `provider_canary_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

No real scoring is executed in this phase.

## Maturity Boundary

Actual 30D readiness remains `DATA_NOT_MATURED`.
`next_check_after=2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false` and `v3_7_actual_verdict_executed=false`.

The package success status is limited to `PAIRED_COGNITIVE_LIFT_EVALUATION_READINESS_READY`.
`cognitive_lift_superiority_verdict_status` must remain `NOT_YET_VERDICT_READY`.

## Future Authorization Boundary

The future provider/30D checklist may record candidate backend metadata:

- `candidate_provider_backend_model=codex_responses_oauth_backend / gpt-5.5`
- `call_cap=X`
- `token_cap=Y`
- `cost_cap=Z`
- `raw_output_boundary=/tmp only`
- `usage_metadata_required=true`
- `authorization_status=NOT_EXECUTABLE_PLACEHOLDER_CAPS`

`X/Y/Z` are placeholders only. They are not concrete budgets and cannot trigger provider execution.
Any future provider canary or actual 30D verdict requires separate user authorization with concrete metadata.

## Claim Boundary

The package can say that future paired-evaluation prerequisites are structured and locally validated.
No paired evaluation was run.
No provider canary was run.
No actual 30D verdict was run.
Formal cognitive-lift superiority remains `NOT_YET_VERDICT_READY`.
It is not an OOS/science/public/trading claim and not investment/trading/action guidance.
