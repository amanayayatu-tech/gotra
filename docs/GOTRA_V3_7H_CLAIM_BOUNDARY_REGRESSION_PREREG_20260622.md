# GOTRA v3.7H Claim-Boundary CI Regression Prereg

## Scope

v3.7H adds a deterministic local claim-boundary regression guard for GOTRA v3.7 engineering artifacts. It turns recurring review findings from v3.7A through v3.7G into fixture-level checks that can run locally or in CI-safe contexts.

This stage is fixture-only engineering/internal guard work. It is not a provider run, not an actual 30D forward-live verdict, not an OOS/science/public/trading claim, and not trading or investment advice. It does not emit a deterministic/full_gotra winner.

## Current Maturity Boundary

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

v3.7 actual verdict execution remains blocked until the real 30D readiness gate returns the required ready state with matching provenance.

## Regression Guard Contract

Entrypoint:

```bash
uv run python scripts/baseline_v3_7h_claim_boundary_regression.py \
  --fixture <fixture.json> \
  --output-dir /tmp/gotra_v3_7h_claim_boundary_regression/runs
```

The guard supports:

- fixture mode through `--fixture`
- explicit file scan through repeated `--file`
- tracked repo scan through `--tracked-scan --pathspec <path>`
- explicit negative-test allowlist through `--allow-negative-test-path`

Forbidden artifact paths are blocked before content reads. Runtime outputs must stay in `/tmp` or another ignored path.

## Blocked Classes

The guard blocks:

- status-like fields that match maturity-gate bypass rule ids
- missing explicit false boundary flags where attestation is required
- true provider/Codex/formal-lite/verdict flags
- short-cycle or prep-stage evidence promoted beyond engineering/internal scope
- missing `direct_llm_parametric_memory_control` labeling or baseline misuse
- evidence overclaim rule ids outside explicit negative-test contexts
- forbidden/raw artifact references in generic path fields such as `source_path`, `artifact_path`, `input_artifact_path`, `summary_path`, `manifest_path`, and `ledger_path`
- digest declarations that omit boundary-critical fields such as runtime flags, verdict flags, and `direct_llm_interpretation`

Allowed terminal status:

- `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`

Blocking statuses:

- `BLOCKED_SCHEMA`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_DIGEST_BOUNDARY`

## Evidence Layer

`evidence_layer=engineering_internal_claim_boundary_regression`

This guard only states that local/CI claim-boundary regressions are available. It does not change actual 30D readiness and does not authorize v3.7 verdict execution.
