# GOTRA v3.6AE Continuous Stack Boundary Guard Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_stack_boundary_guard`.

This result records a local/fixture continuous stack boundary guard for the
ongoing #36-#45 stacked PR workflow. It does not merge PRs, does not modify
`main`, does not call any provider, does not call Codex CLI, does not run
formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #45
  `codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621 @ 430409fd4325fe7ea424c9a07da2545272da6e9a`
- Branch:
  `codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621`
- Target PR base:
  `codex/gotra-v3-6ad-live-stack-readiness-snapshot-20260621`

## Local Fixture Guard

Command:

```bash
uv run python scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py \
  --guard-run-id baseline_v3_6ae_continuous_stack_boundary_guard_20260621T090405Z \
  --manifest /tmp/gotra_v3_6ae_continuous_stack_boundary_guard_20260621T090405Z/clean_manifest.json \
  --snapshot /tmp/gotra_v3_6ae_continuous_stack_boundary_guard_20260621T090405Z/clean_stack_snapshot.json \
  --pr-range 36-37 \
  --output-dir /tmp/gotra_v3_6ae_continuous_stack_boundary_guard_20260621T090405Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ae_continuous_stack_boundary_guard_20260621T090405Z/runs/baseline_v3_6ae_continuous_stack_boundary_guard_20260621T090405Z/summary.json`

Summary sha256:

`97be2bee61e6498938e91c9cfb8c28aac6f892dc0431094478f960738e8ad50e`

Result:

- Stack guard status: `STACK_BOUNDARY_GUARD_CLEAN`
- Checked file count: `4`
- Checked PR count: `2`
- Artifact boundary status: `clean`
- Claim boundary status: `clean`
- Maturity gate status: `clean`
- Direct LLM boundary status: `clean`
- Ready for human merge review: `true`
- Auto merge executed: `false`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py
uv run ruff check --no-cache scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py tests/test_continuous_stack_boundary_guard.py
uv run pytest -q tests/test_continuous_stack_boundary_guard.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_stack_merge_readiness_packet.py tests/test_live_stack_readiness_snapshot.py tests/test_continuous_stack_boundary_guard.py
uv run pytest -q
```

Result:

- py_compile: pass
- Ruff: pass
- Focused v3.6AE tests: `11 passed`
- v3.6AA/v3.6AB/v3.6AC/v3.6AD/v3.6AE regression tests: `89 passed`
- Full test suite: `509 passed`

## Covered Behavior

- clean manifest and stack fixture -> `STACK_BOUNDARY_GUARD_CLEAN`
- forbidden artifact path is blocked before file read
- OOS/public/trading overclaim -> `BLOCKED_CLAIM_BOUNDARY`
- positive v3.7 / 30D verdict wording -> `BLOCKED_MATURITY_GATE`
- explicit false v3.7 lines remain clean
- unmarked `direct_llm` clean-baseline wording -> `BLOCKED_DIRECT_LLM_BOUNDARY`
- `direct_llm_parametric_memory_control` caveat remains clean
- missing requested PR in snapshot -> `SNAPSHOT_INCOMPLETE`
- blocked CLI terminal exits non-zero
- no provider, no new Codex CLI call, no formal-lite

## Artifact Boundary

Fixture outputs are stored under `/tmp` and are not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. #36-#45 remains an open stacked engineering PR workflow for
later human merge/cleanup. The 30D path remains blocked until true actual
readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
