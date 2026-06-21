# GOTRA v3.7E Evidence Dashboard Hardening Result

Date: 2026-06-22

## Scope

This PR adds a deterministic/local internal evidence dashboard hardening command.
The evidence layer is `engineering_internal_evidence_dashboard`.

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
  `d5e21f5d8f26f6ea21d1a592d2643a97a084098f`
- Open PR count before this branch: `0`
- Main CI evidence: `Python checks` success per Judge handoff
- Actual 30D readiness: `DATA_NOT_MATURED`
- Actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`

## Files Changed

- `scripts/baseline_v3_7e_evidence_dashboard_hardening.py`
- `tests/test_v3_7e_evidence_dashboard_hardening.py`
- `docs/GOTRA_V3_7E_EVIDENCE_DASHBOARD_HARDENING_PREREG_20260622.md`
- `docs/GOTRA_V3_7E_EVIDENCE_DASHBOARD_HARDENING_RESULT_20260622.md`

## Dashboard Contents

The dashboard builder validates and emits:

- current `main_commit`, `open_pr_count`, and `main_ci_status`
- actual 30D readiness status and `next_check_after`
- hard false flags for actual verdict executable and executed
- short-horizon engineering/internal status
- v3.7A fixture harness status
- v3.7B report schema validator status
- v3.7C bootstrap/HAC eligibility preflight status
- v3.7D short-horizon canary recheck status
- v3.7K ksana packet v2 status
- `known_blockers`, `can_say`, `cannot_say`, and `next_safe_actions`
- runtime flags all false
- `evidence_layer=engineering_internal_evidence_dashboard`

## Boundary Guard

The command blocks missing schema sections, true runtime flags, true actual
verdict flags, forbidden paths, and claim-boundary overreach. It uses the
existing v3.6AB claim-boundary scanner for dashboard text and path checks.

Short-horizon/canary information can appear only as engineering/internal status.
It cannot set `v3_7_actual_verdict_executable=true` while actual 30D readiness
is `DATA_NOT_MATURED`.

## Local Mock Validation

Run id:
`baseline_v3_7e_evidence_dashboard_hardening_validation_20260621T171753Z`

Summary path:
`/tmp/gotra_v3_7e_evidence_dashboard_hardening_validation_20260621T171753Z/runs/baseline_v3_7e_evidence_dashboard_hardening_validation_20260621T171753Z/summary.json`

Summary sha256:
`af85fb218221e1cd117a39c48081b8b5fa835b63cc7b4a243244507340c27755`

Digest manifest path:
`/tmp/gotra_v3_7e_evidence_dashboard_hardening_validation_20260621T171753Z/runs/baseline_v3_7e_evidence_dashboard_hardening_validation_20260621T171753Z/manifest.json`

Digest manifest sha256:
`d1e1ee39758e20b7c684ad14babf7828885cd54f093a43cb7efeb9855068c490`

Summary status:

- `dashboard_status=V3_7_EVIDENCE_DASHBOARD_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `actual_30d_next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `artifact_boundary_status=clean`
- `claim_boundary_status=clean`
- `schema_boundary_status=clean`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`

The local validation used a synthetic dashboard fixture and wrote outputs only
under `/tmp`.

## Test Coverage

Focused tests cover:

- valid internal dashboard -> `V3_7_EVIDENCE_DASHBOARD_READY`
- 30D readiness not ready keeps `v3_7_actual_verdict_executable=false`
- short-horizon status cannot authorize actual 30D verdict execution
- missing main/readiness/provenance sections -> `BLOCKED_SCHEMA`
- provider, Codex, or formal-lite true flags -> `BLOCKED_SCHEMA`
- claim-boundary overreach -> `BLOCKED_OVERCLAIM`
- v3.7 verdict execution wording -> `BLOCKED_OVERCLAIM`
- forbidden artifact path references -> `BLOCKED_ARTIFACT`
- blocked dashboards exit nonzero
- final `summary.json` digest is verifiable through `manifest.json`

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7e_evidence_dashboard_hardening.py
uv run ruff check --no-cache scripts/baseline_v3_7e_evidence_dashboard_hardening.py tests/test_v3_7e_evidence_dashboard_hardening.py
uv run pytest -q tests/test_v3_7e_evidence_dashboard_hardening.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7b_verdict_report_schema_validator.py tests/test_v3_7c_bootstrap_hac_eligibility_preflight.py tests/test_v3_7d_short_horizon_canary_maturity_recheck.py tests/test_ksana_packet_v2_front_half_optimization.py tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py tests/test_v3_7e_evidence_dashboard_hardening.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7e_docs_20260621T171923Z \
  --output-dir /tmp/gotra_v3_7e_claim_scan_20260621T171923Z/runs \
  --file docs/GOTRA_V3_7E_EVIDENCE_DASHBOARD_HARDENING_PREREG_20260622.md \
  --file docs/GOTRA_V3_7E_EVIDENCE_DASHBOARD_HARDENING_RESULT_20260622.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7E tests: `11 passed`
- Relevant v3.7A / v3.7B / v3.7C / v3.7D / v3.7K / v3.7 entry /
  v3.6 readiness / claim-boundary regression tests: `141 passed`
- v3.7E docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
  - summary path:
    `/tmp/gotra_v3_7e_claim_scan_20260621T171923Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_v3_7e_docs_20260621T171923Z/summary.json`
  - summary sha256:
    `adb5fc6635c49600cf7e7ca942dd4819f2abbbd3a3be0859dddb02ce66d712b3`
  - manifest sha256:
    `6c6127b871866704ff11be4e1c5836f1e4228a9188e46a710248f9d7bae0ce37`
- Full test suite: `700 passed`

## Artifact Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

Actual 30D readiness remains `DATA_NOT_MATURED`.
`v3_7_actual_verdict_executable=false`.

## Next Safe Action

The safe next task is continued 30D maturity monitoring or another
engineering/internal hardening step. A real v3.7 deterministic reference vs
`full_gotra` verdict stage requires actual readiness
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance and separate
authorization.
