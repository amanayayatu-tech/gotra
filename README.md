# GOTRA

> **GOTRA / gotra** 记录一次投研判断的血脉：signal、prediction、evidence、outcome、
> error attribution、feedback、provenance，以及可审计、可复盘的知识状态。

GOTRA 是一个 AI 原生、可审计、可复盘的投研研究工作流与内容/研究基础设施。它的目标是让研究判断、证据、预测、结果和反馈可以被追踪和复核，而不是提供荐股、自动交易或收益承诺。

当前项目状态：内部工程与研究证据阶段。当前 `main` 已包含 Stage4-8、Baseline v2/v3/v3.1/v3.2/v3.3/v3.4/v3.5A 文档与代码路径，包括本地 harness、provider/backend 实验、deterministic reference 和 forward-live capture plumbing。除非某个后续文档明确升级证据层级，否则这些内容默认不构成外部验证、公开证明或科学结论，也不构成交易或投资建议。

## 项目定位

GOTRA 用来：

- 记录带审计元数据的研究判断和预测；
- 把研究证据、价格上下文、反馈和 provenance 绑定到判断链路；
- 通过 Judge Agent 和可人工复核的闸门处理高风险知识决策；
- 在明确 no-future-data 约束下回放历史实验；
- 在结果成熟前捕获 future-live 决策；
- 把工程/runtime 健康、内部研究结果、强证据结论和交易/投资断言分开。

GOTRA 不是：

- 个性化财务建议；
- 自动交易机器人；
- 接券商下单的执行系统；
- 收益保证或利润承诺系统；
- “GOTRA、ksana、alaya 或某个 LLM 可以预测市场”的证明。

## 当前架构

当前仓库主要由以下层组成：

| 层 | 职责 | 主要入口 |
| --- | --- | --- |
| Research / signal generation | 构造价格包、研究包和受控实验 prompt。 | `scripts/baseline_v3_four_arm.py`, `gotra/perplexity_executor/`, `integrations/alaya/` |
| Judge gate / decision routing | 判断 gate candidate，持久化 decision provenance，支持 dry-run polling，保持 strong promotion human-only。 | `gotra/judge_agent/`, `scripts/gate_poller.py`, `gotra/judge_agent/prompts/` |
| Alaya knowledge / feedback layer | 表达 active/strong knowledge 上下文，同步 gates，生成 outcome-derived feedback artifacts，并保持 feedback eligibility 可审计。 | `integrations/alaya/`, `gotra/judge_agent/outcome_feedback.py` |
| Backtest / formal-lite harness | 运行 local/mock/provider/backend grid，计算诊断指标，并执行 no-future-data 与 artifact 边界。 | `gotra/backtest/`, `scripts/baseline_v3_four_arm.py`, `gotra/backtest/statistics.py` |
| Deterministic reference | 提供不调用 LLM/backend/provider 的 cleaner price-only 历史参考。 | v3.4b/v3.4c summary 中的 `deterministic_price_only_baseline` 字段 |
| Forward-live capture | 在 outcome 成熟前捕获 future-only 决策，记录 prompt hash、decision hash 和可选 Codex CLI transcript path。 | `scripts/baseline_v3_5_forward_live_capture.py` |
| Outcome maturity / scoring | 计划中的下一层，只在 horizon 成熟后评分 captured decisions。 | v3.5B planned；v3.5A capture 不做 outcome scoring |
| Evidence / provenance artifacts | 用文档和本地 runtime artifacts 保持每次实验可检查，同时不提交 raw provider output。 | `docs/`, `data/backtest/*.md`, ignored `data/backtest/runs/*` |

旧的 Kimi/GLM/DeepSeek provider API formal-lite/parser 线、新的 `codex_cli_llm_backend` experiment family、deterministic references、forward-live capture path 是不同证据族，不能合并解释成同一个结果。

## 证据梯度

阅读本仓库时请按以下证据层级解释：

