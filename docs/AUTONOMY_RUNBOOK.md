# Gotra 全自主化 + 10×10×10年回测 · Codex 可执行任务书 v1.1

> 类型：可被 **Codex `goal` / `codex exec`** 端到端执行的任务书；同时是人类审阅方的验收清单。
> v1.1 变更：吸收审阅方对 v1.0 的核验结论，修正 8 处执行错配；**确立 gotra 为全新独立仓库与本地新工作区**；新增 Preflight、Phase 0（仓库初始化）、Phase B0（Alaya actor 合同）、Perplexity 原则迁移。所有结论已对照真实代码（文件:行）。
>
> **三仓库基线（以最新为准，已逐行核验）**
> - **gotra**（本任务书主工作面，全新仓库）：`github.com/amanayayatu-tech/gotra`，当前仅 `README.md/LICENSE/docs/ROADMAP.md`。README 自述：「Alaya 当治理底座，worldpay 当领域引擎；先契约后合库；**不重写 Python**」。
> - **ksana**（领域引擎，原 worldpay77 改名，**冻结+保持纯净**）：`github.com/amanayayatu-tech/ksana` @ `8e1f1b9`。
> - **Alaya**（治理底座）：本地 `/Users/peachy/Documents/alaya`，分支 `codex/shadow-run-24h` @ `deba14a0`；origin/main = `ad420ee`。**前置：24h 影子验收须先 PASS 并冻结。**
> - 全系统 LLM：**统一 gpt-5.5、reasoning effort = `xhigh`、经 Codex CLI**（`LLM_PROVIDER=codex_cli`），无 GPT-4o、无其他模型。

---

## 0. 给 Codex 的执行契约（MUST READ FIRST）

### 0.1 三仓库分工与工作面（DA0，冻结）
| 仓库 | 角色 | 在本任务书中的改动范围 |
|---|---|---|
| **gotra**（新仓库，主工作面） | 集成层 + 自主层 + 回测层 | v1.3 桥接（`contracts/`+`integrations/alaya/`）、Judge Agent、自动 Perplexity 执行器、daemon 编排、报告扩展、回测 harness、gotra 方法论。**绝大多数代码写在这里。** |
| **ksana**（git 子模块 `engine/ksana`，**冻结@8e1f1b9 + 保持纯净**） | 领域引擎 | **原则上零业务代码改动**；仅允许 2 处「配置化」最小 PR（§Phase A，单 commit、env 未设时行为不变）。**绝不**在 ksana 内加联网/Perplexity 调用——其 agent 纯度方法论（R8）保持不动。 |
| **Alaya**（独立仓库，基线 deba14a0） | 治理底座 | 仅 1 处最小 actor-API 合同改动（§Phase B0）：允许 automation actor 用于 gate resolve 与 knowledge quarantine；**`active→strong` 仍 human-only（底线 2）**。 |

> **gotra 如何包含 ksana**：`git submodule add` ksana 到 `engine/ksana`，pin `8e1f1b9`，`uv pip install -e engine/ksana` 可被 import（ksana 是 hatch wheel，`packages=[chairman,red_team,orchestrator,business_agents]`，已核实 pyproject）。gotra 通过 import / CLI 驱动 ksana，**不修改其源码**。

### 0.2 角色与协作模型（沿用 Alaya 三方纪律）
- **用户**：派活、拍板、按晚报一键批 strong 知识。
- **Codex（你）**：在 gotra（或对应仓库）**独立分支**实现每个 Phase 并自验；产出 `FIX_REPORT_<phase>.md`/`<phase>.patch`/`REVIEW_BUNDLE_<phase>.tar.gz`（**不进 git**）。
- **审阅方（Computer）**：独立核验（不轻信报告，直查 git/DB/日志/复跑），通过后 no-ff 合并、冻结基线、写下一 Phase。

### 0.3 铁律（违反即判 FAIL，不可旁路）
1. **宪法优先**：严守 ksana 纯函数与 Alaya `PRINCIPLES.md` Part 1 六底线（§1）。**任何与底线冲突的「加速开关」一律禁止**，尤其底线 2（strong 必过人类闸）。
2. **LLM 唯一通道**：全系统 LLM 只经 `LLMProvider` 接口（ksana = `build_llm_client_from_env()` → `CodexCliClient`，已核实 `narrative_generator.py:188`）。业务代码禁 `import openai/anthropic`（底线 6）。**已核实 ksana 无散落直连，故 LLM 统一对 ksana 是纯配置。**
3. **审计不可旁路**：跨系统写入走会记 `event_log(actor)` 的路径，禁 `rawDb` 裸写（底线 3）。
4. **分支隔离 + 单独 commit**：每 Phase 一分支；工装/runner/数据缓存扩展单独 commit。
5. **仓库卫生**：bundle/validation-logs/回测缓存/密钥/报告/patch 不进 git（Phase 0 写 `.gitignore`）。
6. **零未来函数**：回测中任一 T 的决策只用「可得时间 ≤ T」的输入（§4 三层审计强制）。
7. **不得伪装通过**：N/A 标 N/A；失败如实报 FAIL；**禁止为指标变绿而 p-hack**（§4.6）。

