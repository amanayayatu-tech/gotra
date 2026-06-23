# GOTRA v3.8R Rubric-Anchored Reasoning-Quality Result

## Result

Status: `RUBRIC_ANCHORED_REASONING_QUALITY_PREREG_READY`

Evidence layer: `local_checks_rubric_anchored_reasoning_quality_prereg_schema`.

This result is a local schema/prereg validator result only. It does not execute provider/backend calls, Codex CLI calls, formal-lite, or actual 30D verdict logic.

## Runtime Boundary

- `provider_or_backend_called_for_prereg=false`
- `provider_canary_executed_for_prereg=false`
- `codex_cli_new_call=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `real_calls_count=0`
- `token_usage_total=0`
- `raw_output_boundary=/tmp only`
- `repo_raw_artifacts=[]`

## Verdict Boundary

- `rubric_anchored_reasoning_quality_verdict_status=RUBRIC_ANCHORED_REASONING_QUALITY_PREREG_READY`
- `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `direct_llm_clean_baseline=false`

## Local Validation

Summary path:
`/tmp/gotra_v3_8r_rubric_reasoning_quality_validation/gotra_v3_8r_rubric_reasoning_quality_20260622T000000Z/summary.json`

Summary sha256:
`f35b0219436a0402258bfdfc5b644e2bb7022aa154b92d43daafdad3f9a31b1e`

Manifest path:
`/tmp/gotra_v3_8r_rubric_reasoning_quality_validation/gotra_v3_8r_rubric_reasoning_quality_20260622T000000Z/manifest.json`

Locked digests:

- `rubric_sha256=173d498d31d5fc1efd6d895514ae6c0c89f5080fb8dff1448a3666167b03ca19`
- `source_artifact_sha256=515a8b26894b87b0e2ecbdabd0c59b27b05fd813a68c94fb049738a67cd5e7e8`
- `probe_rule_sha256=f748f8b188793fada28323889918dbcb6f67251d0be7a98400ca774ff19433b4`

Validation commands for this artifact:

```bash
codex-gotra-gate --cwd /Users/peachy/Documents/gotra
uv run python -m py_compile scripts/baseline_v3_8r_rubric_anchored_reasoning_quality_prereg.py
uv run ruff check scripts tests
uv run pytest tests/test_v3_8r_rubric_anchored_reasoning_quality_prereg.py
uv run pytest tests/test_v3_8j_cognitive_lift_rubric_prereg_schema.py tests/test_v3_8m_paired_cognitive_lift_evaluation_readiness.py
git diff --check
```

## Cannot Say

- `not_market_edge_verdict`
- `not_realized_pnl_verdict`
- `not_actual_30d_verdict`
- `not_forward_live_outcome_superiority`
- `not_public_science_proof`
- `not_trading_or_investment_advice`
- `not_superiority_over_direct_llm_as_clean_baseline`
