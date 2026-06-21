# GOTRA v3.7C Bootstrap/HAC Eligibility Preflight Result

Date: 2026-06-21

## Scope

This PR adds a deterministic/local bootstrap/HAC eligibility preflight for the
future v3.7 verdict path. It is
`engineering/local v3.7 bootstrap HAC eligibility preflight`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- The preflight does not emit a deterministic / `full_gotra` / ksana winner.
- The preflight does not compute bootstrap/HAC estimates, p-values, or
  confidence intervals.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_7c_bootstrap_hac_eligibility_preflight.py`
- `tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py`
- `docs/GOTRA_V3_7C_BOOTSTRAP_HAC_ELIGIBILITY_PREFLIGHT_PREREG_20260621.md`
- `docs/GOTRA_V3_7C_BOOTSTRAP_HAC_ELIGIBILITY_PREFLIGHT_RESULT_20260621.md`

## Entrypoint

```bash
uv run python scripts/baseline_v3_7c_bootstrap_hac_eligibility_preflight.py \
  --fixture-manifest /path/to/synthetic_fixture_manifest.json \
  --preflight-run-id baseline_v3_7c_bootstrap_hac_eligibility_preflight_<timestamp> \
  --output-dir /tmp/gotra_v3_7c_bootstrap_hac_eligibility_preflight/runs
```

Inputs are local/synthetic fixtures only. Runtime output is written to `/tmp` or
a caller-supplied ignored output root and is not committed.

The preflight verifies:

- deterministic reference and `full_gotra` rows are paired by ticker, decision
  date, and horizon
- horizon is exactly 30 days
- duplicate pair keys and unpaired rows are blockers
- source run id, source artifact path, and source artifact sha256 are present
  in both top-level fields and nested provenance, and are consistent
- forbidden source artifact paths are blocked
- future-data violation count is explicitly present and zero
- schema count fields are non-negative integers
- path-only manifest entries load referenced local fixture files relative to
  the manifest
- sample, ticker, date, and cluster coverage meet prereg thresholds
- no winner/verdict/OOS/science/public/trading overclaim wording is present

CLI behavior: only `V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY` exits `0`. Any
insufficient or blocked status exits non-zero.

## Review Hardening

This repair hardens the active P2 review items:

- nested `provenance.source_*` fields are required and cannot be satisfied by
  top-level fallback fields
- non-ready eligibility statuses return non-zero CLI exit codes
- `rationale`, `reasoning`, and `statement` fields are scanned for claim-boundary
  overclaim text
- `--min-paired-clean-count` is enforced before READY
- non-30D horizons are `BLOCKED_SCHEMA`
- missing `future_data_violation_count` is `BLOCKED_SCHEMA`
- zero-valued p-values and HAC/bootstrap estimate fields block by field
  presence
- path-only manifest entries load referenced fixture JSON files relative to the
  manifest path

## Local Mock Validation

Run id:
`baseline_v3_7c_bootstrap_hac_eligibility_preflight_repair_validation_20260621T161319Z`

Summary path:
`/tmp/gotra_v3_7c_bootstrap_hac_eligibility_preflight_repair_20260621T161319Z/runs/baseline_v3_7c_bootstrap_hac_eligibility_preflight_repair_validation_20260621T161319Z/summary.json`

Summary sha256:
`7b1c244aafd32118e943c57486a943ff3c25a19304054c3f907afdcbe756c49d`

Digest manifest path:
`/tmp/gotra_v3_7c_bootstrap_hac_eligibility_preflight_repair_20260621T161319Z/runs/baseline_v3_7c_bootstrap_hac_eligibility_preflight_repair_validation_20260621T161319Z/manifest.json`

Digest manifest sha256:
`7ec57c2a51abc9250a6eefdc216052600fc13f0b915ab6634fedc16564545482`

Summary status:

- `preflight_status=V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY`
- `sample_count=4`
- `paired_clean_count=4`
- `ticker_cluster_count=2`
- `date_cluster_count=2`
- `date_coverage_count=2`
- `ticker_coverage_count=2`
- `deterministic_reference_available_count=4`
- `full_gotra_available_count=4`
- `paired_coverage_ratio=1.0`
- `bootstrap_eligible=true`
- `hac_eligible=true`
- `cluster_eligible=true`
- `future_data_violation_count=0`
- `provenance_blocker_count=0`
- `pairing_blocker_count=0`
- `schema_blocker_count=0`
- `overclaim_blocker_count=0`
- `winner_emitted=false`
- `actual_30d_verdict_executed=false`
- `v3_7_actual_verdict_executable=false`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`

