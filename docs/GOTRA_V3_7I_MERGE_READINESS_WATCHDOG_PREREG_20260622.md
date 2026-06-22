# GOTRA v3.7I Merge-Readiness Watchdog Prereg

Date: 2026-06-22

## Evidence Layer

`engineering_internal_merge_readiness_watchdog`

This stage adds a deterministic local watchdog for PR merge-readiness metadata.
It is fixture-only and does not call providers, Codex CLI backends, formal-lite,
or any LLM. It does not run an actual 30D v3.7 verdict.

The current actual 30D readiness state remains `DATA_NOT_MATURED`.
The next 30D maturity check remains `2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false`.

## Scope

The watchdog validates mock PR, CI, review, and diff metadata before a Judge
auto-merge gate can treat a PR as structurally clean. It checks only
engineering merge-gate conditions:

- base/head refs and SHAs are present.
- `merge_state_status` is `CLEAN`.
- required CI checks completed with success.
- active P1/P2 review threads block.
- draft PRs block.
- changed files do not reference forbidden/raw artifact locations.
- runtime boundary flags are explicitly false.
- claim-boundary text does not exceed engineering/internal scope.
- actual 30D readiness stays below the verdict gate.

Open PR existence is not treated as a blocker by itself. A clean status only
means the fixture is eligible for Judge merge-gate consideration; it is not a
science, public, trading, or investment conclusion.

## Inputs

The command accepts a JSON fixture:

```bash
uv run python scripts/baseline_v3_7i_merge_readiness_watchdog.py \
  --fixture /tmp/mock_pr_fixture.json \
  --output-dir /tmp/gotra_v3_7i_merge_readiness_watchdog/runs
```

Required fixture fields include:

- `base_ref`, `base_sha`, `head_ref`, `head_sha`
- `merge_state_status`, `is_draft`
- `changed_files`, `status_checks`, `review_threads`
- `evidence_layer`
- `actual_30d_readiness_status`
- `v3_7_actual_verdict_executable`
- `provider_or_backend_called`, `codex_cli_new_call`, `formal_lite_entered`

## Status Values

Allowed terminal statuses:

- `MERGE_READINESS_READY`
- `BLOCKED_CI`
- `BLOCKED_REVIEW`
- `BLOCKED_CONFLICT`
- `BLOCKED_DRAFT`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_SCHEMA`
- `DATA_INSUFFICIENT`

Only `MERGE_READINESS_READY` exits zero. All blocked statuses exit nonzero.

## Non-Claims

This prereg is not a provider run, not formal-lite, not an actual 30D verdict,
not OOS/science/public/trading evidence, and not investment advice.
Historical `direct_llm` remains `direct_llm_parametric_memory_control`.
