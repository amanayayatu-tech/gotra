# GOTRA Full Analyst Production Loop Runbook

## Goal

Operate the independent GOTRA full analyst loop candidate:

public universe slice -> per-symbol prompt -> Codex CLI `gpt-5.5` research -> positive/negative/red-team sections -> judge gate -> optional GOTRA-internal cognition/knowledge/feedback state sync -> hash-chain readback verification -> sanitized status/report artifacts.

## Non-Goals

- Not investment advice.
- Not a trading signal.
- Not performance proof.
- Not science/public proof.
- Not formal production acceptance by itself.
- Does not modify or replace the five daily stock-pool report timers.
- Does not write `/reports/latest.md`.

## Evidence Layer

Allowed labels:

- local checks
- short smoke, when explicitly run as `full-analyst-loop-smoke`
- server runtime loop evidence, only after the independent loop actually runs
- public-safe artifact smoke

Do not label a short smoke as 10h evidence, formal acceptance, science/public proof, performance proof, trading signal, or investment advice.

## LLM Configuration

All real LLM calls use Codex CLI. Default environment fields:

```bash
GOTRA_FULL_ANALYST_LLM_RUNNER=codex-cli
GOTRA_FULL_ANALYST_LLM_MODEL=gpt-5.5
GOTRA_FULL_ANALYST_REASONING_EFFORT=high
GOTRA_FULL_ANALYST_TIMEOUT_SECONDS=300
GOTRA_FULL_ANALYST_RETRIES=0
```

The pipeline hard-stops when `codex-cli` is configured with a model other than `gpt-5.5`. It must not guess a substitute model.

## GOTRA Internal Alaya State Configuration

In this runbook, `Alaya` means the GOTRA repo internal cognition flywheel,
knowledge memory, and feedback state surface. It does not mean a separate Alaya
repository or an external project endpoint.

`--alaya-mode real` writes an append-only hash-chain event under the GOTRA
private audit tree and verifies readback from that same stream. Default path:

```bash
/opt/gotra/data/private/full_analyst_runs/cognition_flywheel/full_analyst_memory_events.jsonl
```

Optional:

```bash
GOTRA_FULL_ANALYST_ALAYA_STATE_PATH
GOTRA_FULL_ANALYST_ALAYA_ACTOR
```

No external state endpoint, external write/readback path, or separate Alaya
checkout is required or allowed for this pipeline. Mock/off results are allowed
for local tests and short smoke, but they must stay labeled as mock/off.

## Policy

Symbol-level:

- `publish`: included in the public report and eligible for Alaya sync.
- `needs_review`: visible as a review item, not synced to Alaya.
- `blocked`: public-safe symbol/reason category only, not synced to Alaya.
- `data_gap`: visible as a data gap and not promoted to full success.

Run-level exit codes:

- `0`: all publish, or only allowed review/data-gap items, with artifacts and scans ok.
- `2`: blocked symbol, failed symbol, artifact write failure, public scan failure, Alaya write failure, or Alaya readback failure/mismatch.
- `1`: top-level unexpected CLI failure before a public status can be written.

## Public Artifacts

Loop artifacts:

```text
/opt/gotra/data/reports/full_analyst_loop/status_full_analyst_loop.json
/opt/gotra/data/reports/full_analyst_loop/full_analyst_loop_latest.md
/var/www/gotra-public-ledger/reports/status_full_analyst_loop.json
/var/www/gotra-public-ledger/reports/full_analyst_loop_latest.md
```

Public artifacts must not contain secrets, raw prompts, completions, messages, provider raw responses, stdout, stderr, trading advice, performance proof, or science/public overclaim.

## Private Audit Artifacts

```text
/opt/gotra/data/private/full_analyst_runs/<run_id>/heartbeat.json
/opt/gotra/data/private/full_analyst_runs/<run_id>/events.jsonl
/opt/gotra/data/private/full_analyst_runs/<run_id>/failures.jsonl
/opt/gotra/data/private/full_analyst_runs/<run_id>/cycle_001_summary.json
/opt/gotra/data/private/full_analyst_runs/<run_id>/attempts/
/opt/gotra/data/private/full_analyst_runs/<run_id>/alaya_events/
```

Private audit may keep sanitized metadata and prompt hashes. Do not copy private audit files into the web root.

## Short Smoke

Fixture smoke, labeled mock:

