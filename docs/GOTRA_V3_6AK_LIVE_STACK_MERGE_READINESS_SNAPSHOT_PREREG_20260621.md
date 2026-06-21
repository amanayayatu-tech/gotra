# GOTRA v3.6AK Live Stack Merge-Readiness Snapshot Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering/local stack audit only`.

This stage records a current live stack refresh and merge-readiness snapshot for
open PRs #36-#51. It reads fixture or live GitHub metadata, reuses the v3.6AH
live stack refresh logic, and writes local summaries under `/tmp` or a
caller-supplied output root.

This stage does not merge PRs, does not modify `main`, does not call providers,
does not call Codex CLI, does not run formal-lite, and does not execute the next
verdict stage.

No OOS/science/public/trading claim is made. No trading/investment advice is
made. The historical direct arm remains
`direct_llm_parametric_memory_control`; it is not a clean no-future baseline.

## Stack Contract

The snapshot must inspect the current #36-#51 open stack:

- base/head topology
- CI status
- `mergeStateStatus`
- active P1/P2 review threads
- claim boundary
- forbidden artifact boundary
- provider/backend, Codex CLI, and formal-lite boundary flags
- 30D data-maturity boundary

Open/unmerged PRs are expected and are not blockers by themselves. A clean
snapshot may report `STACK_READY_FOR_USER_MERGE_REVIEW`, which means only that
the engineering stack is ready for user review of a future manual merge order.
It is not a merge action and not merge authorization.

## Status Contract

Allowed top-level statuses include:

- `STACK_READY_FOR_USER_MERGE_REVIEW`
- `STACK_BLOCKED_CI`
- `STACK_BLOCKED_REVIEW`
- `STACK_BLOCKED_TOPOLOGY`
- `STACK_BLOCKED_CONFLICT`
- `STACK_BLOCKED_ARTIFACT`
- `STACK_BLOCKED_CLAIM_BOUNDARY`
- `STACK_BLOCKED_MATURITY_GATE`
- `STACK_BLOCKED_DIRECT_LLM_BOUNDARY`
- `STACK_BLOCKED_CI_PREFLIGHT`
- `STACK_BLOCKED_PROVIDER_BOUNDARY`
- `STACK_SNAPSHOT_INCOMPLETE`

If a real blocker appears, the summary must include `blocker_reasons` and enough
PR/base/head/path/thread detail from the underlying live refresh to route a
repair goal.

## Required Summary Fields

The summary must include:

- `schema`
- `snapshot_run_id`
- `source_mode`
- `repo`
- `pr_range`
- `pr_numbers`
- `expected_stack_order`
- `base_chain`
- `head_shas`
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
- `provider_boundary_status`
- `ci_boundary_preflight_status`
- `ci_adoption_status`
- `stack_merge_readiness_status`
- `ready_for_user_merge_review`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `auto_merge_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `next_30d_check_after=2026-07-21T00:00:00Z`
- `evidence_layer=engineering/local stack audit only`

## Non-Claims

This snapshot can say the stack is clean for user merge-review preparation if
the live evidence supports that. The boundary statements are:

- the 30D path is not ready
- v3.7 is not allowed
- no verdict is executed
- not science proof
- not public proof
- not trading advice
- not investment advice
