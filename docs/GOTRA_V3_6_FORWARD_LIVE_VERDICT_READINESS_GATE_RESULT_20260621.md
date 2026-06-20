# GOTRA v3.6 Forward-Live Verdict Readiness Gate Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: readiness-gate engineering/local validation only.

This result does not run Kimi/GLM/DeepSeek provider APIs, does not call the Codex
CLI backend, does not run formal-lite, and does not start or score a forward-live
experiment. It is not OOS evidence, not science/public proof, not a trading or
investment claim, and not a `full_gotra` / deterministic / ksana winner verdict.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline and is not used for this readiness decision.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base: `origin/main @ 772656e659d75b9669e00112b2b3ca51f7affd17`
- Branch: `codex/gotra-v3-6-forward-live-verdict-readiness-gate-20260621`

## Implementation Summary

Added a local v3.6 readiness gate that reads v3.5 forward-live artifacts and
decides whether a later verdict stage is ready. It does not compute a verdict.

The gate reports:

- matured and scored `RESOLVED` outcome counts
- ticker/cluster and decision-date coverage
- deterministic price-only reference availability
- `full_gotra` availability on the preregistered primary input layer
- clean deterministic-reference / `full_gotra` pair coverage
- source/capture/outcome/scorer future-data violations
- provenance completeness across source capture, scheduler, resolver, outcome,
  and scorer summary
- bootstrap/HAC eligibility flags only

Statuses are limited to readiness/blocking states:

- `READY_FOR_FORWARD_LIVE_VERDICT`
- `DATA_NOT_MATURED`
- `DATA_INSUFFICIENT`
- `INSUFFICIENT_CLUSTER_COVERAGE`
- `BLOCKED_PROVENANCE`
- `BLOCKED_FUTURE_DATA`
- `BLOCKED_PAIRING`

## Local Readiness Validation

Local validation used synthetic `/tmp` fixtures to exercise a clean sufficient
readiness path. No provider, Codex CLI backend, formal-lite, transcript, or raw
LLM artifact was used.

- Run id: `baseline_v3_6_forward_live_verdict_readiness_local_20260620T191054Z`
- Summary path: `/tmp/gotra_v3_6_readiness_validation_20260620T191054Z/runs/baseline_v3_6_forward_live_verdict_readiness_local_20260620T191054Z/summary.json`
- Summary sha256: `b0333aa4e63f3e7391a65e93027e5ba238d4ea0e5533a2a8b6485680f528b565`
- Status: `READY_FOR_FORWARD_LIVE_VERDICT`
- Matured outcome count: `4`
- Scored outcome count: `4`
- Ticker / cluster count: `2`
- Date count: `2`
- Deterministic reference available count: `4`
- `full_gotra` available count: `4`
- Paired clean count: `4`
- Future-data violation count: `0`
- Provenance failure count: `0`
- Provenance link count: `4`
- Bootstrap eligible: `true`
- HAC eligible: `true`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`

This readiness pass is fixture-level engineering validation. It does not mean
real forward-live artifacts are sufficient for a verdict.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_5_forward_live_outcome_resolver.py scripts/baseline_v3_5_forward_live_outcome_scheduler.py scripts/baseline_v3_5_forward_live_operating_loop.py scripts/baseline_v3_5_forward_live_matured_outcome_scorer.py
uv run ruff check --no-cache scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py tests/test_forward_live_verdict_readiness_gate.py
uv run pytest -q tests/test_forward_live_verdict_readiness_gate.py
uv run pytest -q tests/test_forward_live_outcome_resolver.py tests/test_forward_live_outcome_scheduler.py tests/test_forward_live_operating_loop.py tests/test_forward_live_matured_outcome_scorer.py
uv run pytest -q
uv run python scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py --input-root /tmp/gotra_v3_6_readiness_validation_20260620T191054Z/input --readiness-run-id baseline_v3_6_forward_live_verdict_readiness_local_20260620T191054Z --output-dir /tmp/gotra_v3_6_readiness_validation_20260620T191054Z/runs
```

Results:

- py_compile: pass
- Ruff: pass
- v3.6 focused tests: `11 passed`
- v3.5B/v3.5C/v3.5D/v3.5E regression tests: `46 passed`
- full pytest: `348 passed`
- local readiness validation: `READY_FOR_FORWARD_LIVE_VERDICT`

## Artifact Boundary

No run artifacts, transcripts, raw outputs, provider raw files, `.env*`, DB,
bundle/tar/zip, `data/backtest/runs/**`, `data/paper_trading/**`, Stage8/Stage9
local artifacts, or README changes are intended for commit.

The local readiness summary remains under `/tmp` and is referenced only by path
and hash.

## Next Action

After this PR is reviewed and merged, a separate v3.7 goal may preregister a
real forward-live verdict attempt if actual matured artifacts meet the readiness
gate. v3.6 itself does not start v3.7 and does not output a verdict.
