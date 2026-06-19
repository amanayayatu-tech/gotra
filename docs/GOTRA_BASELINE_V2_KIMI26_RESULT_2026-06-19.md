# GOTRA Baseline v2 Kimi-K2.6 Three-Arm Result (2026-06-19)

## Current Status

- branch/head: `codex/baseline-v2-three-arm-pilot @ 1fe7e6f`
- current terminal status: `PROVIDER_PILOT_PASS`
- provider/model: `kimi` / `Kimi-K2.6`
- provider_base_url: `https://api.sophnet.com/v1/chat/completions`
- provider_max_tokens: `2000`
- detailed report: `docs/GOTRA_BASELINE_V2_KIMI26_INPUT_ECHO_RECOVERY_2026-06-19.md`

## Latest Runs

```text
mock run_id = baseline_v2_three_arm_mock_kimi26_input_echo_recovery_r3_20260619T030201Z
mock status = MOCK_PASS
mock expected_steps = 180
mock actual_step_files = 180
mock paired_coverage = 1.0

repair canary run_id = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r3_20260619T030212Z
repair canary status = PROVIDER_CANARY_PASS
repair canary expected_steps = 18
repair canary actual_step_files = 18
repair canary paired_coverage = 1.0

pilot run_id = baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z
pilot status = PROVIDER_PILOT_PASS
pilot expected_steps = 180
pilot actual_step_files = 180
pilot paired_coverage = 1.0
```

## Error Counts

```text
provider_error_count = 0
input_echo_error_count = 0
json_decode_error_count = 0
schema_contract_error_count = 0
schema_error_count = 0
http_429_count = 0
timeout_count = 0
future_data_violation_count = 0
raw_content_saved_count = 0
```

## Pilot Metrics

```text
direct_llm: scored=60, direction_hit_rate=0.38333333333333336, mse=193.284742, mae=10.395435, policy_a_cumulative_return_pct=17.489133
ksana_only: scored=60, direction_hit_rate=0.26666666666666666, mse=224.882435, mae=10.859464, policy_a_cumulative_return_pct=7.567385
full_gotra: scored=60, direction_hit_rate=0.3, mse=225.483452, mae=11.117102, policy_a_cumulative_return_pct=6.577583
```

## Interpretation

```text
direct_llm is best on direction_hit_rate, MSE, MAE, and Policy A return in this pilot.
This pilot does not support ksana_only or full_gotra outperforming direct_llm.
```

This is a negative/neutral pilot signal for measurable ksana/alaya lift under the current price-derived packet and fixed pilot grid. It is not a final verdict on gotra, ksana research, alaya memory, or product value.

## Evidence Boundary

```text
local checks: PASS
provider/runtime health: Kimi repair canary passed and pilot completed without provider errors
pilot evidence: PROVIDER_PILOT_PASS on the fixed Baseline v2 three-arm pilot grid
long-run/formal acceptance: not entered
science/public claim: not entered
```

## Verdict

`PROVIDER_PILOT_PASS`.

Do not present this as OOS pass, formal acceptance, trading advice, or a public/science claim.
