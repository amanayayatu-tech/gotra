# GOTRA v3.4c Codex CLI Scaled Reference Result

Date: 2026-06-20

## Scope

Project: GOTRA v3.4c `codex_cli_llm_backend` scaled internal run with
deterministic price-only reference.

Repo/root: `/Users/peachy/Documents/gotra`

Branch: `codex/gotra-v3-4c-codex-cli-scaled-reference-20260620`

Base PR: PR #21, `codex/gotra-v3-4b-deterministic-reference-20260620`

Prereg anchor:
`docs/GOTRA_V3_4C_CODEX_CLI_SCALED_REFERENCE_PREREG_20260620.md`

Evidence layer reached: local checks, no-LLM scaled mock, Codex CLI backend
canary, and Codex CLI backend scaled internal run.

Non-claims:
- Not OOS.
- Not forward-live.
- Not science/public proof.
- Not trading or investment advice.
- Not equivalent to Kimi/GLM/DeepSeek provider API runs.

The old provider API formal-lite/parser line remains frozen as historical
provider-runtime evidence. This result belongs to the new
`codex_cli_llm_backend` experiment family.

## Frozen Grid

Scaled grid:
- tickers: `AAPL,MSFT,NVDA,TSM,0700.HK,1211.HK,1810.HK,3690.HK,6060.HK,9988.HK`
- decision dates:
  `2024-01-02,2024-02-01,2024-03-01,2024-04-02,2024-05-02,2024-06-03`
- arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- input layers: `price_only_packet`, `richer_research_packet`
- warm_up_dates: `2`
- expected backend steps: `480`
- expected scored paired groups: `80`

Fixtures:
- research: `tests/fixtures/baseline_v3_1_research_artifacts.json`
- feedback: `tests/fixtures/baseline_v3_2_feedback_artifacts.json`

## Backend Metadata

Backend name: `codex_cli_llm_backend`

Codex CLI version: `codex-cli 0.139.0`

Model: `gpt-5.5`

Reasoning setting: `low`

Scaled run metadata:
- backend transcript path count: `480`
- parsed decision hash count: `480`
- raw content saved count: `0`
- normalization applied count: `0`
- normalization failure count: `0`

Transcripts and run artifacts are local-only under `data/backtest/runs/` and
are not committed.

## Run Summary

| Gate | Run id | Status | Steps | Coverage | Transcript/hash |
| --- | --- | --- | ---: | ---: | --- |
| Mock | `baseline_v3_4_scaled_reference_mock_20260620T115341Z` | `MOCK_PASS` | 480/480 | 1.0 | 0/0 expected |
| Canary | `baseline_v3_4_scaled_reference_canary_20260620T115610Z` | `PROVIDER_CANARY_PASS` | 16/16 | 1.0 | 16/16 |
| Scaled internal | `baseline_v3_4_scaled_reference_internal_20260620T120015Z` | `PROVIDER_PILOT_PASS` | 480/480 | 1.0 | 480/480 |

Scaled runtime diagnostics:
- provider/backend errors: `0`
- provider error rate: `0.0`
- schema contract errors: `0`
- JSON decode errors: `0`
- input echo errors: `0`
- HTTP 429 errors: `0`
- timeouts: `0`
- future-data violations: `0`
- research source leaks: `0`
- feedback source leaks: `0`
- Codex CLI backend blocked count: `0`
- max provider/backend concurrency used: `2`

Run-level completion classification:
`SCALED_INTERNAL_PROVIDER_PILOT_PASS`.

This classification means the preregistered v3.4c scaled internal run completed
with required backend metadata and clean runtime gates. It does not imply OOS,
forward-live, scientific, public, or trading validity.

## Deterministic Reference

`deterministic_price_only_baseline` is present as the clean historical reference.

Summary fields:
- `clean_historical_reference_status`:
  `PRESENT_DETERMINISTIC_PRICE_ONLY_BASELINE`
- `deterministic_price_only_baseline_status`: `REFERENCE_READY`
- unique reference count: `40`
- raw input-layer mirrored equivalent count: `80`
- future-data violations: `0`
- provider/backend called by deterministic reference: `false`
- latest visible price date max: `2024-06-03`

Reference metrics:

| Metric | Value |
| --- | ---: |
| scored_steps | 40 |
| MSE | 155.341486 |
| MAE | 10.078715 |
| direction_hit_rate | 0.4 |
| Policy A cumulative return pct | 16.531249 |
| Brier score direction | 0.247695 |
| abstain_rate | 0.0 |

The deterministic reference uses price rows visible at or before each
`decision_date` for decision construction and is scored only after the decision
is constructed.

## Research and Feedback Diagnostics

Research source kind counts:
- `real`: `18`
- `unverified`: `198`
- `synthetic`: `18`
- `price_derived`: `0`
- `unknown`: `0`

Rejected research artifacts:
- total rejected: `18`
- future-data rejected: `18`
- schema rejected: `0`

Feedback diagnostics:
- `self_feedback_available_points`: `80`
- `strict_feedback_eligible_points`: `60`
- `true_independent_feedback_eligible_points`: `60`
- `C4_feedback_eligible_paired_points`: `60`
- `h2_data_status`: `STRICT_FEEDBACK_ELIGIBLE_PRESENT`
- `h2_data_insufficient_reason`: empty

