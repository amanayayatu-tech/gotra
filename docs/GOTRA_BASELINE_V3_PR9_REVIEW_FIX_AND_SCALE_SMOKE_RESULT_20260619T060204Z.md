# GOTRA Baseline v3 PR9 Review Fix and Scale Smoke Result

UTC: 2026-06-19T06:02:04Z

## Scope

This run addressed PR #9 review feedback and reran local/mock/provider smoke
checks. It did not enter formal-lite acceptance, OOS validation, science/public
claims, or trading claims.

## PR #9 Comments Addressed

- `cluster_bootstrap_ci` now requires at least two clusters before completing a
  bootstrap significance test.
- Paired coverage feasibility now uses unattempted scored points, not paired
  deficit.
- Matured feedback history is isolated by `(ticker, input_layer)`.
- `MOCK_PASS` requires positive scored paired coverage.
- Provider decision JSON now rejects string numeric fields and percentage-style
  confidence values.
- HAC summaries are computed within ticker or ticker/input_layer clusters.
- C4/H2 deltas are restricted to feedback-eligible points.
- `full_gotra` `alaya_memory_refs` must match visible `feedback_ref` ids.
- Calibration/Brier and abstain metrics are reported in per-arm metrics.

## Files Changed

- `scripts/baseline_v3_four_arm.py`
- `tests/test_baseline_v3_four_arm.py`
- `gotra/backtest/statistics.py`
- `docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md`
- `docs/GOTRA_BASELINE_V3_PROVIDER_CANARY_MICRO_PILOT_RESULT_20260619T050222Z.md`
- `docs/GOTRA_BASELINE_V3_PR9_REVIEW_FIX_AND_SCALE_SMOKE_RESULT_20260619T060204Z.md`

## Tests Added

- Strict numeric schema rejection for `expected_change_pct` and `confidence`.
- Single-cluster bootstrap insufficient-state test.
- Stable alaya feedback ref validation.
- Zero-scored mock is not `MOCK_PASS`.
- Paired coverage feasibility with attempted-but-failed scored points.
- HAC cluster-only behavior.
- C4 feedback-eligible-only pairing.
- Feedback input-layer isolation in full mock artifacts.
- Calibration and source-kind summary fields.

## Local Checks

```text
uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run pytest -q tests/test_baseline_v3_four_arm.py
21 passed
```

## Fresh Mock

run_id: `baseline_v3_four_arm_mock_pr9_review_fix_20260619T052723Z`

```text
status: MOCK_PASS
expected_steps: 96
actual_step_files: 96
scored_step_count: 96
expected_scored_points: 18
paired_complete_points: 18
paired_coverage: 1.0
provider_call_status: no real provider HTTP call
provider_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
future_data_violations: 0
research_source_leak_count: 0
raw_content_saved_count: 0
full_gotra_scored_points: 18
full_gotra_feedback_available_scored_points: 18
C4_feedback_eligible_paired_points: 18
source_kind_counts.synthetic: 72
```

## Provider Canary

Initial run:

run_id: `baseline_v3_four_arm_canary_kimi26_pr9_review_fix_20260619T052738Z`

```text
status: PROVIDER_CANARY_FAIL
actual_step_files: 16 / 32
provider_error_count: 1
provider_http_error_count: 1
error: provider_http_error / SophNet Kimi request failed: ProxyError
root_failure: provider_http_error/full_gotra/price_only_packet/AAPL/2024-02-01
schema_error_count: 0
input_echo_error_count: 0
http_429_count: 0
timeout_count: 0
raw_content_saved_count: 0
stop_reason: paired coverage no longer feasible
```

Retry after transient provider/runtime error:

run_id: `baseline_v3_four_arm_canary_kimi26_pr9_review_fix_retry1_20260619T053141Z`

```text
status: PROVIDER_CANARY_PASS
expected_steps: 32
actual_step_files: 32
scored_step_count: 32
schema_pass_count: 32
paired_complete_points: 6
paired_coverage: 1.0
provider_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
http_429_count: 0
timeout_count: 0
future_data_violations: 0
research_source_leak_count: 0
raw_content_saved_count: 0
full_gotra_feedback_available_scored_points: 6
C4_feedback_eligible_paired_points: 6
```

## Tiny Micro-Pilot