### 0.4 退出闸总则
**确定性全套全绿**（§5，按仓库选 ksana/Alaya 套件）+ **该 Phase 专属证据全绿** + **自动化开关关闭后行为与改动前逐位一致**。

### 0.5 Subagent 调度总则
- 实现型（写代码+单测）/ 审阅型（只读核验，不改代码，对应人类审阅角色，防自验自批）/ 并行型（仅限无写冲突任务，各写不同目录）。每 Phase 标 **[Subagent 调度]**。

---

## 0.6 PREFLIGHT —— 开干前必须先处理（否则第一小时即卡死）

> 审阅方已实测的执行面问题，**冻结本节后先逐条修，再开 Phase A**。

| # | 问题（审阅实测） | 处理 |
|---|---|---|
| PF1 | 本地 `gotra` 为空目录、非 git；远端仅 README/docs | → **Phase 0** 初始化 gotra 工作区与子模块；runbook 落到 gotra 仓库根（不再放 Downloads）。 |
| PF2 | Alaya `resolveGate`/knowledge approve/quarantine **硬编码 `actor:"human"`**（`alaya-app/server/routes.ts:700/857/875/882`） | → **Phase B0** 先改 Alaya actor 合同，否则 Phase B 的 `event_log.actor=judge_agent/codex` 验收必不过。 |
| PF3 | ksana methodology 明令「Agent 永不直接调用 Perplexity/外部 API」（`methodologies/research_system_v0.3.md:152`），且有守护测试扫描 `perplexity_client/requests/httpx`（`tests/orchestrator/test_decision_checks.py:8`） | → 自动执行器**放 gotra 编排层、不放 ksana agent**；在 **gotra 方法论 vN** 显式记「编排层自动回填替代 Nepha 手动」的原则迁移；ksana R8 与守护测试**保持不动**（§Phase P）。 |
| PF4 | Codex provider 非物理只读（`--sandbox workspace-write`，`narrative_generator.py:138`），且一次极小调用账面 ~18k tokens（含本机 config/plugins/skills；clean 后仍 ~13k） | → Phase A：provider 角色改 `--sandbox read-only --ignore-user-config`、ephemeral profile；回测加缓存/采样/预算闸（§4.7）。 |
| PF5 | `uv run mypy .` 必失败：pyproject 仅 pytest/ruff（无 mypy） | → §5 全绿套件**去掉 mypy**，用 `ruff + pytest`（与项目现状一致）；如确需类型检查，Phase A 单独 commit 加 mypy 依赖+配置。 |
| PF6 | `orchestrator.daemon --once` / `DRY_RUN` **当前不存在**；CLI 仅 `daemon start/stop/status`，start 只打印（`orchestrator/cli.py:39`） | → **Phase C 先补 CLI 合同**（gotra 侧 daemon 单次运行入口），不假设其存在。 |
| PF7 | 正常 pipeline 默认 `--no-llm`（chairman/red_team，`pipeline.py:97/119`） | → gotra 通过 `run_full_pipeline(steps=...)` 注入「启用 LLM」的自定义步骤（签名已支持传 steps），**不改 ksana**；回测同理。 |
| PF8 | `.gitignore` 现忽略 `data/*`（ksana），会吞掉 `data/backtest/PREREGISTERED.md`；bundle/报告未被忽略 | → Phase 0 设 gotra `.gitignore`：忽略 bundle/报告/patch/validation-logs/回测缓存；`!data/backtest/PREREGISTERED.md` 强制跟踪。 |
| PF9 | v1.0 自相矛盾：DA1 要「唯一通道」却又让补导出 `OpenAIClient` | → **删除该条**。Judge 用 `CodexCliClient`，全程无需暴露 `OpenAIClient`。 |

---

## 1. 不可违反的约束（冻结，复述自 Alaya PRINCIPLES.md Part 1，本地 deba14a0 已读）
| 底线 | 内容 | 对本任务书约束 |
|---|---|---|
| 1 纯函数纯 | `compute_error/classify_error/update_confidence/transition_state` 无副作用、时间靠参数注入 | 回测确定性/可复现的根基；禁让其读时钟/DB/LLM |
| **2 strong 必过人类闸** | `active→strong` `requiresHuman:true`，**禁任何 auto-approve 开关** | **Judge 绝不自动晋级 strong**；候选进晚报由用户一键批。Phase B0 改 actor 也**不得**给 strong 开自动通道。Claude Code 的「全自动 strong + 改 PRINCIPLES」**违宪，不采纳** |
| 3 审计不可旁路 | 写操作必经 `event_log(actor)`，禁 `rawDb` 裸写 | 一切自动化写入带 `actor`（`judge_agent/codex`、`auto_quarantine`、`backtest/walk_forward`） |
| 4 脏知识不进高风险证据 | `stale/expired/quarantined/conflict` 不进证据集，过滤只增不减 | 回测 Alaya 臂检索强制此过滤；auto_quarantine 只隔离不删 |
| 5 灰区不简化 | 0.3<e<0.7 弱累加、连续灰区触发意义闸 | Judge 判决须区分「方法论分歧 vs 潜在错误」，不黑白二分 |
| 6 LLM 留在接口后 | 禁业务代码直连 LLM SDK | = 「全系统走 Codex CLI」的实现纪律 |

---