Feedback source kind counts:
- `outcome_feedback`: `140`
- `realized_error_feedback`: `60`
- `self_feedback`: `280`
- `synthetic_feedback`: `0`
- `unknown`: `0`

Rejected feedback artifacts:
- total rejected: `760`
- future-data rejected: `320`
- schema rejected: `360`
- non-independent rejected: `80`
- duplicate rejected: `0`
- current-run rejected: `0`

The H2 denominator is explicit and uses true-independent strict feedback
eligibility. Self-feedback is not merged into the true-independent denominator.

## Arm Interpretation Boundary

`direct_llm` must be interpreted as
`direct_llm_parametric_memory_control`. It is not a clean historical no-future
baseline because modern LLM parameter memory cannot be cut off at historical
`decision_date`.

Metrics involving `direct_llm`, including C1/C3/C5, MSE, direction hit rate, and
returns, are diagnostics only and must not be used to prove GOTRA, ksana, or
alaya success or failure.

The clean historical reference is `deterministic_price_only_baseline`.

## Prediction Metrics

| Arm/reference | scored_steps | MSE | MAE | direction_hit_rate | Policy A cumulative return pct | Brier score direction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic_price_only_baseline | 40 | 155.341486 | 10.078715 | 0.4 | 16.531249 | 0.247695 |
| direct_llm_parametric_memory_control | 80 | 90.432113 | 7.349812 | 0.3 | 11.360155 | 0.225569 |
| ksana_formatting_only | 80 | 91.627707 | 7.488562 | 0.3125 | 11.063523 | 0.226541 |
| ksana_real_research | 80 | 90.519122 | 7.395635 | 0.15 | 7.529066 | 0.205744 |
| full_gotra | 80 | 95.681577 | 7.662312 | 0.3125 | 12.577868 | 0.239712 |

These metrics are internal diagnostics on the frozen v3.4c grid. They are not
OOS, forward-live, public-science, or trading evidence.

## C1-C5 Statistical Diagnostics

Loss diff convention: `left_mse_minus_right_mse`.

| Comparison | Paired points | Mean loss diff | Bootstrap p | CI low | CI high | Winner arm | HAC status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| C1 direct_minus_formatting | 80 | -1.195594 | 0.699 | -7.228442 | 4.449218 | direct_llm_parametric_memory_control | cluster_level_results_only |
| C2 formatting_minus_real_research | 80 | 1.108586 | 0.6584 | -2.916259 | 6.017364 | ksana_real_research | cluster_level_results_only |
| C3 direct_minus_real_research | 80 | -0.087008 | 0.9724 | -4.468869 | 4.372814 | direct_llm_parametric_memory_control | cluster_level_results_only |
| C4 real_research_minus_full_gotra | 60 | -0.330484 | 0.8592 | -4.451779 | 3.808594 | ksana_real_research | cluster_level_results_only |
| C5 direct_minus_full_gotra | 80 | -5.249463 | 0.0058 | -9.918314 | -1.272708 | direct_llm_parametric_memory_control | cluster_level_results_only |

C1/C3/C5 include `direct_llm_parametric_memory_control` and are diagnostic only.
C4 is the preferred historical alaya-style comparison because it compares
`ksana_real_research` with `full_gotra` on feedback-eligible points. In this
internal run, C4's bootstrap interval crosses zero and does not support a
directional full_gotra improvement claim. This is not an alaya failure claim and
not a trading claim.

## Product Metrics

| Arm | scored_steps | evidence_coverage | invalid_ref_count avg | duplicate_ref_count avg | risk_disclosure_quality | ledger_completeness |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm_parametric_memory_control | 80 | 0.9975 | 0.0375 | 0.0 | 1.0 | 1.0 |
| ksana_formatting_only | 80 | 1.0 | 3.875 | 0.0 | 1.0 | 1.0 |
| ksana_real_research | 80 | 1.0 | 0.925 | 0.0 | 1.0 | 1.0 |
| full_gotra | 80 | 0.244497 | 0.9875 | 0.0 | 1.0 | 1.0 |

Product metrics are reported separately from prediction metrics. They do not
support OOS, scientific, public, or trading conclusions.

## Verdict Boundary

Completion: `SCALED_INTERNAL_PROVIDER_PILOT_PASS`.

H1: internal/inconclusive. Richer research packets included local fixture-backed
`real`/`unverified` evidence, but this is not a production-grade multi-source
research pipeline and not a public science claim.

H2: internally testable denominator present (`true_independent_feedback_eligible_points=60`).
The C4 diagnostic did not show statistically supported full_gotra improvement on
this scaled internal grid. This is not an alaya failure claim.

H3: product and prediction metrics remain separated. Product metrics do not
support trading/OOS/science claims.

## Artifact Boundary

Committed files should include only this result doc and the v3.4c prereg doc.

Not committed:
- `data/backtest/runs/*`
- Codex CLI transcripts
- raw outputs
- provider raw files
- `.env*`
- DB/bundle/tar/zip
- `data/paper_trading/*`
- Stage8/Stage9 artifacts
- unrelated v2 docs/scripts

## Next Action

Review PR #22 as a v3.4c scaled internal evidence PR. Do not merge automatically.
The next planning decision should decide whether to expand the Codex CLI
experiment family, add a stronger deterministic/future-only clean baseline, or
move to forward-live/future-only validation. Do not revive the old provider API
parser/formal-lite line as the main blocker.
