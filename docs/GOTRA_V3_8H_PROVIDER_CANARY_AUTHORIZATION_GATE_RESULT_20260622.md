# GOTRA v3.8H Provider Canary Authorization Gate Result

Date: 2026-06-22

## Result

v3.8H adds a deterministic local authorization gate / execution guard:

- script: `scripts/baseline_v3_8h_provider_canary_authorization_gate.py`
- focused tests: `tests/test_v3_8h_provider_canary_authorization_gate.py`
- evidence layer: `engineering_internal_provider_canary_authorization_gate`
- status vocabulary: `PROVIDER_CANARY_AUTHORIZATION_GATE_READY`, `BLOCKED_AUTHORIZATION_BOUNDARY`, `BLOCKED_RUNTIME_BOUNDARY`, `BLOCKED_ARTIFACT_BOUNDARY`, `BLOCKED_METADATA`, `BLOCKED_OVERCLAIM`, `BLOCKED_SCHEMA`

v3.8H itself makes no backend/provider call:

- real calls: `0`
- token usage: `0`
- `provider_or_backend_called=false`
- `provider_canary_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

## Boundary Summary

Current 30D state remains:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

Can say:

- provider canary authorization gate is locally validated
- future execution artifacts require a separate authorization packet plus complete metadata and raw-output boundary fields

Cannot say:

- not canary run evidence
- not provider benchmark
- not model-comparison result
- actual 30D execution is false
- not OOS/science/public/trading claim
- not investment advice
- not readiness gate passed

`direct_llm_interpretation=direct_llm_parametric_memory_control` remains the only historical direct LLM interpretation.

## Local Validation Target

The local gate validation writes only to `/tmp`:

```bash
uv run python scripts/baseline_v3_8h_provider_canary_authorization_gate.py \
  --gate-run-id baseline_v3_8h_provider_canary_authorization_gate_local_20260622 \
  --output-dir /tmp/gotra_v3_8h_provider_canary_authorization_gate/runs \
  --allow-overwrite
```

Observed local status: `PROVIDER_CANARY_AUTHORIZATION_GATE_READY`.

Summary:

- path: `/tmp/gotra_v3_8h_provider_canary_authorization_gate/runs/baseline_v3_8h_provider_canary_authorization_gate_local_20260622/summary.json`
- sha256: `63036a390979ac0c9854953d777d9a62e786d3885d3d3efa952ec736bd7ccfb4`

Manifest:

- path: `/tmp/gotra_v3_8h_provider_canary_authorization_gate/runs/baseline_v3_8h_provider_canary_authorization_gate_local_20260622/manifest.json`
- content boundary sha256: `362fe0c222d8dd17b5e54eafc2ca90bb1ef60ee96c8937805a7d1aae355693c1`

## Validation Snapshot

- `py_compile`: pass
- `ruff`: pass
- focused v3.8H pytest: `20 passed`
- relevant v3.8G/v3.8F/v3.7H/v3.7I/v3.8H regression: `77 passed`
- full pytest: `905 passed`
- local/mock guard validation: `PROVIDER_CANARY_AUTHORIZATION_GATE_READY`
- docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
- v3.7H PR-file regression: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- `git diff --check`: pass

## Repair Hardening

The PR #72 repair hardens five authorization-boundary cases:

- observed call and token usage must stay within `authorization_packet.max_calls` and `authorization_packet.max_tokens`.
- malformed `observed_call_count` returns a structured blocker instead of raising an exception.
- provider-called/executed summaries must include non-empty observed provider family, backend, and model identity.
- positive `observed_token_usage_total` is treated as provider/backend evidence even when call flags are false.
- `non_claims` must include the complete required attestation set with every value set to true.

## Next Authorization Boundary

The next step is not automatic. Future provider canary execution requires a separate user message that names the provider family/backend/model and confirms call, token, cost, usage metadata, raw-output, repo-artifact, and stop-condition limits. Without that authorization, the only valid state remains authorization-gate-only.
