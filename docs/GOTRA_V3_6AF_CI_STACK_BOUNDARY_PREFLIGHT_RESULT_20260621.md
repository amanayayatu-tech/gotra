# GOTRA v3.6AF CI Stack Boundary Preflight Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_ci_stack_boundary_preflight`.

This result records a local/fixture CI stack boundary preflight wrapper for the
ongoing #36-#46 stacked PR workflow. It does not merge PRs, does not modify
`main`, does not call any provider, does not call Codex CLI, does not run
formal-lite, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #46
  `codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621 @ d42c0b29156c542ff9cd50b08c320963dcaba837`
- Branch:
  `codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621`
- Target PR base:
  `codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621`

## Local Fixture Preflight

Command:

```bash
uv run python scripts/baseline_v3_6af_ci_stack_boundary_preflight.py \
  --preflight-run-id baseline_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z \
  --repo-root /tmp/gotra_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z/repo \
  --pathspec . \
  --output-root /tmp/gotra_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z/runs/baseline_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z/summary.json`

Summary sha256:

`cc8b8b0632850dfc061363d72674e627a2bd4c7118f05cee79a225ac4d725690`

Result:

- Preflight status: `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- Guard summary path:
  `/tmp/gotra_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z/runs/baseline_v3_6af_ci_stack_boundary_preflight_reviewfix_20260621T094751Z/guard_runs/baseline_v3_6ae_continuous_stack_boundary_guard_v3_6af_reviewfix_20260621T094751Z/summary.json`
- Guard summary sha256:
  `e8b0c88874a34bbcde332e883b85c26d73c30287677970d1c0f1e1cc84047ed3`
- Scanned tracked file count: `1`
- Skipped untracked count: `1`
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

Review hardening added after PR review:

- script-path invocation works from repo root without `PYTHONPATH=.`
- duplicate output run ids return a blocked summary without overwriting the
  existing run directory
- default invocation scans no broad historical tracked pathspecs; callers must
  pass explicit scoped `--pathspec` values or manifest/snapshot inputs
- tracked gitlinks, directories, and non-regular files are filtered before
  invoking the v3.6AE guard

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6af_ci_stack_boundary_preflight.py scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py
uv run ruff check --no-cache scripts/baseline_v3_6af_ci_stack_boundary_preflight.py tests/test_ci_stack_boundary_preflight.py
uv run pytest -q tests/test_ci_stack_boundary_preflight.py
uv run pytest -q tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py
uv run pytest -q
```

Result:

- py_compile: pass
- Ruff: pass
- Focused v3.6AF tests: `15 passed`
- v3.6AE/v3.6AF regression tests: `30 passed`
- v3.6AA/v3.6AB/v3.6AE/v3.6AF regression tests: `64 passed`
- Full test suite: `528 passed`

## Covered Behavior

- tracked-only clean fixture -> `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- script-path CLI invocation -> `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- default no-pathspec invocation scans zero broad historical files
- untracked forbidden artifact under `tracked-only` is skipped and not read
- duplicate run id does not overwrite existing summary artifacts
- gitlink/submodule paths are skipped before invoking v3.6AE
- tracked forbidden artifact path -> `BLOCKED_ARTIFACT`
- forbidden manifest path is blocked before read
- forbidden manifest entry -> `BLOCKED_ARTIFACT`
- tracked `OOS evidence` / public proof -> `BLOCKED_CLAIM_BOUNDARY`
- tracked v3.7 / 30D verdict wording -> `BLOCKED_MATURITY_GATE`
- explicit false v3.7 lines remain clean
- unmarked `direct_llm` clean-baseline wording ->
  `BLOCKED_DIRECT_LLM_BOUNDARY`
- `direct_llm_parametric_memory_control` caveat remains clean
- v3.6AE blocked terminal propagates to non-zero wrapper CLI exit
- no provider, no new Codex CLI call, no formal-lite

## CI Wiring Status

The wrapper is not wired into GitHub Actions in this stage. This is intentional:
the existing workflow already runs Ruff and pytest, and the exact broad
tracked-file pathspecs for CI enforcement should be chosen separately to avoid
false positives from historical research docs. The wrapper is ready for local
or future CI fixture/pathspec invocation.

## Artifact Boundary

Fixture outputs are stored under `/tmp` and are not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. #36-#46 remains an open stacked engineering PR workflow for
later human merge/cleanup. The 30D path remains blocked until true actual
readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