| 层级 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| local checks | 代码可导入、确定性测试、lint、fixture 行为、artifact hygiene。 | provider 可靠性、市场 edge、OOS 有效性。 |
| provider/runtime health | 某个 provider/backend 在特定 grid 下能返回 schema-valid decisions。 | replay 有效、科学验收、投资有效。 |
| mock/canary/tiny smoke | 小范围路径在扩容前可跑通。 | formal acceptance 或公开证明。 |
| formal-lite internal research | 预注册内部 grid 完成或失败，并留下诊断记录。 | 外部验证、科学结论、公开证明或交易/投资断言。 |
| forward-live capture | 未来结果发生前，决策已被捕获。 | outcome matured pass；必须等 horizon 成熟后评分。 |
| Mature external proof layer | 需要单独记录的成熟、验收协议。 | 默认不由本 repo 当前状态声称。 |
| Trading/investment assertion | 需要完全不同的合规与证据层。 | 本项目不声称。 |

当前仓库证据默认是 internal engineering/research evidence。除非未来某个命名 artifact 明确升级证据层级，否则不要把局部 smoke、provider health、formal-lite internal run 或 forward-live capture 说成更强结论。

## Direct LLM Caveat

历史 direct-LLM shorthand 必须解释为 `direct_llm_parametric_memory_control`。

它不是干净的 no-future historical baseline。即使 prompts、input packets 和 artifact filters 都限制到 `decision_date`，现代 LLM 的参数记忆也可能包含后来的市场叙事。prompt 和 artifact gate 可以降低显式 future-data 泄漏，但不能抹掉 parametric memory。

因此：

- `direct_llm_parametric_memory_control` metrics 只能作为诊断；
- C1/C3/C5、return、MSE、MAE、direction-hit 等包含 `direct_llm_parametric_memory_control` 的指标，不得用来证明或反驳 GOTRA、ksana、alaya 的成功或失败；
- 更适合历史 alaya-style 解释的比较是 `ksana_real_research` vs `full_gotra`，并且仍然受 internal-evidence 边界约束；
- 更干净的 baseline 是 deterministic price-only 或 simple statistical reference；
- 最可信的未来导向路径是 forward-live/future-only capture，并在 outcome 成熟后再评分。

详见 [`docs/GOTRA_DIRECT_LLM_INTERPRETATION_BOUNDARY_2026-06-20.md`](docs/GOTRA_DIRECT_LLM_INTERPRETATION_BOUNDARY_2026-06-20.md)。

## Baseline 演进摘要

以下是当前主线的审慎时间线，不是市场优越性声明：

- **Stage4-8**：reproducibility、replay gate、provider routing 和 baseline-only signal/PNL screening。它们改进了审计 harness 并明确失败边界，但没有建立公开市场有效性证明。
- **Baseline v2 / v3**：四臂实验族，比较 `direct_llm_parametric_memory_control`、`ksana_formatting_only`、`ksana_real_research`、`full_gotra`，并区分 `price_only_packet` 与 `richer_research_packet`。Baseline v3 formal-lite 属于内部研究证据，强结论仍为 inconclusive。
- **v3.1 / v3.2**：real-evidence 和 true-independent feedback substrate。v3.1 保持 H2 data-insufficient；v3.2 引入更严格的 feedback eligibility，并在 formal-lite attempt 中暴露 provider contract blocker。
- **v3.3a-d**：Judge decision provenance、dry-run gate polling、outcome-derived feedback artifact production、temporal replay/calibration、prompt/spec hardening。这些是 local engineering 和 replay/calibration evidence。
- **v3.4 / v3.4b / v3.4c**：新的 `codex_cli_llm_backend` experiment family、transcript/hash metadata、deterministic price-only reference integration 和 scaled internal run。这些是 internal backend/reference diagnostics，不是外部验证或公开科学结论。
- **v3.5A**：forward-live/future-only decision capture path。它可以在 outcome 发生前捕获决策；outcome scoring 必须等 horizon 成熟。

## 当前不声称

本仓库当前不声称：

- 默认已经具备外部验证、公开证明或科学结论；
- 任何交易或投资推荐；
- provider health、Codex CLI backend health 或 CI success 等于 market edge；
- forward-live capture 等于 matured outcome pass；
- `direct_llm_parametric_memory_control` 是干净的 no-future baseline；
- product metrics 本身可以证明预测质量或投资价值。

如果某个 run 写着 `PROVIDER_PILOT_PASS`、`FORMAL_LITE_MIN_INTERNAL_PASS`、`SCALED_INTERNAL_PROVIDER_PILOT_PASS` 或 `FORWARD_LIVE_CAPTURE_PASS`，请只在对应文档声明的证据层内解释。

