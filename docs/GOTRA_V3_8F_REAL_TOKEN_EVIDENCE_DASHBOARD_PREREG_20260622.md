# GOTRA v3.8F Real-Token Evidence Dashboard Prereg

Date: 2026-06-22

## Purpose

v3.8F builds a deterministic local dashboard and validator for the v3.8 real-connection sweep. It summarizes the engineering evidence from v3.8B, v3.8C, v3.8D, and v3.8E without making a new provider/backend call.

This stage is an internal evidence dashboard only. It is not an actual 30D verdict, not a provider benchmark, not an orchestrator verdict, not an OOS/science/public/trading claim, and not investment advice.

## Fixed Inputs

- v3.8B / PR #66: `REAL_CONNECTION_AUTH_READY`, backend/model `codex_responses_oauth_backend` / `gpt-5.5`, real calls `1`, token usage `86`, latency `3680ms`, merge commit `e974420eb2090f541f20d694444d184019f82dca`.
- v3.8C / PR #67: `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS`, backend/model `codex_responses_oauth_backend` / `gpt-5.5`, real calls `3`, token usage `6518`, latency `24065/26041/24631ms`, schema pass rate `1.0`, overclaim rate `0.0`, missing-field rate `0.0`, merge commit `9d554e48294e74f9af22a72c93bab6f3c6c8c37a`.
- v3.8D / PR #68: `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS`, backend/model `codex_responses_oauth_backend` / `gpt-5.5`, real calls `3`, token usage `6765`, latency `24152/25517/26395ms`, merge commit `b92be9870db661dd27015f4e8dcccd5d7235541e`.
- v3.8E / PR #69: `REAL_TOKEN_FAILURE_MODE_SUITE_PASS`, controlled/local failure suite, real calls `0`, token usage `0`, latency summary `40/47/1000ms`, failure cases `12/12` handled, merge commit `cce6cec18ba856d986e8144d8e7915c37d6c9822`.

Raw provider/backend payloads remain `/tmp` only. The repo stores only code, tests, docs, hashes, status fields, and boundary metadata.

## Required Boundary Fields

- `evidence_layer=engineering_internal_real_connection_evidence_dashboard`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false` for v3.8F itself
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Validator Rules

The validator blocks malformed dashboard summaries, missing source stages, source merge/status mismatches, non-`/tmp` raw paths, legacy backend references, unsafe runtime flags, inconsistent source call/token totals, parametric-memory interpretation drift, and text that tries to upgrade engineering evidence into an actual 30D verdict or claim-boundary overreach.

Allowed statuses:

- `REAL_CONNECTION_EVIDENCE_DASHBOARD_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_PROVENANCE`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`

## Validation Plan

- `py_compile`
- `ruff`
- focused v3.8F pytest
- local/mock dashboard validation to `/tmp`
- v3.7H claim-boundary regression on PR files
- docs claim-boundary scan
- relevant v3.8B/v3.8C/v3.8D/v3.8E/v3.7H/v3.7I regressions
- full pytest if acceptable
- `git diff --check`
- forbidden artifact / secret / raw scan
