# GOTRA v3.7B Verdict Report Schema Validator Result

Date: 2026-06-21

## Scope

This PR adds a deterministic/local schema and provenance validator for the
target v3.7 actual verdict report. It is
`engineering/local v3.7 verdict report schema validator`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- The validator does not emit a deterministic / `full_gotra` / ksana winner.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_7b_verdict_report_schema_validator.py`
- `tests/test_v3_7b_verdict_report_schema_validator.py`
- `docs/GOTRA_V3_7B_VERDICT_REPORT_SCHEMA_VALIDATOR_PREREG_20260621.md`
- `docs/GOTRA_V3_7B_VERDICT_REPORT_SCHEMA_VALIDATOR_RESULT_20260621.md`

## Validator

New entrypoint:

```bash
uv run python scripts/baseline_v3_7b_verdict_report_schema_validator.py \
  --report-manifest /path/to/synthetic_report_manifest.json \
  --validator-run-id baseline_v3_7b_verdict_report_schema_validator_<timestamp> \
  --output-dir /tmp/gotra_v3_7b_verdict_report_schema_validator/runs
```

Inputs are local/synthetic report fixtures or `/tmp` validation artifacts only.
Runtime output is written to `/tmp` or a caller-supplied ignored output root and
is not committed.

The validator checks:

- required target report schema fields
- source readiness and scored summary sha256 values
- optional local source summary hash verification against final bytes
- report run id and source run id consistency with provenance
- count type and pairing coverage consistency
- future-data and provenance blocker counts
- forbidden source artifact paths
- claim boundary and winner/verdict boundary
- runtime flags remain false

## Local Mock Validation

Run id:
`baseline_v3_7b_verdict_report_schema_validator_validation_20260621T143029Z`

Summary path:
`/tmp/gotra_v3_7b_verdict_report_schema_validator_20260621T143029Z/runs/baseline_v3_7b_verdict_report_schema_validator_validation_20260621T143029Z/summary.json`

Summary sha256:
`6b32919270f569483c60d8549e4e71b2e0ab3c93d75773045a6cac7fdf3f8239`

Digest manifest path:
`/tmp/gotra_v3_7b_verdict_report_schema_validator_20260621T143029Z/runs/baseline_v3_7b_verdict_report_schema_validator_validation_20260621T143029Z/manifest.json`

Digest manifest sha256:
`070d659ffa4af55fc94fe94603921de7a33ea4007f01421b30624c69d25231f2`

Summary status:

- `validator_status=V3_7_REPORT_SCHEMA_READY`
- `report_schema_valid=true`
- `readiness_summary_hash_valid=true`
- `scored_summary_hash_valid=true`
- `matured_count=2`
- `scored_count=2`
- `paired_clean_count=2`
- `full_gotra_available_count=2`
- `deterministic_reference_available_count=2`
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

This status is report schema/provenance validation only. It is not an actual
30D forward-live verdict and does not authorize v3.7 execution.

## Test Coverage

Focused tests cover:

- valid synthetic report -> `V3_7_REPORT_SCHEMA_READY`
- missing readiness summary hash -> schema blocker
- wrong readiness summary hash -> provenance blocker
- missing scored summary hash -> schema blocker
- verdict report run id provenance mismatch -> `BLOCKED_PROVENANCE`
- future-data violation -> `BLOCKED_FUTURE_DATA`
- paired coverage inconsistency -> `BLOCKED_PAIRING`
- negative and non-integer counts -> `BLOCKED_SCHEMA`
- forbidden source artifact path -> `BLOCKED_PROVENANCE`
- winner / overclaim wording -> `BLOCKED_OVERCLAIM`
- final `summary.json` digest is verifiable through `manifest.json`
- no provider, no Codex CLI, no formal-lite, no winner, and no actual 30D
  verdict execution

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7b_verdict_report_schema_validator.py scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_7b_verdict_report_schema_validator.py tests/test_v3_7b_verdict_report_schema_validator.py
uv run pytest -q tests/test_v3_7b_verdict_report_schema_validator.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7b_docs_20260621T143029Z \
  --output-dir /tmp/gotra_v3_7b_claim_scan_20260621T143029Z/runs \
  --file docs/GOTRA_V3_7B_VERDICT_REPORT_SCHEMA_VALIDATOR_PREREG_20260621.md \
  --file docs/GOTRA_V3_7B_VERDICT_REPORT_SCHEMA_VALIDATOR_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7B report schema validator tests: `12 passed`
- Relevant v3.7A / v3.7 entry / v3.6 readiness / claim-boundary regression:
  `60 passed`
- v3.7B docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7b_claim_scan_20260621T143029Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7b_docs_20260621T143029Z/summary.json`
  - summary sha256:
    `b36d49db3bd3ee511c8f37bea0067f58be2b78abaecda572bbd9e740f126f63e`
- Full test suite: `631 passed`

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
