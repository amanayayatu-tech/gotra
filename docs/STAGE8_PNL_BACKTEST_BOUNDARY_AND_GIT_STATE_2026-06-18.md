# Stage 8 PnL 回测解释边界与 Git 状态审计（2026-06-18）

## 1. 执行摘要

- 当前模式：BASELINE_ONLY。
- 是否可判断 alaya vs baseline：否。当前 worktree 缺少 `stage7_full_20260617T123803Z` 与 `stage7_repro_20260617T150954Z`，没有可用的 alaya full step JSON。
- Stage7 脏状态结论：当前 staged 改动是既有 Kimi provider smoke/wiring，不是本轮 Stage8 PnL 污染。
- Stage8 新产物：`scripts/stage8_signal_pnl_backtest.py`（50512 bytes）、`docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md`（18510 bytes）、本文档。
- 是否触碰 provider/key/run/push：否。

## 2. Worktree 实况

强制 preflight 核心输出如下：

```text
=== pwd ===
/Users/peachy/Documents/gotra
=== branch ===
codex/stage8-pnl-backtest
=== HEAD ===
d44afa7
=== status --short ===
A  docs/STAGE7_KIMI_SMOKE_2026-06-17.md
M  gotra/backtest/walk_forward.py
M  tests/test_backtest_walk_forward.py
?? docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md
?? docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md
?? scripts/
=== staged diff stat ===
 docs/STAGE7_KIMI_SMOKE_2026-06-17.md | 153 +++++++++++++++++++++++++++++++++++
 gotra/backtest/walk_forward.py       |  81 ++++++++++++++++---
 tests/test_backtest_walk_forward.py  |  72 +++++++++++++++++
 3 files changed, 297 insertions(+), 9 deletions(-)
=== unstaged diff stat ===
=== untracked ===
docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md
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
=== target runs ===
MISSING:stage7_full_20260617T123803Z
MISSING:stage7_repro_20260617T150954Z
EXIST:stage7_kimi_smoke_20260617T094500Z
EXIST:bt_baseline_parallel_replay4_20260615
MISSING:glm_probe_a
MISSING:glm_probe_b
MISSING:kimi_probe_a
MISSING:kimi_probe_b
```

`[PREFLIGHT_VERDICT] safe_to_edit_docs_only=yes; reason=当前只有提示词列出的既有 Stage7 staged 改动和 Stage8 untracked 产物，没有未知大改动；本任务只改 Stage8 报告、Stage8 脚本生成逻辑和新增审计文档。`

## 3. Git 脏状态分层

### 3.1 既有 Stage7 staged 改动

当前 staged 文件：

```text
A docs/STAGE7_KIMI_SMOKE_2026-06-17.md
M gotra/backtest/walk_forward.py
M tests/test_backtest_walk_forward.py
```

这些 staged 改动属于 Stage7 Kimi provider smoke / wiring：

- `ProviderName` 与 CLI `--provider` choices 增加 `kimi`。
- `_build_provider("kimi")` 接入 `KimiCompletionClient`。
- preflight、provider error fuse、provider metadata、determinism metadata 支持 `kimi`。
- `kimi` 复用既有 median-denoising sampling config。
- tests 增加 Kimi provider construction、missing key、determinism、parse args、denoising 相关覆盖。
- `docs/STAGE7_KIMI_SMOKE_2026-06-17.md` 是 Kimi smoke 报告。

这些是既有 staged 改动，不是 Stage8 PnL 回测脚本新引入的改动。Git 切分支会保留 index 与 untracked 文件，因此它们会跟随当前 worktree 出现在 `codex/stage8-pnl-backtest` 上。本任务没有 `reset`、没有 `clean`、没有 `stash`，也没有改写这些 staged 内容。

### 3.2 Stage8 untracked 产物

Stage8 相关 untracked 产物：

```text
scripts/stage8_signal_pnl_backtest.py
docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md
docs/STAGE8_PNL_BACKTEST_BOUNDARY_AND_GIT_STATE_2026-06-18.md
```

用途分层：

- `scripts/stage8_signal_pnl_backtest.py`：离线 PnL 筛查脚本，只读 step/compare JSON，写 Stage8 报告，不写 `data/backtest/runs/`。
- `docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md`：Stage8 PnL 回测报告，当前已在标题后加入 `BASELINE_ONLY` 解释边界。
- `docs/STAGE8_PNL_BACKTEST_BOUNDARY_AND_GIT_STATE_2026-06-18.md`：本文档，记录解释边界和 Git 脏状态分层。

