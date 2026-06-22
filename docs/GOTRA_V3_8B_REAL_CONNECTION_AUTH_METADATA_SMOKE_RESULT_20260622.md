# GOTRA v3.8B Real-Connection Auth Metadata Smoke Result

Date: 2026-06-22

## Evidence Layer

`engineering_internal_real_connection_auth_metadata_smoke`

This result records the bounded auth/metadata smoke harness. It does not create
a ksana packet, run the GOTRA orchestrator, enter formal-lite, or execute an
actual 30D verdict.

## Current Boundary

- actual 30D readiness: `DATA_NOT_MATURED`
- actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- historical direct LLM label remains `direct_llm_parametric_memory_control`

## Implemented Surface

Added:

- `scripts/baseline_v3_8b_real_connection_auth_metadata_smoke.py`
- `tests/test_v3_8b_real_connection_auth_metadata_smoke.py`

The harness enforces:

- allowed backend is the repo Codex OAuth Responses route only
- no fallback to Kimi, GLM, or DeepSeek
- maximum call count and token budget checks
- auth/pre-HTTP blocker state before any network call when auth metadata is not
  available
- auth failure and usage-metadata failure states
- raw response metadata path restricted to `/tmp`
- secret redaction and summary secret scan
- claim-boundary scan for summary narrative/status fields
- deterministic summary/manifest digest convention

## Local Validation

Initial focused validation completed:

- `uv run python -m py_compile scripts/baseline_v3_8b_real_connection_auth_metadata_smoke.py`: pass
- `uv run ruff check --no-cache scripts/baseline_v3_8b_real_connection_auth_metadata_smoke.py tests/test_v3_8b_real_connection_auth_metadata_smoke.py`: pass
- `uv run pytest -q tests/test_v3_8b_real_connection_auth_metadata_smoke.py`: `10 passed`
- relevant v3.7/v3.8 readiness/claim-boundary regression set: `244 passed`
- full pytest: `803 passed`

Local mock validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8b_mock_validation_20260622T033500Z/runs/baseline_v3_8b_real_connection_auth_metadata_smoke_mock_20260622T033500Z/summary.json`
- status: `REAL_CONNECTION_AUTH_READY`
- summary sha256:
  `605556fa472dcd965b7aa9074db249c6914bf66653989e1b55462020c85985b5`

Real-connection validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8b_real_validation_20260622T033800Z/runs/baseline_v3_8b_real_connection_auth_metadata_smoke_real_20260622T033800Z/summary.json`
- status: `REAL_CONNECTION_AUTH_READY`
- summary sha256:
  `3ad2be31ebd215f6d7fb12f70977418a14ef784a50fe05addb4c60e1030e3447`
- backend/model: `codex_responses_oauth_backend` / `gpt-5.5`
- call count: `1`
- token usage total: `86`
- latency: `3680 ms`
- raw metadata path:
  `/tmp/gotra_v3_8b_real_validation_20260622T033800Z/runs/baseline_v3_8b_real_connection_auth_metadata_smoke_real_20260622T033800Z/raw_response_metadata.json`
- raw metadata sha256:
  `3e5f33705813172231bef18d7acf33137b2963eea153bf98e23631c832877ae6`
- runtime flags: `provider_or_backend_called=true`,
  `codex_cli_called=false`, `codex_cli_new_call=false`,
  `formal_lite_entered=false`
- docs claim-boundary scan:
  `/tmp/gotra_v3_8b_claim_scan_20260622T034500Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_8b_docs_20260622T034500Z/summary.json`
- docs claim-boundary status: `CLAIM_BOUNDARY_CLEAN`

Diff check and staged artifact/secret scans are recorded in the final PR report
after staging.

## Non-Claims

This is engineering/internal auth and metadata smoke only. It is not a research
packet, not a provider canary result, not an actual v3.7 or v3.8 verdict, and
not investment advice. It makes no OOS, science, public, or trading assertion.
