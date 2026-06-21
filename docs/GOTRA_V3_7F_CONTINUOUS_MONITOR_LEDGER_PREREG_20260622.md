# GOTRA v3.7F Continuous Monitor Ledger Prereg

Date: 2026-06-22

## Scope

v3.7F adds a deterministic/local continuous monitor ledger and validator. The
evidence layer is `engineering_internal_continuous_monitor_ledger`.

The ledger records current engineering status for main, CI/review state,
actual 30D maturity, short-horizon engineering status, and v3.7 harness/schema
preparation status. It is designed for Judge/Worker status recall and does not
execute a verdict.

## Non-Claims

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- Not a deterministic / `full_gotra` / ksana winner.
- Not a replacement for the 2026-07-21 30D maturity gate.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Actual 30D Gate

The ledger must preserve:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

Short-horizon canary, dashboard, and fixture evidence can be recorded only as
engineering/internal status. They cannot authorize actual 30D verdict execution.

## Entrypoint

```bash
uv run python scripts/baseline_v3_7f_continuous_monitor_ledger.py \
  --ledger-run-id baseline_v3_7f_continuous_monitor_ledger_<timestamp> \
  --ledger-fixture /path/to/ledger_fixture.json \
  --output-dir /tmp/gotra_v3_7f_continuous_monitor_ledger/runs \
  --allow-overwrite
```

Runtime output must be written to `/tmp` or another ignored output root and must
not be committed.

## Ledger Input Shape

The command accepts either a single ledger object or an append/index object:

- single object: required ledger fields at fixture root
- append/index object: `ledger_entries` list of ledger objects

When `ledger_entries` is present, the selected latest entry is deterministic:
`generated_at`, then `main_commit`, then `latest_merged_pr_commit`, with original
index as a stable tie-breaker. Selection does not depend on wall-clock time.

## Required Ledger Fields

The normalized summary supports:

- `ledger_schema_version`
- `generated_at`
- `main_commit`
- `main_ci_status`
- `open_pr_count`
- `latest_merged_pr`
- `latest_merged_pr_head`
- `latest_merged_pr_commit`
- `actual_30d_readiness_status`
- `actual_30d_next_check_after`
- `actual_30d_checked_capture_run_count`
- `actual_30d_capture_artifact_count`
- `actual_30d_matured_candidate_count`
- `actual_30d_resolved_count`
- `actual_30d_scored_count`
- `actual_30d_blocker_reasons`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `short_horizon_status`
- `v3_7a_fixture_harness_status`
- `v3_7b_report_schema_status`
- `v3_7c_stat_preflight_status`
- `v3_7d_short_horizon_recheck_status`
- `v3_7e_dashboard_status`
- `known_blockers`
- `next_safe_actions`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `evidence_layer=engineering_internal_continuous_monitor_ledger`
- `source_documents` or `source_summaries`

Source documents or summaries must be tracked docs or mock summary paths. Raw
runtime artifact paths are blocked by the path guard.

## Guard Rules

The command blocks:

- malformed fixture roots or malformed `ledger_entries`
- missing required ledger fields
- non-negative integer fields with invalid values
- provider, Codex CLI new-call, formal-lite, actual executable, or actual
  executed flags set to true
- actual 30D readiness other than `DATA_NOT_MATURED`
- actual 30D `next_check_after` mismatch
- evidence layer mismatch
- missing source documents/summaries
- forbidden source, raw, transcript, or artifact paths
- claim-boundary overreach in ledger text
- direct-LLM clean-baseline wording
- wording that presents short-horizon/dashboard status as actual 30D verdict

## Status Values

Allowed summary statuses:

- `V3_7_CONTINUOUS_MONITOR_LEDGER_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_ARTIFACT`
- `CONTINUOUS_MONITOR_LEDGER_BLOCKED_RUN_ID_EXISTS`

Only `V3_7_CONTINUOUS_MONITOR_LEDGER_READY` exits with status 0. Ready means the
ledger fixture is schema-clean and boundary-clean. It does not mean actual 30D
verdict readiness.

## Digest Convention

The final `summary.json` sha256 is recorded in `manifest.json`; the summary does
not self-hash.

## Artifact Boundary

This PR may commit only the v3.7F script, focused tests, and v3.7F docs. It must
not commit `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
transcripts, `.env*`, SQLite/DB, bundle/tar/zip, or Stage8/Stage9 local
artifacts.

## Next Gate

Actual 30D readiness remains governed by the actual maturity monitor. The 30D
v3.7 verdict path remains non-executable until actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
