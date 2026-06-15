# Stage 4 Evidence Manifest

Generated at: `2026-06-16 02:29:11 CST (+0800)`

This manifest records the evidence for the Stage 4 stop-at-reproducibility-gate result. Run
directories, SQLite ledgers, price caches, and temporary JSON artifacts remain untracked.

## Commits

| Commit | Purpose |
|---|---|
| `0710bb2` | `stage4: preregister` |
| `f61ba59` | `stage4: cognitive compounding mechanism` |

## Validation Commands

Stage 1 engineering validation completed before any Stage 3 provider replay:

| Command | Result |
|---|---|
| `uv run ruff check . --force-exclude` | pass |
| `uv run pytest -q` | `100 passed in 1.19s` |
| `uv run pytest -q tests/test_backtest_analyze.py tests/test_backtest_ledger.py tests/test_backtest_parallel.py tests/test_backtest_walk_forward.py tests/test_codex_responses_client.py` | `53 passed in 0.97s` |
| CI vendor import guard | pass |
| CI vendor endpoint/SDK dependency guard | pass |
| `git diff --check` | pass |

## Artifacts

| Artifact | Path | SHA-256 |
|---|---|---|
| Stage 4 preregistration | `data/backtest/STAGE4_PREREGISTERED.md` | `a44576366b756aa65de6eb8d55c3f89305409531bd255438f94d5faa15e542cb` |
| Price cache coverage/readiness | `/tmp/gotra_stage4_artifacts/stage4_price_cache_coverage_20260616.json` | `189117ad70e12502d394f7987e85fa60ae6ba0852212601008d227e1c5dbeebb` |
| Replay run 1 summary | `data/backtest/runs/stage4_repro_baseline_run1_20260616/summary.json` | `0032d5394ee0768fa9d3586453943eadbc3e163942a53a41c22fa100c1cdb5a6` |
| Replay run 1 system health | `data/backtest/runs/stage4_repro_baseline_run1_20260616/system_health.json` | `a97e36a79bd524753978997049a56d38aa6f4004bb4cdc69b7900313e2eda136` |
| Replay run 2 summary | `data/backtest/runs/stage4_repro_baseline_run2_20260616/summary.json` | `dcee392d09a1eda78ecebb0d6bf2ee9aea2089cfefd37b42f27205b15548b56c` |
| Replay run 2 system health | `data/backtest/runs/stage4_repro_baseline_run2_20260616/system_health.json` | `a405de72c99c4bcd7ee590ec4440432c6e92f208fdfa0697b5357aeaeb038b57` |
| Replay compare result | `/tmp/gotra_stage4_repro_compare_stdout.json` | `a791f800f78fb74951112440c3e2ba681bc0cbec962f064552c30632ea8d198d` |

## Replay Summary

| Metric | Value |
|---|---:|
| reference run id | `stage4_repro_baseline_run1_20260616` |
| candidate run id | `stage4_repro_baseline_run2_20260616` |
| arm | `baseline` |
| same | 102 |
| total | 126 |
| direction agreement | 0.8095238095 |
| threshold | 0.95 |
| passed | false |
| run 1 token_spent | 498055 |
| run 2 token_spent | 508652 |
| total Stage 3 replay tokens | 1006707 |

## Artifact Hygiene

The following paths are intentionally not tracked by git:

- `data/backtest/prices/`
- `data/backtest/runs/`
- SQLite ledgers under run directories
- temporary JSON/stdout/stderr files under `/tmp`
- prior untracked `docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md`
