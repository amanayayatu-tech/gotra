# GOTRA v3.3a Judge Chain Audit and Decision Provenance

Date: 2026-06-20

Repo/root: `/Users/peachy/Documents/gotra`

Branch: `codex/gotra-v3-3a-judge-provenance-dryrun-20260620`

Base: `codex/baseline-v3-2-kimi-temperature-contract-20260620` at `14cd2ff`

Evidence layer: local engineering/provenance evidence only.

Non-claims: this is not provider/runtime health, not formal-lite, not OOS, not forward-live, not science/public proof, and not trading/investment advice.

## Route Boundary

The Kimi/GLM/DeepSeek provider API JSON parser/formal-lite rerun line is frozen as historical provider-runtime evidence. v3.3a does not continue provider parser hardening and does not run provider API canary, tiny smoke, or full formal-lite.

Historical `direct_llm` must be interpreted as `direct_llm_parametric_memory_control`, not as a clean no-future baseline. Modern LLM parameter memory cannot be cut off at `decision_date`; C1/C3/C5 and any return/MSE/direction metrics involving `direct_llm` are diagnostics for modern LLM parametric-memory control only. More credible historical alaya interpretation should prioritize `ksana_real_research` vs `full_gotra`, and clean baselines should move to deterministic price-only and/or forward-live/future-only validation.

Future `codex_cli_llm_backend` runs are a new experiment family, not equivalent to Kimi provider API results. Future result docs must record codex CLI version, model/reasoning setting, prompt hash, output transcript path, parsed decision hash, and run_id.

## Seven-Segment Chain Audit

| # | Segment | Verdict | Evidence | Notes |
|---|---|---|---|---|
| 1 | Gate candidate / prediction / feedback item enters `judge_agent` | `CODE_PRESENT` | `gotra/judge_agent/gate_poller.py:35-42`; `gotra/judge_agent/judge_agent.py:108-126`; `gotra/judge_agent/judge_agent.py:168-205` | Poller reads pending gates, Judge fetches one gate, builds context from gate payload, Alaya active/strong knowledge, local F/W/G/red-team artifacts, and Alaya predictions. v3.3a provenance now preserves `feedback_ref` when present in the gate payload, but live feedback-item ingress is still payload-level rather than a production outcome-feedback queue. |
| 2 | `judge_agent` makes a decision: approve/reject/defer/watch/quarantine candidate | `CODE_PRESENT` | `gotra/judge_agent/judge_agent.py:27-72`; `gotra/judge_agent/judge_agent.py:126-163` | Strict `JudgeDecision` validates `approve/reject/defer` and `knowledge_flag` values including `watch`, `strong_candidate`, and `quarantine_candidate`. The code routes `defer` and dry-run to no-op. |
| 3 | Decision routes to Alaya write path: approve_gate / reject_gate / quarantine / no-op | `MISSING` | `gotra/judge_agent/judge_agent.py:127-163`; `gotra/judge_agent/alaya_client.py:61-75`; `gotra/judge_agent/auto_quarantine.py:195-240` | `approve_gate`, `reject_gate`, and no-op are implemented. Direct Judge decision routing to `quarantine_knowledge` is not implemented; quarantine exists as a separate auto-quarantine pass after resolved predictions, not as a direct Judge `quarantine_candidate` action. |
| 4 | Approved knowledge status path toward active / strong_candidate / strong human gate | `DESIGN_ONLY` | `gotra/judge_agent/judge_agent.py:185-205`; `tests/test_judge_agent.py:275-290`; `docs/AUTONOMY_RUNBOOK.md:165-170` | Judge reads active/strong knowledge from Alaya and can persist `strong_candidate` as a candidate flag. It does not auto-promote strong knowledge. The active/strong human-gate lifecycle remains an Alaya/human-governed design boundary. |
| 5 | Later retrieval/use of knowledge or feedback in GOTRA/full_gotra prompt or decision context | `CODE_PRESENT` | `scripts/baseline_v3_four_arm.py:776-837`; `scripts/baseline_v3_four_arm.py:1772-1813`; `scripts/baseline_v3_four_arm.py:1849-1858` | `full_gotra` receives visible `alaya_feedback_history` and `decision_inputs` with `kind=alaya_feedback`; non-full arms are guarded against feedback leaks. Research artifacts and price context are prompt inputs per arm policy. |
| 6 | Resolved prediction outcome -> outcome-derived feedback artifact production path | `MISSING` | `gotra/judge_agent/auto_quarantine.py:195-240`; `scripts/baseline_v3_four_arm.py:980-1177`; `scripts/baseline_v3_four_arm.py:2751-2773` | The harness can load and consume `outcome_feedback` / `realized_error_feedback` fixtures, and it can self-generate `self_feedback` during a run. There is no production path that turns resolved predictions/outcomes into append-only true-independent feedback artifacts. This is the v3.3b blocker and is intentionally not implemented in v3.3a. |
| 7 | True independent feedback consumption path in v3 harness / full_gotra with leak guards | `CODE_PRESENT` | `scripts/baseline_v3_four_arm.py:1093-1177`; `scripts/baseline_v3_four_arm.py:1870-1937`; `scripts/baseline_v3_four_arm.py:3178-3182` | v3.2 consumes external feedback artifacts, rejects future/current-run/non-independent/duplicate/schema-invalid rows, computes strict eligibility, and reports H2 data status. This is a consumption substrate, not a production feedback loop. |

## v3.3a Implementation Summary

This layer adds append-only Judge decision provenance and `gate_poller --dry-run`.

Persisted provenance fields:

- `provenance_schema_version`
- `run_id`
- `gate_id`
- `decision`
- `confidence`
- `reason_code`
- `knowledge_flag`
- `audit_actor`
- `knowledge_id`
- `prediction_id`
- `feedback_ref`
- `apply`
- `dry_run`
- `routed_action`
- `alaya_write_attempted`
- `decision_timestamp_utc`
- `input_hash`
- `decision_hash`
- `gate_payload_hash`

Provenance is written only when `provenance_log_path` is configured. The JSONL is append-only and local; generated provenance logs are runtime artifacts and must not be committed.

Dry-run semantics:

- Polls pending gates normally.
- Calls `JudgeAgent.judge_gate(..., apply=False)`.
- Writes provenance if configured.
- Does not call Alaya approve/reject/quarantine write methods.
- CLI output explicitly labels dry-run/shadow mode.

Traceability check:

- `find_provenance_by_feedback_ref(path, feedback_ref)` resolves a mock `full_gotra`-style `feedback_ref` back to the Judge provenance record that produced or is linked to it.
- This is a local/mock join only. v3.3a does not produce real `outcome_feedback` / `realized_error_feedback`.

## Validation

Local validation completed:

- `uv run python -m py_compile gotra/judge_agent/judge_agent.py gotra/judge_agent/gate_poller.py scripts/gate_poller.py` -> PASS
- `uv run ruff check --no-cache gotra/judge_agent/judge_agent.py gotra/judge_agent/gate_poller.py scripts/gate_poller.py tests/test_judge_agent.py` -> PASS
- `uv run pytest -q tests/test_judge_agent.py` -> `11 passed`
- `uv run ruff check --no-cache gotra/judge_agent scripts/gate_poller.py tests` -> PASS
- `uv run pytest -q` -> `217 passed`
- `git diff --check` -> PASS

## Remaining Blockers

- v3.3b must implement production outcome-derived feedback artifact creation from resolved predictions/outcomes.
- v3.3c must implement temporal replay/future-only validation before any stronger research interpretation.
- Deterministic price-only or forward-live/future-only clean baselines remain required before treating historical LLM comparisons as clean evidence.
