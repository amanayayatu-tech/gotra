# gotra

> **गोत्र**（梵语「世系 / 谱系」）—— 让每一次投研判断都有可追溯的血脉：从信号到预测，从预测到观察，从误差归因到知识沉淀。

**gotra 是一个自主、可审计、人类闸门兜底的投研数据飞轮。**

给它一份固定的股票池，它每天自动完成研究、判断、预测、误差归因与知识沉淀，早晚各产出一份详细报告。整个过程零人工干预——唯一保留的人类动作，是为「知识晋级为长期信念（strong）」这一最危险的一步做一次一键确认。系统的目标不是预测得更准，而是**越跑越准**：把每一次判断的对错沉淀成可复用、可审计、可隔离的知识，形成认知复利。

---

## 为什么是 gotra

市面上的 AI 投研工具大多是「一次性」的：每次提问都从零开始，既不记得上次错在哪，也无法证明自己在变好。gotra 反其道而行：

- **有记忆的判断** —— 每个决策都进预测账本，到期后用真实价格计算误差并归因，反馈进知识库的置信度模型（Beta 自适应）。错误的认知会被自动隔离，正确的认知被反复印证后才晋级。
- **可审计的血脉** —— 从信号、预测、观察、误差到知识，每一步写操作都留痕，能回答「这条结论是谁、哪一轮、依据什么证据产生的」。
- **守得住的边界** —— 不下单、不接券商、不输出买卖指令；最危险的认知晋级必须经人类确认，机器永远不能自封「真理」。
- **真正自主** —— 一份股票池之外，研究、闸门判断、报告全自动；人只在每天的晚报里花一分钟，批准值得长期相信的少数结论。

---

## 核心理念：六条不可违反的底线

这是 gotra 之所以是 gotra 的定义性约束，全程冻结：

1. **数学心脏保持纯净** —— 误差计算、误差归因、置信度更新、状态迁移四个核心函数无副作用、时间靠参数注入，保证整个飞轮可复现、可单测、可审计。
2. **strong 晋级必过人类闸** —— 知识晋级为长期信念必须人类批准，**禁止任何「为了跑得快」的自动批准开关**。机器自封 strong = 自我强化的幻觉闭环。
3. **审计不可旁路** —— 一切写操作经会记录操作者（actor）的审计路径，禁止绕过审计的裸写。
4. **脏知识不进高风险证据** —— 过期、隔离、冲突状态的知识不得进入高风险决策的证据集，过滤条件只增不减。
5. **灰区不简化** —— 模糊反馈弱累加、连续模糊触发人类判断，不黑白二分。
6. **模型留在接口后** —— 全系统的模型调用只经统一接口，保证可复现的回归基准与零改动的真实推理注入。

> **认知熵减的本质**：让脏数据失去影响力（降级、隔离、排除出证据集），而不是让它消失。前者可逆、可审计、可申诉；后者一旦做错就是不可逆的认知损失。

---

## 自主闭环（Definition of Done）

```text
唯一人工输入：股票池（固定持仓 + 研究公司）
  → 调度器每日早 / 晚两次自动触发完整流水线
  → 自动深度研究：把研究问题派发给 Perplexity Deep Research，结果自动回填
  → F/W/G 委员会 + Chairman 产出研究简报与决策案例
  → Judge Agent 自动判决闸门：研究闸 / 风险闸全自动放行或驳回
  → 决策案例进入预测账本（1/7/30/90 天 claims，禁用未来数据）
  → 窗口到期 → 观察快照 → 误差计算与归因
  → 误差反馈进知识库（置信度自适应）；误差超阈的知识自动隔离（只隔离不删）
  → strong 知识候选进【晚报待批清单】，由人一键批准（唯一保留的人工动作）
  → 每日早报 / 晚报 自动推送
  → 同一标的再研究时引用既有可信知识，被隔离的知识不进引擎
```

**全系统模型推理统一为 `gpt-5.5`、reasoning effort = `xhigh`，经 Codex CLI 调用。** 每一步可审计；任一子系统停机不阻塞其余部分。

---

## 系统架构

gotra 由四个协作子系统组成，通过事件契约与文件 / HTTP 通道松耦合，各自独立运行、互不阻塞：

| 子系统 | 职责 |
| --- | --- |
| **治理内核**（TypeScript） | 事件账本、人类闸门、预测 / 观察 / 误差归因内核、知识状态机（draft→active→strong / stale / quarantined / conflict） |
| **领域引擎**（Python） | 股票池扫描、F/W/G 委员会、Chairman 决策、红队审计、outcome 快照、自然日窗口取数（零未来函数） |
| **自主层** | 自动 Perplexity 执行器、Judge Agent 分级自动闸门、auto-quarantine、daemon 早晚双窗口调度、每日报告与通知 |
| **回测层** | 10 股 × 10 年 Walk-Forward 零未来函数回测，验证「认知复利」真实有效 |

