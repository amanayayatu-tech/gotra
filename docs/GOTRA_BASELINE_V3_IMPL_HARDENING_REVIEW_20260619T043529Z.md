# GOTRA Baseline v3 Impl Hardening Review (2026-06-19T04:35:29Z)

## Scope

This document records the implementation-layer hardening for Baseline v3
four-arm formal-lite harness.

- evidence layer: `local checks` + `smoke evidence`
- provider/runtime health: not entered
- long-run/formal acceptance: not entered
- science/public claim: not entered
- trading/investment claim: not entered

## Branch / Head

```text
repo/root: /Users/peachy/Documents/gotra
branch: codex/baseline-v3-four-arm-impl-20260619
head before commit: 91e0f0c
stacked PR base: codex/baseline-v2-pilot-evidence-freeze-20260619
```

PR #8 state at preflight:

```text
PR #8: open
title: Freeze Baseline v2 three-arm pilot evidence
head: codex/baseline-v2-pilot-evidence-freeze-20260619
mergeStateStatus: CLEAN
CI: Python checks success
```

## Files Changed

Allowed/staged file set:

```text
scripts/baseline_v3_four_arm.py
tests/test_baseline_v3_four_arm.py
gotra/backtest/statistics.py
docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md
docs/GOTRA_BASELINE_V3_IMPL_RESULT_20260619T042204Z.md
docs/GOTRA_BASELINE_V3_IMPL_HARDENING_REVIEW_20260619T043529Z.md
```

Intentionally not staged/touched:

```text
data/backtest/runs/*
data/paper_trading/*
.env*
provider raw files
SQLite/DB files
bundles/tar/zip
Stage8/Stage8.3/Stage9 artifacts
scripts/stage8*
scripts/stage9*
scripts/baseline_v2_three_arm_pilot.py
tests/test_baseline_v2_three_arm_pilot.py
```

## PR #8 Lessons Absorbed

| Lesson | v3 hardening |
| --- | --- |
| Provider JSON identity can mismatch task | `validate_provider_decision_identity(...)` checks arm/ticker/date/horizon before cache/scoring. |
| Unknown decision JSON keys must not be dropped | `parse_provider_decision(...)` rejects any top-level key outside `DECISION_JSON_ALLOWED_KEYS`. |
| `short` must not be always wrong | Frozen Option A: actual downside (`<= -2%`) counts both `avoid` and `short` as hits. |
| `provider_max_tokens` must affect real provider path | Kimi passes max_tokens to client; GLM/SophNet request body includes `max_tokens`; mock records not applied. |
| `MOCK_PASS` must require real coverage | Requires zero provider/schema/future/leak/price errors, `actual_step_files == expected_steps`, `scored_step_count == expected_steps`, and full paired coverage. |
| Provider canary should not require mature feedback | Provider canary health no longer requires mature alaya feedback; feedback path is separately exposed via `feedback_path_exercised`. |

## Test Coverage Mapping

| Required topic | Test/assertion |
| --- | --- |
| 1. payload boundaries for all four arms | `test_four_arm_payload_boundaries_and_input_layers` |
| 2. richer vs price_only input-layer differences | `test_four_arm_payload_boundaries_and_input_layers` |
| 3. cache_key separation by input_layer/provider_max_tokens/arm | `test_cache_key_contains_input_layer_and_definition_version` |
| 4. strict allowed JSON key rejection | `test_strict_decision_json_rejects_unknown_keys_without_invention` |
| 5. provider decision identity mismatch rejection | `test_provider_decision_identity_mismatch_is_not_scored_or_cached` |
| 6. ref isolation | `test_parse_ref_isolation_normalization_and_input_echo` |
| 7. input_echo detection | `test_parse_ref_isolation_normalization_and_input_echo` |
| 8. conservative normalization/no invented fields | `test_strict_decision_json_rejects_unknown_keys_without_invention` and `test_parse_ref_isolation_normalization_and_input_echo` |
| 9. short/downside scoring rule | `test_short_counts_as_downside_hit` |
| 10. research_source_leak detection | `test_research_source_leak_and_future_data_guards` |
| 11. richer artifact future-data violation | `test_research_source_leak_and_future_data_guards` |
| 12. warm_up written but excluded from stats | `test_mock_run_writes_warm_up_feedback_and_v3_artifacts` and `test_statistics_v3_pairs_by_arm_input_layer_and_segment` |
| 13. matured_feedback no future leak | `test_matured_feedback_filters_future_outcomes` |
| 14. MOCK_PASS fails on price_missing/skipped coverage | `test_mock_pass_fails_when_price_missing_prevents_scored_coverage` |
| 15. nonpositive --step-months rejected | `test_nonpositive_step_months_rejected` |
| 16. provider_max_tokens in GLM body or explicit metadata | `test_glm_provider_max_tokens_is_sent_in_request_body` and mock metadata assertions |
| 17. paired_loss_differences_v3 by arm/input_layer/scored segment | `test_statistics_v3_pairs_by_arm_input_layer_and_segment` |
| 18. cluster_bootstrap_ci deterministic | `test_statistics_v3_pairs_by_arm_input_layer_and_segment` |
| 19. product metric calculation | `test_product_metrics_for_constructed_step` |
| 20. manifest/summary/step include definition/schema/provider tokens/input_layer | `test_mock_run_writes_warm_up_feedback_and_v3_artifacts` |

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run pytest -q tests/test_baseline_v3_four_arm.py
git diff --check
```

Results:

```text
py_compile: pass
ruff: pass
pytest: 15 passed
git diff --check: pass
```

## Mock Run

```text
run_id: baseline_v3_four_arm_mock_hardening_20260619T043506Z
provider_call_status: no real provider HTTP call
```

Summary fields:

```text
status: MOCK_PASS
expected_steps: 96
actual_step_files: 96
scored_step_count: 96
paired_coverage: 1.0
future_data_violations: 0
future_data_violation_count: 0
research_source_leak_count: 0
price_missing_count: 0
provider_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
synthetic_evidence_count: 72
provider_call_status: no real provider HTTP call
provider_max_tokens_applied: False
feedback_path_exercised: True
```

Artifacts are under:

```text
data/backtest/runs/baseline_v3_four_arm_mock_hardening_20260619T043506Z/
```

Run artifacts are intentionally excluded from git.

## Evidence Boundary

This hardening supports only implementation-layer review:

```text
local checks: pass
smoke evidence: mock harness run only
provider/runtime health: not entered
long-run/formal acceptance: not entered
science/public claim: not entered
```

No claim is made about gotra superiority, ksana superiority, alaya superiority,
OOS validity, public scientific validity, or trading/investment value.

## Next Action

Open a clean review PR for implementation-layer review. Provider canary,
concurrency ramp, and formal-lite run remain separate explicitly authorized
goals after PR review.