## 快速开始

前置要求：

- Python `>=3.11`，CI 使用 Python `3.12`；
- [`uv`](https://docs.astral.sh/uv/)；
- 运行触达 `engine/ksana` 的检查前，需要初始化 git submodules。

```bash
git clone https://github.com/amanayayatu-tech/gotra.git
cd gotra
git submodule update --init --recursive
uv sync --frozen
```

可选环境配置见 [`.env.example`](.env.example)。不要把真实 secrets 加入 git。Provider/backend runs 属于高成本且证据敏感动作，必须有明确 goal 和预注册边界后再运行。

## 本地检查

常规本地验证：

```bash
uv run ruff check . --force-exclude
uv run pytest -q
git diff --check
```

README/docs-only 变更通常只需要 `git diff --check`，除非 README 引用了被改动的命令或代码路径。当前 v3 surfaces 的有用 focused checks：

```bash
uv run python -m py_compile \
  scripts/baseline_v3_four_arm.py \
  scripts/baseline_v3_5_forward_live_capture.py \
  gotra/backtest/statistics.py

uv run pytest -q tests/test_baseline_v3_four_arm.py tests/test_forward_live_capture.py
```

CI 还会运行 Ruff、全量 pytest、BT repair tests、heuristic BT canaries、direct-vendor LLM import guards、repository hygiene guard 和 ksana orchestration guard。详见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)。

## Public Stock-Pool Report Ops

`main` includes the single-server public stock-pool report automation used by
the public ledger frontend. The script writes public-safe Markdown/JSON
artifacts only; it does not call LLM providers, read `.env`, expose private UI
state, or generate trading instructions.

Manual run on the server:

```bash
cd /opt/gotra
/root/.local/bin/uv run python scripts/public_stock_pool_report.py --mode morning-global --publish-static
/root/.local/bin/uv run python scripts/public_stock_pool_report.py --mode evening-hk --publish-static
```

Check timers and logs:

```bash
systemctl list-timers --all | grep gotra-stock-pool
sudo systemctl status gotra-stock-pool-morning-report.service --no-pager
sudo systemctl status gotra-stock-pool-evening-report.service --no-pager
sudo journalctl -u gotra-stock-pool-morning-report.service -n 120 --no-pager
sudo journalctl -u gotra-stock-pool-evening-report.service -n 120 --no-pager
```

Check the latest status and failed-symbol list:

```bash
jq '{ok, run_status, mode, as_of_date, trading_date, success_count, failed_count, artifact_write_status, artifact_write_failure_reason}' \
  /opt/gotra/data/reports/status.json
jq -r '.failed_symbols[]? | [.exchange, .symbol, .provider_ticker, .reason] | @tsv' \
  /opt/gotra/data/reports/status.json
curl -fsS http://47.251.249.147/reports/status.json \
  | jq '{ok, run_status, mode, trading_date, success_count, failed_count, artifact_write_status, artifact_write_failure_reason}'
```

If `status.json` cannot be written, the exact `status.json write failed` reason
is preserved in the service journal. Full ops notes, systemd templates, Nginx
route snippet, smoke checks, and safety scans are in
[`docs/PUBLIC_STOCK_POOL_REPORT_AUTOMATION_RUNBOOK.md`](docs/PUBLIC_STOCK_POOL_REPORT_AUTOMATION_RUNBOOK.md).

## Artifact Hygiene

不要提交生成产物或敏感产物：

- `data/backtest/runs/*`
- `data/backtest/prices/*`
- Codex CLI transcripts
- raw provider/API outputs
- `.env*`，但 `.env.example` 除外
- API keys、tokens、auth JSON 或本地 secrets
- SQLite/DB files
- bundle/tar/zip archives
- paper-trading data
- validation logs、review bundles、patch files、generated reports
- Stage8/Stage9 local artifacts，除非某个 docs-only artifact 被明确接受

仓库 `.gitignore` 和 CI hygiene guard 会强制执行这些规则中的稳定子集。

## 文档地图

核心项目契约：

