# Stage 8 Signal PnL 离线回测（2026-06-18）

## ⚠️ 先读：BASELINE_ONLY 解释边界

本报告处于 **BASELINE_ONLY** 降级模式。当前 worktree 缺少 `stage7_full_20260617T123803Z` 与 `stage7_repro_20260617T150954Z`，因此没有可用的 alaya full step JSON，不能判断 `alaya vs baseline` 的真双臂经济价值。

本文中的 `reference_from_compare` **不是 alaya**。它来自 `compare_bt_full_v3_20260615.json` 指向的 reference baseline run（`bt_full_v3_20260615`）。因此 `baseline_candidate` vs `reference_from_compare` 的对比，本质是 baseline run A vs baseline run B 的 PnL 对照，不是 alaya 机制 vs baseline 机制。

`compare_bt_full_v3_20260615.json` 显示 baseline candidate 与 reference baseline 的方向一致率为 `846/1006 = 0.840954`，低于 `0.95` replay threshold。故主口径下 `reference_from_compare` 累计收益 1455.40% vs `baseline_candidate` 1017.41% 的差异，应解释为 baseline replay 不稳定下的 PnL 漂移，而不是机制差异。

另外，`expected_change_pct` 口径是强信号过滤：`expected_change_pct >= 2.0` 才 long，`<= -2.0` 才 avoid，其余 neutral/abstain。该口径可作为强信号子集体检，但不得和 LLM 原始 `decision_direction` 口径混读成同一个策略。

因此，本报告唯一稳健结论是：baseline price-only signal 在当前 10 ticker / 月度 / 1006 step 的本地筛查中具备经济性；它不证明 alaya 机制有效，也不证明 alaya 优于 baseline。

## 工作环境

以下为进入字段探测和 PnL 计算前的 worktree 报告：

```text
=== pwd ===
/Users/peachy/Documents/gotra
=== branch ===
codex/stage8-pnl-backtest
=== HEAD ===
bfaf04a
=== status --short ===
?? docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md
?? docs/STAGE8_PNL_BACKTEST_BOUNDARY_AND_GIT_STATE_2026-06-18.md
?? docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md
?? scripts/
=== untracked ===
docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md
docs/STAGE8_PNL_BACKTEST_BOUNDARY_AND_GIT_STATE_2026-06-18.md
docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md
scripts/stage8_signal_pnl_backtest.py
=== data/backtest/runs ===
bt_baseline_parallel_replay4_20260615
bt_codex_baseline_parallel_canary4_20260615
bt_codex_baseline_parallel_canary_20260615
codex_responses_repro_run1
codex_responses_repro_run2
kimi_probe_aggressive_compare_20260617.json
kimi_probe_aggressive_stdout_20260617.json
kimi_probe_stdout_20260617.json
stage3_provider_gate_check_20260615
stage4_repro_baseline_run1_20260616
stage4_repro_baseline_run2_20260616
stage5_repro_n5_run1_20260616
stage5_repro_n5_run2_20260616
stage5_repro_n7_run1_20260616
stage5_repro_n7_run1_retry_20260616
stage7_kimi_no_key_guard_20260617T000000Z
stage7_kimi_probe_aggressive_run1_20260617T081807Z
stage7_kimi_probe_aggressive_run2_20260617T081807Z
stage7_kimi_probe_run1_20260617T081148Z
stage7_kimi_smoke_20260617T094500Z
=== alaya step counts ===
data/backtest/runs/bt_baseline_parallel_replay4_20260615/              baseline=1006 alaya=   0
data/backtest/runs/bt_codex_baseline_parallel_canary4_20260615/        baseline=  40 alaya=   0
data/backtest/runs/bt_codex_baseline_parallel_canary_20260615/         baseline=  40 alaya=   0
data/backtest/runs/codex_responses_repro_run1/                         baseline=   3 alaya=   0
data/backtest/runs/codex_responses_repro_run2/                         baseline=   3 alaya=   0
data/backtest/runs/stage3_provider_gate_check_20260615/                baseline=   0 alaya=   0
data/backtest/runs/stage4_repro_baseline_run1_20260616/                baseline= 126 alaya=   0
data/backtest/runs/stage4_repro_baseline_run2_20260616/                baseline= 126 alaya=   0
data/backtest/runs/stage5_repro_n5_run1_20260616/                      baseline= 126 alaya=   0
data/backtest/runs/stage5_repro_n5_run2_20260616/                      baseline= 126 alaya=   0
data/backtest/runs/stage5_repro_n7_run1_20260616/                      baseline=   5 alaya=   0
data/backtest/runs/stage5_repro_n7_run1_retry_20260616/                baseline=  30 alaya=   0
data/backtest/runs/stage7_kimi_no_key_guard_20260617T000000Z/          baseline=   0 alaya=   0
data/backtest/runs/stage7_kimi_probe_aggressive_run1_20260617T081807Z/ baseline=  19 alaya=   0
data/backtest/runs/stage7_kimi_probe_aggressive_run2_20260617T081807Z/ baseline=  19 alaya=   0
data/backtest/runs/stage7_kimi_probe_run1_20260617T081148Z/            baseline=   5 alaya=   0
data/backtest/runs/stage7_kimi_smoke_20260617T094500Z/                 baseline=   2 alaya=   2
=== compare JSONs ===
data/backtest/runs/bt_baseline_parallel_replay4_20260615/compare_bt_full_v3_20260615.json
=== 目标 run 存在性 ===
MISSING stage7_full_20260617T123803Z
MISSING stage7_repro_20260617T150954Z
EXIST  stage7_kimi_smoke_20260617T094500Z
EXIST  bt_baseline_parallel_replay4_20260615
MISSING glm_probe_a
MISSING glm_probe_b
MISSING kimi_probe_a
MISSING kimi_probe_b
```

