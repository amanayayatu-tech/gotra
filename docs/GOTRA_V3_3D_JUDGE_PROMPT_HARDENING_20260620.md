# GOTRA v3.3d Judge Prompt / Spec Hardening

Date: 2026-06-20

Branch: `codex/gotra-v3-3d-judge-prompt-hardening-20260620`

Base: PR #18 branch `codex/gotra-v3-3c-judge-temporal-replay-20260620`

## Evidence Layer

This is local prompt/spec contract evidence only.

It is not provider/runtime evidence, not formal-lite acceptance, not OOS, not
forward-live, not science/public proof, and not trading or investment advice.

No Kimi, GLM, DeepSeek, Codex CLI LLM, or provider API call was made. This
change hardens production Judge prompt text and local contract tests; it does
not empirically prove that a live LLM will outperform the previous prompt.

Historical `direct_llm` remains `direct_llm_parametric_memory_control`, not a
clean no-future baseline. v3.3d is Judge prompt/spec hardening and does not
interpret direct LLM arm metrics.

## Relation To v3.3a / v3.3b / v3.3c

v3.3a added Judge decision provenance and `gate_poller --dry-run`.

v3.3b added local outcome-derived feedback artifact production and strict
true-independent feedback closed-loop mock evidence.

v3.3c added local Judge temporal replay/calibration and produced
`REPLAY_CALIBRATION_PASS` on frozen fixture evidence. That verdict was
fixture-level replay evidence only.

v3.3d uses the v3.3c structured/calibrated replay policy as the rationale for
production prompt/spec hardening. It does not modify the replay verdict, v3
formal-lite harness, provider backend, or outcome-feedback production behavior.

## Prompt Changes

Files:

- `gotra/judge_agent/prompts/meaning_gate.md`
- `gotra/judge_agent/prompts/risk_gate.md`

Both prompts now keep the existing strict `JudgeDecision` JSON contract:

- `decision`: `approve|reject|defer`
- `confidence`: `0..1`
- `reasoning`: Simplified Chinese, no more than 300 chars
- `knowledge_flag`: `none|watch|strong_candidate|quarantine_candidate`
- `audit_actor`: `judge_agent/codex`
- optional `reason_code`

Structured dimensions now required in the prompt:

1. methodology disagreement versus factual error / evidence contradiction
2. evidence provenance and source traceability
3. future-source leak / decision-date boundary risk
4. conflict with existing strong knowledge
5. duplicate/noise or low incremental value
6. insufficient evidence / defer conditions
7. likely feedback substrate quality for clean outcome-derived feedback

Decision rubric:

- approve only when evidence is time-bounded, traceable, non-duplicative,
  low-risk, and useful enough for active/working knowledge
- reject for high risk, future-source leak risk, strong conflict without proof,
  factual contradiction, duplicate/noise, data-integrity risk, or low-quality
  artifact value
- defer when evidence may be useful but uncertain, missing provenance, has an
  unresolved conflict, or requires human review

Reason code examples:

- `calibrated_accept`
- `risk_or_future_source_leak`
- `duplicate_or_noise`
- `insufficient_or_uncertain`
- `low_value_or_low_quality`
- `strong_conflict`
- `methodology_disagreement`
- `factual_error`
- `needs_human_review`

The prompts explicitly forbid use of future outcomes, realized returns,
post-horizon labels, or any information unavailable at gate decision time.

`strong_candidate` remains a report flag only. It must never auto-promote
strong knowledge; human approval remains required.

## Context Contract

`JudgeAgent.build_context()["output_contract"]` now includes:

- `reason_code_examples`
- `rubric_dimensions`
- `strong_candidate_policy`

This is a context hint only. It does not add required fields to `JudgeDecision`
and does not change the external Judge API shape.

## Contract Tests

Tests now cover:

- meaning and risk prompt files include the structured rubric dimensions
- prompt files preserve strict JSON-only output contract
- prompt files preserve Simplified Chinese reasoning requirement
- prompt files preserve strong human gate / no auto-promote boundary
- prompt files forbid future outcomes, realized returns, and post-horizon data
- `CodexJudgeProvider` selects risk prompt for risk gates and meaning prompt for
  other gates
- `CodexJudgeProvider` still passes `audit_actor` requirement and
  `temperature=0.0`
- `JudgeAgent.build_context()` exposes reason-code examples and rubric
  dimensions

No test calls a real Codex CLI model, provider API, or LLM backend.

## Validation

Commands run:

```bash
uv run python -m py_compile gotra/judge_agent/judge_agent.py gotra/judge_agent/llm.py gotra/judge_agent/temporal_replay.py
uv run ruff check --no-cache gotra/judge_agent/llm.py gotra/judge_agent/judge_agent.py tests/test_judge_llm.py tests/test_judge_agent.py tests/test_judge_temporal_replay.py
uv run pytest -q tests/test_judge_llm.py tests/test_judge_agent.py tests/test_judge_temporal_replay.py
uv run pytest -q
```

Observed:

- py_compile: pass
- focused ruff: pass
- focused pytest: `26 passed`
- full pytest: `235 passed`

## Artifact Boundary

Committed files are limited to prompt/spec text, local tests, optional context
contract text, and this documentation.

Not committed:

- provider raw responses
- provider/API run artifacts
- `data/backtest/runs/*`
- `.env*` or secrets
- DB, bundle, tar, or zip files
- `data/paper_trading/*`
- Stage8/Stage9 artifacts
- unrelated v2 docs/scripts
- generated runtime artifacts or transcripts

## Next Action

v3.4 should be planned as a separate formal-lite or forward-live /
`codex_cli_llm_backend` experiment family. Future result docs should record
prompt hash, transcript path, parsed decision hash, model/reasoning setting, and
run_id. Do not revive provider API parser/formal-lite reruns as the main
blocker.
