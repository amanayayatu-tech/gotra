# GOTRA v3.4 Codex CLI Backend Formal-Lite Result

Date: 2026-06-20

## Scope

Project: GOTRA v3.4 `codex_cli_llm_backend` formal-lite planning and execution gate.

Repo/root: `/Users/peachy/Documents/gotra`

Branch: `codex/gotra-v3-4-codex-cli-formal-lite-20260620`

Prereg anchor: `docs/GOTRA_V3_4_CODEX_CLI_FORMAL_LITE_PREREG_20260620.md`

Evidence layer reached: local checks, mock/no-LLM gate, Codex CLI backend canary,
tiny smoke, and preregistered formal-lite-min internal run.

Non-claims:
- Not OOS.
- Not forward-live.
- Not science/public proof.
- Not trading or investment advice.
- Not equivalent to Kimi/GLM/DeepSeek provider API runs.

The old provider API formal-lite/parser line remains frozen as historical
provider-runtime evidence. v3.4 is a new experiment family.

## Backend Metadata

Backend name: `codex_cli_llm_backend`

Backend version captured in run summaries: `codex-cli 0.139.0`

Model: `gpt-5.5`

Reasoning setting: `low`

Required metadata status:
- `run_id`: recorded for all gates.
- `prompt_hash`: recorded per step artifact.
- `output_transcript_path`: recorded for backend-scored steps as local run
  artifact paths.
- `parsed_decision_hash`: recorded for backend-scored steps.
- Raw transcripts and run directories are local artifacts only and are not
  committed.

## Frozen Grid

Formal-lite-min grid:
- tickers: `AAPL,MSFT,NVDA`
- dates: `2024-01-02,2024-02-01,2024-03-01,2024-04-02`
- warm_up_dates: `1`
- arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- input layers: `price_only_packet`, `richer_research_packet`
- expected backend steps: `96`
- expected scored paired groups: `18`

Fixtures:
- research: `tests/fixtures/baseline_v3_1_research_artifacts.json`
- feedback: `tests/fixtures/baseline_v3_2_feedback_artifacts.json`

## Run Summary

| Gate | Run id | Status | Steps | Coverage | Backend metadata |
| --- | --- | --- | ---: | ---: | --- |
| Mock | `baseline_v3_4_codex_cli_mock_20260620T103620Z` | `MOCK_PASS` | 96/96 | 1.0 | no transcript expected |
| Canary | `baseline_v3_4_codex_cli_canary_20260620T103649Z` | `PROVIDER_CANARY_PASS` | 16/16 | 1.0 | transcript/hash 16/16 |
| Tiny smoke | `baseline_v3_4_codex_cli_tiny_smoke_20260620T104054Z` | `PROVIDER_PILOT_PASS` | 48/48 | 1.0 | transcript/hash 48/48 |
| Formal-lite-min | `baseline_v3_4_codex_cli_formal_lite_min_20260620T105212Z` | `PROVIDER_PILOT_PASS` | 96/96 | 1.0 | transcript/hash 96/96 |

Formal-lite-min runtime diagnostics:
- provider/backend errors: `0`
- schema errors: `0`
- input echo errors: `0`
- HTTP 429 errors: `0`
- timeouts: `0`
- future-data violations: `0`
- research source leaks: `0`
- feedback source leaks: `0`
- raw content saved count: `0`
- `codex_cli_backend_blocked_count`: `0`

Run-level completion classification:
`FORMAL_LITE_MIN_INTERNAL_PASS`.

This classification means the preregistered v3.4 min-grid internal run completed
with required backend metadata and clean runtime gates. It does not imply OOS,
forward-live, scientific, public, or trading validity.

## Arm Interpretation Boundary

`direct_llm` must be interpreted as
`direct_llm_parametric_memory_control`. It is not a clean historical no-future
baseline because modern LLM parameter memory cannot be cut off at historical
`decision_date`.

Metrics involving `direct_llm`, including C1/C3/C5, MSE, direction hit rate, and
returns, are diagnostics only and must not be used to prove GOTRA, ksana, or
alaya success or failure.

