# Phase BT Preregistration

Preregistered at: `2026-06-14T11:59:51+0800`

This protocol is locked before any Phase BT walk-forward run writes price caches or result
artifacts. It defines the universe, scoring interval, style windows, metrics, hypotheses, and
reporting limits for the Gotra 10 x 10-year walk-forward backtest.

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

Any symbol listed after a decision month is marked `N/A` for that step and excluded from MSE.
The test interval is 2016-01-01 through 2026-01-31. The first 12 months are initialization only.
The full protocol scores monthly 30-day windows; the first Phase BT executable validation must use
quarterly sampled steps before any monthly full run.

## Inputs

- Price data: Yahoo Finance daily adjusted close cached once to `data/backtest/prices/`, then read
  locally. Decision inputs can only include rows with `date <= decision_date`.
- Fundamentals: disabled for Phase BT unless each field carries an `availability_date` that is
  independently audited as `availability_date <= decision_date`.
- Network research: disabled for Phase BT. `PERPLEXITY_API_KEY` must be empty in the backtest run.
- LLM leakage: current frontier models may already know historical outcomes. Absolute MSE is not
  interpreted as real forecasting skill.

## Arms

- `baseline`: stateless single-step decision. It receives the same price slice and prompt skeleton
  as the Alaya arm, but no historical feedback.
- `alaya`: stateful cognitive-compounding decision. It may use only matured prior outcomes for the
  same symbol where `outcome_availability_date <= decision_date`.

Both arms must share the same provider/model settings in a full scientific run. Sampling and
dry-run validation may use a deterministic local provider only to validate plumbing, audit, cache,
budget, and report paths; those runs cannot prove the scientific hypotheses.

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
- Primary metric: mean MSE by arm over valid scored steps.
- Differential metric: `MSE_baseline - MSE_alaya`.
- H3 significance test: paired Diebold-Mariano style loss-differential test using HAC/Newey-West
  standard errors. A naive paired t-test is not acceptable.

## Hypotheses

- H1 convergence: `MSE_alaya` over the final third of valid scored steps is at least 15% lower than
  `MSE_alaya` over the first third.
- H2 drift resistance: in every style window above, `MSE_alaya < MSE_baseline` over valid paired
  steps in that window.
- H3 differential significance: mean `MSE_baseline - MSE_alaya > 0` with HAC robust p-value `< 0.05`.

Negative results must be reported as negative results. Thresholds and windows must not be adjusted
after seeing outputs.

## Selection Bias And Inference Limits

The stock universe is a hand-selected set of well-known surviving companies. Results are not a
general return-prediction claim. Even differential MSE can still contain model-pretraining leakage
interactions with stateful feedback. The valid claim, if supported, is limited to the observed net
incremental effect of the cognitive-compounding mechanism under the shared-input/shared-provider
setup.