补充边界：`/var/minis/shared/gotra/GOTRA_STAGE8_HANDOFF_FOR_MINIS.md` 在本机不存在，所以未能读取 0-1.0 节；报告中的高可信事实均来自当前 worktree 可核验实体文件。

事实分层：
- 用户报告事实：下载提示词中关于 SophNet 非确定性、Stage7 复现闸冻结、Stage8 北极星的叙述。
- 本地可核验事实：当前 worktree、`data/backtest/runs/` step JSON、compare JSON、字段覆盖和本文所有 PnL 指标。

## 数据源模式

模式：**BASELINE_ONLY**

原因：`stage7_full_20260617T123803Z` 与 `stage7_repro_20260617T150954Z` 缺失；`bt_baseline_parallel_replay4_20260615` 存在且 baseline step 数为 1006。按提示词降级规则，本轮跳过真双臂 PnL，改为 baseline candidate 单臂 PnL，并用 `compare_bt_full_v3_20260615.json` 指向的 reference 做参考臂对照。compare JSON 指向的 reference run 实体可读：`/Users/peachy/Documents/gotra-BT-full-monthly/data/backtest/runs/bt_full_v3_20260615`；本文 reference_from_compare 使用该 run 的 baseline step JSON 计算，不是只用 160 条 mismatch 重构。该参考臂不是真双臂 alaya/baseline。

stage7_kimi_smoke_20260617T094500Z 可读：baseline=2 alaya=2，但本轮降级规则为 BASELINE_ONLY，n=2 仅作存在性说明，不进入主 PnL 判断。

## 字段探测结果

```json
{
  "baseline_run": {
    "has_actual_change_pct": true,
    "has_decision_direction": true,
    "has_expected_change_pct": true,
    "has_denoising": false,
    "has_vote_consistency": false,
    "all_keys": [
      "actual_change_pct",
      "arm",
      "audit_actor",
      "cache_hit",
      "cache_namespace",
      "confidence",
      "date",
      "decision_date",
      "decision_direction",
      "decision_inputs",
      "error",
      "estimated_tokens",
      "expected_change_pct",
      "future_data_allowed",
      "mse",
      "outcome_as_of",
      "outcome_inputs",
      "prompt_hash",
      "provider",
      "provider_metadata",
      "provider_network_enabled",
      "reasoning",
      "run_mode",
      "schema",
      "status",
      "step",
      "style_window",
      "ticker",
      "ticker_name",
      "token_usage_source",
      "window_days",
      "window_end_date"
    ],
    "n_steps": 1006,
    "n_actual_non_null": 1006,
    "actual_coverage": "1006/1006 = 1.0000"
  },
  "reference_run": {
    "has_actual_change_pct": true,
    "has_decision_direction": true,
    "has_expected_change_pct": true,
    "has_denoising": false,
    "has_vote_consistency": false,
    "all_keys": [
      "actual_change_pct",
      "arm",
      "audit_actor",
      "cache_hit",
      "cache_namespace",
      "confidence",
      "date",
      "decision_date",
      "decision_direction",
      "decision_inputs",
      "error",
      "estimated_tokens",
      "expected_change_pct",
      "future_data_allowed",
      "mse",
      "outcome_as_of",
      "outcome_inputs",
      "prompt_hash",
      "provider",
      "provider_metadata",
      "provider_network_enabled",
      "reasoning",
      "run_mode",
      "schema",
      "status",
      "step",
      "style_window",
      "ticker",
      "ticker_name",
      "token_usage_source",
      "window_days",
      "window_end_date"
    ],
    "n_steps": 2012,
    "n_actual_non_null": 2012,
    "actual_coverage": "2012/2012 = 1.0000"
  },
  "stage7_smoke": {
    "has_actual_change_pct": true,
    "has_decision_direction": true,
    "has_expected_change_pct": true,
    "has_denoising": true,
    "has_vote_consistency": true,
    "all_keys": [
      "actual_change_pct",
      "arm",
      "audit_actor",
      "cache_hit",
      "cache_namespace",
      "confidence",
      "date",
      "decision_date",
      "decision_direction",
      "decision_inputs",
      "denoising",
      "error",
      "estimated_tokens",
      "expected_change_pct",
      "future_data_allowed",
      "mse",
      "outcome_as_of",
      "outcome_inputs",
      "prompt_hash",
      "provider",
      "provider_metadata",
      "provider_network_enabled",
      "reasoning",
      "run_mode",
      "schema",
      "status",
      "step",
      "style_window",
      "ticker",
      "ticker_name",
      "token_usage_source",
      "window_days",
      "window_end_date"
    ],
    "n_steps": 4,
    "n_actual_non_null": 4,
    "actual_coverage": "4/4 = 1.0000"
  }
}
```