```text
gotra/
  governance/                  # 治理内核：账本 / 闸门 / 预测 / 归因 / 知识状态机
  engine/                      # 领域引擎：股票池 / 委员会 / Chairman / 红队 / outcome
  autonomy/
    perplexity_executor/       # 自动深度研究执行器
    judge_agent/               # Judge Agent 分级自动闸门 + auto_quarantine
    daemon/                    # 早晚双窗口自主调度
    reporting/                 # 每日报告 + Telegram / SMTP 通知
  backtest/                    # Walk-Forward 回测 harness + 价格缓存
  contracts/
    investment_event.schema.json   # 跨子系统事件契约（JSON Schema）
  data/
    stock_pool/master_pool.yaml     # 唯一人工输入：固定持仓 + 研究公司
  docs/
    ROADMAP.md                 # 分阶段执行路线图
    AUTONOMY_RUNBOOK.md        # 自主化 + 回测 可执行任务书（Codex 逐 Phase 执行）
```

### Judge Agent · 分级自主

闸门判断按风险分级，既做到日常零人工，又守住宪法底线：

- **研究闸（meaning）/ 风险闸（risk）** → 全自动放行 / 驳回，由 `gpt-5.5 xhigh` 给出结构化判决，理由区分「方法论分歧」与「潜在错误」，全程留痕。
- **strong 晋级** → **绝不自动**。候选写入晚报待批清单，由人一键批准。这是被反复引用的长期资产，必须守住人类这道物理隔断（底线 2）。

---

## 效力验收：10 股 × 10 年 Walk-Forward 回测

系统是否真的具备「认知复利」，用一个**零未来函数（No Lookahead Bias）**的滚动回测来证明：

- **数据**：10 只代表性港股 / 美股（腾讯、美团、众安、NVIDIA、小米、阿里、比亚迪、苹果、台积电、微软）2016–2026 日频数据。
- **滚动窗口**：1 年初始化窗口，滚动预测下 1 个月，逐月前进。任一 T 时刻决策**只用可得时间 ≤ T 的数据**——三层防泄漏：价格按 `date≤T` 切片、基本面按财报发布日门控、回测期禁实时联网研究。
- **消融对比**：认知复利臂（带知识库 + 置信度自适应）vs Baseline 臂（无状态单步）。**两臂共用同一 `gpt-5.5 xhigh` 模型与 prompt 骨架，唯一变量 = 是否带认知复利。**
- **指标**：MSE 演化。预期复利臂随时间收敛，Baseline 臂在市场风格切换时灾难性漂移；以差分（Diebold-Mariano + Newey-West HAC）度量机制净增量效应。
- **诚实声明**：现成大模型跑历史回测存在不可消除的预训练泄漏，故**绝对 MSE 不可信**，结论仅就「机制差分效应」成立；指标开跑前预注册 + 时间戳锁定，杜绝 p-hacking。

「全绿」分两类：**Correctness 闸**（零未来函数审计、无崩溃、可复现、纯函数单测、全程审计留痕）必须 100% 通过以证明实验有效；**Hypothesis 闸**（MSE 收敛 / 抗漂移 / 差分显著）是真实科学结论，达成则验证「认知复利有效」，未达成如实报负结果。

---

## 路线图

| 阶段 | 内容 | 关键退出标准 |
| --- | --- | --- |
| Phase 0 | 工作区初始化、事件契约、目录骨架 | 子系统可加载、契约校验通过 |
| Phase A | 模型调用统一走 Codex CLI（gpt-5.5 xhigh）+ provider 物理只读硬化 | provider 隔离生效、无行为漂移 |
| Phase B0 | 治理内核 automation-actor 合同（**strong 仍 human-only**） | 自动化可放行闸门 / 隔离知识，**永不能晋级 strong** |
| Phase P | 自动 Perplexity 执行器 | 研究问题自动回填，引擎纯度守护测试仍全绿 |
| Phase B | Judge Agent 分级自动闸门 + auto-quarantine | 闸门决策自动留痕、无自动 strong |
| Phase C | daemon 自主调度 + 每日早晚报告 + 通知 | 两窗口完整运行、strong 待批可一键批 |
| Phase BT | 10×10×10年 Walk-Forward 回测（效力验收） | Correctness 闸 100% 全绿 |

详见 [`docs/AUTONOMY_RUNBOOK.md`](docs/AUTONOMY_RUNBOOK.md) 与 [`docs/ROADMAP.md`](docs/ROADMAP.md)。本仓库按可被 **Codex `goal` / `codex exec`** 逐 Phase 自主执行的任务书组织；每个 Phase 在独立分支实现、自验通过全绿套件后再合并冻结。

---

## 快速开始

前置：本机已安装并登录 Codex CLI（系统所有模型调用经此）。

```bash
git clone https://github.com/amanayayatu-tech/gotra.git
cd gotra
git submodule update --init --recursive

# 安装依赖
uv venv && source .venv/bin/activate
uv sync

# 配置环境（全系统模型调用走 Codex CLI · gpt-5.5 · xhigh）
cp .env.example .env
#   LLM_PROVIDER=codex_cli
#   LLM_MODEL=gpt-5.5
#   CODEX_PROVIDER_REASONING_EFFORT=xhigh
#   AUTO_JUDGE=true
#   PERPLEXITY_API_KEY=...      # 仅实盘自主用；回测期置空

# 校验事件契约
python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/investment_event.schema.json')))"

# daemon 干跑（验证编排串联与失败隔离，不实跑模型）
python -m autonomy.daemon.run --once --type morning --dry-run
```

---

## 状态

🚧 早期建设中。当前阶段：工作区初始化与事件链路（Phase 0 / Phase A）。自主层（Judge Agent / 自动 Perplexity / daemon / 回测）按任务书逐 Phase 推进。

## License

[MIT](LICENSE)
