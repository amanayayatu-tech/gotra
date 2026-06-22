# GOTRA v3.7J Short-Horizon Report Template Result

Date: 2026-06-22

## Evidence Layer

`short_horizon_forward_live_canary_engineering`

This result records a fixture-only local short-horizon report
template/schema validator. It does not call providers, Codex CLI backends,
formal-lite, or any LLM. It does not execute an actual 30D v3.7 verdict.

## Current Boundary

- actual 30D readiness: `DATA_NOT_MATURED`
- actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- historical `direct_llm`: `direct_llm_parametric_memory_control`

## Implemented Surface

Added:

- `scripts/baseline_v3_7j_short_horizon_report_template.py`
- `tests/test_v3_7j_short_horizon_report_template.py`

The validator enforces:

- report schema version and required short-horizon report fields
- source summary hash, artifact path/hash, and provenance consistency
- short-horizon-only horizon values
- matured/not-matured/blocked-data outcome consistency
- explicit false runtime and actual-verdict flags
- claim-boundary scan for report narrative/status fields
- deterministic summary/manifest digest convention

## Local Validation

Initial focused validation completed:

- `uv run python -m py_compile scripts/baseline_v3_7j_short_horizon_report_template.py`: pass
- `uv run ruff check --no-cache scripts/baseline_v3_7j_short_horizon_report_template.py tests/test_v3_7j_short_horizon_report_template.py`: pass
- `uv run pytest -q tests/test_v3_7j_short_horizon_report_template.py`: `13 passed`
- relevant v3.7/readiness/claim-boundary regression set: `210 passed`
- full pytest: `776 passed`

Local mock validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_7j_local_validation_20260622T020600Z/runs/baseline_v3_7j_short_horizon_report_template_local_20260622T020600Z/summary.json`
- manifest:
  `/tmp/gotra_v3_7j_local_validation_20260622T020600Z/runs/baseline_v3_7j_short_horizon_report_template_local_20260622T020600Z/manifest.json`
- status: `SHORT_HORIZON_REPORT_TEMPLATE_READY`
- summary sha256:
  `09927b98962d2f495a0062afc35104a417a594c2842e38446dab0b80056af334`
- manifest digest check: matched final `summary.json` bytes
- docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`

`git diff --check` and staged artifact/secret scans are recorded in the final
PR report after staging.

## Non-Claims

This is short-horizon engineering report-template prep only. No
provider/backend run is performed. It is not an actual 30D verdict.
It makes no OOS, science, public, or trading assertion.
It is not investment advice. It is not a deterministic/full_gotra winner report.
