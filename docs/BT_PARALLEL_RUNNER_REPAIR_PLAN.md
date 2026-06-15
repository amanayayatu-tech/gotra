# BT Parallel Runner Repair Plan

Status: implemented repair plan for runner plumbing. Stage 3 is now frozen as A-class gate failure
and negative/mixed scientific result; see `docs/STAGE3_FINAL_VERDICT_20260615.md`.

Date: 2026-06-15

## 1. Problem Statement

The completed BT Stage 3 run is mechanically healthy but not formally valid:

- `bt_full_v3_20260615`: `system_health=ok`, `audit.ok=true`, `provider_errors=0`, `steps_written=2012`.
- Independent baseline replay: healthy, `cache_hits=0`, `steps_written=1006`.
- Preregistered A-class gate failed: baseline replay direction agreement is `825/1006 = 82.01%`, below the required `95%`.
- Canonical `/Users/peachy/Documents/gotra` concurrency-4 replay also failed the same gate:
  `846/1006 = 84.10%` against `bt_full_v3_20260615`.

The failure is not a cache, isolation, or audit failure. It is a reproducibility failure caused by the current Codex CLI provider surface not exposing reliable `temperature`, `top_p`, or seed controls.

This plan repaired the runner so future verification is faster, resumable, and auditable. It did not lower the preregistered gate and did not reinterpret the failed Stage 3 run as valid. CI green means this repair plumbing is healthy; Stage 3 remains failed because the final baseline replay compare artifact stayed below `95%`.

## 2. Iron Laws

All implementation and validation must obey these constraints from `docs/AUTONOMY_RUNBOOK.md`:

1. LLM calls remain behind the approved provider interface and Codex CLI route. No direct OpenAI or Anthropic SDK imports in gotra business code.
2. No acceleration switch may violate ksana purity or Alaya human-only strong promotion.
3. Backtest decisions at time `T` may only use inputs with `availability_date <= T`.
4. Every backtest step must leave auditable artifacts under the run directory.
5. Run artifacts, price cache, reports, bundles, patches, secrets, and validation logs do not enter git.
6. A-class correctness gates are not softened after observing results.
7. Negative or mixed scientific results are reported as negative or mixed.

## 3. Non-Goals

- Do not change the preregistered `95%` baseline replay direction-agreement threshold.
- Do not switch the Stage BT provider to direct Responses API or any direct vendor SDK.
- Do not change the existing Stage 3 scientific result.
- Do not make prompt compression part of the current Stage 3 evidence retroactively.
- Do not parallelize same-ticker Alaya steps out of order.
- Do not treat Codex CLI `temperature=0` prompt guidance as reliable sampling control.

## 4. Target Architecture

### 4.1 Execution Graph

Baseline steps are independent by `(ticker, decision_date)`. They may run in a worker pool.

Alaya steps are sequential within a ticker because each step may consume matured feedback from prior steps. Different tickers may run concurrently as independent ticker chains.

Final output order must be deterministic. Step IDs and step indexes are assigned from a precomputed sorted plan, not from worker completion order.

### 4.2 Concurrency-Safe State

Replace whole-file JSON cache and in-memory budget accounting with a SQLite WAL ledger:

- `decision_cache(cache_key primary key, namespace, prompt_hash, arm, ticker, decision_date, payload_json, token_usage_json, created_at)`
- `budget(run_id primary key, max_tokens, spent_tokens, cache_hits, cache_misses, over_budget_error)`
- `provider_calls(call_id primary key, run_id, worker_id, arm, ticker, decision_date, cache_key, started_at, finished_at, elapsed_ms, status, estimated_tokens, error_type, attempt)`
- `steps(step_id primary key, run_id, step_index, arm, ticker, decision_date, status, step_path, created_at)`
- `run_flags(run_id primary key, abort_reason, paused_reason, updated_at)`

SQLite must run in WAL mode. Writes that affect cache or budget use transactions.

### 4.3 Analyzer

Add a gotra analyzer modeled after Alaya `shadow-analyze`:

- Rebuild `summary.json` when the runner was interrupted before final summary write.
- Emit `quality_summary.json` with row-level statuses: `pass`, `fail`, `low_coverage`, or `na`.
- Keep formal gates separate from diagnostics.
- Read only local run artifacts; never call the provider.

## 5. Implementation Phases

### R0. Repository Hygiene And CI

Files:

- `.github/workflows/ci.yml`
- `README.md`
- `docs/BT_PARALLEL_RUNNER_REPAIR_PLAN.md`

Steps:

1. Push current complete code branch before new edits.
2. Add GitHub Actions CI.
3. Extract runbook iron laws into README.
4. Add this executable repair plan.

Validation:

