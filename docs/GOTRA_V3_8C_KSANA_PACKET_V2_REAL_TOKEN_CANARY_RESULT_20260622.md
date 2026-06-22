# GOTRA v3.8C Ksana Packet V2 Real-Token Schema Canary Result

Date: 2026-06-22

## Evidence Layer

`engineering_internal_ksana_packet_v2_real_token_schema_canary`

This result records a bounded real-token schema canary for ksana packet v2 using
synthetic/local company briefs. It is not a provider canary verdict, not a
GOTRA orchestrator run, not an actual v3.7 or v3.8 verdict, not an OOS/science/public/trading claim, and not investment advice.

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

- `scripts/baseline_v3_8c_ksana_packet_v2_real_token_canary.py`
- `tests/test_v3_8c_ksana_packet_v2_real_token_canary.py`

The harness enforces:

- allowed backend/model are `codex_responses_oauth_backend` / `gpt-5.5`
- no fallback to Kimi, GLM, or DeepSeek
- default `3` real calls, hard maximum `5`
- token usage budget and hard limit checks
- raw responses and parsed packets restricted to `/tmp`
- required packet v2 schema fields and non-empty structured lists
- claim-boundary scan for generated packet text and summary fields
- provenance/hash metadata for each call
- usage metadata required for pass status
- secret redaction and summary secret scan
- final `summary.json` digest stored in `manifest.json`

## Local Mock Validation

Local validation before the real-token canary:

- `py_compile`: pass
- `ruff`: pass
- focused v3.8C pytest: `11 passed`
- relevant v3.7/v3.8 readiness, packet, provenance, claim-boundary, and
  merge-readiness regression: `255 passed`
- full pytest: `814 passed`

Mock validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8c_mock_validation_20260622T035112Z/runs/baseline_v3_8c_ksana_packet_v2_real_token_canary_mock_20260622T035112Z/summary.json`
- summary sha256:
  `2c358e4c2eeec86946a21ce80a2a509ddd0d1f9e832b0e5fc8a45b2b8d81d959`
- status: `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS`
- call count shape: `3`
- token usage total: `36`

## Real-Token Canary Validation

Real-token validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8c_real_validation_20260622T035129Z/runs/baseline_v3_8c_ksana_packet_v2_real_token_canary_real_20260622T035129Z/summary.json`
- summary sha256:
  `0ead1b71828e8924bbb6ea03d526b408bc0425f873d81849e27138fa0b534a74`
- status: `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS`
- backend/model: `codex_responses_oauth_backend` / `gpt-5.5`
- real calls count: `3`
- token usage total: `6518`
- latency ms values: `24065`, `26041`, `24631`
- schema pass rate: `1.0`
- overclaim rate: `0.0`
- missing-field rate: `0.0`
- usage availability rate: `1.0`
- raw response sha256s:
  - `1590ee12c475ff14718d80b0e59f073b4ff811c66e7a6f7a554f9266af88e0f9`
  - `de5d34d7ad7173cd2f96ca3acf25e8cca52f6757349196df10a9e6558d10e1d5`
  - `afc88e5a7a0095be3bcdf5ea205bede3b36e0624068234ef03133ce172101844`
- parsed packet sha256s:
  - `c23d37456e9f2b7a89be5cee4597f7b064895a433ff30624f8f9b686046e776c`
  - `b7d0ea39f21d91b2b13eb4846a35e5e66778e5769d2aad58bbb1d0e56c5da941`
  - `69a0b7d0dd53207d2a0107a2ce30e0fb3a8622c2e97e244af78b1dd3d949d6b1`

Runtime boundary:

- raw response handling: `/tmp` only
- repo commits: code/tests/docs plus hashes and summary fields only
- `provider_or_backend_called=true`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`

Docs claim-boundary scan:

- summary:
  `/tmp/gotra_v3_8c_claim_scan_20260622T035613Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_8c_docs_20260622T035613Z/summary.json`
- summary sha256:
  `007de7ad0b94f295397d5c8ae985a0e245849e46d0d337d91a4a86f3525c0887`
- status: `CLAIM_BOUNDARY_CLEAN`

## Review Hardening

PR #67 review hardening removed source-code wording that v3.7H treats as
claim-boundary regression text. No additional real-token calls were made.

v3.7H claim-boundary regression over the PR files:

- summary:
  `/tmp/gotra_v3_8c_claim_regression_repair_20260622T040907Z/baseline_v3_7h_claim_boundary_regression_repair_v3_8c_20260622T040907Z/summary.json`
- summary sha256:
  `d73b6afb0b69f69a7b0b3631e5d5b4175b971a474f12fdb61f6a83557c0ea85e`
- status: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- blockers: `0`

## Non-Claims

This is engineering/internal schema canary evidence only. It does not compare
model quality, does not score outcomes, does not produce a research verdict,
and does not authorize the actual 30D v3.7 verdict.
