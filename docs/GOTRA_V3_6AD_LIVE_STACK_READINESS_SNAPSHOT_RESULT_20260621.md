# GOTRA v3.6AD Live Stack Readiness Snapshot Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_live_stack_readiness_snapshot`.

This result records a local fixture snapshot and a read-only GitHub live
snapshot for the open #36-#44 stacked PR set. It does not merge PRs, does not
modify `main`, does not call any provider, does not call Codex CLI, does not run
formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #44
  `codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621 @ cd4eb546527f7c7db7392a2112267f5401c39af6`
- Branch:
  `codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621`
- Target PR base:
  `codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621`

## Fixture Snapshot

Command:

```bash
uv run python scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py \
  --snapshot-run-id baseline_v3_6ad_live_stack_readiness_snapshot_fixture_20260621T081004Z \
  --snapshot /tmp/gotra_v3_6ad_live_stack_readiness_snapshot_20260621T081004Z/fixture_snapshot.json \
  --output-dir /tmp/gotra_v3_6ad_live_stack_readiness_snapshot_20260621T081004Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ad_live_stack_readiness_snapshot_20260621T081004Z/runs/baseline_v3_6ad_live_stack_readiness_snapshot_fixture_20260621T081004Z/summary.json`

Summary sha256:

`2a8944efb2293c36294677faf6aa411c86e78617946f3d72d51b7ca790dfc7cb`

Result:

- Source mode: `fixture`
- Live stack snapshot status: `LIVE_STACK_SNAPSHOT_READY`
- Ready for human merge review: `true`
- Auto merge executed: `false`
- Open PR count: `9`
- PR numbers: `36,37,38,39,40,41,42,43,44`
- CI all success: `true`
- Active P1/P2 count: `0`
- Artifact boundary status: `clean`
- Claim boundary status: `clean`
- Conflict dry-run status: `CLEAN`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`

## Read-Only GitHub Live Snapshot

Command:

```bash
uv run python scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py \
  --snapshot-run-id baseline_v3_6ad_live_stack_readiness_snapshot_live_20260621T080936Z \
  --use-gh \
  --repo amanayayatu-tech/gotra \
  --pr-range 36-44 \
  --output-dir /tmp/gotra_v3_6ad_live_stack_readiness_snapshot_live_20260621T080936Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ad_live_stack_readiness_snapshot_live_20260621T080936Z/runs/baseline_v3_6ad_live_stack_readiness_snapshot_live_20260621T080936Z/summary.json`

Review bundle output, not committed:

`/tmp/gotra_v3_6ad_live_stack_readiness_snapshot_live_20260621T080936Z/runs/baseline_v3_6ad_live_stack_readiness_snapshot_live_20260621T080936Z/review_bundle.md`

Summary sha256:

`669bf160793422df39af815ce76599184814bb72efac7842fb415f07670dcee6`

Result:

- Source mode: `gh_live_snapshot`
- Live stack snapshot status: `LIVE_STACK_SNAPSHOT_READY`
- Ready for human merge review: `true`
- Auto merge executed: `false`
- Open PR count: `9`
- PR numbers: `36,37,38,39,40,41,42,43,44`
- CI all success: `true`
- Active P1/P2 count: `0`
- Stack topology status: `clean`
- Artifact boundary status: `clean`
- Claim boundary status: `clean`
- Conflict dry-run status: `CLEAN`
- Merge-state summary: `{"CLEAN": 9}`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`
- Next 30D check after: `2026-07-21T00:00:00Z`
- Next short-horizon check after: `2026-06-23T00:00:00Z`

Interpretation: the actual live #36-#44 stack is ready for human merge review
as of this snapshot. This does not merge anything, does not authorize
auto-merge, and does not authorize v3.7.

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
- Focused v3.6AD tests: `14 passed`
- v3.6AA/v3.6AB/v3.6AC/v3.6AD regression tests: `63 passed`
- Full test suite: `483 passed`

## Covered Behavior

- clean #36-#44 stack fixture -> `LIVE_STACK_SNAPSHOT_READY`
- open/unmerged PRs do not block
- CI pending/failure -> `BLOCKED_CI`
- active P1/P2 -> `BLOCKED_REVIEW`
- draft PR -> `BLOCKED_TOPOLOGY`
- topology/base-chain break -> `BLOCKED_TOPOLOGY`
- forbidden changed path -> `BLOCKED_ARTIFACT`
- claim-boundary overclaim -> `BLOCKED_CLAIM_BOUNDARY`
- dirty `mergeStateStatus` or conflict fixture -> `BLOCKED_CONFLICT`
- GitHub GraphQL `statusCheckRollup.contexts.nodes` -> flattened CI success
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
