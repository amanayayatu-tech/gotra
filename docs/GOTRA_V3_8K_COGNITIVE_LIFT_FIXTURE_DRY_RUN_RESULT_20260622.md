# GOTRA v3.8K Cognitive-Lift Fixture Dry-Run Result

## Result

v3.8K adds a deterministic/local cognitive-lift fixture dry-run for the v3.8J rubric/prereg schema.

- `dry_run_status=COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY`
- `evidence_layer=engineering_internal_cognitive_lift_fixture_dry_run`
- `cognitive_lift_candidate_status=FIXTURE_DRY_RUN_ONLY`
- `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false`
- `provider_canary_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `real_calls_count=0`
- `token_usage_total=0`

This result is an engineering fixture/tooling readiness result only. It is not an actual evaluation, not provider canary execution, not an actual 30D verdict, not an OOS/science/public/trading claim, and not investment or trading advice.

## Local Fixture Validation

Local validation wrote only `/tmp` artifacts:

- summary path: `/tmp/gotra_v3_8k_cognitive_lift_fixture_dry_run_local/runs/baseline_v3_8k_cognitive_lift_fixture_dry_run_local_20260622T000000Z/summary.json`
- summary sha256: `5cf914a147d9ddb050322dca76f2726620bdd659a89ba08e834e99f64b4769c7`
- dry-run sha256: `111a951c36d2dd3bcba6fb3ea24ef0ca1023e121b58ae32c269ad9ba71ac6a24`
- fixture records sha256: `1757d3361b04b5ee67a2a1835913127b6a0fc608f21ec04cbe3569f5cfd7d96a`

The fixture contains one synthetic paired sample with `ksana_real_research`, `full_gotra`, and `direct_llm_parametric_memory_control`. The third arm remains a historical diagnostic/control arm with parametric memory boundary; it is not a clean baseline and not a no-future baseline.

## Boundary Status

- schema boundary: clean
- protocol boundary: clean
- provenance boundary: clean
- claim boundary: clean
- artifact boundary: clean
- runtime boundary: clean
- direct-LLM boundary: clean, with `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Validation Results

Local validation completed before PR creation:

- `py_compile`: pass
- `ruff`: pass
- focused v3.8K pytest: `12 passed`
- local v3.8K validation to `/tmp`: `COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY`
- v3.7H claim-boundary regression on PR files: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
- relevant v3.8J/v3.8I/v3.8H/v3.7H/v3.7I/v3.8K regression: `88 passed`
- full pytest: `951 passed`
- `git diff --check`: pass

GitHub CI terminal state and staged artifact/secret/raw scan are recorded in the final PR report.

## Next Safe Task

Recommended next task: `v3.8L evidence-bounded conclusion template`.
