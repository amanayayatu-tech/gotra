# GOTRA v3.7E Evidence Dashboard Hardening Prereg

Date: 2026-06-22

## Scope

v3.7E adds a deterministic/local internal evidence dashboard hardening command.
The evidence layer is `engineering_internal_evidence_dashboard`.

This stage builds and validates a structured dashboard from local fixtures or
mock summaries. It does not read provider raw outputs, does not call providers,
does not call a Codex CLI backend, and does not enter formal-lite.

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

The dashboard must preserve the current actual 30D readiness state:

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

Short-horizon canary status is only engineering/internal status. v3.7A, v3.7B,
v3.7C, v3.7D, and v3.7K are harness, schema, statistical preflight,
short-horizon recheck, and front-half packet preparation evidence only. They do
not authorize actual 30D verdict execution.

## Entrypoint

```bash
uv run python scripts/baseline_v3_7e_evidence_dashboard_hardening.py \
  --dashboard-run-id baseline_v3_7e_evidence_dashboard_hardening_<timestamp> \
  --dashboard-fixture /path/to/dashboard_fixture.json \
  --output-dir /tmp/gotra_v3_7e_evidence_dashboard_hardening/runs \
  --allow-overwrite
```

Runtime output must be written to `/tmp` or another ignored output root and must
not be committed.

## Required Dashboard Fields

The validated dashboard summary includes:

- `main_commit`
- `open_pr_count`
- `main_ci_status`
- `actual_30d_readiness_status`
- `actual_30d_next_check_after`
- `v3_7_actual_verdict_executable`
- `v3_7_actual_verdict_executed`
- `short_horizon_status`
- `v3_7a_fixture_harness_status`
- `v3_7b_report_schema_status`
- `v3_7c_stat_preflight_status`
- `v3_7d_short_horizon_recheck_status`
- `v3_7k_ksana_packet_v2_status`
- `known_blockers`
- `can_say`
- `cannot_say`
- `next_safe_actions`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `evidence_layer=engineering_internal_evidence_dashboard`

The fixture must include object sections named `main`, `readiness`,
`provenance`, and `sections`. The provenance section must include source
document paths, a builder input mode, and the direct-LLM interpretation boundary.

## Guard Rules

The command blocks:

- missing required sections or required fields
- provider, Codex CLI new-call, formal-lite, actual executable, or actual
  executed flags set to true
- `actual_30d_readiness_status` other than `DATA_NOT_MATURED`
- `actual_30d_next_check_after` other than `2026-07-21T00:00:00Z`
- evidence layer mismatch
- forbidden source, raw, transcript, or artifact paths in dashboard references
- claim-boundary overreach in dashboard text
- direct-LLM clean-baseline wording
- short-horizon wording that presents itself as actual 30D verdict evidence

## Status Values

Allowed summary statuses:

- `V3_7_EVIDENCE_DASHBOARD_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_ARTIFACT`
- `EVIDENCE_DASHBOARD_BLOCKED_RUN_ID_EXISTS`

Only `V3_7_EVIDENCE_DASHBOARD_READY` exits with status 0. Ready means the
internal dashboard fixture is schema-clean and boundary-clean. It does not mean
actual 30D verdict readiness.

## Digest Convention

The final `summary.json` sha256 is recorded in `manifest.json`; the summary does
not self-hash.

## Artifact Boundary

This PR may commit only the v3.7E script, focused tests, and v3.7E docs. It must
not commit `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
transcripts, `.env*`, SQLite/DB, bundle/tar/zip, or Stage8/Stage9 local
artifacts.

## Next Gate

Actual 30D readiness remains governed by the actual maturity monitor. The 30D
v3.7 verdict path remains non-executable until actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
