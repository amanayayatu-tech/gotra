# GOTRA v3.7H Claim-Boundary CI Regression Result

## Result Summary

v3.7H adds a fixture-only deterministic claim-boundary regression guard:

- Script: `scripts/baseline_v3_7h_claim_boundary_regression.py`
- Focused tests: `tests/test_v3_7h_claim_boundary_regression.py`
- Evidence layer: `engineering_internal_claim_boundary_regression`
- Actual 30D readiness: `DATA_NOT_MATURED`
- Actual 30D next check: `2026-07-21T00:00:00Z`
- v3.7 actual verdict executable: `false`
- v3.7 actual verdict executed: `false`
- Provider/backend called: `false`
- Codex CLI new call: `false`
- Formal-lite entered: `false`

This result is fixture-only local/CI guard work. It is not a provider run, not an actual 30D verdict, not an OOS/science/public/trading claim, not trading or investment advice, and does not emit a deterministic/full_gotra winner.

## Implemented Checks

The guard checks:

- status-like maturity-gate bypass wording
- missing or true runtime/verdict boundary flags
- short-cycle or prep-stage evidence promoted beyond engineering/internal scope
- `direct_llm_parametric_memory_control` labeling and baseline misuse
- evidence overclaim rule ids
- generic forbidden artifact path fields
- digest declarations for boundary-critical field coverage
- explicit negative-test contexts
- final summary digest recorded in `manifest.json`

## Local Validation Snapshot

Focused v3.7H validation:

- `uv run python -m py_compile scripts/baseline_v3_7h_claim_boundary_regression.py`
- `uv run ruff check --no-cache scripts/baseline_v3_7h_claim_boundary_regression.py tests/test_v3_7h_claim_boundary_regression.py`
- `uv run pytest -q tests/test_v3_7h_claim_boundary_regression.py`
- Result: `13 passed`
- Relevant v3.7/readiness/claim-boundary regression: `183 passed`
- Full pytest: `749 passed`
- v3.7H docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`

Local/mock v3.7H CLI validation:

- Run id: `baseline_v3_7h_claim_boundary_regression_local_20260622T012000Z`
- Status: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- Summary path: `/tmp/gotra_v3_7h_local_validation_20260622T012000Z/runs/baseline_v3_7h_claim_boundary_regression_local_20260622T012000Z/summary.json`
- Manifest path: `/tmp/gotra_v3_7h_local_validation_20260622T012000Z/runs/baseline_v3_7h_claim_boundary_regression_local_20260622T012000Z/manifest.json`
- Summary sha256: `f74d530d6a5c8298038297aaebcc8dea5073d8399e10f6950654beb62138153d`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`

## Artifact Boundary

Committed files are limited to v3.7H code, tests, and docs. No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts, `.env*`, SQLite/DB, bundle/tar/zip, or Stage8/Stage9 artifacts are part of this result.

## Next Safe Action

Continue engineering/internal guard work or wait for the scheduled 30D maturity recheck. v3.7 actual verdict remains blocked until real actual readiness returns the required ready state with matching provenance.
