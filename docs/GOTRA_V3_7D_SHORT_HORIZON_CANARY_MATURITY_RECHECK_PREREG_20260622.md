# GOTRA v3.7D Short-Horizon Canary Maturity Recheck Prereg

Date: 2026-06-22

## Scope

v3.7D adds a deterministic/local short-horizon canary maturity recheck for
already captured short-horizon metadata. The evidence layer is
`short_horizon_forward_live_canary_engineering`.

This stage reads existing capture summary and artifact metadata, verifies source
identity and hashes, checks local daily-close availability, and writes a
structured recheck summary. It does not create a new provider, LLM, or Codex CLI
backend call.

## Non-Claims

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- Not a deterministic / `full_gotra` / ksana winner.
- Not a replacement for the 2026-07-21 30D maturity gate.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Inputs

The command accepts local paths only:

- `--source-summary`
- `--expected-source-summary-sha256`
- `--expected-source-artifact-sha256`
- `--expected-run-id`
- optional `--source-artifact`
- optional `--price-dir`
- optional `--as-of-timestamp-utc`

The source summary and source artifact are treated as immutable provenance
inputs for this recheck. The command verifies:

- source summary path is not a forbidden artifact path
- source summary sha256 matches the expected value
- source run id matches the expected run id
- source artifact path is present or discoverable
- source artifact path is not a forbidden artifact path
- source artifact sha256 matches the expected value
- source identity fields are present: run id, decision id, ticker, capture
  timestamp, horizon end date, prompt hash, and parsed decision hash
- claim-boundary text does not make OOS/science/public/trading or 30D verdict
  claims

## Maturity Logic

The local daily-close availability rule is conservative:

- before `horizon_end_date + 1 day 00:00:00Z`, status is
  `SHORT_HORIZON_NOT_MATURED`
- after that timestamp, missing local price data is `BLOCKED_DATA`
- when local decision and outcome prices are available, the command resolves a
  readable short-horizon outcome summary

The actual direction bucket is limited to `long`, `avoid`, or `neutral`.

## Status Values

Allowed summary statuses:

- `SHORT_HORIZON_READY`
- `SHORT_HORIZON_NOT_MATURED`
- `BLOCKED_DATA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `SHORT_HORIZON_RECHECK_BLOCKED_RUN_ID_EXISTS`

`SHORT_HORIZON_READY` only means the short-horizon canary outcome is locally
readable under this engineering recheck. It does not authorize 30D v3.7 verdict
execution.

## Required Summary Fields

The summary includes:

- `source_run_id`
- `source_summary_sha256`
- `source_artifact_path`
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
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `evidence_layer=short_horizon_forward_live_canary_engineering`

The final `summary.json` sha256 is recorded in `manifest.json`; the summary does
not self-hash.

## Artifact Boundary

Runtime outputs must be written to `/tmp` or another ignored output root. This
stage must not commit `data/backtest/runs/**`, `data/paper_trading/**`, raw
outputs, transcripts, `.env*`, SQLite/DB, bundle/tar/zip, or Stage8/Stage9
local artifacts.

## Next Gate

Actual 30D readiness remains governed by the actual maturity monitor. The 30D
v3.7 verdict path remains non-executable until actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
