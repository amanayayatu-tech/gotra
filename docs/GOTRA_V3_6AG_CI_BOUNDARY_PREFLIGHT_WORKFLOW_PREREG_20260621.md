# GOTRA v3.6AG CI Boundary Preflight Workflow Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_ci_boundary_preflight_adoption`.

This stage adopts the v3.6AF CI/local boundary preflight in the GitHub Actions
pull-request workflow. It is a lightweight changed-files guard. It does not
score outcomes, does not run formal-lite, does not call providers, does not
call Codex CLI, does not merge PRs, and does not execute v3.7.

This is an engineering/local guard adoption record. No OOS/science/public/trading
claim is made. No investment advice is made. The historical direct arm remains
`direct_llm_parametric_memory_control`.

## Base Stack

The branch is stacked on PR #47:
`codex/gotra-v3-6af-ci-stack-boundary-preflight-20260621`.

Open/unmerged stacked PRs are expected and are not blockers by themselves. Real
blockers remain CI failure, active P1/P2 review threads, topology or conflict
issues, artifact-boundary violations, evidence overclaims, maturity-gate
bypass wording, provider/Codex/formal-lite boundary violations, and schema
failures.

## Adoption Contract

The v3.6AG helper must:

- compute changed tracked files from `base..head`
- skip deleted files
- skip gitlinks, directories, and non-regular files
- avoid scanning historical tracked docs that are not changed
- avoid reading forbidden artifact contents
- scan documentation/workflow text for claim boundaries while keeping Python
  tests and scripts as path-boundary entries, so negative test fixtures do not
  become release claims
- write a local manifest under `/tmp` or workflow temp
- call the v3.6AF wrapper using that manifest
- propagate v3.6AF clean/blocked terminal status as CI exit code

The workflow step is pull-request only. It uses GitHub-provided base/head SHA
values, fetches those objects, and runs:

```bash
uv run python scripts/baseline_v3_6ag_ci_changed_files_preflight.py \
  --base-sha "$BASE_SHA" \
  --head-sha "$HEAD_SHA" \
  --output-root "$RUNNER_TEMP/gotra_v3_6ag_ci_changed_files_preflight"
```

The step does not require GitHub API mutation, provider credentials, Codex CLI,
or formal-lite infrastructure.

## Summary Contract

The summary must include:

- `schema`
- `ci_adoption_run_id`
- `ci_integration_status`
- `changed_file_count`
- `scanned_file_count`
- `skipped_deleted_count`
- `skipped_gitlink_count`
- `skipped_non_file_count`
- `manifest_path`
- `preflight_summary_path`
- `preflight_summary_sha256`
- `preflight_status`
- `artifact_boundary_status`
- `claim_boundary_status`
- `maturity_gate_status`
- `direct_llm_boundary_status`
- `workflow_files_changed`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `auto_merge_executed=false`
- `v3_7_allowed=false`
- `evidence_layer=engineering_ci_boundary_preflight_adoption`
- `non_claims`
- `blocker_reasons`

Allowed CI integration statuses:

- `CI_PREFLIGHT_WIRED`
- `CI_PREFLIGHT_DOCUMENTED_ONLY`
- `BLOCKED_CI_CONFIG_UNSAFE`

Clean preflight exits `0`; blocked/fail terminal statuses exit non-zero.

## Non-Claims

This adoption can say the changed-file CI guard is wired and locally validated.
It may not say:

- the next numbered verdict stage has permission to run
- the long-horizon forward-live verdict gate has opened
- GOTRA has external validation
- any regulated recommendation is supported
- the historical direct-control arm is a clean no-future baseline

v3.7 remains forbidden until true 30D actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
