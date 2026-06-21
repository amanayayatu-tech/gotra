# GOTRA v3.6AC Stack Merge-Readiness Packet Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_human_merge_readiness_packet`.

This stage adds a local stacked PR human merge-readiness packet and conflict
dry-run guard. It helps a human review the intended #36-#43 stacked PR merge
order and visible blockers. It does not merge PRs, does not modify `main`, does
not squash or rebase, does not call Kimi/GLM/DeepSeek providers, does not call
Codex CLI, does not run formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` must remain
`direct_llm_parametric_memory_control`.

## Inputs

The packet command reads a fixture or read-only GitHub-exported JSON snapshot
with PR number, title, head/base branch, head SHA, draft state,
`mergeStateStatus`, check conclusions, review-thread data, changed files, and
evidence-boundary text.

Optional local conflict metadata can be requested with `--repo-root` and ordered
`--stack-head` values. This local mode uses read-only `git merge-base` and
`git merge-tree`; it must not checkout, merge, reset, commit, or write the
working tree.

## Blocking Rules

The packet blocks human merge-readiness when any of these are present:

- CI failed, cancelled, timed out, pending, or missing: `BLOCKED_CI`
- active unresolved P1/P2 review thread: `BLOCKED_REVIEW`
- broken stack topology or wrong root base: `BLOCKED_TOPOLOGY`
- forbidden changed path such as `data/backtest/runs/**`,
  `data/paper_trading/**`, raw outputs, transcripts, `.env*`, DB files,
  bundles, or Stage8/Stage9 artifacts: `BLOCKED_ARTIFACT`
- claim-boundary issue, including OOS/science/public/trading overclaim,
  maturity-gate bypass, or `direct_llm` mislabeling:
  `BLOCKED_CLAIM_BOUNDARY`
- known or uncertain conflict dry-run result: `BLOCKED_CONFLICT`

Open/unmerged PRs are expected in this stacked workflow and are not blockers by
themselves.

Draft PRs are not merge-ready and block as `BLOCKED_TOPOLOGY`. Non-`CLEAN`
`mergeStateStatus` values are treated as conflict blockers even when no separate
`conflict_status` field is present. GitHub GraphQL check-rollup connections
under `statusCheckRollup.contexts.nodes` are normalized before CI evaluation.
Local `git merge-tree` dry-run output is considered conflicting if it contains
standard conflict markers, `changed in both`, or delete/modify signals such as
`removed in local` / `removed in remote`.

## Summary Contract

The summary includes at least:

- `schema`
- `packet_run_id`
- `packet_timestamp_utc`
- `open_pr_count`
- `expected_merge_order`
- `stack_topology_status`
- `ci_status`
- `review_status`
- `artifact_boundary_status`
- `claim_boundary_status`
- `conflict_dry_run_status`
- `human_merge_readiness_status`
- `ready_for_human_merge`
- `auto_merge_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `next_30d_check_after=2026-07-21T00:00:00Z`
- `next_short_horizon_check_after=2026-06-23T00:00:00Z`
- `evidence_layer=engineering_human_merge_readiness_packet`

`HUMAN_MERGE_PACKET_READY` means only that the local fixture/snapshot has no
packet-level blocker and is ready for human merge review/order. It does not mean
auto-merge was executed, does not mean the Judge authorized merge, and does not
authorize v3.7.

If 30D readiness is still `DATA_NOT_MATURED`, the packet may still be
human-merge-ready for engineering PRs, but `v3_7_allowed=false` remains a hard
boundary note.

## Next Boundary

v3.7 remains forbidden until true 30D actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance. A clean merge packet,
clean stack, or short-horizon canary cannot substitute for the 30D maturity
gate.