This status is fixture-only statistical eligibility validation. It is not an
actual 30D forward-live verdict and does not authorize v3.7 execution.

## Test Coverage

Focused tests cover:

- valid multi-ticker / multi-date paired fixture ->
  `V3_7_BOOTSTRAP_HAC_PREFLIGHT_READY`
- insufficient sample count -> `INSUFFICIENT_SAMPLE_COUNT`
- single ticker cluster -> `INSUFFICIENT_CLUSTER_COVERAGE`
- insufficient date coverage -> `INSUFFICIENT_DATE_COVERAGE`
- missing deterministic reference arm -> `BLOCKED_PAIRING`
- missing `full_gotra` arm -> `BLOCKED_PAIRING`
- duplicate pair key -> `BLOCKED_PAIRING`
- future-data violation -> `BLOCKED_FUTURE_DATA`
- missing future-data count -> `BLOCKED_SCHEMA`
- provenance run id mismatch -> `BLOCKED_PROVENANCE`
- missing nested provenance fields -> `BLOCKED_PROVENANCE`
- forbidden source artifact path -> `BLOCKED_PROVENANCE`
- non-30D horizon -> `BLOCKED_SCHEMA`
- malformed row and negative count -> `BLOCKED_SCHEMA`
- path-only manifest entries load relative fixture files
- non-object fixture row -> `BLOCKED_SCHEMA`
- rationale/statement overclaim wording -> `BLOCKED_OVERCLAIM`
- winner / zero-valued p-value / estimate / overclaim wording ->
  `BLOCKED_OVERCLAIM`
- paired-clean threshold insufficiency -> `INSUFFICIENT_SAMPLE_COUNT`
- CLI non-ready statuses exit non-zero
- final `summary.json` digest is verifiable through `manifest.json`
- no provider, no Codex CLI, no formal-lite, no winner, and no actual 30D
  verdict execution

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7c_bootstrap_hac_eligibility_preflight.py scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py scripts/baseline_v3_7b_verdict_report_schema_validator.py scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py
uv run ruff check --no-cache scripts/baseline_v3_7c_bootstrap_hac_eligibility_preflight.py tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py
uv run pytest -q tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py tests/test_ksana_packet_v2_front_half_optimization.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7c_docs_repair_20260621T161410Z \
  --output-dir /tmp/gotra_v3_7c_claim_scan_repair_20260621T161410Z/runs \
  --file docs/GOTRA_V3_7C_BOOTSTRAP_HAC_ELIGIBILITY_PREFLIGHT_PREREG_20260621.md \
  --file docs/GOTRA_V3_7C_BOOTSTRAP_HAC_ELIGIBILITY_PREFLIGHT_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7C bootstrap/HAC eligibility preflight tests: `22 passed`
- Relevant v3.7A / v3.7B / v3.7 entry / v3.6 readiness /
  claim-boundary / v3.7K regression tests: `94 passed`
- v3.7C docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7c_claim_scan_repair_20260621T161410Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7c_docs_repair_20260621T161410Z/summary.json`
  - summary sha256:
    `2834c7f6c2b796ba4a1f385913d0ff28be5a2a44668996ce5aaaf4ae950da44c`
- Full test suite: `675 passed`

## Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

Actual 30D readiness remains `DATA_NOT_MATURED`; the next 30D check remains
governed by the actual maturity monitor. `v3_7_actual_verdict_executable=false`.

## Next Action

The safe next step is continued maturity monitoring or additional fixture/report
hardening. A real v3.7 deterministic reference vs `full_gotra` verdict stage
requires actual readiness `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance and a separate authorization.
