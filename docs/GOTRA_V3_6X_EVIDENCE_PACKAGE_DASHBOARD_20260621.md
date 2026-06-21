# GOTRA v3.6X Evidence Package Decision Dashboard

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local evidence packaging plus historical/internal
summary only.

This package summarizes the current v3.6S/v3.6T/v3.6U/v3.6V state without
running Kimi/GLM/DeepSeek provider APIs, without calling the Codex CLI backend,
without running formal-lite, and without executing a v3.7 verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base stack head: PR #38
  `codex/gotra-v3-6u-v-parallel-feedback-routes-20260621 @ dd3760a3ef5f326178cb19dc43c48d1d8c886da0`
- Branch:
  `codex/gotra-v3-6x-evidence-package-dashboard-20260621`
- Target PR base:
  `codex/gotra-v3-6u-v-parallel-feedback-routes-20260621`

## Package Builder

Added:

- `scripts/baseline_v3_6x_evidence_package_dashboard.py`
- `tests/test_evidence_package_dashboard.py`

The builder reads the existing v3.6S/v3.6T/v3.6U/v3.6V docs, verifies that
required evidence-boundary snippets are present, and writes a structured JSON
dashboard summary. Runtime output is local only and is not committed.

Review hardening added after PR #39 self-audit:

- `--source-doc` now overrides by known `doc_id` instead of replacing the
  entire default source document set.
- Single-document overrides keep the other default source docs and preserve the
  default required boundary snippets.
- Unknown source doc ids are rejected.
- Any overridden source doc that lacks required boundary snippets blocks
  `EVIDENCE_PACKAGE_READY`.

Required dashboard fields include:

- `thirty_day_forward_live_maturity_status`
- `next_check_after`
- `v3_7_allowed`
- `historical_internal_verdict`
- `short_horizon_status`
- `open_pr_stack`
- `active_blockers`
- `can_say`
- `cannot_say`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Source Documents

The dashboard consumes these committed source docs:

- `docs/GOTRA_V3_6S_ACTUAL_MATURITY_MONITOR_RESULT_20260621.md`
- `docs/GOTRA_V3_6T_FORWARD_LIVE_MONITOR_OPS_RESULT_20260621.md`
- `docs/GOTRA_V3_6U_HISTORICAL_INTERNAL_LARGE_REGRESSION_VERDICT_20260621.md`
- `docs/GOTRA_V3_6V_SHORT_HORIZON_FORWARD_LIVE_COHORT_PREREG_20260621.md`

The local package validation found all four source docs and all required
boundary snippets.

## Current Dashboard Snapshot

Command:

```bash
uv run python scripts/baseline_v3_6x_evidence_package_dashboard.py \
  --package-run-id baseline_v3_6x_evidence_package_dashboard_reviewfix_20260621T043048Z \
  --output-dir /tmp/gotra_v3_6x_evidence_package_dashboard_reviewfix_20260621T043048Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6x_evidence_package_dashboard_reviewfix_20260621T043048Z/runs/baseline_v3_6x_evidence_package_dashboard_reviewfix_20260621T043048Z/summary.json`

Summary sha256:

`9548b0b3d5b38b1c0ced19146d84876252c8511f0cf03179d0a28d39f1f6a9c5`

Summary status:

`EVIDENCE_PACKAGE_READY`

Key fields:

- Source document count: `4`
- Source document missing count: `0`
- Required boundary snippet missing count: `0`
- 30D forward-live maturity status: `DATA_NOT_MATURED`
- Next 30D maturity recheck: `2026-07-21T00:00:00Z`
- v3.7 verdict allowed: `false`
- Active blockers: `none_currently_detected`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`

## Existing Historical/Internal Summary

The package records the existing v3.6U conclusion only as
historical/internal fast-feedback evidence:

- Primary comparison:
  `deterministic_price_only_baseline_vs_full_gotra`
- Status: `FULL_GOTRA_BETTER`
- Criterion: `mse_loss_diff_det_minus_full`
- Reason: `mse_ci_excludes_zero_positive`
- Scope: `historical_internal_mse_specific_only`

This is not a forward-live result and not a broad superiority claim. It does
not create an OOS/science/public/trading conclusion, and it does not establish
a ksana/full_gotra H2 winner.

## 30D Maturity Status

The 30D actual forward-live path remains:

- Status: `DATA_NOT_MATURED`
- Next check after: `2026-07-21T00:00:00Z`
- v3.7 allowed now: `false`

The correct next 30D action is continued maturity monitoring or a recheck at or
after the next-check timestamp. v3.7 must not execute until real artifacts and
current-root provenance reach `READY_FOR_FORWARD_LIVE_VERDICT`.

## Short-Horizon Status

v3.6V is a separate short-horizon family:

- Status: `SHORT_HORIZON_COHORT_PLAN_READY`
- Horizons: `1D`, `3D`, `5D`
- Earliest planned short-horizon maturity availability:
  `2026-06-23T00:00:00Z`
- Default future Codex CLI backend setting if separately authorized:
  `model=gpt-5.5`, `reasoning=high`

Short-horizon evidence is not equivalent to the 30D cohort and cannot bypass
the 30D maturity gate.

## Open PR Stack

Current stacked PR status at package time:

| PR | Title | Head | Status |
|---:|---|---|---|
| #36 | Add actual forward-live maturity monitor | `365a52a87cb0e1dbed39a3323ffb8bf4de2fd511` | open, CI success, CLEAN, P2 resolved/outdated |
| #37 | Add forward-live maturity monitor operations ledger | `56fe015b8a033878f9ad5378fe83a04e221448af` | open, CI success, CLEAN, P2 resolved/outdated |
| #38 | Add parallel fast-feedback routes | `dd3760a3ef5f326178cb19dc43c48d1d8c886da0` | open, CI success, CLEAN, P2 resolved/outdated |

Open PRs are allowed in this workflow. The fact that these PRs are unmerged is
not itself a blocker for this follow-up packaging PR, and this stage does not
merge them.

## Can Say / Cannot Say

Can say:

- Engineering/local monitor and readiness chain exists.
- A historical/internal offline MSE-specific
  `deterministic_price_only_baseline` vs `full_gotra` result exists.
- 30D actual forward-live outcomes are not mature.
- A short-horizon experiment family/preregistration exists as a separate path.
- Open stacked PRs can be clean without being merged.

Cannot say:

- OOS pass.
- Science/public proof.
- Trading or investment recommendation.
- 30D forward-live verdict.
- ksana/full_gotra H2 winner.
- Provider/formal-lite acceptance.
- `direct_llm` is a clean no-future baseline.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6x_evidence_package_dashboard.py
uv run ruff check --no-cache scripts/baseline_v3_6x_evidence_package_dashboard.py tests/test_evidence_package_dashboard.py
uv run pytest -q tests/test_evidence_package_dashboard.py
uv run python -m py_compile scripts/baseline_v3_6x_evidence_package_dashboard.py scripts/baseline_v3_6t_forward_live_monitor_ops.py scripts/baseline_v3_6v_short_horizon_cohort_plan.py
uv run ruff check --no-cache scripts/baseline_v3_6x_evidence_package_dashboard.py tests/test_evidence_package_dashboard.py scripts/baseline_v3_6t_forward_live_monitor_ops.py tests/test_forward_live_monitor_ops.py scripts/baseline_v3_6v_short_horizon_cohort_plan.py tests/test_short_horizon_cohort_plan.py
uv run pytest -q tests/test_evidence_package_dashboard.py tests/test_forward_live_monitor_ops.py tests/test_short_horizon_cohort_plan.py
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused tests: `8 passed`
- Related v3.6T/v3.6V regression set: `24 passed`
- Full test suite: `390 passed`
- `git diff --check`: pass

## Artifact Boundary

The dashboard runtime summary is stored under `/tmp` and is not committed. This
stage must not commit `data/backtest/runs/**`, `data/paper_trading/**`, raw
outputs, transcripts, `.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local
artifacts, or README changes.

## Next Action

Do not execute v3.7. The permitted actions are continued maturity monitoring,
or a separately authorized short-horizon capture/maturity recheck. A v3.7
verdict can only be planned after real actual readiness reaches
`READY_FOR_FORWARD_LIVE_VERDICT` with matching current-root provenance.