```bash
git status --short --branch
uv run ruff check . --force-exclude
uv run pytest -q
uv run pytest -q engine/ksana/tests/orchestrator/test_decision_checks.py
git diff --check
if rg -n "import openai|from openai|import anthropic|from anthropic" --glob "*.py" --glob "!engine/ksana/chairman/llm/narrative_generator.py" .; then exit 1; fi
git push
```

Acceptance:

- GitHub branch exists and includes complete local code.
- CI file is present.
- README states the iron laws and current code status.
- Local deterministic checks pass.

### R1. Analyzer And Quality Summary

Files:

- `gotra/backtest/analyze.py` implemented
- `tests/test_backtest_analyze.py` implemented

Steps:

1. Read all step files under `<run_root>/<arm>/step_*.json`.
2. Read `event_log.jsonl` if present.
3. Recompute audit with `audit_run(run_root)`.
4. Recompute metrics with `summarize_steps(steps)`.
5. Reconstruct `system_health.json` when missing from available evidence.
6. Write `summary.json` and `quality_summary.json`.

Quality rows:

- `future_leak_audit`
- `steps_written`
- `provider_errors`
- `provider_abort`
- `token_budget`
- `event_log_actor`
- `baseline_replay_agreement`
- `paired_step_coverage`
- `latency_observed`

Validation:

```bash
uv run pytest -q tests/test_backtest_analyze.py
uv run python -m gotra.backtest.analyze --run-root data/backtest/runs/<RUN_ID>
python -m json.tool data/backtest/runs/<RUN_ID>/summary.json >/dev/null
python -m json.tool data/backtest/runs/<RUN_ID>/quality_summary.json >/dev/null
```

Acceptance:

- Removing `summary.json` from a fixture run and re-running the analyzer recreates equivalent core metrics.
- Analyzer never calls Codex CLI or network.
- `quality_summary.json` labels failed, low-coverage, and unavailable evidence distinctly.

### R2. SQLite Ledger In Serial Mode

Files:

- `gotra/backtest/ledger.py` implemented
- `gotra/backtest/walk_forward.py` integrated behind `--ledger sqlite`
- `tests/test_backtest_ledger.py` implemented

Steps:

1. Add `SQLiteDecisionLedger`.
2. Add CLI/config options:
   - `--ledger sqlite|json`
   - `--ledger-path`
   - `--resume`
3. Keep default behavior serial.
4. In serial mode, replace cache writes with ledger-backed cache writes.
5. Keep existing JSON cache compatibility for read-only migration if needed.

Validation:

```bash
uv run pytest -q tests/test_backtest_ledger.py tests/test_backtest_walk_forward.py
uv run python -m gotra.backtest.walk_forward --provider heuristic --mode sampled --run-id ledger_serial_canary --max-steps 20 --ledger sqlite --cache-namespace ledger-serial-canary
uv run python -m gotra.backtest.analyze --run-root data/backtest/runs/ledger_serial_canary
```

Acceptance:

- `--ledger sqlite --provider-concurrency 1` produces the same scored step count and audit status as the old serial path on the same sampled fixture.
- No cache corruption when a process exits after writing some steps.
- Budget overage still pauses and writes `system_health`.

### R3. Baseline Parallelism

Files:

- `gotra/backtest/parallel.py` implemented
- `gotra/backtest/walk_forward.py` integrated behind `--parallel-mode baseline`
- `tests/test_backtest_parallel.py` implemented

Steps:

1. Precompute all eligible baseline tasks.
2. Assign stable `step_index` before dispatch.
3. Run tasks with `ThreadPoolExecutor(max_workers=N)`.
4. Worker writes step artifacts atomically.
5. Main process runs analyzer at the end.

CLI:

```bash
uv run python -m gotra.backtest.walk_forward \
  --provider codex_cli \
  --mode full \
  --arms baseline \
  --step-months 1 \
  --provider-concurrency 4 \
  --parallel-mode baseline \
  --ledger sqlite \
  --cache-namespace baseline-parallel-canary-20260615 \
  --run-id bt_baseline_parallel_canary_20260615 \
  --max-steps 40
```

Validation:

```bash
uv run pytest -q tests/test_backtest_parallel.py
uv run python -m gotra.backtest.walk_forward --provider heuristic --mode sampled --arms baseline --provider-concurrency 4 --parallel-mode baseline --ledger sqlite --run-id heuristic_parallel_baseline --max-steps 40
uv run python -m gotra.backtest.analyze --run-root data/backtest/runs/heuristic_parallel_baseline
```

Acceptance:

- Fake provider sleep test shows wall time decreases with concurrency.
- All step indexes are deterministic.
- Re-running with `--resume` skips completed steps without duplicate provider calls.
- `provider_calls.elapsed_ms` is populated.

### R4. Alaya Ticker-Chain Parallelism

Files:

