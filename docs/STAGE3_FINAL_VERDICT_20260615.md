# Stage 3 Final Verdict 2026-06-15

Status: frozen as preregistered A-class gate failure and negative/mixed scientific result.

This document is the final Stage 3 verdict for the Codex CLI-only Phase BT run. It does not
reinterpret, soften, or repair the preregistered gates after observing results.

## Verdict

Stage 3 did not validate cognitive enhancement.

- A-class correctness gate: FAIL.
- H1 convergence: FAIL.
- H2 drift resistance: mixed.
- H3 HAC differential: FAIL.

The engineering/runtime chain is healthy enough to be useful, but the formal science claim is not
accepted because the preregistered baseline replay direction-agreement gate did not pass.

## A-Class Correctness

The formal Stage 3 run itself was mechanically healthy:

- Run: `/Users/peachy/Documents/gotra-BT-full-monthly/data/backtest/runs/bt_full_v3_20260615`
- `system_health.status=ok`
- `audit.ok=true`
- `provider_errors=0`
- `steps_written=2012`
- `sampled_validation_only=false`

The canonical independent baseline replay in `/Users/peachy/Documents/gotra` was also mechanically
healthy:

- Run: `data/backtest/runs/bt_baseline_parallel_replay4_20260615`
- `system_health.status=ok`
- `audit.ok=true`
- `provider_errors=0`
- `steps_written=1006`
- `cache_hits=0`
- `token_budget.spent_tokens=16853142`
- `parallel.provider_concurrency=4`
- `parallel.mode=baseline`
- `ledger.backend=sqlite`

The preregistered replay gate failed:

- Reference run: `bt_full_v3_20260615`
- Candidate replay: `bt_baseline_parallel_replay4_20260615`
- Arm: `baseline`
- Direction agreement: `846/1006 = 84.10%`
- Required threshold: `95%`
- Compare artifact:
  `data/backtest/runs/bt_baseline_parallel_replay4_20260615/compare_bt_full_v3_20260615.json`

Therefore, A-class correctness is FAIL even though the runtime, audit, provider isolation, ledger,
resume, and cache-isolation checks were healthy.

## Scientific Hypotheses

These results are reported honestly, but they are not sufficient to claim formal validation because
the A-class replay gate failed first.

### H1 Convergence

FAIL.

- First-third MSE: `131.354241`
- Final-third MSE: `177.067368`
- Observed reduction: `-34.8014%`
- Required reduction: `>=15%`

### H2 Drift Resistance

Mixed.

Passed windows:

- US-China trade war
- HK platform regulation
- Global rate hikes
- Generative AI regime

Failed window:

- COVID shock

Observed formal run details:

- COVID shock: `alaya_mse=141.282633`, `baseline_mse=137.934271`, FAIL
- US-China trade war: `alaya_mse=125.493476`, `baseline_mse=129.913555`, PASS
- HK platform regulation: `alaya_mse=103.587226`, `baseline_mse=117.713273`, PASS
- Global rate hikes: `alaya_mse=169.43905`, `baseline_mse=173.582246`, PASS
- Generative AI regime: `alaya_mse=186.323214`, `baseline_mse=191.304267`, PASS

### H3 HAC Differential

FAIL.

- `n=1006`
- `mean_loss_diff=2.817066`
- `z_score=1.731243`
- `p_value=0.08340848`
- Required threshold: `p<0.05`

## Provider Determinism

This project remains Codex CLI-only for real LLM calls under the current routebook. That constraint is
accepted for this frozen Stage 3 verdict.

Current Codex CLI can run real provider research, but it does not expose reliable sampling controls
for `temperature`, `top_p`, or `seed`. The repository now records this with an explicit gate:

- Gate run: `data/backtest/runs/stage3_provider_gate_check_20260615`
- `system_health.status=blocked_provider_determinism`
- `steps_written=0`
- `provider_errors=0`
- `provider_health.preflight_enabled=false`
- `provider_determinism.stage3_acceptance_eligible=false`

This prevents future expensive formal science runs from accidentally using a provider that cannot
meet the preregistered replay requirement.

## Final Claim Boundary

Allowed claims:

- Gotra's BT plumbing, audit chain, SQLite ledger, provider isolation, resume behavior, and baseline
  parallel execution are working on the observed artifacts.
- Codex CLI-only Stage 3 produced useful negative/mixed evidence.
- H2 contains local exploratory signals in four of five preregistered windows.

Disallowed claims:

- Do not claim Stage 3 passed.
- Do not claim cognitive enhancement was formally validated.
- Do not claim CI green or provider health implies scientific acceptance.
- Do not rerun Codex CLI full replay and reinterpret a below-threshold replay as valid.

## Frozen Outcome

Stage 3 is closed as:

```text
A-class gate: FAIL
H1: FAIL
H2: mixed
H3: FAIL
Cognitive enhancement: not proven
```

Any future attempt to prove cognitive enhancement must be a new preregistered stage, not a
retroactive repair of Stage 3.
