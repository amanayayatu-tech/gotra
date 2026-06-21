# GOTRA v3.6AI Ksana Cognitive-Lift Audit Prereg

Date: 2026-06-21

## Evidence Layer

This stage is `engineering/local cognitive-lift audit only`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary: not OOS/science/public/trading claim and not investment advice.
It does not execute a 30D forward-live verdict and keeps `v3_7_allowed=false`.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Source Chain Audit

Current GOTRA ksana/research input plumbing is:

1. Source artifact / fixture:
   public ksana or research packet JSON, such as
   `tests/fixtures/baseline_v3_1_research_artifacts.json`.
2. Public adapter:
   `gotra/ksana_public_adapter.py::adapt_ksana_public_research_artifacts`.
3. Harness adapter entry:
   `scripts/baseline_v3_four_arm.py::filter_external_research_artifacts`.
4. Prompt payload:
   `scripts/baseline_v3_four_arm.py::research_artifact_filter_result` feeds
   `build_prompt_payload`.
5. Provider prompt serialization:
   `scripts/baseline_v3_four_arm.py::render_provider_prompt`.

The current harness consumes normalized research artifact fields such as
`summary`, `text`, `citations`, `evidence`, `claims`, `features`,
`availability_date`, `source_kind`, `source_run_id`, `source_artifact_path`, and
`provenance_hash`. It does not yet have a first-class cognitive-lift contract for
ranked hypotheses, counterfactuals, falsification triggers, disagreement with a
price-only baseline, evidence gaps, or uncertainty decomposition.

## Audit Goal

The goal is to diagnose whether ksana/research packets are too generic or
over-cautious to provide downstream information gain, and to define a local,
deterministic contract for front-half research packet quality before any future
fixture-level comparison.

This audit is allowed to read committed fixtures, docs, and explicit local
artifact paths supplied by the caller. It must not read raw transcripts or
provider raw outputs, and it must not call any backend.

## Cognitive-Lift Contract

A v3.6AI research packet must include:

- `source_run_id`
- `source_artifact_path`
- `ticker`
- `decision_date`
- `research_mode`
- `hypotheses`
- `rank`
- `confidence`
- `why_it_matters`
- `falsification_triggers`
- `expected_observable_evidence`
- `counterfactuals`
- `disagreement_with_price_only`
- `evidence_gaps`
- `uncertainty_decomposition`
- `non_claims`
- `evidence_layer`
- `provider_or_backend_called`
- `codex_cli_new_call`
- `formal_lite_entered`
- `provenance`

The contract is intentionally stricter than the current public adapter. Legacy
adapter fixtures without these fields are not automatically treated as clean
cognitive-lift packets.

Review-hardening contract details:

- `--manifest` must be a JSON object; if present, `artifacts` must be a list.
- Top-level and `provenance.source_artifact_path` values are checked against
  forbidden artifact paths before a packet can be considered provenance-clean.
- Every `hypotheses` entry must be an object; malformed entries are
  `BLOCKED_SCHEMA`, not silently ignored.
- Hypothesis `rank` and `confidence` must be numeric, `confidence` must be in
  `[0, 1]`, and nested `falsification_triggers`,
  `expected_observable_evidence`, and optional hypothesis-level
  `counterfactuals` must be lists.
- `disagreement_with_price_only` must be structured as a list or object; scalar
  text is `BLOCKED_SCHEMA`.
- Boundary claim scanning is field-scoped. `non_claims` documents the boundary
  but cannot negate an overclaim in `summary`, `hypotheses`, `claims`, or other
  claim-bearing fields.
- The verifiable digest for the final `summary.json` is recorded in
  `manifest.json` as `summary_sha256`.

## Metrics

The analyzer must output at least:

- `input_artifact_count`
- `source_artifact_path_count`
- `gotra_used_field_count`
- `gotra_ignored_field_count`
- `hypothesis_count`
- `ranked_hypothesis_count`
- `counterfactual_count`
- `falsifiable_trigger_count`
- `explicit_disagreement_count`
- `evidence_gap_count`
- `uncertainty_decomposition_count`
- `price_only_disagreement_signal`
- `generic_caution_phrase_count`
- `provenance_link_count`
- `future_data_metadata_count`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`

## Statuses

Allowed statuses:

- `COGNITIVE_LIFT_READY_FOR_FIXTURE_COMPARISON`
- `LOW_INFORMATION_GAIN`
- `DATA_INSUFFICIENT`
- `BLOCKED_PROVENANCE`
- `BLOCKED_SCHEMA`
- `BLOCKED_OVERCLAIM`

`COGNITIVE_LIFT_READY_FOR_FIXTURE_COMPARISON` only means a local fixture has
enough structured front-half research fields for a later fixture-level
comparison. It is not a GOTRA/ksana/alaya winner conclusion.

## Blockers

The analyzer must block:

- missing or inconsistent provenance
- forbidden inline or provenance source artifact paths
- missing or invalid required schema fields
- malformed manifest shape
- boundary-overclaim wording caught by the v3.6AB scanner
- `direct_llm_parametric_memory_control` clean-baseline misuse
- any provider/backend/formal-lite boundary violation
- any attempt to treat this audit as 30D forward-live verdict readiness

## Next Action

If this PR is accepted, the next safe action is still engineering-only: use the
contract to build fixture-level research packet comparisons or improve upstream
research packet structure. v3.7 remains blocked until true 30D actual readiness
returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
