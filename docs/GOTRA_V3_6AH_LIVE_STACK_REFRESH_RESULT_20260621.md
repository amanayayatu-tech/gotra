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
  `codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621 @ f7477dac767be753bf7e4f286c74c9b294fc0502`
- Branch: `codex/gotra-v3-6ah-live-stack-refresh-20260621`
- Target PR base:
  `codex/gotra-v3-6ag-ci-boundary-preflight-workflow-20260621`

## Local Fixture Refresh

Command:

```bash
uv run python scripts/baseline_v3_6ah_live_stack_refresh.py \
  --refresh-run-id baseline_v3_6ah_live_stack_refresh_reviewfix_fixture_20260621T111227Z \
  --snapshot /tmp/gotra_v3_6ah_reviewfix_clean_20260621T111227Z/snapshot.json \
  --pr-range 36-48 \
  --output-dir /tmp/gotra_v3_6ah_reviewfix_clean_20260621T111227Z/fixture_runs
```

Summary path:

`/tmp/gotra_v3_6ah_reviewfix_clean_20260621T111227Z/fixture_runs/baseline_v3_6ah_live_stack_refresh_reviewfix_fixture_20260621T111227Z/summary.json`

Summary sha256:

`e7b36a8ef43ea8a34e9c7ad7ff00ea65c169fd0e738058fe01c4edc828f66452`

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
  --refresh-run-id baseline_v3_6ah_live_stack_refresh_reviewfix_live_20260621T111227Z \
  --use-gh \
  --repo amanayayatu-tech/gotra \
  --pr-range 36-48 \
  --output-dir /tmp/gotra_v3_6ah_reviewfix_clean_20260621T111227Z/live_runs
```

Summary path:

`/tmp/gotra_v3_6ah_reviewfix_clean_20260621T111227Z/live_runs/baseline_v3_6ah_live_stack_refresh_reviewfix_live_20260621T111227Z/summary.json`

Summary sha256:

`d587a819f8308b37397b50607b2795737c219b322133a067c4b2027f5e6f6f9a`

Status:

- `live_stack_refresh_status`: `LIVE_STACK_REFRESH_READY`
- `ready_for_human_merge_review`: `true`
- `top_pr_number`: `48`
- `top_head_sha`: `f7477dac767be753bf7e4f286c74c9b294fc0502`
- `ci_boundary_preflight_status`: `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- `ci_adoption_status`: `CI_PREFLIGHT_WIRED`
- `artifact_boundary_status`: `clean`
- `claim_boundary_status`: `clean`
- `maturity_gate_status`: `clean`
- `direct_llm_boundary_status`: `clean`
- `active_p1_p2_count`: `0`
- `unresolved_review_thread_count`: `0`
- `blocker_reasons`: none

The read-only live GitHub refresh now records #36-#48 as clean after the PR #48
repair was pushed. This status is limited to the #36-#48 engineering stack and
does not authorize auto-merge or any 30D verdict stage. PR #49 review hardening
is handled by this follow-up commit.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py scripts/baseline_v3_6ah_live_stack_refresh.py scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py scripts/baseline_v3_6ae_continuous_stack_boundary_guard.py scripts/baseline_v3_6af_ci_stack_boundary_preflight.py scripts/baseline_v3_6ag_ci_changed_files_preflight.py
uv run ruff check --no-cache scripts/baseline_v3_6ah_live_stack_refresh.py tests/test_live_stack_refresh.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py tests/test_evidence_claim_boundary_scanner.py
uv run pytest -q tests/test_evidence_claim_boundary_scanner.py tests/test_live_stack_refresh.py
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_stack_merge_readiness_packet.py tests/test_live_stack_readiness_snapshot.py tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py tests/test_ci_changed_files_preflight.py tests/test_live_stack_refresh.py
uv run pytest -q
```

Result:

- py_compile: pass
- Ruff: pass
- Focused v3.6AB/v3.6AH tests: `39 passed`
- v3.6AA/v3.6AB/v3.6AC/v3.6AD/v3.6AE/v3.6AF/v3.6AG/v3.6AH regression tests:
  `144 passed`
- Full test suite: `564 passed`
- v3.6AF self-scan is not used as the review-fix evidence for this patch
  because the scanner source and tests intentionally contain blocked example
  strings. Boundary behavior is covered by focused tests and the v3.6AH
  fixture/live refresh summaries above.

## Hardening Notes

- Review hardening now preserves live snapshot conflict blockers as
  `BLOCKED_CONFLICT` instead of relabeling them as topology failures.
- Claim-boundary substatus classification now parses the scanner rule id from
  `claim_boundary:<path>:<line>:<rule_id>`, so path text containing
  `direct_llm`, `30d`, or `v3_7` cannot misclassify an ordinary overclaim.
- Direct-arm guard-description exemptions now apply only to clauses that
  explicitly reject/block clean no-future-baseline wording; unrelated guard
  verbs do not hide affirmative baseline claims.
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
until the real actual readiness gate returns ready with matching provenance. The
current #36-#48 live refresh is clean for human merge-review preparation only;
it is not a merge action, not a verdict, and not permission to start v3.7.
