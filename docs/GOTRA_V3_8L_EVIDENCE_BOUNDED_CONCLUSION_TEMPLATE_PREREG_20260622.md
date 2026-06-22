# GOTRA v3.8L Evidence-Bounded Conclusion Template Prereg

## Scope

v3.8L defines a deterministic/local conclusion template and validator for layered evidence wording. It is fixture/local only and makes no new provider/backend calls.

Evidence layer: `engineering_internal_evidence_bounded_conclusion_template`.

## Goal

The validator binds the current engineering record from #66-#75 and checks that can-say / cannot-say / missing-before-superiority-verdict wording stays inside the available evidence layer.

The only success status is `EVIDENCE_BOUNDED_CONCLUSION_TEMPLATE_READY`.

## Canonical Sources

The validator requires these source-stage records in order:

| Stage | PR | Required status |
| --- | ---: | --- |
| v3.8B | #66 | `REAL_CONNECTION_AUTH_READY` |
| v3.8C | #67 | `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS` |
| v3.8D | #68 | `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS` |
| v3.8E | #69 | `REAL_TOKEN_FAILURE_MODE_SUITE_PASS` |
| v3.8F | #70 | `REAL_CONNECTION_EVIDENCE_DASHBOARD_READY` |
| v3.8G | #71 | `PROVIDER_CANARY_PREREG_READY` |
| v3.8H | #72 | `PROVIDER_CANARY_AUTHORIZATION_GATE_READY` |
| v3.8I | #73 | `END_TO_END_CONNECTIVITY_READY` |
| v3.8J | #74 | `COGNITIVE_LIFT_RUBRIC_PREREG_READY` |
| v3.8K | #75 | `COGNITIVE_LIFT_FIXTURE_DRY_RUN_READY` |

Each stage is bound to its canonical PR number, head SHA, merge commit, status, evidence layer, runtime flags, call/token metadata, and source-stage digest.

## Conclusion Layers

1. `Engineering Connectivity Conclusion`: may state bounded internal engineering evidence exists across connectivity, schema, provenance/hash, claim-boundary, usage metadata, and failure-handling stages.
2. `Cognitive-Lift Candidate Conclusion`: may state a future candidate evaluation path is defined by rubric and fixture tooling.
3. `Cognitive-Lift Superiority Verdict`: must remain `NOT_YET_VERDICT_READY`.

## Required Boundaries

- v3.8L itself: `real_calls_count=0`, `token_usage_total=0`, `provider_or_backend_called=false`, `provider_canary_executed=false`, `codex_cli_new_call=false`, `formal_lite_entered=false`.
- 30D gate: `actual_30d_readiness_status=DATA_NOT_MATURED`, `next_check_after=2026-07-21T00:00:00Z`, `v3_7_actual_verdict_executable=false`, `v3_7_actual_verdict_executed=false`.
- Historical direct arm: `direct_llm_interpretation=direct_llm_parametric_memory_control`; the `direct_llm_parametric_memory_control` arm is not a clean baseline.
- Raw boundary: `/tmp` only for local validation artifacts; repository contains no raw responses or transcripts.

## Blockers

Allowed blocking statuses:

- `BLOCKED_SCHEMA`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_DIRECT_LLM_BOUNDARY`
- `BLOCKED_MISSING_EVIDENCE_BOUNDARY`
- `BLOCKED_VERDICT_OVERREACH`

The validator must block missing or swapped source-stage evidence, unsafe runtime flags, raw or forbidden paths, direct-LLM boundary drift, and any wording that converts engineering evidence into a formal comparative conclusion.

## Non-Claims

This prereg is not a provider canary execution, not an actual 30D verdict, not a real-output evaluation, not an OOS/science/public/trading claim, and not investment or trading guidance.