The clean historical reference path is `deterministic_price_only_baseline` or a
future-only/forward-live design. In this PR, the deterministic price-only helper
is implemented and tested for no future-price use, but it was not added as a
fifth scored formal-lite arm in the 96-step four-arm run.

## Research and Feedback Diagnostics

Formal-lite-min source kind counts:
- `real`: 12
- `unverified`: 48
- `synthetic`: 12
- `price_derived`: 0
- `unknown`: 0

Feedback diagnostics:
- `self_feedback_available_points`: 18
- `strict_feedback_eligible_points`: 6
- `true_independent_feedback_eligible_points`: 6
- `h2_data_status`: `STRICT_FEEDBACK_ELIGIBLE_PRESENT`
- `C4_feedback_eligible_paired_points`: 6
- `rejected_feedback_artifact_count`: 168
- `rejected_feedback_schema_count`: 72
- `rejected_feedback_future_data_count`: 84
- `rejected_feedback_non_independent_count`: 12
- `rejected_feedback_current_run_count`: 0
- `rejected_feedback_duplicate_count`: 0

Eligibility is present only on later scored points in this small min grid. It is
not a production-scale mature feedback claim.

## C1-C5 Internal Diagnostics

Loss convention: `left_mse_minus_right_mse`. Positive values mean the right arm
has lower MSE for that comparison.

| Comparison | Paired points | Feedback-only | Bootstrap mean | Bootstrap p | Bootstrap passed | HAC status |
| --- | ---: | --- | ---: | ---: | --- | --- |
| C1 direct/control minus formatting | 18 | false | 4.409759 | 0.5116 | false | cluster-level only |
| C2 formatting minus real research | 18 | false | -3.591780 | 0.5116 | false | cluster-level only |
| C3 direct/control minus real research | 18 | false | 0.817978 | 0.0736 | false | cluster-level only |
| C4 real research minus full_gotra | 6 | true | -17.703974 | 0.2916 | false | not enough time points |
| C5 direct/control minus full_gotra | 18 | false | 10.347512 | 0.5852 | false | cluster-level only |

Directional interpretation:
- H1 remains internal/inconclusive in this min grid. The research packet includes
  local fixture real/unverified/synthetic artifacts, not production-grade
  multi-source research ingestion.
- H2 has a non-zero true-independent feedback subset (`6` points), but C4 is not
  statistically accepted in this min grid and HAC is insufficient because each
  cluster has too few time points.
- H3 product metrics are computed separately from prediction metrics. Product
  metrics do not imply OOS, science/public, or trading value.

## Product and Calibration Metrics

Selected formal-lite-min product metrics:

| Arm | scored_steps | evidence_coverage | invalid_ref_count | risk_disclosure_quality |
| --- | ---: | ---: | ---: | ---: |
| `direct_llm` | 18 | 0.988889 | 0.000000 | 1.000000 |
| `ksana_formatting_only` | 18 | 1.000000 | 3.944444 | 1.000000 |
| `ksana_real_research` | 18 | 1.000000 | 0.666667 | 1.000000 |
| `full_gotra` | 18 | 0.408189 | 1.000000 | 1.000000 |

Calibration/abstain metrics were recorded inside per-arm `metrics.calibration`.
All four arms had `abstain_count=0` and `abstain_rate=0.0` in this min run.

## Artifact Boundary

Committed artifacts should include only code, tests, preregistration, and this
result document.

Not committed:
- `data/backtest/runs/*`
- Codex CLI transcripts
- raw provider/API outputs
- `.env*` or secrets
- DB/bundle/tar/zip artifacts
- `data/paper_trading/*`
- Stage8/Stage9 artifacts

## Remaining Blockers

- The v3.4 deterministic price-only baseline exists as a tested helper but is
  not yet integrated as a scored formal-lite arm or formal reference table.
- The formal-lite-min grid is intentionally small. It is useful for a new backend
  family gate, but it is not a production-scale or public/scientific result.
- Codex CLI backend results must remain separate from Kimi/GLM/DeepSeek provider
  API results.

## Next Action

Review PR for v3.4 backend-path implementation. The next engineering step is to
integrate `deterministic_price_only_baseline` into a formal scored reference path
before any larger v3.4 experiment, while preserving the
`direct_llm_parametric_memory_control` interpretation boundary.