## 2. 架构决策（DA 系列，与 v1.3 D1–D7 并列冻结）

**DA0 — 三仓库分工**：见 §0.1。gotra 集成层为主工作面；ksana 冻结子模块；Alaya 最小 actor 改动。

**DA1 — LLM 统一 gpt-5.5 xhigh / Codex CLI（对 ksana 近零代码）**：`LLM_PROVIDER=codex_cli`、`LLM_MODEL=gpt-5.5`、`CODEX_PROVIDER_REASONING_EFFORT=xhigh`。已核实 ksana 无散落 `import openai`，故引擎侧仅配置。**Provider 硬化（PF4）**：provider 角色用 `--sandbox read-only --ignore-user-config` 干净 ephemeral profile（物理只读，而非靠 prompt）；该硬化通过「ksana 配置化最小 PR ①」实现：`CodexCliClient` 读 `CODEX_PROVIDER_SANDBOX`（默认 `read-only`）决定 `--sandbox` 取值，env 未设时回退现状不破坏。Judge 与回测两臂均走同一 gpt-5.5 xhigh。

**DA2 — Codex 两角色物理隔离**：Provider 角色（只读、禁联网、只回答）vs Orchestrator 角色（daemon/CLI 外层编排 shell、判退出码、重试）。二者不共用沙箱约束。

**DA3 — Judge Agent 分级自主（守底线 2）**：`meaning`/`risk` gate 全自动 approve/reject；**`strong` 晋级只进晚报待批清单、绝不自动**。Judge LLM = `CodexCliClient`（gpt-5.5 xhigh），不用 OpenAIClient。`AUTO_JUDGE=true` 总开关，`false` 行为逐位一致。

**DA4 — 全自主调度**：唯一人工输入 = ksana `data/stock_pool/master_pool.yaml`（既有，含 `trading/watchlist/a_share`，`StockPool.load` 已核实）。调度扩展既有 `scheduler.py` YAML；**daemon 单次运行入口需 Phase C 新建（PF6），不假设存在**。`--no-llm` 通过 gotra 注入自定义 steps 解决（PF7）。

**DA5 — 自动 Perplexity 执行器（放 gotra，化解 R8 冲突）**：ksana 现状 `perplexity_wait` 等人工填 `_filled.yaml`（`pipeline.py`/`perplexity_wait.py` 已核实）。执行器**新建在 gotra 编排层**：读 ksana `data/pull_requests/PR-*.yaml` → 调 Perplexity `sonar-deep-research` → 写 ksana `data/perplexity_results/PR-*_filled.yaml`（即 Nepha 原手动填点）。**ksana agent 仍永不调 Perplexity（R8 不变），其守护测试照常绿**。原则迁移在 gotra 方法论 vN 显式记录（PF3），不静默绕过。

**DA6 — 回测确定性与零未来函数**：三层强制（§4.3），复用 ksana `build_outcome_snapshots_for_case` 已有的 `date<=outcome_as_of` 预过滤（`learning.py:238` 已核实）；价格一次性缓存全 10 年日频帧、按 `≤T` 切片；纯函数靠时间参数注入。差分实验设计（§4.5）。

**DA7 — Alaya automation-actor 合同（最小改动，守底线 2）**：见 Phase B0。允许 gate resolve / knowledge quarantine 带 automation actor；`active→strong` 仍 human-only。

---

## 3. Phase 序列

> 依赖：Phase 0 → A → (B0 ∥ P) → B → C → BT。每 Phase 完成即停，交审阅，通过再继续。

### Phase 0 — gotra 仓库与本地工作区初始化（≈0.5 天）
**仓库** gotra（main 起新分支 `init/workspace`）
**[Subagent 调度]** 单实现 subagent。
**步骤**
- 0.1 本地**新建独立工作区**（满足「本地新启一个项目」）：`git clone git@github.com:amanayayatu-tech/gotra.git /Users/peachy/Documents/gotra`。
- 0.2 加 ksana 子模块并安装：`git submodule add https://github.com/amanayayatu-tech/ksana.git engine/ksana && cd engine/ksana && git checkout 8e1f1b9 && cd ../.. && uv venv && uv pip install -e engine/ksana`。
- 0.3 脚手架：`contracts/`、`integrations/alaya/`、`gotra/`（自主层包：judge_agent、perplexity_executor、daemon_orchestration、reporting_ext、backtest）、`methodologies/`（gotra 方法论 vN，记 Perplexity 原则迁移）、`pyproject.toml`（依赖 ksana + perplexity/telegram/统计库 + pytest/ruff）。
- 0.4 `.gitignore`（PF8）：忽略 `FIX_REPORT_*.md`、`*.patch`、`REVIEW_BUNDLE_*.tar.gz`、`validation-logs/`、`data/backtest/prices/`、`data/backtest/runs/`、`*.env`、`.venv/`；`!data/backtest/PREREGISTERED.md` 强制跟踪。
- 0.5 把本 runbook 复制进 `gotra/GOTRA_RUNBOOK_v1.1.md`（启动命令从此路径读，不再用 Downloads）。
**退出闸**：`uv run python -c "import chairman, orchestrator, business_agents"` 成功；子模块 pin 在 8e1f1b9；`.gitignore` 生效；`ruff check .` 绿。
**回滚**：删本地工作区，远端 gotra 无破坏。

