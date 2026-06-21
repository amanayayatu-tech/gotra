# GOTRA v3.7B Verdict Report Schema Validator Prereg

Date: 2026-06-21

## Evidence Layer

This stage is `engineering/local v3.7 verdict report schema validator`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- The validator must not emit a deterministic / `full_gotra` / ksana winner.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Goal

Define and validate the target actual v3.7 verdict report schema using
local/synthetic report fixtures only. `V3_7_REPORT_SCHEMA_READY` means the
report schema and provenance validator are runnable at fixture level. It does
not mean actual v3.7 can execute.

The actual 30D path remains gated by actual readiness. Current actual readiness
is `DATA_NOT_MATURED`, so `v3_7_actual_verdict_executable=false`.

## Target Report Contract

The target report must include:

- `report_schema`
- `verdict_report_run_id`
- `source_readiness_summary_path`
- `source_readiness_summary_sha256`
- `source_scored_summary_path`
- `source_scored_summary_sha256`
- `matured_count`
- `scored_count`
- `paired_clean_count`
- `full_gotra_available_count`
- `deterministic_reference_available_count`
- `source_artifact_paths`
- `source_run_ids`
- `future_data_violation_count`
- `provenance_blocker_count`
- `pairing_blocker_count`
- `winner_emitted=false`
- `actual_30d_verdict_executed=false`
- `v3_7_actual_verdict_executable=false` unless a future actual readiness
  source is truly `READY_FOR_FORWARD_LIVE_VERDICT`
- `evidence_layer`
- `non_claims`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`

The source readiness and scored summary hashes must be 64-character sha256
hex strings. If a local file path exists, the validator must hash final file
bytes and compare them with the report value.

## Blockers

The validator must block:

- missing or malformed schema fields
- missing readiness or scored summary hashes
- hash mismatch for local source summaries
- verdict report run id mismatch against provenance
- source run id mismatch against provenance
- negative or non-integer counts
- pairing coverage inconsistency
- future-data violations
- non-zero provenance or pairing blocker counts
- forbidden source artifact paths
- winner/verdict/OOS/science/public/trading overclaim wording

Allowed statuses:

- `V3_7_REPORT_SCHEMA_READY`
- `DATA_INSUFFICIENT`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_FUTURE_DATA`
- `BLOCKED_PAIRING`
- `BLOCKED_OVERCLAIM`

`V3_7_REPORT_SCHEMA_READY` is a schema/provenance validator status only. It is
not an actual verdict and does not bypass the 2026-07-21 30D maturity gate.

## Digest Convention

The final `summary.json` digest is recorded in `manifest.json` as
`summary_sha256`; the summary does not store a self-invalidating digest field.

## Next Action

If this stage merges later, the safe follow-up is continued maturity monitoring
or additional report/dashboard hardening. A real v3.7 deterministic reference
vs `full_gotra` verdict stage requires actual readiness
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
