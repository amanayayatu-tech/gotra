# GOTRA v3.5B Forward-Live Outcome Resolver Prereg

Date: 2026-06-20

## Scope

v3.5B implements a local forward-live outcome resolver / maturity watcher for already-captured v3.5A future-only decision artifacts.

Evidence layer: local engineering validation only.

This is not a provider/API run, not a Codex CLI experiment, not a formal-lite run, not an OOS pass, not science/public proof, and not trading or investment advice.

## Goal

The resolver reads existing forward-live capture artifacts and price cache data, then classifies each captured decision by maturity and data availability:

- `NOT_MATURED`: `as_of_date` is before `horizon_end_date`; no outcome fields are populated.
- `BLOCKED_DATA`: horizon is mature but required decision/outcome price data is missing within the preregistered outcome window.
- `BLOCKED_SOURCE_FUTURE_DATA`: source capture artifact is already contaminated by decision-side future-data leakage, such as `future_data_violation: true` or `latest_visible_price_date` after the capture-time allowed visible date.
- `RESOLVED`: horizon is mature and both decision price and allowed outcome price are available.

The resolver must not call LLMs, provider APIs, Codex CLI, or formal-lite harnesses. Blocked resolver runs, including reused resolver run ids, must exit non-zero from the CLI so automation cannot treat a no-op blocker as success.

## Inputs

The resolver supports:

- `--capture-run-dir`
- `--resolver-run-id`
- `--as-of-timestamp-utc`
- `--price-dir`
- `--output-dir`
- `--outcome-window-days`
- `--allow-overwrite`

Captured decision artifacts are expected to come from the v3.5A forward-live capture path and include `decision_date_local`, `horizon_days`, `horizon_end_date`, `ticker`, `arm`, `input_layer`, `run_id`, and source price metadata such as `latest_visible_price_date`.

## Outcome Price Rule

For matured decisions, v3.5B selects the first valid price date on or after `horizon_end_date` and on or before both:

- `as_of_date`
- `horizon_end_date + outcome_window_days`

Daily close availability rule: a daily price row for date D is only visible at D+1 `00:00:00Z` or later. For example, `2026-07-20` close is not usable at `2026-07-20T00:00:00Z`; it becomes usable at `2026-07-21T00:00:00Z`.

The default `outcome_window_days` is 7 calendar days. If no price row exists inside that bounded window, the record is `BLOCKED_DATA`.

## Future-Data Guard

The resolver must:

- Not resolve if `as_of_date < horizon_end_date`.
- Not use price rows after the latest daily close visible at `as_of_timestamp_utc`.
- Not use price rows after the allowed outcome window.
- Not resolve source artifacts with `future_data_violation: true`.
- Not resolve source artifacts whose `latest_visible_price_date` is after the capture-time allowed visible date.
- Not fabricate missing prices.
- Not populate `outcome_price`, `actual_change_pct`, or `actual_direction` for `NOT_MATURED`, `BLOCKED_DATA`, or `BLOCKED_SOURCE_FUTURE_DATA`.

`NOT_MATURED`, `BLOCKED_DATA`, and `BLOCKED_SOURCE_FUTURE_DATA` records may carry decision-side metadata and provenance, but not realized outcome fields.

`actual_direction` must use the v3 direction bucket contract:

- `actual_change_pct >= +2.0`: `long`
- `actual_change_pct <= -2.0`: `avoid`
- otherwise: `neutral`

## Outcome Artifact Schema

Each resolver record must include at least:

- `schema`
- `resolver_run_id`
- `source_run_id`
- `source_decision_id`
- `source_decision_artifact`
- `ticker`
- `decision_date`
- `horizon_days`
- `horizon_end_date`
- `outcome_status`
- `outcome_price_date`
- `decision_price`
- `outcome_price`
- `actual_change_pct`
- `actual_direction`
- `resolved_at`
- `provenance`

## Provenance

Provenance must support reverse lookup to the original capture:

- source capture run id
- source decision id
- source artifact path/ref
- resolver run id
- resolver schema/script version
- price source path
- price row dates used
- no-future-data decision explaining why selected outcome price is allowed

## Summary Requirements

The resolver summary must report:

- capture artifact count
- `NOT_MATURED` count
- `BLOCKED_DATA` count
- `BLOCKED_SOURCE_FUTURE_DATA` count
- `RESOLVED` count
- source future-data violation count
- future-data violation count
- provider/backend called: false
- Codex CLI called: false
- formal-lite entered: false
- provenance reverse lookup status

## Non-Claims

v3.5B only resolves maturity/data status. It does not prove prediction quality, OOS performance, scientific/public claims, product superiority, or trading value.
