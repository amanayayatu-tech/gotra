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
- duplicate pair keys and unpaired rows are blockers
- source run id, source artifact path, and source artifact sha256 are present
  and consistent with provenance
- forbidden source artifact paths are blocked
- future-data violation count is zero
- schema count fields are non-negative integers
- sample, ticker, date, and cluster coverage meet prereg thresholds
- no winner/verdict/OOS/science/public/trading overclaim wording is present

## Local Mock Validation

Run id:
`baseline_v3_7c_bootstrap_hac_eligibility_preflight_validation_20260621T154845Z`

Summary path:
`/tmp/gotra_v3_7c_bootstrap_hac_eligibility_preflight_20260621T154845Z/runs/baseline_v3_7c_bootstrap_hac_eligibility_preflight_validation_20260621T154845Z/summary.json`

Summary sha256:
`4eac6b1dc0a5ea4975457b4bab970cb057018ca6c5b9ceeeb6f43b63e804deb9`

Digest manifest path:
`/tmp/gotra_v3_7c_bootstrap_hac_eligibility_preflight_20260621T154845Z/runs/baseline_v3_7c_bootstrap_hac_eligibility_preflight_validation_20260621T154845Z/manifest.json`

Digest manifest sha256:
`a9e9782ebfc3858d68e3509415fb05e4780f7a4dbe9daa58a40d37e5a1321f28`

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
- provenance run id mismatch -> `BLOCKED_PROVENANCE`
- forbidden source artifact path -> `BLOCKED_PROVENANCE`
- malformed row and negative count -> `BLOCKED_SCHEMA`
- non-object fixture row -> `BLOCKED_SCHEMA`
- winner / p-value / overclaim wording -> `BLOCKED_OVERCLAIM`
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
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7c_docs_20260621T155106Z \
  --output-dir /tmp/gotra_v3_7c_claim_scan_20260621T155106Z/runs \
  --file docs/GOTRA_V3_7C_BOOTSTRAP_HAC_ELIGIBILITY_PREFLIGHT_PREREG_20260621.md \
  --file docs/GOTRA_V3_7C_BOOTSTRAP_HAC_ELIGIBILITY_PREFLIGHT_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7C bootstrap/HAC eligibility preflight tests: `14 passed`
- Relevant v3.7A / v3.7B / v3.7 entry / v3.6 readiness /
  claim-boundary / v3.7K regression tests: `94 passed`
- v3.7C docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7c_claim_scan_20260621T155106Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7c_docs_20260621T155106Z/summary.json`
  - summary sha256:
    `9affb4fdc8dee74862fa42503bd51d09c9d9f90ce6e6697b4714aa34e0beea00`
- Full test suite: `667 passed`

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
