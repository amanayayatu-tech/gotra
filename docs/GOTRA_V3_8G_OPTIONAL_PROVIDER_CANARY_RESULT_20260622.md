# GOTRA v3.8G Optional Provider Canary Prereg Result

Date: 2026-06-22

## Result

v3.8G adds a deterministic local prereg/runbook/schema validator:

- script: `scripts/baseline_v3_8g_optional_provider_canary_prereg.py`
- focused tests: `tests/test_v3_8g_optional_provider_canary_prereg.py`
- evidence layer: `engineering_internal_provider_canary_prereg_only`
- status vocabulary: `PROVIDER_CANARY_PREREG_READY`, `BLOCKED_SCHEMA`, `BLOCKED_OVERCLAIM`, `BLOCKED_RUNTIME_BOUNDARY`, `BLOCKED_AUTHORIZATION_BOUNDARY`, `BLOCKED_ARTIFACT_BOUNDARY`

v3.8G itself makes no backend/provider call:

- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- real calls: `0`
- token usage: `0`

## Boundary Summary

Current 30D state remains:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

Can say:

- future optional bounded provider canary prereg/runbook/schema is locally validated
- future execution requires a separate user authorization with named provider family and explicit budgets

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

The local prereg validation writes only to `/tmp`:

```bash
uv run python scripts/baseline_v3_8g_optional_provider_canary_prereg.py \
  --prereg-id baseline_v3_8g_optional_provider_canary_prereg_local_20260622 \
  --output-dir /tmp/gotra_v3_8g_optional_provider_canary_prereg/runs \
  --allow-overwrite
```

Observed local status: `PROVIDER_CANARY_PREREG_READY`.

Summary:

- path: `/tmp/gotra_v3_8g_optional_provider_canary_prereg/runs/baseline_v3_8g_optional_provider_canary_prereg_local_20260622/summary.json`
- sha256: `8f40a463d6a21c54b903f19eef5a07f6b88afa61a555dcb57afff520226822fc`

Manifest:

- path: `/tmp/gotra_v3_8g_optional_provider_canary_prereg/runs/baseline_v3_8g_optional_provider_canary_prereg_local_20260622/manifest.json`
- content boundary sha256: `7a1a2a5efbed903c30823bdc9870c9bb49f989d604eabdda0d847a8a1f595997`

## Validation Snapshot

- `py_compile`: pass
- `ruff`: pass
- focused v3.8G pytest: `14 passed`
- relevant v3.8B/v3.8C/v3.8D/v3.8E/v3.8F/v3.7H/v3.7I/v3.8G regression: `124 passed`
- full pytest: `890 passed`
- docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
- v3.7H PR-file regression: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- `git diff --check`: pass

## Next Authorization Boundary

The next step is not automatic. A future canary requires a separate user message that names the provider family/backend/model and confirms call, token, cost, metadata, raw-output, and stop-condition limits. Without that authorization, the only valid state remains prereg-only.