字段覆盖闸：baseline actual coverage 为 1006/1006 = 1.0000，满足 `>=0.99` 后进入 PnL 计算。

## 交易口径声明

- `AVOID_AS_SHORT=False`：long=+1，avoid=0，short=-1，neutral/watch=0。
- `AVOID_AS_SHORT=True`：long=+1，avoid=-1，short=-1，neutral/watch=0。
- 成本跑两版：`COST_BPS=10` 与 `COST_BPS=0`；无风险利率 `RISK_FREE_RATE=0.0`。
- 单期收益：`position * actual_change_pct / 100`。
- 组合月收益：每个 `decision_date` 对当期非零仓位 ticker 等权；交易成本按单边仓位变化计，分母优先使用当期非零持仓 ticker 数；若当期全空仓但有清仓成本，则使用上期非零持仓数避免除零。
- 两套方向口径均计算：LLM 原始 `decision_direction`，以及 `expected_to_direction(expected_change_pct)`：`>=2.0` 为 long，`<=-2.0` 为 avoid，否则 neutral。
- reference 参考臂有实体 step JSON，因此同时计算 `decision_direction` 和 `expected_change_pct` 推算两套方向口径。
- vote 阈值 / 成本 / 无风险利率是评估口径，不是信号口径。

## 经济指标表

