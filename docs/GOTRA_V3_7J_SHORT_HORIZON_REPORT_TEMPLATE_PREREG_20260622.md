# GOTRA v3.7J Short-Horizon Report Template Prereg

Date: 2026-06-22

## Evidence Layer

`short_horizon_forward_live_canary_engineering`

This stage defines a deterministic local short-horizon report
template/schema validator. It is fixture-only. It does not call providers,
Codex CLI backends, formal-lite, or any LLM. It does not execute an actual
30D v3.7 verdict.

The current 30D actual readiness remains `DATA_NOT_MATURED`.
The next 30D check remains `2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false`.

## Scope

The validator checks synthetic/local short-horizon canary report fixtures for:

- schema/version/required fields
- source run, summary hash, artifact path/hash, and provenance consistency
- short-horizon-only horizon values: `1D`, `3D`, `5D`, or `next_close`
- maturity and outcome field consistency
- explicit false runtime flags
- explicit 30D gate boundary fields
- claim-boundary text in report narrative/status fields
- final `summary.json` digest recorded in `manifest.json`

`SHORT_HORIZON_REPORT_TEMPLATE_READY` only means the local template/schema
validator is usable for engineering reports. It does not mean 30D readiness is
ready, executable, or accepted.

## Required Report Fields

Minimum fields:

- `report_schema_version`
- `source_run_id`
- `source_summary_sha256`
- `source_artifact_path`
- `source_artifact_sha256`
- `capture_timestamp`
- `horizon`
- `horizon_end_date`
- `maturity_status`
- `outcome_status`
- `decision_price`
- `outcome_price`
- `actual_change_pct`
- `actual_direction`
- `resolved_count`
- `scored_count`
- `readiness_status`
- `next_check_after`
- `blocker_reasons`
- `evidence_layer`
- `actual_30d_readiness_status`
- `actual_30d_next_check_after`
- `v3_7_actual_verdict_executable`
- `v3_7_actual_verdict_executed`
- `provider_or_backend_called`
- `codex_cli_new_call`
- `formal_lite_entered`
- `direct_llm_interpretation`
- `non_claims`
- `provenance`

## Allowed Statuses

- `SHORT_HORIZON_REPORT_TEMPLATE_READY`
- `SHORT_HORIZON_NOT_MATURED`
- `BLOCKED_DATA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `DATA_INSUFFICIENT`

Only template-ready or not-matured fixture summaries exit zero. Blocked
statuses exit nonzero.

## Non-Claims

No provider/backend run is performed. This is not an actual 30D verdict.
It makes no OOS, science, public, or trading assertion.
This is not investment advice. It is not a deterministic/full_gotra winner report. Historical
`direct_llm_parametric_memory_control` is the only allowed direct LLM label.
