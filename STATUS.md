# Gotra Status（2026-06-18）

## Current Repo State

- repo/root: `/Users/peachy/Documents/gotra`
- branch/head: `codex/stage8-pnl-backtest @ a408315`
- PR #6: `OPEN`, headRef=`codex/stage8-pnl-backtest`, headRefOid=`a408315e31f729d92479fdc455e215c2fd35f016`, url=`https://github.com/amanayayatu-tech/gotra/pull/6`
- worktree: `/Users/peachy/Documents/gotra refs/heads/codex/stage8-pnl-backtest`
- remote: `https://github.com/amanayayatu-tech/gotra.git`

## Evidence Ledger

| 项目 | 当前判定 | 证据层级 | 允许说 | 禁止说 |
| --- | --- | --- | --- | --- |
| PR #6 | baseline-only, review-fix local only | local checks | PR #6 可继续作为 Stage4-8 baseline-only/repro chain review surface | PR #6 已包含 Stage8.3/OOS/Stage9 |
| PR #6 review fixes | local code/test fixes | local checks | 5 条 diff comments 已本地修复并通过本地检查 | 已经 merge、已经远端生效 |
| Stage8 baseline-only | `BASELINE_ONLY` | local checks / screening | baseline/reference screening | alaya superiority |
| Stage8 dual-arm offline PnL | historical offline screening | local checks / historical screening | 离线历史样本中有信号，需 OOS | formal acceptance、science claim、实盘有效 |
| Stage8.1 robustness | `Fragile-positive` | local checks / robustness screening | 主结果强但集中度和分组风险明显 | robust-positive、策略有效 |
| Stage8.2 OOS design | `DESIGN_ONLY` | design only | OOS 方案/验收设计已写 | OOS 已通过 |
| Stage8.3 prereg bundle | `PASS_FOR_STAGE8_3_PREREG_BUNDLE` | design/prereg bundle | universe/spec/acceptance 已预注册待执行 | OOS pass |
| Stage8.3 canary data generation | canary complete | smoke/data-generation evidence | canary provider/run path 可用 | full OOS complete |
| Stage8.3 full data generation | `DATA_GENERATION_PARTIAL / BLOCKED_AUTH_OR_PROVIDER` | provider/runtime health / partial data-generation | full run 被 SophNet/Kimi HTTP 429 阻塞，paired coverage 不足 | validator pass、OOS pass |
| Stage9 paper smoke | paper smoke only | smoke evidence | no-provider/dry-run/paper-only | live trading、realized PnL、OOS、alaya superiority |

## Current Local Fixes

- PR #6 review comments fixed locally:
  - `gotra/backtest/kimi_probe.py`
  - `scripts/stage8_signal_pnl_backtest.py`
  - `tests/test_kimi_probe.py`
  - `tests/test_stage8_signal_pnl_backtest.py`
- review branch coverage:
  - `kimi_probe.py`: 缺历史点先 skip 再建 prompt，skip path 不估算 prompt/token。
  - `kimi_probe.py`: denoising aggregation 传入 `provider_name="kimi_sophnet"`。
  - `stage8_signal_pnl_backtest.py`: `FULL` / `FULL_PARTIAL` 实际加载 `stage7_full_20260617T123803Z` 的 baseline/alaya 双臂。
  - `stage8_signal_pnl_backtest.py`: reference 缺失时返回 NA，不再用 `next(...)` 触发 `StopIteration`。
  - `stage8_signal_pnl_backtest.py`: compare 含 `missing_candidate_step` 时拒绝用 candidate 子集重构 reference。
  - 两个测试文件覆盖以上 review branches。
- validation:
  - `uv run python -m py_compile gotra/backtest/kimi_probe.py scripts/stage8_signal_pnl_backtest.py`: passed
  - `uv run ruff check --no-cache gotra/backtest/kimi_probe.py scripts/stage8_signal_pnl_backtest.py tests/test_kimi_probe.py tests/test_stage8_signal_pnl_backtest.py`: passed
  - `uv run pytest -q tests/test_kimi_probe.py tests/test_stage8_signal_pnl_backtest.py`: `8 passed`
  - `uv run python scripts/stage8_signal_pnl_backtest.py --summary-only`: passed, reported `MODE=BASELINE_ONLY`, alaya=`NA`, baseline/reference screening only
  - `git diff --check`: passed
  - `uv run pytest -q`: `131 passed`

## Blocking Facts

- replay gate: 当前已知 compare 为 `846/1006 = 0.8409542743538767 < 0.95`，`passed=false`，仍未过 replay gate。
- Stage8.3 full: `stage8_3_oos_v1_full_20260618T134003Z` 为 partial/provider-blocked；full paired coverage 远低于验收要求，`paired scored coverage = 4 / 56 scored = 0.142857`，provider_errors=`2222`。
- ASML: `ASML` price data 缺失仍是 Stage8.3 数据问题之一。
- OOS validator: 不应运行 OOS validator，直到完整且 paired 的 full Stage8.3 run 存在。
- Stage9: paper smoke 与研究/OOS 路线存在路线冲突，不能混成一条验收链。

## Next User Decision Needed

- A. return to `AUTONOMY_RUNBOOK` / system line
- B. separate Stage9 engineering smoke line
- C. close out as provider/replay negative result
