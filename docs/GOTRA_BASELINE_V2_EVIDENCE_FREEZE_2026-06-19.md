# Gotra Baseline v2 Three-Arm Pilot Evidence Freeze (2026-06-19)

## Repo And Run Identity

```text
Repo/root = /Users/peachy/Documents/gotra
Branch/HEAD = codex/baseline-v2-three-arm-pilot @ 1fe7e6f
Provider/model = kimi / Kimi-K2.6
Provider base_url = https://api.sophnet.com/v1/chat/completions
Provider max_tokens = 2000
Run root = data/backtest/runs/baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z
Run status = PROVIDER_PILOT_PASS
```

## Changed Files

```text
scripts/baseline_v2_three_arm_pilot.py
tests/test_baseline_v2_three_arm_pilot.py
docs/GOTRA_BASELINE_V2_THREE_ARM_PREREG_2026-06-18.md
docs/GOTRA_BASELINE_V2_KIMI26_INPUT_ECHO_RECOVERY_2026-06-19.md
docs/GOTRA_BASELINE_V2_KIMI26_RESULT_2026-06-19.md
docs/GOTRA_BASELINE_V2_THREE_ARM_PILOT_RESULT_2026-06-19.md
docs/GOTRA_BASELINE_V2_EVIDENCE_FREEZE_2026-06-19.md
docs/GOTRA_BASELINE_V2_NEXT_LAYER_DESIGN_2026-06-19.md
```

## Validation Stack

```text
baseline_v2_pilot_summary_check = PASS
uv run python -m py_compile scripts/baseline_v2_three_arm_pilot.py = PASS
uv run ruff check --no-cache scripts/baseline_v2_three_arm_pilot.py tests/test_baseline_v2_three_arm_pilot.py = PASS
uv run pytest -q tests/test_baseline_v2_three_arm_pilot.py = 41 passed
git diff --check = PASS
```

## Evidence Boundary

```text
local checks: PASS
provider/runtime health: Kimi repair canary + pilot provider path completed without provider/runtime/schema errors
pilot evidence: PROVIDER_PILOT_PASS on the fixed Baseline v2 three-arm pilot grid
long-run/formal acceptance: not entered
science/public claim: not entered
paper trading/trading advice: not entered
```

## Pilot Pass Definition

`PROVIDER_PILOT_PASS` only means the fixed Baseline v2 pilot grid completed on the Kimi-K2.6 provider path with paired coverage `1.0` and no provider/schema/future-data errors.

It does not mean formal-lite pass, OOS pass, Stage9 pass, paper trading readiness, or a science/public claim.

## Direct LLM Interpretation Boundary

Historical `direct_llm` metrics in this document must be read as
`direct_llm_parametric_memory_control`; see
`docs/GOTRA_DIRECT_LLM_INTERPRETATION_BOUNDARY_2026-06-20.md`.

This is not a clean no-future historical baseline. Modern LLM parameter memory
may contain later market narratives even when prompts and artifacts are
time-bounded. The `direct_llm` metrics below are diagnostic only and must not be
used to prove or refute GOTRA, ksana, or alaya success.

## Pilot Metrics

| arm | scored_steps | direction_hit_rate | MSE | MAE | Policy A cumulative return pct |
| --- | ---: | ---: | ---: | ---: | ---: |
| `direct_llm` | 60 | 0.38333333333333336 | 193.284742 | 10.395435 | 17.489133 |
| `ksana_only` | 60 | 0.26666666666666666 | 224.882435 | 10.859464 | 7.567385 |
| `full_gotra` | 60 | 0.3 | 225.483452 | 11.117102 | 6.577583 |

## Paired Diffs

| comparison | paired_points | mse_delta_left_minus_right | policy_a_return_delta_right_minus_left_pct |
| --- | ---: | ---: | ---: |
| `direct_vs_ksana` | 60 | -31.597694 | -1.563016 |
| `ksana_vs_full` | 60 | -0.601017 | -0.156457 |
| `direct_vs_full` | 60 | -32.19871 | -1.719473 |

## Interpretation

In this pilot, `direct_llm_parametric_memory_control` had the best direction hit
rate, MSE, MAE, and Policy A cumulative return. The paired diffs are
directionally unfavorable to `ksana_only` and `full_gotra` under this pilot
metric stack.

This pilot does not support the claim that `ksana_only` or `full_gotra`
outperformed `direct_llm_parametric_memory_control` on the fixed Baseline v2
pilot grid. This diagnostic comparison must not be promoted to an OOS,
science/public, or trading conclusion.

This is not a gotra project failure. It means the current Baseline v2 input packet, ksana artifact construction, alaya feedback maturity, or metric design did not surface an advantage for the more complex arms.

## Negative Or Neutral Signal Statement

The frozen pilot signal is negative/neutral for the hypothesis that ksana/alaya add measurable price-prediction lift over direct LLM under this specific grid and input design.

The result should be treated as a design diagnostic, not as a final verdict on the gotra system.

## What This Does Not Prove

This result does not prove:

- `direct_llm` is generally superior outside this pilot grid.
- ksana research is useless when real multi-source research artifacts are available.
- alaya memory has no value after a larger mature-feedback window.
- gotra lacks content-product value.
- any trading strategy is ready for paper/live deployment.
- any formal, OOS, science, or public claim is justified.

## What Is Frozen

Frozen evidence:

```text
run_id = baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z
status = PROVIDER_PILOT_PASS
expected_steps = 180
actual_step_files = 180
expected_points = 60
paired_complete_points = 60
paired_coverage = 1.0
provider_error_count = 0
input_echo_error_count = 0
json_decode_error_count = 0
schema_contract_error_count = 0
schema_error_count = 0
http_429_count = 0
timeout_count = 0
future_data_violation_count = 0
```

Frozen interpretation:

```text
direct_llm_parametric_memory_control ranked ahead of ksana_only and full_gotra
on this pilot grid.
The result is pilot evidence only.
No formal-lite, OOS, Stage9, paper trading, science, or public claim is made.
```

## What Remains Open

Open questions:

- Whether richer time-bounded inputs change the relative arm ordering.
- Whether real ksana research artifacts add signal beyond direct prompt formatting.
- Whether matured alaya feedback has enough density to help only after a longer warm-up window.
- Whether product-facing metrics such as explanation auditability and ledger completeness should be evaluated separately from price-prediction metrics.
- Whether repeat-run/provider variance materially changes the pilot ordering.

## Recommended Next Layer

Recommended next step:

```text
Baseline v3 Design / Formal-Lite Prereg
```

The next layer should not tune the experiment until `full_gotra` wins. It should test whether gotra's advantage requires richer input packets, real ksana research, mature alaya feedback, and a separate product-metric track.
