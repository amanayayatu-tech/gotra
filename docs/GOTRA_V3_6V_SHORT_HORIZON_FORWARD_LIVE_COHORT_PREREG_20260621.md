# GOTRA v3.6V Short-Horizon Forward-Live Cohort Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: short-horizon forward-live cohort planning and local dry-run
validation only.

This stage defines a new fast-feedback short-horizon experiment family. It does
not inherit conclusions from the existing 30D forward-live cohort and it cannot
be used as a substitute for the 30D v3.7 verdict.

This stage does not run Kimi/GLM/DeepSeek provider APIs, does not call the
Codex CLI backend, does not run formal-lite, and does not create OOS,
science/public, or trading/investment claims. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Motivation

The actual 30D forward-live cohort remains `DATA_NOT_MATURED`, with the next
30D recheck at `2026-07-21T00:00:00Z`. The project should not fabricate a 30D
verdict before maturity, but it can start a separate short-horizon cohort to
surface obvious capture, metadata, parsing, provenance, and maturity issues
within 1D / 3D / 5D windows.

## Planned Family

Family name:

`v3.6v_short_horizon_forward_live`

Horizons:

- `1D`
- `3D`
- `5D`

Outcome maturity rule:

- The cache has daily close rows without intraday availability.
- Daily close for date `D` is considered available at `D + 1 day 00:00:00 UTC`.
- Short-horizon outcomes must not be scored before that timestamp.

Default capture metadata for any future real capture:

- backend: `codex_cli_llm_backend`
- model default: `gpt-5.5`
- reasoning default: `high`
- run id
- horizon
- capture timestamp UTC
- decision date local
- horizon end date
- latest visible price date
- prompt hash
- transcript path if a real backend capture is run
- parsed decision hash if a real backend capture is run
- deterministic reference metadata
- `future_outcome_status=not_matured`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

No real capture is performed by this prereg/local dry-run.

## Dry-Run Planner

Script:

```bash
scripts/baseline_v3_6v_short_horizon_cohort_plan.py
```

The planner is local and deterministic. It reads price cache metadata, computes
short-horizon cohort points, expected backend decision counts for a future
capture, deterministic reference counts, future-data guards, and outcome
maturity timestamps.

It must not call provider APIs, Codex CLI, formal-lite, or v3.7 verdict code.

## Local Dry-Run

Command:

```bash
uv run python scripts/baseline_v3_6v_short_horizon_cohort_plan.py \
  --plan-run-id baseline_v3_6v_short_horizon_cohort_plan_20260621T034446Z \
  --output-dir /tmp/gotra_v3_6u_v_parallel_feedback_20260621T034446Z/v36v/runs \
  --capture-timestamp-utc 2026-06-21T03:00:00Z
```

Output summary, not committed:

`/tmp/gotra_v3_6u_v_parallel_feedback_20260621T034446Z/v36v/runs/baseline_v3_6v_short_horizon_cohort_plan_20260621T034446Z/summary.json`

Summary sha256:

`23540125b51a835a5c56a60c0eb9837ba1b37ba770bf36d781a81cdb156de515`

Dry-run result:

- Status: `SHORT_HORIZON_COHORT_PLAN_READY`
- Tickers: `5`
- Horizons: `1, 3, 5`
- Cohort points: `15`
- Arms: `4`
- Input layers: `2`
- Expected backend decisions if a future real capture is authorized: `120`
- Deterministic reference expected count: `15`
- Future-data violation count: `0`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`
- 30D v3.7 verdict allowed: `false`
- Earliest short-horizon maturity availability: `2026-06-23T00:00:00Z`

## Feedback Timing

If a future real short-horizon capture is separately authorized and run:

- 1D feedback can first be checked after the 1D horizon close is available
  under the daily-close rule, e.g. `2026-06-23T00:00:00Z` for a
  `2026-06-21` local decision date.
- 3D feedback can first be checked around `2026-06-25T00:00:00Z`.
- 5D feedback can first be checked around `2026-06-27T00:00:00Z`.

These short-horizon checks are for fast operational feedback. They are not
equivalent to 30D outcomes and cannot be used to bypass the 30D maturity gate.

## Acceptance Boundary

Short-horizon output can be used to find:

- capture metadata defects
- prompt/output parsing defects
- future-data guard defects
- provenance and maturity-rule defects
- obvious short-window behavioral anomalies

Short-horizon output cannot be used to claim:

- 30D forward-live verdict
- OOS proof
- science/public proof
- trading or investment advice
- direct equivalence to historical/internal formal-lite or provider API results

## Relationship To v3.6U And 7/21

v3.6U gives an internal historical/offline deterministic regression conclusion
today. v3.6V gives a separate short-horizon future-only path for faster
operational feedback if a future capture is authorized.

The 30D cohort remains governed by v3.6S/v3.6T maturity monitoring. The
`2026-07-21T00:00:00Z` recheck remains responsible for the actual 30D verdict
readiness gate. v3.6V does not change that responsibility.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6v_short_horizon_cohort_plan.py scripts/baseline_v3_deterministic_price_only_verdict.py
uv run ruff check --no-cache scripts/baseline_v3_6v_short_horizon_cohort_plan.py tests/test_short_horizon_cohort_plan.py scripts/baseline_v3_deterministic_price_only_verdict.py tests/test_deterministic_price_only_verdict.py
uv run pytest -q tests/test_short_horizon_cohort_plan.py tests/test_deterministic_price_only_verdict.py
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused tests: `23 passed`
- Full test suite: `381 passed`
- `git diff --check`: pass
