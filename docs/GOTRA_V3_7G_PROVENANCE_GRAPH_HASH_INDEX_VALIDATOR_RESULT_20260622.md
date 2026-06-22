# GOTRA v3.7G Provenance Graph / Artifact Hash Index Validator Result

## Result Summary

v3.7G adds a fixture-only deterministic provenance graph and artifact hash index validator:

- Script: `scripts/baseline_v3_7g_provenance_graph_hash_index_validator.py`
- Focused tests: `tests/test_v3_7g_provenance_graph_hash_index_validator.py`
- Evidence layer: `engineering_internal_provenance_graph_hash_index`
- Actual 30D readiness: `DATA_NOT_MATURED`
- Actual 30D next check: `2026-07-21T00:00:00Z`
- v3.7 actual verdict executable: `false`
- v3.7 actual verdict executed: `false`
- Provider/backend called: `false`
- Codex CLI new call: `false`
- Formal-lite entered: `false`

This result is fixture-only engineering prep. It is not an actual 30D forward-live verdict, not an OOS/science/public/trading claim, not trading or investment advice, and does not emit a deterministic/full_gotra winner.

## Implemented Checks

The validator checks:

- node and edge schema
- node source hash presence and local byte-level hash match
- nested provenance fields and run/path/hash consistency
- forbidden/raw path boundary
- `generated_at` ISO timestamp parsing
- duplicate node id
- edge reference integrity
- cycle detection
- required source reachability
- allowed evidence layers
- runtime flags false
- explicit runtime and verdict boundary flags at root, node, and provenance object level
- forbidden source paths short-circuited before hash reads
- status-like fields scanned for actual verdict/readiness wording
- generic graph artifact path fields included in path-boundary scan
- graph content digest includes boundary-critical fields
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- claim-boundary overreach
- short-horizon/canary evidence not upgraded to 30D verdict
- actual verdict executable/executed flags remain false

## Local Validation Snapshot

Focused v3.7G unit validation:

- `uv run python -m py_compile scripts/baseline_v3_7g_provenance_graph_hash_index_validator.py`
- `uv run pytest -q tests/test_v3_7g_provenance_graph_hash_index_validator.py`
- Result after review hardening: `20 passed`

Formatting and regression validation:

- `uv run ruff check --no-cache scripts/baseline_v3_7g_provenance_graph_hash_index_validator.py tests/test_v3_7g_provenance_graph_hash_index_validator.py`
- Result: pass
- Relevant regression command: `uv run pytest -q tests/test_v3_7g_provenance_graph_hash_index_validator.py tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py tests/test_v3_7d_short_horizon_canary_maturity_recheck.py tests/test_v3_7e_evidence_dashboard_hardening.py tests/test_v3_7f_continuous_monitor_ledger.py tests/test_ksana_packet_v2_front_half_optimization.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py`
- Result: `163 passed`
- Full pytest: `729 passed`
- v3.7G docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`

The final local/mock validation summary path and manifest hash are recorded during PR validation and not committed as runtime artifacts.

Local/mock v3.7G CLI validation:

- Run id: `baseline_v3_7g_provenance_graph_hash_index_validator_repair_20260622T010000Z`
- Status: `V3_7_PROVENANCE_GRAPH_HASH_INDEX_READY`
- Summary path: `/tmp/gotra_v3_7g_repair_validation_20260622T010000Z/runs/baseline_v3_7g_provenance_graph_hash_index_validator_repair_20260622T010000Z/summary.json`
- Manifest path: `/tmp/gotra_v3_7g_repair_validation_20260622T010000Z/runs/baseline_v3_7g_provenance_graph_hash_index_validator_repair_20260622T010000Z/manifest.json`
- Summary sha256: `848651f240819c75dba52d169e7934141ad4462029c5536a67df6a7abfe8560b`
- Graph content sha256: `f8eb91757e1ccc68fe7fdb34106b35f3aa35f4c61b873b418763c740b85518f2`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`

## Artifact Boundary

Committed files are limited to v3.7G code, tests, and docs. No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts, `.env*`, SQLite/DB, bundle/tar/zip, or Stage8/Stage9 artifacts are part of this result.

## Next Safe Action

Continue engineering/internal preflight work or wait for the scheduled 30D maturity recheck. v3.7 actual 30D verdict remains blocked until real actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
