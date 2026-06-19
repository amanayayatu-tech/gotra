# Gotra Baseline v2 Three-Arm Preregistration (2026-06-18)

## 1. Purpose And Boundary

This preregistration freezes Baseline v2 for a small, auditable pilot comparing three arms:

| Arm | Plain-language definition | Technical definition | Question answered |
| --- | --- | --- | --- |
| `direct_llm` | A bare student answers directly | Same provider/model, ticker/date, raw `<=T` inputs, and output schema; no ksana workflow; no alaya read/update; no historical feedback | What does a direct LLM baseline do? |
| `ksana_only` | A teacher organizes the material, with no mistake notebook | Uses the ksana research/committee/screening workflow; forbids alaya historical knowledge feedback, alaya confidence, and alaya history state | Does the ksana research workflow add value? |
| `full_gotra` | A teacher organizes the material and has a mistake notebook | Ksana workflow plus alaya knowledge state, historical error feedback, and confidence update candidates; strong knowledge still requires a human gate | Does ksana plus alaya feedback add incremental value? |

Existing gotra BT code uses `baseline` and `alaya` arms. In that code path, `baseline` already uses the shared F/W/G + Chairman-style ksana workflow prompt without alaya feedback, so Baseline v2 treats existing `baseline` semantics as `ksana_only`, not as `direct_llm`.

This task is a preregistered pilot harness and engineering health check. It is not full formal acceptance, not OOS pass, not paper/live trading, and not a science/public claim.

## 2. Fairness Constraints

All three arms must share:

- same ticker/date universe
- same `decision_date`
- same provider/model when provider mode is used
- same output schema
- same actual outcome calculation
- same future-data audit
- same cache discipline

The only allowed differences are:

- `direct_llm`: no ksana workflow, no alaya, no feedback
- `ksana_only`: ksana workflow, no alaya feedback/history
- `full_gotra`: ksana workflow plus alaya feedback/history/knowledge state

## 3. Three-Arm Prompt Contract

`direct_llm` contract:

```text
你是一个单次股票判断模型。只基于下面这个截至 decision_date 的 time-bounded market packet，对 ticker 未来 horizon_days 的方向和幅度做判断。你不能使用 ksana 研究流程，不能使用 alaya 历史记忆，不能引用未来结果。请输出严格 JSON。
```

Allowed context: ticker, decision_date, horizon_days, price/history features where availability_date <= decision_date, and optional public facts only if availability_date <= decision_date.

Forbidden context: ksana output, alaya memory, historical error feedback, and actual future outcome.

`ksana_only` contract:

```text
你是 gotra/ksana 研究流程的最终裁决器。你可以使用 ksana 基于同一 time-bounded packet 生成的研究/委员会/风险输出，但不能使用 alaya 的历史知识反馈、错题本、置信度状态或 strong knowledge 候选。请输出严格 JSON。
```

Allowed context: same raw packet as `direct_llm`, plus ksana research/committee/risk artifacts generated only from `<= decision_date` inputs.

Forbidden context: alaya historical prediction ledger, alaya resolved error feedback, alaya confidence state, and future outcomes.

`full_gotra` contract:

```text
你是完整 gotra 系统的最终裁决器。你可以使用 ksana 研究流程输出，也可以使用截至 decision_date 已经可用的 alaya 知识状态、历史错误归因、置信度更新和 quarantine 过滤结果。strong knowledge 只能使用已由人类批准或当前规则允许的状态；不得使用未来 outcome。请输出严格 JSON，并列出使用了哪些 memory/knowledge refs。
```

Allowed context: same raw packet, same ksana artifacts, alaya memory/knowledge/error feedback where availability_date <= decision_date, with quarantined/conflict/stale knowledge excluded.

Forbidden context: outcomes resolved after decision_date, unapproved strong auto-promotion, and future price / actual_change_pct as signal input.

## 4. Output Schema

Each arm returns the same JSON shape:

```json
{
  "schema": "gotra.baseline_v2.three_arm_decision.v1",
  "arm": "direct_llm|ksana_only|full_gotra",
  "ticker": "AAPL",
  "decision_date": "2024-01-02",
  "horizon_days": 30,
  "direction": "long|avoid|neutral|watch|short",
  "expected_change_pct": 0.0,
  "confidence": 0.0,
  "reasoning": "string",
  "evidence_refs": [],
  "ksana_refs": [],
  "alaya_memory_refs": [],
  "risk_factors": [],
  "abstain_reason": null,
  "input_cutoff": "2024-01-02",
  "future_data_allowed": false
}
```

The harness must validate this schema before a step can count as scored.

Rules:

- `direct_llm`: `ksana_refs=[]`, `alaya_memory_refs=[]`
- `ksana_only`: `alaya_memory_refs=[]`
- `full_gotra`: `alaya_memory_refs` allowed only if availability_date <= decision_date

## 5. Universe And Time Grid

Ten stocks are too few for a formal conclusion. They are pilot only.

| Layer | Scale | Purpose |
| --- | ---: | --- |
| V0 canary | 1-3 tickers, 1-2 dates | provider/schema/future-data |
| V1 pilot | 10 tickers, 4-6 dates | harness/cost/error-rate |
| V2 formal-lite | 30-50 tickers, 12-24 monthly dates | internal research |
| V3 formal/OOS | 80-150 tickers or forward live ledger | public claim requires prereg |

V1 pilot default:

