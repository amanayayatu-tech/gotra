# GOTRA Baseline v3.2 Kimi Temperature Contract Repair Result

Date: 2026-06-20T07:54:39Z

## Scope

This result records a provider request-contract repair and gated rerun attempt for Baseline v3.2.

Evidence layer:
- local checks
- targeted provider/runtime canary
- tiny provider smoke
- one bounded formal-lite internal research rerun attempt

Non-claims:
- not OOS evidence
- not forward-live evidence
- not science/public proof
- not trading or investment advice
- no gotra/ksana/alaya superiority claim is made here

## Frozen PR #14 Failure

Frozen failed run:
- run_id: `baseline_v3_2_formal_lite_kimi26_min30x12_20260620T033017Z`
- status: `PROVIDER_PILOT_FAIL`
- expected_steps: 2880
- actual_step_files: 2880
- scored_step_count: 2879
- paired_coverage: 1.0
- provider_error_count: 1
- provider_http_error_count: 1
- root_failure: `provider_http_error/direct_llm/richer_research_packet/AMD/2024-02-01`
- error class: SophNet Kimi HTTP 400, `invalid temperature: only 1 is allowed for this model`

The failing step reported `provider_temperature=null`, so the repair focused on the Kimi/SophNet request payload, cache identity, and audit metadata.

## Implementation

Changed files:
- `scripts/baseline_v3_four_arm.py`
- `tests/test_baseline_v3_four_arm.py`

Implementation summary:
- Kimi/SophNet provider requests now send explicit `temperature=1.0`.
- `provider_temperature` is included in the provider cache key identity, preventing reuse of prior incompatible cache entries.
- `provider_temperature`, `provider_temperature_applied`, and `provider_temperature_reason` are exposed in request diagnostics, manifest, summary, and step artifacts where applicable.
- Non-Kimi providers are not forced onto the Kimi temperature contract.

Focused tests added:
- Kimi-K2.6/SophNet request payload sends `temperature=1.0`.
- Provider cache identity changes when temperature changes.
- Manifest/summary/step metadata expose `provider_temperature`.
- Non-Kimi provider temperature metadata remains unapplied.

## Local Validation

Passed before provider runs:
- `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py`
- `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py`
- `uv run pytest -q tests/test_baseline_v3_four_arm.py`
- `git diff --check`

Pytest result: `42 passed`.

## Targeted Canary

run_id: `baseline_v3_2_kimi_temp_contract_canary_20260620T064615Z`

Grid:
- ticker: `AMD`
- dates: `2024-01-02,2024-02-01`
- arms: all four arms
- input layers: both
- warm_up_dates: 1

Result:
- status: `PROVIDER_CANARY_PASS`
- actual_step_files: 16
- expected_steps: 16
- paired_coverage: 1.0
- provider_error_count: 0
- provider_http_error_count: 0
- schema_error_count: 0
- input_echo_error_count: 0
- http_429_count: 0
- timeout_count: 0
- future_data_violation_count: 0
- research_source_leak_count: 0
- feedback_source_leak_count: 0
- raw_content_saved_count: 0
- provider_temperature: 1.0
- provider_temperature_applied: true
- root_failure: empty

The exact frozen root-failure cell `direct_llm/richer_research_packet/AMD/2024-02-01` scored successfully with `provider_temperature=1.0` and cache identity containing `temperature=1`.

## Tiny Smoke

run_id: `baseline_v3_2_kimi_temp_contract_tiny_smoke_20260620T065014Z`

Grid:
- tickers: `AAPL,MSFT,AMD,NVDA`
- dates: `2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03`
- arms: all four arms
- input layers: both
- warm_up_dates: 3

Result:
- status: `PROVIDER_PILOT_PASS`
- actual_step_files: 192
- expected_steps: 192
- paired_coverage: 1.0
- provider_error_count: 0
- provider_http_error_count: 0
- schema_error_count: 0
- input_echo_error_count: 0
- http_429_count: 0
- timeout_count: 0
- future_data_violation_count: 0
- research_source_leak_count: 0
- feedback_source_leak_count: 0
- raw_content_saved_count: 0
- true_independent_feedback_eligible_points: 24
- provider_temperature: 1.0
- provider_temperature_applied: true
- root_failure: empty

