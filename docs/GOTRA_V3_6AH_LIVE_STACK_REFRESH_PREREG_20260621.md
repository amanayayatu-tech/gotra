# GOTRA v3.6AH Live Stack Refresh Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_live_stack_refresh`.

This stage refreshes the current open stacked PR status for #36-#48. It reads
fixture or live GitHub metadata, writes local summaries, and prepares a review
bundle for later human merge cleanup. It does not merge PRs, does not modify
`main`, does not call providers, does not call Codex CLI, does not run
formal-lite, and does not execute the next verdict stage.

No OOS/science/public/trading claim is made. No trading/investment advice is
made. The historical direct arm remains
`direct_llm_parametric_memory_control`.

## Base Stack

The branch is stacked on PR #48:
`codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621`.

Open/unmerged stacked PRs are expected and are not blockers by themselves.
Blockers remain draft PRs, CI failure, active P1/P2 review threads, topology
breaks, artifact-boundary violations, claim-boundary violations,
maturity-gate wording violations, direct-arm caveat violations, and
CI-preflight/adoption blockers.

## Refresh Contract

The v3.6AH command must:

- support fixture snapshot mode without GitHub network access
- optionally support read-only live GitHub snapshot mode
- reuse the v3.6AD live snapshot checks for topology, CI, review, artifact, and
  claim boundary status
- reuse v3.6AF/v3.6AG semantics for CI boundary preflight and workflow adoption
- write `summary.json` plus `review_bundle.md` under `/tmp` or a configured
  output root
- keep `auto_merge_executed=false`
- keep `v3_7_allowed=false`

## Summary Contract

The summary must include:

- `schema`
- `refresh_run_id`
- `source_mode`
- `repo`
- `pr_numbers`
- `top_pr_number`
- `top_head_sha`
- `ci_all_success`
- `merge_state_all_clean`
- `unresolved_review_thread_count`
- `active_p1_p2_count`
- `stack_topology_status`
- `artifact_boundary_status`
- `claim_boundary_status`
- `maturity_gate_status`
- `direct_llm_boundary_status`
- `ci_boundary_preflight_status`
- `ci_adoption_status`
- `live_stack_refresh_status`
- `ready_for_human_merge_review`
- `auto_merge_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `next_30d_check_after=2026-07-21T00:00:00Z`
- `evidence_layer=engineering_live_stack_refresh`
- `non_claims`
- `blocker_reasons`

Allowed terminal statuses:

- `LIVE_STACK_REFRESH_READY`
- `BLOCKED_CI`
- `BLOCKED_REVIEW`
- `BLOCKED_TOPOLOGY`
- `BLOCKED_ARTIFACT`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_MATURITY_GATE`
- `BLOCKED_DIRECT_LLM_BOUNDARY`
- `BLOCKED_CI_PREFLIGHT`
- `SNAPSHOT_INCOMPLETE`

Clean refresh exits `0`; blocked or incomplete terminal statuses exit
non-zero.

## Non-Claims

This refresh can say the engineering stack snapshot is current and clean for
human review preparation when the checks support that. It does not authorize
auto-merge and does not authorize the next verdict stage. The long-horizon data
maturity path remains governed by the actual maturity gate and the recorded
`next_check_after` value.
