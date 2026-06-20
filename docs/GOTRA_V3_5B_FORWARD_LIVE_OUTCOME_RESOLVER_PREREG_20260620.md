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
- `RESOLVED`: horizon is mature and both decision price and allowed outcome price are available.

The resolver must not call LLMs, provider APIs, Codex CLI, or formal-lite harnesses.

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

The default `outcome_window_days` is 7 calendar days. If no price row exists inside that bounded window, the record is `BLOCKED_DATA`.

## Future-Data Guard

The resolver must:

- Not resolve if `as_of_date < horizon_end_date`.
- Not use price rows after `as_of_date`.
- Not use price rows after the allowed outcome window.
- Not fabricate missing prices.
- Not populate `outcome_price`, `actual_change_pct`, or `actual_direction` for `NOT_MATURED` or `BLOCKED_DATA`.

`NOT_MATURED` and `BLOCKED_DATA` records may carry decision-side metadata and provenance, but not realized outcome fields.

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
- `RESOLVED` count
- future-data violation count
- provider/backend called: false
- Codex CLI called: false
- formal-lite entered: false
- provenance reverse lookup status

## Non-Claims

v3.5B only resolves maturity/data status. It does not prove prediction quality, OOS performance, scientific/public claims, product superiority, or trading value.
