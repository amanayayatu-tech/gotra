# GOTRA v3.3c Judge Temporal Replay / Calibration

Date: 2026-06-20

Branch: `codex/gotra-v3-3c-judge-temporal-replay-20260620`

Base: PR #17 branch `codex/gotra-v3-3b-outcome-feedback-production-20260620`

## Evidence Layer

This is local replay/calibration evidence only.

It is not provider/runtime evidence, not formal-lite acceptance, not OOS, not
forward-live, not science/public proof, and not trading or investment advice.

This layer does not call Kimi, GLM, DeepSeek, Codex CLI backend, or any provider
API. It does not replace production `CodexJudgeProvider` prompts and does not
change the v3 formal-lite harness.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.3c is Judge replay/calibration and does not
interpret direct LLM arm metrics.

## Relation To v3.3a / v3.3b

v3.3a added Judge decision provenance and `gate_poller --dry-run`.

v3.3b added local outcome-derived feedback artifact production and closed-loop
mock evidence for strict true-independent feedback eligibility.

v3.3c adds a local temporal replay harness that compares deterministic offline
Judge policies on frozen gate fixtures with decision-time visible inputs. This
is the calibration layer before any v3.3d prompt hardening or later v3.4
planning.

## Fixture Schema

Fixture path:

`tests/fixtures/judge_temporal_replay/golden_cases.json`

Each case has:

- `case_id`
- `gate_type`
- `decision_date`
- `available_at`
- `visible`
- `labels`

Policy-visible fields are only under `visible`.

Scoring-only labels are only under `labels`:

- `expected_decision`
- `risk_outcome`
- `valuable_evidence`
- `should_defer`
- `would_create_independent_feedback`

Future/scoring-only fields are forbidden inside `visible`, including:

- `future_return`
- `actual_return_after_decision`
- `outcome`
- `post_horizon`
- `realized_after_decision`
- `label` / `labels`
- `expected_decision`
- `risk_outcome`
- `valuable_evidence`
- `should_defer`
- `would_create_independent_feedback`

The audit fails if those fields appear in policy-visible input.

## Replay Policies

Module:

`gotra/judge_agent/temporal_replay.py`

Policies:

- `judge_vn_current`: deterministic thin/legacy replay approximation.
- `judge_vn1_calibrated_candidate`: deterministic structured/calibrated
  replay candidate.

These are replay/spec policies only. They are not production prompt replacements
and are not wired into `gate_poller` production behavior.

## Metrics

Command:

```bash
uv run python -m gotra.judge_agent.temporal_replay --fixture tests/fixtures/judge_temporal_replay/golden_cases.json
```

Terminal verdict:

`REPLAY_CALIBRATION_PASS`

Future-input audit:

`future_input_violation_count = 0`

| Metric | `judge_vn_current` | `judge_vn1_calibrated_candidate` |
|---|---:|---:|
| case_count | 10 | 10 |
| decision_accuracy | 0.600000 | 1.000000 |
| high_risk_case_count | 3 | 3 |
| high_risk_false_pass_rate | 0.666667 | 0.000000 |
| valuable_case_count | 4 | 4 |
| useful_evidence_false_kill_rate | 0.000000 | 0.000000 |
| should_defer_case_count | 2 | 2 |
| defer_reasonableness_rate | 0.500000 | 1.000000 |
| safe_non_defer_case_count | 5 | 5 |
| over_defer_rate_on_safe_cases | 0.000000 | 0.000000 |
| brier_score | 0.270160 | 0.034835 |
| expected_feedback_substrate_yield | 3 | 3 |

Acceptance semantics:

The candidate policy is strictly better on high-risk false pass rate and
non-worse on useful evidence false kill, defer reasonableness, safe-case
over-defer, and confidence calibration. Since future-input violations are zero,
the replay status is `REPLAY_CALIBRATION_PASS`.

## Provenance Redaction Hardening

Carry-forward v3.3a/b hygiene issue:

`sanitize_error_message()` previously normalized newlines and truncated error
messages but did not redact obvious secret-like substrings.

v3.3c now redacts persisted Alaya write failure messages for patterns such as:

- `Bearer ...`
- `Authorization: ...`
- `api_key=...`
- `apiKey=...`
- `token=...`
- `access_token=...`
- `sk-...`

The original exception is still re-raised. Only the persisted provenance error
message is sanitized.

## What Improved

- Local replay now has an explicit future-input audit.
- Replay fixture labels are scoring-only and separated from decision-time
  visible context.
- Candidate replay policy eliminates high-risk false passes in the golden
  fixture while preserving useful-evidence handling.
- Calibration improves on the fixture Brier score.
- Expected feedback substrate yield remains auditable and label-derived.

## What This Does Not Prove

- It does not prove production Judge prompts are better.
- It does not prove provider/model output reliability.
- It does not prove GOTRA/ksana/alaya science or trading value.
- It does not create OOS or forward-live evidence.

## Validation

Commands run:

```bash
uv run python -m py_compile gotra/judge_agent/judge_agent.py gotra/judge_agent/outcome_feedback.py gotra/judge_agent/temporal_replay.py
uv run ruff check --no-cache gotra/judge_agent/temporal_replay.py gotra/judge_agent/judge_agent.py tests/test_judge_temporal_replay.py tests/test_judge_agent.py
uv run pytest -q tests/test_judge_temporal_replay.py tests/test_outcome_feedback.py tests/test_judge_agent.py
uv run python -m gotra.judge_agent.temporal_replay --fixture tests/fixtures/judge_temporal_replay/golden_cases.json
uv run pytest -q
```

Observed:

- py_compile: pass
- ruff focused: pass
- focused pytest: `27 passed`
- replay CLI verdict: `REPLAY_CALIBRATION_PASS`
- full pytest: `233 passed`

## Artifact Boundary

Committed files are limited to local replay code, tests, fixture data, and this
documentation.

Not committed:

- provider raw responses
- provider/API run artifacts
- `data/backtest/runs/*`
- `.env*` or secrets
- DB, bundle, tar, or zip files
- `data/paper_trading/*`
- Stage8/Stage9 artifacts
- unrelated v2 docs/scripts
- generated runtime replay artifacts

## Next Action

Because this fixture-level replay is `REPLAY_CALIBRATION_PASS`, v3.3d may
implement production prompt/spec hardening under a separate goal. A later v3.4
formal-lite plan should remain blocked until v3.3d is separately reviewed and
accepted.
