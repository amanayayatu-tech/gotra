# GOTRA v3.7A Fixture Verdict Harness Dry-Run Prereg

Date: 2026-06-21

## Evidence Layer

This stage is `engineering/local v3.7 fixture-only harness dry-run`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- The harness must not emit a deterministic / `full_gotra` / ksana winner.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Goal

Prepare the v3.7 verdict harness shape with synthetic/local fixtures only. This
stage proves that schema, pair identity, provenance, future-data, and claim
guards can run at fixture level before the actual 30D forward-live data matures.

The 30D actual path remains gated by actual readiness. As of this prereg, the
actual 30D readiness state is `DATA_NOT_MATURED`, so
`v3_7_actual_verdict_executable=false`.

## Fixture Contract

Each row must be a local/synthetic fixture object with:

- `fixture_kind`: `deterministic_reference` or `full_gotra`
- `ticker`
- `decision_date`
- `horizon_days`
- `source_run_id`
- `source_hash` or `source_artifact_sha256`
- `source_artifact_path`
- `future_data_violation=false`
- `provenance.source_run_id`
- `provenance.source_hash` or `provenance.source_artifact_sha256`
- `provenance.source_artifact_path`

Rows are paired only by `(ticker, decision_date, horizon_days)`. Each pair key
must have exactly one deterministic reference row and exactly one `full_gotra`
row. Duplicate or unpaired rows are blockers.

## Blockers

The dry-run must block:

- missing deterministic fixture
- missing `full_gotra` fixture
- unpaired rows
- duplicate pair keys
- future-data violation
- missing or mismatched provenance
- missing source hash
- schema-unsafe rows
- winner/verdict/overclaim wording

Allowed statuses:

- `V3_7_FIXTURE_HARNESS_READY`
- `DATA_INSUFFICIENT`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_FUTURE_DATA`
- `BLOCKED_PAIRING`
- `BLOCKED_OVERCLAIM`

`V3_7_FIXTURE_HARNESS_READY` means only that synthetic fixtures are pairable and
guard-clean. It does not authorize actual v3.7 execution.

## Summary Fields

The summary must include at least:

- `harness_status`
- `fixture_pair_count`
- `deterministic_fixture_count`
- `full_gotra_fixture_count`
- `paired_clean_count`
- `duplicate_pair_count`
- `future_data_violation_count`
- `provenance_blocker_count`
- `schema_blocker_count`
- `winner_emitted=false`
- `actual_30d_verdict_executed=false`
- `v3_7_actual_verdict_executable=false`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `evidence_layer=engineering/local v3.7 fixture-only harness dry-run`
- `non_claims`

The final `summary.json` digest is recorded in `manifest.json` as
`summary_sha256`; the summary does not store a self-invalidating digest field.

## Next Action

If this stage merges later, the safe follow-up is still actual maturity
monitoring and separate fixture/report hardening. A real 30D v3.7 verdict stage
must wait until actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with
matching provenance.
