# GOTRA ksana Public Adapter Hardening Result

Date: 2026-06-21

## Project

- Project: GOTRA ksana CI / public adapter hardening
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-ksana-public-adapter-hardening-20260621`
- Base: `origin/main` at `5e3f22573d4bf8c55cd7c362abc9e614fecaddf7`

## Evidence Layer

Adapter engineering/local validation only.

This stage did not call Kimi/GLM/DeepSeek provider APIs, did not call the Codex
CLI backend, did not run formal-lite, and does not make OOS, science/public,
product superiority, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. This adapter work does not use `direct_llm` for any
GOTRA/ksana/alaya conclusion.

## Coupling Audit Summary

Current code paths found:

| Path | Status | Notes |
|---|---|---|
| `scripts/baseline_v3_four_arm.py` `research_artifact_filter_result` / `filter_external_research_artifacts` | `ADAPTER_BACKED` | External `research_artifacts_path` rows now pass through `gotra.ksana_public_adapter`. Synthetic fallback remains local harness plumbing. |
| `scripts/baseline_v3_5_forward_live_capture.py` `capture_research_filter_result` | `ADAPTER_BACKED_INDIRECTLY` | Reuses the v3 research filter, then adds capture timestamp guards. |
| `tests/fixtures/baseline_v3_1_research_artifacts.json` | `LEGACY_FIXTURE_COMPAT` | Fixture has no explicit public schema, so accepted rows are marked `adapter_legacy_unverified=true`; future-leak row is still rejected. |
| `pyproject.toml` local dependency `ksana-researchos = { path = "engine/ksana" }` | `INTERNAL_SUBMODULE_DEPENDENCY` | Dependency remains for existing repo tests/imports; not refactored in this stage. |
| `gotra/perplexity_executor/executor.py` | `LEGACY_INTERNAL_COUPLING` | Reads/writes ksana Perplexity YAML/result shapes for orchestration compatibility; not modified here. |
| `engine/ksana/**` | `INTERNAL_SUBMODULE` | Not modified. Public adapter is in GOTRA and does not call provider/LLM code. |

## Adapter Contract

New module:

- `gotra/ksana_public_adapter.py`

Schema:

- `gotra.ksana_public_research_adapter.v1`

The adapter normalizes local research artifacts into the v3 harness-compatible
`research_artifact` shape and retains:

- input identity: `ticker`, `decision_date`, `horizon_days`, `input_layer`,
  `source_kind`
- availability metadata: `availability_date`, `latest_visible_price_date`,
  `publish_timestamp`, `captured_at`, `decision_date_max`
- body fields: `summary`, `text`, `citations`, `evidence`, `claims`,
  `features`
- provenance: `source_artifact_path`, `source_artifact_hash`,
  `source_fixture_id`, `source_run_id`, `provenance_hash`
- legacy marker: `adapter_legacy_unverified`

The adapter is deterministic/local only and does not require provider, Codex CLI,
LLM, API key, or network access.

## Blocked / Error Modes

Structured blocked diagnostics now cover:

- `missing_or_invalid_required_field`
- `unknown_schema_version`
- `future_data_metadata_leak`
- `untrusted_source_kind`
- `artifact_identity_mismatch`
- `source_kind_not_ksana_research`
- `schema_type_mismatch`

Synthetic rows can remain visible as synthetic local evidence, but synthetic,
deterministic, or reference packets cannot masquerade as `ksana_real_research`.
Deterministic/reference packets are rejected from the ksana research packet path.

## Harness Integration

`scripts/baseline_v3_four_arm.py` now calls the adapter from
`filter_external_research_artifacts`. Existing top-level rejection fields are
preserved:

- `rejected_research_artifact_count`
- `rejected_research_future_data_count`
- `rejected_research_schema_count`

Additional diagnostics are exposed:

- `rejected_research_identity_count`
- `legacy_unverified_research_artifact_count`
- `ksana_public_adapter_issue_count`
- `ksana_public_adapter_issues`

## Focused Tests

New focused tests:

- valid public research packet normalizes with provenance path/hash/run id
- missing required field blocks
- unknown schema version blocks
- future metadata leak blocks
- synthetic packet cannot masquerade as `ksana_real_research`
- reference packet cannot enter the ksana research packet path
- v3 harness filter uses the adapter while preserving legacy fixture behavior

Existing v3/v3.5 harness tests were kept in scope for validation.

## Validation

Commands run:

```bash
uv run python -m py_compile gotra/ksana_public_adapter.py scripts/baseline_v3_four_arm.py scripts/baseline_v3_5_forward_live_capture.py gotra/backtest/statistics.py
uv run ruff check --no-cache gotra/ksana_public_adapter.py scripts/baseline_v3_four_arm.py scripts/baseline_v3_5_forward_live_capture.py tests/test_ksana_public_adapter.py tests/test_baseline_v3_four_arm.py tests/test_forward_live_capture.py gotra/backtest/statistics.py
uv run pytest -q tests/test_ksana_public_adapter.py
uv run pytest -q tests/test_baseline_v3_four_arm.py
uv run pytest -q tests/test_forward_live_capture.py
uv run pytest -q
```

Results:

- `py_compile`: PASS
- `ruff`: PASS
- `tests/test_ksana_public_adapter.py`: `7 passed`
- `tests/test_baseline_v3_four_arm.py`: `49 passed`
- `tests/test_forward_live_capture.py`: `13 passed`
- full pytest: `303 passed`

## Artifact Boundary

No run artifacts, provider raw outputs, Codex CLI transcripts, `.env*`,
SQLite/DB files, bundles, tar/zip files, paper trading data, Stage8/Stage9 local
artifacts, or README changes are part of this result.

## Next Action

After this PR is reviewed/merged, remaining legacy/internal ksana coupling can be
reduced in a separate stage, starting with a public contract around
`gotra/perplexity_executor/executor.py` if that path becomes part of the public
research artifact pipeline.
