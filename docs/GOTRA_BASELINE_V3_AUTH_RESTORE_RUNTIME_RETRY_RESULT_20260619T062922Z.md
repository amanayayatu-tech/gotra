# GOTRA Baseline v3 Auth Restore Runtime Retry Result

UTC: 2026-06-19T06:29:22Z

## Scope

This document records the conservative provider runtime ladder after restoring
the local provider auth environment. It is provider/runtime and smoke evidence
only. It is not formal-lite acceptance, OOS validation, science/public
validation, or trading evidence.

Directional metrics are recorded in run artifacts but are not interpreted here
as gotra/ksana/alaya superiority or inferiority.

## Preflight

```text
repo/root: /Users/peachy/Documents/gotra
branch: codex/baseline-v3-four-arm-impl-20260619
head before this doc: 757c21d Document PR9 comment closure and runtime retry
PR: https://github.com/amanayayatu-tech/gotra/pull/9
PR state: open
PR head: 757c21d100b7d75099f92ca5aafaf89c873902d9
PR mergeable_state: clean
PR checks before this doc: Python checks pass, Python checks pass
```

Existing untracked Stage8/Stage9/paper-trading artifacts were present before
this goal and were not touched or staged.

## Auth Environment Check

No secret value was read, printed, copied, or written.

```text
.env.sophnet exists: yes
.env.sophnet permissions: -rw-------
.env.sophnet gitignore coverage: .gitignore:24:.env.*
CLI supports --env-file: yes
CLI supports provider/timeout flags: yes
provider commands used --env-file .env.sophnet: yes
```

Auth blocker status:

```text
PROVIDER_BLOCKED_PRE_HTTP: not observed in this goal
provider HTTP attempted: yes
```

## Local Checks

```text
uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run pytest -q tests/test_baseline_v3_four_arm.py
21 passed
```

## Provider Canary

run_id: `baseline_v3_four_arm_canary_kimi26_auth_restored_20260619T061945Z`

Configuration:

```text
provider: kimi
model: Kimi-K2.6
provider_base_url: https://api.sophnet.com/v1/chat/completions
provider_max_tokens: 2000
provider_concurrency: 1
max_provider_concurrency: 1
input_layer: both
tickers: AAPL
dates: 2024-01-02,2024-02-01,2024-03-01,2024-04-01
warm_up_dates: 1
request_timeout_seconds: 900
max_request_timeout_seconds: 900
env_file: .env.sophnet
```

Summary:

```text
status: PROVIDER_CANARY_PASS
expected_steps: 32
actual_step_files: 32
scored_step_count: 32
schema_pass_count: 32
paired_complete_points: 6
paired_coverage: 1.0
provider_error_count: 0
provider_http_error_count: 0
schema_error_count: 0
schema_contract_error_count: 0
input_echo_error_count: 0
http_429_count: 0
timeout_count: 0
future_data_violations: 0
research_source_leak_count: 0
raw_content_saved_count: 0
max_provider_concurrency_used: 1
```

## Tiny Micro-Pilot C1

run_id: `baseline_v3_four_arm_micro_pilot_kimi26_auth_restored_c1_20260619T062650Z`

Configuration:

```text
provider: kimi
model: Kimi-K2.6
provider_base_url: https://api.sophnet.com/v1/chat/completions
provider_max_tokens: 2000
provider_concurrency: 1
max_provider_concurrency: 1
input_layer: both
tickers: AAPL,MSFT,NVDA
dates: 2024-01-02,2024-02-01,2024-03-01,2024-04-01
warm_up_dates: 1
request_timeout_seconds: 900
max_request_timeout_seconds: 900
env_file: .env.sophnet
```

Summary:

```text
status: STOPPED_BY_CIRCUIT_BREAKER
expected_steps: 96
actual_step_files: 9
scored_step_count: 8
schema_pass_count: 8
paired_complete_points: 0
paired_coverage: 0.0
provider_error_count: 1
provider_http_error_count: 0
schema_error_count: 1
schema_contract_error_count: 1
input_echo_error_count: 0
http_429_count: 0
timeout_count: 0
future_data_violations: 0
research_source_leak_count: 0
raw_content_saved_count: 1
max_provider_concurrency_used: 1
stop_reason: schema/parser error observed
trigger_reason: schema/parser error observed
root_failure: schema_contract_error/direct_llm/price_only_packet/MSFT/2024-01-02
```

Provider output contract blocker:

```text
arm: direct_llm
input_layer: price_only_packet
ticker: MSFT
decision_date: 2024-01-02
scoring_segment: warm_up
error_type: schema_contract_error
error_message: direct_llm must not include ksana_refs or alaya_memory_refs
provider_error_class: SchemaContractError
provider_attempts: 1
provider_retry_count: 0
request_duration_seconds: 9.966759
request_timeout_seconds: 900.0
provider_raw_content_path: data/backtest/runs/baseline_v3_four_arm_micro_pilot_kimi26_auth_restored_c1_20260619T062650Z/provider_raw/direct_llm/raw_2024-01-02_msft_price_only_packet.txt
provider_raw_content_sha256: f4d1cb3df6ba2ac51f86ddc26692a96542ba61fc8124c922a9d4b61179635a4c
```

The raw provider response was retained as an artifact but is not quoted or
printed in this document.

Follow-up sanitized diagnosis on 2026-06-19:

```text
raw_json_valid: true
forbidden_non_empty_fields: alaya_memory_refs
sanitized_forbidden_value_sample: ["full_gotra"]
interpretation: generic placeholder in a forbidden direct_llm ref field; not
  price evidence and not a valid alaya feedback_ref.
```

## Tiny Micro-Pilot C2

Not entered.

Reason: C1 did not pass. The ladder requires C1 pass before C2.

## Medium Scale-Smoke

Not entered.

Reason: canary passed, but C1 did not pass. The ladder requires canary + C1 +
C2 all pass before the 480-step medium scale-smoke.

## Evidence Layer

```text
local checks: PASS
provider/runtime health: canary PASS with restored auth
tiny micro-pilot C1 smoke: attempted; blocked by provider schema contract output
tiny micro-pilot C2 smoke: not entered
medium scale-smoke: not entered
formal-lite acceptance: not entered
OOS validation: not entered
science/public claim: not entered
trading claim: not entered
```

## Remaining Blockers

- Auth is available locally through `.env.sophnet`; no pre-HTTP auth blocker was
  observed in this goal.
- Provider output contract remains unstable beyond the single-ticker canary:
  C1 stopped when `direct_llm` returned disallowed `ksana_refs` or
  `alaya_memory_refs`.
- Because C1 did not pass, C2 and scale-smoke were correctly not entered.

## Next Action

Inspect the retained raw response artifact offline and decide whether the
provider prompt/schema guard should be hardened further or whether this should
be treated as provider output instability. Do not enter C2 or scale-smoke until
C1 completes with provider/schema/input_echo/error counters at 0 and required
paired coverage.
