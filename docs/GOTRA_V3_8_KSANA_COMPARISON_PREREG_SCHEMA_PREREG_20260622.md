# GOTRA v3.8 Ksana Comparison Prereg Schema Prereg

Date: 2026-06-22

## Evidence Layer

`engineering_internal_v3_8_ksana_comparison_prereg_schema`

This stage defines a deterministic local prereg/schema validator for a future
`ksana_real_research` versus `full_gotra` comparison. It is fixture-only.
It does not call providers, Codex CLI backends, formal-lite, or any LLM.
It does not execute an actual 30D v3.7 or v3.8 verdict.

The current 30D actual readiness remains `DATA_NOT_MATURED`.
The next 30D check remains `2026-07-21T00:00:00Z`.
`v3_7_actual_verdict_executable=false`.

## Scope

The validator checks synthetic/local prereg fixtures for:

- exact future comparison arms: `ksana_real_research` and `full_gotra`
- optional historical diagnostic metadata arm:
  `direct_llm_parametric_memory_control`
- paired design keys: `ticker`, `decision_date`, and `horizon`
- source run ids, source artifact paths, source summary hashes, artifact hashes,
  generated timestamps, and provenance consistency
- explicit false runtime flags
- explicit 30D data-maturity gate boundary fields
- forbidden/raw artifact path references
- claim-boundary text in prereg narrative/status fields
- final `summary.json` digest recorded in `manifest.json`

`V3_8_KSANA_COMPARISON_PREREG_SCHEMA_READY` only means the local
prereg/schema validator is usable for future engineering prep. It does not mean
the comparison has run, that 30D data is mature, or that any winner/verdict
exists.

## Required Prereg Fields

Minimum fields:

- `comparison_id`
- `prereg_id`
- `schema_version`
- `arms`
- `paired_design`
- `provenance`
- `actual_30d_readiness_status`
- `actual_30d_next_check_after`
- `provider_or_backend_called`
- `codex_cli_called`
- `codex_cli_new_call`
- `formal_lite_entered`
- `v3_7_actual_verdict_executable`
- `v3_7_actual_verdict_executed`
- `direct_llm_interpretation`
- `evidence_layer`
- `non_claims`

Each primary arm must include:

- `arm_id`
- `source_run_id`
- `source_artifact_path`
- `source_summary_sha256`
- `source_artifact_sha256`
- `generated_at`

Each primary arm must also have a matching nested entry under
`provenance.arms`. Duplicate comparison arms are invalid.

## Direct LLM Boundary

The only allowed direct LLM label is
`direct_llm_parametric_memory_control`. It may be recorded only as historical
diagnostic metadata. It is not a clean baseline, not a no-future baseline, and
not a primary comparator for this future comparison design.

Primary comparison arms may use ordinary role labels such as `baseline` or
`treatment`; those role restrictions apply only to direct-LLM metadata entries.

## Allowed Statuses

- `V3_8_KSANA_COMPARISON_PREREG_SCHEMA_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_OVERCLAIM`
- `BLOCKED_RUNTIME_BOUNDARY`
- `DATA_NOT_MATURED`
- `DATA_INSUFFICIENT`

Only `V3_8_KSANA_COMPARISON_PREREG_SCHEMA_READY` exits zero. Blocked statuses
exit nonzero.

## Non-Claims

No provider/backend run is performed. This is not an actual 30D verdict and not
an actual v3.8 comparison result. It makes no OOS, science, public, or trading
assertion. It is not investment advice. It is not a winner report.
