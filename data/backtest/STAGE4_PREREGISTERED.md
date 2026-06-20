# Stage 4 Preregistration

Generated at: `2026-06-16 01:00:34 CST (+0800)`

This protocol is locked before any Stage 4 engineering change or scientific run output is
observed on the `codex/stage4-experiment` branch. Stage 4 is a new preregistered experiment; it
does not amend the Stage 3 verdict and does not modify `data/backtest/PREREGISTERED.md`.

## Scope

Stage 4 tests the net incremental effect of the cognitive-compounding mechanism under a shared
provider and shared prompt skeleton. It does not claim general market forecasting skill, and it does
not interpret absolute MSE as reliable because current frontier models may contain unavoidable
pretraining leakage about historical market regimes.

The scientific claim, if supported, is limited to whether the stateful cognitive-compounding arm
improves paired walk-forward MSE relative to the stateless baseline arm under this protocol.

## Universe

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

Listing gate semantics remain unchanged from the original backtest preregistration: any symbol
listed after a decision month is marked `N/A` for that step and excluded from MSE.

## Interval And Cadence

- Interval: `2016-01-01` through `2026-01-31`.
- The first 12 months are initialization only.
- Cadence: full monthly walk-forward with 30-day scoring windows.

## Provider

- Provider: `codex_responses`, the ChatGPT OAuth direct Responses API route used by Codex.
- Transport: streaming SSE over the Codex OAuth backend.
- Determinism controls: this backend does not accept explicit `temperature`, `top_p`, or `seed`.
- Reproducibility criterion: empirically measured baseline replay direction agreement must be at
  least `95%`. The criterion is direction-level agreement, not byte-level equality.

## Arms

- `baseline`: stateless single-step decision. It receives the same price slice and prompt skeleton
  as the Alaya arm, but no cognitive-compounding state.
- `alaya`: stateful cognitive-compounding decision. It receives only matured prior outcomes for the
  same symbol where `outcome_availability_date <= decision_date`, represented as knowledge cards
  and confidence-adaptation context.

Both arms must use the same provider and the same prompt skeleton. The only experimental variable is
whether cognitive-compounding state is present.

## Style Windows

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

- H1 convergence: `MSE_alaya` over the final third of valid scored steps is at least `15%` lower
  than `MSE_alaya` over the first third.
- H2 drift resistance: in every style window above, `MSE_alaya < MSE_baseline` over valid paired
  steps in that window.
- H3 incremental significance: mean `MSE_baseline - MSE_alaya > 0` with HAC/Newey-West robust
  p-value `< 0.05`.

These thresholds, windows, universe, and the `95%` replay gate are locked before observing Stage 4
scientific outputs and must not be adjusted after seeing H1/H2/H3 results.

## A-Class Correctness Gates

All A-class gates must pass for the experiment to be valid:

- Zero future-function audit violations.
- No run crash.
- Baseline replay direction agreement at or above `95%`.
- Pure-function unit tests pass.
- Full audit trail is retained.

A-class gates are validity gates. The H1/H2/H3 outcomes are the scientific conclusion gates. If the
A-class gates pass but hypotheses fail, the correct conclusion is a valid negative or mixed Stage 4
result, not a threshold change.

## Inference Limits

The ready-made model may have learned historical information during pretraining. Absolute MSE is not
credible evidence of real market forecasting skill. This preregistered experiment only evaluates the
net incremental effect of the cognitive-compounding mechanism under the shared-input/shared-provider
setup. Preregistration and this time lock are used to prevent p-hacking; Stage 4 is a new phase, not
a retroactive change to Stage 3.