- `gotra/backtest/parallel.py` implemented
- `gotra/backtest/walk_forward.py` integrated behind `--parallel-mode ticker-chains`
- `tests/test_backtest_walk_forward.py` includes Alaya ticker-chain integration coverage

Steps:

1. Build one sequential task chain per ticker.
2. Run ticker chains concurrently.
3. Preserve matured feedback order within each ticker.
4. For each chain, compute feedback only from steps whose `outcome_availability_date <= decision_date`.

Validation:

```bash
uv run pytest -q tests/test_backtest_parallel.py tests/test_backtest_walk_forward.py
uv run python -m gotra.backtest.walk_forward --provider heuristic --mode sampled --arms alaya --provider-concurrency 4 --parallel-mode ticker-chains --ledger sqlite --run-id heuristic_parallel_alaya --max-steps 40
uv run python -m gotra.backtest.analyze --run-root data/backtest/runs/heuristic_parallel_alaya
```

Acceptance:

- Same ticker never has overlapping provider calls.
- Different tickers can overlap.
- Feedback counts and dates match serial execution for the same sampled fixture.

### R5. Real Codex CLI Replay

Steps:

1. Run baseline-only Codex canary at concurrency 2.
2. If provider health is clean, run concurrency 4.
3. Only after canaries pass, run the full independent baseline replay.
4. Compare against the formal run.

Commands:

```bash
uv run python -m gotra.backtest.walk_forward \
  --provider codex_cli \
  --mode full \
  --arms baseline \
  --step-months 1 \
  --provider-concurrency 4 \
  --parallel-mode baseline \
  --ledger sqlite \
  --resume \
  --cache-namespace baseline-replay-parallel-20260615 \
  --run-id bt_baseline_replay_parallel_20260615

uv run python -m gotra.backtest.compare_runs \
  --reference-run /Users/peachy/Documents/gotra-BT-full-monthly/data/backtest/runs/bt_full_v3_20260615 \
  --candidate-run data/backtest/runs/bt_baseline_replay_parallel_20260615 \
  --arm baseline \
  --threshold 0.95 \
  > data/backtest/runs/bt_baseline_replay_parallel_20260615/compare_baseline_direction.json
```

Acceptance:

- If direction agreement is `>=95%`, A-class replay gate passes for that run pair.
- If direction agreement remains below `95%`, report the experiment as invalid under the preregistered gate.
- In either case, do not change thresholds after observing results.

### R6. Provider Determinism Gate

The approved routebook currently allows Codex CLI as the LLM route and forbids direct vendor SDKs
inside gotra business code. The current Codex CLI provider does not expose reliable
`temperature`, `top_p`, or `seed` controls. Therefore no current real LLM provider in this repo is
eligible for preregistered Stage 3 replay acceptance.

Use `--require-stage3-provider` before any future formal science run. It must abort before provider
preflight or provider calls unless the selected provider explicitly declares Stage 3 eligibility.

```bash
uv run python -m gotra.backtest.walk_forward \
  --provider codex_cli \
  --mode full \
  --arms baseline \
  --step-months 1 \
  --ledger sqlite \
  --require-stage3-provider \
  --run-id stage3_provider_gate_check
```

Expected current result:

- `system_health.status=blocked_provider_determinism`.
- `steps_written=0`.
- `provider_errors=0`.
- `provider_determinism.stage3_acceptance_eligible=false`.
- The run is blocked by provider capability, not by cache, audit, budget, or isolation.

## 6. Speed Targets

Observed independent baseline replay:

- Events: `1006`
- Span: approximately `7.23h`
- Mean interval: approximately `25.9s/step`

Targets:

- Concurrency 2: under `4h`.
- Concurrency 4: under `2h` plus provider overhead.
- Concurrency 8: exploratory only after concurrency 4 is stable.

These are operational speed targets, not scientific acceptance gates.

## 7. Rollback

- Disable parallelism with `--provider-concurrency 1 --parallel-mode off`.
- Keep JSON cache compatibility until SQLite ledger has passed canaries.
- If provider instability increases under concurrency, retain analyzer and ledger improvements but keep real Codex replay serial.
- Never delete prior run directories during repair; create new run IDs.

## 8. Final Definition Of Done

The repair is complete only when all are true:

- Local CI-equivalent checks pass.
- GitHub Actions is green on the repair branch.
- Analyzer can reconstruct an interrupted run.
- SQLite ledger passes race and resume tests.
- Baseline parallel canary shows speedup without cache, budget, or event-log corruption.
- Alaya ticker-chain parallel canary preserves serial feedback semantics.
- `--require-stage3-provider` blocks current `codex_cli` before expensive formal science calls.
- Repair report states that CI green is not formal Stage 3 acceptance.
- Formal Stage 3 report states whether the preregistered replay gate passes or fails, without changing the gate.
