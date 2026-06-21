# GOTRA v3.7K Ksana Packet V2 Front-Half Optimization Prereg

Date: 2026-06-21

## Evidence Layer

This stage is
`engineering/local ksana packet v2 front-half optimization fixture-only`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not a provider run.
- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- Not a GOTRA / ksana / alaya superiority conclusion.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Goal

Define and validate a local fixture-only `ksana` research packet v2 contract for
front-half cognitive-lift work. The contract is designed to reduce overly
generic caution and force explicit, ranked, falsifiable research structure
before any separately authorized provider canary.

`KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY` means the synthetic/local packet v2
fixture is schema-clean, provenance-clean, claim-boundary clean, and structurally
richer than a conservative fixture baseline. It does not authorize or execute a
provider canary, and it does not authorize an actual v3.7 30D verdict.

Actual 30D readiness remains `DATA_NOT_MATURED`, so
`v3_7_actual_verdict_executable=false`.

## Packet V2 Contract

Each packet v2 artifact must include:

- `source_run_id`
- `source_artifact_path`
- `ticker`
- `decision_date`
- `research_mode`
- `ranked_hypotheses`
- `why_it_matters`
- `confidence`
- `falsification_triggers`
- `expected_observable_evidence`
- `counterfactuals`
- `disagreement_with_price_only`
- `evidence_gaps`
- `uncertainty_decomposition`
- `non_claims`
- `evidence_layer`
- `provenance`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

Each ranked hypothesis must include:

- `rank`
- `hypothesis`
- `confidence`
- `why_it_matters`
- `falsification_triggers`
- `expected_observable_evidence`

The validator requires structured, non-empty lists for counterfactuals,
falsification triggers, expected observable evidence, evidence gaps, and
`disagreement_with_price_only`. Scalar disagreement wording is blocked because
it is not the packet v2 structure.

## Metrics

The validator reports:

- `hypothesis_count`
- `ranked_hypothesis_count`
- `counterfactual_count`
- `falsifiable_trigger_count`
- `explicit_disagreement_count`
- `evidence_gap_count`
- `uncertainty_decomposition_count`
- `price_only_disagreement_signal`
- `generic_caution_phrase_count`
- `information_gain_delta`

The comparison is deterministic and fixture-only. `information_gain_delta` is a
structural packet metric, not a prediction-quality metric.

## Blockers

Allowed statuses:

- `KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY`
- `LOW_INFORMATION_GAIN`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_OVERCLAIM`
- `DATA_INSUFFICIENT`

The validator blocks:

- missing or malformed packet v2 schema fields
- missing ranked hypotheses
- missing counterfactuals
- missing falsification triggers
- scalar or empty `disagreement_with_price_only`
- missing or inconsistent provenance
- forbidden source artifact paths
- OOS/science/public/trading/investment overclaim wording
- `direct_llm_parametric_memory_control` clean-baseline misuse wording
- non-false runtime flags

`LOW_INFORMATION_GAIN` is non-blocking but not sufficient for a provider canary
proposal. It indicates the packet is still too conservative or too generic.

## Digest Convention

The final `summary.json` digest is recorded in `manifest.json` as
`summary_sha256`; the summary does not store a self-invalidating digest field.

## Next Action

If this stage merges later, the only safe follow-up is a separately authorized,
bounded provider canary using the v2 packet contract. That canary must not use
old Kimi/GLM/DeepSeek provider paths and must include complete metadata. The
actual 30D v3.7 verdict remains blocked until actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
