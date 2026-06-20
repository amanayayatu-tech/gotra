# Gotra Route Reset and Evidence Freeze（2026-06-18）

## 1. 执行摘要

- repo/root: `/Users/peachy/Documents/gotra`
- branch/head: `codex/stage8-pnl-backtest @ a408315`
- remote: `https://github.com/amanayayatu-tech/gotra.git`
- PR #6: `OPEN`, title=`Add Stage 4-8 reproducibility and baseline-only PnL screening`, headRef=`codex/stage8-pnl-backtest`, headRefOid=`a408315e31f729d92479fdc455e215c2fd35f016`, url=`https://github.com/amanayayatu-tech/gotra/pull/6`
- 本任务是路线冻结、证据分账、PR #6 review-fix 核验与受控推送，不是新实验，不是 rerun，不是 OOS validator，不是 paper trading 推进。
- 当前最重要结论：暂停新 provider/OOS/validator/paper-trading 推进，先把证据和 PR 边界分清。

## 2. Worktree 实况

Preflight 核心结果：

```text
cwd: /Users/peachy/Documents/gotra
project: gotra (bridge/control repo and reproducibility experiments)
git root: /Users/peachy/Documents/gotra
branch/head: codex/stage8-pnl-backtest a408315
remote: https://github.com/amanayayatu-tech/gotra.git
worktree: /Users/peachy/Documents/gotra refs/heads/codex/stage8-pnl-backtest
PR #6: OPEN, headRef=codex/stage8-pnl-backtest, headRefOid=a408315e31f729d92479fdc455e215c2fd35f016
```

Tracked modified files：

```text
gotra/backtest/kimi_probe.py
scripts/stage8_signal_pnl_backtest.py
tests/test_kimi_probe.py
```

Allowed untracked PR #6 review-fix file：

```text
tests/test_stage8_signal_pnl_backtest.py
```

旧 Stage8 / Stage8.3 / Stage9 local artifacts，不属于 PR #6 review-fix，本轮不删除、不清理、不 stage 到 PR #6：

```text
STATUS.md
data/paper_trading/
docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md
docs/PR6_REVIEW_CHECKLIST_2026-06-18.md
docs/STAGE8_2_*.md/csv
docs/STAGE8_3_*.md/csv
docs/STAGE8_DUAL_ARM_*.md
docs/STAGE8_FINAL_BOUNDARY_AND_NEXT_DECISION_2026-06-18.md
docs/STAGE8_STAGE9_HANDOFF_STATUS_2026-06-18.md
docs/STAGE9_FORWARD_PAPER_TRADING_FIRST_RESULT_2026-06-18.md
scripts/stage8_2_oos_validation_design.py
scripts/stage8_3_generate_oos_data.py
scripts/stage8_dual_arm_*.py
scripts/stage9_forward_paper_trading.py
tests/test_stage8_3_generate_oos_data.py
```

Recent run artifacts：

```text
data/backtest/runs/stage8_3_oos_v1_full_20260618T134003Z
data/backtest/runs/stage8_3_oos_v1_canary_20260618T133650Z
data/backtest/runs/stage8_3_oos_v1_canary_20260618T133426Z
data/backtest/runs/stage7_kimi_smoke_20260617T094500Z
data/backtest/runs/stage7_kimi_no_key_guard_20260617T000000Z
data/backtest/runs/stage7_kimi_probe_aggressive_run2_20260617T081807Z
data/backtest/runs/stage7_kimi_probe_aggressive_run1_20260617T081807Z
data/backtest/runs/stage7_kimi_probe_run1_20260617T081148Z
data/backtest/runs/stage5_repro_n5_run1_20260616
```

## 3. PR #6 边界

- PR #6 当前只代表 Stage4-8 baseline-only / reproducibility chain review surface。
- PR #6 不包含 Stage8.3 OOS data generation、Stage8.3 validator、Stage9 paper smoke、`data/paper_trading/` 或 run artifacts。
- 本轮 5 条 diff comments 的本地修复文件：
  - `gotra/backtest/kimi_probe.py`
  - `scripts/stage8_signal_pnl_backtest.py`
  - `tests/test_kimi_probe.py`
  - `tests/test_stage8_signal_pnl_backtest.py`
- 本轮 prompt 已授权一次受控 path-limited Git flow；更新 PR #6 只能 stage/commit/push 上述 4 个 review-fix 文件。

Review-fix 核验：

- `kimi_probe.py`：缺历史点先 skip 再建 prompt，skip path 不生成 prompt hash，不估算 token。
- `kimi_probe.py`：denoising aggregation 传入 `provider_name="kimi_sophnet"`。
- `stage8_signal_pnl_backtest.py`：`FULL` / `FULL_PARTIAL` 实际加载 `stage7_full_20260617T123803Z` 的 baseline/alaya 双臂。
- `stage8_signal_pnl_backtest.py`：reference 缺失时使用 nullable primary result，render/report 输出 NA，不再 `StopIteration`。
- `stage8_signal_pnl_backtest.py`：含 `missing_candidate_step` 时拒绝用 candidate 子集重构 reference。
- `tests/test_kimi_probe.py` 和 `tests/test_stage8_signal_pnl_backtest.py` 覆盖以上 review branches。

