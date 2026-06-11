# gotra

> **गोत्र**（梵语「世系 / 谱系」）—— 让每一次投研判断都有可追溯的血脉：从信号到预测，从预测到观察，从误差归因到知识沉淀。

**gotra 是 [Alaya](https://github.com/amanayayatu-tech/Alaya) 与 [worldpay77](https://github.com/amanayayatu-tech/worldpay77) 两个项目的合并落地仓库**，目标是把二者连成一个可审计、可回滚、人类闸门兜底的**投研数据飞轮**：

- **[Alaya](https://github.com/amanayayatu-tech/Alaya)**（TypeScript）：治理底座 —— 事件账本、人类闸门（human gates）、预测/观察/误差归因内核、知识状态机
- **[worldpay77](https://github.com/amanayayatu-tech/worldpay77)**（Python）：领域引擎 —— 股票池扫描、F/W/G 委员会、Chairman 决策、红队审计、outcome 快照

合并原则：**Alaya 当治理底座，worldpay 当领域引擎；先契约后合库；不重写 Python。**

---

## 终态闭环（Definition of Done）

```text
worldpay morning run 扫描股票池
  → 导出 events.jsonl → 推入 Alaya（business signal，幂等）
  → PR-* prompt 在 Alaya 成为 pending meaning gate
  → 人在 Alaya（Web 或 Telegram）回填/跳过
  → gate_sync 写回 PR-*_filled.yaml，worldpay 下一轮引擎可消费
  → 委员会 + Chairman 产出 brief / decision_case
  → decision_case 进 Alaya prediction（1/7/30/90 天 claims）
  → 7 天后 outcome 快照 → 进 Alaya observation
  → Alaya 完成误差计算与归因
  → 研究结论进 Alaya knowledge_items，strong 晋级必经人类批准
  → 同 ticker 再研究时，双侧引用既有知识，被隔离知识不进引擎
```

每一步可审计；任一侧停机不阻塞另一侧。

## 架构形态

集成期维持**双仓库 + 桥接**：Alaya 与 worldpay77 各自独立运行、独立演进，gotra 是二者之间的**契约与桥接中枢**；契约连续 2 周无 breaking change 且 Phase 1–4 验收全绿后，再评估将引擎以 subtree 方式合入本仓。

```text
gotra/
  contracts/
    investment_event.schema.json   # 事件契约 v1（JSON Schema，跨仓 SoR）
  bridge/
    export_events.py               # worldpay run 产物 → events.jsonl（只读、幂等可重跑）
    push_to_alaya.py               # events.jsonl → POST Alaya API（signal/gate/prediction 分发）
    sync_gates.py                  # 轮询 Alaya resolved gates → 写回 PR-*_filled/_skipped.yaml
    sync_knowledge_filter.py       # 拉取 Alaya 知识状态 → quarantine_list.yaml（Phase 4）
    state/id_map.sqlite            # 双侧实体 ID 映射（桥接自身状态）
  docs/
    ROADMAP.md                     # 合并执行路线图（当前 v1.3）
  modules/                         # Phase 5 触发条件满足后，subtree 合入引擎（暂空）
```

### 核心架构决策（摘要）

| # | 决策 | 要点 |
| --- | --- | --- |
| D1 | 仓库形态 | 双仓库 + 桥接为默认；subtree 合仓后置，需触发条件 |
| D2 | 集成方式 | 文件 + HTTP，两条通道；不跨运行时 spawn；任一侧宕机不阻塞另一侧 |
| D3 | System of Record | 闸门状态、预测账本、知识状态机以 Alaya 为准；run/报告/原始 artifact 以 worldpay 为准 |
| D4 | 时间与窗口 | 全链 UTC；窗口与日期推算只在 worldpay 一侧计算，Alaya 只消费不重算；停牌顺延超阈打 `window_drift` |
| D5 | 幂等与顺序 | `event_id` 确定性生成且全局唯一，导入侧以 dedupeKey 去重；前置实体缺失记 errors 不静默落库 |
| D6 | 冻结底线 | strong 知识必过人类闸；审计不可旁路；不下单、不接券商、不输出买卖指令 |
| D7 | 桥接通信 | Bearer key 鉴权；批量 ≤500；指数退避重试；文件目录即天然队列，积压可告警 |

完整决策与执行细节见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。

## 里程碑

| 阶段 | 内容 | 工期 | 硬性退出标准 |
| --- | --- | --- | --- |
| P0 | 契约与原则冻结 | 0.5–1 天 | schema 校验过、双仓 PR 合并 |
| P1 | 最小事件链路（exporter + pusher） | 2–4 天 | 幂等验证 V1–V4 全过 |
| P2 | Deep Research 闸门 + 双向回写 | 4–6 天 | filled/skipped 双路径 E2E 绿 |
| P3 | 决策进 Prediction Ledger | 4–6 天 | 1 条真实归因链完整 |
| P4 | 知识 SoR 落地与反向过滤 | 1–2 周 | 隔离双侧生效、无自动 strong |
| P5 | 调度与 UI 收敛（后置） | 触发条件制 | 契约稳定 2 周后进入 |

合计约 4–7 周到达终态（单人兼职，含 1 周端到端观察期）。每阶段独立可回滚。

## 快速开始

前置：本地已 clone 并能独立运行两个上游项目。

```bash
# 1. Alaya（治理底座，端口 5000）
git clone https://github.com/amanayayatu-tech/Alaya.git
cd Alaya && npm install && npm run dev

# 2. worldpay77（领域引擎，端口 7777）
git clone https://github.com/amanayayatu-tech/worldpay77.git
cd worldpay77 && uv sync && uv run python webui.py

# 3. gotra（契约 + 桥接）
git clone https://github.com/amanayayatu-tech/gotra.git
cd gotra

# 校验事件契约
python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/investment_event.schema.json')))"

# 跑一轮最小链路（Phase 1）
python bridge/export_events.py --run-id RUN-xxx --out exports/events-RUN-xxx.jsonl
python bridge/push_to_alaya.py --events exports/events-RUN-xxx.jsonl \
  --alaya-url http://localhost:5000 --project-id $PID
```

## 验收清单

- [ ] **幂等**：任意导入重放零副作用（同一 events.jsonl 推两次，信号行数不变）
- [ ] **审计**：每次跨系统写入在 event_log / trace 留痕，可回答「谁、何时、依据哪个 artifact」
- [ ] **回写**：Alaya 闸门结果在 worldpay 文件系统物化且被引擎消费
- [ ] **账本**：prediction → observation → error → 归因 全链可见
- [ ] **治理**：无自动 strong；quarantined 知识不进引擎；冲突知识进 review
- [ ] **边界**：全程无下单/券商调用
- [ ] **独立性**：停掉任一侧，另一侧本职功能不受影响

## License

[MIT](LICENSE)