### Phase A — LLM 统一 + Provider 硬化（≈0.5–1 天）
**仓库** gotra 分支 `A-llm-codex`；ksana 分支 `cfg/provider-sandbox`（配置化 PR ①）
**[Subagent 调度]** 实现 subagent + 审阅 subagent。
**步骤**
- A.1 **ksana 配置化 PR ①（单 commit，唯一 ksana 代码改动之一）**：`CodexCliClient` 命令构造读 `os.getenv("CODEX_PROVIDER_SANDBOX","read-only")` 决定 `--sandbox`；新增 `--ignore-user-config`（可由 `CODEX_PROVIDER_CLEAN=1` 开）。env 未设时**行为与 8e1f1b9 完全一致**（默认值需与现状对齐或显式标注变更）。附单测。
- A.2 gotra LLM 工厂与 Judge 客户端（**走 Codex，非 OpenAI**）：
  ```python
  # gotra/judge_agent/llm.py
  from chairman.llm.narrative_generator import CodexCliClient
  def build_judge_client() -> CodexCliClient:
      import os; from dotenv import load_dotenv; load_dotenv()
      os.environ["CODEX_PROVIDER_REASONING_EFFORT"] = os.getenv("JUDGE_CODEX_REASONING_EFFORT", "xhigh")
      os.environ.setdefault("CODEX_PROVIDER_SANDBOX", "read-only")
      os.environ.setdefault("CODEX_PROVIDER_CLEAN", "1")
      return CodexCliClient(model=os.getenv("JUDGE_LLM_MODEL", "gpt-5.5"))
  ```
- A.3 gotra `.env.example`：`LLM_PROVIDER=codex_cli`、`LLM_MODEL=gpt-5.5`、`CODEX_PROVIDER_REASONING_EFFORT=xhigh`、`CODEX_PROVIDER_SANDBOX=read-only`、`CODEX_PROVIDER_CLEAN=1`、`AUTO_JUDGE=true`、`JUDGE_CODEX_REASONING_EFFORT=xhigh`、`PERPLEXITY_API_KEY=`、`PERPLEXITY_MODEL=sonar-deep-research`、`JUDGE_DAILY_TOKEN_BUDGET=`。
- A.4 Provider smoke（成本基线）：固定 prompt 跑 `read-only + clean` provider，记录 token 用量写 `FIX_REPORT_A.md`，作为 §4.7 预算闸基准。
**退出闸**：`build_judge_client()` 返回 `CodexCliClient`；`CODEX_PROVIDER_SANDBOX` 生效（read-only 下写文件被拒）；ksana env 未设时单测全绿（无行为漂移）；§5（ruff+pytest）绿。
**回滚**：env 复位、revert 配置 PR，零数据影响。

### Phase B0 — Alaya automation-actor 合同（≈1–2 天，仓库 Alaya）
**仓库** Alaya 分支 `codex/automation-actor`
**[Subagent 调度]** 实现 subagent + **独立审阅 subagent 必做**（核验 strong 仍 human-only）。
**步骤**
- B0.1 `resolveGate`（`routes.ts:688`）与 knowledge `quarantine`（:882）支持从受信调用方传入 `actor`（如 `judge_agent/codex`、`auto_quarantine`）：取自鉴权后的 API key 身份或显式 body 字段，**经 service 层落 `event_log`**（底线 3），不裸写。
- B0.2 **硬约束**：`POST /api/knowledge/:id/approve`（→ `active→strong`，:857/875）**拒绝任何非 human actor**；即使传 automation actor 也返回 4xx。新增/扩展守卫测试断言「automation actor 永不能产生 strong」（底线 2）。
- B0.3 `human-gates approve/reject` 接受 automation actor，但 `risk` gate 的 blocking 语义不变。
**退出闸**：Alaya 全套（`typecheck/guard/test:all/test:scripts/e2e:*/flywheel/build/secret:scan/git diff --check`）全绿 + ≥1h 真实复测；新增测试证明 automation 可 resolve gate / quarantine 但**绝不能 approve strong**；`event_log.actor` 可落非 human 值。
**回滚**：revert 分支，Alaya 回 deba14a0 行为。
> 已知环境限制：审阅方经 pc 通道在 Mac 跑服务类测试 `listen EPERM`（6 个端口绑定测试必失败）——属环境，完整复跑在沙箱 Linux 克隆做。

