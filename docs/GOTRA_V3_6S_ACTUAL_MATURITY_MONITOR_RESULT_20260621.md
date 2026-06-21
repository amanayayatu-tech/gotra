# GOTRA v3.6S Actual Maturity Monitor Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local maturity monitoring only.

This result records a local maturity-monitor implementation and one actual
artifact recheck. It does not run Kimi/GLM/DeepSeek provider APIs, does not call
the Codex CLI backend, does not run formal-lite, and does not execute a
forward-live verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base main: `origin/main @ a8a6ad5f85b20f7fd2c46c16ad87c3a5d399e59b`
- Branch: `codex/gotra-v3-6s-actual-maturity-monitor-20260621`

## Implementation Summary

Added:

- `scripts/baseline_v3_6s_actual_maturity_monitor.py`
- `tests/test_forward_live_maturity_monitor.py`

The monitor reads actual v3.5A capture artifacts, checks horizon maturity,
checks matured price availability using the existing v3.5B daily-close
availability rule, surfaces source future-data contamination, and optionally
reads a v3.6 readiness summary. It never executes v3.7 verdict logic.

## Actual Maturity Recheck

Command:

```bash
uv run python scripts/baseline_v3_6s_actual_maturity_monitor.py \
  --input-root data/backtest/runs \
  --monitor-run-id baseline_v3_6s_actual_maturity_monitor_actual_20260621T030035Z \
  --output-dir /tmp/gotra_v3_6s_actual_maturity_20260621T030035Z/runs \
  --price-dir data/backtest/prices
```

Output:

- Run id: `baseline_v3_6s_actual_maturity_monitor_actual_20260621T030035Z`
- Summary path: `/tmp/gotra_v3_6s_actual_maturity_20260621T030035Z/runs/baseline_v3_6s_actual_maturity_monitor_actual_20260621T030035Z/summary.json`
- Summary sha256: `2754d4dd5a21c49e8b34128e9787c05d003a9054b1860643d4d475fb63b5a3dd`
- Status: `DATA_NOT_MATURED`
- Readiness status: `NOT_RUN`
- Next check after: `2026-07-21T00:00:00Z`

Key counts:

- Checked capture run count: `4`
- Capture artifact count: `128`
- Not matured count: `128`
- Matured candidate count: `0`
- Matured price available count: `0`
- Blocked data count: `0`
- Blocked future data count: `0`
- Resolved count: `0`
- Scored count: `0`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`
- `next_stage_planning_allowed`: `false`
- `v3_7_verdict_executed`: `false`

Blocking reasons:

- `capture_horizons_not_matured`
- `readiness_not_ready`

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6s_actual_maturity_monitor.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py
uv run ruff check --no-cache scripts/baseline_v3_6s_actual_maturity_monitor.py tests/test_forward_live_maturity_monitor.py
uv run pytest -q tests/test_forward_live_maturity_monitor.py
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.6S tests: `6 passed`

## Artifact Boundary

The actual monitor summary is stored under `/tmp` and is not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not start v3.7 from the current actual artifact state. The correct next
action is another v3.6S maturity recheck at or after
`2026-07-21T00:00:00Z`, then only if the actual readiness chain reaches
`READY_FOR_FORWARD_LIVE_VERDICT`, plan a separate preregistered v3.7 verdict
stage.
