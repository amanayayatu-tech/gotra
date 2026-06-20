# Stage 6 Preregistration

Legacy salvage note: this document is preserved as a historical Stage6 evidence record from a
legacy PR. It is not a new experiment, not a current-main reproducibility claim, not
OOS/science/public proof, and not trading/investment advice.

Generated at: `2026-06-16 13:30:57 CST (+0800)`

This protocol is locked before any Stage 6 engineering change, replay output, or scientific run
output is observed on the `codex/stage6-experiment` branch. Stage 6 is a new preregistered
experiment. It does not amend the Stage 3 verdict, Stage 4 verdict, Stage 5 preregistration, or
any existing `PREREGISTERED` document.

Stage 5 remains a failed reproducibility-gate experiment for its preregistered route. With
multi-sample median denoising at `N=5`, the measured baseline replay direction agreement was
`116 / 126 = 0.9206349206`, below the locked `95%` acceptance threshold. Stage 6 preserves that
conclusion and starts a new protocol.

## Scope

Stage 6 tests the net incremental effect of the cognitive-compounding mechanism under a shared
provider, shared prompt skeleton, preregistered multi-sample median denoising layer, and a
preregistered dead-zone estimator for near-zero expected changes.

It does not claim general market forecasting skill, and it does not interpret absolute MSE as
reliable because current frontier models may contain unavoidable pretraining leakage about
historical market regimes. The scientific claim, if supported, is limited to whether the stateful
cognitive-compounding arm improves paired walk-forward MSE relative to the stateless baseline arm
under this protocol after the A-class replay reproducibility gate is empirically met.

## Universe

The universe is unchanged from Stage 5.

| Symbol | Name | Listing gate |
|---|---|---|
| 0700.HK | Tencent | 2004-06-16 |
| 3690.HK | Meituan | 2018-09-20 |
| 6060.HK | ZhongAn Online | 2017-09-28 |
| NVDA | NVIDIA | 1999-01-22 |
| 1810.HK | Xiaomi | 2018-07-09 |
| 9988.HK | Alibaba HK | 2019-11-26 |
| 1211.HK | BYD H Shares | 2002-07-31 |
| AAPL | Apple | 1980-12-12 |
| TSM | Taiwan Semiconductor | 1997-10-09 |
| MSFT | Microsoft | 1986-03-13 |

Listing gate semantics remain unchanged: any symbol listed after a decision month is marked `N/A`
for that step and excluded from MSE.

## Interval And Cadence

- Interval: `2016-01-01` through `2026-01-31`.
- The first 12 months are initialization only.
- Cadence: full monthly walk-forward with 30-day scoring windows.

## Provider

- Provider: `codex_responses`, the ChatGPT OAuth direct Responses API route used by Codex.
- Transport: streaming SSE over the Codex OAuth backend.
- Determinism controls: this backend does not accept explicit `temperature`, `top_p`, or `seed`.
- Reproducibility criterion: empirically measured baseline replay direction agreement must be at
  least `95%`. The criterion is direction-level agreement after the preregistered median denoising
  and dead-zone estimator, not byte-level equality.

## Stage 6 Estimator

Stage 6 keeps the Stage 5 multi-sample median denoising layer and adds a preregistered dead-zone
decision rule for near-zero medians.

- For every decision point, the provider sends the same prompt through `N` independent
  `codex_responses` samples.
- The Stage 6 value of `N` is fixed at `5`.
- Each sample uses the same no-temperature wire payload as Stage 5. No unsupported decode controls
  are added.
- Each single-sample transport failure may be retried by the configured engineering retry policy.
  The retry decision must depend only on transport/provider failure signals such as timeout,
  connection failure, SSE interruption, or HTTP error. A successfully returned sample must not be
  discarded because of response content, answer speed, proximity to zero, direction uncertainty, or
  any scientific result.
- The sample set is valid only when all `N=5` samples produce valid decision JSON. If fewer than
  five valid samples are available after retries, the decision point follows the existing
  provider-error semantics. The estimator must not take a median from fewer than `N` valid samples.
- Let `m` be the median of the five parsed `expected_change_pct` values.
- The preregistered dead-zone threshold is `epsilon = 0.3%` (`0.3` in percentage-point units). This
  value is locked before Stage 6 replay or scientific outputs and must not be changed within Stage
  6.
- If `abs(m) <= epsilon`, the decision direction is `neutral` and the final predicted
  `expected_change_pct` used for MSE is `0.0`.
- If `m > epsilon`, the decision direction is `long` and the final predicted
  `expected_change_pct` is `m`.
- If `m < -epsilon`, the decision direction is `avoid` and the final predicted
  `expected_change_pct` is `m`.
- `vote_consistency` is recorded as the fraction of samples in the modal pre-dead-zone sample
  direction.

The dead-zone rule reflects the Stage 5 observation that the remaining replay instability is
dominated by near-zero median values whose signs can flip across uncontrolled backend samples.
`epsilon = 0.3%` is a fixed preregistered threshold for this new Stage 6 protocol. It must not be
adjusted after observing replay details, H1, H2, H3, style-window results, convergence curves, MSE
values, or any other scientific output.

