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

Review hardening added after PR #36 self-audit:

- Artifact-directory roots now scan their own `**/*.json` contents, so
  `.../captures/full_gotra/...` style inputs are accepted.
- Missing or invalid `horizon_end_date` is `BLOCKED_DATA`, not
  `DATA_NOT_MATURED`.
- Empty, malformed, or unreadable price caches are `BLOCKED_DATA` blockers.
- Any matured capture with missing price data forces `BLOCKED_DATA`; partial
  price availability does not advertise resolver eligibility.
- External `READY_FOR_FORWARD_LIVE_VERDICT` summaries cannot allow planning
  unless the current monitor result is resolver-path eligible and the readiness
  summary roots match the current input roots.

## Actual Maturity Recheck

Command:

```bash
uv run python scripts/baseline_v3_6s_actual_maturity_monitor.py \
  --input-root data/backtest/runs \
  --monitor-run-id baseline_v3_6s_actual_maturity_monitor_reviewfix_20260621T031553Z \
  --output-dir /tmp/gotra_v3_6s_actual_maturity_reviewfix_20260621T031553Z/runs \
  --price-dir data/backtest/prices
```

Output:

- Run id: `baseline_v3_6s_actual_maturity_monitor_reviewfix_20260621T031553Z`
- Summary path: `/tmp/gotra_v3_6s_actual_maturity_reviewfix_20260621T031553Z/runs/baseline_v3_6s_actual_maturity_monitor_reviewfix_20260621T031553Z/summary.json`
- Summary sha256: `fbcd080243fdce43c89d2909014cd13ed1cd7c82b9b96894e6448d9650836c6b`
- Status: `DATA_NOT_MATURED`
- Readiness status: `NOT_RUN`
- Readiness summary root match: `false`
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
uv run pytest -q tests/test_forward_live_maturity_monitor.py tests/test_forward_live_capture.py tests/test_forward_live_outcome_resolver.py tests/test_forward_live_outcome_scheduler.py tests/test_forward_live_operating_loop.py tests/test_forward_live_matured_outcome_scorer.py tests/test_forward_live_verdict_readiness_gate.py
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.6S tests: `12 passed`
- v3.5/v3.6 regression set: `88 passed`
- Full test suite: `366 passed`

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
