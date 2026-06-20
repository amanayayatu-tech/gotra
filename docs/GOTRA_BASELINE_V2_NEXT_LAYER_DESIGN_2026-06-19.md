# GOTRA Baseline v2 Next-Layer Design (2026-06-19)

## Purpose

This document explains why `ksana_only` and `full_gotra` did not show an advantage over `direct_llm` in the frozen Baseline v2 Kimi-K2.6 provider pilot, and defines the next validation layer.

The goal is not to tune the setup until `full_gotra` wins. The goal is to learn whether gotra's advantage requires richer inputs, real ksana research, matured alaya feedback, and metrics that separate prediction quality from content-product value.

## Frozen Pilot Signal

```text
run_id = baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z
status = PROVIDER_PILOT_PASS
paired_coverage = 1.0
provider/schema/future-data errors = 0
```

Frozen pilot metrics:

| arm | direction_hit_rate | MSE | MAE | Policy A cumulative return pct |
| --- | ---: | ---: | ---: | ---: |
| `direct_llm` | 0.38333333333333336 | 193.284742 | 10.395435 | 17.489133 |
| `ksana_only` | 0.26666666666666666 | 224.882435 | 10.859464 | 7.567385 |
| `full_gotra` | 0.3 | 225.483452 | 11.117102 | 6.577583 |

Direct conclusion:

```text
This pilot does not show ksana_only or full_gotra outperforming direct_llm.
```

## 1. Input May Be Too Weak

The current pilot is mostly a price-derived, limited packet. `direct_llm` may already be strong enough when the task is reduced to a small set of price features and recent adjusted-close history.

The likely advantage of ksana/alaya should come from richer time-bounded evidence:

- news and event context
- fundamentals and earnings context
- narrative shifts
- risk and governance signals
- historical error attribution
- prior ledger continuity

If the input is only a price slice, a complex workflow can add structure but not necessarily signal. It can also add prompt burden, constraints, and noise.

Next-layer implication:

```text
Baseline v3 should use richer packets while preserving strict availability_date <= decision_date.
```

## 2. Ksana Artifacts May Be Too Simulated

The current `ksana_only` arm uses F/W/G/Chairman-style structure, but those artifacts are mainly generated from the same price packet used by `direct_llm`.

That means the pilot may be testing "ksana as formatting workflow" more than "ksana as real research workflow." If ksana does not add independent evidence, it can lose to direct LLM because it adds constraints without adding information.

Next-layer implication:

```text
Baseline v3 should distinguish ksana-as-formatting from ksana-as-real-research.
```

Candidate design:

- `direct_llm`: raw packet only.
- `ksana_formatting_only`: same packet plus internal role structure.
- `ksana_real_research`: same packet plus time-bounded multi-source research artifacts.
- `full_gotra`: real ksana research plus mature alaya feedback.

This split would identify whether the loss comes from the ksana idea or from the current simulated artifact layer.

## 3. Alaya Feedback May Be Immature Or Sparse

The `full_gotra` advantage depends on mature historical feedback, error attribution, knowledge state, and quarantine/conflict filtering.

In the current pilot, matured feedback is likely too sparse, too short-horizon, or too synthetic to show compounding value. Early dates have little or no matured feedback. Later dates have some feedback, but not necessarily enough for stable alaya learning.

Next-layer implication:

```text
Evaluate alaya only when feedback is actually mature and available by decision_date.
```

Candidate design:

- Add a warm-up period that produces feedback but is not part of final scoring.
- Report `full_gotra` separately on all dates and on feedback-eligible dates.
- Require every alaya memory ref to have `availability_date <= decision_date`.
- Track feedback density, feedback age, and quarantine exclusions.
- Avoid claiming alaya lift on dates where alaya has no mature information advantage.

## 4. Metrics May Not Fully Match Content-Product Value

MSE, MAE, direction hit, and Policy A return are useful engineering pilot metrics. They do not fully cover the value described in gotra's product direction:

- public ledger quality
- explainable judgment
- error attribution
- trusted review history
- continuity across decisions
- abstain discipline
- auditability and user readability

These product metrics may be real, but they must not replace price-prediction metrics when making investment-effectiveness claims.

Next-layer implication:

```text
Separate prediction metrics from content-product metrics.
```

Potential product metrics:

- calibration quality
- abstain quality
- risk-aware utility
- explanation auditability
- evidence citation completeness
- ledger completeness
- consistency of postmortem/error attribution
- user readability and reviewability

Boundary:

```text
Product metrics can support content-product claims.
They cannot by themselves support trading, OOS, or science claims.
```

## 5. Recommended Next Layer

Recommended next stage:

```text
Baseline v3 Design / Formal-Lite Prereg
```

Suggested design:

```text
tickers = 30-50
dates = 12-24 monthly dates
provider/model = predeclared
packets = richer, time-bounded, availability-audited
arms = direct_llm, ksana_only, full_gotra
optional diagnostic arm = ksana_formatting_only
feedback = matured alaya feedback only when availability_date <= decision_date
metrics = separate prediction metrics and product-content metrics
comparisons = paired direct_vs_ksana, ksana_vs_full, direct_vs_full
variance = repeat-run/provider variance check if budget allows
claims = predeclared H1/H2/H3 only after gate pass
```

Predeclared questions:

```text
H1: Does real ksana research improve prediction metrics over direct_llm?
H2: Does mature alaya feedback improve prediction metrics over ksana_only on feedback-eligible dates?
H3: Does full_gotra improve product-content metrics without degrading prediction metrics beyond a predeclared tolerance?
```

Acceptance boundary:

- Provider/runtime health is not evidence of arm superiority.
- Pilot pass is not formal-lite pass.
- Product metrics do not prove investment effectiveness.
- OOS/public claims require separate preregistration and acceptance.

## 6. What The Next Layer Should Not Do

The next layer should not:

- drop losing ticker/date rows from the frozen grid after seeing results
- change primary metrics to make `full_gotra` win
- hide the direct LLM baseline
- use future outcomes as input
- evaluate alaya on dates with no mature feedback and call that an alaya failure
- promote product-content metrics into trading claims

## Recommended Decision

Freeze Baseline v2 as a completed provider pilot with negative/neutral arm-lift signal. Move to Baseline v3 only through a preregistered design that tests richer input, real ksana research, mature alaya feedback, and separated product metrics.
