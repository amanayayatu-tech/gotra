# GOTRA v3.8F Real-Token Evidence Dashboard Result

Date: 2026-06-22

## Result

v3.8F adds a deterministic local dashboard generator and validator:

- script: `scripts/baseline_v3_8f_real_token_evidence_dashboard.py`
- focused tests: `tests/test_v3_8f_real_token_evidence_dashboard.py`
- evidence layer: `engineering_internal_real_connection_evidence_dashboard`
- status vocabulary: `REAL_CONNECTION_EVIDENCE_DASHBOARD_READY`, `BLOCKED_SCHEMA`, `BLOCKED_OVERCLAIM`, `BLOCKED_PROVENANCE`, `BLOCKED_RUNTIME_BOUNDARY`, `BLOCKED_ARTIFACT_BOUNDARY`

The dashboard makes no new backend/provider calls. v3.8F itself records `provider_or_backend_called=false`, `codex_cli_new_call=false`, and `formal_lite_entered=false`.

## Source Evidence Summary

| Stage | PR | Merge commit | Status | Calls | Tokens | Latency evidence |
| --- | ---: | --- | --- | ---: | ---: | --- |
| v3.8B | #66 | `e974420eb2090f541f20d694444d184019f82dca` | `REAL_CONNECTION_AUTH_READY` | 1 | 86 | `3680ms` |
| v3.8C | #67 | `9d554e48294e74f9af22a72c93bab6f3c6c8c37a` | `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS` | 3 | 6518 | `24065/26041/24631ms` |
| v3.8D | #68 | `b92be9870db661dd27015f4e8dcccd5d7235541e` | `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS` | 3 | 6765 | `24152/25517/26395ms` |
| v3.8E | #69 | `cce6cec18ba856d986e8144d8e7915c37d6c9822` | `REAL_TOKEN_FAILURE_MODE_SUITE_PASS` | 0 | 0 | controlled/local `40/47/1000ms` |

Source-stage totals:

- real calls: `7`
- token usage: `13369`
- backend/model: `codex_responses_oauth_backend` / `gpt-5.5`
- raw-output handling: `/tmp` only; repo commits no raw payloads or full transcripts

## Boundary Summary

Current 30D state remains:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

Can say:

- engineering real-connection smoke validated auth metadata boundary
- engineering synthetic packet schema canary validated structured output boundary
- engineering orchestrator dry-run validated synthetic wiring boundary
- engineering controlled failure-mode handling validated local blocker paths

Cannot say:

- not actual 30D verdict
- not v3.7 or v3.8 comparative result
- not OOS/science/public/trading claim
- not investment advice
- not provider benchmark
- not readiness gate passed

`direct_llm_interpretation=direct_llm_parametric_memory_control` remains the only historical direct LLM interpretation.

## Local Validation Target

The local dashboard validation writes only to `/tmp`:

```bash
uv run python scripts/baseline_v3_8f_real_token_evidence_dashboard.py \
  --dashboard-run-id baseline_v3_8f_real_token_evidence_dashboard_local_20260622 \
  --output-dir /tmp/gotra_v3_8f_real_token_evidence_dashboard/runs \
  --allow-overwrite
```

Expected status: `REAL_CONNECTION_EVIDENCE_DASHBOARD_READY`.

This result is internal engineering evidence only. It is not a provider benchmark, not a provider canary verdict, not an orchestrator verdict, not an actual 30D verdict, not an OOS/science/public/trading claim, and not investment advice.