### Phase P — 自动 Perplexity 执行器 + 原则迁移（≈2–3 天，仓库 gotra）
**仓库** gotra 分支 `P-pplx-executor`
**[Subagent 调度]** 实现 subagent；审阅 subagent（核验未触碰 ksana agent / 守护测试、零联网泄漏边界、降级路径）。
**步骤**
- P.1 `gotra/perplexity_executor/{executor.py,pplx_client.py,tests/}`。executor 读 ksana `data/pull_requests/PR-*.yaml` → `pplx_client` 调 `sonar-deep-research` → 复用 ksana `_common/perplexity_results.py` 的 `_filled.yaml` 写格式与长度约束（`MAX_PERPLEXITY_ANSWER_CHARS=2600` 等已核实）→ 写 ksana `data/perplexity_results/`。**不 import 或修改 ksana agent；不触碰 ksana 守护测试。**
- P.2 `pplx_client`：超时 120s、指数退避 ≤3、并发上限 2、写回前过 ksana `output_validator.py: PerplexityPrompt` schema。
- P.3 **原则迁移文档（PF3，必做）**：在 `gotra/methodologies/autonomy_v1.md` 写明：ksana agent 的 R8（永不调 Perplexity）**不变且仍受 ksana 守护测试保护**；**gotra 编排层**引入「auto-fill operator」角色，机械替代「Nepha 手动在 Perplexity Max 回填」。这是层级迁移，非绕过 agent 纯度。
- P.4 与 pipeline 对齐：executor 在 `perplexity_wait` 步骤前跑（Phase C daemon 串联）；保留 `perplexity_wait` 作失败兜底（自动优先、人工可降级）。
- P.5 成本计入 gotra reporting（扩展，见 Phase C）。
**退出闸**：mock 单测绿；真实 1 条 PR → 自动 `_filled.yaml` → `cd engine/ksana && uv run orchestrator rerun --from-step partners` 后 `PerplexityContext=filled`；**ksana 守护测试 `test_decision_checks.py` 仍全绿（证明未污染引擎）**；API 超时优雅降级人工通道；§5 绿。
**回滚**：禁用 executor 回人工填，零数据影响。
> **回测约束**：执行器仅用于实盘自主；回测中禁实时 Perplexity（§4.3 第 3 层），`PERPLEXITY_API_KEY` 在回测环境置空。

### Phase B — Judge Agent 分级自动闸门（≈4–6 天，仓库 gotra，**依赖 B0**）
**仓库** gotra 分支 `B-judge-agent`
**[Subagent 调度]** 实现 subagent + **独立审阅 subagent 必做**（本 Phase 风险最高）。
**步骤**
- B.1 `gotra/judge_agent/{judge_agent.py,gate_poller.py,auto_quarantine.py,prompts/{meaning_gate.md,risk_gate.md},tests/}`。
- B.2 判决上下文（来源已核验）：`ticker+gate_type+prompt_text`（Alaya `GET /api/human-gates/:id` routes.ts:639）、`existing_knowledge`（ksana `knowledge_store.py`，仅 active/strong，强制底线 4 过滤）、`fwg_recommendations`（同 run_id）、`red_team_findings`（`data/red_team_audits/`）、`historical_accuracy`（Alaya `GET /api/projects/:id/predictions` routes.ts:772，经 id_map）、`quarantine_list`。输出严格 JSON：`{decision, confidence, reasoning(简体中文≤300字，区分方法论分歧 vs 潜在错误), knowledge_flag:none|watch|strong_candidate|quarantine_candidate, audit_actor:"judge_agent/codex"}`。
- B.3 路由：`approve`→`POST /api/human-gates/:id/approve`（**带 B0 的 automation actor**）；`reject`→`/reject`。物化回写复用 v1.3 P2 `sync_gates.py`——Judge 不直接写文件。
- B.4 `gate_poller.py`：60s 轮询（`JUDGE_POLL_INTERVAL`），连失 ≥5 轮 stderr 告警不退出；`AUTO_JUDGE=false` → `sys.exit(0)`。
- B.5 `auto_quarantine.py`（晚报窗、`refresh_outcome_snapshots` 后串联）：方向反向（看多实跌 >5%）或 `price_error > QUARANTINE_ERROR_THRESHOLD`（默认 0.15）→ `POST /api/knowledge/:id/quarantine`（带 automation actor，仅匹配 `source_pr_id`）→ 写晚报 + event_log。只隔离不删（底线 4/熵减）。
- B.6 **strong 晋级（守底线 2）**：`strong_candidate` 只写晚报待批清单，**绝不调 approve**。用户一键批才走 `POST /api/knowledge/:id/approve`（human actor）。
**退出闸**：一条 meaning + 一条 risk gate 走完 judge→approve→sync→回写；`event_log.actor=judge_agent/codex` 可查（依赖 B0）；**CI 硬断言「无任何 strong 由非 human actor 晋级」**；`AUTO_JUDGE=false` 行为逐位一致；§5 绿。
**回滚**：`AUTO_JUDGE=false`，gate 回人工，零数据修改。

### Phase C — daemon CLI 合同 + 全自主调度 + 每日报告（≈3–4 天，仓库 gotra）
**仓库** gotra 分支 `C-daemon-report`
**[Subagent 调度]** 实现 subagent + 审阅 subagent（核验失败隔离/降级/不覆盖既有基类）。
**步骤**
- C.0 **先补 CLI 合同（PF6）**：gotra 新建 daemon 单次运行入口 `python -m gotra.daemon_orchestration.run --once --type {morning|evening} [--dry-run]`，**不依赖 ksana 不存在的 `--once`**。
- C.1 沿用 ksana `master_pool.yaml`（trading=固定持仓、watchlist=研究公司），`StockPool.load(data)`，不改 API。
- C.2 调度：扩展 ksana `scheduler.py` 的 YAML 配置（按用户作息定时间/时区）；gotra daemon 串联，失败隔离（任一步失败记录后继续；run/push 失败跳过依赖步但仍出报告标 `pipeline_failed=true`）：
  ```text
  1 perplexity_executor 预填(Phase P)
  2 gotra 注入 LLM-enabled steps → run_full_pipeline(steps=...)   # 解决 PF7（不改 ksana）
  3 export_events.py → push_to_alaya.py          # v1.3 P1
  4 gate_poller.py --once(Phase B)
  5 sync_gates.py                                 # v1.3 P2 物化
  6 refresh_outcome_snapshots + auto_quarantine   # 仅晚报
  7 export_events.py(快照) → push_to_alaya.py       # 仅晚报
  8 report_render + notifier 推送
  ```
  并发防护：lockfile `/tmp/gotra_run.lock`，已锁跳过标 `system_health.skipped=true`。