| arm | direction source | AVOID_AS_SHORT | cost bps | 累计收益 | 年化收益 | 夏普 | 最大回撤 | 方向命中率 | 胜率 | 盈亏比 | 交易次数 | abstain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_candidate | decision_direction | False | 10.0 | 1017.41% | 30.44% | 1.316 | 27.58% | 62.11% | 70.64% | 1.170 | 615 | 38.87% |
| baseline_candidate | expected_change_pct | False | 10.0 | 2597.85% | 43.73% | 1.332 | 39.00% | 64.13% | 65.14% | 1.578 | 407 | 59.54% |
| reference_from_compare | reference_direction | False | 10.0 | 1455.40% | 35.27% | 1.448 | 26.91% | 61.23% | 70.64% | 1.344 | 632 | 37.18% |
| reference_from_compare | expected_change_pct | False | 10.0 | 1965.14% | 39.56% | 1.269 | 41.22% | 63.57% | 62.39% | 1.652 | 409 | 59.34% |
| buy_hold_equal_weight | decision_direction | False | 10.0 | 462.79% | 20.95% | 0.858 | 48.88% | 53.08% | 56.88% | 1.470 | 1006 | 0.00% |
| baseline_candidate | decision_direction | False | 0.0 | 1154.99% | 32.11% | 1.376 | 26.95% | 62.11% | 71.56% | 1.168 | 615 | 38.87% |
| baseline_candidate | expected_change_pct | False | 0.0 | 2956.90% | 45.72% | 1.378 | 38.45% | 64.13% | 65.14% | 1.424 | 407 | 59.54% |
| reference_from_compare | reference_direction | False | 0.0 | 1655.46% | 37.09% | 1.506 | 26.00% | 61.23% | 70.64% | 1.408 | 632 | 37.18% |
| reference_from_compare | expected_change_pct | False | 0.0 | 2251.04% | 41.57% | 1.320 | 40.12% | 63.57% | 62.39% | 1.472 | 409 | 59.34% |
| buy_hold_equal_weight | decision_direction | False | 0.0 | 463.59% | 20.97% | 0.859 | 48.88% | 53.08% | 56.88% | 1.470 | 1006 | 0.00% |
| baseline_candidate | decision_direction | True | 10.0 | 1013.24% | 30.38% | 1.314 | 27.58% | 62.18% | 70.64% | 1.169 | 616 | 38.77% |
| baseline_candidate | expected_change_pct | True | 10.0 | 1275.95% | 33.46% | 1.585 | 17.08% | 61.68% | 70.64% | 1.393 | 668 | 33.60% |
| reference_from_compare | reference_direction | True | 10.0 | 1423.13% | 34.96% | 1.439 | 26.91% | 61.14% | 70.64% | 1.337 | 633 | 37.08% |
| reference_from_compare | expected_change_pct | True | 10.0 | 1458.12% | 35.30% | 1.581 | 19.89% | 60.80% | 71.56% | 1.354 | 676 | 32.80% |
| buy_hold_equal_weight | decision_direction | True | 10.0 | 462.79% | 20.95% | 0.858 | 48.88% | 53.08% | 56.88% | 1.470 | 1006 | 0.00% |
| baseline_candidate | decision_direction | True | 0.0 | 1150.18% | 32.06% | 1.374 | 26.95% | 62.18% | 71.56% | 1.167 | 616 | 38.77% |
| baseline_candidate | expected_change_pct | True | 0.0 | 1432.16% | 35.05% | 1.647 | 16.87% | 61.68% | 70.64% | 1.460 | 668 | 33.60% |
| reference_from_compare | reference_direction | True | 0.0 | 1618.24% | 36.76% | 1.497 | 26.00% | 61.14% | 70.64% | 1.401 | 633 | 37.08% |
| reference_from_compare | expected_change_pct | True | 0.0 | 1638.51% | 36.94% | 1.640 | 19.70% | 60.80% | 71.56% | 1.417 | 676 | 32.80% |
| buy_hold_equal_weight | decision_direction | True | 0.0 | 463.59% | 20.97% | 0.859 | 48.88% | 53.08% | 56.88% | 1.470 | 1006 | 0.00% |

## vote_consistency 阈值扫描

跳过：bt_baseline_parallel_replay4_20260615 是单 sample，denoising=null，没有 vote_consistency 字段。

## 逐 ticker 拆解：baseline candidate（decision_direction, AVOID_AS_SHORT=False, COST_BPS=10）

| ticker | 收益贡献 | 单票累计 | 命中率 | 交易数 | 累计贡献% |
| --- | --- | --- | --- | --- | --- |
| NVDA | 55.06% | 69.50% | 63.89% | 72 | 19.77% |
| AAPL | 43.42% | 52.42% | 69.86% | 73 | 35.37% |
| 1810.HK | 32.47% | 36.26% | 55.56% | 54 | 47.03% |
| 3690.HK | 31.38% | 33.71% | 54.72% | 53 | 58.30% |
| MSFT | 31.12% | 35.21% | 69.62% | 79 | 69.48% |
| 9988.HK | 22.18% | 23.48% | 57.50% | 40 | 77.44% |
| 0700.HK | 19.86% | 20.92% | 57.63% | 59 | 84.57% |
| 1211.HK | 19.74% | 19.87% | 58.93% | 56 | 91.66% |
| TSM | 16.74% | 16.64% | 65.71% | 70 | 97.68% |
| 6060.HK | 6.47% | 3.70% | 59.32% | 59 | 100.00% |

去最大贡献 ticker：top=NVDA；去掉后 baseline candidate 累计收益=688.98%，夏普=1.107。

## 逐 ticker 拆解：reference_from_compare（reference_direction, AVOID_AS_SHORT=False, COST_BPS=10）

