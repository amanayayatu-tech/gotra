# GOTRA v3.6AJ Cognitive-Lift Fixture Comparison Prereg

Date: 2026-06-21

## Evidence Layer

This stage is `engineering/local cognitive-lift fixture comparison only`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary: not OOS/science/public/trading claim and not investment advice.
This stage does not execute a 30D forward-live verdict and keeps
`v3_7_allowed=false`.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Goal

Use the v3.6AI cognitive-lift contract to compare local fixtures only:

1. a conservative / generic caution-heavy research packet
2. a cognitive-lift contract-compliant packet
3. optional malformed, overclaim, or missing-provenance fixtures

The comparison answers only whether structural information gain is detectable at
fixture level. It does not answer real prediction quality, investment value,
OOS validity, science/public acceptance, or GOTRA/ksana/alaya superiority.

## Implementation Contract

The comparison harness must reuse v3.6AI analyzer and validator behavior. It
must not duplicate schema, provenance, overclaim, or `direct_llm_parametric_memory_control`
boundary logic.

Each side is audited through `scripts/baseline_v3_6ai_ksana_cognitive_lift_audit.py`,
then compared on structural metrics:

- ranked hypotheses
- counterfactuals
- falsification triggers
- evidence gaps
- generic caution phrases
- provenance links
- schema blockers
- overclaim blockers

## Summary Fields

The summary must include at least:

- `comparison_status`
- `baseline_information_gain_status`
- `candidate_information_gain_status`
- `baseline_hypothesis_count`
- `candidate_hypothesis_count`
- `baseline_counterfactual_count`
- `candidate_counterfactual_count`
- `baseline_falsifiable_trigger_count`
- `candidate_falsifiable_trigger_count`
- `baseline_evidence_gap_count`
- `candidate_evidence_gap_count`
- `baseline_generic_caution_phrase_count`
- `candidate_generic_caution_phrase_count`
- `delta_ranked_hypothesis_count`
- `delta_counterfactual_count`
- `delta_falsifiable_trigger_count`
- `delta_generic_caution_phrase_count`
- `provenance_link_count`
- `overclaim_blocker_count`
- `schema_blocker_count`
- `evidence_layer=engineering/local cognitive-lift fixture comparison only`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`

## Statuses

Allowed statuses:

- `COGNITIVE_LIFT_FIXTURE_COMPARISON_READY`
- `COGNITIVE_LIFT_FIXTURE_IMPROVED`
- `LOW_INFORMATION_GAIN_BASELINE`
- `LOW_INFORMATION_GAIN_CANDIDATE`
- `DATA_INSUFFICIENT`
- `BLOCKED_PROVENANCE`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`

`COGNITIVE_LIFT_FIXTURE_IMPROVED` means only that a local candidate fixture has
more structured front-half research fields than a low-information local
baseline fixture. It is not a real outcome score, not a 30D readiness signal,
and not a winner conclusion.

## Next Action

If this PR merges later, the safe follow-up is still engineering design work:
use the fixture comparison to refine research packet structure or request a
separately authorized future canary. Any real canary/provider capture must be
authorized separately and must include full metadata. v3.7 remains blocked until
true 30D actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance.
