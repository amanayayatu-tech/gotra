# Stage 6 Final Verdict

Generated at: `2026-06-17 16:52:39 CST (+0800)`

## Verdict

Stage 6 does not validate the cognitive-compounding net incremental effect under the
`gpt-5.5` / `codex_responses` configuration.

The final decision is a failure, for two independent reasons:

- A-class replay reproducibility did not clear the locked `>= 95%` gate after including the HK
  points: `118 / 126 = 93.6508%`.
- H3 did not show a positive statistically significant net incremental effect:
  `mean_loss_diff = -1.044412`, `z = -0.664089`, `p = 0.50663356`, `passed = false`, based on
  `866` paired full-run points.

The observed H3 direction is slightly negative rather than positive. This is not evidence for
cognitive compounding. No epsilon, N, universe, window, hypothesis threshold, or replay threshold is
changed after seeing the results.

## Registered Method

Stage 6 was a new preregistered stage, not a Stage 5 patch. The locked estimator was:

- `N = 5` independent `codex_responses` samples per decision point.
- Median aggregation over `expected_change_pct`.
- Dead-zone direction rule with `epsilon = 0.3` percentage points:
  `|median| <= 0.3` is `neutral`; otherwise direction is the sign of the median.
- `neutral` is an ordinary third direction class in replay comparison. It is not exempted.
- Baseline and Alaya use the same N, timeout, retry, concurrency, median, and dead-zone rules.

## Reproducibility Gate

The final A-class replay gate is failed:

| Metric | Value |
|---|---:|
| Required direction agreement | `>= 0.95` |
| HK-inclusive agreement | `118 / 126 = 0.9365079365` |
| Result | FAIL |

An auxiliary paired-success-only compare artifact exists for the two aggressive replay runs:
`102 / 107 = 0.9532710280`, `passed = true`. This is not used to upgrade the final A-class verdict,
because the final Stage 6 decision keeps the HK-inclusive replay evidence and does not lower or
reinterpret the `95%` gate.

## Full Run

Primary full run:
`stage6_full_n5_deadzone_aggressive_20260616`

| Metric | Value |
|---|---:|
| mode | `full` |
| provider | `codex_responses` |
| arms | `baseline,alaya` |
| steps_written | `2012` |
| scored_steps | `1761` |
| paired_steps | `866` |
| provider_errors | `251` |
| audit.ok | `true` |
| audit violations | `0` |
| token spent | `38359805` |
| system_health.status | `failed` |

The system health failure is due to retained `provider_error` steps, not a zero-future-function
audit failure. The future-data audit passed with `2012` steps checked and `2014` event rows checked.

Provider-error classification from the retained full-run manifest:

| Kind | Count |
|---|---:|
| `provider_limit_429` | `95` |
| `transport_proxy_error` | `107` |
| `transport_connect_error` | `29` |
| `transport_remote_protocol_error` | `1` |
| `transport_timeout` | `19` |
| model content parse/schema failure | `0` |

The repair run `stage6_full_n5_deadzone_aggressive_repair_20260617` was stopped by operator
instruction after writing `6 / 120` planned baseline repair files. It is retained as an artifact but
is not used to change the final Stage 6 conclusion.

## Hypotheses

### H1

H1 failed.

| Metric | Value |
|---|---:|
| first_third_mse | `104.281648` |
| final_third_mse | `153.748701` |
| reduction_pct | `-47.436` |
| threshold_pct | `15.0` |
| passed | `false` |

### H2

H2 was mixed and does not rescue the stage.

| Window | Result | Alaya MSE | Baseline MSE | Steps |
|---|---|---:|---:|---:|
| US-China trade war | PASS | `106.767824` | `115.77003` | `178` |
| COVID shock | FAIL | `119.895419` | `118.574751` | `40` |
| HK platform regulation | FAIL | `103.65111` | `102.953354` | `53` |
| Global rate hikes | PASS | `148.832273` | `150.981597` | `105` |
| Generative AI regime | PASS | `149.218964` | `150.236506` | `179` |

### H3

H3 failed.

| Metric | Value |
|---|---:|
| paired n | `866` |
| mean_loss_diff | `-1.044412` |
| z_score | `-0.664089` |
| p_value | `0.50663356` |
| HAC lag | `5` |
| passed | `false` |

This result is negative and not significant. It does not support a cognitive-compounding net
incremental effect.

## Neutral Rate

| Arm | Neutral Count | Scored Count | Neutral Share |
|---|---:|---:|---:|
| baseline | `2` | `886` | `0.002257` |
| alaya | `7` | `875` | `0.008` |

The dead-zone estimator did not create enough stable neutral mass to remove the reproducibility
bottleneck, and it did not produce a positive H3 effect.

## Uncertainty Evidence

The `1211.HK` / `2022-04-01` point is retained as uncertainty evidence:

| Run | Status | Direction | expected_change_pct | Error Class |
|---|---|---|---:|---|
| `stage6_repro_n5_deadzone_aggressive_run1_20260616` | `provider_error` | n/a | n/a | `transport_timeout` |
| `stage6_repro_n5_deadzone_aggressive_run2_20260616` | `scored` | `long` | `3.5` | n/a |
| `stage6_full_n5_deadzone_aggressive_20260616` baseline | `provider_error` | n/a | n/a | `transport_proxy_error` |
| `stage6_full_n5_deadzone_aggressive_20260616` alaya | `provider_error` | n/a | n/a | `transport_proxy_error` |

This point is not used to claim a model-content effect. It is retained because it illustrates the
remaining engineering/provider uncertainty around HK points.

## Boundary

Absolute MSE remains untrusted because frontier models may have historical market leakage. Stage 6
only tests the preregistered incremental mechanism. Under the current evidence, that mechanism is
not validated.

Stage 5's `92.06%` replay result and Stage 6's `93.65%` HK-inclusive replay result are both
preserved as failures below the locked `95%` A-class threshold. The final conclusion is not softened
by rerunning, dropping hard points, changing epsilon, raising N, or changing comparison rules after
seeing H1/H2/H3.
