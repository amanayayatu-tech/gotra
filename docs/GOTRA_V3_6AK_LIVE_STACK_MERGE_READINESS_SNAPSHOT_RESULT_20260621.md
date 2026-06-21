# GOTRA v3.6AK Post-Merge Stack Closeout Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering/local stack audit only`.

This result records the repaired v3.6AK closeout snapshot after PRs #36-#51 were
merged to `main` by external Judge/user workflow. It replaces stale open-stack
wording from the initial #52 snapshot.

This result does not merge PRs, does not modify `main`, does not call providers,
does not call Codex CLI, does not run formal-lite, and does not execute the next
verdict stage.

No OOS/science/public/trading claim is made. No trading/investment advice is
made. The historical direct arm remains
`direct_llm_parametric_memory_control`; it is not a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py`
- `scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py`
- `tests/test_live_stack_merge_readiness_snapshot.py`
- `docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_PREREG_20260621.md`
- `docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_RESULT_20260621.md`

## Main And PR #52 Base Evidence

- `origin/main`: `02b8c474534a908aa2f536e5cd62d735eed67ca8`
- #52 branch: `codex/gotra-v3-6ak-live-stack-readiness-snapshot-20260621`
- #52 is the pending repair PR after #36-#51 merged.
- #52 must be reviewed and merged separately by Judge/user workflow.
- `auto_merge_executed_by_worker`: `false`

## Merged Stack Evidence

| PR | Head SHA | Merge commit |
| --- | --- | --- |
| #36 | `365a52a87cb0e1dbed39a3323ffb8bf4de2fd511` | `aeb93f42a3ac3441efdfc2354eef90cf1ba0de93` |
| #37 | `56fe015b8a033878f9ad5378fe83a04e221448af` | `9d835fe73d6ea9b1fe9deb37d0d2ba7c0659f1e7` |
| #38 | `dd3760a3ef5f326178cb19dc43c48d1d8c886da0` | `ae771f5f66aed81b45fcfb8fdd2f996da51e74ad` |
| #39 | `2997261c7462d9f99b422f0edef1ca0d52e82838` | `17b2483a1067571e55f40b75ff457a31c9e68220` |
| #40 | `2e1c93cc8af56f90799c0075a7df5c65c9cc1db5` | `22dc1d6940bde7d1e23abeae22017a124c2a7926` |
| #41 | `9f10a29b082eb596c6c7221b66da774d4dabb338` | `24d862fc1ffd5b7ce6a6cf2e5116f9ce50ee49ce` |
| #42 | `1e3a0fc77f36949e2ac28e3b68c9a7a8c7f95c78` | `546fa1d516581cd1fb55925e7a178c5d83d45fba` |
| #43 | `f38d5953e567015986e8f08b6d466c2f6da91100` | `674bbf272fd90b4ba7bf5932b2fea3260cd45bd2` |
| #44 | `cd4eb546527f7c7db7392a2112267f5401c39af6` | `13c9a3ef085aa71abdb3cd9af0c2c19828a9e35e` |
| #45 | `430409fd4325fe7ea424c9a07da2545272da6e9a` | `dfba4e0048d257181d9bdaca4153c06b35683885` |
| #46 | `d42c0b29156c542ff9cd50b08c320963dcaba837` | `721759a21e015fc0fa2f9654e527314174dcd6ac` |
| #47 | `eee69bf5cbbb1ca2134f5e346d337eed9cdce4e5` | `3598e39bc4e3ecb0ef74df46f29af1a282222ccb` |
| #48 | `f7477dac767be753bf7e4f286c74c9b294fc0502` | `ccae6d5fe877b5c6f8b83c7a92c90799ed72ae45` |
| #49 | `ebd304a8e0a3b8e3b77a8d984bca9b32cc60b421` | `1b54e0e87d6f2d02747d67fd2a081dd5d3b9343c` |
| #50 | `675698b108e03659548190aab89a764481f23df5` | `8b46dc96c7c84c8b2e581b7bd0315ece77916a06` |
| #51 | `6e3bd3eaedcec1fce83dadb63a40102452eacbb5` | `02b8c474534a908aa2f536e5cd62d735eed67ca8` |

`main_after_merge_commit`: `02b8c474534a908aa2f536e5cd62d735eed67ca8`

## Actual 30D Readiness Evidence

Judge-provided 30D refresh remains:

- `status`: `DATA_NOT_MATURED`
- `checked_capture_run_count`: `4`
- `capture_artifact_count`: `128`
- `not_matured_count`: `128`
- `matured_candidate_count`: `0`
- `resolved_count`: `0`
- `scored_count`: `0`
- `blocker_reasons`: `capture_horizons_not_matured`, `readiness_not_ready`
- `next_check_after`: `2026-07-21T00:00:00Z`
- summary path:
  `/tmp/gotra_actual_30d_readiness_refresh_20260621T122837Z/runs/baseline_v3_6s_actual_maturity_monitor_judge_refresh_20260621T122837Z/summary.json`
- summary sha256:
  `a1a6d1024c0176c8831a675b53c5c8ef00c20a4bddd0c8026d051966768c6c93`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `v3_7_verdict_allowed=false`

## Live Closeout Snapshot

Command:

```bash
uv run python scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py \
  --snapshot-run-id baseline_v3_6ak_live_stack_merge_readiness_snapshot_post_merge_closeout_final2_20260621T131700Z \
  --use-gh \
  --repo amanayayatu-tech/gotra \
  --pr-range 36-51 \
  --output-dir /tmp/gotra_v3_6ak_post_merge_closeout_final2_20260621T131700Z/runs
