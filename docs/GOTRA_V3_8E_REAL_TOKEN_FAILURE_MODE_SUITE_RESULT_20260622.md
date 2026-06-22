# GOTRA v3.8E Real-Token Failure-Mode Suite Result

Date: 2026-06-22

## Evidence Layer

`engineering_internal_real_token_failure_mode_suite`

This result records a deterministic controlled failure-mode suite for the
real-token connection path. It is engineering/internal evidence only. It is not
an actual v3.7 or v3.8 verdict, not 30D readiness, not a provider benchmark, not an OOS/science/public/trading claim, and not investment advice.

## Current Boundary

- actual 30D readiness: `DATA_NOT_MATURED`
- actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `actual_30d_verdict_executed=false`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- historical direct LLM label remains `direct_llm_parametric_memory_control`

## Implemented Surface

Added:

- `scripts/baseline_v3_8e_real_token_failure_mode_suite.py`
- `tests/test_v3_8e_real_token_failure_mode_suite.py`

The harness enforces:

- allowed backend/model metadata are `codex_responses_oauth_backend` /
  `gpt-5.5`
- no fallback to Kimi, GLM, or DeepSeek
- controlled failure suite defaults to zero real backend calls
- hard maximum real calls is `3`
- retry ceiling is `1`
- token budget and hard token limit checks
- raw/error payloads restricted to `/tmp`
- provider, Codex CLI, formal-lite, and actual verdict flags explicitly checked
- future-data metadata blocker handling
- summary and per-case claim-boundary checks
- secret redaction and summary secret scan
- final `summary.json` digest stored in `manifest.json`

## Local Controlled Validation

Local controlled validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8e_failure_mode_suite_mock_20260622T052000Z/runs/baseline_v3_8e_real_token_failure_mode_suite_mock_20260622T052000Z/summary.json`
- summary sha256:
  `983f4d9a5f8fcfa03dd872d01f58677733e2e1264c0a63a042b8a499ec044a6d`
- manifest sha256:
  `8139b2dd6eacd61a7963038e2199c29b40a29fd0a46afeceec119546a7cb69ff`
- status: `REAL_TOKEN_FAILURE_MODE_SUITE_PASS`
- total cases: `12`
- passed cases: `12`
- blocked cases: `0`
- real calls count: `0`
- token usage total: `0`
- retry count total: `1`
- latency min/median/max ms: `40` / `47` / `1000`
- backend/model metadata: `codex_responses_oauth_backend` / `gpt-5.5`
- provider/backend called: `false`
- raw/error payload handling: `/tmp` only

Case status counts:

- `PROVIDER_BLOCKED_PRE_HTTP`: `1`
- `PROVIDER_AUTH_FAILED`: `1`
- `PROVIDER_TIMEOUT_HANDLED`: `1`
- `PROVIDER_ERROR_HANDLED`: `1`
- `BLOCKED_METADATA`: `1`
- `BLOCKED_SCHEMA`: `2`
- `BLOCKED_RUNTIME_BOUNDARY`: `4`
- `BLOCKED_OVERCLAIM`: `1`

Redacted raw/error payload hashes:

- `282c72180ef71c9570b03f43d4817c675df038c2d8093d21a4ac9bac19ddf1e0`
- `e775ebb50b23026479a5a364fb20a12e0969294a11b5131a151e27ed06f488fa`

Content boundary digest:

- `bcf83c7469d452efeb766f3b37a8715db482954b0c2dc49594f461414df5fc23`

## Focused Tests

The focused test suite covers:

- controlled missing auth / pre-http block handling
- redacted auth failure
- timeout handling without retry expansion
- malformed, empty, and usage-missing response cases
- provider error handling with `/tmp` payloads
- raw/error path outside `/tmp`
- call/retry budget blocking
- unsafe runtime flags and future-data metadata
- status-like overclaim blocking
- old provider metadata blocking
- blocked CLI exit semantics
- final manifest digest verification

Validation results:

- `py_compile`: pass
- `ruff`: pass
- focused v3.8E pytest: `12 passed`
- relevant v3.8B/v3.8C/v3.8D/v3.7G/v3.7H/v3.7I regression:
  `101 passed`
- full pytest: `847 passed`

Docs claim-boundary scan:

- summary:
  `/tmp/gotra_v3_8e_claim_scan_20260622T052900Z/baseline_v3_6ab_evidence_claim_boundary_scan_v3_8e_docs_20260622T052900Z/summary.json`
- summary sha256:
  `d0f5e32f03054e8feaeba91585c1edeaf40cbce08fae7dfa2eafac99bee55f1c`
- status: `CLAIM_BOUNDARY_CLEAN`
- blockers: `0`

v3.7H claim-boundary regression over the PR files:

- summary:
  `/tmp/gotra_v3_8e_claim_regression_20260622T052900Z/baseline_v3_7h_claim_boundary_regression_v3_8e_20260622T052900Z/summary.json`
- summary sha256:
  `9b30ce0b4da35b16965bf8655eb62c1d049b859ca1dd2844b097d133c906aa74`
- status: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- blockers: `0`

## Non-Claims

This result does not score outcomes, does not produce a research result, does
not compare providers, does not execute any 30D verdict, and does not authorize
the actual v3.7 verdict gate.
