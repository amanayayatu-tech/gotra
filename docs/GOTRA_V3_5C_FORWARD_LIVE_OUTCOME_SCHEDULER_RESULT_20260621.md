# GOTRA v3.5C Forward-Live Outcome Scheduler Result

Date: 2026-06-21

## Project

- Project: GOTRA v3.5C forward-live outcome maturity/scoring scheduler
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-v3-5c-forward-live-outcome-scheduler-20260621`
- Base: `origin/main` at `b8913520834221453964289509b2bae6e543b0e2`

## Evidence Layer

Forward-live scheduler engineering/local validation only.

This stage did not call Kimi/GLM/DeepSeek provider APIs, did not call the Codex
CLI backend, did not run formal-lite, and does not make OOS, science/public,
product superiority, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.5C does not use it for any success/failure
interpretation.

## Implementation Summary

New scheduler:

- `scripts/baseline_v3_5_forward_live_outcome_scheduler.py`

The scheduler:

- scans v3.5A capture artifacts with the existing v3.5B capture discovery logic
- computes source decision ids with the v3.5B resolver identity function
- skips already resolved source decisions idempotently
- delegates decision resolution to v3.5B `resolve_capture_artifact`
- writes scheduler provenance into newly produced resolver artifacts
- reports structured scheduler summary fields for maturity, blocked data,
  future-data blocks, duplicates/existing outcomes, and provenance links

No provider, Codex CLI, formal-lite, or old provider parser path is invoked.

## Scheduler / Resolver / Capture Chain

1. v3.5A capture artifact remains the source decision record.
2. v3.5C scheduler scans the capture run and decides whether to call the v3.5B
   resolver for each source decision.
3. v3.5B resolver applies maturity, daily close availability, source
   future-data, and bounded outcome-window rules.
4. v3.5C scheduler annotates the resolver outcome artifact with
   `scheduler_run_id`, `scheduler_schema`, and `scheduler_script_version`.
5. Scheduler summary records counts and reverse-link provenance.

Existing `RESOLVED` outcomes are detected by `source_decision_id` under the
configured output directory and are skipped rather than rewritten.

## Local Scheduler Validation

Local/mock scheduler run:

- run id: `baseline_v3_5c_outcome_scheduler_local_mock_20260621T173235Z`
- summary status: `OUTCOME_SCHEDULER_PASS`
- summary path:
  `/tmp/gotra_v3_5c_scheduler_validation/runs/baseline_v3_5c_outcome_scheduler_local_mock_20260621T173235Z/summary.json`

Validation summary:

- provider/backend called: `false`
- Codex CLI called: `false`
- formal-lite entered: `false`
- scanned decision count: `3`
- resolved count: `1`
- blocked data count: `1`
- not matured count: `1`
- blocked future-data count: `0`
- future-data violations: `0`
- provenance link count: `3`
- source future-data contamination covered by focused tests and classified as
  `BLOCKED_SOURCE_FUTURE_DATA`

## Future-Data Guard

Validated guards:

- immature decisions remain `NOT_MATURED`
- same-day daily close is not visible until D+1 `00:00:00Z`
- missing price data remains `BLOCKED_DATA`
- outcome rows outside the resolver outcome window are not used
- source capture future-data contamination is blocked and counted
- empty capture grid cannot pass

## Provenance

Newly written resolver outcome artifacts include:

- `scheduler_run_id`
- `resolver_run_id`
- `source_decision_id`
- `source_decision_artifact`
- source capture run id
- source artifact path/ref
- price source path and dates used

The existing audit event chain is not updated in v3.5C. The reason is boundary:
this local scheduler produces ignored run artifacts and does not perform a
Judge/Gate knowledge transition. Audit-chain wiring should be a later scoped
stage if scheduler execution becomes part of the live control plane.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_5_forward_live_outcome_scheduler.py scripts/baseline_v3_5_forward_live_outcome_resolver.py scripts/baseline_v3_5_forward_live_capture.py
uv run ruff check --no-cache scripts/baseline_v3_5_forward_live_outcome_scheduler.py tests/test_forward_live_outcome_scheduler.py scripts/baseline_v3_5_forward_live_outcome_resolver.py tests/test_forward_live_outcome_resolver.py scripts/baseline_v3_5_forward_live_capture.py tests/test_forward_live_capture.py
uv run pytest -q tests/test_forward_live_outcome_scheduler.py
uv run pytest -q tests/test_forward_live_outcome_resolver.py
uv run pytest -q tests/test_forward_live_capture.py
uv run python scripts/baseline_v3_5_forward_live_outcome_scheduler.py --capture-run-dir /tmp/gotra_v3_5c_scheduler_validation/capture_run --scheduler-run-id baseline_v3_5c_outcome_scheduler_local_mock_20260621T173235Z --as-of-timestamp-utc 2026-07-25T00:00:00Z --price-dir /tmp/gotra_v3_5c_scheduler_validation/prices --output-dir /tmp/gotra_v3_5c_scheduler_validation/runs
uv run pytest -q
```

Results:

- `py_compile`: PASS
- `ruff`: PASS
- `tests/test_forward_live_outcome_scheduler.py`: `10 passed`
- `tests/test_forward_live_outcome_resolver.py`: `12 passed`
- `tests/test_forward_live_capture.py`: `13 passed`
- local/mock scheduler validation: `OUTCOME_SCHEDULER_PASS`
- full pytest: `313 passed`

## Artifact Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB files, bundle/tar/zip files, Stage8/Stage9 local artifacts,
or README changes are part of this result.

## Next Action

After this PR is reviewed and merged, scheduler can be run against real v3.5A
capture artifacts only when horizons mature and price data is available. Any
actual forward-live performance verdict must be a later preregistered evidence
stage, not this scheduler engineering layer.
