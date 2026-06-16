# Stage 5 Preregistration

Generated at: `2026-06-16 08:44:16 CST (+0800)`

This protocol is locked before any Stage 5 engineering change, replay output, or scientific run
output is observed on the `codex/stage5-experiment` branch. Stage 5 is a new preregistered
experiment. It does not amend the Stage 3 verdict, the Stage 4 verdict, `data/backtest/PREREGISTERED.md`,
or `data/backtest/STAGE4_PREREGISTERED.md`.

Stage 4 remains a failed reproducibility-gate experiment: the `codex_responses` ChatGPT OAuth route
showed uncontrolled bare sampling, and the baseline replay direction agreement did not reach the
locked `95%` acceptance threshold. Stage 5 preserves that conclusion and starts a new protocol.

## Scope

Stage 5 tests the net incremental effect of the cognitive-compounding mechanism under a shared
provider, shared prompt skeleton, and preregistered multi-sample median denoising layer. It does not
claim general market forecasting skill, and it does not interpret absolute MSE as reliable because
current frontier models may contain unavoidable pretraining leakage about historical market regimes.

The scientific claim, if supported, is limited to whether the stateful cognitive-compounding arm
improves paired walk-forward MSE relative to the stateless baseline arm under this protocol after
the A-class replay reproducibility gate is empirically met.

## Universe

The universe is unchanged from Stage 4.

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

Listing gate semantics remain unchanged from the original backtest preregistration and Stage 4: any
symbol listed after a decision month is marked `N/A` for that step and excluded from MSE.

## Interval And Cadence

- Interval: `2016-01-01` through `2026-01-31`.
- The first 12 months are initialization only.
- Cadence: full monthly walk-forward with 30-day scoring windows.

## Provider

- Provider: `codex_responses`, the ChatGPT OAuth direct Responses API route used by Codex.
- Transport: streaming SSE over the Codex OAuth backend.
- Determinism controls: this backend does not accept explicit `temperature`, `top_p`, or `seed`.
- Reproducibility criterion: empirically measured baseline replay direction agreement must be at
  least `95%`. The criterion is direction-level agreement after the preregistered denoising layer,
  not byte-level equality.

## Stage 5 Denoising Method

The only new Stage 5 method change is a preregistered multi-sample median denoising layer for
`codex_responses`.

- For every decision point, the provider sends the same prompt through `N` independent
  `codex_responses` samples.
- The preregistered starting value is `N=5`.
- Each sample uses the same no-temperature wire payload as Stage 4. No unsupported decode controls
  are added.
- Each single-sample failure is retried once. If it still fails, the decision point follows the
  existing provider-error semantics.
- The final `expected_change_pct` is the median of the `N` parsed sample values.
- The final direction is derived from the sign and magnitude of the median using the same decision
  direction semantics as the existing BT runner.
- `vote_consistency` is recorded as the fraction of samples in the modal direction.
- The baseline and Alaya arms both use the same denoising layer and the same `N`. The only
  experimental variable remains whether cognitive-compounding state is present.
- Only the Alaya arm may receive `vote_consistency` as confidence context for future matured
  cognitive-compounding feedback. The baseline prompt must remain free of that confidence context.

## Preregistered N Ladder

The fixed replay ladder is `5 -> 7 -> 9`.

`N` may be increased only when the baseline replay reproducibility gate has been measured and fails
to reach `95%`. The increase serves only the A-class reproducibility gate. `N` must not be adjusted
after observing H1, H2, H3, style-window results, convergence curves, MSE values, or any scientific
effect-size result.

If `N=9` still fails to reach the `95%` replay direction-agreement threshold, Stage 5 fails the
A-class reproducibility gate.

## Arms

- `baseline`: stateless single-step decision. It receives the same price slice and prompt skeleton
  as the Alaya arm, but no cognitive-compounding state and no denoising confidence context.
- `alaya`: stateful cognitive-compounding decision. It receives only matured prior outcomes for the
  same symbol where `outcome_availability_date <= decision_date`, represented as knowledge cards,
  confidence-adaptation context, and Stage 5 denoising confidence context when available.

Both arms must use the same provider, the same prompt skeleton, the same denoising `N`, and the same
median aggregation rule. The only experimental variable is whether cognitive-compounding state is
present.

## Style Windows

The style windows are unchanged from Stage 4.

| Window | Start | End |
|---|---:|---:|
| US-China trade war | 2018-03-01 | 2019-12-31 |
| COVID shock | 2020-01-01 | 2020-04-30 |
| HK platform regulation | 2021-07-01 | 2021-12-31 |
| Global rate hikes | 2022-01-01 | 2022-12-31 |
| Generative AI regime | 2023-01-01 | 2024-12-31 |

## Metrics

- Per-step error: `actual_change_pct - expected_change_pct`.
- Per-step MSE: squared error.
- Primary differential metric: `MSE_baseline - MSE_alaya`.
- H3 significance test: paired loss-differential test using HAC/Newey-West robust standard errors.

## Hypotheses

The Stage 4 hypothesis thresholds are unchanged.

- H1 convergence: `MSE_alaya` over the final third of valid scored steps is at least `15%` lower
  than `MSE_alaya` over the first third.
- H2 drift resistance: in every style window above, `MSE_alaya < MSE_baseline` over valid paired
  steps in that window.
- H3 incremental significance: mean `MSE_baseline - MSE_alaya > 0` with HAC/Newey-West robust
  p-value `< 0.05`.

These thresholds, windows, universe, and the `95%` replay gate are locked before observing Stage 5
scientific outputs and must not be adjusted after seeing H1/H2/H3 results.

## A-Class Correctness Gates

All A-class gates must pass for the experiment to be valid:

- Zero future-function audit violations.
- No run crash.
- Baseline replay direction agreement at or above `95%` after the preregistered denoising layer.
- Pure-function unit tests pass.
- Full audit trail is retained.

A-class gates are validity gates. The H1/H2/H3 outcomes are the scientific conclusion gates. If the
A-class gates pass but hypotheses fail, the correct conclusion is a valid negative or mixed Stage 5
result, not a threshold change.

## Inference Limits

The ready-made model may have learned historical information during pretraining. Absolute MSE is not
credible evidence of real market forecasting skill. This preregistered experiment only evaluates the
net incremental effect of the cognitive-compounding mechanism under the shared-input/shared-provider
setup. Preregistration and this time lock are used to prevent p-hacking; Stage 5 is a new phase, not
a retroactive change to Stage 4.
