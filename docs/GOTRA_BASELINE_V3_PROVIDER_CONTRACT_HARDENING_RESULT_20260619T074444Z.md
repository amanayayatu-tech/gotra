# GOTRA Baseline v3 Provider Contract Hardening Result

UTC timestamp: 2026-06-19T07:44:44Z

## Scope

This document records provider output contract hardening and bounded runtime
smoke evidence for PR #9. It is not formal-lite acceptance, OOS evidence,
science/public evidence, or a trading claim.

No directional metrics are interpreted as gotra/ksana/alaya superiority.

## Raw Diagnosis

Inspected one retained raw provider artifact from the prior C1 blocker:

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_auth_restored_c1_20260619T062650Z
artifact: provider_raw/direct_llm/raw_2024-01-02_msft_price_only_packet.txt
raw_json_valid: true
forbidden_non_empty_fields: alaya_memory_refs
sanitized_forbidden_value_sample: ["full_gotra"]
diagnosis: generic placeholder in a forbidden direct_llm ref field; not price
  evidence and not a valid alaya feedback_ref.
```

Full raw content is intentionally not quoted here.

## Hardening Change

Files changed:

```text
scripts/baseline_v3_four_arm.py
tests/test_baseline_v3_four_arm.py
docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md
docs/GOTRA_BASELINE_V3_AUTH_RESTORE_RUNTIME_RETRY_RESULT_20260619T062922Z.md
docs/GOTRA_BASELINE_V3_PROVIDER_CONTRACT_HARDENING_RESULT_20260619T074444Z.md
```

Implementation summary:

- Added arm-specific `ksana_refs` / `alaya_memory_refs` output contract text
  to provider payloads.
- Added prompt-level `ARM_SPECIFIC_REF_RULES`,
  `OUTPUT_CONTRACT_JSON`, and a same-schema JSON skeleton.
- Kept parser/schema guards strict. Invalid refs are still rejected and are not
  silently cleared or scored.
- Clarified the prereg/documented runtime result boundary.

## Local Validation

```text
uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
PASS

uv run pytest -q tests/test_baseline_v3_four_arm.py
PASS: 22 passed

git diff --check
PASS
```

New/expanded tests cover:

- `render_provider_prompt` includes explicit direct_llm empty ref-array rules.
- direct_llm still rejects non-empty `ksana_refs`.
- direct_llm still rejects non-empty `alaya_memory_refs`.
- ksana arms still reject `alaya_memory_refs`.
- full_gotra still rejects alaya refs when no matching visible feedback ref is
  available.

## Provider Canary

```text
run_id: baseline_v3_four_arm_canary_kimi26_contract_hardened_20260619T063900Z
provider: kimi
model: Kimi-K2.6
base_url: https://api.sophnet.com/v1/chat/completions
max_tokens: 2000
grid: AAPL; 2024-01-02,2024-02-01,2024-03-01,2024-04-01; both input layers; four arms
concurrency: 1 / max 1
status: PROVIDER_CANARY_PASS
expected_steps: 32
actual_step_files: 32
schema_pass_count: 32
schema_contract_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
provider_error_count: 0
provider_http_error_count: 0
timeout_count: 0
http_429_count: 0
raw_content_saved_count: 0
```

## Tiny Micro-Pilot C1

First C1 attempt:

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_contract_hardened_c1_20260619T064511Z
grid: AAPL,MSFT,NVDA; 4 dates; both input layers; four arms
concurrency: 1 / max 1
status: PROVIDER_PILOT_FAIL
expected_steps: 96
actual_step_files: 96
schema_pass_count: 95
schema_contract_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
provider_error_count: 1
provider_http_error_count: 1
timeout_count: 0
http_429_count: 0
root_failure: provider_http_error/ksana_formatting_only/price_only_packet/NVDA/2024-04-01
sanitized_error: SophNet Kimi HTTP 500 InternalError
```

Conservative retry after the transient provider HTTP 500:

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_contract_hardened_c1_retry1_20260619T070356Z
concurrency: 1 / max 1
status: PROVIDER_PILOT_PASS
expected_steps: 96
actual_step_files: 96
schema_pass_count: 96
schema_contract_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
provider_error_count: 0
provider_http_error_count: 0
timeout_count: 0
http_429_count: 0
raw_content_saved_count: 0
```

## Tiny Micro-Pilot C2

```text
run_id: baseline_v3_four_arm_micro_pilot_kimi26_contract_hardened_c2_20260619T072227Z
grid: AAPL,MSFT,NVDA; 4 dates; both input layers; four arms
concurrency: 1 / max 2
status: PROVIDER_PILOT_FAIL
expected_steps: 96
actual_step_files: 48
schema_pass_count: 47
schema_contract_error_count: 0
schema_error_count: 0
input_echo_error_count: 0
provider_error_count: 1
provider_http_error_count: 0
timeout_count: 1
http_429_count: 0
root_failure: provider_timeout/ksana_real_research/richer_research_packet/NVDA/2024-02-01
sanitized_error: SophNet Kimi request timed out after 900.151456 seconds
stop_reason: paired coverage no longer feasible
```

C2 did not pass. Therefore scale-smoke was not run.

## Scale-Smoke

```text
status: NOT_RUN
reason: C2 did not pass; stopped at provider runtime timeout blocker.
```

## Evidence Boundary

This result supports:

- local implementation checks
- provider canary pass evidence
- tiny micro-pilot C1 smoke evidence after one conservative retry
- provider/runtime blocker evidence for C2 at max concurrency 2

This result does not support:

- formal-lite acceptance
- OOS acceptance
- science/public claim
- trading claim
- any directional superiority claim for gotra, ksana, alaya, or direct_llm

## Remaining Blockers

- C2 max-concurrency probe is blocked by provider runtime timeout on
  `ksana_real_research/richer_research_packet/NVDA/2024-02-01`.
- direct_llm contract hardening appears effective in the observed fresh canary
  and C1 retry runs, but broader claims are out of scope.

## Next Action

Treat C2 as a provider/runtime hardening item before scale-smoke. Do not enter
formal-lite until the provider ladder has a clean C2 and subsequent scale-smoke
under the preregistered boundaries.

## Addendum: Runtime Timeout Hardening Follow-Up

UTC: 2026-06-19T09:03:47Z

Follow-up runtime hardening was completed after the C2 provider timeout blocker
recorded above. The Kimi provider path now uses a bounded retry for retryable
provider runtime failures while keeping schema contract, input echo,
future-data, and invalid-response failures strict and non-retryable.

Follow-up evidence:

```text
C2 rerun: baseline_v3_four_arm_micro_pilot_kimi26_runtime_retry_c2_20260619T075718Z
C2 status: PROVIDER_PILOT_PASS
C2 expected_steps: 96
C2 actual_step_files: 96
C2 schema_contract_error_count: 0
C2 provider_error_count: 0
C2 timeout_count: 0

scale-smoke: baseline_v3_four_arm_scale_smoke_kimi26_runtime_retry_10x6_20260619T080822Z
scale status: PROVIDER_PILOT_PASS
scale expected_steps: 480
scale actual_step_files: 480
scale schema_contract_error_count: 0
scale provider_error_count: 0
scale timeout_count: 0
scale retryable_provider_error_recovered_count: 2
```

See
`docs/GOTRA_BASELINE_V3_PROVIDER_RUNTIME_TIMEOUT_HARDENING_RESULT_20260619T090347Z.md`
for the full provider/runtime follow-up record. This addendum does not change
the evidence boundary: it is provider/runtime smoke evidence only, not
formal-lite, OOS, science/public, trading, or directional arm superiority
evidence.
