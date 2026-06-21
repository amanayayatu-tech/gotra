# GOTRA v3.6AD Live Stack Readiness Snapshot Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_live_stack_readiness_snapshot`.

This result records a local fixture snapshot for the open #36-#45 stacked PR
set and the review hardening applied to the read-only GitHub live snapshot path.
It does not merge PRs, does not modify `main`, does not call any provider, does
not call Codex CLI, does not run formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #45 repair target
  `codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621 @ 238ab7285c7f11c1a0ab19510e7be2b667707bb4`
- Branch:
  `codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621`
- Target PR base:
  `codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621`

## Fixture Snapshot

Command:

```bash
uv run python scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py \
  --snapshot-run-id baseline_v3_6ad_live_stack_readiness_snapshot_reviewfix_fixture_20260621T083817Z \
  --snapshot /tmp/gotra_v3_6ad_live_stack_readiness_snapshot_reviewfix_20260621T083401Z/fixture_snapshot.json \
  --output-dir /tmp/gotra_v3_6ad_live_stack_readiness_snapshot_reviewfix_20260621T083817Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ad_live_stack_readiness_snapshot_reviewfix_20260621T083817Z/runs/baseline_v3_6ad_live_stack_readiness_snapshot_reviewfix_fixture_20260621T083817Z/summary.json`

Summary sha256:

`6691195cf15f872da5f8b08ca69161e90950422378566626dca2df864b50495a`

Result:

- Source mode: `fixture`
- Live stack snapshot status: `LIVE_STACK_SNAPSHOT_READY`
- Ready for human merge review: `true`
- Auto merge executed: `false`
- Open PR count: `10`
- PR numbers: `36,37,38,39,40,41,42,43,44,45`
- CI all success: `true`
- Active P1/P2 count: `0`
- Artifact boundary status: `clean`
- Claim boundary status: `clean`
- Conflict dry-run status: `CLEAN`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`

## Review Hardening

This review-fix hardens the live stack snapshot path before a final PR-level
live check:

- live `--use-gh` changed files are paginated until
  `pageInfo.hasNextPage=false`; incomplete pagination becomes
  `SNAPSHOT_INCOMPLETE`, and forbidden files on later pages still block.
- v3.7 false-boundary lines must be unambiguously negative. Positive forms
  such as `v3_7_allowed=true (was false before)` and
  `v3.7 is allowed, not false anymore` block claim-boundary readiness.
- every requested PR must have state `OPEN`; missing, closed, or merged records
  block topology/readiness.
- fixture snapshots are compared against the requested `--pr-range`, so a
  partial clean fixture cannot represent the full #36-#45 stack.

The earlier read-only live snapshot was superseded by this hardening pass. The
post-push live status should be read from the PR checks and the final
`gh_live_snapshot` summary generated after review threads are resolved.

Reference live command:

```bash
uv run python scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py \
  --snapshot-run-id <live_snapshot_run_id> \
  --use-gh \
  --repo amanayayatu-tech/gotra \
  --pr-range 36-45 \
  --output-dir /tmp/<live_snapshot_run_id>/runs
```

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py scripts/baseline_v3_6aa_stack_evidence_boundary_audit.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py scripts/baseline_v3_6ac_stack_merge_readiness_packet.py
uv run ruff check --no-cache scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py tests/test_live_stack_readiness_snapshot.py
uv run pytest -q tests/test_live_stack_readiness_snapshot.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_stack_merge_readiness_packet.py tests/test_live_stack_readiness_snapshot.py
uv run pytest -q
```

Result:

- py_compile: pass
- Ruff: pass
- Focused v3.6AD tests: `25 passed`
- v3.6AA/v3.6AB/v3.6AC/v3.6AD regression tests: `74 passed`
- Full test suite: `494 passed`

## Covered Behavior

- clean #36-#45 stack fixture -> `LIVE_STACK_SNAPSHOT_READY`
- open/unmerged PRs do not block
- CI pending/failure -> `BLOCKED_CI`
- active P1/P2 -> `BLOCKED_REVIEW`
- draft PR -> `BLOCKED_TOPOLOGY`
- topology/base-chain break -> `BLOCKED_TOPOLOGY`
- forbidden changed path -> `BLOCKED_ARTIFACT`
- claim-boundary overclaim -> `BLOCKED_CLAIM_BOUNDARY`
- dirty `mergeStateStatus` or conflict fixture -> `BLOCKED_CONFLICT`
- GitHub GraphQL `statusCheckRollup.contexts.nodes` -> flattened CI success
- live GitHub changed-file pagination includes files after the first 100 and
  blocks incomplete pagination
- PR state must be `OPEN`; closed, merged, or missing state blocks readiness
- fixture PR records must cover the requested `--pr-range`
- v3.7 positive claims with nearby `false` wording still block; explicit
  `v3_7_allowed=false`, `v3.7 verdict allowed: false`, and
  `v3.7 not allowed` remain clean
- 30D `DATA_NOT_MATURED` remains `v3_7_allowed=false` and does not block
  engineering stack review
- explicit negative-boundary PR body wording such as "Cannot say" and
  `v3_7_allowed=false` does not become a false claim-boundary blocker
- no provider, no new Codex CLI call, no formal-lite

## Artifact Boundary

Fixture and live snapshot outputs are stored under `/tmp` and are not
committed. No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
transcripts, `.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts,
or README changes are intended for commit.

## Next Action

Do not execute v3.7. Human merge/cleanup remains a separate manual action. The
30D path remains blocked until true actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
