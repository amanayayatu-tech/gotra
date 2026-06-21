# GOTRA v3.6T Forward-Live Monitor Operations Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local monitor operations only.

This result records a local operations ledger over actual v3.6S maturity
monitor summaries. It does not run Kimi/GLM/DeepSeek provider APIs, does not
call the Codex CLI backend, does not run formal-lite, does not execute
forward-live experiments, and does not produce a deterministic / `full_gotra` /
ksana winner verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base branch: `codex/gotra-v3-6s-actual-maturity-monitor-20260621`
- Base head: `365a52a87cb0e1dbed39a3323ffb8bf4de2fd511`
- Branch: `codex/gotra-v3-6t-forward-live-monitor-ops-20260621`

## Implementation Summary

Added:

- `scripts/baseline_v3_6t_forward_live_monitor_ops.py`
- `tests/test_forward_live_monitor_ops.py`

The command reads one or more v3.6S actual maturity monitor summaries, builds a
deterministically ordered ledger, selects the latest monitor summary, and emits
a compact operations summary. It preserves prior monitor run identity by
recording each input summary path and sha256.

The command never calls provider APIs, Codex CLI, formal-lite, or v3.7 verdict
logic.

Review hardening added after PR #37 self-audit:

- `DATA_NOT_MATURED` keeps wait/recheck semantics even when an optional
  readiness summary is stale/ready.
- `RESOLVER_PATH_ELIGIBLE` without
  `READY_FOR_FORWARD_LIVE_VERDICT` is a readiness-chain blocker and returns
  `FIX_BLOCKER`, not `RECHECK_NOW_ALLOWED`.
- CLI exit semantics now return non-zero for hard-blocked latest monitor
  statuses such as `BLOCKED_DATA`, `BLOCKED_SOURCE_FUTURE_DATA`, and
  `MONITOR_FAIL`.

## Summary Schema

Key summary fields:

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
- `latest_summary_path`
- `latest_summary_sha256`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Actual Monitor Operations Recheck

The actual recheck was run in two local steps. First v3.6S produced a fresh
actual maturity monitor summary from local `data/backtest/runs`. Then v3.6T
read that summary and produced the operations ledger.

v3.6S command:

```bash
uv run python scripts/baseline_v3_6s_actual_maturity_monitor.py \
  --input-root data/backtest/runs \
  --monitor-run-id baseline_v3_6s_actual_maturity_monitor_opsinput_20260621T033439Z \
  --output-dir /tmp/gotra_v3_6t_ops_actual_20260621T033439Z/monitor/runs \
  --price-dir data/backtest/prices
```

v3.6T command:

```bash
uv run python scripts/baseline_v3_6t_forward_live_monitor_ops.py \
  --input-root /tmp/gotra_v3_6t_ops_actual_20260621T033439Z/monitor/runs/baseline_v3_6s_actual_maturity_monitor_opsinput_20260621T033439Z/summary.json \
  --ops-run-id baseline_v3_6t_monitor_ops_actual_20260621T033439Z \
  --output-dir /tmp/gotra_v3_6t_ops_actual_20260621T033439Z/ops/runs
```

v3.6S actual monitor output:

- Run id: `baseline_v3_6s_actual_maturity_monitor_opsinput_20260621T033439Z`
- Summary path: `/tmp/gotra_v3_6t_ops_actual_20260621T033439Z/monitor/runs/baseline_v3_6s_actual_maturity_monitor_opsinput_20260621T033439Z/summary.json`
- Summary sha256: `1e82a63362ec7f6ac41b668964620484d06172b3334965a83b20cabeb3244a09`
- Status: `DATA_NOT_MATURED`

v3.6T monitor ops output:

- Run id: `baseline_v3_6t_monitor_ops_actual_20260621T033439Z`
- Summary path: `/tmp/gotra_v3_6t_ops_actual_20260621T033439Z/ops/runs/baseline_v3_6t_monitor_ops_actual_20260621T033439Z/summary.json`
- Summary sha256: `211c85541c864b68cdcc9477b74aba2c0b90df689f33679e205cd0648c2d378e`
- Status: `DATA_NOT_MATURED`
- Latest monitor run id: `baseline_v3_6s_actual_maturity_monitor_opsinput_20260621T033439Z`
- Latest next check after: `2026-07-21T00:00:00Z`
- Recommendation: `WAIT_UNTIL_NEXT_CHECK`
- v3.7 verdict allowed: `false`

Key counts:

- Checked capture run count: `4`
- Not matured count: `128`
- Matured candidate count: `0`
- Blocked data count: `0`
- Resolved count: `0`
- Scored count: `0`
- Readiness status: `NOT_RUN`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`

Blocker reasons:

- `capture_horizons_not_matured`
- `readiness_not_ready`

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6t_forward_live_monitor_ops.py scripts/baseline_v3_6s_actual_maturity_monitor.py
uv run ruff check --no-cache scripts/baseline_v3_6t_forward_live_monitor_ops.py tests/test_forward_live_monitor_ops.py
uv run pytest -q tests/test_forward_live_monitor_ops.py
uv run pytest -q tests/test_forward_live_maturity_monitor.py tests/test_forward_live_verdict_readiness_gate.py tests/test_forward_live_outcome_resolver.py tests/test_forward_live_outcome_scheduler.py tests/test_forward_live_operating_loop.py tests/test_forward_live_matured_outcome_scorer.py
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.6T tests: `10 passed`
- Review hardening focused tests: included in focused v3.6T tests
- v3.5/v3.6 forward-live regression set: `75 passed`
- Full test suite: `373 passed`
- `git diff --check`: pass

## Artifact Boundary

The actual monitor and ops summaries are stored under `/tmp` and are not
committed. No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
transcripts, `.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local
artifacts, or README changes are intended for commit.

## Next Action

Do not start v3.7 from the current actual artifact state. The correct next
action is another maturity recheck at or after `2026-07-21T00:00:00Z`. Only if
actual monitor eligibility and current-root readiness reach
`READY_FOR_FORWARD_LIVE_VERDICT` should a separate preregistered v3.7 planning
stage be opened.
