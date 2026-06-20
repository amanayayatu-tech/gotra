# GOTRA Baseline v3.2 Formal-Lite Provider Result

Date: 2026-06-20T06:17:57Z

## Scope

- Project: GOTRA Baseline v3.2 Provider Ramp + Formal-Lite Run
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/baseline-v3-2-formal-lite-run-20260620`
- Run-plan commit: `4a4653c` (`Preregister Baseline v3.2 formal-lite run plan`)
- Evidence layer: local checks -> mock recheck -> provider canary -> tiny provider smoke -> formal-lite internal research attempt.
- Non-claims: this is not OOS, not forward-live, not science/public proof, and not trading/investment advice.
- Artifact boundary: run directories and provider artifacts remain local under `data/backtest/runs/*`; no raw provider output, `.env*`, DB/bundle/tar/zip, paper trading, Stage8/Stage9 artifacts, or secrets are included in this commit.

## Frozen Config

- Provider/model/base URL: `kimi` / `Kimi-K2.6` / `https://api.sophnet.com/v1/chat/completions`
- Provider max tokens: `2000`
- Arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
- Input layers: `price_only_packet`, `richer_research_packet`
- Research fixture: `tests/fixtures/baseline_v3_1_research_artifacts.json`
- Feedback fixture: `tests/fixtures/baseline_v3_2_feedback_artifacts.json`
- Full grid: 30 tickers x 12 dates x 4 arms x 2 input layers = 2880 expected provider steps
- Warm-up dates: 3
- Timeout/retry: `--max-request-timeout-seconds 900`, `--timeout-retries 1`, `--timeout-retry-backoff-seconds 30`

## Validation Before Provider

- `uv run python -m py_compile scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py` -> PASS
- `uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py` -> PASS
- `uv run pytest -q tests/test_baseline_v3_four_arm.py` -> PASS (`39 passed`)
- `git diff --check` -> PASS

## Run Ladder

| Gate | Run id | Status | Key diagnostics |
| --- | --- | --- | --- |
| mock recheck | `baseline_v3_2_formal_lite_mock_20260620T025321Z` | `MOCK_PASS` | 2880/2880, paired_coverage=1.0, provider HTTP not used, future-data/research leak/feedback leak all 0, true_independent_feedback_eligible_points=540 |
| Kimi canary | `baseline_v3_2_formal_lite_canary_kimi26_20260620T025501Z` | `PROVIDER_CANARY_PASS` | 96/96, paired_coverage=1.0, provider/schema/input_echo/429/timeout/future-data/raw terminal errors all 0, true_independent_feedback_eligible_points=12 |
| tiny smoke | `baseline_v3_2_formal_lite_tiny_smoke_kimi26_20260620T031320Z` | `PROVIDER_PILOT_PASS` | 144/144, paired_coverage=1.0, provider/schema/input_echo/429/timeout/future-data/raw terminal errors all 0, true_independent_feedback_eligible_points=18 |
| formal-lite | `baseline_v3_2_formal_lite_kimi26_min30x12_20260620T033017Z` | `PROVIDER_PILOT_FAIL` | 2880/2880 step files, paired_coverage=1.0, but 1 unrecovered provider HTTP 400 error |

## Formal-Lite Terminal State

Completion classification: `PROVIDER_BLOCKED_BY_HTTP_400`.

The formal-lite run reached a terminal provider failure, so it is not classified as `FORMAL_LITE_PASS`. Scored paired diagnostics were computed and are recorded below as failed-run diagnostics only.

Root failure:

- `provider_http_error/direct_llm/richer_research_packet/AMD/2024-02-01`
- Segment: warm-up
- Provider error summary: SophNet Kimi returned HTTP 400, `invalid temperature: only 1 is allowed for this model`.

Provider/runtime diagnostics:

| Field | Value |
| --- | ---: |
| expected_steps | 2880 |
| actual_step_files | 2880 |
| paired_coverage | 1.0 |
| provider_error_count | 1 |
| provider_error_rate | 0.0003472222 |
| provider_http_error_count | 1 |
| unrecovered_provider_http_error_count | 1 |
| timeout_count | 0 |
| unrecovered_provider_timeout_count | 0 |
| schema_contract_error_count | 0 |
| input_echo_error_count | 0 |
| http_429_count | 0 |
| future_data_violation_count | 0 |
| research_source_leak_count | 0 |
| feedback_source_leak_count | 0 |
| raw_content_saved_count | 0 |
| max_provider_concurrency_used | 4 |

## Research Verdict

Because the run-level status is `PROVIDER_PILOT_FAIL`, H1/H2/H3 are not promoted to accepted formal-lite verdicts.

- H1: no accepted verdict. Failed-run diagnostics used committed local fixture research evidence (`h1_research_evidence_status=RESEARCH_EVIDENCE_PRESENT_LOCAL_MOCK`); this is not production-grade multi-source research ingestion.
- H2: no accepted verdict. The strict true-independent feedback path was exercised (`true_independent_feedback_eligible_points=540`), but the failed provider terminal state prevents formal-lite acceptance.
- H3: no accepted verdict. Product metrics are recorded as failed-run diagnostics only and do not support OOS/science/trading claims.

## Prediction Diagnostics

These values are internal failed-run diagnostics. Lower MSE is better, but no arm superiority claim is made from this failed run.

| Arm | Scored steps | Direction hit rate | MSE | MAE | Policy A cumulative return pct | Brier direction | Abstain rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 540 | 0.211111 | 157.714897 | 7.790485 | 6.183643 | 0.234489 | 0.0 |
| ksana_formatting_only | 540 | 0.150000 | 160.648945 | 7.834473 | 2.330242 | 0.215640 | 0.0 |
| ksana_real_research | 540 | 0.148148 | 159.223474 | 7.765639 | 4.165336 | 0.223514 | 0.003704 |
| full_gotra | 540 | 0.198148 | 159.604679 | 7.824875 | 5.909296 | 0.219383 | 0.0 |

## C1-C5 Diagnostics

Loss convention: `left_mse_minus_right_mse`. Positive means right arm has lower MSE for that comparison. These are failed-run diagnostics only.

| Comparison | Paired points | Mean loss diff | Bootstrap p | Bootstrap CI | Bootstrap passed | HAC status |
| --- | ---: | ---: | ---: | --- | --- | --- |
| C1 direct minus formatting | 540 | -2.934048 | 0.0566 | [-5.816428, 0.059484] | false | computed within clusters; aggregate status `cluster_level_results_only` |
| C2 formatting minus real research | 540 | 1.425471 | 0.2730 | [-1.143952, 4.003890] | false | computed within clusters; aggregate status `cluster_level_results_only` |
| C3 direct minus real research | 540 | -1.508576 | 0.2760 | [-4.629046, 1.037565] | false | computed within clusters; aggregate status `cluster_level_results_only` |
| C4 real research minus full gotra | 540 | -0.381206 | 0.8010 | [-3.875950, 3.960565] | false | computed within clusters; aggregate status `cluster_level_results_only` |
| C5 direct minus full gotra | 540 | -1.889782 | 0.4208 | [-6.617021, 3.201464] | false | computed within clusters; aggregate status `cluster_level_results_only` |

## Product Metrics Diagnostics

Product metrics are separate from prediction metrics and do not imply trading value.

| Arm | evidence_coverage | invalid_ref_count | valid_ref_count | ledger_completeness | error_attribution_quality | risk_disclosure_quality |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_llm | 0.919259 | 1.694444 | 1.379630 | 1.0 | 0.0 | 1.0 |
| ksana_formatting_only | 0.985185 | 3.853704 | 0.985185 | 1.0 | 0.0 | 1.0 |
| ksana_real_research | 0.874074 | 2.327778 | 1.346296 | 1.0 | 0.0 | 1.0 |
| full_gotra | 0.089323 | 3.046296 | 0.962963 | 1.0 | 0.998148 | 1.0 |

## Evidence And Feedback Diagnostics

- `source_kind_counts`: `real=36`, `unverified=1115`, `synthetic=36`, `price_derived=0`, `unknown=0`; research evidence remains local fixture-backed and not production-grade multi-source ingestion.
- `synthetic_evidence_count`: 36
- `rejected_research_future_data_count`: 18
- `research_source_leak_count`: 0
- `feedback_source_kind_counts`: `outcome_feedback=1440`, `realized_error_feedback=540`, `self_feedback=3780`, `synthetic_feedback=0`, `unknown=0`
- `strict_feedback_eligible_points`: 540
- `true_independent_feedback_eligible_points`: 540
- `self_feedback_available_points`: 540
- `rejected_feedback_schema_count`: 2160
- `rejected_feedback_future_data_count`: 1020
- `rejected_feedback_non_independent_count`: 600
- `rejected_feedback_current_run_count`: 0
- `rejected_feedback_duplicate_count`: 0
- `feedback_source_leak_count`: 0

Prompt separation was checked in canary/tiny smoke gates: non-full arms had no `alaya_feedback` decision inputs, and full_gotra strict eligible points had `alaya_feedback` inputs. The failed full formal-lite run still reports `feedback_source_leak_count=0`.

## Remaining Blocker

The next blocker is provider request compatibility for SophNet Kimi temperature handling:

- One warm-up step failed with HTTP 400: `invalid temperature: only 1 is allowed for this model`.
- This should be treated as provider contract/runtime hardening before any next formal-lite attempt.
- Do not rerun the full formal-lite grid until the Kimi temperature contract is fixed and covered by local tests/canary/smoke.

## Next Action

Open the stacked PR with this frozen failed-run evidence. The next worker goal should fix the provider temperature contract in the harness, verify locally, then repeat the ladder from canary/tiny smoke before any new formal-lite attempt.
