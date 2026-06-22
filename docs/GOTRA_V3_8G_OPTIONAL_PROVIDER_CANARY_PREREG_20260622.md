# GOTRA v3.8G Optional Provider Canary Prereg

Date: 2026-06-22

## Purpose

v3.8G adds a deterministic local prereg, runbook, and schema validator for a future optional bounded provider canary. This PR does not run a canary and does not make a backend/provider call.

This stage is engineering prep only. It is not an actual 30D verdict, not a provider benchmark, not a model-comparison result, not an OOS/science/public/trading claim, and not investment advice.

## Authorization Boundary

A future canary may only run after separate user authorization that names the provider family, backend, model, max call count, token cap, and raw-output handling rules. Legacy provider families are not allowed by this prereg unless a future user message explicitly names and authorizes that family.

Default future caps encoded by the prereg:

- suggested calls: `<=3`
- hard call ceiling: `<=5`
- suggested token cap: `<=25000`
- hard token ceiling: `<=100000`
- raw payloads: `/tmp` only
- repo payload policy: hashes, metadata, status, and blocker reasons only
- usage metadata: required; missing usage stays blocked

## Required Boundary Fields

- `evidence_layer=engineering_internal_provider_canary_prereg_only`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Validator Contract

The validator blocks:

- missing explicit future-user authorization requirement
- prereg-only summaries that set provider/backend, Codex CLI, formal-lite, or actual-verdict flags to true
- missing or oversized call/token caps
- raw-output locations outside `/tmp`
- repo raw-output policy drift
- missing usage-metadata requirement
- 30D readiness or executable-field drift
- old provider families without separate future authorization
- forbidden/raw artifact paths
- claim-boundary text that exceeds engineering prereg scope
- direct LLM wording that is not `direct_llm_parametric_memory_control`

Allowed v3.8G summary statuses:

- `PROVIDER_CANARY_PREREG_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_AUTHORIZATION_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`

## Validation Plan

- `py_compile`
- `ruff`
- focused v3.8G pytest
- local/mock prereg validation to `/tmp`
- v3.7H claim-boundary regression on PR files
- docs claim-boundary scan
- relevant v3.8F/v3.7H/v3.7I/v3.8B-E regressions
- full pytest if acceptable
- `git diff --check`
- forbidden artifact / secret / raw scan
