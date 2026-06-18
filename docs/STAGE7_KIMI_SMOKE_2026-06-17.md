# gotra Stage 7 Kimi Provider Smoke - 2026-06-17

## Scope

This is a provider/plumbing smoke record for wiring SophNet Kimi-K2.6 into
`gotra.backtest.walk_forward` as `--provider kimi`.

Evidence layer: smoke evidence. This is not a Stage 7 preregistration, not a
full/monthly run, and not an H1/H2/H3 science claim.

## Code Changes

- Added `kimi` to `ProviderName`, `--provider` choices, and `_build_provider`.
- Routed `kimi` through `CodexDecisionProvider(client=KimiCompletionClient(), provider_name="kimi")`.
- Included `kimi` in provider preflight, provider error fuse handling, provider metadata, determinism metadata, and median-denoising cache prompt versioning.
- Reused the existing `--codex-responses-samples` / `--codex-responses-sample-concurrency` sampling layer for Kimi; no new N, epsilon, universe, window, or gate was introduced.
- Added regression coverage for Kimi provider construction, missing `SOPHNET_API_KEY`, CLI parsing, and median-denoising reuse.

## Commands

Missing-key guard:

```bash
env -u SOPHNET_API_KEY -u PERPLEXITY_API_KEY -u PPLX_API_KEY \
  uv run python -m gotra.backtest.walk_forward \
  --provider kimi \
  --mode sampled \
  --arms baseline,alaya \
  --tickers AAPL \
  --max-steps 1 \
  --run-id stage7_kimi_no_key_guard_20260617T000000Z \
  --cache-namespace stage7_kimi_no_key_guard \
  --ledger sqlite
```

Expected result: exit code 1 with provider preflight failure:
`SOPHNET_API_KEY is required for KimiCompletionClient`. No heuristic fallback occurred.

Real Kimi smoke. `SOPHNET_API_KEY` was provided through the local environment and
is intentionally not recorded here.

```bash
uv run python -m gotra.backtest.walk_forward \
  --provider kimi \
  --mode sampled \
  --arms baseline,alaya \
  --tickers AAPL,1211.HK \
  --max-steps 4 \
  --run-id stage7_kimi_smoke_20260617T094500Z \
  --cache-namespace stage7_kimi_smoke_20260617 \
  --ledger sqlite
```

## Smoke Artifacts

Run directory:
`data/backtest/runs/stage7_kimi_smoke_20260617T094500Z`

These artifacts are intentionally not committed:

- `summary.json`
- `system_health.json`
- `quality_summary.json`
- `event_log.jsonl`
- `run_ledger.sqlite`
- arm step JSON files

## Smoke Results

Summary readback:

| Field | Value |
| --- | --- |
| provider | `kimi` |
| mode | `sampled` |
| run_id | `stage7_kimi_smoke_20260617T094500Z` |
| cache_namespace | `stage7_kimi_smoke_20260617` |
| tickers | `1211.HK`, `AAPL` |
| arms | `baseline`, `alaya` |
| steps_written | `4` |
| scored_steps | `4` |
| paired_steps | `2` |
| provider_errors | `0` |
| provider preflight | `ok` |
| system_health.status | `ok` |
| audit.ok | `true` |
| audit.steps_checked | `4` |
| audit.violations | `[]` |
| event_log rows | `4` |
| ledger provider_calls | `ok=4` |
| ledger steps | `4` |
| token_usage_source provider ratio | `4/4 = 1.0` |
| spent provider tokens | `50044` |

Step readback:

| arm | ticker | decision_date | status | token_usage_source | tokens | sample_count | vote_consistency |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| baseline | `1211.HK` | `2017-01-01` | `scored` | `provider_usage` | `12506` | `5` | `1.0` |
| baseline | `AAPL` | `2017-01-01` | `scored` | `provider_usage` | `12556` | `5` | `1.0` |
| alaya | `1211.HK` | `2017-01-01` | `scored` | `provider_usage` | `12395` | `5` | `1.0` |
| alaya | `AAPL` | `2017-01-01` | `scored` | `provider_usage` | `12587` | `5` | `1.0` |

Schema / parse / runtime status:

- `schema_error`: `0` observed.
- `error_type`: empty on all step JSON files.
- `provider_error`: empty on all step JSON files.
- Crashes: `0`.
- Future-function audit: pass, zero violations.
- `quality_summary.overall_status`: `pass`.

## Fixes During This Task

- Fixed the missing first-class Kimi path in `walk_forward.py`.
- Fixed sampling behavior so Kimi uses the existing median-denoising configuration layer instead of silently running as a single sample provider.
- Fixed preflight/error-fuse/metadata coverage so Kimi missing-key and unhealthy-provider paths are explicit and auditable.
- Added tests so Kimi provider wiring cannot regress silently.

No transport retry or sample replacement was needed in the real smoke run.

## Verification

All commands passed:

```bash
uv run pytest -q
uv run pytest -q tests/test_backtest_walk_forward.py
uv run ruff check . --force-exclude
python3 -m py_compile gotra/backtest/walk_forward.py gotra/backtest/kimi_client.py
git diff --check
uv run pytest -q engine/ksana/tests/orchestrator/test_decision_checks.py
```

Observed results:

- Full pytest: `118 passed`.
- Walk-forward focused pytest: `40 passed`.
- Ruff: `All checks passed!`.
- `py_compile`: passed.
- `git diff --check`: passed.
- Ksana orchestration guard: `1 passed`.
- Direct LLM import/endpoint guard: no forbidden `openai` / `anthropic` import or endpoint hits outside the existing allowed adapter.

## Boundary Statement

This smoke shows that the Kimi provider path is wired into `walk_forward`, can
run a minimal real two-arm sample without crash, records provider usage, writes
auditable step artifacts, and passes local validation.

It does not establish replay-gate correctness, long-run/formal acceptance, or
any H1/H2/H3 scientific conclusion. The next separate human-approved step would
be Stage 7 preregistration text and its formal run protocol.
