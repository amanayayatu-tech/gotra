# GOTRA v3.6Z Short-Horizon Outcome Recheck Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `short_horizon_forward_live_canary_engineering`.

This stage adds a local outcome maturity/recheck command for the already
captured v3.6Y 1D short-horizon canary. It reads committed code plus local
metadata from the v3.6Y run summary and capture artifact. It does not run
Kimi/GLM/DeepSeek providers, does not run Codex CLI again, does not run
formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Source Contract

The command requires explicit source identity inputs:

- `--source-summary`
- `--expected-source-summary-sha256`
- `--expected-run-id`

For the v3.6Y source canary:

- Source run id:
  `baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z`
- Source summary:
  `/tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs/baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/summary.json`
- Expected source summary sha256:
  `c40ecbe021afcd313abb896616e5dcd79329465c73496ccbf118f789f4682da9`
- Source backend metadata: `codex_cli_llm_backend`, `codex-cli 0.141.0`,
  `gpt-5.5`, reasoning `high`

v3.6Z itself must not make a new Codex CLI or provider call. The source summary
may record that v3.6Y historically called Codex CLI, but v3.6Z summary fields
must keep `provider_or_backend_called=false`, `codex_cli_new_call=false`, and
`formal_lite_entered=false`.

## Guard Rules

The recheck must block with `BLOCKED_PROVENANCE` when:

- source summary is missing or malformed
- source summary hash differs from the expected hash
- source run id differs from the expected run id
- source summary is not a passing v3.6Y capture summary
- source capture artifact is missing
- prompt hash, parsed decision hash, transcript path metadata, or core
  decision artifact identity is missing

The recheck must return `SHORT_HORIZON_NOT_MATURED` when the horizon close is not
yet available under the daily-close rule. Daily close for date D is available at
D+1 `00:00:00Z`. For the source canary, `horizon_end_date=2026-06-22`, so the
first allowed check time is `2026-06-23T00:00:00Z`.

The recheck must return `BLOCKED_DATA` when the horizon is mature but required
decision/outcome price data is missing.

The recheck may return `SHORT_HORIZON_READY` only when this single short-horizon
canary outcome is readable and locally scored. That status is not a 30D
readiness status, not a verdict, and does not authorize v3.7.

Actual direction buckets are restricted to the v3/v3.5 contract:
`long`, `avoid`, and `neutral`.

## Summary Fields

The output summary includes:

- `source_run_id`
- `source_summary_sha256`
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
- `evidence_layer=short_horizon_forward_live_canary_engineering`
- `v3_7_30d_verdict_allowed=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Next Boundary

v3.6Z can monitor only the short-cycle canary. The 30D path remains governed by
the actual v3.6S/v3.6T monitor/readiness chain. v3.7 remains blocked unless true
30D actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance.
