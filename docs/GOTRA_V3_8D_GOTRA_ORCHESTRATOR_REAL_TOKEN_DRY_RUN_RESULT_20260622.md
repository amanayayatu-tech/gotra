# GOTRA v3.8D Orchestrator Real-Token Dry-Run Result

Date: 2026-06-22

## Evidence Layer

`engineering_internal_gotra_orchestrator_real_token_dry_run`

This result records a bounded real-token dry-run of GOTRA orchestration wiring
using synthetic/local inputs only. It is not an actual v3.7 or v3.8 verdict, not
30D readiness, not a provider benchmark, not an OOS/science/public/trading
claim, and not investment advice.

## Current Boundary

- actual 30D readiness: `DATA_NOT_MATURED`
- actual 30D next check: `2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `actual_30d_verdict_executed=false`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- historical direct LLM label remains `direct_llm_parametric_memory_control`

## Implemented Surface

Added:

- `scripts/baseline_v3_8d_gotra_orchestrator_real_token_dry_run.py`
- `tests/test_v3_8d_gotra_orchestrator_real_token_dry_run.py`

The harness enforces:

- allowed backend/model are `codex_responses_oauth_backend` / `gpt-5.5`
- reasoning effort is `xhigh`
- no fallback to Kimi, GLM, or DeepSeek
- default `3` real calls, hard maximum `5`
- token usage budget and hard limit checks
- raw responses, parsed packets, and orchestrator traces restricted to `/tmp`
- required packet v2 schema through the existing v3.8C validator
- claim-boundary scan for packet and summary surfaces
- provenance/hash metadata for every call
- usage metadata required for pass status
- secret redaction and summary secret scan
- final `summary.json` digest stored in `manifest.json`

## Local Validation

- `py_compile`: pass
- `ruff`: pass
- focused v3.8D pytest: `12 passed`
- relevant v3.8B/v3.8C/v3.7H/v3.7I/provenance/claim-boundary
  regression: `113 passed`
- full pytest: `835 passed`

## Local Mock Validation

Local mock validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8d_mock_validation_20260622T050000Z/runs/baseline_v3_8d_gotra_orchestrator_real_token_dry_run_mock_20260622T050000Z/summary.json`
- summary sha256:
  `78eb543d2765ca3f703a141efd79502b666348ba6f497e510f3fff519a2aac99`
- status: `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS`
- call count shape: `3`
- token usage total: `36`

## Real-Token Dry-Run Validation

Real-token validation was written only under `/tmp`:

- summary:
  `/tmp/gotra_v3_8d_real_validation_20260622T050100Z/runs/baseline_v3_8d_gotra_orchestrator_real_token_dry_run_real_20260622T050100Z/summary.json`
- summary sha256:
  `1ed528dd252380a69fb829c1f4fe183ef4255db29ca72f0ff02a397167fd765f`
- status: `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS`
- backend/model: `codex_responses_oauth_backend` / `gpt-5.5`
- real calls count: `3`
- token usage total: `6765`
- latency ms values: `25517`, `24152`, `26395`
- latency min/median/max ms: `24152` / `25517` / `26395`
- schema pass rate: `1.0`
- overclaim rate: `0.0`
- usage availability rate: `1.0`
- raw response sha256s:
  - `c757512af1146741db97d7db79f87e461d684d8f16b82e75f690a936585c53c9`
  - `33e399723444321f18f6fe471567e510c3d1d8a0580cddff7b83323b79e4b662`
  - `93a7764c689ac6ddf0389533922796675e3497bf3ff3a6b5dd2b3b2bc8b955d1`
- parsed packet sha256s:
  - `fdf2ca20aecd631c47b6f88c8c1dcd571637612eec2d40cf0f5e71f79dbd18ac`
  - `ac4b99a5f8159eaeac361234e25bccc94ef768808580c2f0e0c8fd534f8f00db`
  - `e80c6c7c7be6793f1e78939c7c2b55de44c4e5b55039c46ed8b2cafeedb848e5`
- orchestrator trace sha256s:
  - `53af5f432f01cf320075a1a74ef1737ff8ba4ad29b8d603661adf607ad9b60a4`
  - `0ffd75dea0d6c0169337152ea5e520d9917a916ad149aa5446c5a89276fedf99`
  - `06a87efeb38cf63ed3c4dc079f360bfd390c8d2523ed64f28ab41e4353161f22`

Runtime boundary:

- raw response handling: `/tmp` only
- parsed packet handling: `/tmp` only
- orchestrator trace handling: `/tmp` only
- repo commits: code/tests/docs plus hashes and summary fields only
- `provider_or_backend_called=true`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `v3_7_actual_verdict_executable=false`

Docs claim-boundary scan:

- summary:
  `/tmp/gotra_v3_8d_claim_scan_20260622T050600Z/baseline_v3_6ab_evidence_claim_boundary_scan_v3_8d_docs_20260622T050600Z/summary.json`
- summary sha256:
  `cb471a324e82221bb9195ee196ab140e0a860e1bc98f3267dfcd67068c8fa1c3`
- status: `CLAIM_BOUNDARY_CLEAN`

v3.7H claim-boundary regression over the PR files:

- summary:
  `/tmp/gotra_v3_8d_claim_regression_20260622T050600Z/baseline_v3_7h_claim_boundary_regression_v3_8d_20260622T050600Z/summary.json`
- summary sha256:
  `7f39455140352c301d3724fc940d046e30eacfa077a859a739b96c20b4f27a32`
- status: `V3_7_CLAIM_BOUNDARY_REGRESSION_READY`
- blockers: `0`

## Non-Claims

This is engineering/internal dry-run evidence only. It does not score outcomes,
does not produce a research verdict, does not emit a comparative result, and
does not authorize the actual 30D v3.7 verdict.
