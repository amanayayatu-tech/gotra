# gotra

> **गोत्र**（梵语「世系 / 谱系」）—— 让每一次投研判断都有可追溯的血脉：从信号到预测，从预测到观察，从误差归因到知识沉淀。

**gotra 是一个可审计、可回滚、人类闸门兜底的自主投研数据飞轮。** 它把两个上游项目连成一个端到端系统，并在其上叠加一层**全自主编排**：除了一份固定的股票池，系统每天自动完成研究、判断、预测、归因与知识沉淀，早晚各产出一份详细报告；只有「知识晋级为 strong」这一最危险的动作保留人类一键确认。

- **[Alaya](https://github.com/amanayayatu-tech/Alaya)**（TypeScript）：治理底座 —— 事件账本、人类闸门（human gates）、预测/观察/误差归因内核、知识状态机。
- **[ksana](https://github.com/amanayayatu-tech/ksana)**（Python，原 worldpay77）：领域引擎 —— 股票池扫描、F/W/G 委员会、Chairman 决策、红队审计、outcome 快照。
- **gotra**（本仓库）：集成层 + 自主层 + 回测层 —— 跨仓契约与桥接、自动 Perplexity 执行器、Judge Agent 自动闸门、daemon 自主调度、每日报告、Walk-Forward 回测。

> 合并原则（不变）：**Alaya 当治理底座，ksana 当领域引擎；先契约后合库；不重写引擎。** gotra 以 ksana 为子模块（冻结 + 保持纯净），通过 import / CLI 驱动它，不修改其源码。

---

## 三仓库分工

| 仓库 | 角色 | 在 gotra 中的形态 |
| --- | --- | --- |
| **gotra**（本仓库） | 集成 + 自主 + 回测 | 主工作面，绝大多数新代码在这里 |
| **[ksana](https://github.com/amanayayatu-tech/ksana)** | 领域引擎 | git 子模块 `engine/ksana`，**冻结 + 纯净**；不加联网 / 不加 Perplexity 调用 |
| **[Alaya](https://github.com/amanayayatu-tech/Alaya)** | 治理底座 | 独立仓库；仅做最小 actor-API 合同改动（允许自动化 actor，**但 strong 晋级仍 human-only**） |

---

## 设计哲学：六条不可违反的底线

继承自 Alaya 宪法 `PRINCIPLES.md` Part 1，全程冻结：

1. **纯函数保持纯** —— `compute_error / classify_error / update_confidence / transition_state` 无副作用、时间靠参数注入（可复现、可单测、可审计的数学心脏）。
2. **strong 晋级必过人类闸** —— `active → strong` 必须人类批准，**禁止任何「为了跑得快」的 auto-approve 开关**。机器自封 strong = 自我强化的幻觉闭环。
3. **审计不可旁路** —— 一切写操作经会记 `event_log(actor)` 的路径，禁 `rawDb` 裸写。
4. **脏知识不进高风险证据** —— `stale / quarantined / conflict` 状态的知识不得进入高风险决策证据集，过滤只增不减。
5. **灰区不简化** —— 模糊反馈弱累加、连续灰区触发意义闸，不黑白二分。
6. **LLM 留在接口后** —— 全系统 LLM 只经 `LLMProvider` 接口，禁业务代码直连 SDK。

> 产品边界同样冻结：**不下单、不接券商、不输出买卖指令**；outcome 快照是观察值，不自动等于 thesis 真相。

---

## 自主闭环（Definition of Done）

```text
唯一人工输入：data/stock_pool/master_pool.yaml（固定持仓 + 研究公司）
  → daemon 每日早/晚两次自动触发完整 pipeline
  → 自动 Perplexity 执行器：PR-* prompt → sonar-deep-research → 回填 PR-*_filled.yaml
  → F/W/G 委员会 + Chairman 产出 brief / decision_case
  → Judge Agent 自动判决闸门：meaning / risk gate 全自动 approve/reject（gpt-5.5 xhigh）
  → decision_case 进 Alaya prediction（1/7/30/90 天 claims，future_data_allowed=false）
  → outcome 快照 → Alaya observation → compute_error / classify_error 误差归因
  → 误差反馈进知识库（Beta 置信度自适应）；outcome 误差超阈自动 quarantine（只隔离不删）
  → strong 知识候选进【晚报待批清单】，由人一键批准（唯一保留的人工动作）
  → 每日早报 / 晚报 自动推送（Telegram / SMTP / 本地）
  → 同 ticker 再研究时引用既有 active/strong 知识，被隔离知识不进引擎
```

**全系统 LLM 推理统一为 `gpt-5.5`、reasoning effort = `xhigh`、经 Codex CLI 调用**（`LLM_PROVIDER=codex_cli`），无其他模型。每一步可审计；任一侧停机不阻塞另一侧。

---

## 仓库结构

```text
gotra/
  engine/ksana/                      # git 子模块（pin @8e1f1b9，冻结 + 纯净）
  contracts/
    investment_event.schema.json     # 跨仓事件契约 v1（JSON Schema）
  integrations/alaya/                # 桥接（v1.3 双仓库 + 桥接）
    export_events.py                 # ksana run 产物 → events.jsonl（只读、幂等）
    push_to_alaya.py                 # events.jsonl → POST Alaya API（signal/gate/prediction 分发）
    sync_gates.py                    # 轮询 Alaya resolved gates → 回写 PR-*_filled/_skipped.yaml
    sync_knowledge_filter.py         # 拉取 Alaya 知识状态 → quarantine_list.yaml
    state/id_map.sqlite              # 双侧实体 ID 映射
  gotra/                             # 自主层
    perplexity_executor/             # 自动 Perplexity 执行器（编排层，非引擎 agent）
    judge_agent/                     # Judge Agent 分级自动闸门 + auto_quarantine
    daemon_orchestration/            # daemon 单次/定时编排（早晚双窗口）
    reporting_ext/                   # 报告扩展 + Telegram/SMTP Notifier 子类
    backtest/                        # Walk-Forward 回测 harness + 价格缓存
  methodologies/
    autonomy_v1.md                   # 自主层方法论（含 Perplexity 原则迁移说明）
  docs/
    ROADMAP.md                       # 合并执行路线图 v1.3（桥接基础，含命名横幅）
    AUTONOMY_RUNBOOK.md              # 自主化 + 回测 可执行任务书 v1.1（Codex 执行）
```

---

## 路线图

### 第一阶段 · 桥接基础（来自合并路线图 v1.3）

| 阶段 | 内容 | 硬性退出标准 |
| --- | --- | --- |
| P0 | 契约与原则冻结 | schema 校验过、双仓 PR 合并 |
| P1 | 最小事件链路（exporter + pusher） | 幂等 V1–V4 全过 |
| P2 | Deep Research 闸门 + 双向回写 | filled/skipped 双路径 E2E 绿 |
| P3 | 决策进 Prediction Ledger | 1 条真实归因链完整 |
| P4 | 知识 SoR 落地与反向过滤 | 隔离双侧生效、无自动 strong |

详见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。

### 第二阶段 · 全自主化 + 回测（执行任务书 v1.1）

| 阶段 | 仓库 | 内容 | 关键退出标准 |
| --- | --- | --- | --- |
| Phase 0 | gotra | 仓库与本地工作区初始化、ksana 子模块、`.gitignore` | 可 import ksana、子模块 pin 8e1f1b9 |
| Phase A | gotra / ksana | LLM 统一走 Codex CLI（gpt-5.5 xhigh）+ provider 物理只读硬化 | provider read-only 生效、无行为漂移 |
| Phase B0 | Alaya | automation-actor 合同（**strong 仍 human-only**） | 自动化可 resolve gate / quarantine，**永不能 approve strong** |
| Phase P | gotra | 自动 Perplexity 执行器（编排层）+ 原则迁移文档 | ksana agent 纯度守护测试仍全绿 |
| Phase B | gotra | Judge Agent 分级自动闸门 + auto_quarantine | `event_log.actor=judge_agent/codex` 可查、无自动 strong |
| Phase C | gotra | daemon 自主调度 + 每日早晚报告 + 通知 | 两窗口完整 run、strong 待批可一键批 |
| Phase BT | gotra | 10×10×10年 Walk-Forward 回测（效力验收） | Correctness 闸 100% 全绿 |

详见 [`docs/AUTONOMY_RUNBOOK.md`](docs/AUTONOMY_RUNBOOK.md)。

---

## 效力验收：10 股 × 10 年 Walk-Forward 回测

系统是否真的具备「认知复利」，用一个**零未来函数**的滚动回测来证明：

- **数据**：10 只代表性港股 / 美股（腾讯、美团、众安、NVIDIA、小米、阿里、比亚迪、苹果、台积电、微软）2016–2026 日频数据。
- **滚动窗口**：1 年初始化窗口，滚动预测下 1 个月，逐月前进；任一 T 时刻决策**只用可得时间 ≤ T 的数据**（三层防泄漏：价格按 `date≤T` 切片、基本面按财报发布日门控、回测期禁实时联网研究）。
- **对比**：Alaya 臂（带知识库 + Beta 置信度自适应）vs Baseline 臂（无状态单步）。**两臂共用同一 gpt-5.5 xhigh 模型与 prompt 骨架，唯一变量 = 是否带认知复利**——干净的消融实验。
- **指标**：MSE 演化。预期 Alaya 臂随时间收敛，Baseline 臂在市场风格切换时灾难性漂移；以差分 `MSE_Baseline − MSE_Alaya`（Diebold-Mariano + Newey-West HAC）度量机制净增量效应。
- **诚实声明**：现成 LLM 跑历史回测存在不可消除的预训练泄漏，故**绝对 MSE 不可信**，结论仅就「机制差分效应」成立；预注册阈值 + 时间戳锁定，杜绝 p-hacking。

「全绿」分两类：**Correctness 闸**（零未来函数审计、无崩溃、可复现、纯函数单测、全程审计留痕）必须 100% 通过以证明实验有效；**Hypothesis 闸**（MSE 收敛 / 抗漂移 / 差分显著）是真实科学结论，达成则验证「认知复利有效」，未达成如实报负结果。

---

## 快速开始

前置：本地能独立运行 Alaya（治理底座）；本机已安装并登录 Codex CLI（系统所有 LLM 调用经此）。

```bash
# 1. clone gotra 并拉取 ksana 子模块
git clone https://github.com/amanayayatu-tech/gotra.git
cd gotra
git submodule update --init --recursive

# 2. 安装（ksana 作为可编辑依赖）
uv venv && source .venv/bin/activate
uv pip install -e engine/ksana

# 3. 配置环境（全系统 LLM 走 Codex CLI · gpt-5.5 · xhigh）
cp .env.example .env
#   LLM_PROVIDER=codex_cli
#   LLM_MODEL=gpt-5.5
#   CODEX_PROVIDER_REASONING_EFFORT=xhigh
#   AUTO_JUDGE=true
#   PERPLEXITY_API_KEY=...      # 仅实盘自主用；回测期置空

# 4. 校验事件契约
python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/investment_event.schema.json')))"

# 5. daemon 干跑（验证编排串联与失败隔离，不实跑 LLM）
python -m gotra.daemon_orchestration.run --once --type morning --dry-run
```

> 本仓库按可被 **Codex `goal` / `codex exec`** 逐 Phase 自主执行的任务书组织，详见 [`docs/AUTONOMY_RUNBOOK.md`](docs/AUTONOMY_RUNBOOK.md)。每个 Phase 在独立分支实现、自验通过全绿套件后再合并冻结。

---

## 状态

🚧 早期建设中。当前阶段：仓库初始化与桥接（Phase 0 / 第一阶段 P0–P1）。自主层（Judge Agent / 自动 Perplexity / daemon / 回测）按任务书 v1.1 逐 Phase 推进。

## License

[MIT](LICENSE)
