# GOTRA Baseline v3 Four-Arm Impl Result (2026-06-19T04:22:04Z)

## Scope

本结果只覆盖 Baseline v3 four-arm formal-lite harness 的实现层：

- evidence layer: `local checks`
- provider run: 未进入
- formal-lite acceptance: 未进入
- science / OOS / public / trading claim: 未进入

对应 prereg:
`docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md`

## Implemented

- 新增 `scripts/baseline_v3_four_arm.py`
  - four arms: `direct_llm`, `ksana_formatting_only`, `ksana_real_research`, `full_gotra`
  - input layers: `price_only_packet`, `richer_research_packet`
  - cache key includes `input_layer`
  - run namespace: `data/backtest/runs/baseline_v3_four_arm_*`
  - warm-up/scored segment tracking
  - richer research artifact fields with `source_kind` and `availability_date`
  - `research_source_leak` guard for `ksana_formatting_only`
  - richer-packet future-data guard
  - reasoning chars and product metric counters
  - manifest/step/summary schemas:
    - `gotra.baseline_v3.four_arm_decision.v1`
    - `gotra.baseline_v3.four_arm_step.v1`
    - `gotra.baseline_v3.four_arm_summary.v1`
- Extended `gotra/backtest/statistics.py`
  - `paired_loss_differences_v3(...)`
  - `cluster_bootstrap_ci(...)`
  - existing v1/v2 two-arm functions left in place
- Added `tests/test_baseline_v3_four_arm.py`
  - payload isolation
  - input-layer cache separation
  - source-leak and future-data guards
  - parser normalization/input-echo/ref isolation
  - warm-up exclusion and matured feedback
  - product metrics
  - v3 paired loss and cluster bootstrap determinism
  - manifest/summary/step schema and provider token fields

## Validation

Commands:

```bash
uv run python -m py_compile scripts/baseline_v3_four_arm.py
uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run pytest -q tests/test_baseline_v3_four_arm.py
uv run python scripts/baseline_v3_four_arm.py --mode mock --input-layer both \
  --tickers AAPL,MSFT,NVDA \
  --dates 2024-01-02,2024-02-01,2024-03-01,2024-04-01 \
  --warm-up-dates 1 \
  --run-id baseline_v3_four_arm_mock_impl_check
```

Results:

```text
py_compile: pass
ruff:       pass
pytest:     7 passed
mock run:   exit 0
```

Mock summary:

```json
{
  "status": "MOCK_PASS",
  "provider_call_status": "no real provider HTTP call",
  "expected_scored_points": 18,
  "paired_complete_points": 18,
  "paired_coverage": 1.0,
  "future_data_violations": 0,
  "research_source_leak_count": 0,
  "provider_error_count": 0,
  "schema_error_count": 0,
  "synthetic_evidence_count": 72,
  "full_gotra_feedback_available_scored_points": 18,
  "provider_max_tokens": 1200,
  "decision_schema": "gotra.baseline_v3.four_arm_decision.v1",
  "step_schema": "gotra.baseline_v3.four_arm_step.v1"
}
```

Artifacts:

- `data/backtest/runs/baseline_v3_four_arm_mock_impl_check/summary.json`
- `data/backtest/runs/baseline_v3_four_arm_mock_impl_check/manifest.json`
- `data/backtest/runs/baseline_v3_four_arm_mock_impl_check/ledger.jsonl`
- arm step files under the run directory

## Boundary

This is an implementation-layer freeze only. It proves local mechanics and mock
harness behavior. It does not prove provider/runtime health, formal-lite
acceptance, H1/H2/H3, OOS behavior, public research validity, or trading value.

Provider canary/ramp/formal-lite run remains a separate explicitly authorized
goal with `.env` readiness and provider gates.

## Hardening Follow-Up

After this initial result, the implementation was hardened before review PR:

- strict decision JSON top-level key rejection
- provider decision identity validation against task point before scoring/cache
- `short` downside-hit scoring rule documented in the prereg
- GLM/Kimi `provider_max_tokens` request-path application and metadata
- stricter `MOCK_PASS` requirements for scored steps and paired coverage
- provider canary no longer requires mature alaya feedback path

See the later `docs/GOTRA_BASELINE_V3_IMPL_HARDENING_REVIEW_*.md` document for
the expanded test mapping and hardening validation evidence.
