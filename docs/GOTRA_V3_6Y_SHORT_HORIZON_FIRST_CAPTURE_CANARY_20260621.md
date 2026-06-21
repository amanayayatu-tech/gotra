# GOTRA v3.6Y Short-Horizon First-Capture Canary

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local plus forward-live capture canary only.

This stage starts the v3.6V short-horizon experiment family with one tiny
future-only capture canary. It does not run Kimi/GLM/DeepSeek provider APIs,
does not run formal-lite, does not score outcomes, and does not execute a v3.7
30D verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline.

## Base And Branch

- Repo: `/Users/peachy/Documents/gotra`
- Base stack head: PR #39
  `codex/gotra-v3-6x-evidence-package-dashboard-20260621 @ 2997261c7462d9f99b422f0edef1ca0d52e82838`
- Branch:
  `codex/gotra-v3-6y-short-horizon-first-capture-20260621`
- Target PR base:
  `codex/gotra-v3-6x-evidence-package-dashboard-20260621`

## Implementation

Added:

- `scripts/baseline_v3_6y_short_horizon_first_capture.py`
- `tests/test_short_horizon_first_capture.py`

The canary command is deliberately separate from the v3.5A 30D capture script
so this stage does not change 30D forward-live semantics. It supports:

- `mock` mode for local metadata/provenance validation.
- `codex-cli-capture` mode with an explicit `--execute-backend` safety switch.
- One-ticker first canary by default.
- Short-horizon `horizon_days`, default `1`.
- Required future-only metadata:
  `capture_timestamp_utc`, `decision_date_local`, `horizon_end_date`,
  `outcome_price_available_after_utc`, backend/model/reasoning, `prompt_hash`,
  transcript path, parsed decision hash, and `future_outcome_status=not_matured`.
- Maturity ledger rows linking `source_decision_id` to the future outcome
  availability timestamp.
- No outcome scoring fields and no winner/verdict fields in capture artifacts.

## Preregistered Canary Shape

First real capture canary:

- Ticker: `AAPL`
- Horizon: `1D`
- Arm: `direct_llm`
- Input layer: `price_only_packet`
- Backend: `codex_cli_llm_backend`
- Model: `gpt-5.5`
- Reasoning: `high`
- Backend concurrency: `1`
- Capture timestamp: `2026-06-21T03:00:00Z`
- Decision date local: `2026-06-21`
- Market-session note: weekend/non-market-session capture canary
- Outcome status: `not_matured`
- Outcome scoring: not entered

This short-horizon canary is not equivalent to the 30D cohort. It cannot
replace the `2026-07-21T00:00:00Z` 30D maturity recheck and cannot authorize
v3.7.

## Local Mock Validation

Command:

```bash
uv run python scripts/baseline_v3_6y_short_horizon_first_capture.py \
  --mode mock \
  --run-id baseline_v3_6y_short_horizon_first_capture_mock_20260621T045017Z \
  --output-dir /tmp/gotra_v3_6y_short_horizon_first_capture_mock_20260621T045017Z/runs \
  --tickers AAPL \
  --horizon-days 1 \
  --arms direct_llm \
  --input-layer price_only_packet \
  --capture-timestamp-utc 2026-06-21T03:00:00Z \
  --price-dir data/backtest/prices
```

Output, not committed:

`/tmp/gotra_v3_6y_short_horizon_first_capture_mock_20260621T045017Z/runs/baseline_v3_6y_short_horizon_first_capture_mock_20260621T045017Z/summary.json`

Summary sha256:

`19014b1327540755db0789acca9cb6d9e377907e740cd91d67fe5f071f3effa7`

Mock result:

- Status: `SHORT_HORIZON_CAPTURE_CANARY_PASS`
- Expected capture decisions: `1`
- Actual capture artifacts: `1`
- Future outcome status: `not_matured`
- Horizon end date: `2026-06-22`
- Provider/backend called: `false`
- Codex CLI called: `false`
- Formal-lite entered: `false`
- v3.7 30D verdict allowed: `false`

## Codex CLI Backend Canary

Command:

```bash
uv run python scripts/baseline_v3_6y_short_horizon_first_capture.py \
  --mode codex-cli-capture \
  --execute-backend \
  --run-id baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z \
  --output-dir /tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs \
  --tickers AAPL \
  --horizon-days 1 \
  --arms direct_llm \
  --input-layer price_only_packet \
  --capture-timestamp-utc 2026-06-21T03:00:00Z \
  --price-dir data/backtest/prices \
  --provider-model gpt-5.5 \
  --codex-cli-reasoning-setting high \
  --backend-concurrency 1 \
  --request-timeout-seconds 900
```

Output, not committed:

`/tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs/baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/summary.json`

Summary sha256:

`c40ecbe021afcd313abb896616e5dcd79329465c73496ccbf118f789f4682da9`

