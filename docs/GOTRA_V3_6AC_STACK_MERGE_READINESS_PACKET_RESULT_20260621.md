# GOTRA v3.6AC Stack Merge-Readiness Packet Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_human_merge_readiness_packet`.

This result records local fixture validation of the v3.6AC stacked PR human
merge-readiness packet. It does not merge PRs, does not modify `main`, does not
call any provider, does not call Codex CLI, does not run formal-lite, and does
not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #43
  `codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621 @ f38d5953e567015986e8f08b6d466c2f6da91100`
- Branch:
  `codex/gotra-v3-6ac-stack-merge-readiness-packet-20260621`
- Target PR base:
  `codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621`

## Local Fixture Packet

Command:

```bash
uv run python scripts/baseline_v3_6ac_stack_merge_readiness_packet.py \
  --packet-run-id baseline_v3_6ac_stack_merge_readiness_packet_fixture_20260621T073346Z \
  --snapshot /tmp/gotra_v3_6ac_stack_merge_readiness_packet_20260621T073346Z/stack_merge_snapshot.json \
  --output-dir /tmp/gotra_v3_6ac_stack_merge_readiness_packet_20260621T073346Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ac_stack_merge_readiness_packet_20260621T073346Z/runs/baseline_v3_6ac_stack_merge_readiness_packet_fixture_20260621T073346Z/summary.json`

Human packet output, not committed:

`/tmp/gotra_v3_6ac_stack_merge_readiness_packet_20260621T073346Z/runs/baseline_v3_6ac_stack_merge_readiness_packet_fixture_20260621T073346Z/packet.md`

Summary sha256:

`5da389fecfe73008ddd32e3046d3579d95b85ca22ff89743c4baaa8533d5932b`

Result:

- Human merge-readiness status: `HUMAN_MERGE_PACKET_READY`
- Ready for human merge review/order: `true`
- Auto merge executed: `false`
- Open PR count: `8`
- Stack topology status: `clean`
- CI status: `clean`
- Review status: `clean`
- Artifact boundary status: `clean`
- Claim boundary status: `clean`
- Conflict dry-run status: `CLEAN`
- Maturity boundary status: `DATA_NOT_MATURED_MONITOR_ONLY`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`
- Next 30D check after: `2026-07-21T00:00:00Z`
- Next short-horizon check after: `2026-06-23T00:00:00Z`

Interpretation: the fixture demonstrates the packet can classify a clean
stacked PR set as ready for human merge review/order while keeping auto-merge
and v3.7 disabled. It does not merge anything and does not authorize a 30D
verdict.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ac_stack_merge_readiness_packet.py
uv run ruff check --no-cache scripts/baseline_v3_6ac_stack_merge_readiness_packet.py tests/test_stack_merge_readiness_packet.py
uv run pytest -q tests/test_stack_merge_readiness_packet.py
uv run pytest -q tests/test_stack_merge_readiness_packet.py tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py
uv run pytest -q
git diff --check
```

Result:

- py_compile: pass
- Ruff: pass
- Focused tests: `11 passed`
- v3.6AA/v3.6AB/v3.6AC regression tests: `45 passed`
- Full test suite: `465 passed`
- `git diff --check`: pass

Covered behavior:

- clean stacked PR fixture -> `HUMAN_MERGE_PACKET_READY`
- open/unmerged PR stack does not block
- CI pending/failure -> `BLOCKED_CI`
- active P2 -> `BLOCKED_REVIEW`
- topology break -> `BLOCKED_TOPOLOGY`
- forbidden artifact path -> `BLOCKED_ARTIFACT`
- claim-boundary overclaim -> `BLOCKED_CLAIM_BOUNDARY`
- conflict fixture -> `BLOCKED_CONFLICT`
- unknown conflict -> `UNKNOWN_REQUIRES_HUMAN` and not ready
- 30D `DATA_NOT_MATURED` is a boundary note, not a human engineering merge blocker
- no provider, no new Codex CLI call, no formal-lite

## Artifact Boundary

The local packet output is stored under `/tmp` and is not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. Human merge/cleanup remains a separate manual action. The
30D path remains blocked until true actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
