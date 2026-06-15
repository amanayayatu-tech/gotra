# Gotra Path Sync Review - 2026-06-15

This note records the local workspace repair that made
`/Users/peachy/Documents/gotra` usable as a clean gotra implementation checkout.

## Context

`/Users/peachy/Documents/gotra` was on `main` with only documentation tracked.
The BT implementation lived in the separate worktree
`/Users/peachy/Documents/gotra-BT-full-monthly` on `BT-provider-fix`.

The local `gotra` checkout also contained untracked runtime artifacts:

- `FIX_REPORT_*.md`, `*.patch`, `REVIEW_BUNDLE_*.tar.gz`
- `bt_full_monthly.bundle`
- `data/backtest/prices/`, `data/backtest/runs/`, generated reports
- Python caches and macOS `.DS_Store` files
- an untracked nested `engine/ksana` clone

These files were review artifacts and runtime output, not pending source code.

## Repair

The untracked artifacts were preserved outside the active source tree before the
checkout was switched:

- Git stash: `stash@{0}` named
  `codex preserve gotra path pre-sync artifacts 2026-06-15`
- Nested ksana clone: `/Users/peachy/Documents/gotra-preserved-untracked-20260615-1643/engine`

The active checkout was then switched to `codex/gotra-path-sync`, based on
`origin/BT-provider-fix`, and `engine/ksana` was initialized as the tracked
submodule at `0a528a8220db463927d6d87df21ae25f484226c4`.

## Review Result

No source changes were found in the pre-sync untracked `gotra/` or `tests/`
directories; they contained caches rather than `.py` source files.

The active implementation was reviewed for the relevant risk areas:

- direct OpenAI/Anthropic imports: none outside the allowed ksana provider adapter
- SQLite writes: parameterized statements; WAL enabled for concurrent workers
- generated artifacts: covered by `.gitignore` and CI repository hygiene guard
- parallel runner: baseline runs independent tasks concurrently; Alaya runs one
  ordered chain per ticker so feedback order is preserved
- analyzer: reads local artifacts only and does not call provider/network/subprocess

## Verification

Run from `/Users/peachy/Documents/gotra`:

```bash
uv run ruff check . --force-exclude
uv run pytest -q
uv run pytest -q engine/ksana/tests/orchestrator/test_decision_checks.py
git diff --check
```

CI also runs heuristic canaries for:

- `--parallel-mode baseline`
- `--parallel-mode ticker-chains`

This path sync does not change the Stage 3 scientific result. A formal Stage 3
acceptance still requires a full baseline replay compare artifact with
direction agreement at or above the preregistered 95 percent gate.