| ticker | 收益贡献 | 单票累计 | 命中率 | 交易数 | 累计贡献% |
| --- | --- | --- | --- | --- | --- |
| NVDA | 91.09% | 136.95% | 63.77% | 69 | 29.07% |
| TSM | 42.28% | 51.24% | 69.44% | 72 | 42.56% |
| 1810.HK | 41.48% | 48.39% | 61.40% | 57 | 55.80% |
| AAPL | 40.98% | 49.19% | 68.42% | 76 | 68.87% |
| 3690.HK | 39.56% | 45.32% | 55.56% | 54 | 81.50% |
| 0700.HK | 27.54% | 30.71% | 62.90% | 62 | 90.29% |
| MSFT | 14.92% | 15.38% | 64.86% | 74 | 95.05% |
| 9988.HK | 7.79% | 7.14% | 48.78% | 41 | 97.53% |
| 1211.HK | 4.24% | 2.82% | 54.69% | 64 | 98.89% |
| 6060.HK | 3.49% | 0.58% | 53.97% | 63 | 100.00% |

## 基准对照

buy & hold 等权同周期见经济指标表中的 `buy_hold_equal_weight` 行。随机方向基线为 N=10000，随机 long/avoid，使用同一成本和 AVOID_AS_SHORT 设置：

| arm | AVOID_AS_SHORT | cost bps | random P5 | random P50 | random P95 | 策略百分位 |
| --- | --- | --- | --- | --- | --- | --- |
| baseline_candidate | False | 0.0 | 176.59% | 418.07% | 887.43% | 98.8 |
| reference_from_compare | False | 0.0 | 176.59% | 418.07% | 887.43% | 99.9 |
| baseline_candidate | False | 10.0 | 143.07% | 357.84% | 770.52% | 98.9 |
| reference_from_compare | False | 10.0 | 143.07% | 357.84% | 770.52% | 99.9 |
| baseline_candidate | True | 0.0 | -55.47% | -8.15% | 83.74% | 100.0 |
| reference_from_compare | True | 0.0 | -55.47% | -8.15% | 83.74% | 100.0 |
| baseline_candidate | True | 10.0 | -60.10% | -17.63% | 64.58% | 100.0 |
| reference_from_compare | True | 10.0 | -60.10% | -17.63% | 64.58% | 100.0 |

主口径下 baseline candidate 随机百分位=98.9，reference 随机百分位=99.9。

## MSE 辅助

缺 stage7_repro 与 alaya full/repro，跳过 baseline run 间噪声基线和 alaya-baseline MSE 对照。可核验 baseline candidate 自身 mse：count=1006, mean=161.179, median=45.879。该项仅为辅助参考，不作为主判断。

## 零未来函数声明

信号生成时刻 t 不包含 actual，actual 仅用于 t+1 结算，符合回测标准口径。`decision_inputs[*].availability_date <= decision_date` 已在 walk_forward harness 验证；当前 1006 个 baseline step 的 `future_data_allowed` 均为 `[False]`。本脚本没有用 `actual_change_pct` 生成信号。

## 主判断

1. 降级模式：**BASELINE_ONLY**，数据不足以下真双臂 alaya vs baseline 判断。
2. 关键经济指标（主口径 AVOID_AS_SHORT=False, COST_BPS=10）：
   - alaya：NA（无 full alaya step）。
   - baseline candidate：累计收益 1017.41%，夏普 1.316, 最大回撤 27.58%。
   - reference_from_compare：累计收益 1455.40%，夏普 1.448, 最大回撤 26.91%。
   - buy & hold：累计收益 462.79%，夏普 0.858, 最大回撤 48.88%。
3. vote_consistency 结论：跳过；baseline candidate 没有 vote_consistency。
4. 逐 ticker 拆解结论：baseline candidate top ticker=NVDA；单票支配=false；去最大单票后 PnL 转负=false。
5. screening 判断：数据不足以下真双臂判断（BASELINE_ONLY）：没有 stage7_full/stage7_repro，无法判断 alaya 方向信号是否优于 baseline。baseline/reference 的单臂结果只能作为 Stage8 经济学筛查的本地基线，不构成机制有效性结论。
6. 验证状态：rerun=ok rg=ok py_compile=ok ruff=ok diff_check=ok。
7. 产物路径：脚本 `scripts/stage8_signal_pnl_backtest.py`；报告 `docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md`。
8. 诚实边界：本结果是 screening 非最终验证；没有 stage7 full/repro，不能给 alaya 机制经济价值结论；零未来函数已声明；交易假设全部标注；key 未接触；未 push。

## compare JSON 摘要

- reference_run: `/Users/peachy/Documents/gotra-BT-full-monthly/data/backtest/runs/bt_full_v3_20260615`
- candidate_run: `data/backtest/runs/bt_baseline_parallel_replay4_20260615`
- total=1006, same=846, rate=0.841, threshold=0.950, passed=False
