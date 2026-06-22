# GOTRA v3.8H Provider Canary Authorization Gate Prereg

Date: 2026-06-22

## Purpose

v3.8H adds a deterministic local authorization gate and CI-style guard for future optional provider canary execution artifacts. This PR does not run a provider canary and does not make a backend/provider call.

This stage is engineering guard work only. It is not provider canary execution, not an actual 30D verdict, not a provider benchmark, not an OOS/science/public/trading claim, and not investment advice.

## Authorization Boundary

Future provider canary execution remains blocked unless a separate user authorization packet exists and binds:

- `user_authorization_present=true`
- authorization id and timestamp
- provider family, backend, and model
- `max_calls` and `max_tokens`
- optional cost cap if used
- `raw_tmp_only=true`
- `no_raw_repo=true`
- `usage_metadata_required=true`

Legacy provider families are not allowed unless a future user message explicitly names and authorizes that family. The guard records this as an authorization-boundary condition, not as a provider-health result.

Default future caps enforced by the gate:

- suggested calls: `<=3`
- hard call ceiling: `<=5`
- token cap: `<=25000`
- hard token ceiling encoded for schema comparison: `<=100000`
- raw payloads: `/tmp` only
- repo payload policy: hashes, metadata, status, and blocker reasons only

## Required Boundary Fields

- `evidence_layer=engineering_internal_provider_canary_authorization_gate`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`
- `provider_or_backend_called=false` for v3.8H itself
- `provider_canary_executed=false` for v3.8H itself
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Guard Rules

The guard blocks:

- provider canary execution or backend usage without a separate authorization packet
- observed calls/tokens above the authorization packet limits
- malformed observed call or token counts
- missing observed provider family, backend, or model identity when provider evidence is present
- positive token usage without matching authorization evidence
- legacy provider references without explicit named future authorization
- missing or oversized call/token budgets
- missing usage metadata for any recorded call
- partial or malformed non-claim attestations
- raw paths outside `/tmp`
- committed raw/full transcript/data artifacts
- forbidden artifact paths such as env files, DB files, bundles, backtest run directories, and paper-trading data directories
- actual 30D executable/executed/allowed field drift while readiness is `DATA_NOT_MATURED`
- claim-boundary wording that exceeds internal engineering scope
- historical direct LLM wording that is not `direct_llm_parametric_memory_control`

Allowed v3.8H statuses:

- `PROVIDER_CANARY_AUTHORIZATION_GATE_READY`
- `BLOCKED_AUTHORIZATION_BOUNDARY`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_METADATA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_SCHEMA`

## Validation Plan

- `py_compile`
- `ruff`
- focused v3.8H pytest
- local/mock guard validation to `/tmp`
- v3.7H claim-boundary regression on PR files
- docs claim-boundary scan
- relevant v3.8G/v3.8F/v3.7H/v3.7I regressions
- full pytest if acceptable
- `git diff --check`
- forbidden artifact / secret / raw scan
