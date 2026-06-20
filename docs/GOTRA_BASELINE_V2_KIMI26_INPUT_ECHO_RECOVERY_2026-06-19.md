# GOTRA Baseline v2 Kimi-K2.6 Input-Echo Recovery (2026-06-19)

## Status

- branch/head: `codex/baseline-v2-three-arm-pilot @ 1fe7e6f`
- repo/root: `/Users/peachy/Documents/gotra`
- terminal status: `PROVIDER_PILOT_PASS`
- provider/model/base_url: `kimi` / `Kimi-K2.6` / `https://api.sophnet.com/v1/chat/completions`
- provider_max_tokens: `2000`
- secret handling: `.env.sophnet` loaded by CLI; secret values were not printed.

## Previous Blocker

Previous pilot:

```text
run_id = baseline_v2_three_arm_pilot_kimi26_goal_autorun_20260619T022830Z
status = STOPPED_BY_CIRCUIT_BREAKER
root_failure = json_decode_error/ksana_only/AAPL/2023-01-03
raw = data/backtest/runs/baseline_v2_three_arm_pilot_kimi26_goal_autorun_20260619T022830Z/provider_raw/ksana_only/raw_2023-01-03_aapl.txt
```

Raw content looked like an incomplete echoed input packet. It was not scored.

## Implementation

Changed files:

```text
scripts/baseline_v2_three_arm_pilot.py
tests/test_baseline_v2_three_arm_pilot.py
docs/GOTRA_BASELINE_V2_KIMI26_INPUT_ECHO_RECOVERY_2026-06-19.md
docs/GOTRA_BASELINE_V2_KIMI26_RESULT_2026-06-19.md
docs/GOTRA_BASELINE_V2_THREE_ARM_PILOT_RESULT_2026-06-19.md
```

Harness changes:

```text
provider prompt v2 = segmented TASK / OUTPUT REQUIREMENTS / DECISION_JSON_ALLOWED_KEYS / ARM_CONTRACT / INPUT_PACKET_DO_NOT_COPY
input_echo_error = added and counted as provider/schema error
input_echo detection = complete JSON payload keys plus raw prefix scan
raw content = saved on provider-output failure
normalization = still limited to trim, fence stripping, first balanced JSON extraction
provider_max_tokens = kept in client/cache/manifest/summary/step at 2000 for this run
```

The prompt repair did not change arms, ticker/date universe, main metrics, score metric, future-data audit, or output schema.

## Local Validation

```text
uv run python -m py_compile scripts/baseline_v2_three_arm_pilot.py = PASS
uv run ruff check --no-cache scripts/baseline_v2_three_arm_pilot.py tests/test_baseline_v2_three_arm_pilot.py = PASS
uv run pytest -q tests/test_baseline_v2_three_arm_pilot.py = 41 passed
git diff --check = PASS
```

## Repair Rounds

Round 1:

```text
mock = baseline_v2_three_arm_mock_kimi26_input_echo_recovery_20260619T025708Z / MOCK_PASS
canary = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r1_20260619T025720Z / PROVIDER_CANARY_FAIL
root_failure = schema_contract_error/direct_llm/AAPL/2023-01-03
cause = direction was "up"; raw saved
```

Round 2:

```text
mock = baseline_v2_three_arm_mock_kimi26_input_echo_recovery_r2_20260619T025822Z / MOCK_PASS
canary = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r2_20260619T025830Z / PROVIDER_CANARY_FAIL
root_failure = schema_contract_error/direct_llm/AAPL/2024-07-01
cause = confidence was "medium"; raw saved
```

Round 3:

```text
mock = baseline_v2_three_arm_mock_kimi26_input_echo_recovery_r3_20260619T030201Z / MOCK_PASS
canary = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r3_20260619T030212Z / PROVIDER_CANARY_PASS
canary expected_steps = 18
canary actual_step_files = 18
canary paired_coverage = 1.0
canary provider_error/input_echo/json/schema/429/timeout/future-data = 0
```

## Provider Pilot

```text
run_id = baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z
status = PROVIDER_PILOT_PASS
expected_steps = 180
actual_step_files = 180
paired_coverage = 1.0
provider_error_count = 0
input_echo_error_count = 0
json_decode_error_count = 0
schema_contract_error_count = 0
schema_error_count = 0
http_429_count = 0
timeout_count = 0
future_data_violation_count = 0
raw_content_saved_count = 0
root_failure =
```

Runtime policy:

```text
scheduler_policy = per_date_feedback_snapshot_interleaved_point_arm_v2
timeout_policy = per_arm_complexity_normalized_v2
request-timeout-seconds = 240
timeout_retries = 1
timeout_retry_backoff_seconds = 20
pilot provider_concurrency = 2
pilot max_provider_concurrency = 4
pilot max_provider_concurrency_used = 4
```

Pilot metrics:

```text
direct_llm: scored=60, direction_hit_rate=0.38333333333333336, mse=193.284742, mae=10.395435, policy_a_cumulative_return_pct=17.489133
ksana_only: scored=60, direction_hit_rate=0.26666666666666666, mse=224.882435, mae=10.859464, policy_a_cumulative_return_pct=7.567385
full_gotra: scored=60, direction_hit_rate=0.3, mse=225.483452, mae=11.117102, policy_a_cumulative_return_pct=6.577583
```

Pilot paired diffs:

```text
direct_vs_ksana: paired_points=60, mse_delta_left_minus_right=-31.597694, policy_a_return_delta_right_minus_left_pct=-1.563016
ksana_vs_full: paired_points=60, mse_delta_left_minus_right=-0.601017, policy_a_return_delta_right_minus_left_pct=-0.156457
direct_vs_full: paired_points=60, mse_delta_left_minus_right=-32.19871, policy_a_return_delta_right_minus_left_pct=-1.719473
```

## Evidence Boundary

```text
local checks: PASS
provider/runtime health: Kimi repair canary passed; pilot completed without provider/runtime/schema blockers
pilot evidence: PROVIDER_PILOT_PASS for this small fixed three-arm grid
long-run/formal acceptance: not entered
science/public claim: not entered
paper trading/trading advice: not entered
```

## Verdict

`PROVIDER_PILOT_PASS`.

This is not formal-lite, not OOS acceptance, not Stage9, not paper trading, and not a science/public claim that any arm wins.
