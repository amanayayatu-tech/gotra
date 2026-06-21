# GOTRA v3.6T Forward-Live Monitor Operations Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local monitor operations only.

This stage adds a local operations ledger over actual v3.6S maturity-monitor
summaries. It does not run Kimi/GLM/DeepSeek provider APIs, does not call the
Codex CLI backend, does not run formal-lite, does not execute forward-live
experiments, and does not produce a deterministic / `full_gotra` / ksana
winner verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline.

## Base

v3.6T is stacked on the v3.6S actual maturity monitor branch/PR because PR #36
is clean but not merged at prereg time.

- Base branch: `codex/gotra-v3-6s-actual-maturity-monitor-20260621`
- Base head at branch creation: `365a52a87cb0e1dbed39a3323ffb8bf4de2fd511`
- v3.7 verdict remains blocked unless actual v3.6S/v3.6 readiness reaches a
  real `READY_FOR_FORWARD_LIVE_VERDICT` state with matching current roots.

## Command

Script:

```bash
scripts/baseline_v3_6t_forward_live_monitor_ops.py
```

Required input:

- One or more `--input-root` paths containing v3.6S actual maturity monitor
  `summary.json` files.
- The command may read a direct summary path or a directory containing previous
  monitor summaries.
- It reads only local JSON summaries and writes a new local ops run directory.

The command must not call providers, Codex CLI, formal-lite, v3.7 verdict code,
or any LLM.

## Summary Contract

The v3.6T summary includes:

- `schema`
- `ops_run_id`
- `status`
- `evidence_layer`
- `monitor_run_count`
- `latest_monitor_run_id`
- `latest_status`
- `latest_next_check_after`
- `checked_capture_run_count`
- `not_matured_count`
- `matured_candidate_count`
- `blocked_data_count`
- `resolved_count`
- `scored_count`
- `readiness_status`
- `next_stage_planning_allowed`
- `next_action_recommendation`
- `v3_7_verdict_allowed`
- `v3_7_verdict_executed=false`
- `ledger_entry_count`
- `ledger_entries`
- `latest_summary_path`
- `latest_summary_sha256`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Recommendation Contract

- No monitor summaries: `DATA_INSUFFICIENT` and `FIX_BLOCKER`.
- Latest `DATA_NOT_MATURED` before `next_check_after`:
  `WAIT_UNTIL_NEXT_CHECK`, even if an optional readiness summary is already
  stale/ready. Immature horizons take precedence over readiness repair.
- Latest `DATA_NOT_MATURED` at or after `next_check_after`:
  `RECHECK_NOW_ALLOWED`.
- Latest `BLOCKED_DATA`, `BLOCKED_SOURCE_FUTURE_DATA`, invalid provenance, or
  monitor failure: `FIX_BLOCKER`; the CLI exits non-zero for these hard-blocked
  latest monitor statuses.
- Latest `RESOLVER_PATH_ELIGIBLE` without
  `READY_FOR_FORWARD_LIVE_VERDICT`: `FIX_BLOCKER`, because the readiness chain
  is missing or incomplete and a maturity recheck alone is not enough.
- `READY_FOR_FORWARD_LIVE_VERDICT` from a monitor summary is not enough by
  itself. v3.6T only allows v3.7 planning when the latest v3.6S summary also
  has current monitor eligibility:
  `status=RESOLVER_PATH_ELIGIBLE`, `resolver_path_eligible=true`,
  `next_stage_planning_allowed=true`, and `v3_7_verdict_executed=false`.
- Even when planning is allowed, v3.6T never executes v3.7 verdict logic.

## Artifact Boundary

The ops ledger output is a local runtime artifact and must not be committed
under `data/backtest/runs/**`. Docs may record run ids, summary paths, and
summary hashes only.

## Next Stage Boundary

If the latest actual status remains `DATA_NOT_MATURED`, the next action is a
future maturity recheck. If the latest actual status is `BLOCKED_DATA` or
another blocker, the next action is data/provenance repair. Only a real, current
actual `READY_FOR_FORWARD_LIVE_VERDICT` state can allow planning a separate
preregistered v3.7 verdict stage.
