# GOTRA v3.8B Real-Connection Auth Metadata Smoke Prereg

Date: 2026-06-22

## Evidence Layer

`engineering_internal_real_connection_auth_metadata_smoke`

This stage defines a bounded real-connection auth and metadata smoke harness.
It is not a ksana packet canary, not a GOTRA orchestrator run, not a provider
verdict, and not an actual 30D verdict.

The current 30D actual readiness remains `DATA_NOT_MATURED`.
The next 30D check remains `2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false`.

## Scope

The allowed backend for this stage is the current repo Codex OAuth Responses
route exposed by `gotra.backtest.codex_responses_client.CodexResponsesCompletionClient`.
No fallback to Kimi, GLM, or DeepSeek is allowed.

The real-connection path is budgeted:

- maximum real calls in this PR: `2`
- default token budget: `5000`
- hard token budget: `100000`
- raw backend metadata may be written only under `/tmp`
- repo commits may contain only code, tests, docs, hashes, and summary fields

If auth metadata is missing before HTTP, the status must be
`PROVIDER_BLOCKED_PRE_HTTP`. If the backend returns an auth failure, the status
must be `PROVIDER_AUTH_FAILED`. If a real call returns without usage metadata,
the status must be `BLOCKED_USAGE_METADATA`.

## Required Summary Fields

Minimum fields:

- `smoke_status`
- `backend_name`
- `model`
- `reasoning_effort`
- `auth_status`
- `latency_ms`
- `usage_metadata_available`
- `prompt_input_hash`
- `response_output_hash`
- `raw_response_tmp_path`
- `raw_response_sha256`
- `call_count`
- `max_call_count`
- `token_usage_input`
- `token_usage_output`
- `token_usage_total`
- `token_budget`
- `provider_or_backend_called`
- `codex_cli_called`
- `codex_cli_new_call`
- `formal_lite_entered`
- `v3_7_actual_verdict_executable`
- `v3_7_actual_verdict_executed`
- `actual_30d_readiness_status`
- `actual_30d_next_check_after`
- `evidence_layer`
- `non_claims`

## Allowed Statuses

- `REAL_CONNECTION_AUTH_READY`
- `PROVIDER_BLOCKED_PRE_HTTP`
- `PROVIDER_AUTH_FAILED`
- `BLOCKED_USAGE_METADATA`
- `BLOCKED_RUNTIME_BOUNDARY`

Only `REAL_CONNECTION_AUTH_READY` exits zero. Blocked states exit nonzero.

## Non-Claims

This is real-connection auth and metadata smoke only. It is not a research
packet, not a provider canary result, not an actual v3.7 or v3.8 verdict, and
not investment advice. It makes no OOS, science, public, or trading assertion.