## 4. Evidence Ledger

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

## 5. Stage8.3 Provider-Blocked 判定

- Canary complete: `data/backtest/runs/stage8_3_oos_v1_canary_20260618T133650Z` 完成 baseline=4、alaya=4、paired scored=4、provider_errors=0，证明小规模 provider/run path 可用。
- Full partial: `data/backtest/runs/stage8_3_oos_v1_full_20260618T134003Z` 只形成 partial data-generation evidence。
- Full V1 provider/runtime blocker: `system_health.status=failed`，dominant observed error 为 SophNet/Kimi HTTP 429，`Rate limit exceeded. Please try again later.`
- Full V1 paired coverage 不足：`paired scored coverage = 4 / 56 scored = 0.142857`，低于 `0.95`。
- Full V1 provider_errors=`2222`，质量摘要失败项包括 provider_errors 与 paired_step_coverage。
- `ASML` price data 缺失仍是 Stage8.3 数据问题之一。
- 不运行 OOS validator，直到完整且 paired 的 full Stage8.3 run 存在。
- Replay gate 仍未过：`compare_bt_full_v3_20260615.json` 当前为 `846/1006 = 0.8409542743538767 < 0.95`，`passed=false`。

## 6. Stage9 / Paper Smoke 隔离

- Stage9 当前只是 paper smoke / no-provider dry-run 证据。
- Stage9 不得混入 OOS、Stage8.3 validator 或 PR #6。
- `data/paper_trading/` 不应进入当前 review-fix commit。
- Stage9 paper smoke 与研究/OOS 路线存在路线冲突，不能混成一条验收链。
- Stage9 不能被描述为 live trading、realized PnL、OOS pass、alaya superiority 或 science/public claim。

## 7. 回到总项目目标

`AUTONOMY_RUNBOOK` 原主线是 gotra 自主化系统 + 可审计 BT harness，不是无限 Stage8.x 实验。后续只能三选一：

- A. 回 `AUTONOMY_RUNBOOK` 系统主线：Phase / guardrails / provider hardening / Judge / autonomy。
- B. 单独工程 smoke 路线：Stage9 paper-only，独立分支，独立状态，绝不声称 OOS。
- C. 方法论负结果/收尾路线：冻结 SophNet replay/provider-blocker，写 postmortem/whitepaper。

## 8. 推荐下一步

- 默认推荐：先提交 PR #6 review-fix 的 4 个文件，随后单独 docs-only route-freeze PR。
- 在用户选择路线前，不要 resume Stage8.3 full，不要跑 validator，不要扩大 paper trading。
- 同事 review 之前，不继续新实验。

## 9. Validation

```text
uv run python -m py_compile gotra/backtest/kimi_probe.py scripts/stage8_signal_pnl_backtest.py
result: passed

uv run ruff check --no-cache gotra/backtest/kimi_probe.py scripts/stage8_signal_pnl_backtest.py tests/test_kimi_probe.py tests/test_stage8_signal_pnl_backtest.py
result: passed; output included "All checks passed!"

uv run pytest -q tests/test_kimi_probe.py tests/test_stage8_signal_pnl_backtest.py
result: passed; 8 passed

uv run python scripts/stage8_signal_pnl_backtest.py --summary-only
result: passed; key output:
- [MODE] BASELINE_ONLY
- [DATA] baseline_runs=bt_baseline_parallel_replay4_20260615:1006 alaya_runs=stage7_full_20260617T123803Z:0
- [PNL_AVOID_SHORT=False] alaya: NA | baseline: cumret=1017.41% sharpe=1.316 mdd=27.58% hit=62.11% | reference: cumret=1455.40% sharpe=1.448 mdd=26.91% hit=61.23%
- [VERDICT] Stage8 PnL screening；正式 replay acceptance/provider health/science claim 需分层判断
- [KEY_TOUCHED] no
- [PUSHED] no

git diff --check
result: passed

uv run pytest -q
result: passed; 131 passed
```

## 10. Git 操作建议

- 不要 `git add .`。
- Option 1: PR #6 review-fix path-limited file list：

```text
gotra/backtest/kimi_probe.py
scripts/stage8_signal_pnl_backtest.py
tests/test_kimi_probe.py
tests/test_stage8_signal_pnl_backtest.py
```

- Option 2: route-freeze docs-only path-limited file list：

```text
STATUS.md
docs/GOTRA_ROUTE_RESET_AND_EVIDENCE_FREEZE_2026-06-18.md
```

- Explicit exclusions:

```text
data/paper_trading/
data/backtest/runs/
data/backtest/prices/
*.env
*.key
provider logs
docs/STAGE9_FORWARD_PAPER_TRADING_FIRST_RESULT_2026-06-18.md
scripts/stage9_forward_paper_trading.py
Stage8.3 run artifacts
any key/env/provider file
```
