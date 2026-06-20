# GOTRA v3.3b Outcome-Derived Feedback Production

Date: 2026-06-20

Branch: `codex/gotra-v3-3b-outcome-feedback-production-20260620`

Base: PR #16 branch `codex/gotra-v3-3a-judge-provenance-dryrun-20260620`

## Evidence Layer

This change is local engineering and mock closed-loop evidence only.

It is not provider/runtime health evidence, not formal-lite acceptance, not OOS,
not forward-live, not a science/public claim, and not trading or investment
advice.

The historical `direct_llm` arm remains a
`direct_llm_parametric_memory_control` diagnostic arm. It is not a clean
no-future baseline because modern LLM parameter memory cannot be cut off at a
historical `decision_date`.

## Relation To v3.3a Audit

v3.3a recorded the 7-segment cognitive compounding chain audit. Segment 6,
resolved prediction outcome to `outcome_feedback` / `realized_error_feedback`
production, was missing.

v3.3b moves segment 6 to `CODE_PRESENT` and `LOCAL_TESTED` for local,
append-only production artifact generation. It does not claim live Alaya
deployment, temporal replay, provider execution, or formal-lite completion.

Segment 4, approved knowledge lifecycle toward active or strong status, remains
`DESIGN_ONLY / NOT_IMPLEMENTED_IN_V3_3B` for active status writes. Strong
knowledge still requires human-gated promotion and is not auto-promoted.

## Producer Summary

New module: `gotra/judge_agent/outcome_feedback.py`

The producer converts resolved prediction records into strict v3-compatible
feedback artifacts without provider calls, secrets, or network access.

Output source kinds:

- `outcome_feedback`
- `realized_error_feedback`

Required v3 compatibility fields emitted:

- `ticker`
- `input_layer`
- `feedback_ref`
- `feedback_source_kind`
- `availability_date`
- `source_run_id`
- `source_step_id`
- `source_decision_date`
- `source_horizon_end_date`
- `actual_return`
- `prior_prediction`

Additional provenance fields emitted:

- `producer_schema_version`
- `source_prediction_id`
- `source_gate_id`
- `source_knowledge_id`
- `judge_provenance_ref`
- `judge_decision_hash`
- `generated_at_utc`
- `provenance_hash`
- `error`
- `mse`
- `summary`

Stable feedback refs use:

`outcome:{ticker}:{input_layer}:{source_decision_date}:{source_prediction_id}`

Safety gates:

- unresolved predictions are rejected
- missing required schema fields are rejected
- non-finite numeric values are rejected
- inconsistent caller-provided `error` or `mse` is rejected
- forbidden future/current fields are rejected
- invalid temporal order is rejected
- current-run feedback is rejected when `source_run_id == current_run_id`
- duplicate `feedback_ref` rows are deduplicated

Append-only support:

- `write_feedback_artifacts_jsonl(..., append=True)` appends JSONL records
- `append=False` uses exclusive creation and fails if the target already exists
- generated runtime artifacts are test-local and are not committed

## Closed-Loop Mock Result

Test: `tests/test_outcome_feedback.py::test_closed_loop_mock_run_consumes_generated_outcome_feedback`

Mock flow:

1. Generate three prior-run resolved prediction records for AAPL across at least
   two mature prior waves.
2. Produce local `outcome_feedback` / `realized_error_feedback` JSONL artifacts.
3. Feed those artifacts into the existing v3 feedback fixture loader and strict
   feedback filter without changing the consumer threshold.
4. Run the v3 mock harness with no provider HTTP.
5. Verify a later `full_gotra` point receives eligible independent feedback and
   the summary reports true-independent eligibility.

Observed local test result:

- summary status: `MOCK_PASS`
- provider call status: `no real provider HTTP call`
- `true_independent_feedback_eligible_points > 0`
- `h2_data_status = STRICT_FEEDBACK_ELIGIBLE_PRESENT`
- `feedback_source_leak_count = 0`
- later `full_gotra` step has `true_independent_feedback_eligible = true`
- feedback trace reaches source prediction ids `pred-wave-1`,
  `pred-wave-2`, and `pred-wave-3`

This is engineering evidence that generated artifacts can satisfy the existing
strict v3 consumer filter. It is not formal-lite or strategy evidence.

## Provenance Hardening

File: `gotra/judge_agent/judge_agent.py`

v3.3b also hardens a narrow v3.3a provenance gap. If `approve_gate` or
`reject_gate` raises after a Judge decision is made, the decision provenance is
now persisted before re-raising the original exception.

Persisted failure metadata:

- `routed_action_status = failed`
- `alaya_write_attempted = true`
- `alaya_write_error_class`
- sanitized `alaya_write_error_message`

Successful apply paths record `routed_action_status = succeeded`.

Dry-run/defer behavior remains no-write and unchanged.

## Active Status Write Audit

Audited files:

- `gotra/judge_agent/alaya_client.py`
- `gotra/judge_agent/auto_quarantine.py`
- current judge/gate-poller paths

Result:

No safe existing client method was found for approved knowledge to active
candidate status. v3.3b therefore does not fabricate an Alaya active write path.
This remains `DESIGN_ONLY / NOT_IMPLEMENTED_IN_V3_3B`.

## Validation

Commands run:

```bash
uv run python -m py_compile gotra/judge_agent/judge_agent.py gotra/judge_agent/outcome_feedback.py
uv run ruff check --no-cache gotra/judge_agent scripts tests
uv run pytest -q tests/test_outcome_feedback.py tests/test_judge_agent.py
uv run pytest -q
```

Results:

- py_compile: pass
- ruff: pass
- focused pytest: `19 passed`
- full pytest: `225 passed`

## Artifact Boundary

Committed files are limited to code, tests, and this documentation.

Not committed:

- provider raw responses
- provider/API run artifacts
- `data/backtest/runs/*`
- `.env*` or secrets
- DB, bundle, tar, or zip files
- `data/paper_trading/*`
- Stage8/Stage9 artifacts
- generated feedback runtime JSONL from tests

The provider-json WIP from the older v3.2 line remains isolated in stash
`stash@{0}` and is not part of v3.3b.

## Next Action

Proceed to v3.3c temporal replay and calibration after review. Do not return to
provider parser/formal-lite reruns as the main line for this phase.
