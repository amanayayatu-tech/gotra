# GOTRA Audit Event Chain Hardening Prereg

Date: 2026-06-21

Repo/root: `/Users/peachy/Documents/gotra`

Branch: `codex/gotra-audit-hardening-event-chain-20260621`

Base: `main` at `43594054e15aaa4315102b4ee3d9c3dfed5cb6e5`

## Scope

Goal: harden GOTRA Judge/Gate audit engineering so gate decisions and knowledge
transition records can be verified as an append-only event chain.

Evidence layer: audit engineering/local validation only.

Non-claims: this is not a provider run, not a Codex CLI backend experiment, not
formal-lite, not OOS, not science/public proof, and not trading or investment
advice.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. This audit layer does not use `direct_llm` for any
experiment interpretation.

## Event Chain Contract

Current code-path audit before changes:

- `gotra/backtest/audit.py` reads historical backtest `event_log.jsonl` and
  checks actor/future-data invariants, but historical rows are not hash-chained.
- `gotra/judge_agent/judge_agent.py` writes Judge decision provenance JSONL
  when `provenance_log_path` is configured.
- `gotra/judge_agent/gate_poller.py` calls the Judge path and supports
  dry-run/shadow evaluation.
- `integrations/alaya/sync_gates.py` materializes resolved Alaya gates into
  local ksana result files.
- `gotra/judge_agent/auto_quarantine.py` can quarantine knowledge after
  resolved predictions, but it is a separate pass and not a direct Judge
  decision route.

This stage hardens newly written Judge/Gate audit events. It does not rewrite
historical backtest event logs or generated artifacts.

New audit events must include:

- `audit_chain_schema_version`
- `event_type`
- `audit_actor`
- `event_timestamp_utc`
- `prev_event_hash`
- `event_hash`

`event_hash` is SHA-256 over canonical JSON:

- UTF-8 JSON
- sorted keys
- compact separators
- `event_hash` excluded from the hashed payload
- `prev_event_hash` included so ordering is bound into the digest

`prev_event_hash` points to the previous verified event in the same JSONL
ledger. The first hashed event uses `null` as the genesis pointer. Legacy rows
without `event_hash` are read-compatible but reported as
`legacy_unverified_count`; they are not silently treated as verified.

## Verifier Requirements

The local verifier must emit structured JSON with:

- `ok`
- `event_count`
- `verified_event_count`
- `legacy_unverified_count`
- `violation_count`
- `violations`

It must detect:

- event body tampering through `invalid_hash`
- reordered events through `broken_prev_event_hash`
- missing events or broken prev pointers through `broken_prev_event_hash`
- duplicate event hashes through `duplicate_event_hash`
- malformed JSON through `invalid_json`
- legacy rows through `legacy_unverified_count`

## Gate / Knowledge Transition Coverage

Gate decision provenance is written by `JudgeAgent` when
`provenance_log_path` is configured. It must now be part of the same audit
event chain and include:

- `event_type=gate_decision`
- `audit_actor`
- `gate_id`
- `decision`
- `confidence`
- `reason_code`
- `knowledge_flag`
- `knowledge_id`
- `prediction_id`
- `feedback_ref`
- `previous_status`
- `new_status`
- `source_provenance_ids`
- `input_hash`
- `decision_hash`
- `gate_payload_hash`

Knowledge transition events are local audit events. They do not create a new
Alaya active/strong write path. They must record:

- `event_type=knowledge_transition`
- `audit_actor`
- `gate_id`
- `decision`
- `confidence`
- `reason_code`
- `knowledge_flag`
- `knowledge_id`
- `previous_status`
- `new_status`
- `prediction_id` and/or `feedback_ref` when present
- `source_provenance_ids`

## Human Gate Negative Contract

The audit layer must reject or block these transitions:

- `strong_candidate` cannot auto-promote to `strong` or `active_strong`
- `reject` and `defer` cannot activate knowledge
- `quarantine_candidate` cannot activate knowledge
- active/strong-style transitions require source provenance
- missing required transition provenance cannot be marked audited/pass

Strong knowledge remains human-gated. This stage does not invent a new Alaya
active or strong promotion endpoint.

## Artifact Boundary

Allowed PR files:

- audit-chain code
- verifier CLI
- focused tests
- audit-hardening docs

Forbidden PR files:

- `data/backtest/runs/**`
- `data/paper_trading/**`
- raw outputs/transcripts/provider raw
- `.env*`
- SQLite/DB files
- bundle/tar/zip files
- Stage8/Stage9 local artifacts
- README
