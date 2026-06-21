# GOTRA v3.7K Ksana Packet V2 Front-Half Optimization Result

Date: 2026-06-21

## Scope

This PR adds a deterministic/local validator for a fixture-only `ksana` research
packet v2 contract. It is
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

## Files Changed

- `scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py`
- `tests/test_ksana_packet_v2_front_half_optimization.py`
- `docs/GOTRA_V3_7K_KSANA_PACKET_V2_FRONT_HALF_OPTIMIZATION_PREREG_20260621.md`
- `docs/GOTRA_V3_7K_KSANA_PACKET_V2_FRONT_HALF_OPTIMIZATION_RESULT_20260621.md`

## Validator

New entrypoint:

```bash
uv run python scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py \
  --packet-manifest /path/to/synthetic_packet_v2_manifest.json \
  --baseline-manifest /path/to/synthetic_conservative_baseline_manifest.json \
  --validator-run-id baseline_v3_7k_ksana_packet_v2_front_half_<timestamp> \
  --output-dir /tmp/gotra_v3_7k_ksana_packet_v2_front_half/runs
```

The validator reads only local/synthetic fixtures or `/tmp` validation
artifacts. Runtime output is written to `/tmp` or a caller-supplied ignored
output root and is not committed.

The validator checks:

- required packet v2 schema fields
- exact fixture-only `evidence_layer`
- ranked hypothesis field types
- non-empty counterfactuals, falsification triggers, expected evidence,
  evidence gaps, and disagreement fields
- placeholder list entries are rejected instead of counted
- provenance consistency and forbidden source paths
- embedded manifest payload paths are checked for forbidden locations
- malformed manifests and non-object artifact entries return structured
  `BLOCKED_SCHEMA`
- positive baseline structural lift is required when a baseline manifest is
  provided
- claim boundary and parametric-memory-control boundary
- runtime flags remain false
- final `summary.json` digest is verifiable through `manifest.json`

## Local Mock Validation

Run id:
`baseline_v3_7k_ksana_packet_v2_front_half_repair_20260621T152121Z`

Summary path:
`/tmp/gotra_v3_7k_repair_validation_20260621T152121Z/runs/baseline_v3_7k_ksana_packet_v2_front_half_repair_20260621T152121Z/summary.json`

Summary sha256:
`c5530f855600a4939cdc1404f33618484a65e0a2b0b50d8865ad21775f10125c`

Digest manifest path:
`/tmp/gotra_v3_7k_repair_validation_20260621T152121Z/runs/baseline_v3_7k_ksana_packet_v2_front_half_repair_20260621T152121Z/manifest.json`

Digest manifest sha256:
`2dca48d01fe82d091d1290482bbcffd8cb9e98b1b97dc998e855d83dd77aad2a`

Summary status:

- `validator_status=KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY`
- `packet_schema_valid=true`
- `source_run_id=ksana-packet-v2-repair-candidate`
- `source_artifact_path=fixtures/ksana/v2/aapl_candidate.json`
- `hypothesis_count=2`
- `ranked_hypothesis_count=2`
- `counterfactual_count=3`
- `falsifiable_trigger_count=3`
- `explicit_disagreement_count=1`
- `evidence_gap_count=1`
- `uncertainty_decomposition_count=3`
- `price_only_disagreement_signal=true`
- `generic_caution_phrase_count=0`
- `information_gain_delta=25`
- `overclaim_blocker_count=0`
- `schema_blocker_count=0`
- `provenance_blocker_count=0`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `actual_30d_verdict_executed=false`
- `v3_7_actual_verdict_executable=false`

This status is fixture-only contract readiness for a possible future provider
canary. It is not a provider run, not a real outcome score, and not an actual
30D verdict.

## Test Coverage

Focused tests cover:

- conservative / generic caution-heavy packet -> `LOW_INFORMATION_GAIN`
- malicious or wrong `evidence_layer` -> `BLOCKED_SCHEMA`
- valid candidate against richer baseline with non-positive lift ->
  `LOW_INFORMATION_GAIN`
- packet missing ranked hypotheses -> `BLOCKED_SCHEMA`
- packet missing counterfactuals -> `BLOCKED_SCHEMA`
- packet missing falsification trigger -> `BLOCKED_SCHEMA`
- placeholder required list entries -> `BLOCKED_SCHEMA`
- ranked hypothesis missing non-empty text -> `BLOCKED_SCHEMA`
- scalar or empty `disagreement_with_price_only` -> `BLOCKED_SCHEMA`
- missing or invalid packet manifest -> structured `BLOCKED_SCHEMA`
- missing provenance -> `BLOCKED_PROVENANCE`
- forbidden source artifact path -> `BLOCKED_PROVENANCE`
- embedded manifest payload forbidden path -> `BLOCKED_SCHEMA`
- non-object artifact entry -> `BLOCKED_SCHEMA`
- boundary-overreach wording -> `BLOCKED_OVERCLAIM`
- `direct_llm_parametric_memory_control` clean-baseline misuse wording -> blocked
- `direct_llm_parametric_memory_control` boundary -> accepted
- valid packet v2 -> `KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY`
- final `summary.json` digest is verifiable through `manifest.json`
- no provider, no new Codex CLI, no formal-lite, no actual 30D verdict

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py scripts/baseline_v3_6ai_ksana_cognitive_lift_audit.py scripts/baseline_v3_6aj_cognitive_lift_fixture_comparison.py scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py scripts/baseline_v3_7b_verdict_report_schema_validator.py scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py tests/test_ksana_packet_v2_front_half_optimization.py
uv run pytest -q tests/test_ksana_packet_v2_front_half_optimization.py
uv run pytest -q tests/test_ksana_packet_v2_front_half_optimization.py tests/test_ksana_cognitive_lift_audit.py tests/test_cognitive_lift_fixture_comparison.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_repair_docs_20260621T152216Z \
  --output-dir /tmp/gotra_v3_7k_repair_claim_scan_baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_repair_docs_20260621T152216Z/runs \
  --file docs/GOTRA_V3_7K_KSANA_PACKET_V2_FRONT_HALF_OPTIMIZATION_PREREG_20260621.md \
  --file docs/GOTRA_V3_7K_KSANA_PACKET_V2_FRONT_HALF_OPTIMIZATION_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7K tests: `22 passed`
- v3.6AI/v3.6AJ/v3.7K cognitive-lift regression: `51 passed`
- v3.7A/v3.7B/v3.7 entry/readiness/claim-boundary regression: `72 passed`
- v3.7K docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7k_repair_claim_scan_baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_repair_docs_20260621T152216Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_repair_docs_20260621T152216Z/summary.json`
  - summary sha256:
    `c500e88a40fd3c25be01834e4b5a56ca2dcfc7a36c3350145be8b013b364a606`
- Full test suite: `653 passed`

## Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

Actual 30D readiness remains `DATA_NOT_MATURED`; `v3_7_actual_verdict_executable=false`.

## Next Action

The safe next step is a separately authorized, bounded provider canary using the
packet v2 contract. That canary must not start automatically from this PR and
must not use old Kimi/GLM/DeepSeek provider paths. The actual 30D v3.7 verdict
remains blocked until actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT`
with matching provenance.