## Replay Agreement

Replay agreement is computed on the final Stage 6 direction label. `neutral` is an ordinary
direction category:

- `neutral` versus `neutral` is counted as agreement.
- `neutral` versus `long` or `avoid` is counted as disagreement.
- `long` versus `avoid` is counted as disagreement.

There is no special neutral exemption in the `95%` replay gate.

## Arms

- `baseline`: stateless single-step decision. It receives the same price slice and prompt skeleton
  as the Alaya arm, but no cognitive-compounding state and no denoising confidence context.
- `alaya`: stateful cognitive-compounding decision. It receives only matured prior outcomes for the
  same symbol where `outcome_availability_date <= decision_date`, represented as knowledge cards,
  confidence-adaptation context, and denoising confidence context when available.

Both arms must use the same provider, prompt skeleton, `N=5`, dead-zone `epsilon = 0.3%`, timeout
policy, retry policy, and bounded-concurrency policy. The only experimental variable is whether
cognitive-compounding state is present.

## Engineering Runtime Policy

The Stage 6 runtime may use bounded intra-decision sample concurrency and a total single-sample
wall-clock deadline. These are engineering throughput and failure-handling policies, not scientific
variables. They must be identical for baseline and Alaya.

The default Stage 6 runtime is:

- `--codex-responses-samples 5`
- `--codex-responses-sample-concurrency 2`
- `--codex-responses-provider-connection-limit 4`
- `--codex-responses-sample-timeout-seconds 90`
- `--codex-responses-sample-retries 2`

The product of active decision-point concurrency and intra-decision sample concurrency must remain
bounded by the provider connection limit. Engineering self-correction may reduce concurrency after
provider transport failures, but it must not change `N`, `epsilon`, the replay threshold, or any
scientific hypothesis threshold.

## Style Windows

The style windows are unchanged from Stage 5.

| Window | Start | End |
|---|---:|---:|
| US-China trade war | 2018-03-01 | 2019-12-31 |
| COVID shock | 2020-01-01 | 2020-04-30 |
| HK platform regulation | 2021-07-01 | 2021-12-31 |
| Global rate hikes | 2022-01-01 | 2022-12-31 |
| Generative AI regime | 2023-01-01 | 2024-12-31 |

## Metrics

- Per-step error: `actual_change_pct - expected_change_pct`.
- For `neutral` decisions, `expected_change_pct` is preregistered as `0.0`, so neutral points
  participate in MSE as a zero-change prediction.
- Per-step MSE: squared error.
- Primary differential metric: `MSE_baseline - MSE_alaya`.
- H3 significance test: paired loss-differential test using HAC/Newey-West robust standard errors.
- Neutral share is reported as descriptive evidence for the replay gate and final verdict, not as
  a hypothesis threshold.

## Hypotheses

The Stage 5 hypothesis thresholds are unchanged.

- H1 convergence: `MSE_alaya` over the final third of valid scored steps is at least `15%` lower
  than `MSE_alaya` over the first third.
- H2 drift resistance: in every style window above, `MSE_alaya < MSE_baseline` over valid paired
  steps in that window.
- H3 incremental significance: mean `MSE_baseline - MSE_alaya > 0` with HAC/Newey-West robust
  p-value `< 0.05`.

These thresholds, windows, universe, `epsilon = 0.3%`, `N=5`, and the `95%` replay gate are locked
before observing Stage 6 scientific outputs and must not be adjusted after seeing H1/H2/H3 results.

## A-Class Correctness Gates

All A-class gates must pass for the experiment to be valid:

- Zero future-function audit violations.
- No run crash.
- Baseline replay direction agreement at or above `95%` after the preregistered median denoising
  and dead-zone estimator.
- Pure-function unit tests pass.
- Full audit trail is retained.

A-class gates are validity gates. The H1/H2/H3 outcomes are the scientific conclusion gates. If the
A-class gates pass but hypotheses fail, the correct conclusion is a valid negative or mixed Stage 6
result, not a threshold or epsilon change.

## Failure Handling

If the Stage 6 sampled replay gate remains between `90%` and `95%`, Stage 6 must report that
`epsilon = 0.3%` was insufficient to eliminate near-zero replay noise, including neutral share and
the observed distribution of remaining mismatches. It must stop before the full scientific run and
wait for a separate future preregistered stage if `epsilon` is to be changed.

If the sampled replay gate falls below `90%` or shows abnormal provider/runtime behavior, the correct
action is engineering diagnosis of dead-zone implementation, SSE deadline handling, retry semantics,
or bounded concurrency. It is not a license to alter the replay threshold, universe, windows,
`epsilon`, `N`, or hypothesis thresholds.

## Inference Limits

The ready-made model may have learned historical information during pretraining. Absolute MSE is not
credible evidence of real market forecasting skill. This preregistered experiment only evaluates the
net incremental effect of the cognitive-compounding mechanism under the shared-input/shared-provider
setup. Preregistration and this time lock are used to prevent p-hacking; Stage 6 is a new phase, not
a retroactive change to Stage 5.
