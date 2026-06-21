# GOTRA v3.6AJ Cognitive-Lift Fixture Comparison Result

Date: 2026-06-21

## Scope

This PR adds a deterministic/local fixture comparison harness for the v3.6AI
cognitive-lift packet contract. It is
`engineering/local cognitive-lift fixture comparison only`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary: not OOS/science/public/trading claim and not investment advice.
This stage does not execute a 30D forward-live verdict and keeps
`v3_7_allowed=false`.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_6aj_cognitive_lift_fixture_comparison.py`
- `tests/test_cognitive_lift_fixture_comparison.py`
- `docs/GOTRA_V3_6AJ_COGNITIVE_LIFT_FIXTURE_COMPARISON_PREREG_20260621.md`
- `docs/GOTRA_V3_6AJ_COGNITIVE_LIFT_FIXTURE_COMPARISON_RESULT_20260621.md`

## Harness

New entrypoint:

```bash
uv run python scripts/baseline_v3_6aj_cognitive_lift_fixture_comparison.py \
  --baseline-manifest /path/to/baseline_manifest.json \
  --candidate-manifest /path/to/candidate_manifest.json \
  --comparison-run-id baseline_v3_6aj_cognitive_lift_fixture_comparison_<timestamp> \
  --output-dir /tmp/gotra_v3_6aj_cognitive_lift_fixture_comparison/runs
```

The harness calls the v3.6AI analyzer separately for baseline and candidate
fixtures, then compares structural front-half metrics. Runtime output is written
to `/tmp` or a caller-supplied ignored output root and is not committed.

## Local Mock Validation

Run id:
`baseline_v3_6aj_cognitive_lift_fixture_comparison_mock_20260621T114338Z`

Summary path:
`/tmp/gotra_v3_6aj_cognitive_lift_fixture_comparison/runs/baseline_v3_6aj_cognitive_lift_fixture_comparison_mock_20260621T114338Z/summary.json`

Summary sha256:
`087f2354b5f4acfa08150ce3e9dc579bc4c36b4b08eef0b0e2067a23658e11bf`

Summary status:

- `comparison_status=COGNITIVE_LIFT_FIXTURE_IMPROVED`
- `baseline_information_gain_status=LOW_INFORMATION_GAIN`
- `candidate_information_gain_status=SUFFICIENT_FOR_FIXTURE_COMPARISON`
- `delta_ranked_hypothesis_count=1`
- `delta_counterfactual_count=2`
- `delta_falsifiable_trigger_count=2`
- `delta_generic_caution_phrase_count=-6`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`

This status is fixture-level structural comparison only. It does not score real
outcomes, does not authorize v3.7, and does not make a GOTRA/ksana/alaya
superiority conclusion.

## Test Coverage

Focused tests cover:

- conservative baseline plus structured candidate -> fixture structural
  improvement
- contract-compliant baseline and candidate -> fixture comparison ready
- malformed candidate -> `BLOCKED_SCHEMA`
- missing provenance -> `BLOCKED_PROVENANCE`
- boundary-overclaim wording -> `BLOCKED_OVERCLAIM`
- `direct_llm_parametric_memory_control` clean-baseline misuse -> blocked
- `direct_llm_parametric_memory_control` boundary -> accepted
- low-information candidate -> `LOW_INFORMATION_GAIN_CANDIDATE`
- no provider, no new Codex CLI, no formal-lite, and `v3_7_allowed=false`

## Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

## Next Action

If this PR merges later, the next safe step is to use fixture-level deltas for
front-half research packet design. A real canary/provider capture must be
separately authorized by the user and must include full metadata. The 30D path
remains gated by actual forward-live readiness; v3.7 remains disallowed until
true actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching
provenance.