- C.3 报告复用 ksana `reporting/html_renderer.py`（1144 行，已核实）+ `llm_usage.py` 成本核算，gotra 侧扩展 section：早报（System Health｜Research Signals｜Judge 决策｜Active Predictions｜Knowledge Additions）；晚报（+Outcome Updates｜Auto-Quarantine 表｜**Strong 待批清单(一键批)**｜Next Run Queue）。
- C.4 `gotra/reporting_ext/` 新增 `TelegramNotifier(Notifier)`/`SmtpNotifier(Notifier)` 实现 ksana 既有 `Notifier` ABC（`notifications/notifier.py`，**不覆盖基类/LocalNotifier**）；通道走 `NOTIFIER_CHANNELS`；均不可达降级写 `data/reports/{date}_{type}.{md,html}` 不报错。
**退出闸**：`StockPool.load` 读出计数；`python -m gotra.daemon_orchestration.run --once --dry-run` 验证串联与失败隔离（不实跑 LLM）；两窗口各一次完整 run（LLM-enabled，确认实际走 Codex）；通知到达或降级；strong 待批可一键批；§5 绿。
**回滚**：停 daemon 回手动，报告无副作用。

### Phase BT — 10×10×10年 Walk-Forward 零未来函数回测（最终验收）
见 §4。Correctness 闸必须 100% 全绿。

---

## 4. Phase BT 详设（仓库 gotra 分支 `BT-backtest`）
**[Subagent 调度]** 数据缓存 10 并行 subagent（每票写 `data/backtest/prices/<ticker>.csv`）；实验跑批 2 并行 subagent（Alaya/Baseline 臂，各写 `data/backtest/runs/{alaya,baseline}/`）；审计+制图 1 独立审阅 subagent（只读）。

### 4.1 标的与区间
腾讯 `0700.HK`、美团 `3690.HK`（2018-09 上市）、众安在线 `6060.HK`（2017-09）、NVIDIA `NVDA`、小米 `1810.HK`（2018-07）、阿里 `9988.HK`（2019-11，或全程用 `BABA`）、比亚迪 `1211.HK`、苹果 `AAPL`、台积电 `TSM`、微软 `MSFT`。区间 **2016-01 → 2026-01**。
- **上市晚于步 T 的票，该步标 N/A 不参与**（不得用上市后数据回填上市前预测=未来函数）。
- **选择偏差声明（必写进报告）**：这 10 只为事后挑选的知名存活公司，本身带幸存者/选择偏差；结论仅就「认知复利机制的差分效应」成立，不可外推为普适收益预测。

### 4.2 Walk-Forward 协议
- 初始窗口 12 个月（仅初始化、不计分）；预测步长 1 个月；滚动步进 1 个月 ≈ **108 计分步/票**。
- 每步 T：① 输入仅「可得时间 ≤ T」（价格切片 + §4.3 受控基本面/文本）；② 产出 `decision_case`（方向 + 预期涨跌幅 %，`verification_windows_days=30`）；③ 窗口到期（`outcome_as_of` 过 `window_end_date`）后用缓存价格算实际涨跌 → `compute_error` → 该步 MSE。
- 两臂：**Alaya 臂**带认知复利（把此前已到期步的 outcome/error 反馈进知识库 + Beta 置信度 `update_confidence.ts` + 误差归因 `classify_error`，检索强制底线 4 过滤）；**Baseline 臂**无状态单步（**同一 gpt-5.5 xhigh、同一 prompt 骨架**，不携带历史、不更新置信度）。唯一变量 = 是否带认知复利。

### 4.3 零未来函数三层强制（核心）
- **第 1 层 价格**：一次性缓存全 10 年**日频 adjusted close（复权）**帧（统一复权口径，避免拆股/分红造成的伪跳变）；每步用 `build_outcome_snapshots_for_case` 已有 `rows=[r for r in history if date<=outcome_as_of]` 预过滤（`learning.py:238` 已核实）。**需新增工装**（单独 commit）`gotra/backtest/price_cache.py`：用 Yahoo `period1/period2` 全程拉一次落 CSV（`YFinanceClient` 现仅 `period`，已核实），运行期只读切片、不再联网。
- **第 2 层 基本面（最隐蔽陷阱）**：yfinance 财务为**重述后**数据带前视。**默认禁用基本面**；如启用，必须按「**财报发布日**（非财季结束日）≤ T」门控，字段标 `availability_date`；审计脚本对每个被喂字段断言 `availability_date<=T`，否则该步 FAIL。
- **第 3 层 联网研究（LLM 最大泄漏源）**：回测**禁实时 Perplexity/任何联网**（`PERPLEXITY_API_KEY` 置空；Codex provider 本就 read-only 禁联网）。agent 只见价格切片（+ 可选严格 ≤T 的点位新闻语料）。

