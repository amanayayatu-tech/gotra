# GOTRA v3.6AD Live Stack Readiness Snapshot Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_live_stack_readiness_snapshot`.

This stage adds a local/read-only live stacked PR readiness snapshot and review
bundle refresher for the open #36-#45 stack. It helps a human review current PR
topology, CI, review, artifact-boundary, claim-boundary, and merge-state risk.
It does not merge PRs, does not modify `main`, does not squash or rebase, does
not call Kimi/GLM/DeepSeek providers, does not call Codex CLI, does not run
formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Inputs

The command supports two input modes:

- `--snapshot`: fixture or read-only exported JSON. Tests use this mode and do
  not require GitHub network access.
- `--use-gh --repo amanayayatu-tech/gotra --pr-range 36-45`: read-only GitHub
  live snapshot export through `gh api graphql`. This mode reads PR metadata,
  status checks, review threads, changed files, PR bodies, branch names, head
  SHAs, draft state, and `mergeStateStatus`. It performs no GitHub mutation.

Optional `--repo-root` and `--stack-head` inputs may be used only for read-only
local conflict metadata. The command must not checkout, merge, reset, commit,
or write the working tree.

## Blocking Rules

Open/unmerged PRs are expected in this stacked workflow and are not blockers by
themselves.

The snapshot blocks human merge review readiness when any of these are present:

- missing PRs in the requested stack range: `SNAPSHOT_INCOMPLETE`
- incomplete GitHub changed-file pagination: `SNAPSHOT_INCOMPLETE`
- any requested PR with missing or non-`OPEN` state: `BLOCKED_TOPOLOGY`
- CI failed, cancelled, timed out, pending, or missing: `BLOCKED_CI`
- active unresolved P1/P2 review thread: `BLOCKED_REVIEW`
- draft PR, broken topology, or wrong root base: `BLOCKED_TOPOLOGY`
- forbidden changed path such as `data/backtest/runs/**`,
  `data/paper_trading/**`, raw outputs, transcripts, `.env*`, DB files,
  bundles, or Stage8/Stage9 artifacts: `BLOCKED_ARTIFACT`
- claim-boundary issue, including OOS/science/public/trading overclaim,
  maturity-gate bypass, or `direct_llm` mislabeling:
  `BLOCKED_CLAIM_BOUNDARY`
- dirty `mergeStateStatus`, known conflict, or unknown conflict dry-run:
  `BLOCKED_CONFLICT`

The live PR-body claim scan may ignore explicit negative-boundary or test
coverage wording, such as "Cannot say", `v3_7_allowed=false`, and
`non-claim` boundary descriptions. False v3.7 lines must be unambiguously
negative: positive forms such as `v3_7_allowed=true (was false before)` and
`v3.7 is allowed, not false anymore` still block.

Fixture snapshots are checked against the requested `--pr-range`; a partial
fixture cannot declare a clean stack by omitting PRs from the requested range.
Live GitHub changed files are paginated until `pageInfo.hasNextPage=false`.
If pagination cannot be completed or confirmed, the snapshot is incomplete and
must not report artifact boundary clean.

## Summary Contract

The summary includes at least:

- `schema`
- `snapshot_run_id`
- `snapshot_timestamp_utc`
- `source_mode`
- `repo`
- `open_pr_count`
- `pr_numbers`
- `expected_pr_numbers`
- `expected_stack_order`
- `base_chain`
- `head_shas`
- `ci_all_success`
- `unresolved_review_thread_count`
- `active_p1_p2_count`
- `stack_topology_status`
- `artifact_boundary_status`
- `claim_boundary_status`
- `merge_packet_status`
- `conflict_dry_run_status`
- `merge_state_status_summary`
- `missing_pr_numbers`
- `incomplete_pr_numbers`
- `live_stack_snapshot_status`
- `ready_for_human_merge_review`
- `auto_merge_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `next_30d_check_after=2026-07-21T00:00:00Z`
- `next_short_horizon_check_after=2026-06-23T00:00:00Z`
- `evidence_layer=engineering_live_stack_readiness_snapshot`
- `non_claims`

`LIVE_STACK_SNAPSHOT_READY` means only that the snapshot has no live stack
blocker and is ready for human merge review. It is not Judge merge
authorization, not auto-merge, and not v3.7 authorization.

## Next Boundary

30D `DATA_NOT_MATURED` is not an engineering stack merge blocker, but
`v3_7_allowed=false` remains a hard boundary. v3.7 remains forbidden until true
30D actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance.