另有 `docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md` 为既有 untracked 文档，不属于本轮 Stage8 PnL 产物。

### 3.3 不建议直接 git add . 的原因

不建议直接运行 `git add .`，因为当前 worktree 同时包含：

- 既有 staged Stage7 Kimi provider smoke/wiring；
- Stage8 PnL 脚本与报告；
- 既有 untracked `docs/CODEX_RESPONSES_REPRO_CHECK_2026-06-16.md`。

直接 `git add .` 会把 Stage7、Stage8 和无关 untracked 文档混入同一提交，破坏证据边界和审计可读性。

### 3.4 推荐 Git 处理方式

1. 保持现状，只读报告：不 commit、不 push，继续把 Stage8 结论作为本地审计产物。
2. 分两个 commit：先提交 Stage7 Kimi smoke/wiring，再提交 Stage8 PnL 脚本、报告和本审计文档。
3. 只提交 Stage8：必须 path 限定，例如只 stage `scripts/stage8_signal_pnl_backtest.py`、`docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md`、`docs/STAGE8_PNL_BACKTEST_BOUNDARY_AND_GIT_STATE_2026-06-18.md`，并且不要改动既有 index 中的 Stage7 staged 文件。

## 4. Stage8 PnL 报告解释边界

Stage8 PnL 报告现在必须按以下边界阅读：

- 当前是 `BASELINE_ONLY`，不是 alaya vs baseline 真双臂 PnL。
- `reference_from_compare` 不是 alaya；它是 `compare_bt_full_v3_20260615.json` 指向的 reference baseline run（`bt_full_v3_20260615`）。
- `baseline_candidate` vs `reference_from_compare` 是 baseline run A vs baseline run B，不是机制 A vs 机制 B。
- compare JSON 显示 `same=846 / total=1006`，`rate=0.8409542743538767`，低于 `threshold=0.95`，所以 reference 1455.40% vs baseline candidate 1017.41% 的差异应解释为 baseline replay 不稳定下的 PnL 漂移。
- `expected_change_pct` 口径是强信号过滤：`expected_change_pct >= 2.0` 才 long，`<= -2.0` 才 avoid，其余 neutral/abstain；该口径交易覆盖更低、abstain 更高，可以作为强信号子集体检，但不能和 LLM 原始 `decision_direction` 口径混读成同一个策略。
- 唯一稳健结论：baseline price-only signal 在当前 10 ticker / 月度 / 1006 step 的本地筛查中具备经济性；它不证明 alaya 机制有效，也不证明 alaya 优于 baseline。

## 5. 已执行修订

已在 `docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md` 标题后新增：

```text
## ⚠️ 先读：BASELINE_ONLY 解释边界
```

同时已修改 `scripts/stage8_signal_pnl_backtest.py` 的报告生成模板，使重新运行脚本后该小节仍会被生成，不会被覆盖丢失。

## 6. 验证结果

已执行验证：

```text
python3 scripts/stage8_signal_pnl_backtest.py
rg -n "## ⚠️ 先读：BASELINE_ONLY 解释边界" docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md
uv run python -m py_compile scripts/stage8_signal_pnl_backtest.py
uv run ruff check . --force-exclude
git diff --check
git status --short
```

结果：

- rerun：ok。重跑脚本后 `docs/STAGE8_SIGNAL_PNL_BACKTEST_2026-06-18.md` 仍包含 `## ⚠️ 先读：BASELINE_ONLY 解释边界`。
- py_compile：ok。
- ruff：ok。
- diff_check：ok。
- status：ok；仍为既有 Stage7 staged 改动 + Stage8 untracked 产物，没有 commit，没有 push。

## 7. 下一步建议

- 如果目标是正式结论：需要 alaya full run，或明确承认数据不足，不能把 `BASELINE_ONLY` 升级成 alaya 机制结论。
- 如果目标是 Git 卫生：拆 commit，不要 `git add .`。
- 如果目标是方法论收尾：把 `BASELINE_ONLY` 作为诚实负结果/数据不足结果冻结到 handoff。
