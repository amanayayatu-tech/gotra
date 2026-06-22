# GOTRA v3.7I Merge-Readiness Watchdog Result

Date: 2026-06-22

## Evidence Layer

`engineering_internal_merge_readiness_watchdog`

This result records a fixture-only local merge-readiness watchdog. It does not
call providers, Codex CLI backends, formal-lite, or any LLM. It does not run an
actual 30D v3.7 verdict.

## Current Boundary

- actual 30D readiness: `DATA_NOT_MATURED`
- actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- historical `direct_llm`: `direct_llm_parametric_memory_control`

## Implemented Surface

Added:

- `scripts/baseline_v3_7i_merge_readiness_watchdog.py`
- `tests/test_v3_7i_merge_readiness_watchdog.py`

The watchdog validates fixture metadata for:

- base/head identity
- `merge_state_status=CLEAN`
- required CI checks
- active P1/P2 review threads
- draft state
- changed-file artifact boundary
- runtime boundary flags
- claim-boundary text in title/body/summary/status metadata
- actual 30D verdict gate boundary

## Local Validation

Focused validation completed:

- `uv run python -m py_compile scripts/baseline_v3_7i_merge_readiness_watchdog.py`: pass
- `uv run ruff check --no-cache scripts/baseline_v3_7i_merge_readiness_watchdog.py tests/test_v3_7i_merge_readiness_watchdog.py`: pass
- `uv run pytest -q tests/test_v3_7i_merge_readiness_watchdog.py`: `14 passed`
- relevant v3.7/readiness/claim-boundary regression set: `197 passed`
- full pytest: `763 passed`

Local mock validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_7i_local_validation_20260622T014600Z/runs/baseline_v3_7i_merge_readiness_watchdog_local_20260622T014600Z/summary.json`
- manifest:
  `/tmp/gotra_v3_7i_local_validation_20260622T014600Z/runs/baseline_v3_7i_merge_readiness_watchdog_local_20260622T014600Z/manifest.json`
- status: `MERGE_READINESS_READY`
- summary sha256:
  `7c35c44f4723cedc554cb5ba264dd25559abcce95055f64e57a55f32ea52e17d`
- manifest digest check: matched final `summary.json` bytes

Docs claim-boundary scan, `git diff --check`, and staged artifact/secret scans
are recorded in the final PR report after staging.

## Non-Claims

This is engineering/internal merge-gate tooling only. It is not an actual 30D
verdict, not OOS/science/public/trading evidence, not investment advice, and
not a deterministic/full_gotra result.
