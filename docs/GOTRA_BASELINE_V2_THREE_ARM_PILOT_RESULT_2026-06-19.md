# GOTRA Baseline v2 Three-Arm Pilot Result Index (2026-06-19)

## Current Terminal Status

- branch/head: `codex/baseline-v2-three-arm-pilot @ 1fe7e6f`
- current provider/model: `kimi` / `Kimi-K2.6`
- provider_base_url: `https://api.sophnet.com/v1/chat/completions`
- provider_max_tokens: `2000`
- terminal status: `PROVIDER_PILOT_PASS`
- detailed report: `docs/GOTRA_BASELINE_V2_KIMI26_INPUT_ECHO_RECOVERY_2026-06-19.md`

## DeepSeek and GLM Lines

These lines remain frozen and were not rerun in the Kimi input-echo recovery goal:

```text
GLM-5.2 = provider timeout/runtime blocker
DeepSeek-V4-Flash = endpoint discovery PASS, schema/parser compatibility blocker
```

## Kimi Input-Echo Recovery

```text
round 1 canary = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r1_20260619T025720Z / PROVIDER_CANARY_FAIL
round 1 root_failure = schema_contract_error/direct_llm/AAPL/2023-01-03

round 2 canary = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r2_20260619T025830Z / PROVIDER_CANARY_FAIL
round 2 root_failure = schema_contract_error/direct_llm/AAPL/2024-07-01

round 3 canary = baseline_v2_three_arm_canary_kimi26_input_echo_recovery_r3_20260619T030212Z / PROVIDER_CANARY_PASS
round 3 canary expected_steps = 18
round 3 canary actual_step_files = 18
round 3 canary paired_coverage = 1.0

pilot = baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z / PROVIDER_PILOT_PASS
pilot expected_steps = 180
pilot actual_step_files = 180
pilot paired_coverage = 1.0
pilot provider_error/input_echo/json/schema/429/timeout/future-data = 0
```

## Frozen Interpretation

```text
direct_llm:
  direction_hit_rate = 0.38333333333333336
  mse = 193.284742
  mae = 10.395435
  policy_a_cumulative_return_pct = 17.489133

ksana_only:
  direction_hit_rate = 0.26666666666666666
  mse = 224.882435
  mae = 10.859464
  policy_a_cumulative_return_pct = 7.567385

full_gotra:
  direction_hit_rate = 0.3
  mse = 225.483452
  mae = 11.117102
  policy_a_cumulative_return_pct = 6.577583
```

The direct conclusion is that this pilot does not show `ksana_only` or `full_gotra` outperforming `direct_llm`. This is a pilot-layer negative/neutral signal for the current Baseline v2 input and artifact design.

## Local Validation

```text
uv run python -m py_compile scripts/baseline_v2_three_arm_pilot.py = PASS
uv run ruff check --no-cache scripts/baseline_v2_three_arm_pilot.py tests/test_baseline_v2_three_arm_pilot.py = PASS
uv run pytest -q tests/test_baseline_v2_three_arm_pilot.py = 41 passed
git diff --check = PASS
```

## Runtime Policy

```text
scheduler_policy = per_date_feedback_snapshot_interleaved_point_arm_v2
timeout_policy = per_arm_complexity_normalized_v2
request-timeout-seconds = 240
timeout_retries = 1
timeout_retry_backoff_seconds = 20
repair canary provider_concurrency = 1
repair canary max_provider_concurrency = 1
pilot provider_concurrency = 2
pilot max_provider_concurrency = 4
pilot max_provider_concurrency_used = 4
```

## Evidence Boundary

```text
local checks: PASS
provider/runtime health: Kimi canary and pilot provider path completed without provider/runtime/schema errors
pilot evidence: PROVIDER_PILOT_PASS on the fixed Baseline v2 three-arm pilot grid
long-run/formal acceptance: not entered
science/public claim: not entered
paper trading/trading advice: not entered
```

## Verdict

`PROVIDER_PILOT_PASS`.

This does not upgrade the result to formal-lite, OOS, Stage9, paper trading, or a public/science claim.
