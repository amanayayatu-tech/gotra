# GOTRA v3.6AI Ksana Cognitive-Lift Audit Result

Date: 2026-06-21

## Scope

This PR adds a deterministic/local ksana cognitive-lift audit. It is
`engineering/local cognitive-lift audit only`.

Runtime boundary: no Kimi, GLM, DeepSeek, provider APIs, Codex CLI backend, new
LLM calls, or formal-lite.

Claim boundary: not OOS/science/public/trading claim and not investment advice.
It does not execute a 30D forward-live verdict and keeps `v3_7_allowed=false`.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is not
a clean no-future baseline.

## Files Changed

- `scripts/baseline_v3_6ai_ksana_cognitive_lift_audit.py`
- `tests/test_ksana_cognitive_lift_audit.py`
- `docs/GOTRA_V3_6AI_KSANA_COGNITIVE_LIFT_AUDIT_PREREG_20260621.md`
- `docs/GOTRA_V3_6AI_KSANA_COGNITIVE_LIFT_AUDIT_RESULT_20260621.md`

## Source Chain Audit

Current GOTRA ksana/research input plumbing is:

- Source artifact or fixture:
  public ksana/research packet JSON.
- Public adapter:
  `gotra/ksana_public_adapter.py::adapt_ksana_public_research_artifacts`.
- Harness adapter entry:
  `scripts/baseline_v3_four_arm.py::filter_external_research_artifacts`.
- Prompt payload:
  `scripts/baseline_v3_four_arm.py::research_artifact_filter_result` and
  `build_prompt_payload`.
- Prompt serialization:
  `scripts/baseline_v3_four_arm.py::render_provider_prompt`.

The current harness consumes normalized research artifact fields, including
`summary`, `text`, `citations`, `evidence`, `claims`, `features`,
`availability_date`, `source_kind`, `source_run_id`, `source_artifact_path`, and
`provenance_hash`.

The fields that matter for cognitive lift but are not first-class GOTRA consumed
fields yet include ranked `hypotheses`, `counterfactuals`,
`falsification_triggers`, `expected_observable_evidence`,
`disagreement_with_price_only`, `evidence_gaps`, and
`uncertainty_decomposition`.

## Analyzer

New entrypoint:

```bash
uv run python scripts/baseline_v3_6ai_ksana_cognitive_lift_audit.py \
  --manifest /path/to/manifest.json \
  --audit-run-id baseline_v3_6ai_ksana_cognitive_lift_audit_<timestamp> \
  --output-dir /tmp/gotra_v3_6ai_ksana_cognitive_lift_audit/runs
```

The analyzer writes structured `summary.json` and `manifest.json` under the
requested output directory. Runtime output is not committed.

## Local Mock Validation

Run id:
`baseline_v3_6ai_ksana_cognitive_lift_audit_mock_20260621T112931Z`

Summary path:
`/tmp/gotra_v3_6ai_ksana_cognitive_lift_audit/runs/baseline_v3_6ai_ksana_cognitive_lift_audit_mock_20260621T112931Z/summary.json`

Summary sha256:
`f55540686450e2a1658b5a2761c29222004ba682aac64270647767f7cd67029f`

Summary status:

- `overall_status=COGNITIVE_LIFT_READY_FOR_FIXTURE_COMPARISON`
- `information_gain_status=SUFFICIENT_FOR_FIXTURE_COMPARISON`
- `cognitive_lift_status=COGNITIVE_LIFT_READY_FOR_FIXTURE_COMPARISON`
- `input_artifact_count=1`
- `hypothesis_count=2`
- `counterfactual_count=2`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`

This READY status is fixture-level only. It does not mean true 30D forward-live
readiness, does not authorize v3.7, and does not make a GOTRA/ksana/alaya
superiority conclusion.

## Test Coverage

Focused tests cover:

- conservative / generic caution-heavy report -> `LOW_INFORMATION_GAIN`
- forced hypothesis and counterfactual schema fixture -> fixture comparison ready
- missing provenance -> `BLOCKED_PROVENANCE`
- missing or invalid required schema field -> `BLOCKED_SCHEMA`
- boundary-overclaim wording -> `BLOCKED_OVERCLAIM`
- `direct_llm_parametric_memory_control` clean-baseline misuse -> blocked
- `direct_llm_parametric_memory_control` boundary -> accepted
- no provider, no new Codex CLI, no formal-lite, and `v3_7_allowed=false`
- READY status remains fixture-level and does not emit a verdict or winner field

## Boundary

No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, or local runtime artifacts are committed by
this PR.

## Next Action

If this PR merges later, the next safe action is to use the v3.6AI contract for
fixture-level research packet comparison or upstream packet optimization. The
30D path remains gated by actual forward-live readiness; v3.7 remains disallowed
until true actual readiness returns `READY_FOR_FORWARD_LIVE_VERDICT` with
matching provenance.
