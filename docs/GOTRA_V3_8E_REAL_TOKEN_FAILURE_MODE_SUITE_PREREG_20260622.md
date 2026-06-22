# GOTRA v3.8E Real-Token Failure-Mode Suite Preregistration

Date: 2026-06-22

## Evidence Layer

`engineering_internal_real_token_failure_mode_suite`

This stage adds a bounded failure-mode suite for the real-token connection path.
It is engineering/internal evidence only. It is not an actual v3.7 or v3.8
verdict, not 30D readiness, not a provider benchmark, not an OOS/science/public/trading claim, and not investment advice.

## Boundary

- actual 30D readiness remains `DATA_NOT_MATURED`
- actual 30D next check remains `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- historical direct LLM label remains `direct_llm_parametric_memory_control`

## Goal

Validate that controlled failure modes are handled deterministically without
leaking secrets, writing raw payloads into the repository, entering formal-lite,
or expanding real backend calls. Real probes are optional and budget-gated; the
default local validation path is controlled fixture handling with zero backend
calls.

## Required Failure Cases

The suite must cover:

- missing auth/key or pre-http block
- auth failure with redaction
- timeout handling without retry expansion
- malformed response
- empty response
- missing usage metadata
- provider error handling
- raw/error payload path outside `/tmp`
- over-budget call/token/retry behavior
- unsafe runtime flags
- future-data metadata violation
- status-like or narrative boundary overclaim

## Allowed Statuses

- `REAL_TOKEN_FAILURE_MODE_SUITE_PASS`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_METADATA`
- `BLOCKED_RUNTIME_BOUNDARY`
- `PROVIDER_AUTH_FAILED`
- `PROVIDER_BLOCKED_PRE_HTTP`
- `PROVIDER_TIMEOUT_HANDLED`
- `PROVIDER_ERROR_HANDLED`

`REAL_TOKEN_FAILURE_MODE_SUITE_PASS` means every configured failure case was
handled safely. It does not mean a provider canary passed and does not authorize
any actual verdict.

## Runtime Limits

- default controlled mode: `0` real calls
- suggested real probe range, if explicitly enabled in a later task: `0-2`
- hard real-call ceiling: `3`
- default token budget: `25000`
- hard token ceiling: `100000`
- retry ceiling: `1`
- raw/error payloads: `/tmp` only
- repository commits: code, tests, docs, schemas, hashes, statuses, and metadata
  only

## Summary Contract

The summary must include:

- `failure_suite_run_id`
- `suite_status`
- `evidence_layer`
- case counts and per-case statuses
- `real_calls_count`
- `token_usage_total`
- `retry_count_total`
- latency summary
- raw tmp paths and hashes, when any redacted payload exists
- provider/backend/model metadata
- explicit runtime flags
- 30D maturity boundary fields
- `non_claims`
- final `summary.json` digest in `manifest.json`

## Non-Claims

This stage does not run a GOTRA orchestrator experiment, does not produce a
research packet result, does not compare providers, does not use actual 30D
outcomes, and does not produce any public or trading conclusion.