run_id: `baseline_v3_four_arm_micro_pilot_kimi26_pr9_review_fix_20260619T053903Z`

```text
status: PROVIDER_PILOT_FAIL
expected_steps: 96
actual_step_files: 72
scored_step_count: 70
schema_pass_count: 70
paired_complete_points: 11
paired_coverage: 0.6111111111111112
provider_error_count: 2
provider_http_error_count: 1
timeout_count: 1
schema_error_count: 0
input_echo_error_count: 0
http_429_count: 0
future_data_violations: 0
research_source_leak_count: 0
raw_content_saved_count: 0
max_provider_concurrency_used: 2
stop_reason: paired coverage no longer feasible
root_failure: provider_http_error/direct_llm/richer_research_packet/AAPL/2024-01-02
```

Provider/runtime error details:

```text
1. direct_llm / richer_research_packet / AAPL / 2024-01-02 / warm_up
   error_type: provider_http_error
   error_message: SophNet Kimi request failed: ProxyError
   provider_attempts: 1
   raw_content_saved: no

2. ksana_real_research / richer_research_packet / NVDA / 2024-03-01 / scored
   error_type: provider_timeout
   error_message: SophNet Kimi request timed out
   request_duration_seconds: 620.183081
   request_timeout_seconds: 620.0
   raw_content_saved: no
```

## Medium Scale-Smoke

Not entered.

Reason: tiny micro-pilot did not pass due provider/runtime errors and paired
coverage became no longer feasible. Per goal boundary, scale-smoke must only run
after mock + canary + tiny micro-pilot pass.

## Evidence Layer

```text
local checks: PASS
mock harness smoke: PASS
provider/runtime health: canary PASS on retry; tiny micro-pilot FAIL due provider/runtime errors
tiny micro-pilot smoke evidence: attempted, blocked before full completion
medium provider scale-smoke evidence: not entered
long-run/formal acceptance: not entered
science/public claim: not entered
trading claim: not entered
```

Directional metrics are recorded in run artifacts but intentionally not
interpreted as arm superiority or inferiority.

## Remaining Blockers

- Tiny micro-pilot is provider/runtime blocked by one `ProxyError` and one
  provider timeout.
- Kimi canary is usable on retry, but the larger tiny micro-pilot path was not
  stable enough to justify scale-smoke.
- No schema/parser/input_echo/identity failures were observed in the passing
  canary retry or failed micro-pilot.

## Next Action

Stabilize provider runtime before scale-smoke. Do not enter medium scale-smoke
until tiny micro-pilot completes with provider error counters at 0 and paired
coverage at the required threshold.

## Addendum: PR9 Comment Closure and Runtime Retry 2026-06-19T06:12:25Z

PR #9 inline comments were re-audited against current head `a31743f`. All 9
comments are verified resolved by the current implementation and tests. Seven
comments are stale GitHub threads on old commit
`89b326fe41e2c3f83b7621e96b3d926b3632c765` with `line:null`; two comments still
map to current `a31743f` lines, but current code validates `full_gotra`
`alaya_memory_refs` against visible feedback refs and reports calibration/Brier
and abstain metrics in per-arm summaries.

Local checks were rerun:

```text
py_compile: PASS
ruff: PASS
pytest tests/test_baseline_v3_four_arm.py: 21 passed
git diff --check: PASS
```

Fresh conservative Kimi canary retry was attempted:

```text
run_id: baseline_v3_four_arm_canary_kimi26_runtime_retry_20260619T061200Z
status: PROVIDER_BLOCKED_PRE_HTTP
provider_call_status: no real provider HTTP call
provider_preflight_error: PROVIDER_BLOCKED_PRE_HTTP: SOPHNET_API_KEY=not_set
auth_missing_count: 32
schema_error_count: 0
input_echo_error_count: 0
http_429_count: 0
timeout_count: 0
future_data_violations: 0
research_source_leak_count: 0
```

This addendum extends the previous provider-runtime blocker evidence with a
current local provider-auth preflight blocker. It is not a provider runtime
health pass/fail because no real HTTP call was made. Tiny micro-pilot C1, tiny
micro-pilot C2, and medium scale-smoke were not entered. Formal-lite acceptance,
OOS validation, science/public claims, and trading claims remain not entered.
