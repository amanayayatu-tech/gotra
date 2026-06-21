# GOTRA v3.7A Fixture Verdict Harness Dry-Run Result

Date: 2026-06-21

## Scope

This PR adds a deterministic/local fixture-only dry-run harness for the v3.7
verdict path. It is `engineering/local v3.7 fixture-only harness dry-run`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary:

- Not an actual 30D forward-live verdict.
- Not OOS evidence.
- Not science/public proof.
- Not trading or investment advice.
- The harness does not emit a deterministic / `full_gotra` / ksana winner.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py`
- `tests/test_v3_7a_fixture_verdict_harness_dry_run.py`
- `docs/GOTRA_V3_7A_FIXTURE_VERDICT_HARNESS_DRY_RUN_PREREG_20260621.md`
- `docs/GOTRA_V3_7A_FIXTURE_VERDICT_HARNESS_DRY_RUN_RESULT_20260621.md`

## Harness

New entrypoint:

```bash
uv run python scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py \
  --fixture-manifest /path/to/synthetic_fixture_manifest.json \
  --harness-run-id baseline_v3_7a_fixture_verdict_harness_dry_run_<timestamp> \
  --output-dir /tmp/gotra_v3_7a_fixture_verdict_harness_dry_run/runs
```

Inputs are local/synthetic fixtures only. Runtime output is written to `/tmp` or
a caller-supplied ignored output root and is not committed.

The harness verifies:

- one deterministic reference fixture and one `full_gotra` fixture per pair key
- no duplicate pair keys
- no unpaired rows
- source run id and source hash consistency between fixture and provenance
- no future-data violation
- no forbidden provenance/source paths
- no winner/verdict/OOS/science/public/trading overclaim wording

## Local Mock Validation

Run id:
`baseline_v3_7a_fixture_verdict_harness_dry_run_validation_20260621T140615Z`

Summary path:
`/tmp/gotra_v3_7a_fixture_verdict_harness_dry_run_20260621T140615Z/runs/baseline_v3_7a_fixture_verdict_harness_dry_run_validation_20260621T140615Z/summary.json`

Summary sha256:
`d3bbfe0fa50e30274de147c1e1b48926041b56dddf517a053db76afb3b5453ae`

Digest manifest path:
`/tmp/gotra_v3_7a_fixture_verdict_harness_dry_run_20260621T140615Z/runs/baseline_v3_7a_fixture_verdict_harness_dry_run_validation_20260621T140615Z/manifest.json`

Digest manifest sha256:
`ac9f5700260ce46abb6dce6d20afbd5fa7640c77660c9b8aaed059a835ab323a`

Summary status:

- `harness_status=V3_7_FIXTURE_HARNESS_READY`
- `input_fixture_count=2`
- `fixture_pair_count=1`
- `deterministic_fixture_count=1`
- `full_gotra_fixture_count=1`
- `paired_clean_count=1`
- `duplicate_pair_count=0`
- `future_data_violation_count=0`
- `provenance_blocker_count=0`
- `schema_blocker_count=0`
- `winner_emitted=false`
- `actual_30d_verdict_executed=false`
- `v3_7_actual_verdict_executable=false`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`

This status is fixture-only engineering validation. It is not an actual 30D
forward-live verdict and does not authorize v3.7 execution.

## Test Coverage

Focused tests cover:

- paired synthetic inputs -> `V3_7_FIXTURE_HARNESS_READY`
- missing deterministic fixture -> pairing blocker
- missing `full_gotra` fixture -> pairing blocker
- unpaired rows -> pairing blocker
- duplicate pair keys -> `BLOCKED_PAIRING`
- future-data violation -> `BLOCKED_FUTURE_DATA`
- provenance run id / hash blocker -> `BLOCKED_PROVENANCE`
- schema-unsafe row -> `BLOCKED_SCHEMA`
- winner / overclaim wording -> `BLOCKED_OVERCLAIM`
- final `summary.json` digest is verifiable through `manifest.json`
- no provider, no Codex CLI, no formal-lite, no winner, and no actual 30D
  verdict execution

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py scripts/baseline_v3_7_forward_live_entry_decision.py scripts/baseline_v3_6_forward_live_verdict_readiness_gate.py scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_7a_fixture_verdict_harness_dry_run.py tests/test_v3_7a_fixture_verdict_harness_dry_run.py
uv run pytest -q tests/test_v3_7a_fixture_verdict_harness_dry_run.py
uv run pytest -q tests/test_forward_live_v3_7_entry_decision.py tests/test_forward_live_verdict_readiness_gate.py tests/test_evidence_claim_boundary_scanner.py
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_v3_7a_docs_20260621T140615Z \
  --output-dir /tmp/gotra_v3_7a_claim_scan_20260621T140615Z/runs \
  --file docs/GOTRA_V3_7A_FIXTURE_VERDICT_HARNESS_DRY_RUN_PREREG_20260621.md \
  --file docs/GOTRA_V3_7A_FIXTURE_VERDICT_HARNESS_DRY_RUN_RESULT_20260621.md \
  --allow-overwrite
uv run pytest -q
```

Results:

- py_compile: pass
- Ruff: pass
- Focused v3.7A fixture harness tests: `12 passed`
- Relevant v3.7 entry / v3.6 readiness / claim-boundary regression: `48 passed`
- v3.7A docs claim-boundary scan: `CLAIM_BOUNDARY_CLEAN`
- Full test suite: `619 passed`

## Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

Actual 30D readiness remains `DATA_NOT_MATURED`; the next 30D check remains
governed by the actual maturity monitor. `v3_7_actual_verdict_executable=false`.

## Next Action

The safe next step is continued maturity monitoring or further fixture/report
hardening. A real v3.7 deterministic reference vs `full_gotra` verdict stage
requires actual readiness `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance and a separate authorization.
