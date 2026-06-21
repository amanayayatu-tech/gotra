# GOTRA v3.7 Forward-Live Entry Decision Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local v3.7 entry decision only.

This stage converts a current actual v3.6S 30D readiness refresh into a
machine-readable v3.7 entry decision. It does not run Kimi/GLM/DeepSeek provider
APIs, does not call the Codex CLI backend, does not run formal-lite, does not
execute a 30D verdict, and does not produce a deterministic / `full_gotra` /
ksana winner.

Non-claim boundary:

- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- Historical `direct_llm=direct_llm_parametric_memory_control`; not a clean
  no-future baseline.

## Command

Script:

```bash
scripts/baseline_v3_7_forward_live_entry_decision.py
```

Inputs:

- `--readiness-summary-path`: an actual v3.6S maturity monitor `summary.json`.
- `--readiness-summary-sha256`: optional expected sha256 for provenance
  verification.
- `--entry-run-id`: v3.7 entry decision run id.
- `--output-dir`: output root. Actual validation runs must use `/tmp`.
- `--as-of-timestamp-utc`: current refresh timestamp.

## Status Contract

Allowed output statuses:

- `V3_7_READY_FOR_FORWARD_LIVE_VERDICT_WORKFLOW`: the actual monitor is
  resolver-path eligible, the current readiness gate is
  `READY_FOR_FORWARD_LIVE_VERDICT`, provenance matches, and no runtime boundary
  flags were set. This permits a separate v3.7 verdict stage, but this command
  still does not execute the verdict.
- `V3_7_VERDICT_BLOCKED_BY_ACTUAL_READINESS`: actual readiness is not ready,
  including `DATA_NOT_MATURED`, `DATA_INSUFFICIENT`, or any `BLOCKED_*` state.
  This permits non-verdict harness/report/provenance preparation only.
- `BLOCKED_PROVENANCE`: the source summary is missing, malformed, schema
  mismatched, hash mismatched, or already claims verdict execution.
- `BLOCKED_RUNTIME_BOUNDARY`: the source summary indicates provider/backend,
  Codex CLI, or formal-lite execution.
- `V3_7_ENTRY_BLOCKED_RUN_ID_EXISTS`: output run id already exists.

## Required Summary Fields

The summary must include:

- `readiness_status`
- `source_monitor_status`
- `source_readiness_gate_status`
- `checked_capture_run_count`
- `matured_candidate_count`
- `resolved_count`
- `scored_count`
- `paired_clean_count`
- `full_gotra_available_count`
- `deterministic_reference_available_count`
- `blocker_reasons`
- `next_check_after`
- `source_summary_path`
- `source_summary_sha256`
- `v3_7_actual_verdict_executable`
- `v3_7_verdict_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `evidence_layer`

When actual readiness is blocked, the command should also emit
`non_blocking_next_tasks` such as fixture harness dry-run, report schema,
provenance validation, dashboard hardening, or short-horizon recheck. These are
engineering/internal tasks only and cannot substitute for the 30D maturity gate.

## Verdict Boundary

This stage is a v3.7 workflow entry gate, not the verdict itself. A real v3.7
deterministic reference vs `full_gotra` verdict may only run in a separate
stage after current actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT`
with matching provenance and matured/resolved/scored/paired clean artifacts.
