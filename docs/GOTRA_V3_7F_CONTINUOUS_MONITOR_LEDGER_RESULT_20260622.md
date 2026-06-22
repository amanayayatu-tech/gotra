# GOTRA v3.7F Continuous Monitor Ledger Result

Date: 2026-06-22

## Scope

This PR adds a deterministic/local continuous monitor ledger and validator. The
evidence layer is `engineering_internal_continuous_monitor_ledger`.

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

## Current Main and Gate State

- `origin/main` before this branch:
  `dac5f685b09abffa361a5d65a83cfb6fabca996d`
- Latest merged PR: `#59`
- Latest merged PR head: `c729488b80219157434811b232fb43517a893c50`
- Latest merged PR commit: `dac5f685b09abffa361a5d65a83cfb6fabca996d`
- Open PR count before this branch: `0`
- Main CI evidence: `Python checks` success per Judge handoff
- Actual 30D readiness: `DATA_NOT_MATURED`
- Actual 30D next check: `2026-07-21T00:00:00Z`
- `actual_30d_checked_capture_run_count=4`
- `actual_30d_capture_artifact_count=128`
- `actual_30d_matured_candidate_count=0`
- `actual_30d_resolved_count=0`
- `actual_30d_scored_count=0`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

## Files Changed

- `scripts/baseline_v3_7f_continuous_monitor_ledger.py`
- `tests/test_v3_7f_continuous_monitor_ledger.py`
- `docs/GOTRA_V3_7F_CONTINUOUS_MONITOR_LEDGER_PREREG_20260622.md`
- `docs/GOTRA_V3_7F_CONTINUOUS_MONITOR_LEDGER_RESULT_20260622.md`

## Ledger Contents

The ledger builder validates and emits:

- current `main_commit`, `main_ci_status`, and `open_pr_count`
- latest merged PR number, head, and merge commit
- actual 30D readiness counts and blocker reasons
- hard false flags for actual verdict executable and executed
- short-horizon engineering/internal status
- v3.7A fixture harness status
- v3.7B report schema validator status
- v3.7C bootstrap/HAC eligibility preflight status
- v3.7D short-horizon canary recheck status
- v3.7E evidence dashboard status
- `known_blockers` and `next_safe_actions`
- source document or mock summary references
- runtime flags all false
- `evidence_layer=engineering_internal_continuous_monitor_ledger`

## Boundary Guard

The command blocks missing schema fields, true runtime flags, true actual
verdict flags, forbidden paths, and claim-boundary overreach. It uses the
existing v3.6AB claim-boundary scanner for ledger text and path checks.

Short-horizon/canary/dashboard information can appear only as
engineering/internal status. It cannot set `v3_7_actual_verdict_executable=true`
while actual 30D readiness is `DATA_NOT_MATURED`.

## Review Hardening

This repair hardens the active P2 review items:

- required status fields are included in claim-boundary scanning, so status
  wording cannot present short-horizon status as actual 30D verdict readiness
- `source_documents` or `source_summaries` must contain at least one non-empty
  reference
- append/index ledgers validate every object entry before returning a clean
  summary, including historical entries that are not selected as latest
- `generated_at` is parsed as an ISO timestamp before latest selection; malformed
  timestamps are `BLOCKED_SCHEMA`

## Local Mock Validation

Run id:
`baseline_v3_7f_continuous_monitor_ledger_repair_validation_20260622T001907Z`

Summary path:
`/tmp/gotra_v3_7f_continuous_monitor_ledger_repair_20260622T001907Z/runs/baseline_v3_7f_continuous_monitor_ledger_repair_validation_20260622T001907Z/summary.json`

Summary sha256:
`78fde94e14e9e706a2bec737db51ca8061f5b1439a5a32f5c769d952797a5d4e`

Digest manifest path:
`/tmp/gotra_v3_7f_continuous_monitor_ledger_repair_20260622T001907Z/runs/baseline_v3_7f_continuous_monitor_ledger_repair_validation_20260622T001907Z/manifest.json`

Digest manifest sha256:
`97f2e75a90cac891e2022b952bff1ac3876912743bb447204a5d2a9daf4001a4`

