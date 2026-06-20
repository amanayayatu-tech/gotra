# GOTRA v3.4 Codex CLI Backend Formal-Lite Preregistration

Date: 2026-06-20

## Scope

This document freezes the v3.4 `codex_cli_llm_backend` experiment path before any
Codex CLI backend canary, tiny smoke, or formal-lite-min run.

Evidence layer: planned formal-lite internal research evidence only.

Non-claims:
- Not OOS.
- Not forward-live.
- Not science/public proof.
- Not trading or investment advice.
- Not equivalent to prior Kimi/GLM/DeepSeek provider API runs.

The Kimi/GLM/DeepSeek provider API formal-lite/parser line remains frozen as
historical provider-runtime evidence. v3.4 is a new experiment family and does
not inherit those results.

## Backend

Backend name: `codex_cli_llm_backend`

Required backend metadata for every v3.4 backend run/result:
- `codex_cli_version`
- `model`
- `reasoning_setting`
- `prompt_hash`
- `output_transcript_path` as a local run artifact path, not committed
- `parsed_decision_hash`
- `run_id`
- backend name exactly `codex_cli_llm_backend`

Default locked backend config for this prereg:
- model: `gpt-5.5`
- reasoning_setting: `low`
- provider_max_tokens: `2000`
- Codex CLI sandbox: read-only
- Codex CLI approval mode: never
- raw transcripts: local run artifacts only, never committed

If Codex CLI is missing, cannot report a version, cannot capture transcript
paths, or cannot parse strict JSON safely, the terminal status is
`CODEX_CLI_BACKEND_BLOCKED` or the exact schema/parser blocker. The runner must
not fall back to Kimi/GLM/DeepSeek provider APIs.

## Arm Interpretation

Historical `direct_llm` is reported as
`direct_llm_parametric_memory_control`. It is not a clean no-future baseline
because modern LLM parameter memory cannot be cut off at historical
`decision_date`.

Metrics involving `direct_llm`, including C1/C3/C5, MSE, direction hit rate, or
returns, are diagnostic only. They must not be used to prove GOTRA, ksana, or
alaya success or failure.

Primary comparison hierarchy:
1. `deterministic_price_only_baseline` as the clean historical non-LLM reference.
2. `ksana_real_research` vs `full_gotra` for Alaya feedback increment, only when
   `true_independent_feedback_eligible_points > 0`.
3. `direct_llm_parametric_memory_control` only as a modern LLM parameter-memory
   diagnostic.

## Deterministic Price-Only Baseline

The deterministic reference must:
- call no LLM;
- use only price/history rows with `date <= decision_date`;
- expose `future_rows_excluded`;
- produce comparable direction, expected change, and confidence fields;
- never be interpreted as provider/backend health.

## Frozen v3.4 Min Grid

The v3.4 min grid is intentionally smaller than prior v3.2 30x12 provider API
formal-lite because Codex CLI is a new backend family with heavier transcript
capture and different runtime characteristics. This run is not numerically
comparable to the v3.2 Kimi/SophNet provider API runs.

Formal-lite-min grid:
- tickers: `AAPL,MSFT,NVDA`
- dates: `2024-01-02,2024-02-01,2024-03-01,2024-04-02`
- warm_up_dates: `1`
- arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- input layers: `price_only_packet`, `richer_research_packet`
- expected provider/backend steps: `3 tickers x 4 dates x 4 arms x 2 layers = 96`
- expected scored paired groups: `3 tickers x 3 scored dates x 2 layers = 18`

Fixtures:
- research_artifacts_path:
  `tests/fixtures/baseline_v3_1_research_artifacts.json`
- feedback_artifacts_path:
  `tests/fixtures/baseline_v3_2_feedback_artifacts.json`

## Gates

Run order:
1. Local checks: py_compile, ruff, focused pytest, and diff check.
2. Mock/no-LLM run over the frozen min grid.
3. Codex CLI backend canary.
4. Codex CLI backend tiny smoke.
5. Formal-lite-min run only if all prior gates pass cleanly.

Canary grid:
- tickers: `AAPL`
- dates: `2024-01-02,2024-02-01`
- all four arms and both input layers
- warm_up_dates: `1`

Tiny smoke grid:
- tickers: `AAPL,MSFT`
- dates: `2024-01-02,2024-02-01,2024-03-01`
- all four arms and both input layers
- warm_up_dates: `1`

Pass gates:
- expected steps complete for the gate size;
- paired coverage is complete where scored points exist;
- future-data violations = 0;
- research_source_leak_count = 0;
- feedback_source_leak_count = 0;
- schema/parser/input_echo errors = 0;
- `codex_cli_version`, `prompt_hash`, `output_transcript_path`, and
  `parsed_decision_hash` are present for backend-scored steps.

If `true_independent_feedback_eligible_points == 0`, H2 must be reported as
`DATA_INSUFFICIENT_FOR_H2`; self-feedback cannot be counted as true independent
Alaya feedback.

## Result Semantics

Completion status is separate from research verdict:
- `MOCK_PASS`: local/no-LLM harness gate passed.
- `PROVIDER_CANARY_PASS`: Codex CLI backend canary passed. This is backend
  health only.
- `PROVIDER_PILOT_PASS`: backend pilot/formal-lite-min completed validly. This
  is formal-lite internal research evidence only.
- `CODEX_CLI_BACKEND_BLOCKED`: Codex CLI executable/version/transcript/backend
  contract blocker.
- `STOPPED_NO_FORMAL_VERDICT` or exact terminal blocker if interrupted or stopped
  before a terminal summary.

No v3.4 document may claim OOS, forward-live, science/public proof, trading
value, or provider API equivalence.