### 4.4 LLM 预训练泄漏：诚实面对
现成 LLM 跑历史回测有**不可消除泄漏**（模型已「知道」2024 NVDA 大涨等）。因此**绝对 MSE 不可信**（偏乐观），报告显著位置声明。

### 4.5 差分设计（严谨表述，已采纳审阅 P2 修正）
两臂共用同一 gpt-5.5 xhigh，承受**同向**预训练泄漏，故**差分 `MSE_Baseline − MSE_Alaya` 比绝对 MSE 更稳健**。**但不保证泄漏完全抵消**：Alaya 臂把历史反馈写入状态，泄漏可能与状态交互（如模型「记得」未来 → 反馈回路被污染）。因此结论限定为：**在共享模型与共享输入下，差分 MSE 估计的是认知复利机制的「净增量效应」，可能仍含未被抵消的交互偏差**；报告必须如实标注此局限，不得宣称差分=无偏因果效应。

### 4.6 预注册与 anti-p-hacking
**开跑前**写 `data/backtest/PREREGISTERED.md` 并 commit（时间戳锁定，PF8 已强制跟踪）：
- 精确风格切换窗口日期（开跑前定死）：2018 中美贸易战、2020-Q1 COVID、2021-H2 港股平台监管、2022 全球加息、2023 生成式 AI 行情——每段给明确起止月。
- H1 收敛：`MSE_Alaya` 后 1/3 时段均值 < 前 1/3，降幅 ≥ X%（建议 X=15，开跑前定死）。
- H2 抗漂移：上列窗口内 `MSE_Alaya < MSE_Baseline`。
- H3 差分显著：`MSE_Baseline − MSE_Alaya > 0` 且通过配对 **Diebold-Mariano 检验**；**因预测序列重叠/月度自相关，须用 HAC（Newey-West）稳健标准误**，不可用朴素配对 t。p<0.05。
> 阈值预注册后不得事后改；假设未达成如实报负结果，不回去调参刷绿。

### 4.7 成本控制与预算闸（PF4，必做）
BT 规模 = 10 票 × 108 步 × 2 臂，且每步含 F/W/G + Chairman（+Alaya 臂的反馈），单步多次 Codex 调用；按 ~13k tokens/调用，总量巨大。强制措施：
- 干净轻量 provider profile（`read-only + ignore-user-config + ephemeral`，Phase A 已备）。
- **结果缓存**：以 `(ticker, T, arm, prompt_hash)` 为键缓存 LLM 输出，重跑命中不重复计费。
- **采样模式**：先跑「季度步」（步进 3 月）validate 全链路与审计，再决定是否全量月度。
- **预算闸**：`JUDGE_DAILY_TOKEN_BUDGET` 同款机制用于 BT，累计 token 超阈即暂停并告警，写 `system_health`。

### 4.8 「全绿」两类闸（务必区分）
- **A 类 Correctness（必须 100% 全绿，证明实验有效）**：① 零未来函数审计零违规（扫描每步全部输入 `availability_date≤T`，含三层）；② 两臂全步无 crash；③ 可复现：固定种子；gpt-5.5 在固定 reasoning effort 下仍有非确定性，故以「同输入二次跑 Baseline 决策方向一致率 ≥95%」度量，余下标注（不强求逐字节）；④ `compute_error/classify_error` 纯函数+时间参数注入，单测绿（底线 1）；⑤ 全程 `event_log(actor=backtest/walk_forward)`，无 rawDb 裸写；⑥ §5 绿。
- **B 类 Hypothesis（科学结论，按预注册判定）**：H1/H2/H3。
> **交付判定**：A 类必须全绿（否则实验无效、结论作废）；B 类是真实结论——全达成=「认知复利真实有效」获验证，未达成=如实报负结果+归因（不刷绿）。

### 4.9 产物
`data/backtest/prices/<ticker>.csv`（缓存，不进 git）、`runs/{alaya,baseline}/step_*.json`（决策+输入溯源+error，不进 git）、`PREREGISTERED.md`（进 git）、`REPORT_backtest.md` + MSE 演化图（Alaya vs Baseline 双曲线 + 风格窗竖线）、`FIX_REPORT_BT.md`/`REVIEW_BUNDLE_BT.tar.gz`（不进 git）。

---

## 5. 「全绿」确定性套件（按仓库选用；已去 mypy，PF5）
**gotra / ksana（`uv run`）**：
```
uv run ruff check .
uv run pytest -q                 # 全量
uv run pytest -q <phase 专属目录>
git diff --check
grep -rn "import openai\|import anthropic" --include=*.py . | grep -v narrative_generator.py   # 须空(底线6)
cd engine/ksana && uv run pytest -q tests/orchestrator/test_decision_checks.py   # Phase P 后须仍绿(引擎纯度未污染)
```
**Alaya（仅 Phase B0，`npm`）**：`typecheck/guard/test:all/test:scripts/e2e:review-window/e2e:knowledge-lifecycle/e2e:long-evolution/benchmark:smoke/flywheel/build/secret:scan/git diff --check` 全绿 + ≥1h 真实复测（`local_api_human_proxy`、provider ratio ≥95%、A 类 9 判据、`UNIQUE/closed+drafting/error/runner_crashed` 扫描 0）。
> 已知环境限制：审阅方 pc 通道 Mac 跑服务类测试 `listen EPERM`（6 测试必失败）属环境，完整复跑在沙箱 Linux 克隆做。

