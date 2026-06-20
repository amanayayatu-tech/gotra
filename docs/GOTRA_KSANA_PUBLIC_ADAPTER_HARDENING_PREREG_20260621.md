# GOTRA ksana Public Adapter Hardening Prereg

Date: 2026-06-21

## Scope

This stage hardens the GOTRA/ksana research artifact boundary.

Evidence layer: adapter engineering/local validation only.

This is not a provider run, not a Codex CLI backend run, not formal-lite, not
OOS, not science/public proof, and not trading or investment advice.

No Kimi/GLM/DeepSeek provider APIs, Codex CLI backend, LLM sampling, or
formal-lite experiments may be run for this stage.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. This stage does not use `direct_llm` for any
experiment interpretation.

## Coupling Audit Targets

The read-only coupling audit must identify:

- Baseline v3/v3.4/v3.5 harness paths that build `richer_research_packet`.
- `ksana_real_research` / `full_gotra` prompt input paths that consume research
  artifacts.
- `research_artifacts_path` fixture/file loading paths.
- Any direct imports, path dependencies, or legacy internal ksana coupling.
- Which paths are adapter-backed, legacy/internal, test fixtures, or design-only.

## Adapter Contract

The public adapter/facade must be local, deterministic, and provider-free. It
normalizes research artifacts into the stable GOTRA harness packet shape while
making blocked conditions explicit.

The contract covers:

- Input identity: `ticker`, `decision_date`, `horizon_days`, `input_layer`,
  `source_kind`.
- Availability metadata: `availability_date`, `latest_visible_price_date`,
  `publish_timestamp`, `captured_at`, `decision_date_max`.
- Body fields: `summary`, `text`, `citations`, `evidence`, `claims`,
  `features`.
- Source-kind separation: `real`, `unverified`, `synthetic`,
  `deterministic`, and `reference` must not collapse into one category.
- Provenance: source artifact path/hash, fixture id, source run id when present,
  and stable per-artifact provenance hash.

## Blocked Modes

The adapter must block or structure-diagnose:

- Missing required fields.
- Required field type mismatch.
- Unknown schema/schema drift.
- Future-data metadata leak, including forbidden realized outcome fields,
  `availability_date > decision_date`, `latest_visible_price_date >
  decision_date`, `decision_date_max > decision_date`, or post-decision source
  timestamps.
- Untrusted `source_kind`.
- Artifact identity mismatch, including synthetic, deterministic, or reference
  packets attempting to masquerade as `ksana_real_research`.

Legacy fixture artifacts without an explicit public schema may remain readable
only as `legacy_unverified`; they must not be documented as production-grade
ksana real research.

## Acceptance

Acceptance for this stage is local:

- Focused adapter tests pass without provider, Codex CLI, API keys, or network.
- Existing v3/v3.5 local harness tests for research artifact plumbing still pass.
- Adapter diagnostics are visible in the research filter result.
- Docs record current coupling map, adapter contract, and remaining legacy
  paths.
- No forbidden run artifacts, raw outputs, transcripts, secrets, DBs, archives,
  paper-trading data, Stage8/Stage9 local artifacts, or README changes are
  staged.
