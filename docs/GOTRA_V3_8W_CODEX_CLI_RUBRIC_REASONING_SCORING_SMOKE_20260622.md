# GOTRA v3.8W Codex CLI Rubric Reasoning Scoring Smoke

## Result

Status: `PASS`

Evidence layer: `smoke_evidence_codex_cli_llm_api_rubric_reasoning_scoring`.

This artifact is repo-facing metadata only. Runtime response files stay under
`/tmp/gotra_rubric_reasoning_quality/**`; this document records only hashes,
counts, status, and paths to summary metadata.

## Runtime Boundary

- `authorized_llm_path=codex_cli_llm_api`
- `allowed_command_family=codex exec`
- `cost_cap_usd=500.00`
- `token_budget_hard_cap=1000000000`
- `token_budget_policy=hard_cap_not_target`
- `raw_output_boundary=/tmp/gotra_rubric_reasoning_quality/** only`
- `repo_raw_artifacts=[]`
- `no_raw_repo=true`
- `no_github_push=true`
- `no_actual_30d_verdict=true`

## Preserved Verdict Boundary

- `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `v3_7_actual_verdict_executable=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `direct_llm_clean_baseline=false`

## Smoke Summary

- `real_calls_count=2`
- `token_usage_total=52302`
- `usage_metadata_available=true`
- `cost_observed_usd=null`
- `cost_cap_usd=500.00`
- `latency_summary_ms.min=9210`
- `latency_summary_ms.median=11784`
- `latency_summary_ms.max=14358`
- `bounded_synthetic_batch_executed=true`
- `bounded_batch_scope=synthetic/local two-record rubric fixture`

Per-run metadata:

| summary | run_mode | run_scope | bounded_batch_executed |
| --- | --- | --- | --- |
| `gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260623T011609Z` | `smoke` | `minimal_codex_cli_json_smoke` | `false` |
| `gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260623T011705Z` | `synthetic_batch` | `synthetic/local two-record rubric fixture` | `true` |

Summary artifacts:

- `/tmp/gotra_rubric_reasoning_quality/summaries/gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260623T011609Z/summary.json`
- `/tmp/gotra_rubric_reasoning_quality/summaries/gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260623T011705Z/summary.json`

Manifest artifacts:

- `/tmp/gotra_rubric_reasoning_quality/summaries/gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260623T011609Z/manifest.json`
- `/tmp/gotra_rubric_reasoning_quality/summaries/gotra_v3_8w_codex_cli_rubric_reasoning_scoring_smoke_20260623T011705Z/manifest.json`

Runtime file hashes:

- `/tmp/gotra_rubric_reasoning_quality/codex_cli_smoke/v3_8w_20260623T011609Z/stream.jsonl`: `b99d61f411d2ba2fe1c1bb8cc42432cf1248d822e4ce9322eadbff69e94a2eb2`
- `/tmp/gotra_rubric_reasoning_quality/codex_cli_smoke/v3_8w_20260623T011609Z/last_message.txt`: `23e39f6d809c907cc6724740967e3ddba1014401f972fa69b135db4a21dd64f1`
- `/tmp/gotra_rubric_reasoning_quality/codex_cli_smoke/v3_8w_20260623T011609Z/stderr.txt`: `ceac758e75de2ad8d0ebe08c01278e727284b5015c844285ae8cc77f03416599`
- `/tmp/gotra_rubric_reasoning_quality/codex_cli_batch/v3_8w_20260623T011705Z/stream.jsonl`: `747eedd8d2e501d29589c2e873f63bcabc2cf7665fb2918f8706b3968c979196`
- `/tmp/gotra_rubric_reasoning_quality/codex_cli_batch/v3_8w_20260623T011705Z/last_message.txt`: `aad4614a67174905911b3f1861ed746744a3c976f3de719d60fcebb5989aade6`
- `/tmp/gotra_rubric_reasoning_quality/codex_cli_batch/v3_8w_20260623T011705Z/stderr.txt`: `06a8d770bdf1bf08ef2ae00243646c1c5387a52afef8a7ad2ffc64529c0735c3`

## Validation Commands

```bash
codex-gotra-gate --cwd /Users/peachy/Documents/gotra
uv run python -m py_compile scripts/baseline_v3_8w_codex_cli_rubric_reasoning_scoring_smoke.py
uv run ruff check scripts tests
uv run pytest tests/test_v3_8w_codex_cli_rubric_reasoning_scoring_smoke.py
git diff --check
```

## Cannot Say

- `not_bounded_reasoning_quality_verdict`
- `not_actual_30d_verdict`
- `not_forward_live_outcome_superiority`
- `not_realized_pnl_verdict`
- `not_public_science_proof`
- `not_trading_or_investment_advice`
- `not_superiority_over_direct_llm_as_clean_baseline`
