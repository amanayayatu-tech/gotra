# GOTRA v3.6Z Short-Horizon Outcome Recheck Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `short_horizon_forward_live_canary_engineering`.

This result records the local maturity recheck for the already captured v3.6Y
1D short-horizon canary. It does not run any provider, does not run Codex CLI
again, does not run formal-lite, does not score a 30D outcome, and does not
execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #40
  `codex/gotra-v3-6y-short-horizon-first-capture-20260621 @ 2e1c93cc8af56f90799c0075a7df5c65c9cc1db5`
- Branch:
  `codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621`
- Target PR base:
  `codex/gotra-v3-6y-short-horizon-first-capture-20260621`

## Source Summary

- Source run id:
  `baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z`
- Source summary path:
  `/tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs/baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/summary.json`
- Source summary sha256:
  `c40ecbe021afcd313abb896616e5dcd79329465c73496ccbf118f789f4682da9`
- Source capture backend metadata:
  `codex_cli_llm_backend`, `codex-cli 0.141.0`, `gpt-5.5`, reasoning `high`
- Source capture timestamp: `2026-06-21T03:00:00Z`
- Source horizon: `1D`
- Source horizon end date: `2026-06-22`

The v3.6Z recheck reads the source summary and capture artifact metadata only.
It does not read raw transcript contents.

## Actual Recheck

Command:

```bash
uv run python scripts/baseline_v3_6z_short_horizon_outcome_recheck.py \
  --recheck-run-id baseline_v3_6z_short_horizon_outcome_recheck_actual_20260621T052745Z \
  --source-summary /tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs/baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/summary.json \
  --expected-source-summary-sha256 c40ecbe021afcd313abb896616e5dcd79329465c73496ccbf118f789f4682da9 \
  --expected-run-id baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z \
  --output-dir /tmp/gotra_v3_6z_short_horizon_outcome_recheck_actual_20260621T052745Z/runs \
  --as-of-timestamp-utc 2026-06-21T05:25:00Z \
  --price-dir data/backtest/prices
```

Output, not committed:

`/tmp/gotra_v3_6z_short_horizon_outcome_recheck_actual_20260621T052745Z/runs/baseline_v3_6z_short_horizon_outcome_recheck_actual_20260621T052745Z/summary.json`

Summary sha256:

`87d583ce8d24f0880666067cacaa3102e9fe4c5565682edfb5270041179e771f`

Result:

- Status: `SHORT_HORIZON_NOT_MATURED`
- Maturity status: `SHORT_HORIZON_NOT_MATURED`
- Outcome status: `NOT_MATURED`
- Resolved count: `0`
- Scored count: `0`
- Readiness status: `SHORT_HORIZON_NOT_MATURED`
- Next check after: `2026-06-23T00:00:00Z`
- Provider/backend called by v3.6Z: `false`
- New Codex CLI call by v3.6Z: `false`
- Formal-lite entered: `false`
- v3.7 30D verdict allowed: `false`

Interpretation: the 1D short-horizon source canary has not yet reached the
daily-close availability boundary. v3.6Z correctly did not resolve or score the
outcome.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6z_short_horizon_outcome_recheck.py
uv run ruff check --no-cache scripts/baseline_v3_6z_short_horizon_outcome_recheck.py tests/test_short_horizon_outcome_recheck.py
uv run pytest -q tests/test_short_horizon_outcome_recheck.py
uv run python -m py_compile scripts/baseline_v3_6z_short_horizon_outcome_recheck.py scripts/baseline_v3_6y_short_horizon_first_capture.py scripts/baseline_v3_5_forward_live_outcome_resolver.py scripts/baseline_v3_5_forward_live_matured_outcome_scorer.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py
uv run ruff check --no-cache scripts/baseline_v3_6z_short_horizon_outcome_recheck.py tests/test_short_horizon_outcome_recheck.py scripts/baseline_v3_6y_short_horizon_first_capture.py tests/test_short_horizon_first_capture.py
uv run pytest -q tests/test_short_horizon_outcome_recheck.py tests/test_short_horizon_first_capture.py
uv run pytest -q tests/test_forward_live_outcome_resolver.py tests/test_forward_live_matured_outcome_scorer.py tests/test_forward_live_verdict_readiness_gate.py
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused tests: `6 passed`
- v3.6Z/v3.6Y regression tests: `16 passed`
- v3.5B/v3.5E/v3.6 readiness regression tests: `43 passed`
- Full test suite: `410 passed`
- `git diff --check`: pass

Covered behavior:

- immature horizon -> `SHORT_HORIZON_NOT_MATURED`
- matured but no outcome price -> `BLOCKED_DATA`
- matured with price -> `SHORT_HORIZON_READY` with one resolved/scored canary
- malformed or wrong source summary -> `BLOCKED_PROVENANCE`
- actual direction buckets restricted to `long` / `avoid` / `neutral`
- no provider, no new Codex CLI call, no formal-lite, no v3.7 verdict

## Artifact Boundary

The recheck output is stored under `/tmp` and is not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. The 30D actual forward-live path remains governed by
v3.6S/v3.6T and still requires true actual readiness
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance. The short-horizon
canary can be rechecked again at or after `2026-06-23T00:00:00Z`.
