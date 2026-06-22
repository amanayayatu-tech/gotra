# GOTRA v3.8J Cognitive-Lift Rubric Prereg Schema

Date: 2026-06-22

## Scope

v3.8J defines a fixture-only deterministic rubric and prereg schema for a future paired cognitive-lift evaluation.

This PR does not run a provider/backend, does not execute a provider canary, does not run an actual 30D verdict path, does not score real outputs, and does not emit a superiority conclusion.

Evidence layer: `engineering_internal_cognitive_lift_rubric_prereg_schema`.

## Rubric Dimensions

The schema requires eight dimensions:

1. `problem_decomposition`
2. `evidence_grounding`
3. `provenance_completeness`
4. `uncertainty_calibration`
5. `overclaim_avoidance`
6. `failure_recovery`
7. `determinism_stability`
8. `actionability`

Each dimension must include:

- description
- integer score range
- required evidence fields
- blocker conditions
- claim-boundary notes
- minimum provenance requirements

## Paired Protocol

Allowed arms are fixed:

- `ksana_real_research`
- `full_gotra`
- `direct_llm_parametric_memory_control`

`direct_llm_parametric_memory_control` is a historical diagnostic/control arm with parametric memory boundary. It is not a clean baseline and is not a primary comparator.

The paired protocol requires:

- matched prompt/input identity
- paired sample id
- same visible data boundary
- same horizon/readiness gate
- same scoring rubric version
- blind or locked scoring metadata
- per-dimension scores
- preregistered aggregate rules
- missing-data handling
- tie/inconclusive handling
- future-data and overclaim block conditions

## Conclusion Boundaries

Three levels are explicitly separated:

- Engineering Connectivity Conclusion: supported by #73 as bounded engineering replay evidence only.
- Cognitive-Lift Candidate Conclusion: v3.8J defines a future evaluation path only.
- Cognitive-Lift Superiority Verdict: `NOT_YET_VERDICT_READY`.

Current readiness boundary:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

## Status Vocabulary

- `COGNITIVE_LIFT_RUBRIC_PREREG_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROTOCOL`
- `BLOCKED_PROVENANCE`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_DIRECT_LLM_BOUNDARY`

This prereg is evaluation readiness only. It is not actual evaluation, not an actual 30D verdict, not provider canary execution, not an OOS/science/public/trading claim, and not investment advice.