```text
tickers: AAPL, MSFT, NVDA, TSM, 0700.HK, 1211.HK, 1810.HK, 3690.HK, 6060.HK, 9988.HK
dates: 2023-01-03, 2023-07-03, 2024-01-02, 2024-07-01, 2025-01-02, 2025-07-01
horizon_days: 30
arms: direct_llm, ksana_only, full_gotra
total arm decisions: 10 * 6 * 3 = 180
```

Time-grid principle:

- primary grid: first trading day of each month
- pilot density: semiannual or quarterly allowed
- formal-lite density: monthly
- daily content ledger: product data, not formal statistical proof unless separately preregistered

## 6. Pilot Metrics

Pilot metrics are exploratory only:

- provider error rate
- paired coverage
- future-data violations
- parse/schema pass rate
- direction hit
- expected_change_pct MSE / MAE
- Policy A long-only / short-as-cash PnL
- Direct vs Ksana-only paired diff
- Ksana-only vs Full paired diff
- Direct vs Full paired diff

Formal follow-up work, not this pilot, may use paired DM/HAC, repeated-run variance components, OOS acceptance, and H1/H2/H3 science claims.

## 7. Pilot Success Standard

Pilot success means the three-arm harness is ready for a formal design, not that alaya is proven effective:

- provider health canary pass
- all three arms produce valid schema
- paired coverage >= 0.95 on selected pilot points
- future-data violations = 0
- provider error rate <= 0.05, unless explicitly classified `PROVIDER_BLOCKED`
- result documentation honestly separates engineering health, pilot signal, and no science claim

## 8. Anti-Cheating Rules

- Do not delete ticker/date rows based on pilot results.
- Do not tune thresholds to make `full_gotra` win.
- Do not treat `confidence` as vote consistency.
- Do not use `actual_change_pct` to generate signals.
- Do not change the primary metric after seeing results.

## 9. Provider And Model

This continuation corrects the Baseline v2 target provider from the earlier default `kimi` / `Kimi-K2.6` to:

```text
provider name: glm_sophnet
default model: GLM-5.2
base_url: https://www.sophnet.com/api/open-apis/v1/chat/completions
auth env priority: SOPHNET_API_KEY first, then API_KEY fallback
request: messages, model, stream=false
```

The earlier `baseline_v2_three_arm_canary_20260618T150000Z` artifact was a Kimi/Kimi-K2.6 local preflight blocker, not a real provider HTTP run.

The pilot CLI now defaults to:

```bash
--provider glm_sophnet
--provider-model GLM-5.2
```

If GLM-5.2 is blocked but Kimi is available, the harness must not auto-fallback to Kimi. Kimi fallback requires separate user authorization.

## 10. Adaptive Concurrency

Provider pilot must run provider canary first. If canary fails auth, HTTP 429, provider error, schema parse, or future-data audit, the provider pilot must not run.

Provider-pilot concurrency plan:

- canary: `provider_concurrency=1`
- ramp probe 1: `provider_concurrency=2`
- ramp probe 2: `provider_concurrency=4`
- pilot max: `provider_concurrency<=8` unless separately justified

Ramp requires zero HTTP 429, zero provider errors, zero schema parse failures, zero future-data violations, and feasible paired coverage. Any HTTP 429 or provider error downgrades to the last safe concurrency. Failure at concurrency 1 is `PROVIDER_BLOCKED`.

`full_gotra` time dependencies must be preserved by processing decision dates as waves. Within a date wave, ticker/arm work may run in parallel only when the full-gotra feedback snapshot is already frozen to `<=T`.

The current resume stage does not run provider-pilot. It only requires CLI parameters and summary fields for `--provider-concurrency`, `--max-provider-concurrency`, and `--adaptive-concurrency`.

## 11. Run Artifacts

Allowed run namespace:

```text
data/backtest/runs/baseline_v2_three_arm_*
```

Each run must write:

```text
summary.json
manifest.json
ledger.jsonl
direct_llm/step_*.json
ksana_only/step_*.json
full_gotra/step_*.json
```

Run artifacts are not git artifacts.

## 12. Evidence Layer

Final reporting must use these layers:

```text
local checks: code/tests/static validation
provider/runtime health: canary and pilot provider errors
pilot evidence: small three-arm paired run only
long-run/formal acceptance: not entered
science/public claim: not entered
```

The pilot must not be described as proving alaya superiority, gotra beating baseline, live trading readiness, OOS pass, or a formal scientific conclusion.

## 13. 2026-06-19 Kimi Provider Pilot Note

The 2026-06-19 Baseline v2 Kimi-K2.6 provider pilot was run under separate user authorization after GLM/DeepSeek provider lines were frozen as provider/runtime or schema-compatibility blockers.

This note does not change the three-arm definitions, ticker/date universe, output schema, score metric, primary metrics, or future-data audit. It records only the runtime evidence boundary for the Kimi pilot:

```text
provider = kimi
provider_model = Kimi-K2.6
provider_base_url = https://api.sophnet.com/v1/chat/completions
provider_max_tokens = 2000
run_id = baseline_v2_three_arm_pilot_kimi26_input_echo_recovery_20260619T030608Z
status = PROVIDER_PILOT_PASS
expected_steps = 180
actual_step_files = 180
paired_coverage = 1.0
```

`PROVIDER_PILOT_PASS` means the fixed Baseline v2 pilot grid completed on the Kimi provider path with paired coverage 1.0 and no provider/schema/future-data errors. It does not mean formal-lite pass, OOS pass, Stage9 pass, paper trading readiness, or a science/public claim.

In this pilot, `direct_llm` had better direction hit rate, MSE, MAE, and Policy A return than `ksana_only` and `full_gotra`. The pilot therefore does not support the claim that `ksana_only` or `full_gotra` outperformed `direct_llm` on this grid.
