# GOTRA v3.6AA Stack Evidence Boundary Audit Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_stack_audit`.

This stage adds a local stacked-PR and evidence-boundary audit command for the
open GOTRA v3.6 stack. It reads a fixture or read-only GitHub-exported JSON
snapshot. It does not merge PRs, does not call Kimi/GLM/DeepSeek providers, does
not call Codex CLI, does not run formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` must remain
`direct_llm_parametric_memory_control`.

## Stack Semantics

Open PRs are allowed in this operating mode. An open/unmerged PR is not a
blocker by itself.

The intended topology is:

`#36 -> #37 -> #38 -> #39 -> #40 -> #41 -> #42(v3.6AA)`

Each PR base must point to the previous PR head branch. A broken base/head chain
is `STACK_AUDIT_BLOCKED_TOPOLOGY`.

## Blocking Rules

The audit blocks when any of the following is present:

- failed, cancelled, timed-out, or pending CI check:
  `STACK_AUDIT_BLOCKED_CI`
- unresolved P1/P2 review thread:
  `STACK_AUDIT_BLOCKED_REVIEW`
- broken stacked PR topology:
  `STACK_AUDIT_BLOCKED_TOPOLOGY`
- forbidden changed file path, including `data/backtest/runs/**`,
  `data/paper_trading/**`, raw outputs, transcripts, `.env*`, SQLite/DB,
  bundle/tar/zip, or Stage8/Stage9 local artifacts:
  `STACK_AUDIT_BLOCKED_ARTIFACT`
- evidence overclaim, including OOS/science/public/trading claims or `direct_llm`
  without `direct_llm_parametric_memory_control`:
  `STACK_AUDIT_BLOCKED_OVERCLAIM`

Unresolved non-P1/P2 comments are counted but do not block.

## Summary Contract

The summary includes at least:

- `schema`
- `audit_run_id`
- `audit_timestamp_utc`
- `open_pr_count`
- `stack_topology_status`
- `ci_success_count`
- `active_p1_p2_count`
- `artifact_boundary_violation_count`
- `evidence_overclaim_count`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `next_30d_check_after=2026-07-21T00:00:00Z`
- `next_short_horizon_check_after=2026-06-23T00:00:00Z`
- `evidence_layer=engineering_stack_audit`
- `overall_status`

`STACK_AUDIT_CLEAN` means only that the stack/evidence boundary audit is clean.
It does not mean 30D forward-live readiness is ready and does not authorize
v3.7.

## Next Boundary

v3.7 remains forbidden until true 30D actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance. A short-horizon
canary or clean PR stack cannot substitute for the 30D data-maturity gate.
