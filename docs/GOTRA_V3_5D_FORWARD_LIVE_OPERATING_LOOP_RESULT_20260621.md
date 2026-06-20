# GOTRA v3.5D Forward-Live Operating Loop Result

Date: 2026-06-21

## Project

- Project: GOTRA v3.5D forward-live operating-loop hardening
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-v3-5d-forward-live-operating-loop-20260621`
- Base: `origin/main` at `bf399cc0f9f9361974b4427bfab8e32b4424d1ac`

## Evidence Layer

Forward-live operating-loop engineering/local validation only.

This stage did not call Kimi/GLM/DeepSeek provider APIs, did not call the Codex
CLI backend, did not run formal-lite or OOS, and does not make science/public,
product superiority, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.5D does not use it for any success/failure
interpretation.

## Implementation Summary

New entrypoint:

- `scripts/baseline_v3_5_forward_live_operating_loop.py`

The operating loop:

- accepts a v3.5A capture run root or `captures/` child
- delegates maturity/outcome processing to the v3.5C scheduler and v3.5B
  resolver
- summarizes capture, scheduler, resolver, and outcome provenance in one
  structured summary
- records `audit_event_count=0` and `audit_event_status=not_connected` because
  this local dry-run does not perform a Judge/Gate knowledge transition
- preserves `provider_or_backend_called=false`, `codex_cli_called=false`, and
  `formal_lite_entered=false`
- produces no win/loss, OOS, public, science, or trading verdict

## Local Dry-Run Validation

Local validation run:

- run id: `baseline_v3_5d_operating_loop_local_dryrun_20260620T181003Z`
- summary status: `OPERATING_LOOP_PASS`
- outcome scoring status: `RESOLVED_OUTCOMES_AVAILABLE_NO_VERDICT`
- summary path:
  `/tmp/gotra_v3_5d_operating_loop_validation_20260620T181003Z/runs/baseline_v3_5d_operating_loop_local_dryrun_20260620T181003Z/summary.json`

Validation fixture:

- 2 tickers x 2 decision dates = 4 capture artifacts
- as-of timestamp: `2026-07-25T00:00:00Z`
- local synthetic price cache under `/tmp`
- provider/backend called: `false`
- Codex CLI called: `false`
- formal-lite entered: `false`

Summary counts:

- capture count: `4`
- resolved count: `1`
- blocked data count: `1`
- not matured count: `2`
- blocked future-data count: `0`
- duplicate/existing count: `0`
- provenance link count: `4`
- audit event count: `0`
- future-data violation count: `0`

The single resolved outcome is engineering proof that the local chain can carry
a matured artifact through the scheduler/resolver path. It is not a performance
or trading verdict.

## Provenance

The operating-loop summary contains per-outcome provenance links with:

- source capture run id
- source decision id
- source capture artifact path/ref
- scheduler run id
- scheduler summary path
- resolver run id
- outcome artifact path
- audit event status

Validation showed `4/4` current outcome records had complete reverse lookup
links. Audit event hash is intentionally `null` in v3.5D because audit-chain
wiring is not connected for ignored local run artifacts.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_5_forward_live_operating_loop.py
uv run ruff check --no-cache scripts/baseline_v3_5_forward_live_operating_loop.py tests/test_forward_live_operating_loop.py
uv run pytest -q tests/test_forward_live_operating_loop.py
uv run pytest -q tests/test_forward_live_capture.py tests/test_forward_live_outcome_resolver.py tests/test_forward_live_outcome_scheduler.py
uv run python scripts/baseline_v3_5_forward_live_operating_loop.py --capture-run-dir /tmp/gotra_v3_5d_operating_loop_validation_20260620T181003Z/capture_run --operating-loop-run-id baseline_v3_5d_operating_loop_local_dryrun_20260620T181003Z --as-of-timestamp-utc 2026-07-25T00:00:00Z --price-dir /tmp/gotra_v3_5d_operating_loop_validation_20260620T181003Z/prices --output-dir /tmp/gotra_v3_5d_operating_loop_validation_20260620T181003Z/runs
uv run pytest -q
```

Results:

- `py_compile`: PASS
- `ruff`: PASS
- `tests/test_forward_live_operating_loop.py`: `8 passed`
- v3.5A/v3.5B/v3.5C regression tests: `37 passed`
- local dry-run validation: `OPERATING_LOOP_PASS`
- full pytest: `323 passed`

## Artifact Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB files, bundle/tar/zip files, Stage8/Stage9 local artifacts,
or README changes are part of this result.

## Next Action

After this PR is reviewed and merged, the operating loop can be used as a local
dry-run control surface around mature forward-live captures. Any actual
forward-live performance verdict must be a later preregistered evidence stage
after sufficient mature, clean, provenance-complete outcomes exist.
