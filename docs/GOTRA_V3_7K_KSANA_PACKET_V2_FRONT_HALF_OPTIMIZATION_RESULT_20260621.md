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
- ranked hypothesis field types
- non-empty counterfactuals, falsification triggers, expected evidence,
  evidence gaps, and disagreement fields
- provenance consistency and forbidden source paths
- claim boundary and parametric-memory-control boundary
- runtime flags remain false
- final `summary.json` digest is verifiable through `manifest.json`

## Local Mock Validation

Run id:
`baseline_v3_7k_ksana_packet_v2_front_half_validation_20260621T144939Z`

Summary path:
`/tmp/gotra_v3_7k_ksana_packet_v2_front_half_validation_20260621T144939Z/runs/baseline_v3_7k_ksana_packet_v2_front_half_validation_20260621T144939Z/summary.json`

Summary sha256:
`88c093b0f346ca15f890976dd1c7c8cbbb702b55ed73b9620bc1c541b1bee410`

Digest manifest path:
`/tmp/gotra_v3_7k_ksana_packet_v2_front_half_validation_20260621T144939Z/runs/baseline_v3_7k_ksana_packet_v2_front_half_validation_20260621T144939Z/manifest.json`

Digest manifest sha256:
`42cf975ff33f843577d1f8a73b30aa6e8d498c3c58cbf99201ef6279da0be7a6`

Summary status:

- `validator_status=KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY`
- `packet_schema_valid=true`
- `source_run_id=ksana-packet-v2-validation-candidate`
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
- packet missing ranked hypotheses -> `BLOCKED_SCHEMA`
- packet missing counterfactuals -> `BLOCKED_SCHEMA`
- packet missing falsification trigger -> `BLOCKED_SCHEMA`
- scalar or empty `disagreement_with_price_only` -> `BLOCKED_SCHEMA`
- missing provenance -> `BLOCKED_PROVENANCE`
- forbidden source artifact path -> `BLOCKED_PROVENANCE`
- boundary-overreach wording -> `BLOCKED_OVERCLAIM`
- `direct_llm_parametric_memory_control` clean-baseline misuse wording -> blocked
- `direct_llm_parametric_memory_control` boundary -> accepted
- valid packet v2 -> `KSANA_PACKET_V2_READY_FOR_PROVIDER_CANARY`
- final `summary.json` digest is verifiable through `manifest.json`
- no provider, no new Codex CLI, no formal-lite, no actual 30D verdict

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py
uv run ruff check --no-cache scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py tests/test_ksana_packet_v2_front_half_optimization.py
uv run pytest -q tests/test_ksana_packet_v2_front_half_optimization.py
uv run pytest -q tests/test_ksana_packet_v2_front_half_optimization.py tests/test_ksana_cognitive_lift_audit.py tests/test_cognitive_lift_fixture_comparison.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_docs_20260621T145227Z \
  --output-dir /tmp/gotra_v3_7k_claim_scan_baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_docs_20260621T145227Z/runs \
  --file docs/GOTRA_V3_7K_KSANA_PACKET_V2_FRONT_HALF_OPTIMIZATION_PREREG_20260621.md \
  --file docs/GOTRA_V3_7K_KSANA_PACKET_V2_FRONT_HALF_OPTIMIZATION_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7K tests: `14 passed`
- v3.6AI/v3.6AJ/v3.7K cognitive-lift regression: `43 passed`
- v3.7A/v3.7B/v3.7 entry/readiness/claim-boundary regression: `72 passed`
- v3.7K docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7k_claim_scan_baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_docs_20260621T145227Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7k_docs_20260621T145227Z/summary.json`
  - summary sha256:
    `bfb5ccaf2e8283a90e0f476334bb1d426859990908e27e78885a001882644e4c`
- Full test suite: `645 passed`

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
