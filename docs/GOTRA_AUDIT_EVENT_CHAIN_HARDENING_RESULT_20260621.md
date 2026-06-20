# GOTRA Audit Event Chain Hardening Result

Date: 2026-06-21

## Project

- Project: GOTRA audit event chain hardening
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-audit-hardening-event-chain-20260621`
- Base main commit: `43594054e15aaa4315102b4ee3d9c3dfed5cb6e5`

## Evidence Layer

Audit engineering/local validation only.

This is not a provider run, not a Codex CLI backend experiment, not formal-lite,
not OOS, not science/public proof, and not trading or investment advice.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`; it is
not used in this audit hardening stage.

## Implementation Summary

Existing path audit:

- `gotra/backtest/audit.py` already validates historical backtest
  `event_log.jsonl` rows for actor/future-data checks, but those legacy rows
  were not hash-chained and are not rewritten by this stage.
- `gotra/judge_agent/judge_agent.py` was the active Judge decision provenance
  writer through `provenance_log_path`.
- `gotra/judge_agent/gate_poller.py` already supported dry-run/shadow
  evaluation and now benefits from chained provenance when a log path is
  configured.
- `integrations/alaya/sync_gates.py` and
  `gotra/judge_agent/auto_quarantine.py` are existing gate/knowledge materialize
  or quarantine surfaces; this PR does not add a new Alaya active/strong
  promotion endpoint.

Added `gotra/judge_agent/audit_chain.py`:

- canonical JSON hashing for audit events
- append-only JSONL hash chain with `prev_event_hash` and `event_hash`
- verifier summary with `legacy_unverified_count` and structured violations
- knowledge transition audit-event builder and validator

Updated `gotra/judge_agent/judge_agent.py`:

- Judge decision provenance now writes through the audit-chain appender
- records include `event_type=gate_decision`
- records include `previous_status`, `new_status`, `source_provenance_ids`, and
  `transition_audit_status`
- existing append-only JSONL behavior remains local and opt-in through
  `provenance_log_path`

Added `scripts/verify_audit_event_chain.py`:

- local verifier CLI
- exits `0` when the chain verifies
- exits non-zero when tamper/order/missing/duplicate/hash violations are found

## Verifier Coverage

Focused tests cover:

- valid append chain
- event body tampering
- event reorder
- missing event / broken prev pointer
- duplicate event hash
- legacy/unverified event reporting
- canonical hash stability independent of field order or whitespace

## Human Gate Negative Tests

Focused tests cover:

- `strong_candidate` cannot auto-promote to `strong`
- `reject` cannot activate knowledge
- `defer` cannot activate knowledge
- `quarantine_candidate` cannot activate knowledge
- active transition without source provenance is rejected
- transition missing required provenance is rejected before it can be marked
  audited/pass

Existing Judge tests continue to cover that `strong_candidate` does not call a
knowledge promotion method and that dry-run writes provenance without Alaya
writes.

## Chain Audit Status

Code present/local tested:

- gate decision audit-chain event writing
- event chain verifier
- knowledge transition audit-event validation
- local provenance reverse lookup by `feedback_ref`

Design/compatibility:

- legacy rows without `event_hash` remain readable and are counted as
  `legacy_unverified_count`
- knowledge transition audit events are local audit records, not a new Alaya
  active/strong write endpoint

Not implemented in this stage:

- provider/Codex CLI/formal-lite execution
- automatic strong knowledge promotion
- public/science/trading acceptance layer

## Validation

Local validation completed:

- `uv run python -m py_compile gotra/judge_agent/judge_agent.py gotra/judge_agent/audit_chain.py gotra/judge_agent/gate_poller.py scripts/verify_audit_event_chain.py` -> PASS
- `uv run ruff check --no-cache gotra/judge_agent/judge_agent.py gotra/judge_agent/audit_chain.py gotra/judge_agent/gate_poller.py scripts/verify_audit_event_chain.py tests/test_audit_event_chain.py tests/test_judge_agent.py` -> PASS
- `uv run pytest -q tests/test_audit_event_chain.py tests/test_judge_agent.py` -> `29 passed`
- local verifier mock validation -> `ok=true`, `event_count=2`, `verified_event_count=2`, `legacy_unverified_count=0`, `violation_count=0`
- `uv run pytest -q` -> `296 passed`
- `git diff --check` -> PASS

## Artifact Boundary

No provider, Codex CLI backend, formal-lite, OOS, or forward-live experiment was
run. Runtime JSONL files generated during local verifier validation are local
only and are not committed.

Forbidden artifacts remain excluded from the PR:

- `data/backtest/runs/**`
- `data/paper_trading/**`
- raw outputs/transcripts/provider raw
- `.env*`
- SQLite/DB files
- bundle/tar/zip files
- Stage8/Stage9 local artifacts
- README
