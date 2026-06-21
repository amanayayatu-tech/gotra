# GOTRA v3.6AH Live Stack Refresh Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_live_stack_refresh`.

This result records a top-of-stack refresh for the open #36-#48 engineering PR
stack. It does not merge PRs, does not modify `main`, does not call providers,
does not call Codex CLI, does not run formal-lite, and does not execute the
next verdict stage.

No OOS/science/public/trading claim is made. No trading/investment advice is
made. The historical direct arm remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #48
  `codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621 @ 7ecb214a51c8aeb2eb7dd18625c12d77d8911527`
- Branch: `codex/gotra-v3-6ah-live-stack-refresh-20260621`
- Target PR base:
  `codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621`

## Local Fixture Refresh

Command:

```bash
uv run python scripts/baseline_v3_6ah_live_stack_refresh.py \
  --refresh-run-id baseline_v3_6ah_live_stack_refresh_20260621T104211Z \
  --snapshot /tmp/gotra_v3_6ah_fixture_refresh_20260621T104211Z/snapshot.json \
  --pr-range 36-48 \
  --output-dir /tmp/gotra_v3_6ah_fixture_refresh_20260621T104211Z/runs
```

Summary path:

`/tmp/gotra_v3_6ah_fixture_refresh_20260621T104211Z/runs/baseline_v3_6ah_live_stack_refresh_20260621T104211Z/summary.json`

Summary sha256:

`197bc324cc66dbf844e04c3bde7a2fa9270c020fe77970ea3c4691351e277ef5`

Status:

- `live_stack_refresh_status`: `LIVE_STACK_REFRESH_READY`
- `ready_for_human_merge_review`: `true`
- `top_pr_number`: `48`
- `top_head_sha`: `sha-48`
- `artifact_boundary_status`: `clean`
- `claim_boundary_status`: `clean`
- `maturity_gate_status`: `clean`
- `direct_llm_boundary_status`: `clean`
- `ci_boundary_preflight_status`: `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- `ci_adoption_status`: `CI_PREFLIGHT_WIRED`
- `auto_merge_executed`: `false`
- `provider_or_backend_called`: `false`
- `codex_cli_new_call`: `false`
- `formal_lite_entered`: `false`
- `v3_7_allowed`: `false`

## Live GitHub Refresh

Command:

```bash
uv run python scripts/baseline_v3_6ah_live_stack_refresh.py \
  --refresh-run-id baseline_v3_6ah_live_stack_refresh_20260621T104224Z \
  --use-gh \
  --repo amanayayatu-tech/gotra \
  --pr-range 36-48 \
  --output-dir /tmp/gotra_v3_6ah_live_refresh_20260621T104224Z/runs
```

Summary path:

`/tmp/gotra_v3_6ah_live_refresh_20260621T104224Z/runs/baseline_v3_6ah_live_stack_refresh_20260621T104224Z/summary.json`

Summary sha256:

`a6702b2801917f5f297c563201e5bf93d0d998df0249eb4a74056c2337c53ffa`

Status:

- `live_stack_refresh_status`: `BLOCKED_REVIEW`
- `ready_for_human_merge_review`: `false`
- `top_pr_number`: `48`
- `top_head_sha`: `7ecb214a51c8aeb2eb7dd18625c12d77d8911527`
- `ci_boundary_preflight_status`: `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- `ci_adoption_status`: `CI_PREFLIGHT_WIRED`
- `artifact_boundary_status`: `clean`
- `claim_boundary_status`: `clean`
- `maturity_gate_status`: `clean`
- `direct_llm_boundary_status`: `clean`
- `active_p1_p2_count`: `4`
- `unresolved_review_thread_count`: `4`
- `blocker_reasons`: four `review:active_P2:pr_48` entries

The read-only live GitHub refresh contradicted the earlier clean handoff:
current PR #48 metadata reports four unresolved P2 review threads. This result
therefore records the actual stack status as `BLOCKED_REVIEW`, not ready. No
repair is performed in this stage.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py scripts/baseline_v3_6ah_live_stack_refresh.py scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py scripts/baseline_v3_6af_ci_stack_boundary_preflight.py scripts/baseline_v3_6ag_ci_changed_files_preflight.py
uv run ruff check --no-cache scripts/baseline_v3_6ah_live_stack_refresh.py tests/test_live_stack_refresh.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py tests/test_evidence_claim_boundary_scanner.py
uv run pytest -q tests/test_evidence_claim_boundary_scanner.py tests/test_live_stack_refresh.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_stack_merge_readiness_packet.py tests/test_live_stack_readiness_snapshot.py tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py tests/test_ci_changed_files_preflight.py tests/test_live_stack_refresh.py
uv run pytest -q
uv run python scripts/baseline_v3_6af_ci_stack_boundary_preflight.py --preflight-run-id baseline_v3_6af_ci_stack_boundary_preflight_v3_6ah_20260621T104622Z --manifest /tmp/gotra_v3_6ah_changed_file_preflight_20260621T104622Z/manifest.json --output-root /tmp/gotra_v3_6ah_changed_file_preflight_20260621T104622Z/runs
```

Result:

- py_compile: pass
- Ruff: pass
- Focused v3.6AB/v3.6AH tests: `33 passed`
- v3.6AA/v3.6AB/v3.6AC/v3.6AD/v3.6AE/v3.6AF/v3.6AG/v3.6AH regression tests:
  `133 passed`
- Full test suite: `553 passed`
- v3.6AF changed-file boundary preflight over this stage's script/test/docs:
  `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`; summary sha256
  `0bf734c367b32aba614a455c23c82084b9d97dfd707d0fe754f9bec21bd0eecf`

## Hardening Notes

- `BLOCKED_REVIEW` now takes precedence over CI preflight/adoption blockers when
  active P1/P2 review threads exist, so live summaries do not hide review
  blockers.
- v3.6AH now infers #47/#48 CI preflight/adoption implementation status from
  open, non-draft, merge-clean, CI-success PR metadata without mixing in review
  status; review remains a separate blocker.
- The v3.6AB direct-arm scanner now allows narrow guard descriptions while
  still blocking actual unlabeled direct-arm baseline claims.

## Artifact Boundary

Refresh outputs are stored under `/tmp` and are not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute the next verdict stage. The open stack remains an engineering PR
workflow for later human merge/cleanup. The long-horizon path remains blocked
until the real actual readiness gate returns ready with matching provenance.
Given the current live refresh, the immediate stack blocker is PR #48 active P2
review status, not the artifact, claim, maturity, direct-arm, CI-preflight, or
CI-adoption boundaries.