Summary status:

- `ledger_status=V3_7_CONTINUOUS_MONITOR_LEDGER_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `actual_30d_checked_capture_run_count=4`
- `actual_30d_capture_artifact_count=128`
- `actual_30d_matured_candidate_count=0`
- `actual_30d_resolved_count=0`
- `actual_30d_scored_count=0`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `artifact_boundary_status=clean`
- `claim_boundary_status=clean`
- `schema_boundary_status=clean`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

The local validation used a synthetic ledger fixture and wrote outputs only
under `/tmp`.

## Test Coverage

Focused tests cover:

- valid internal ledger -> `V3_7_CONTINUOUS_MONITOR_LEDGER_READY`
- missing required ledger field -> `BLOCKED_SCHEMA`
- 30D readiness not ready with actual executable true -> `BLOCKED_SCHEMA`
- short-horizon/dashboard status cannot authorize actual 30D verdict execution
- provider, Codex, or formal-lite true flags -> `BLOCKED_SCHEMA`
- forbidden artifact path references -> `BLOCKED_ARTIFACT`
- claim-boundary overreach -> `BLOCKED_OVERCLAIM`
- v3.7 verdict execution wording -> `BLOCKED_OVERCLAIM`
- final `summary.json` digest is verifiable through `manifest.json`
- append/index `ledger_entries` latest selection is deterministic
- non-object ledger entries -> `BLOCKED_SCHEMA`
- status-field maturity overclaim wording -> `BLOCKED_OVERCLAIM`
- empty source references -> `BLOCKED_SCHEMA`
- invalid historical ledger entry in an index -> `BLOCKED_SCHEMA`
- malformed `generated_at` timestamp -> `BLOCKED_SCHEMA`
- blocked ledgers exit nonzero

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7f_continuous_monitor_ledger.py scripts/baseline_v3_7e_evidence_dashboard_hardening.py scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py scripts/baseline_v3_7b_verdict_report_schema_validator.py scripts/baseline_v3_7c_bootstrap_hac_eligibility_preflight.py scripts/baseline_v3_7d_short_horizon_canary_maturity_recheck.py scripts/baseline_v3_7k_ksana_packet_v2_front_half_optimization.py scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_7f_continuous_monitor_ledger.py tests/test_v3_7f_continuous_monitor_ledger.py
uv run pytest -q tests/test_v3_7f_continuous_monitor_ledger.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py tests/test_v3_7d_short_horizon_canary_maturity_recheck.py tests/test_v3_7e_evidence_dashboard_hardening.py tests/test_v3_7f_continuous_monitor_ledger.py tests/test_ksana_packet_v2_front_half_optimization.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7f_docs_repair_20260622T002013Z \
  --output-dir /tmp/gotra_v3_7f_claim_scan_repair_20260622T002013Z/runs \
  --file docs/GOTRA_V3_7F_CONTINUOUS_MONITOR_LEDGER_PREREG_20260622.md \
  --file docs/GOTRA_V3_7F_CONTINUOUS_MONITOR_LEDGER_RESULT_20260622.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7F tests: `16 passed`
- Relevant v3.7A / v3.7B / v3.7C / v3.7D / v3.7E / v3.7K /
  v3.7 entry / v3.6 readiness / claim-boundary regression tests: `157 passed`
- v3.7F docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7f_claim_scan_repair_20260622T002013Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7f_docs_repair_20260622T002013Z/summary.json`
  - summary sha256:
    `bfbd691320534bc6aa8510bda657419f66d9c547670a45d5104819bcfc25a468`
  - manifest sha256:
    `b82449907451213c6943d0f3b072ad43abf7b1d356d7e8679bbf9438666bfb8c`
- Full test suite: `716 passed`

## Artifact Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

Actual 30D readiness remains `DATA_NOT_MATURED`.
`v3_7_actual_verdict_executable=false`.

## Next Safe Action

The safe next task is continued 30D maturity monitoring or another
engineering/internal ledger/dashboard hardening step. A real v3.7 deterministic
reference vs `full_gotra` verdict stage requires actual readiness
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