- [`SPEC.md`](SPEC.md)：agent-facing 操作规约、边界和验证命令。
- [`docs/AUTONOMY_RUNBOOK.md`](docs/AUTONOMY_RUNBOOK.md)：自主化/runbook 约束。
- [`docs/ROADMAP.md`](docs/ROADMAP.md)：阶段路线图。
- [`data/backtest/PREREGISTERED.md`](data/backtest/PREREGISTERED.md)：原始 BT protocol。

证据与边界文档：

- [`docs/GOTRA_DIRECT_LLM_INTERPRETATION_BOUNDARY_2026-06-20.md`](docs/GOTRA_DIRECT_LLM_INTERPRETATION_BOUNDARY_2026-06-20.md)
- [`data/backtest/STAGE6_PREREGISTERED.md`](data/backtest/STAGE6_PREREGISTERED.md)
- [`docs/STAGE6_EVIDENCE_MANIFEST_20260617.md`](docs/STAGE6_EVIDENCE_MANIFEST_20260617.md)
- [`docs/STAGE6_FINAL_VERDICT_2026-06-17.md`](docs/STAGE6_FINAL_VERDICT_2026-06-17.md)
- [`docs/GOTRA_V3_3A_CHAIN_AUDIT_AND_PROVENANCE_20260620.md`](docs/GOTRA_V3_3A_CHAIN_AUDIT_AND_PROVENANCE_20260620.md)
- [`docs/GOTRA_V3_3B_OUTCOME_FEEDBACK_PRODUCTION_20260620.md`](docs/GOTRA_V3_3B_OUTCOME_FEEDBACK_PRODUCTION_20260620.md)
- [`docs/GOTRA_V3_3C_JUDGE_TEMPORAL_REPLAY_20260620.md`](docs/GOTRA_V3_3C_JUDGE_TEMPORAL_REPLAY_20260620.md)
- [`docs/GOTRA_V3_3D_JUDGE_PROMPT_HARDENING_20260620.md`](docs/GOTRA_V3_3D_JUDGE_PROMPT_HARDENING_20260620.md)
- [`docs/GOTRA_V3_4_CODEX_CLI_FORMAL_LITE_RESULT_20260620.md`](docs/GOTRA_V3_4_CODEX_CLI_FORMAL_LITE_RESULT_20260620.md)
- [`docs/GOTRA_V3_4B_DETERMINISTIC_REFERENCE_RESULT_20260620.md`](docs/GOTRA_V3_4B_DETERMINISTIC_REFERENCE_RESULT_20260620.md)
- [`docs/GOTRA_V3_4C_CODEX_CLI_SCALED_REFERENCE_RESULT_20260620.md`](docs/GOTRA_V3_4C_CODEX_CLI_SCALED_REFERENCE_RESULT_20260620.md)
- [`docs/GOTRA_V3_5A_FORWARD_LIVE_CAPTURE_RESULT_20260620.md`](docs/GOTRA_V3_5A_FORWARD_LIVE_CAPTURE_RESULT_20260620.md)

相关代码和测试入口：

- [`scripts/baseline_v3_four_arm.py`](scripts/baseline_v3_four_arm.py)
- [`scripts/baseline_v3_5_forward_live_capture.py`](scripts/baseline_v3_5_forward_live_capture.py)
- [`gotra/judge_agent/outcome_feedback.py`](gotra/judge_agent/outcome_feedback.py)
- [`gotra/judge_agent/temporal_replay.py`](gotra/judge_agent/temporal_replay.py)
- [`tests/test_baseline_v3_four_arm.py`](tests/test_baseline_v3_four_arm.py)
- [`tests/test_forward_live_capture.py`](tests/test_forward_live_capture.py)
- [`tests/test_judge_agent.py`](tests/test_judge_agent.py)
- [`tests/test_outcome_feedback.py`](tests/test_outcome_feedback.py)
- [`tests/test_judge_temporal_replay.py`](tests/test_judge_temporal_replay.py)

## 合规与使用警示

GOTRA 仅用于研究和信息整理。它不提供投资建议、组合管理、交易执行，也不构成对任何证券的买入、卖出或持有建议。用户对自己的决策负责。任何结果都可能错误、不完整、结论不足、过时，或受数据、provider、模型和实验设计限制影响。

## License

[MIT](LICENSE)