```

Summary path:

`/tmp/gotra_v3_6ak_post_merge_closeout_final2_20260621T131700Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_post_merge_closeout_final2_20260621T131700Z/summary.json`

Summary sha256:

`2cd69b661d3d8e77fbed6bf650cd01f41c746ca0557aad090fab430b35928cae`

Manifest path:

`/tmp/gotra_v3_6ak_post_merge_closeout_final2_20260621T131700Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_post_merge_closeout_final2_20260621T131700Z/manifest.json`

Manifest sha256:

`b07f4edd6dc1f5de1326289ab70c266768565a0f21b21a895779ec290679e11d`

Review bundle path:

`/tmp/gotra_v3_6ak_post_merge_closeout_final2_20260621T131700Z/runs/baseline_v3_6ak_live_stack_merge_readiness_snapshot_post_merge_closeout_final2_20260621T131700Z/review_bundle.md`

Review bundle sha256:

`c538c45e66aac0cf5845b2d5b5153488b02c6d191d9ce3c0c41c3b3f0408cd84`

## Snapshot Status

- `stack_merge_readiness_status`: `STACK_MERGED_TO_MAIN`
- `stack_closeout_status`: `merged_to_main`
- `stack_already_merged_to_main`: `true`
- `merged_pr_count`: `16`
- `merge_commit_count`: `16`
- `main_after_merge_commit`: `02b8c474534a908aa2f536e5cd62d735eed67ca8`
- `ready_for_user_merge_review`: `false`
- `auto_merge_executed_by_worker`: `false`
- `blocker_reasons`: none
- `artifact_boundary_status`: `clean`
- `claim_boundary_status`: `clean`
- `provider_boundary_status`: `clean`
- `actual_30d_readiness_status`: `DATA_NOT_MATURED`
- `maturity_gate_status`: `DATA_NOT_MATURED`
- `provider_or_backend_called`: `false`
- `codex_cli_new_call`: `false`
- `formal_lite_entered`: `false`
- `v3_7_allowed`: `false`
- `next_30d_check_after`: `2026-07-21T00:00:00Z`

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py scripts/baseline_v3_6ah_live_stack_refresh.py
uv run ruff check --no-cache scripts/baseline_v3_6ak_live_stack_merge_readiness_snapshot.py scripts/baseline_v3_6ad_live_stack_readiness_snapshot.py tests/test_live_stack_merge_readiness_snapshot.py
uv run pytest -q tests/test_live_stack_merge_readiness_snapshot.py
uv run pytest -q tests/test_live_stack_readiness_snapshot.py tests/test_live_stack_refresh.py tests/test_live_stack_merge_readiness_snapshot.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_6ak_closeout_docs_final_20260621T130800Z --file docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_PREREG_20260621.md --file docs/GOTRA_V3_6AK_LIVE_STACK_MERGE_READINESS_SNAPSHOT_RESULT_20260621.md --output-dir /tmp/gotra_v3_6ak_closeout_claim_scan_final_20260621T130800Z/runs
uv run pytest -q tests/test_stack_evidence_boundary_audit.py tests/test_evidence_claim_boundary_scanner.py tests/test_stack_merge_readiness_packet.py tests/test_live_stack_readiness_snapshot.py tests/test_continuous_stack_boundary_guard.py tests/test_ci_stack_boundary_preflight.py tests/test_ci_changed_files_preflight.py tests/test_live_stack_refresh.py tests/test_live_stack_merge_readiness_snapshot.py
uv run pytest -q
git diff --check
```

Final repair validation result:

- py_compile: pass
- Ruff: pass
- v3.6AK focused tests: `7 passed`
- v3.6AD/v3.6AH/v3.6AK focused tests: `49 passed`
- v3.6AK docs claim-boundary scan:
  `CLAIM_BOUNDARY_CLEAN` with 0 blocked items and 1 non-blocking ambiguous
  readiness wording warning
- v3.6AA/v3.6AB/v3.6AC/v3.6AD/v3.6AE/v3.6AF/v3.6AG/v3.6AH/v3.6AK
  regression tests: `149 passed`
- Full test suite: `598 passed`
- `git diff --check`: pass

## Artifact Boundary

Runtime outputs are stored under `/tmp` and are not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. The 30D path remains governed by actual maturity and the
recorded next check after `2026-07-21T00:00:00Z`. PR #52 should be reviewed as a
post-merge closeout repair, not as an authorization to run a verdict.
