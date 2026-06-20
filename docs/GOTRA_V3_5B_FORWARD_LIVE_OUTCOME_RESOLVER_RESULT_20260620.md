# GOTRA v3.5B Forward-Live Outcome Resolver Result

Date: 2026-06-20

## Project

- Project: GOTRA v3.5B forward-live outcome resolver / maturity watcher
- Repo/root: `/Users/peachy/Documents/gotra`
- Branch: `codex/gotra-v3-5b-forward-live-outcome-resolver-20260620`
- Base: `origin/main` at `07ee4908a537cc5dea00cf902c4d8f8eac7570e4`

## Evidence Layer

Engineering/local validation for forward-live outcome maturity resolution only.

This run did not call provider APIs, did not call the Codex CLI backend, did not enter formal-lite, and does not make OOS, science/public proof, product superiority, trading, or investment claims.

## Implementation Summary

Added a standalone local resolver:

- Script: `scripts/baseline_v3_5_forward_live_outcome_resolver.py`
- Prereg/design: `docs/GOTRA_V3_5B_FORWARD_LIVE_OUTCOME_RESOLVER_PREREG_20260620.md`
- Tests: `tests/test_forward_live_outcome_resolver.py`

The resolver reads v3.5A forward-live capture artifacts and price cache files, then classifies each captured decision:

- `NOT_MATURED`: `as_of_date < horizon_end_date`; realized outcome fields are withheld.
- `BLOCKED_DATA`: horizon is mature but decision or bounded outcome price data is missing.
- `BLOCKED_SOURCE_FUTURE_DATA`: source capture artifact is contaminated by decision-side future-data leakage.
- `RESOLVED`: horizon is mature and both decision price plus allowed outcome price are available.

The resolver uses the first valid price row on or after `horizon_end_date`, bounded by both `as_of_date`, next-day daily-close availability, and `horizon_end_date + outcome_window_days`. It writes append-only resolver artifacts under the selected output directory and records provenance back to the source capture artifact.

## PR Review Hardening

This update addresses the PR #27 active P2 review comments:

- Source capture future-data contamination is propagated into resolver artifacts and summary fields. Contaminated source artifacts are blocked as `BLOCKED_SOURCE_FUTURE_DATA`; `OUTCOME_RESOLVER_PASS` requires `source_future_data_violation_count == 0`.
- CLI exit semantics now return non-zero for `BLOCKED_RUN_ID_EXISTS` and other non-pass terminal statuses.
- Daily close rows use a conservative availability rule: row D is visible only at D+1 `00:00:00Z` or later. Same-day close cannot be used at the start of that UTC date.
- `actual_direction` now follows the v3 bucket contract: `long` for `>= +2.0%`, `avoid` for `<= -2.0%`, otherwise `neutral`.

## Local Resolver Validation

Local run id:

`baseline_v3_5b_outcome_resolver_review_fix_20260620T154803Z`

Validation used synthetic temporary capture and price fixtures under `/tmp`, not committed artifacts.

Summary:

| Field | Value |
|---|---:|
| status | `OUTCOME_RESOLVER_PASS` |
| capture_artifact_count | 4 |
| resolved_count | 1 |
| blocked_data_count | 2 |
| blocked_source_future_data_count | 0 |
| not_matured_count | 1 |
| source_future_data_violation_count | 0 |
| future_data_violation_count | 0 |
| resolver_error_count | 0 |
| provenance_reverse_lookup_status | `PASS` |
| provider_or_backend_called | `false` |
| codex_cli_called | `false` |
| formal_lite_entered | `false` |

Outcome status coverage:

- `RESOLVED`: available decision price and allowed outcome price.
- `BLOCKED_DATA`: missing outcome price, plus a price row outside the allowed outcome window.
- `NOT_MATURED`: `as_of_date` before `horizon_end_date`, with no realized outcome fields populated.
- `BLOCKED_SOURCE_FUTURE_DATA`: covered by focused tests for both `future_data_violation: true` and `latest_visible_price_date` beyond the capture-time allowed visible date.

## Future-Data Guard

Validated behavior:

- Immature decisions do not receive `outcome_price`, `actual_change_pct`, or `actual_direction`.
- Matured decisions do not use price rows after the latest daily close visible at `as_of_timestamp_utc`.
- Matured decisions do not use price rows after the preregistered outcome window.
- Source capture future-data contamination blocks outcome resolution and prevents pass classification.
- Missing prices remain `BLOCKED_DATA`; no prices are fabricated.
- Blocked resolver run ids return non-zero from the CLI.
- Resolved outcome direction uses `long` / `avoid` / `neutral`, not `up` / `down` / `flat`.

## Provenance / Reverse Lookup

Each resolver artifact records:

- source capture run id
- source decision id
- source capture artifact path/ref
- resolver run id
- resolver schema/script version
- price source path
- price row dates used
- no-future-data decision rationale

Focused tests and local validation confirmed reverse lookup from resolver artifact back to the source capture artifact.

## Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_5_forward_live_outcome_resolver.py scripts/baseline_v3_5_forward_live_capture.py scripts/baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run ruff check --no-cache scripts/baseline_v3_5_forward_live_outcome_resolver.py tests/test_forward_live_outcome_resolver.py scripts/baseline_v3_5_forward_live_capture.py tests/test_forward_live_capture.py scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
uv run pytest -q tests/test_forward_live_outcome_resolver.py
uv run pytest -q tests/test_forward_live_capture.py
uv run pytest -q
```

Results:

- `py_compile`: PASS
- `ruff`: PASS
- `tests/test_forward_live_outcome_resolver.py`: `12 passed`
- `tests/test_forward_live_capture.py`: `13 passed`
- full pytest: `267 passed`

## Artifact Boundary

No run artifacts, transcripts, raw provider outputs, `.env*`, DB/bundle/tar/zip files, paper trading data, Stage8/Stage9 artifacts, old v2 artifacts, or README changes are part of this result.

## Next Action

After this PR merges, schedule or run the resolver against real v3.5A capture artifacts only when their horizons mature and required price data is available. Until then, captured forward-live decisions remain unscored and must not be described as OOS, science/public proof, or trading evidence.
