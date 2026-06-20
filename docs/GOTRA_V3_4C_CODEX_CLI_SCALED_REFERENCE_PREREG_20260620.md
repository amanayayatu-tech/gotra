# GOTRA v3.4c Codex CLI Scaled Internal Run Preregistration

Date: 2026-06-20

## Scope

Project: GOTRA v3.4c `codex_cli_llm_backend` scaled internal run with
deterministic price-only reference.

Base stack:
- PR #20: v3.4 Codex CLI backend formal-lite-min path.
- PR #21: v3.4b deterministic price-only reference integration.

Evidence layer target: scaled internal formal-lite research evidence only.

Non-claims:
- Not OOS.
- Not forward-live.
- Not science/public proof.
- Not trading or investment advice.
- Not equivalent to Kimi/GLM/DeepSeek provider API runs.

The Kimi/GLM/DeepSeek provider API line remains frozen as historical
provider-runtime evidence. v3.4c uses only the new `codex_cli_llm_backend`
experiment family.

## Backend

Backend name: `codex_cli_llm_backend`

Locked backend config:
- model: `gpt-5.5`
- reasoning_setting: `low`
- provider_max_tokens: `2000`
- Codex CLI sandbox: read-only
- Codex CLI approval mode: never
- raw transcripts: local run artifacts only, never committed

Required metadata:
- `codex_cli_version`
- `codex_cli_model`
- `codex_cli_reasoning_setting`
- `prompt_hash`
- `output_transcript_path`
- `parsed_decision_hash`
- `run_id`
- backend name exactly `codex_cli_llm_backend`

If the backend is unavailable, metadata is missing, parsing/schema is unsafe,
future-data or source-leak audit fails, or artifacts would cross the commit
boundary, the run must stop and report the exact terminal blocker.

## Frozen Scaled Grid

The v3.4c scaled grid uses the existing v3.2/v3.4 medium smoke universe/date
shape rather than inventing new tickers or dates.

Tickers, exact order:
`AAPL,MSFT,NVDA,TSM,0700.HK,1211.HK,1810.HK,3690.HK,6060.HK,9988.HK`

Decision dates, exact order:
`2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03`

Other config:
- arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- input layers: `price_only_packet`, `richer_research_packet`
- warm_up_dates: `2`
- expected backend steps: `10 tickers x 6 dates x 2 layers x 4 arms = 480`
- expected scored paired groups: `10 tickers x 4 scored dates x 2 layers = 80`

Fixtures:
- research_artifacts_path:
  `tests/fixtures/baseline_v3_1_research_artifacts.json`
- feedback_artifacts_path:
  `tests/fixtures/baseline_v3_2_feedback_artifacts.json`

## Deterministic Reference

The deterministic price-only reference is the clean historical reference. It:
- calls no LLM/backend/provider;
- uses only price rows with `date <= decision_date` for decision construction;
- uses existing outcome scoring only after decision construction;
- reports `future_rows_excluded`;
- is counted once per unique `(ticker, decision_date, horizon)` scored point.

Expected v3.4c deterministic reference count:
`10 tickers x 4 scored dates = 40`.

Input-layer mirrored equivalent count should be reported separately:
`40 unique references x 2 input layers = 80`.

Required summary fields include `clean_historical_reference_status`,
`deterministic_price_only_baseline_status`,
`deterministic_price_only_baseline_count`,
`deterministic_price_only_baseline_metrics`, and
`deterministic_price_only_baseline_future_data_violations`.

## Gate Sequence

1. Local checks:
   - `py_compile`
   - `ruff`
   - focused v3 tests
   - `git diff --check`
2. Mock/no-LLM scaled grid:
   - expected steps `480`
   - paired coverage complete or at preregistered threshold
   - future/research/feedback leak counts `0`
   - deterministic reference present with future-data violations `0`
   - Codex CLI transcript/hash counts `0`
3. Codex CLI backend canary:
   - small grid, concurrency `1`
   - same backend/model/reasoning and fixtures
   - metadata complete
4. Codex CLI scaled internal run:
   - scaled grid above
   - provider_concurrency `2`
   - max_provider_concurrency `2`
   - adaptive_concurrency `false`
   - timeout/retry: conservative v3.4 defaults, no repeated reruns to chase pass

## Interpretation Boundary

Historical `direct_llm` is
`direct_llm_parametric_memory_control`, not a clean no-future baseline. Metrics
involving direct LLM, including C1/C3/C5, returns, MSE, and direction hit rate,
are diagnostics only and must not be used to prove GOTRA, ksana, or alaya
success or failure.

Primary historical interpretation should prioritize `ksana_real_research` vs
`full_gotra` only when `true_independent_feedback_eligible_points` is sufficient.
If the eligible sample is too small, H2 must be reported as data-insufficient or
internal/inconclusive, not as alaya failure.

Completion status is separate from research verdict. A clean backend run is
internal research evidence only.
