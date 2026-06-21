# GOTRA v3.6AK Post-Merge Stack Closeout Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering/local stack audit only`.

This stage records a closeout snapshot for PRs #36-#51 after those engineering
PRs were merged to `main` by external Judge/user workflow. It replaces the
earlier open-stack merge-readiness wording so #52 does not add stale evidence
to `main`.

This stage does not merge PRs, does not modify `main`, does not call providers,
does not call Codex CLI, does not run formal-lite, and does not execute the next
verdict stage.

No OOS/science/public/trading claim is made. No trading/investment advice is
made. The historical direct arm remains
`direct_llm_parametric_memory_control`; it is not a clean no-future baseline.

## Closeout Contract

The snapshot must inspect PRs #36-#51 and distinguish two safe terminal
engineering states:

- `STACK_READY_FOR_USER_MERGE_REVIEW`: all requested PRs are still open,
  non-draft, clean, and ready for later human merge review.
- `STACK_MERGED_TO_MAIN`: all requested PRs are already merged, each has a
  recorded head SHA and merge commit, and the top merge commit is recorded as
  the `main` after-stack evidence.

When the stack is already merged, the summary must not keep wording that implies
pending open PRs are still waiting for user merge review. It must instead
record post-merge closeout evidence and keep #52 as the pending repair PR until
that PR is separately reviewed and merged.

## Required Checks

The summary must include or preserve:

- PR numbers and head SHAs for #36-#51
- merge commit for each merged PR
- `main_after_merge_commit`
- `stack_merge_readiness_status`
- `stack_closeout_status`
- `merged_pr_count`
- `merge_commit_count`
- `artifact_boundary_status`
- `claim_boundary_status`
- `provider_boundary_status`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `auto_merge_executed_by_worker=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `next_30d_check_after=2026-07-21T00:00:00Z`
- `evidence_layer=engineering/local stack audit only`

If a real blocker appears, the summary must include `blocker_reasons` and enough
PR/base/head/path/thread detail to route a repair goal.

## Non-Claims

The boundary statements are:

- not an auto-merge by this worker
- not merge authorization for #52
- not a 30D forward-live verdict
- not science proof
- not public proof
- not trading advice
- not investment advice
