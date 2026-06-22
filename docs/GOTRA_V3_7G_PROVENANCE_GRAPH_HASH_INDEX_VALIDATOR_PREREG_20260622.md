# GOTRA v3.7G Provenance Graph / Artifact Hash Index Validator Prereg

## Scope

v3.7G adds a deterministic local provenance graph and artifact hash index validator for future v3.7 actual verdict preparation. This is fixture-only engineering prep. It does not run providers, Codex CLI backend, formal-lite, or any new LLM call.

This stage is not an actual 30D forward-live verdict, not an OOS/science/public/trading claim, and not trading or investment advice. It does not emit a deterministic/full_gotra winner.

## Current Maturity Boundary

- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

v3.7 actual verdict execution remains blocked until the real 30D readiness gate returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.

## Validator Contract

Entrypoint:

```bash
uv run python scripts/baseline_v3_7g_provenance_graph_hash_index_validator.py \
  --graph-fixture <fixture.json> \
  --output-dir /tmp/gotra_v3_7g_provenance_graph_hash_index/runs
```

The input fixture must be a local/tracked mock graph/index. It must not reference raw provider output, transcripts, `data/backtest/runs/**`, `data/paper_trading/**`, `.env*`, SQLite/DB files, bundles, archives, or Stage8/Stage9 artifacts.

Graph root fields include:

- `graph_schema_version`
- `generated_at`
- `actual_30d_readiness_status`
- `actual_30d_next_check_after`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `evidence_layer=engineering_internal_provenance_graph_hash_index`
- `nodes`
- `edges`
- optional `required_source_node_ids`

Each node must include:

- `node_id`
- `source_path`
- `source_sha256` or `summary_sha256`
- `run_id`
- `generated_at`
- `evidence_layer`
- `artifact_kind`
- nested `provenance.source_run_id`
- nested `provenance.source_artifact_path`
- nested `provenance.source_sha256` or `provenance.summary_sha256`
- runtime flags set to false

Each edge must include:

- `source_node_id`
- `target_node_id`
- `relationship`
- `evidence_layer`

## Blocking Rules

Allowed terminal statuses:

- `V3_7_PROVENANCE_GRAPH_HASH_INDEX_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_HASH_MISMATCH`
- `BLOCKED_CYCLE`
- `BLOCKED_OVERCLAIM`
- `DATA_INSUFFICIENT`

The validator blocks on:

- missing or malformed schema fields
- missing artifact hash
- hash mismatch against readable local fixture bytes
- forbidden or raw source paths
- missing nested provenance
- invalid `generated_at`
- duplicate `node_id`
- edge references to missing nodes
- graph cycles
- required source nodes that cannot reach a terminal derived node
- evidence layer outside the allowed engineering/internal set
- runtime flags set to true
- claim-boundary overreach
- short-horizon/canary evidence being upgraded to 30D verdict
- actual verdict executable or executed flags set to true

## Digest Convention

The final `summary.json` is written first. Its sha256 is stored in `manifest.json` as `summary_sha256`. The summary also includes a stable `graph_content_sha256` over the normalized graph content; that digest is independent of output directory and run id.

## Evidence Layer

`evidence_layer=engineering_internal_provenance_graph_hash_index`

This is an internal engineering source-integrity preflight only. It does not alter the 30D maturity gate and does not authorize v3.7 verdict execution.
