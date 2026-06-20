# GOTRA v3.5D Forward-Live Operating Loop Preregistration

Date: 2026-06-21

## Scope

Evidence layer: forward-live operating-loop engineering/local validation only.

This stage wires the v3.5A capture artifacts, v3.5B outcome resolver, and v3.5C
outcome scheduler into one local dry-run operating-loop entrypoint. It does not
call Kimi/GLM/DeepSeek provider APIs, does not call the Codex CLI backend, does
not run formal-lite or OOS, and does not make science/public, product
superiority, trading, or investment claims.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.5D must not use it to judge GOTRA, ksana, or alaya
prediction quality.

## Inputs

- Capture source: v3.5A forward-live capture run root or its `captures/` child.
- Outcome source: local price cache rows visible under the v3.5B next-day daily
  close availability rule.
- Scheduler source: v3.5C local scheduler logic.
- Output: ignored local run artifacts under the requested output directory.

No provider, LLM backend, transcript, raw output, or formal-lite artifact may be
created or required.

## Operating Loop Contract

The v3.5D entrypoint must:

1. Validate operating-loop run id and output collision before running.
2. Scan v3.5A capture artifacts through the v3.5C scheduler.
3. Let v3.5B resolver produce `NOT_MATURED`, `BLOCKED_DATA`,
   `BLOCKED_SOURCE_FUTURE_DATA`, or `RESOLVED` outcome artifacts.
4. Summarize capture -> scheduler -> resolver -> outcome provenance.
5. Preserve no-provider/no-Codex/no-formal-lite flags.
6. Avoid any win/loss or return verdict.

The unified summary must include:

- `operating_loop_run_id`
- `status`
- `outcome_scoring_status`
- `capture_count`
- `not_matured_count`
- `resolved_count`
- `blocked_data_count`
- `blocked_future_data_count`
- `duplicate_existing_count`
- `provenance_link_count`
- `audit_event_count`
- `scheduler_run_id`
- `resolver_run_ids`
- `source_capture_run_ids`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`

## Status Semantics

- `OPERATING_LOOP_PASS`: local engineering chain completed with no hard blocker.
  It may still have `NO_MATURED_OUTCOMES` or `DATA_BLOCKED_MISSING_PRICE`.
- `NO_MATURED_OUTCOMES`: no matured outcome exists yet; no scoring verdict is
  available.
- `RESOLVED_OUTCOMES_AVAILABLE_NO_VERDICT`: at least one outcome resolved, but
  this stage still does not produce a performance verdict.
- `DATA_BLOCKED_MISSING_PRICE`: matured outcomes exist but required prices are
  missing for one or more points.
- `BLOCKED_SOURCE_FUTURE_DATA`: source capture contamination was found; the CLI
  must exit non-zero.
- `BLOCKED_PROVENANCE`: required provenance links are incomplete; the CLI must
  exit non-zero.
- `OPERATING_LOOP_FAIL`: invalid inputs, empty capture grid, scheduler errors,
  or other unexpected blockers.

## Provenance

For each current scheduler/resolver outcome artifact, the operating-loop summary
must allow reverse lookup to:

- source capture run id
- source capture decision artifact
- scheduler run id
- scheduler summary path
- resolver run id
- outcome artifact path

Audit event chain is not connected in v3.5D because the operating loop writes
ignored local run artifacts and does not perform a Judge/Gate knowledge
transition. The summary must set `audit_event_count=0` and explain the
not-connected status. Audit-chain integration can be a later scoped stage if
this loop becomes part of the live control plane.

## Acceptance

Local acceptance requires:

- py_compile and ruff pass for the new script and focused tests.
- Focused operating-loop tests cover matured, not-matured, missing-price,
  idempotency, provenance, source future-data block, empty capture, run-id
  collision, and no-provider/no-Codex/no-formal-lite flags.
- v3.5A/v3.5B/v3.5C regression tests pass.
- A local dry-run validation writes output only to `/tmp` or ignored paths.
- No `data/backtest/runs/**`, `data/paper_trading/**`, raw outputs,
  transcripts, `.env*`, DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or
  README changes are committed.
