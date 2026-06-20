# GOTRA Baseline v3 Provider Runtime Timeout Hardening Result

UTC: 2026-06-19T09:03:47Z

## Scope

This document records provider/runtime timeout hardening and the gated smoke
ladder for Baseline v3 four-arm harness on PR #9.

Evidence boundary:

- local checks
- provider/runtime health
- tiny C2 smoke evidence
- medium scale-smoke evidence

Out of scope:

- formal-lite acceptance
- OOS acceptance
- science/public claim
- trading claim
- directional interpretation of gotra/ksana/alaya/direct_llm metrics

## Previous Blocker

Previous C2 run:

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_contract_hardened_c2_20260619T072227Z
status: PROVIDER_PILOT_FAIL
root_failure: provider_timeout/ksana_real_research/richer_research_packet/NVDA/2024-02-01
expected_steps: 96
actual_step_files: 48
schema_pass_count: 47
schema_contract_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
future_data_violation_count: 0
provider_error_count: 1
provider_http_error_count: 0
timeout_count: 1
http_429_count: 0
max_provider_concurrency_used: 2
stop_reason: paired coverage no longer feasible
```

Step-level diagnosis:

```text
status: provider_error
error_type: provider_timeout
provider_error_class: TimeoutException
request_timeout_seconds: 900.0
provider_attempts: 1
provider_retry_count: 0
provider_raw_content_path: ""
```

No provider raw response artifact was present for the timeout step.

## Implementation

Minimal provider runtime hardening was applied to
`scripts/baseline_v3_four_arm.py`.

Implementation summary:

- Kimi provider requests now use the existing bounded retry knobs:
  `timeout_retries` and `timeout_retry_backoff_seconds`.
- Retryable runtime failures are limited to provider timeouts, provider HTTP
  500/502/503/504, and transient proxy/connect/read/remote protocol/network
  errors.
- HTTP 429 is not retried by this path.
- Schema contract errors, input echo errors, future-data violations, invalid
  provider JSON/content, and price/data errors remain non-retryable.
- Failed retry attempts do not write scored steps and do not populate success
  cache entries.
- Successful recovered steps record `provider_attempts`,
  `provider_retry_count`, and `last_retryable_error_type`.
- Summary diagnostics now expose
  `retryable_provider_error_recovered_count`,
  `unrecovered_provider_timeout_count`, and
  `unrecovered_provider_http_error_count`.

The schema guard was not relaxed.

## Validation

Local checks:

```text
uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run pytest -q tests/test_baseline_v3_four_arm.py
26 passed in 0.66s

git diff --check
PASS
```

Test coverage added:

- retryable Kimi timeout can recover with one bounded retry and records attempt
  metadata
- schema contract and input echo errors are not retried into scored output
- failed runtime retry is not scored and is not written to success cache
- summary/request diagnostics record recovered retry metadata

## Fresh C2 Rerun

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_runtime_retry_c2_20260619T075718Z
provider: kimi
provider_model: Kimi-K2.6
provider_base_url: https://api.sophnet.com/v1/chat/completions
provider_max_tokens: 2000
provider_concurrency: 1
max_provider_concurrency: 2
input_layer: both
tickers: AAPL,MSFT,NVDA
dates: 2024-01-02,2024-02-01,2024-03-01,2024-04-01
warm_up_dates: 1
request_timeout_seconds: 900
status: PROVIDER_PILOT_PASS
expected_steps: 96
actual_step_files: 96
schema_pass_count: 96
scored_step_count: 96
paired_complete_points: 18
paired_coverage: 1.0
schema_contract_error_count: 0
schema_error_count: 0
json_decode_error_count: 0
input_echo_error_count: 0
future_data_violation_count: 0
provider_error_count: 0
provider_http_error_count: 0
timeout_count: 0
http_429_count: 0
retryable_provider_error_recovered_count: 0
unrecovered_provider_timeout_count: 0
unrecovered_provider_http_error_count: 0
raw_content_saved_count: 0
max_provider_concurrency_used: 2
```

## Scale-Smoke

Scale-smoke was entered only after the fresh C2 rerun passed.

```text
run_id: baseline_v3_four_arm_scale_smoke_kimi26_runtime_retry_10x6_20260619T080822Z
provider: kimi
provider_model: Kimi-K2.6
provider_base_url: https://api.sophnet.com/v1/chat/completions
provider_max_tokens: 2000
provider_concurrency: 1
max_provider_concurrency: 2
input_layer: both
tickers: AAPL,MSFT,NVDA,TSM,0700.HK,1211.HK,1810.HK,3690.HK,6060.HK,9988.HK
dates: 2024-01-02,2024-02-01,2024-03-01,2024-04-01,2024-05-01,2024-06-03
warm_up_dates: 2
status: PROVIDER_PILOT_PASS
expected_steps: 480
actual_step_files: 480
schema_pass_count: 480
scored_step_count: 480
paired_complete_points: 80
paired_coverage: 1.0
schema_contract_error_count: 0
schema_error_count: 0
json_decode_error_count: 0
input_echo_error_count: 0
future_data_violation_count: 0
provider_error_count: 0
provider_http_error_count: 0
timeout_count: 0
http_429_count: 0
retryable_provider_error_recovered_count: 2
unrecovered_provider_timeout_count: 0
unrecovered_provider_http_error_count: 0
raw_content_saved_count: 0
max_provider_concurrency_used: 2
```

Recovered retry metadata in scale-smoke:

```text
full_gotra: retryable_provider_error_recovered_count=1, last_retryable_error_types=["provider_http_error"]
ksana_real_research: retryable_provider_error_recovered_count=1, last_retryable_error_types=["provider_http_error"]
direct_llm: retryable_provider_error_recovered_count=0
ksana_formatting_only: retryable_provider_error_recovered_count=0
```

This metadata only indicates provider/runtime recovery behavior. It is not a
directional performance claim.

## Files Changed

- `scripts/baseline_v3_four_arm.py`
- `tests/test_baseline_v3_four_arm.py`
- `docs/GOTRA_BASELINE_V3_PROVIDER_CONTRACT_HARDENING_RESULT_20260619T074444Z.md`
- `docs/GOTRA_BASELINE_V3_PROVIDER_RUNTIME_TIMEOUT_HARDENING_RESULT_20260619T090347Z.md`

## Remaining Blockers

- No provider/runtime blocker remains in the bounded C2 and scale-smoke ladder
  covered by this result.
- Formal-lite has not been run and remains a separate explicitly gated step.
- OOS/science/public/trading claims remain unsupported by this smoke evidence.

## Next Action

Review PR #9 with this provider/runtime smoke evidence. Enter formal-lite only
under a separate explicit authorization and evidence boundary.
