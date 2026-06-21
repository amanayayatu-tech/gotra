# GOTRA v3.7D Short-Horizon Canary Maturity Recheck Result

Date: 2026-06-22

## Scope

This PR adds a deterministic/local short-horizon canary maturity recheck. The
evidence layer is `short_horizon_forward_live_canary_engineering`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- Not a deterministic / `full_gotra` / ksana winner.
- Not a replacement for the 2026-07-21 30D maturity gate.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_7d_short_horizon_canary_maturity_recheck.py`
- `tests/test_v3_7d_short_horizon_canary_maturity_recheck.py`
- `docs/GOTRA_V3_7D_SHORT_HORIZON_CANARY_MATURITY_RECHECK_PREREG_20260622.md`
- `docs/GOTRA_V3_7D_SHORT_HORIZON_CANARY_MATURITY_RECHECK_RESULT_20260622.md`

## Entrypoint

```bash
uv run python scripts/baseline_v3_7d_short_horizon_canary_maturity_recheck.py \
  --recheck-run-id baseline_v3_7d_short_horizon_canary_maturity_recheck_<timestamp> \
  --source-summary /path/to/source_summary.json \
  --expected-source-summary-sha256 <sha256> \
  --expected-source-artifact-sha256 <sha256> \
  --expected-run-id <source_run_id> \
  --source-artifact /path/to/source_capture.json \
  --output-dir /tmp/gotra_v3_7d_short_horizon_canary_maturity_recheck/runs \
  --as-of-timestamp-utc <timestamp> \
  --price-dir /path/to/local_price_cache
```

Inputs are existing local metadata and local price cache data only. Runtime
output is written to `/tmp` or a caller-supplied ignored output root and is not
committed.

The recheck verifies:

- source summary hash and run id
- source artifact hash
- source identity fields: decision id, ticker, capture timestamp, horizon,
  horizon end date, prompt hash, parsed decision hash
- forbidden source path boundary
- claim-boundary text
- daily-close maturity
- local decision and outcome price availability
- actual direction bucket in `long`, `avoid`, or `neutral`

## Local Mock Validation

Run id:
`baseline_v3_7d_short_horizon_canary_maturity_recheck_validation_20260621T163500Z`

Summary path:
`/tmp/gotra_v3_7d_short_horizon_canary_maturity_recheck_validation_20260621T163500Z/runs/baseline_v3_7d_short_horizon_canary_maturity_recheck_validation_20260621T163500Z/summary.json`

Summary sha256:
`98ec2c864dec0605cbb8f72513e2df014e43531190ff77f83d9a33d8c6c6e2d7`

Digest manifest path:
`/tmp/gotra_v3_7d_short_horizon_canary_maturity_recheck_validation_20260621T163500Z/runs/baseline_v3_7d_short_horizon_canary_maturity_recheck_validation_20260621T163500Z/manifest.json`

Digest manifest sha256:
`7c3cdb8a2f448097b00876c6d2e0f41c840b1c2a6407d74d707e49969b662583`

Summary status:

- `maturity_status=SHORT_HORIZON_READY`
- `outcome_status=RESOLVED`
- `resolved_count=1`
- `scored_count=1`
- `actual_direction=long`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `v3_7_actual_verdict_executable=false`

This status is local/mock short-horizon readability validation. It is not an
actual 30D forward-live verdict.

## Test Coverage

Focused tests cover:

- immature horizon -> `SHORT_HORIZON_NOT_MATURED`
- matured but missing price -> `BLOCKED_DATA`
- matured with local price data -> `SHORT_HORIZON_READY`
- missing source summary -> `BLOCKED_PROVENANCE`
- malformed source summary -> `BLOCKED_SCHEMA`
- wrong summary hash -> `BLOCKED_PROVENANCE`
- wrong source run id -> `BLOCKED_PROVENANCE`
- actual direction buckets limited to `long`, `avoid`, and `neutral`
- claim overreach text -> `BLOCKED_OVERCLAIM`
- forbidden source artifact path -> `BLOCKED_PROVENANCE`
- final `summary.json` digest is verifiable through `manifest.json`
- no provider, no Codex CLI new call, no formal-lite, and no actual 30D verdict
  execution

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7d_short_horizon_canary_maturity_recheck.py scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py scripts/baseline_v3_7b_verdict_report_schema_validator.py scripts/baseline_v3_7c_bootstrap_hac_eligibility_preflight.py scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_7d_short_horizon_canary_maturity_recheck.py tests/test_v3_7d_short_horizon_canary_maturity_recheck.py
uv run pytest -q tests/test_v3_7d_short_horizon_canary_maturity_recheck.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py tests/test_ksana_packet_v2_front_half_optimization.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py tests/test_v3_7d_short_horizon_canary_maturity_recheck.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7d_docs_final_20260621T163728Z \
  --output-dir /tmp/gotra_v3_7d_claim_scan_final_20260621T163728Z/runs \
  --file docs/GOTRA_V3_7D_SHORT_HORIZON_CANARY_MATURITY_RECHECK_PREREG_20260622.md \
  --file docs/GOTRA_V3_7D_SHORT_HORIZON_CANARY_MATURITY_RECHECK_RESULT_20260622.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7D tests: `10 passed`
- Relevant v3.7A / v3.7B / v3.7C / v3.7K / v3.7 entry /
  v3.6 readiness / claim-boundary regression tests: `126 passed`
- v3.7D docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7d_claim_scan_final_20260621T163728Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7d_docs_final_20260621T163728Z/summary.json`
  - summary sha256:
    `4864e4d20b74b98f75d70b1c27f8f88ec2fc5bfbca36f624606c57ac0d36c263`
- Full test suite: `685 passed`

## Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

Actual 30D readiness remains `DATA_NOT_MATURED`.
`v3_7_actual_verdict_executable=false`.

## Next Action

The safe next step is continued 30D maturity monitoring or additional
engineering/report hardening. A real v3.7 deterministic reference vs
`full_gotra` verdict stage requires actual readiness
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