## Full Formal-Lite Rerun Attempt

run_id: `baseline_v3_2_formal_lite_kimi26_tempfixed_min30x12_20260620T071033Z`

Grid:
- 30 tickers x 12 dates x 4 arms x 2 input layers
- expected_steps: 2880
- warm_up_dates: 3
- provider: `kimi`
- model: `Kimi-K2.6`
- provider_max_tokens: 2000
- provider_temperature: 1.0
- research_artifacts_path: `tests/fixtures/baseline_v3_1_research_artifacts.json`
- feedback_artifacts_path: `tests/fixtures/baseline_v3_2_feedback_artifacts.json`

Terminal result:
- status: `STOPPED_BY_CIRCUIT_BREAKER`
- actual_step_files: 439
- scored_step_count: 438
- paired_coverage: 0.0
- provider_error_count: 1
- provider_http_error_count: 0
- schema_error_count: 1
- json_decode_error_count: 1
- schema_contract_error_count: 0
- input_echo_error_count: 0
- http_429_count: 0
- timeout_count: 0
- future_data_violation_count: 0
- research_source_leak_count: 0
- feedback_source_leak_count: 0
- raw_content_saved_count: 1
- true_independent_feedback_eligible_points: 0
- provider_temperature: 1.0
- provider_temperature_applied: true
- trigger_reason: `schema/parser error observed`
- root_failure: `json_decode_error/ksana_formatting_only/richer_research_packet/0005.HK/2024-02-01`

Failure step metadata:
- step: `data/backtest/runs/baseline_v3_2_formal_lite_kimi26_tempfixed_min30x12_20260620T071033Z/ksana_formatting_only/step_2024-02-01_0005_hk_richer_research_packet.json`
- error_type: `json_decode_error`
- error_message: `provider response content was not valid v3 decision JSON`
- provider_error_class: `JSONDecodeError`
- provider_attempts: 1
- provider_retry_count: 0
- provider_temperature: 1.0
- provider_temperature_applied: true
- provider_raw_content_path: local run artifact only, not committed
- provider_raw_content_chars: 1487
- provider_raw_content_sha256: `ad85c52cd130a2304bbd6dcdeaf0b7412b99aa0ae1c47a33d4eb9d1327cc042f`

Completion classification:
- `FORMAL_LITE_RUNTIME_FAIL`
- Run-level terminal state is `STOPPED_BY_CIRCUIT_BREAKER`.
- The Kimi temperature HTTP 400 blocker is repaired for the targeted canary and tiny smoke.
- The full rerun did not produce a clean formal-lite terminal result because a new provider-output JSON decode blocker stopped the run.

## H1/H2/H3 Verdict Boundary

H1/H2/H3 are not accepted or rejected by this run.

Reason:
- The full formal-lite rerun stopped before completion.
- The scored formal-lite denominator is incomplete.
- `paired_coverage=0.0` at terminal stop because the run stopped during warm-up dates before scored paired groups were available.
- Directional metrics from the incomplete run are not interpreted.

## Artifact Boundary

- Run directories remain local under `data/backtest/runs/*`.
- Provider raw response artifacts were not printed here and must not be committed.
- `.env.sophnet` was used only through ignored `--env-file` support; no secret values were read, printed, or committed.
- No `data/backtest/runs/*`, provider raw files, `.env*`, DB/bundle/tar/zip, `data/paper_trading/*`, or Stage8/Stage9 artifacts are part of the intended commit.

## Remaining Blocker

The next blocker is provider-output JSON validity for:

`ksana_formatting_only/richer_research_packet/0005.HK/2024-02-01`

This is separate from the Kimi temperature contract. The strict parser/schema guard correctly prevented scoring malformed provider output.

## Next Action

Review the saved raw artifact under the local run directory for sanitized diagnosis, then decide whether a narrowly scoped provider-output contract hardening is justified. Do not rerun full formal-lite until that blocker is understood and covered by tests.
