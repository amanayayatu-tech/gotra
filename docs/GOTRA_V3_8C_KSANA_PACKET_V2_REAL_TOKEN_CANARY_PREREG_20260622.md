# GOTRA v3.8C Ksana Packet V2 Real-Token Schema Canary Prereg

Date: 2026-06-22

## Evidence Layer

`engineering_internal_ksana_packet_v2_real_token_schema_canary`

This stage is a bounded real-token schema canary for the ksana packet v2
contract. It uses only synthetic/local company briefs. It is not a provider
canary verdict, not a GOTRA orchestrator run, not an actual v3.7 or v3.8
verdict, not an OOS/science/public/trading claim, and not investment advice.

The current actual 30D readiness remains `DATA_NOT_MATURED`.
The next actual 30D check remains `2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false`.

## Runtime Scope

Allowed backend:

- `codex_responses_oauth_backend`
- model: `gpt-5.5`
- reasoning effort: `xhigh`

No fallback to Kimi, GLM, or DeepSeek is allowed. The stage does not enter
formal-lite and does not invoke Codex CLI backend experiments.

Budget:

- default real calls: `3`
- maximum real calls: `5`
- default token budget: `25000`
- hard token budget: `100000`

Raw provider/backend responses and parsed packet files may be written only under
`/tmp`. Repo commits may contain code, tests, docs, summary fields, hashes,
usage, latency, and blocker reasons only.

## Packet V2 Fields

Each generated packet must satisfy the v2 contract:

- `ranked_hypotheses`
- `why_it_matters`
- `confidence`
- `falsification_triggers`
- `expected_observable_evidence`
- `counterfactuals`
- `disagreement_with_price_only`
- `evidence_gaps`
- `uncertainty_decomposition`
- `non_claims`
- `evidence_layer=engineering_internal_ksana_packet_v2_real_token_schema_canary`
- `provenance`
- `provider_or_backend_called=false` inside the packet payload
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

The stage summary records the real backend call boundary separately:
`provider_or_backend_called=true` if any real call is made.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it must
not be described as a clean no-future baseline.

## Required Per-Call Metadata

Each real call must record:

- run id and call id
- backend and model
- SDK/API version if available
- prompt hash
- input fixture hash
- raw response `/tmp` path and sha256
- parsed packet `/tmp` path and sha256
- schema status
- claim-boundary status
- provenance/hash status
- latency in milliseconds
- token usage
- blocker reasons

If usage metadata is unavailable after a call, the stage reports
`BLOCKED_METADATA` and does not expand the call count.

## Allowed Statuses

- `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_METADATA`
- `BLOCKED_RUNTIME_BOUNDARY`

Only `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS` exits zero.

## Non-Claims

This preregistered stage only checks whether a synthetic/local brief can produce
a schema-clean packet v2 structure through the allowed backend under a tight
metadata budget. It does not compare models, does not score outcomes, does not
emit a winner, and does not authorize the actual 30D verdict.
