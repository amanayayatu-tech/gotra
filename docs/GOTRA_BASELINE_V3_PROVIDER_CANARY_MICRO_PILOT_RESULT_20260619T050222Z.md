# GOTRA Baseline v3 Provider Canary + Tiny Micro-Pilot Result (2026-06-19T05:02:22Z)

## Scope

This document records only provider/runtime health and tiny smoke evidence for
the Baseline v3 four-arm harness.

Evidence boundary:

```text
local checks: entered
provider/runtime health: entered
tiny micro-pilot smoke evidence: entered
long-run/formal acceptance: not entered
science/public claim: not entered
```

No claim is made about gotra, ksana, alaya, arm superiority, OOS validity,
public/science validity, trading value, or investment value. Directional
metrics are intentionally not interpreted here.

## Context

```text
repo/root: /Users/peachy/Documents/gotra
branch: codex/baseline-v3-four-arm-impl-20260619
head: 89b326f
PR: https://github.com/amanayayatu-tech/gotra/pull/9
provider: kimi
model: Kimi-K2.6
provider_base_url: https://api.sophnet.com/v1/chat/completions
provider_max_tokens: 2000
```

PR #9 pre-run status:

```text
state: OPEN
mergeStateStatus: CLEAN
CI: Python checks SUCCESS
comments/reviews requiring fix: none observed
```

Historical untracked Stage8/Stage9/paper artifacts were present and were left
untouched. No `.env` secret value was read or printed.

## Local Checks

Commands:

```bash
uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run pytest -q tests/test_baseline_v3_four_arm.py
```

Result:

```text
py_compile: pass
ruff: pass
pytest: 15 passed
```

## Provider Canary

Run:

```text
run_id: baseline_v3_four_arm_canary_kimi26_20260619T044109Z
mode: provider-canary
tickers: AAPL
dates: 2024-01-02,2024-02-01,2024-03-01,2024-04-01
input_layer: both
warm_up_dates: 1
provider_concurrency: 1
max_provider_concurrency: 1
```

Summary:

```text
status: PROVIDER_CANARY_PASS
provider_call_status: provider HTTP canary attempted
expected_steps: 32
actual_step_files: 32
scored_step_count: 32
paired_coverage: 1.0
future_data_violations: 0
future_data_violation_count: 0
research_source_leak_count: 0
price_missing_count: 0
provider_error_count: 0
provider_error_rate: 0.0
schema_error_count: 0
json_decode_error_count: 0
schema_contract_error_count: 0
input_echo_error_count: 0
timeout_count: 0
http_429_count: 0
raw_content_saved_count: 0
full_gotra_feedback_available_scored_points: 6
feedback_path_exercised: true
provider_max_tokens: 2000
provider_max_tokens_applied: true
max_provider_concurrency_used: 1
stop_reason:
root_failure:
```

Interpretation:

```text
provider/runtime health: canary path usable for this tiny Kimi-K2.6 grid
formal-lite acceptance: not entered
science/public claim: not entered
```

## Tiny Micro-Pilot

The tiny micro-pilot was run only after the provider canary passed.

Run:

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_20260619T044859Z
mode: provider-pilot
tickers: AAPL,MSFT,NVDA
dates: 2024-01-02,2024-02-01,2024-03-01,2024-04-01
input_layer: both
warm_up_dates: 1
provider_concurrency: 1
max_provider_concurrency: 2
```

Summary:

```text
status: PROVIDER_PILOT_PASS
provider_call_status: provider HTTP pilot attempted
expected_steps: 96
actual_step_files: 96
scored_step_count: 96
paired_coverage: 1.0
future_data_violations: 0
future_data_violation_count: 0
research_source_leak_count: 0
price_missing_count: 0
provider_error_count: 0
provider_error_rate: 0.0
schema_error_count: 0
json_decode_error_count: 0
schema_contract_error_count: 0
input_echo_error_count: 0
timeout_count: 0
http_429_count: 0
raw_content_saved_count: 0
full_gotra_feedback_available_scored_points: 18
feedback_path_exercised: true
provider_max_tokens: 2000
provider_max_tokens_applied: true
max_provider_concurrency_used: 2
stop_reason:
root_failure:
```

Interpretation:

```text
tiny micro-pilot smoke evidence: completed without provider/schema/runtime errors
long-run/formal acceptance: not entered
science/public claim: not entered
```

The script status string `PROVIDER_PILOT_PASS` is treated here only as the
tiny smoke run completing its predeclared provider/runtime gates. It is not a
formal-lite pass and is not a directional result.

## Artifacts

Run artifacts are intentionally excluded from git:

```text
data/backtest/runs/baseline_v3_four_arm_canary_kimi26_20260619T044109Z/
data/backtest/runs/baseline_v3_four_arm_micro_pilot_kimi26_20260619T044859Z/
```

No provider raw error artifacts were saved in either run:

```text
raw_content_saved_count: 0
```

## Next Hardening Items

These are documentation/contract clarity items only. They were not used to
expand the experiment or tune results.

```text
1. Clarify in prereg/docs that direct_llm under richer_research_packet receives
   the richer input layer by design, while still not receiving ksana/alaya
   workflow state.
2. Clarify the word "passed" in bootstrap/statistical summaries so it cannot be
   mistaken for formal acceptance or arm superiority in smoke runs.
3. Add explicit feedback denominator fields in summary, e.g.
   full_gotra_feedback_available_scored_points / full_gotra_scored_points.
```

## Boundary

This result supports:

```text
provider/runtime health: canary and tiny smoke paths usable on Kimi-K2.6
tiny micro-pilot smoke evidence: completed at the fixed tiny scale
```

This result does not support:

```text
FORMAL_LITE_PASS
OOS pass
gotra superiority
ksana superiority
alaya superiority
science/public validation
trading or investment value
```

## Addendum: PR #9 Review Hardening Follow-Up

UTC: 2026-06-19T06:02:04Z

The next hardening items above were addressed in the PR #9 review-fix pass:

```text
direct_llm + richer_research_packet contract: clarified in prereg and prompt policy
bootstrap "passed" semantics: clarified with explicit statistical_test_completed / right_arm_better_significant fields
feedback denominator: added full_gotra_scored_points and C4_feedback_eligible_paired_points
```

The follow-up run is documented in:

```text
docs/GOTRA_BASELINE_V3_PR9_REVIEW_FIX_AND_SCALE_SMOKE_RESULT_20260619T060204Z.md
```

That follow-up canary passed on retry, but the tiny micro-pilot was provider/runtime
blocked by one `ProxyError` and one provider timeout. Medium scale-smoke was not
entered. No directional metric from either document should be interpreted as
gotra/ksana/alaya superiority.
