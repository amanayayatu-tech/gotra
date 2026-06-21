# GOTRA v3.6AK Live Stack Merge-Readiness Snapshot Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering/local stack audit only`.

This result records a read-only live stack refresh for open PRs #36-#51. It does
not merge PRs, does not modify `main`, does not call providers, does not call
Codex CLI, does not run formal-lite, and does not execute the next verdict
stage.

No OOS/science/public/trading claim is made. No trading/investment advice is
made. The historical direct arm remains
`direct_llm_parametric_memory_control`; it is not a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py`
- `tests/test_live_stack_merge_readiness_snapshot.py`
- `docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_PREREG_20260621.md`
- `docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_RESULT_20260621.md`

## Live Stack Snapshot

Command:

```bash
uv run python scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py \
  --snapshot-run-id baseline_v3_6ak_live_stack_merge_readiness_snapshot_live_20260621T122702Z \
  --use-gh \
  --repo amanayayatu-tech/gotra \
  --pr-range 36-51 \
  --output-dir /tmp/gotra_v3_6ak_live_stack_merge_readiness_snapshot_20260621T122702Z/runs
```

Summary path:

`/tmp/gotra_v3_6ak_live_stack_merge_readiness_snapshot_20260621T122702Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_live_20260621T122702Z/summary.json`

Summary sha256:

`151539a59f0ad560e9d15eb8af13f778b1404eda4007d004961c7225babd7517`

Manifest path:

`/tmp/gotra_v3_6ak_live_stack_merge_readiness_snapshot_20260621T122702Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_live_20260621T122702Z/manifest.json`

Manifest sha256:

`dd6669501ccc3ced5f17228ae2a21abe361ee82c13b15e2639e3f8be21421e7f`

Review bundle path:

`/tmp/gotra_v3_6ak_live_stack_merge_readiness_snapshot_20260621T122702Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_live_20260621T122702Z/review_bundle.md`

Review bundle sha256:

`ec0b4608b9007dd1c0955933e9d56bbd4821abdfd733bba73c815a4382ad8dc9`

Underlying v3.6AH summary path:

`/tmp/gotra_v3_6ak_live_stack_merge_readiness_snapshot_20260621T122702Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_live_20260621T122702Z/underlying_v3_6ah_runs/baseline_v3_6ah_live_stack_refresh_v3_6ak_live_20260621T122702Z/summary.json`

Underlying v3.6AH summary sha256:

`bc5f38e66ae5a94d40cd8f5bbdb48847582fe12e9f80034f6404c152df6ea9fd`

## Snapshot Status

- `stack_merge_readiness_status`: `STACK_READY_FOR_USER_MERGE_REVIEW`
- `underlying_live_stack_refresh_status`: `LIVE_STACK_REFRESH_READY`
- `source_mode`: `gh_live_snapshot`
- `pr_range`: `36-51`
- `pr_numbers`: `36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51`
- `top_pr_number`: `51`
- `top_head_sha`: `6e3bd3eaedcec1fce83dadb63a40102452eacbb5`
- `ci_all_success`: `true`
- `merge_state_all_clean`: `true`
- `merge_state_status_summary`: `CLEAN=16`
- `unresolved_review_thread_count`: `0`
- `active_p1_p2_count`: `0`
- `stack_topology_status`: `clean`
- `artifact_boundary_status`: `clean`
- `claim_boundary_status`: `clean`
- `maturity_gate_status`: `clean`
- `direct_llm_boundary_status`: `clean`
- `provider_boundary_status`: `clean`
- `ci_boundary_preflight_status`: `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- `ci_adoption_status`: `CI_PREFLIGHT_WIRED`
- `blocker_reasons`: none
- `provider_or_backend_called`: `false`
- `codex_cli_new_call`: `false`
- `formal_lite_entered`: `false`
- `auto_merge_executed`: `false`
- `actual_30d_readiness_status`: `DATA_NOT_MATURED`
- `v3_7_allowed`: `false`
- `next_30d_check_after`: `2026-07-21T00:00:00Z`
- `next_short_horizon_check_after`: `2026-06-23T00:00:00Z`

The clean stack status means only that the current engineering PR stack is ready
for user merge-review preparation. The boundary statements are:

- not an auto-merge
- not merge authorization
- not a 30D forward-live verdict
- not science proof
- not public proof
- not trading advice
- not investment advice

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py scripts/baseline_v3_6ah_live_stack_refresh.py
uv run ruff check --no-cache scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py tests/test_live_stack_merge_readiness_snapshot.py
uv run pytest -q tests/test_live_stack_merge_readiness_snapshot.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_6ak_docs_final_20260621T123250Z --file docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_PREREG_20260621.md --file docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_RESULT_20260621.md --output-dir /tmp/gotra_v3_6ak_claim_scan_final_20260621T123250Z/runs
```

Initial focused validation result:

- py_compile: pass
- Ruff: pass
- v3.6AK focused tests: `4 passed`
- v3.6AK/v3.6AH focused tests: `19 passed`
- v3.6AA/v3.6AB/v3.6AC/v3.6AD/v3.6AE/v3.6AF/v3.6AG/v3.6AH/v3.6AK
  regression tests: `148 passed`
- Full test suite: `597 passed`
- v3.6AK docs claim-boundary scan:
  `CLAIM_BOUNDARY_CLEAN` with 0 blocked items and 3 non-blocking ambiguous
  readiness wording warnings
- `git diff --check`: pass

## Artifact Boundary

Runtime outputs are stored under `/tmp` and are not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. The 30D path remains governed by actual maturity and the
recorded next check after `2026-07-21T00:00:00Z`. The user can use this snapshot
for later manual stack merge-review preparation only.
