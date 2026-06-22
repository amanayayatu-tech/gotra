# GOTRA v3.8J Cognitive-Lift Rubric Prereg Schema Result

Date: 2026-06-22

## Result

v3.8J adds a deterministic local rubric/prereg schema validator:

- script: `scripts/baseline_v3_8j_cognitive_lift_rubric_prereg_schema.py`
- focused tests: `tests/test_v3_8j_cognitive_lift_rubric_prereg_schema.py`
- evidence layer: `engineering_internal_cognitive_lift_rubric_prereg_schema`
- status: `COGNITIVE_LIFT_RUBRIC_PREREG_READY`

v3.8J itself records:

- `provider_or_backend_called=false`
- `provider_canary_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_8j_real_calls_count=0`
- `v3_8j_token_usage_total=0`

## Rubric Summary

Dimensions:

- `problem_decomposition`
- `evidence_grounding`
- `provenance_completeness`
- `uncertainty_calibration`
- `overclaim_avoidance`
- `failure_recovery`
- `determinism_stability`
- `actionability`

Allowed arms:

- `ksana_real_research`
- `full_gotra`
- `direct_llm_parametric_memory_control`

`direct_llm_interpretation=direct_llm_parametric_memory_control` and `direct_llm_clean_baseline=false`.

## Local Validation Summary

Local validation wrote only to `/tmp`:

- summary path: `/tmp/gotra_v3_8j_cognitive_lift_rubric_prereg/runs/baseline_v3_8j_cognitive_lift_rubric_prereg_local_20260622/summary.json`
- manifest path: `/tmp/gotra_v3_8j_cognitive_lift_rubric_prereg/runs/baseline_v3_8j_cognitive_lift_rubric_prereg_local_20260622/manifest.json`
- summary sha256: `57fdfff3298a25301b0b988b0becc99e53f34003d4ee9c718a4a4d04ea6c8413`
- `rubric_prereg_sha256`: `a16fa1ffd64897f84b48381e3e38c95362096402c3c17eeb4cc89b577a34f4f2`

## Boundary Summary

Current 30D state remains:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

Can say:

- rubric/prereg schema for future cognitive-lift paired evaluation is available for fixture-level validation

Cannot say:

- not cognitive-lift superiority proof
- not a GOTRA/ksana/full_gotra comparative result against the diagnostic/control arm
- `direct_llm_parametric_memory_control` is not a clean baseline
- actual 30D verdict is not executable
- provider canary was not executed
- not investment or trading advice

This result is internal engineering evidence only. It is not actual evaluation, not an actual 30D verdict, not a provider canary run, not an OOS/science/public/trading claim, and not investment advice.
