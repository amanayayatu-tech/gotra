# GOTRA v3.7 Forward-Live Entry Decision Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local v3.7 entry decision only.

This result records a current-date actual 30D readiness refresh and a v3.7 entry
decision closeout. It does not run Kimi/GLM/DeepSeek provider APIs, does not
call the Codex CLI backend, does not run formal-lite, does not execute a 30D
forward-live verdict, and does not produce a deterministic / `full_gotra` /
ksana winner.

Non-claim boundary:

- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- Historical `direct_llm=direct_llm_parametric_memory_control`; not a clean
  no-future baseline.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base branch: `origin/main`
- Base head before branch: `6eb5f47f815ea9dc2aa360046a6da26f4f3eb0cd`
- Branch: `codex/gotra-v3-7-readiness-refresh-harness-prep-20260621`
- PR: https://github.com/amanayayatu-tech/gotra/pull/53
- GitHub CI: two `Python checks` passed during PR validation.
- `origin/main` after PR creation: unchanged at
  `6eb5f47f815ea9dc2aa360046a6da26f4f3eb0cd`

## Actual 30D Readiness Refresh

Command:

```bash
uv run python scripts/baseline_v3_6s_actual_maturity_monitor.py \
  --input-root data/backtest/runs \
  --monitor-run-id baseline_v3_6s_actual_maturity_monitor_v3_7_entry_refresh_20260621T132608Z \
  --as-of-timestamp-utc 2026-06-21T13:26:08Z \
  --output-dir /tmp/gotra_v3_7_entry_readiness_refresh_20260621T132608Z/runs \
  --allow-overwrite
```

Output:

- Summary path:
  `/tmp/gotra_v3_7_entry_readiness_refresh_20260621T132608Z/runs/baseline_v3_6s_actual_maturity_monitor_v3_7_entry_refresh_20260621T132608Z/summary.json`
- Summary sha256:
  `8ae97a6ff9a17acf207c4136476697357dbdc5e75186067e3417be134b26c7c5`
- Status: `DATA_NOT_MATURED`
- Readiness gate status: `NOT_RUN`
- Checked capture run count: `4`
- Capture artifact count: `128`
- Matured candidate count: `0`
- Resolved count: `0`
- Scored count: `0`
- Not matured count: `128`
- Next check after: `2026-07-21T00:00:00Z`
- Blocker reasons:
  - `capture_horizons_not_matured`
  - `readiness_not_ready`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`
- v3.7 actual verdict executable: `false`

## v3.7 Entry Decision

Command:

```bash
uv run python scripts/baseline_v3_7_forward_live_entry_decision.py \
  --readiness-summary-path /tmp/gotra_v3_7_entry_readiness_refresh_20260621T132608Z/runs/baseline_v3_6s_actual_maturity_monitor_v3_7_entry_refresh_20260621T132608Z/summary.json \
  --readiness-summary-sha256 8ae97a6ff9a17acf207c4136476697357dbdc5e75186067e3417be134b26c7c5 \
  --entry-run-id baseline_v3_7_forward_live_entry_decision_actual_20260621T132608Z \
  --as-of-timestamp-utc 2026-06-21T13:26:08Z \
  --output-dir /tmp/gotra_v3_7_entry_decision_20260621T132608Z/runs \
  --allow-overwrite
```

Output:

- Summary path:
  `/tmp/gotra_v3_7_entry_decision_20260621T132608Z/runs/baseline_v3_7_forward_live_entry_decision_actual_20260621T132608Z/summary.json`
- Summary sha256:
  `922cfd94044373811849b93e1dbb666e32851dd6638696b731079e449b591819`
- Manifest path:
  `/tmp/gotra_v3_7_entry_decision_20260621T132608Z/runs/baseline_v3_7_forward_live_entry_decision_actual_20260621T132608Z/manifest.json`
- Manifest sha256:
  `3402c6b01d84caf9039ef8ec00be08ad6cd8d47d9a4e99a8e279345de1b961b4`
- Entry status: `V3_7_VERDICT_BLOCKED_BY_ACTUAL_READINESS`
- Readiness status: `DATA_NOT_MATURED`
- Source monitor status: `DATA_NOT_MATURED`
- Source readiness gate status: `NOT_RUN`
- Checked capture run count: `4`
- Matured candidate count: `0`
- Resolved count: `0`
- Scored count: `0`
- Paired clean count: `0`
- `full_gotra` available count: `0`
- Deterministic reference available count: `0`
- Next check after: `2026-07-21T00:00:00Z`
- Blocker reasons:
  - `capture_horizons_not_matured`
  - `readiness_not_ready`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`
- v3.7 actual verdict executable: `false`
- v3.7 verdict executed: `false`
- Harness prep allowed: `true`

## Decision

The actual 30D forward-live path is not ready for a real v3.7 deterministic
reference vs `full_gotra` verdict. The correct current status is:

`V3_7_VERDICT_BLOCKED_BY_ACTUAL_READINESS`

The non-blocking next work may prepare fixture-only harness/report/provenance
infrastructure, dashboard hardening, or short-horizon recheck handling. None of
those tasks can substitute for the 30D actual readiness gate.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7_forward_live_entry_decision.py
uv run python -m py_compile scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6s_actual_maturity_monitor.py scripts/baseline_v3_6t_forward_live_monitor_ops.py
uv run ruff check --no-cache scripts/baseline_v3_7_forward_live_entry_decision.py tests/test_forward_live_v3_7_entry_decision.py
uv run pytest -q tests/test_forward_live_v3_7_entry_decision.py
uv run pytest -q tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_maturity_monitor.py tests/test_forward_live_monitor_ops.py tests/test_forward_live_verdict_readiness_gate.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7_entry_docs_20260621T132608Z \
  --output-dir /tmp/gotra_v3_7_entry_claim_scan_20260621T132608Z/runs \
  --file docs/GOTRA_V3_7_FORWARD_LIVE_ENTRY_DECISION_PREREG_20260621.md \
  --file docs/GOTRA_V3_7_FORWARD_LIVE_ENTRY_DECISION_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7 entry decision tests: `7 passed`
- Relevant v3.6/v3.7 regression set: `46 passed`
- Claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - blocked items: `0`
  - warnings: `2` ambiguous readiness wording warnings, no blocker
- Full test suite: `607 passed`
- `git diff --check`: pass
- GitHub CI: two `Python checks` passed during PR #53 validation.

## Artifact Boundary

Actual refresh and entry-decision summaries are stored under `/tmp` and are not
committed. This stage must not commit `data/backtest/runs/**`,
`data/paper_trading/**`, raw outputs, transcripts, `.env*`, SQLite/DB,
bundle/tar/zip, Stage8/Stage9 artifacts, or README changes.
