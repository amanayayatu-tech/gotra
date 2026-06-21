# GOTRA v3.6AE Continuous Stack Boundary Guard Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_stack_boundary_guard`.

This stage adds a fast local/CI preflight guard for the ongoing #36-#45 stacked
PR workflow. Open/unmerged stacked PRs are expected and are not blockers by
themselves. The guard is an engineering boundary check only: it does not merge
PRs, does not modify `main`, does not call Kimi/GLM/DeepSeek providers, does not
call Codex CLI, does not run formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` must remain
`direct_llm_parametric_memory_control` and must not be described as a clean
no-future baseline.

## Inputs

The command supports CI-local inputs without a GitHub token:

- `--file`: one or more committed file paths to scan.
- `--manifest`: JSON with file text and/or changed-file paths.
- `--snapshot`: optional PR-stack metadata fixture with PR number, title, head,
  base, head SHA, draft state, `mergeStateStatus`, check conclusions, review
  threads, changed files, and PR body text.

Forbidden artifact paths must be blocked before reading file contents:
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, and Stage8/Stage9 artifacts.

## Checks

The guard must block:

- forbidden artifact path or file type
- OOS/science/public/trading/investment overclaim
- positive v3.7 or 30D forward-live verdict wording such as allowed, ready, or
  pass
- unmarked `direct_llm` or any wording that treats it as a clean no-future
  baseline
- missing or incomplete requested PR range in a stack snapshot
- dirty/draft/failed/pending/review-blocked stack metadata when a snapshot is
  provided

Explicit negative boundary statements such as `v3_7_allowed=false`,
`v3.7 allowed: false`, and `v3.7 not allowed` must remain clean.

## Summary Contract

The summary includes:

- `schema`
- `guard_run_id`
- `checked_file_count`
- `checked_pr_count`
- `artifact_boundary_status`
- `claim_boundary_status`
- `maturity_gate_status`
- `direct_llm_boundary_status`
- `stack_guard_status`
- `ready_for_human_merge_review`
- `auto_merge_executed=false`
- `v3_7_allowed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `evidence_layer=engineering_stack_boundary_guard`
- `blocker_reasons`

Clean status exits `0`; any blocked or incomplete terminal status exits
non-zero.

## Boundary

This stage can support human merge review preparation only. It cannot authorize
auto-merge and cannot authorize v3.7. The 30D path remains blocked until true
actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance.
