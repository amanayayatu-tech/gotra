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
  --ci-adoption-run-id baseline_v3_6ag_ci_changed_files_preflight_pr48_repair_20260621T105815Z \
  --repo-root /Users/peachy/Documents/gotra \
  --base-sha origin/codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621 \
  --head-sha HEAD \
  --output-root /tmp/gotra_v3_6ag_pr48_repair_validation_20260621T105815Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ag_pr48_repair_validation_20260621T105815Z/runs/baseline_v3_6ag_ci_changed_files_preflight_pr48_repair_20260621T105815Z/summary.json`

Summary sha256:

`56ae05cad79fb1d14176a19b1f1f96a2058efc6f077b920ebdf41f40763d32df`

Result:

- CI integration status: `CI_PREFLIGHT_WIRED`
- Changed file count: `7`
- Scanned file count: `7`
- Skipped deleted count: `0`
- Skipped gitlink count: `0`
- Skipped non-file count: `0`
- Manifest path:
  `/tmp/gotra_v3_6ag_pr48_repair_validation_20260621T105815Z/runs/baseline_v3_6ag_ci_changed_files_preflight_pr48_repair_20260621T105815Z/changed_files_manifest.json`
- Preflight summary path:
  `/tmp/gotra_v3_6ag_pr48_repair_validation_20260621T105815Z/runs/baseline_v3_6ag_ci_changed_files_preflight_pr48_repair_20260621T105815Z/preflight_runs/baseline_v3_6af_ci_stack_boundary_preflight_v3_6ag_pr48_repair_20260621T105815Z/summary.json`
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
- Focused v3.6AB/v3.6AG tests: `39 passed`
- v3.6AE/v3.6AF/v3.6AG plus scanner regression tests: `69 passed`
- v3.6AA/v3.6AB/v3.6AE/v3.6AF/v3.6AG regression tests:
  covered by the focused and full-suite runs above
- Full test suite: `547 passed`

## Review Hardening

This repair covers the active PR #48 P2 review items:

- changed-file detection now diffs from the PR merge base to `head`, avoiding
  base-tip-only files and false deletions when the PR branch is behind base
- symlink entries with git mode `120000` are skipped before any target content
  can be followed or scanned
- direct-arm technical field names are field-scoped; a same-line unlabelled
  direct-arm claim is still blocked unless it uses
  `direct_llm_parametric_memory_control`
- tracked `.env.example` placeholder templates are allowed as paths, while real
  `.env*` paths and secret-like values remain blocked

## Covered Behavior

- clean changed-file fixture -> `CI_PREFLIGHT_WIRED` with v3.6AF clean status
- helper scans only changed tracked files, not historical docs
- helper uses merge-base-to-head PR delta, not base-tip-to-head diff
- deleted changed files are skipped
- gitlink changed files are skipped
- symlink, directory, and non-file changed entries are skipped
- `.env.example` placeholder templates are allowed
- `.env.example` with secret-like values is blocked
- real `.env` files remain blocked
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
