# GOTRA v3.8D Orchestrator Real-Token Dry-Run Prereg

Date: 2026-06-22

## Evidence Layer

`engineering_internal_gotra_orchestrator_real_token_dry_run`

This stage is a bounded real-token dry-run of GOTRA orchestration wiring using
only synthetic/local company briefs. It exercises the path from input fixture to
ksana packet v2 schema validation, provenance/hash checks, claim-boundary checks,
and a dry-run summary. It is not an actual v3.7 or v3.8 verdict, not 30D
readiness, not a provider benchmark, not an OOS/science/public/trading claim,
and not investment advice.

The current actual 30D readiness remains `DATA_NOT_MATURED`.
The next actual 30D check remains `2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false`.

## Runtime Scope

Allowed backend:

- backend: `codex_responses_oauth_backend`
- model: `gpt-5.5`
- reasoning effort: `xhigh`

The dry-run must not fall back to Kimi, GLM, or DeepSeek. It must not enter
formal-lite and must not invoke Codex CLI backend experiments.

Budget:

- default real calls: `3`
- maximum real calls: `5`
- default token budget: `25000`
- hard token budget: `100000`

If usage metadata is unavailable, the status must be `BLOCKED_METADATA` or a
runtime-boundary blocker. The run must not increase call count to compensate.

## Artifact Boundary

Raw backend responses, parsed packets, and intermediate dry-run traces may be
written only under `/tmp`. Repo commits may contain code, tests, docs, schema,
hashes, usage metadata, latency metadata, status fields, and blocker reasons.

Forbidden repo artifacts remain blocked:

- `data/backtest/runs/**`
- `data/paper_trading/**`
- raw outputs or transcripts
- `.env*`
- SQLite or DB files
- bundle, tar, or zip files
- Stage8 or Stage9 artifacts

## Required Summary Surface

The dry-run summary must record:

- run id and timestamp
- backend, model, API/client version if available
- requested and actual call count
- token usage total and per-call latency
- usage availability
- prompt/input hashes
- raw response `/tmp` paths and sha256 values
- parsed packet `/tmp` paths and sha256 values
- orchestrator trace `/tmp` paths and sha256 values
- source artifact paths and hashes
- schema, claim-boundary, provenance/hash, metadata, runtime, artifact, and
  secret boundary statuses
- runtime flags:
  - `provider_or_backend_called=true/false` according to actual execution
  - `codex_cli_new_call=false`
  - `codex_cli_called=false`
  - `formal_lite_entered=false`
  - `v3_7_actual_verdict_executable=false`
  - `v3_7_actual_verdict_executed=false`
  - `actual_30d_verdict_executed=false`

The dry-run must not score outcomes, compare real outcomes, emit a comparative
result, or authorize an actual 30D verdict.

## Allowed Statuses

- `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_METADATA`
- `BLOCKED_RUNTIME_BOUNDARY`
- `PROVIDER_AUTH_FAILED`
- `PROVIDER_BLOCKED_PRE_HTTP`

Only `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS` exits zero.

## Non-Claims

This stage only checks bounded engineering wiring and metadata integrity. It is
not a research conclusion, not public proof, not trading guidance, not a model
quality claim, and not a maturity-gate bypass.

Historical `direct_llm` remains `direct_llm_parametric_memory_control` and must
not be described as a clean no-future baseline.
