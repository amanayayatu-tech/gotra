# GOTRA v3.8 Ksana Comparison Prereg Schema Result

Date: 2026-06-22

## Evidence Layer

`engineering_internal_v3_8_ksana_comparison_prereg_schema`

This result records a fixture-only local prereg/schema validator for a future
`ksana_real_research` versus `full_gotra` comparison. It does not call
providers, Codex CLI backends, formal-lite, or any LLM. It does not execute an
actual 30D v3.7 or v3.8 verdict.

## Current Boundary

- actual 30D readiness: `DATA_NOT_MATURED`
- actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- historical direct LLM label: `direct_llm_parametric_memory_control`

## Implemented Surface

Added:

- `scripts/baseline_v3_8_ksana_comparison_prereg_schema.py`
- `tests/test_v3_8_ksana_comparison_prereg_schema.py`

The validator enforces:

- exact primary arms `ksana_real_research` and `full_gotra`
- optional `direct_llm_parametric_memory_control` diagnostic metadata only
- paired design keys for future fixture comparison prep
- source run id, source artifact path, source summary hash, artifact hash, and
  provenance consistency
- explicit false runtime and actual-verdict flags
- current 30D readiness remains `DATA_NOT_MATURED`
- claim-boundary scan for prereg narrative/status fields
- forbidden/raw artifact path boundary
- deterministic summary/manifest digest convention

Repair hardening added for PR review:

- primary arms must have explicit matching `provenance.arms` entries
- duplicate comparison arm rows are schema blockers
- direct-LLM role restrictions are scoped to direct-LLM metadata entries
- repo-relative source artifact paths fall back to the repository root when the
  fixture lives outside the repo
- malformed or empty `non_claims` attestations are schema blockers
- forbidden/raw source artifact paths are blocked without hashing file bytes
- legacy `codex_cli_called` must be present and false, in addition to
  `codex_cli_new_call=false`

## Local Validation

Initial focused validation completed:

- `uv run python -m py_compile scripts/baseline_v3_8_ksana_comparison_prereg_schema.py`: pass
- `uv run ruff check --no-cache scripts/baseline_v3_8_ksana_comparison_prereg_schema.py tests/test_v3_8_ksana_comparison_prereg_schema.py`: pass
- `uv run pytest -q tests/test_v3_8_ksana_comparison_prereg_schema.py`: `17 passed`
- relevant v3.7/readiness/claim-boundary regression set: `252 passed`
- full pytest: `793 passed`

Local mock validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8_repair_validation_20260622T031500Z/runs/baseline_v3_8_ksana_comparison_prereg_schema_repair_20260622T031500Z/summary.json`
- manifest:
  `/tmp/gotra_v3_8_repair_validation_20260622T031500Z/runs/baseline_v3_8_ksana_comparison_prereg_schema_repair_20260622T031500Z/manifest.json`
- status: `V3_8_KSANA_COMPARISON_PREREG_SCHEMA_READY`
- summary sha256:
  `89a2bd8edf51c5c5be598f9564c4e8ad41cafb0c274feb33c530830cf3ffc4e3`
- manifest digest check: matched final `summary.json` bytes
- runtime flags: `provider_or_backend_called=false`, `codex_cli_called=false`,
  `codex_cli_new_call=false`, `formal_lite_entered=false`
- docs claim-boundary scan:
  `/tmp/gotra_v3_8_repair_claim_scan_20260622T031800Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_8_repair_docs_20260622T031800Z/summary.json`
- docs claim-boundary status: `CLAIM_BOUNDARY_CLEAN`

Diff check and staged artifact/secret scans are recorded in the final PR report
after staging.

## Non-Claims

This is engineering/internal prereg-schema prep only. No provider/backend run
is performed. It is not an actual 30D verdict and not an actual v3.8 comparison
result. It makes no OOS, science, public, or trading assertion. It is not
investment guidance. It is not a winner report.
