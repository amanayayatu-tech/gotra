# GOTRA v3.6S Actual Maturity Monitor Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: engineering/local maturity monitoring only.

This stage adds a local command that rechecks actual forward-live capture
maturity before any future verdict planning. It does not run Kimi/GLM/DeepSeek
provider APIs, does not call the Codex CLI backend, does not run formal-lite,
does not score new LLM outputs, and does not produce a deterministic /
`full_gotra` / ksana winner verdict.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`, not a clean no-future baseline.

## Command

Script:

```bash
scripts/baseline_v3_6s_actual_maturity_monitor.py
```

Required behavior:

- Read one or more actual v3.5A capture roots or artifact roots.
  - A run root, `captures/` child, arm/layer artifact directory, or any local
    artifact directory must scan its own `**/*.json` contents and then filter by
    v3.5A capture schema.
- Count capture runs and capture decision artifacts.
- Check each capture artifact's `horizon_end_date` against
  `--as-of-timestamp-utc`.
- Missing or invalid `horizon_end_date` is a data blocker, not a normal
  not-matured state.
- Do not read or use outcome prices for immature captures.
- For matured captures, check whether decision and outcome prices are available
  under the existing v3.5B next-day daily-close availability rule.
  - Empty, malformed, or unreadable local price-cache files are `BLOCKED_DATA`
    blockers.
  - If any matured capture is missing decision or outcome price data, the
    monitor status is `BLOCKED_DATA`; a partial usable subset is not enough to
    declare resolver eligibility.
- Count source future-data contamination before declaring any resolver path
  eligible.
- Optionally read a v3.6 readiness summary and expose its status.
- Never execute v3.7 verdict logic. If readiness is
  `READY_FOR_FORWARD_LIVE_VERDICT`, only set
  `next_stage_planning_allowed=true` when the current monitor result is also
  resolver-path eligible and the readiness summary `input_roots` match the
  current monitored roots.

## Status Contract

Allowed monitor statuses:

- `DATA_INSUFFICIENT`: no capture artifacts were found.
- `DATA_NOT_MATURED`: capture artifacts exist, but no horizon has matured.
- `BLOCKED_DATA`: at least one horizon matured, but usable price data is missing.
  This also covers malformed capture horizon metadata and malformed local price
  caches.
- `BLOCKED_SOURCE_FUTURE_DATA`: source capture artifacts contain decision-side
  future-data contamination.
- `RESOLVER_PATH_ELIGIBLE`: at least one matured capture has usable prices and
  no source future-data contamination.
- `MONITOR_BLOCKED_RUN_ID_EXISTS`: output run id already exists.
- `MONITOR_FAIL`: unexpected invalid monitor state.

Summary fields include:

- `checked_capture_run_count`
- `not_matured_count`
- `matured_candidate_count`
- `matured_price_available_count`
- `resolved_count`
- `scored_count`
- `readiness_status`
- `readiness_summary_root_match`
- `next_check_after`
- `blocker_reasons`
- `provider_or_backend_called=false`
- `codex_cli_called=false`
- `formal_lite_entered=false`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`
- `next_stage_planning_allowed`
- `v3_7_verdict_executed=false`

## Verdict Boundary

v3.6S can only monitor maturity and readiness prerequisites.

If the status is `DATA_NOT_MATURED`, the next action is another maturity
recheck after `next_check_after`, not v3.7. If the status is `BLOCKED_DATA`,
the next action is price-data repair or waiting for price availability. If
readiness later becomes `READY_FOR_FORWARD_LIVE_VERDICT`, v3.6S can only mark
next-stage planning as allowed when current-root eligibility and readiness-root
matching both pass; a separate preregistered v3.7 stage is still required before
any verdict attempt.