Capture artifact, not committed:

`/tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs/baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/captures/direct_llm/capture_2026-06-21_aapl_h1_price_only_packet.json`

Capture artifact sha256:

`c2b3a18e356ec6aa95dcab7bb35414f5298006c1c3f7c91989362c1271079e2c`

Result:

- Status: `SHORT_HORIZON_CAPTURE_CANARY_PASS`
- Backend: `codex_cli_llm_backend`
- Codex CLI version: `codex-cli 0.141.0`
- Model: `gpt-5.5`
- Reasoning: `high`
- Capture timestamp: `2026-06-21T03:00:00Z`
- Decision date local: `2026-06-21`
- Ticker: `AAPL`
- Arm: `direct_llm`
- Arm interpretation: `direct_llm_parametric_memory_control`
- Input layer: `price_only_packet`
- Horizon days: `1`
- Horizon end date: `2026-06-22`
- Outcome price available after UTC: `2026-06-23T00:00:00Z`
- Future outcome status: `not_matured`
- Expected capture decisions: `1`
- Actual capture artifacts: `1`
- Prompt hash count: `1`
- Output transcript path count: `1`
- Parsed decision hash count: `1`
- Future-data violation count: `0`
- Deterministic reference count: `1`
- Deterministic reference future-data violations: `0`
- Provider/backend called: `true`
- Codex CLI called: `true`
- Formal-lite entered: `false`
- v3.7 30D verdict allowed: `false`

Recorded artifact metadata:

- `source_decision_id`:
  `c4cc681621586695bd66755b9903b85433c1fdd6768fd28e4c21e9c7e29fcd3d`
- `prompt_hash`:
  `13c0bb12b896aae7a3c2bb5b768ad3932a6e69a0038f4d3fb1824ce583ad0494`
- `parsed_decision_hash`:
  `b50bfba63f37d69ffe7031cd6447e2661ec952e6e5c94fb91541811284853f55`
- Transcript path:
  `/tmp/gotra_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/runs/baseline_v3_6y_short_horizon_first_capture_codex_20260621T045041Z/codex_cli_transcripts/direct_llm/transcript_2026-06-21_aapl_price_only_packet.txt`
- Latest visible price date: `2026-06-18`
- Visible price rows: `1119`
- Future rows excluded: `0`

The raw transcript is local-only and is not committed or printed in this
document.

## Maturity Ledger

The canary maturity ledger has one row:

- `source_decision_id`:
  `c4cc681621586695bd66755b9903b85433c1fdd6768fd28e4c21e9c7e29fcd3d`
- Ticker: `AAPL`
- Arm: `direct_llm`
- Input layer: `price_only_packet`
- Decision date local: `2026-06-21`
- Horizon: `1D`
- Horizon end date: `2026-06-22`
- Outcome price available after UTC: `2026-06-23T00:00:00Z`
- Future outcome status: `not_matured`
- Outcome scoring allowed now: `false`

No outcome scoring, direction-hit, return, MSE, MAE, winner, or verdict is
computed in v3.6Y.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6y_short_horizon_first_capture.py
uv run ruff check --no-cache scripts/baseline_v3_6y_short_horizon_first_capture.py tests/test_short_horizon_first_capture.py
uv run pytest -q tests/test_short_horizon_first_capture.py
uv run python -m py_compile scripts/baseline_v3_6y_short_horizon_first_capture.py scripts/baseline_v3_6v_short_horizon_cohort_plan.py scripts/baseline_v3_6x_evidence_package_dashboard.py
uv run ruff check --no-cache scripts/baseline_v3_6y_short_horizon_first_capture.py tests/test_short_horizon_first_capture.py scripts/baseline_v3_6v_short_horizon_cohort_plan.py tests/test_short_horizon_cohort_plan.py scripts/baseline_v3_6x_evidence_package_dashboard.py tests/test_evidence_package_dashboard.py
uv run pytest -q tests/test_short_horizon_first_capture.py tests/test_short_horizon_cohort_plan.py tests/test_evidence_package_dashboard.py
uv run pytest -q
git diff --check
```

Results:

- py_compile: pass
- Ruff: pass
- Focused tests: `5 passed`
- v3.6Y/v3.6V/v3.6X regression set: `23 passed`
- Full test suite: `399 passed`
- `git diff --check`: pass

## Artifact Boundary

The mock and Codex CLI canary outputs are stored under `/tmp` and are not
committed. No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
transcripts, `.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts,
or README changes are intended for commit.

## Next Action

Do not execute v3.7. The 30D actual forward-live path remains governed by
v3.6S/v3.6T and still has `next_check_after=2026-07-21T00:00:00Z`. The
short-horizon canary can be resolved/scored only after its own maturity rule is
satisfied, and that future short-horizon result remains a separate experiment
family rather than a 30D verdict.