```bash
cd /opt/gotra
uv run python scripts/public_stock_pool_full_analyst_pipeline.py \
  --mode full-analyst-loop-smoke \
  --run-id full_analyst_10h_loop_20260629_v1 \
  --output-dir /opt/gotra/data/reports/full_analyst_loop \
  --private-audit-root /opt/gotra/data/private/full_analyst_runs \
  --static-dir /var/www/gotra-public-ledger/reports \
  --publish-static \
  --llm-runner fixture \
  --alaya-mode mock \
  --symbol HKEX:0700
```

## Independent 10h Candidate Command

Use only after PR/deploy approval and GOTRA-internal state readiness:

```bash
cd /opt/gotra
uv run python scripts/public_stock_pool_full_analyst_pipeline.py \
  --mode full-analyst-production-loop \
  --run-id full_analyst_10h_loop_20260629_v1 \
  --output-dir /opt/gotra/data/reports/full_analyst_loop \
  --private-audit-root /opt/gotra/data/private/full_analyst_runs \
  --static-dir /var/www/gotra-public-ledger/reports \
  --publish-static \
  --llm-runner codex-cli \
  --model gpt-5.5 \
  --reasoning-effort "${GOTRA_FULL_ANALYST_REASONING_EFFORT:-high}" \
  --per-symbol-timeout-seconds "${GOTRA_FULL_ANALYST_TIMEOUT_SECONDS:-300}" \
  --retries "${GOTRA_FULL_ANALYST_RETRIES:-0}" \
  --alaya-mode real \
  --loop-duration-seconds 36000 \
  --heartbeat-interval-seconds 300 \
  --sample-cadence-seconds 1800
```

This command is independent from the daily timers. Do not enable a timer for it unless explicitly approved.

## Monitoring

Heartbeat:

```bash
jq . /opt/gotra/data/private/full_analyst_runs/full_analyst_10h_loop_20260629_v1/heartbeat.json
```

Events and failures:

```bash
tail -n 50 /opt/gotra/data/private/full_analyst_runs/full_analyst_10h_loop_20260629_v1/events.jsonl
tail -n 50 /opt/gotra/data/private/full_analyst_runs/full_analyst_10h_loop_20260629_v1/failures.jsonl
```

Public status:

```bash
curl -sS https://gotra.me/reports/status_full_analyst_loop.json | jq .
curl -sS https://gotra.me/reports/full_analyst_loop_latest.md | head
```

Frontend:

- Open `https://gotra.me/reports`.
- Confirm phase, heartbeat, elapsed time, cycle, publish/review/blocked/data_gap counts, Alaya sync/readback counts, evidence layer, and limitations are visible.
- Confirm stale heartbeat is warning/critical.
- Confirm mock is not displayed as real.
- Confirm blocked is not displayed as success.

## Scans and Validation

Backend:

```bash
cd /opt/gotra
uv run python -m py_compile scripts/public_stock_pool_full_analyst_pipeline.py
uv run ruff check
uv run pytest tests/test_public_stock_pool_full_analyst_pipeline.py tests/test_public_stock_pool_report.py tests/test_public_stock_pool_full_research.py
```

Frontend:

```bash
cd /opt/gotra-public-ledger
npm run secrets:scan
npm run compliance:scan
npm run lint
npm run typecheck
npm test
npm run build
```

## Failure Alert Strategy

Before external alerts are wired, sanitized failure state is exposed through:

- private `events.jsonl`
- private `failures.jsonl`
- private `heartbeat.json`
- public `status_full_analyst_loop.json`
- `/reports` stale/blocked display

Never expose raw exception text, traceback, prompt, model output text, shell output, API payloads, or secret values in public artifacts.

## Stop and Resume

Stop an interactive run with the shell/job controller for that process. Do not modify the five daily timers.

Resume by starting a new reviewed run id or rerunning the same run id only when the audit owner accepts appending to the same private run directory. Do not delete historical data to make a rerun look clean.

## Acceptance Checklist

- Required local checks pass.
- Public scan passes.
- Private audit and public artifact paths are writable.
- Codex CLI `gpt-5.5` preflight passes.
- GOTRA-internal state path is writable.
- GOTRA-internal Alaya state append succeeds.
- GOTRA-internal readback verifies event hash.
- Heartbeat is fresh and visible.
- Frontend `/reports` displays status without stale/blocked/mock confusion.
- Five daily timers remain unchanged.
- No secret/raw model I/O leaks.
- No advice, trading-signal, performance-proof, or science/public-proof claims.
