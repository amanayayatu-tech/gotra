# GOTRA v3.5E Matured Outcome Scorer Result

Date: 2026-06-21

## Project

- Project: GOTRA v3.5E forward-live matured outcome scorer/report generator
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-v3-5e-matured-outcome-scorer-20260621`
- Base: `origin/main` at `85c9e8642e4a66f76048644009c41f08f9626069`

## Evidence Layer

Matured outcome scorer engineering/local validation only.

This stage did not call Kimi/GLM/DeepSeek provider APIs, did not call the Codex
CLI backend, did not run formal-lite or OOS, and does not make science/public,
product superiority, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.5E does not use it to prove GOTRA, ksana, or alaya
success or failure.

## Implementation Summary

New entrypoint:

- `scripts/baseline_v3_5_forward_live_matured_outcome_scorer.py`

The scorer:

- scans v3.5B resolver outcome artifacts directly or via v3.5D provenance links
- scores only `outcome_status=RESOLVED` records
- reverse-links each scored outcome to the source capture artifact
- reads predicted direction and optional `expected_change_pct` from source
  capture decisions
- uses only `long` / `avoid` / `neutral` direction buckets
- reports direction hit rate, MAE/MSE availability, exclusion counts, cluster
  counts, and provenance/future-data blockers
- reports `POLICY_RETURN_NOT_COMPUTED`
- produces no winner/verdict

## Local Scorer Validation

Local validation run:

- run id: `baseline_v3_5e_matured_outcome_scorer_local_20260620T182539Z`
- summary status: `SCORED_OUTCOMES_AVAILABLE`
- summary path:
  `/tmp/gotra_v3_5e_matured_outcome_scorer_validation_20260620T182539Z/runs/baseline_v3_5e_matured_outcome_scorer_local_20260620T182539Z/summary.json`

Validation fixture:

- 3 resolved mature outcomes across 3 tickers/clusters
- 1 not-matured outcome excluded
- all source capture artifacts are local mock fixtures with complete provenance
- provider/backend called: `false`
- Codex CLI called: `false`
- formal-lite entered: `false`

Summary counts:

- resolved outcome count: `3`
- scored outcome count: `3`
- excluded not-matured count: `1`
- ticker count / cluster count: `3`
- date count: `1`
- provenance link count: `3`
- future-data violation count: `0`
- direction hit rate: `1.0`
- metric available count: `3`
- metric unavailable count: `0`
- MAE: `0.8333333333333334`
- MSE: `0.75`
- policy return status: `POLICY_RETURN_NOT_COMPUTED`

This is a descriptive matured-outcome scorer report only. It is not a
full_gotra, deterministic, ksana, OOS, science/public, or trading verdict.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_5_forward_live_matured_outcome_scorer.py
uv run ruff check --no-cache scripts/baseline_v3_5_forward_live_matured_outcome_scorer.py tests/test_forward_live_matured_outcome_scorer.py
uv run pytest -q tests/test_forward_live_matured_outcome_scorer.py
uv run pytest -q tests/test_forward_live_outcome_resolver.py tests/test_forward_live_outcome_scheduler.py tests/test_forward_live_operating_loop.py
uv run python scripts/baseline_v3_5_forward_live_matured_outcome_scorer.py --input-root /tmp/gotra_v3_5e_matured_outcome_scorer_validation_20260620T182539Z/input --scorer-run-id baseline_v3_5e_matured_outcome_scorer_local_20260620T182539Z --output-dir /tmp/gotra_v3_5e_matured_outcome_scorer_validation_20260620T182539Z/runs
uv run pytest -q
```

Results:

- `py_compile`: PASS
- `ruff`: PASS
- `tests/test_forward_live_matured_outcome_scorer.py`: `9 passed`
- v3.5B/v3.5C/v3.5D regression tests: `32 passed`
- local scorer validation: `SCORED_OUTCOMES_AVAILABLE`
- full pytest: `332 passed`

## Artifact Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB files, bundle/tar/zip files, Stage8/Stage9 local artifacts,
or README changes are part of this result.

## Next Action

After this PR is reviewed and merged, a later v3.6 readiness gate should decide
whether enough mature, clean, provenance-complete outcomes exist to preregister a
true verdict stage. v3.5E itself remains a descriptive engineering scorer/report
layer.
