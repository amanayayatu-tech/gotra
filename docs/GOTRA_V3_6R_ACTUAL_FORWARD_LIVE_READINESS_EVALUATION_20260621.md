# GOTRA v3.6R Actual Forward-Live Readiness Evaluation

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: actual-readiness / data-maturity engineering snapshot only.

This document records a read-only discovery of locally available forward-live
artifacts and one v3.6 readiness-gate run against the discovered actual artifact
set. It does not run Kimi/GLM/DeepSeek provider APIs, does not call the Codex CLI
backend, does not run formal-lite, and does not start or score a forward-live
experiment.

This is not OOS evidence, not science/public proof, not trading or investment
advice, and not a deterministic / `full_gotra` / ksana winner verdict.
Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base main: `origin/main @ b4fc74f401d811c9a58112db26acd8190a2e10df`
- Branch: `codex/gotra-v3-6r-actual-readiness-evaluation-20260621`

## Artifact Discovery

Discovery roots checked:

- `data/backtest/runs`
- `/tmp` v3.5 forward-live patterns

`/tmp` had no retained v3.5B/v3.5C/v3.5D/v3.5E artifacts matching the discovery
patterns at evaluation time. The repo-local ignored run directory contained only
v3.5A capture/reference artifacts:

| Schema | Count | Run id count |
| --- | ---: | ---: |
| `gotra.baseline_v3_5a.forward_live_capture.v1` | 128 | 4 |
| `gotra.baseline_v3_5a.deterministic_price_only_capture_reference.v1` | 16 | 4 |
| `gotra.baseline_v3_5a.forward_live_capture_summary.v1` | 4 | 4 |
| `gotra.baseline_v3_5a.forward_live_capture_manifest.v1` | 4 | 4 |
| v3.5B resolver outcome schemas | 0 | 0 |
| v3.5C scheduler schemas | 0 | 0 |
| v3.5D operating-loop schemas | 0 | 0 |
| v3.5E scorer summary schemas | 0 | 0 |

Discovered v3.5A run summaries:

| Run id | Summary sha256 | Status | Outcome status | Capture artifacts | Deterministic refs |
| --- | --- | --- | --- | ---: | ---: |
| `baseline_v3_5a_forward_live_codex_smoke_20260620T132011Z` | `ad92f573576349108f9b5fa4467e2969d03234bd238c802ec8bb72a3a3f63dd0` | `FORWARD_LIVE_CAPTURE_PASS` | `NOT_MATURED` | 8 | 1 |
| `baseline_v3_5a_forward_live_mock_20260620T131950Z` | `3398cee40ce89bb5df40dcdd7a199879e6cf83e4fe384f932dede7e364fd3daf` | `FORWARD_LIVE_CAPTURE_PASS` | `NOT_MATURED` | 40 | 5 |
| `baseline_v3_5a_forward_live_mock_review_fix_20260620T133922Z` | `a95a447e6a05b79548a79b2f51f7825d8f81f78a8d2a5b55f32ff7e540a3da14` | `FORWARD_LIVE_CAPTURE_PASS` | `NOT_MATURED` | 40 | 5 |
| `baseline_v3_5a_forward_live_mock_followup_20260620T135203Z` | `b4ebcc9a9da27734e868e4c7c9aacb682931db426977dff5e296530ce2402233` | `FORWARD_LIVE_CAPTURE_PASS` | `NOT_MATURED` | 40 | 5 |

The readiness run used the latest coherent v3.5A root:

`data/backtest/runs/baseline_v3_5a_forward_live_mock_followup_20260620T135203Z`

This avoids cross-run duplicate deterministic-reference keys while still using
actual local artifacts rather than synthetic `/tmp` fixtures.

## Readiness Gate Run

Command:

```bash
uv run python scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py \
  --input-root data/backtest/runs/baseline_v3_5a_forward_live_mock_followup_20260620T135203Z \
  --readiness-run-id baseline_v3_6_forward_live_verdict_readiness_actual_20260620T200240Z \
  --output-dir /tmp/gotra_v3_6r_actual_readiness_20260620T200240Z/runs
```

Readiness output:

- Run id: `baseline_v3_6_forward_live_verdict_readiness_actual_20260620T200240Z`
- Summary path: `/tmp/gotra_v3_6r_actual_readiness_20260620T200240Z/runs/baseline_v3_6_forward_live_verdict_readiness_actual_20260620T200240Z/summary.json`
- Summary sha256: `020f7cda6cf0feba6fa5cca2cd01647ed64572de519c8866fbcfa9b5b9aa5c75`
- Gate status: `BLOCKED_PROVENANCE`
- Data-maturity interpretation: `DATA_NOT_MATURED`

Key counts:

- Candidate JSON count: `47`
- Deterministic reference available count: `5`
- Matured outcome count: `0`
- Scored outcome count: `0`
- Outcome artifact count: `0`
- `full_gotra` available count: `0`
- Paired candidate count: `0`
- Paired clean count: `0`
- Ticker / cluster count: `0`
- Date count: `0`
- Future-data violation count: `0`
- Provenance failure count: `1`
- Scorer summary count: `0`
- Scorer summary success count: `0`
- Bootstrap eligible: `false`
- HAC eligible: `false`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`
- `direct_llm_interpretation`: `direct_llm_parametric_memory_control`

Blocking reasons:

- `missing_matured_outcome_scorer_summary`
- `missing_full_gotra_outcomes`
- `no_resolved_mature_outcomes`
- `no_clean_deterministic_full_gotra_pairs`
- `scored_outcome_count_below_minimum`
- `cluster_count_below_minimum`
- `date_count_below_minimum`
- `provenance_failure_detected`

## Interpretation

Actual local artifacts are not ready for v3.7 verdict planning.

The machine currently has v3.5A capture/reference artifacts, including one Codex
smoke capture and mock capture runs, but it does not have matured resolved
outcome artifacts, scheduler/resolver provenance chains, operating-loop
summaries, or a successful v3.5E scorer summary for those captures.

The prior PR #34 `READY_FOR_FORWARD_LIVE_VERDICT` was fixture-level `/tmp`
readiness validation. It must not be treated as actual forward-live artifact
readiness.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py
uv run ruff check --no-cache scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py tests/test_forward_live_verdict_readiness_gate.py
uv run pytest -q tests/test_forward_live_verdict_readiness_gate.py
uv run pytest -q tests/test_forward_live_outcome_resolver.py tests/test_forward_live_outcome_scheduler.py tests/test_forward_live_operating_loop.py tests/test_forward_live_matured_outcome_scorer.py
```

Results:

- py_compile: pass
- Ruff: pass
- v3.6 focused tests: `17 passed`
- v3.5B/v3.5C/v3.5D/v3.5E regression tests: `46 passed`

## Artifact Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

The readiness summary remains in `/tmp` and is referenced only by path and hash.

## Next Action

Do not start v3.7 verdict from the current actual artifact state.

Next action is to monitor/wait until forward-live horizons mature, then run the
v3.5B resolver, v3.5C scheduler, v3.5D operating loop, v3.5E scorer, and v3.6
readiness gate on the actual artifacts. Only a real artifact status of
`READY_FOR_FORWARD_LIVE_VERDICT` should unblock a separately preregistered v3.7
verdict attempt.
