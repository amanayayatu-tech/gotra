# GOTRA v3.6AA Stack Evidence Boundary Audit Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_stack_audit`.

This result records a local fixture validation of the v3.6AA stacked PR /
evidence-boundary audit command. It does not merge PRs, does not call
Kimi/GLM/DeepSeek providers, does not call Codex CLI, does not run formal-lite,
and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #41
  `codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621 @ 9f10a29b082eb596c6c7221b66da774d4dabb338`
- Branch:
  `codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621`
- Target PR base:
  `codex/gotra-v3-6z-short-horizon-outcome-recheck-20260621`

## Local Fixture Audit

Command:

```bash
uv run python scripts/baseline_v3_6aa_stack_evidence_boundary_audit.py \
  --audit-run-id baseline_v3_6aa_stack_evidence_boundary_audit_reviewfix_20260621T071627Z \
  --snapshot /tmp/gotra_v3_6aa_stack_audit_reviewfix_20260621T071627Z/stack_snapshot.json \
  --output-dir /tmp/gotra_v3_6aa_stack_audit_reviewfix_20260621T071627Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6aa_stack_audit_reviewfix_20260621T071627Z/runs/baseline_v3_6aa_stack_evidence_boundary_audit_reviewfix_20260621T071627Z/summary.json`

Summary sha256:

`767fe2e947535a29f34bd0b17edec26017da8d2c20f13f80f100e0a0308da6df`

Result:

- Overall status: `STACK_AUDIT_CLEAN`
- Open PR count: `7`
- Stack topology status: `clean`
- CI success count: `14`
- Active P1/P2 count: `0`
- Artifact boundary violation count: `0`
- Evidence overclaim count: `0`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`
- Next 30D check after: `2026-07-21T00:00:00Z`
- Next short-horizon check after: `2026-06-23T00:00:00Z`

Interpretation: the fixture demonstrates the audit command can classify a clean
stack without treating open/unmerged PRs as blockers. It does not imply 30D
readiness and does not authorize v3.7.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6aa_stack_evidence_boundary_audit.py
uv run ruff check --no-cache scripts/baseline_v3_6aa_stack_evidence_boundary_audit.py tests/test_stack_evidence_boundary_audit.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_package_dashboard.py tests/test_short_horizon_first_capture.py tests/test_short_horizon_outcome_recheck.py tests/test_forward_live_maturity_monitor.py
uv run pytest -q
git diff --check
```

Result:

- py_compile: pass
- Ruff: pass
- Focused tests: `14 passed`
- v3.6AA/v3.6X/v3.6Y/v3.6Z/v3.6S regression tests: `60 passed`
- Full test suite: `434 passed`
- `git diff --check`: pass

Covered behavior:

- clean stacked PR fixture -> `STACK_AUDIT_CLEAN`
- open/unmerged PR stack does not block
- CI pending/failure -> `STACK_AUDIT_BLOCKED_CI`
- active P2 -> `STACK_AUDIT_BLOCKED_REVIEW`
- topology break -> `STACK_AUDIT_BLOCKED_TOPOLOGY`
- bottom PR root base mismatch -> `STACK_AUDIT_BLOCKED_TOPOLOGY`
- forbidden artifact path -> `STACK_AUDIT_BLOCKED_ARTIFACT`
- GitHub connection-shaped changed files -> artifact boundary scan
- evidence overclaim -> `STACK_AUDIT_BLOCKED_OVERCLAIM`
- PR body evidence overclaim -> `STACK_AUDIT_BLOCKED_OVERCLAIM`
- negation scoped to the matched overclaim phrase, not a neighboring clause
- `direct_llm` without `direct_llm_parametric_memory_control` -> overclaim block
- short-horizon ready does not authorize v3.7
- no provider, no new Codex CLI call, no formal-lite

## Artifact Boundary

The local audit output is stored under `/tmp` and is not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. Continue stack monitoring or maturity rechecks only under
separate authorization. The 30D path remains blocked until true actual readiness
returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
