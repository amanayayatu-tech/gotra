# Stage 4 Final Verdict

Generated at: `2026-06-16 02:29:11 CST (+0800)`

## Verdict

Stage 4 is stopped at the Stage 3 reproducibility gate. The full/monthly dual-arm scientific run
was not started, so H1/H2/H3 were not tested and there is no valid Stage 4 evidence for or against
the cognitive-compounding net incremental effect.

The blocking A-class gate is baseline replay direction reproducibility:

- Required: direction agreement `>= 0.95`.
- Observed: `102 / 126 = 0.8095238095`.
- Result: FAIL.

This cannot be reported as a valid Stage 4 scientific experiment. It also cannot be upgraded into a
claim about cognitive compounding, because only the baseline sampled replay gate was run.

## What Ran

1. Stage 4 preregistration was committed before Stage 4 engineering and provider outputs.
2. The Alaya arm prompt state was upgraded from raw matured feedback to structured knowledge cards
   plus confidence-adaptation context, with mock tests for future-data exclusion.
3. Local price caches were checked for the full 10-symbol universe. No severe coverage deficiency
   was found. Current walk-forward readiness is `1002 / 1006` eligible monthly decisions with the
   existing cache semantics.
4. The expanded `codex_responses` baseline replay gate was run twice with independent run IDs and
   independent cache namespaces:
   - Subset: `0700.HK,1211.HK,3690.HK,NVDA,AAPL,MSFT`.
   - Interval: `2018-01-01` through `2024-01-01`.
   - Cadence: sampled quarterly, `step-months=3`.
   - Provider concurrency: `2`.
   - Token budget: `600000` per run.

## Stage 3 Replay Results

| Metric | Run 1 | Run 2 |
|---|---:|---:|
| steps_written | 126 | 126 |
| provider_errors | 0 | 0 |
| token_spent | 498055 | 508652 |
| system_health.status | ok | ok |
| audit.ok | true | true |
| cache_hits | 0 | 0 |
| cache_misses | 126 | 126 |

Compare result:

- same: `102`
- total: `126`
- direction agreement: `0.8095238095`
- threshold: `0.95`
- passed: `false`

Total model tokens spent in Stage 3 replay: `1006707`.

## Root Cause Assessment

The two replay runs used identical prompt hashes for all paired steps. Both runs had
`provider_errors=0`, `audit.ok=true`, and `system_health.status=ok`. SSE truncation is unlikely:
truncated or malformed streamed output would have produced parse failures and provider-error steps,
which did not occur.

The failed pairs are not just label-normalization noise. Among the 24 direction mismatches, 21 also
changed the expected-change bucket derived from `expected_change_pct`. The observed failure is
therefore consistent with uncontrolled backend sampling on the ChatGPT OAuth `codex_responses`
route.

## A-Class Gates

| Gate | Result | Evidence |
|---|---|---|
| Zero future-function audit violations | PASS for replay runs | `audit.ok=true` in both summaries |
| No run crash | PASS for replay runs | both replay commands exited 0 |
| Baseline replay direction agreement >=95% | FAIL | `102/126 = 80.95%` |
| Pure-function unit tests pass | PASS before replay | `pytest -q` reported 100 passed |
| Audit trail retained | PASS for replay runs | run summaries, system health, and compare artifact retained locally |

Because one A-class gate failed, Stage 4 is invalid and stops before full/monthly provider science.

## H1/H2/H3

H1, H2, and H3 were not run. No full/monthly `baseline,alaya` scientific run was started. The
correct conclusion is: Stage 4 did not reach the scientific hypothesis test because the provider
reproducibility prerequisite failed.

## Denoising Layer

No denoising layer was enabled in this preregistered Stage 4 run. The expanded naked replay landed
below the preregistered `<84%` branch, where the protocol requires root-cause investigation and
stopping if no engineering/data/SSE defect is found. Implementing a new multi-sampling layer after
this failed gate would be a new route requiring a separate preregistered design, not a continuation
of this locked Stage 4 experiment.

## Boundary

Absolute MSE remains untrusted because current frontier models may have historical market leakage.
This run does not validate cognitive compounding, does not validate H1/H2/H3, and does not change the
Stage 3 verdict or the original preregistration.
