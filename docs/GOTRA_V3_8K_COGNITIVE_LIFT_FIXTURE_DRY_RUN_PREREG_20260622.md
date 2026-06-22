# GOTRA v3.8K Cognitive-Lift Fixture Dry-Run Prereg

## Scope

v3.8K is a deterministic/local fixture dry-run for the v3.8J cognitive-lift rubric and prereg schema. It checks synthetic paired-record shape, protocol identity, provenance fields, runtime flags, artifact references, and text-boundary fields.

This is engineering fixture validation only. It is not an actual evaluation, not a provider canary execution, not an actual 30D verdict, not an OOS/science/public/trading claim, and not investment or trading advice.

## Evidence Layer

- `evidence_layer=engineering_internal_cognitive_lift_fixture_dry_run`
- `dry_run_status=COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY` is allowed only when synthetic/local paired records satisfy the fixture protocol.
- `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY` must remain fixed.

## Runtime Boundary

v3.8K itself must keep:

- `real_calls_count=0`
- `token_usage_total=0`
- `provider_or_backend_called=false`
- `provider_canary_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

The actual 30D maturity boundary remains:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`

## Fixture Protocol

The synthetic fixture must include paired records for:

- `ksana_real_research`
- `full_gotra`
- `direct_llm_parametric_memory_control`

The third arm is a historical diagnostic/control arm with parametric memory boundary. It is not a clean baseline, not a no-future baseline, and not a primary superiority comparator.

Each record must include:

- `paired_sample_id`
- prompt/input hashes
- source run id and source hashes
- same visible data boundary
- same horizon/readiness gate
- same scoring rubric version
- per-dimension evidence fields
- per-dimension integer fixture scores

Required rubric dimensions:

- `problem_decomposition`
- `evidence_grounding`
- `provenance_completeness`
- `uncertainty_calibration`
- `overclaim_avoidance`
- `failure_recovery`
- `determinism_stability`
- `actionability`

The dry-run may emit structured fixture-only per-dimension scores. Those scores are not real output scores and must not be summarized as a superiority verdict.

## Blocking Rules

Allowed top-level statuses:

- `COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROTOCOL`
- `BLOCKED_PROVENANCE`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_DIRECT_LLM_BOUNDARY`
- `BLOCKED_METADATA`

The validator must block malformed paired identity, missing dimension evidence, malformed or out-of-range fixture scores, true runtime flags, forbidden artifact references, overclaim wording, and any `direct_llm_parametric_memory_control` wording that treats it as a clean/no-future/no-memory baseline.

## Can Say / Cannot Say

Can say: rubric/tooling can produce structured deterministic fixture validation records.

Cannot say: real-output ranking, external conclusion, action guidance, or any change to `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY`.