---

## 6. 风险与回滚总览
| 风险 | 缓解 | 回滚 |
|---|---|---|
| gotra 空工作面致卡死 | Phase 0 先初始化仓库/子模块/.gitignore | 删本地工作区 |
| Phase B actor 验收过不了 | **先做 Phase B0** Alaya actor 合同 | revert Alaya 分支 |
| Perplexity 自动化撞 ksana R8/守护测试 | 执行器放 gotra 编排层、ksana 不动、方法论 vN 记迁移 | 禁执行器回人工填 |
| Judge 自动升 strong（违底线 2） | DA3 strong 只进晚报；B0 拒绝非 human approve strong；CI 硬断言 | `AUTO_JUDGE=false` |
| Codex provider 非隔离/成本爆 | read-only+clean profile；缓存/采样/预算闸 | 降级采样或停 BT |
| daemon `--once` 不存在 | Phase C 先补 CLI 合同 | — |
| `--no-llm` 默认不走 LLM | gotra 注入 LLM-enabled steps，不改 ksana | 用默认 steps |
| 回测未来函数泄漏 | 三层审计强制 `availability_date≤T` | 违规即 FAIL |
| 绝对 MSE 当真实预测力 / 差分被当无偏 | 报告声明泄漏 + 4.5 交互偏差局限 | — |
| p-hacking 刷绿 | 预注册+时间戳锁定，负结果如实报 | — |

---

## 7. 启动方式（Codex goal / exec）
**前置**：Alaya 24h 影子验收 PASS 并冻结；Phase 0 已初始化本地 `/Users/peachy/Documents/gotra`（含 ksana 子模块）；`LLM_PROVIDER=codex_cli`。
逐 Phase 启动（推荐，每 Phase 停下交审阅）：
```bash
# 在 gotra 仓库根目录（/Users/peachy/Documents/gotra）
codex --ask-for-approval never --sandbox workspace-write exec --cd "$(pwd)" \
  "阅读 GOTRA_RUNBOOK_v1.1.md，先完成 §0.6 PREFLIGHT 与 Phase 0；自验通过 §5 后产出 \
   FIX_REPORT_0.md / 0.patch / REVIEW_BUNDLE_0.tar.gz，停下等待审阅，不要继续 Phase A。"
```
> 若你的 Codex 提供 `goal` 自治模式，把同样 Phase 指令作为 goal 输入；务必保留「每 Phase 停下交审阅」边界，禁一口气跑到 BT。Subagent 按各 Phase **[Subagent 调度]** 执行：实现与审阅分离、并行任务各写不同目录。

---

## 附录 · 已核验事实（v1.1，防过期假设施工）
- gotra 仓库：当前仅 `README.md/LICENSE/docs/ROADMAP.md`；README 自述「合并落地仓库，不重写 Python」。✅（gh 核实）
- ksana **无散落 `import openai/anthropic`**（narrative_generator 之外 grep 为空）→ LLM 统一对 ksana 近零代码。✅
- ksana 可被 import：hatch wheel，`packages=[chairman,red_team,orchestrator,business_agents]`。✅
- ksana methodology 明令 Agent 永不调 Perplexity/外部 API（`research_system_v0.3.md:152/541`），守护测试扫 `perplexity_client/requests/httpx`（`test_decision_checks.py:8`）。✅ → 执行器必须放 gotra。
- ksana pipeline 默认 `--no-llm`（`pipeline.py:97/119`）；`run_full_pipeline(steps=...)` 可注入自定义步骤。✅
- ksana `.gitignore` 忽略 `data/*`（除 stock_pool）；无 mypy（pyproject 仅 pytest/ruff）。✅
- ksana `learning.py:238` `build_outcome_snapshots_for_case` 已 `date<=outcome_as_of` 预过滤；`yfinance_client` 仅接受 `period`（无日期范围）。✅
- Alaya `routes.ts`：`resolveGate`(:688) 与 knowledge approve/quarantine **硬编码 `actor:"human"`**（:700/857/875/882）；无 automation actor 参数。✅ → Phase B0 前置。
- Alaya API 端点（human-gates approve/reject/modify/defer/revoke :729-750；predictions POST/observation/error :775-796；knowledge approve/quarantine :861-881；business-signals/import）真实存在。✅
- Codex provider：`--ask-for-approval never exec --sandbox workspace-write`（`narrative_generator.py:138`）；审阅方本地 smoke：`codex exec --model gpt-5.5` 返回 OK，单次极小调用 ~18k tokens（clean 后 ~13k）。✅ → provider 硬化 + BT 预算闸。
- Alaya `PRINCIPLES.md` Part 1 六底线（deba14a0）：底线 2「strong 必过人类闸、禁 auto-approve 开关」；底线 6「LLM 留接口后」。✅
