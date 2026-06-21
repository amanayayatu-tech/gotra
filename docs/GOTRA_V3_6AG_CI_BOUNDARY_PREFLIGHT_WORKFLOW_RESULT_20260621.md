# GOTRA v3.6AG CI Boundary Preflight Workflow Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_ci_boundary_preflight_adoption`.

This result records adoption of a lightweight changed-file boundary preflight in
the GitHub Actions pull-request workflow. It does not merge PRs, does not
modify `main`, does not call any provider, does not call Codex CLI, does not
run formal-lite, and does not execute v3.7.

This is an engineering/local guard adoption record. No OOS/science/public/trading
claim is made. No investment advice is made. The historical direct arm remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #47
  `codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621 @ eee69bf5cbbb1ca2134f5e346d337eed9cdce4e5`
- Branch:
  `codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621`
- Target PR base:
  `codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621`

## CI Integration

Status: `CI_PREFLIGHT_WIRED`.

Workflow changed: `.github/workflows/ci.yml`.

The workflow now includes a pull-request-only step named
`GOTRA changed-file boundary preflight`. The step fetches GitHub-provided base
and head SHAs, then runs:

```bash
uv run python scripts/baseline_v3_6ag_ci_changed_files_preflight.py \
  --base-sha "$BASE_SHA" \
  --head-sha "$HEAD_SHA" \
  --output-root "$RUNNER_TEMP/gotra_v3_6ag_ci_changed_files_preflight"
```

Push events do not run this step. Existing Ruff, pytest, BT, hygiene, and
Ksana orchestration checks remain unchanged.

## Local Fixture Adoption Run

Command:

```bash
uv run python scripts/baseline_v3_6ag_ci_changed_files_preflight.py \
  --ci-adoption-run-id baseline_v3_6ag_ci_changed_files_preflight_20260621T101945Z \
  --repo-root /tmp/gotra_v3_6ag_self_ci_sim_20260621T101945Z/repo \
  --base-sha 22f779c43403e9394ef7c099a0bc0c99575ae7d9 \
  --head-sha HEAD \
  --output-root /tmp/gotra_v3_6ag_self_ci_sim_20260621T101945Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ag_self_ci_sim_20260621T101945Z/runs/baseline_v3_6ag_ci_changed_files_preflight_20260621T101945Z/summary.json`

Summary sha256:

`10bdfa95932e74b6e36dc7164491a0deace0d6f5a6037e281fcf679236fe6342`

Result:

- CI integration status: `CI_PREFLIGHT_WIRED`
- Changed file count: `7`
- Scanned file count: `7`
- Skipped deleted count: `0`
- Skipped gitlink count: `0`
- Skipped non-file count: `0`
- Manifest path:
  `/tmp/gotra_v3_6ag_self_ci_sim_20260621T101945Z/runs/baseline_v3_6ag_ci_changed_files_preflight_20260621T101945Z/changed_files_manifest.json`
- Manifest sha256:
  `f64d301bcd0e3fbe1664db4b04c11b0592906092e87d5103fca5a7d4b1c261e0`
- Preflight summary path:
  `/tmp/gotra_v3_6ag_self_ci_sim_20260621T101945Z/runs/baseline_v3_6ag_ci_changed_files_preflight_20260621T101945Z/preflight_runs/baseline_v3_6af_ci_stack_boundary_preflight_v3_6ag_20260621T101945Z/summary.json`
- Preflight summary sha256:
  `3087f7da091f2d59c04e3bdcee9d62da9ababfbc70e27bf7bdc089879ac16442`
- Preflight status: `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- Artifact boundary status: `clean`
- Claim boundary status: `clean`
- Maturity gate status: `clean`
- Direct LLM boundary status: `clean`
- Auto merge executed: `false`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ag_ci_changed_files_preflight.py scripts/baseline_v3_6af_ci_stack_boundary_preflight.py scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py scripts/baseline_v3_6ag_ci_changed_files_preflight.py tests/test_evidence_claim_boundary_scanner.py tests/test_ci_changed_files_preflight.py
uv run pytest -q tests/test_evidence_claim_boundary_scanner.py tests/test_ci_changed_files_preflight.py
uv run pytest -q tests/test_ci_changed_files_preflight.py
uv run pytest -q tests/test_ci_stack_boundary_preflight.py tests/test_ci_changed_files_preflight.py
uv run pytest -q tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py tests/test_ci_changed_files_preflight.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py tests/test_ci_changed_files_preflight.py
uv run pytest -q
```

Result:

- py_compile: pass
- Ruff: pass
- Focused v3.6AB/v3.6AG tests: `33 passed`
- Focused v3.6AG tests: `12 passed`
- v3.6AF/v3.6AG regression tests: `27 passed`
- v3.6AE/v3.6AF/v3.6AG regression tests: `42 passed`
- v3.6AA/v3.6AB/v3.6AE/v3.6AF/v3.6AG regression tests:
  `77 passed`
- Full test suite: `541 passed`

## Covered Behavior

- clean changed-file fixture -> `CI_PREFLIGHT_WIRED` with v3.6AF clean status
- helper scans only changed tracked files, not historical docs
- deleted changed files are skipped
- gitlink changed files are skipped
- directory/non-file changed entries are skipped
- changed forbidden artifact path -> blocked non-zero
- changed OOS/public/science/trading overclaim -> blocked
- changed v3.7 / 30D verdict wording -> maturity gate blocked
- changed explicit false v3.7 plus
  `direct_llm_parametric_memory_control` caveat -> clean
- workflow command is pull-request only and uses base/head SHA inputs
- Python tests/scripts are kept as path-boundary entries so fixture strings do
  not become evidence claims
- technical summary field names such as `direct_llm_boundary_status` are not
  treated as direct-arm evidence claims
- duplicate adoption run id without overwrite does not replace existing summary
- no provider, no new Codex CLI call, no formal-lite

## Artifact Boundary

Fixture outputs are stored under `/tmp` and are not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. #36-#48 remains an open stacked engineering PR workflow for
later human merge/cleanup. The 30D path remains blocked until true actual
readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
