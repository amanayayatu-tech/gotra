# Alaya × ksana 投研数据飞轮 · 合并执行路线图（修订版 v1.3）

> **命名说明（2026-06-13 更新）**：本文撰写时领域引擎仓库名为 `worldpay77`，现已改名为 **`ksana`**（`github.com/amanayayatu-tech/ksana`）。全文出现的 `worldpay77` / `worldpay` 一律等同 `ksana`，路径与命令照旧有效。本路线图覆盖**第一阶段·桥接基础（P0–P4）**；在其之上的**全自主化与回测扩展**见 [`AUTONOMY_RUNBOOK.md`](AUTONOMY_RUNBOOK.md)（执行任务书 v1.1）。在 gotra 中，ksana 以 git 子模块 `engine/ksana`（冻结 + 纯净）形态存在，桥接代码统一放在 gotra 的 `integrations/alaya/` 与 `contracts/`。
>
> 日期：2026-06-11（v1.3，同日第三轮复核）
> 基线：worldpay77 @ `Stabilize WebUI UX states`（2026-06-08）；Alaya @ `Merge phase2: sensor firewall + attribution confidence`（2026-06-11）
> 性质：在原《Alaya × worldpay77 合并建议》基础上的**修订执行版**。原建议的方向（Alaya 治理底座 + worldpay 领域引擎、先契约后合库、不重写 Python）全部保留；本文 v1.0 修正了原建议的 6 个执行层问题（见下表），并把每一步落到已核实的真实命令、文件路径和 API 上；v1.1–v1.3 为三轮复核修订（见下方记录）。
> v1.1（同日复核）：依据外部评审核查后修订 10 处——skipped 事件三表去向对齐；filled / knowledge_card 双知识路径界定与统一去重键；新增 D7 桥接通信规格（复用 Alaya 现有 `ALAYA_API_KEY` 鉴权 + 重试/轮询/积压）；**修正 D4 事实错误**（经查 worldpay 实为自然日窗口而非交易日历）并确立窗口单点计算原则；附录 B 两处口径修正；exporter stdout 静默约束；sqlite 直连只读注记；sha256 漂移负向用例；schema_version 升级操作细则；工期合计修正为 4–7 周。
> v1.2（第二轮复核）：清扫 D4 纠错的下游残留——附录 A 信封表 `as_of_date` / `market` 措辞与 D4 字字对齐，D4 改写为"三基准并排"公式；**再修正一处取数方向事实错误**——代码 `first_row_on_or_after` 是向后顺延到下一个有数据交易日，v1.1 误写为"不晚于截止日"的回退（外部评审建议的"回退最近交易日"同样与代码不符，一并按代码纠正）；修补 v1.1 引入的衔接漏洞——信封新增可选 `replay` 字段，历史回填的 created 不建 pending gate，filled/skipped 前置改为同 pr_id 的 created 信号、与 gate 解耦，pending gate 由 importer 代 resolve（顺带消除 webui 双入口悬挂闸）；Runbook 前置补鉴权约定；3.4 补 audit id 查重；修订计数表述消歧。
> v1.3（第三轮复核）：M1——对照代码确认顺延**硬上界**为 `outcome_as_of`（候选行预过滤 `<= outcome_as_of`），与 `future_data_allowed=false` 不冲突；顺延在上界内无固定上限属实，新增 `window_drift` 治理（payload 增带 `price_start_date`/`price_end_date`，阈值默认 5 自然日，超限降权复核），并顺带封堵同根缺口——pending 快照不导出 observation、同一 (case, window) 至多一条；M2——replay 信号保留落库以保审计真相（`observedAt` 取历史原始时间），payload 必带 `replay=true`，统计/面板默认过滤；M3——replay 行内注明 schema 不入 required、`default: false`；M4——风险表补 3 行（重放灌入、代 resolve 误判、窗口漂移）；附录 C「唯一核心改动」表述随 P3 两行增量字段同步修正。

**v1.0 相对原建议的 6 处修订**：

| # | 原建议 | 修订为 | 原因 |
| --- | --- | --- | --- |
| 1 | Phase 2 回填进 Alaya knowledge candidate | **双向回写**：闸门 resolve 后必须写回 `data/perplexity_results/PR-*_filled.yaml` | F/W/G 读的是 worldpay 自己的 knowledge store（由 `*_filled.yaml` 重建）；只进 Alaya 则引擎下轮看不到，闸门失效 |
| 2 | subtree 合仓为主、双仓库为备选 | **双仓库 + 桥接包为默认**；subtree 设触发条件后置 | 两仓库本周都有提交、均在高频演进；过早合仓带来同步成本 |
| 3 | Alaya 用 `child_process.spawn` 调 `uv run` | **文件 + HTTP 集成**，不跨运行时 spawn | spawn 要求 Alaya 部署环境同时有 Node + Python/uv，破坏现有 Docker shadow 部署；worldpay 自有 `daemon.py` 可独立跑 |
| 4 | 第一张 PR 含新 API + 新 importer + 新 UI 页 | **第一刀更小**：复用现成 `POST /api/projects/:id/business-signals/import` | 该端点已存在且自带 `dedupeKey` 去重；UI 拆到 Phase 5 |
| 5 | 契约只有 event_id + sha256 | 契约显式加入**幂等与顺序规则** | 重复导入、乱序导入是事件集成最常见的脏数据来源 |
| 6 | 知识同时存两边、关系未定 | **Phase 0 写死 SoR**：知识状态机以 Alaya 为准，worldpay store 是按状态过滤的读视图；`as_of_date` 钉死时区 | 双知识库无主必然漂移；时区不钉死，1D/7D outcome 对不上 |

---

## 0. 终态定义（Definition of Done）

"跑起来"指以下闭环在真实数据上完整转一圈，且每一步可审计：

```text
worldpay morning run 扫描股票池
  → 导出 events.jsonl → 推入 Alaya（business signal，幂等）
  → PR-* prompt 在 Alaya 成为 pending meaning gate
  → 人在 Alaya（Web 或 Telegram）回填/跳过
  → gate_sync 写回 PR-*_filled.yaml，worldpay 下一轮引擎可消费
  → 委员会 + Chairman 产出 brief / decision_case
  → decision_case 进 Alaya prediction（1/7/30/90 天 claims，future_data_allowed=false）
  → 7 天后 refresh_outcome_snapshots 产出快照 → 进 Alaya observation
  → Alaya compute_error / classify_error 完成误差归因
  → 研究结论进 Alaya knowledge_items（draft/active），strong 晋级必经人类批准
  → 同 ticker 再次研究时，worldpay 引擎与 Alaya 双侧都能引用既有知识，被隔离知识不进引擎
```

**最终验收标准（第 9 节 Runbook 逐条验证）**：

1. 同一份 `events.jsonl` 导入两次，Alaya 信号行数不变（幂等）。
2. 每次跨系统写入在 Alaya `event_log` / `trace_events` 留痕，无 `rawDb` 裸写。
3. 在 Alaya 回填的研究，worldpay 下一次 run 的 `PerplexityContext` 状态为 filled。
4. 每个 decision_case 在 Alaya 能看到 prediction → observation → error → 归因 的完整链。
5. 不存在机器自动晋级的 strong 知识；`quarantined/conflict` 知识不出现在引擎高风险上下文。

---

## 1. 冻结的架构决策（实施前先共识，写进 Phase 0 文档）

**D1 仓库形态**：双仓库。桥接代码统一放在 `worldpay77/integrations/alaya/`（Python，因为它读写的是 worldpay 数据目录）；契约 schema 放 `worldpay77/contracts/`，Alaya 侧测试只持有 fixture 副本。subtree 仅在"契约连续 2 周零 breaking change"后再评估。

**D2 集成方式**：worldpay 与 Alaya 各自独立运行（`uv run python webui.py` @ 7777 / `npm run dev` @ 5000）。集成只通过两条通道：worldpay 导出 JSONL → 桥接脚本 POST Alaya API；桥接脚本轮询 Alaya API → 写 worldpay data 文件。任何一侧宕机不阻塞另一侧。

**D3 System of Record（谁说了算）**：

| 资产 | SoR | 另一侧的角色 |
| --- | --- | --- |
| 股票池 / run / 报告 / 原始 YAML artifact | worldpay `data/` | Alaya 存索引、摘要、`source_artifact_path`、sha256 |
| 人类闸门状态（pending/approved/rejected） | Alaya `human_gate_items` | worldpay 的 filled/skipped 文件是闸门结果的**物化** |
| 预测 / 观察 / 误差归因 | Alaya `predictions` / `observations` | worldpay `decision_case` / `outcome_snapshot` 是事实来源（输入），不是账本 |
| 知识状态机（draft/active/strong/stale/conflict/quarantined） | Alaya `knowledge_items` | worldpay knowledge store 是**按 Alaya 状态过滤后的读视图**（Phase 4 落地） |
| F/W/G/Chairman/Red Team 方法论 | worldpay `methodologies/` | Alaya 不复制、不稀释 |

**D4 时间、时区与窗口单点计算**：事件信封时间戳一律 UTC ISO 8601；payload 必带 `market` 字段（决定时区与价格数据所属交易所，美股按 America/New_York 收盘口径）。三个基准并排写死（均以 `learning.py: build_outcome_snapshots_for_case` 代码为准）：① `as_of_date` = 决策基准日（brief 日期，交易日语义，YYYY-MM-DD）；② 窗口加法 = **自然日**（`end_date = decision_date + timedelta(days=window)`，`DEFAULT_WINDOWS = [1, 7, 30, 90]`），不是交易日历窗口；③ 取数 = `first_row_on_or_after`——起点价取 `as_of_date` **当日或之后**第一个有数据交易日，终点价取 `end_date` **当日或之后**第一个有数据交易日（**向后顺延，不是回退**）；窗口未到期（`end_date > outcome_as_of`）则快照为 `pending / not_due`。为根除两侧对不齐：**窗口与日期推算只发生在 worldpay 一侧**，`outcome_snapshot_created` 事件 payload 透传快照原生字段 `window_days` / `window_end_date` / `decision_date` / `outcome_as_of`，Alaya 只消费、永不自行重算。④ 顺延边界（对照代码确认）：候选行在搜索前已预过滤 `<= outcome_as_of`，故顺延的**硬上界是取数截止日**，永远不会取 cutoff 之后的数据——与 `future_data_allowed=false` 不冲突；停牌至 cutoff 仍无行，则快照保持 `pending`、不产生观察值。但顺延在上界内**无固定上限**，等于把停牌票的窗口隐性拉长，治理规则：payload 增带 `price_start_date` / `price_end_date`，定义 `roll_forward_days = price_end_date − window_end_date`（自然日），超过阈值（默认 5，可配）→ Alaya 侧 observation 打 `window_drift` 标记，归因结果降权并转人工复核，不得静默当作正常窗口。

**D5 幂等与顺序**：`event_id` 全局唯一且确定性生成（`evt_{run_id}_{event_type}_{业务主键}`）；导入侧以 `dedupeKey = event_id` 去重（Alaya `importBusinessSignals` 原生支持：命中 dedupe 计 `skipped`，不产生新行）；导入按文件行序处理，遇到引用未到达实体的事件（如 brief 先于 run）记 `errors` 并跳过，不得静默落库。

**D6 不可违反约束（全程冻结）**：继承 Alaya `PRINCIPLES.md` Part 1 全部底线（纯函数、strong 必过人类闸、审计不可旁路、脏知识不进高风险证据、灰区不简化、LLM 走 Provider 接口）；继承 worldpay 产品边界（不下单、不接券商、不输出买卖指令）；Partner Performance 只给 Chairman 与人看，不回喂 F/W/G；outcome snapshot 是 observation，不自动等于 thesis 真相。

**D7 桥接通信规格（鉴权 / 重试 / 轮询 / 积压）**：

- 鉴权：复用 Alaya 现有机制（`server/security/auth.ts`，已核实），不另造令牌。桥接脚本读环境变量 `ALAYA_API_KEY`，请求携带 `Authorization: Bearer <key>`（或 `X-Alaya-API-Key` 头）。本地开发双侧仅绑定 localhost 时可不设 key；Alaya 在 shadow/staging/production 模式会强制要求 key（`isApiAuthRequired` 逻辑），届时桥接必须配齐。
- pusher（写 Alaya）：单批 ≤500（端点上限）；单请求超时 10s；失败按指数退避重试（1/2/4/8/16s，至多 5 次）；重试耗尽则该批记 errors、进程退出码非 0，jsonl 原样保留供重放（幂等由 dedupeKey 兜底，重放安全）。
- sync_gates / sync_knowledge_filter（读 Alaya）：默认 60s 轮询（可配）；单轮失败不退出，连续失败 ≥10 轮向 stderr 告警并以非 0 退出，交由 cron/daemon 拉起。
- 积压与告警：`data/exports/` 即天然队列；Alaya 不可达时事件文件原地等待，未推送文件滞留 >24h 或 >50 个时告警。任一侧停机，另一侧本职功能照常（呼应 D2）。

---

## 2. 集成拓扑与目录

```text
worldpay77/
  contracts/
    investment_event.schema.json      # 事件契约 v1（附录 A）
  integrations/alaya/
    export_events.py                  # run 产物 → events.jsonl（只读 data/，幂等可重跑）
    push_to_alaya.py                  # events.jsonl → POST Alaya API（signal / prediction / observation 分发）
    sync_gates.py                     # 轮询 Alaya resolved gates → 写 PR-*_filled.yaml / _skipped.yaml
    sync_knowledge_filter.py          # Phase 4：拉取 Alaya 知识状态 → 写 quarantine_list.yaml
    state/id_map.sqlite               # worldpay 实体 ID ↔ Alaya 实体 ID 映射（桥接自身状态）
    README.md

Alaya/（改动刻意最小）
  alaya-app/server/investmentResearch/
    importer.ts                       # Phase 2 起：闸门/预测类事件的服务层导入器（经 storage/service，禁 rawDb）
  alaya-app/tests/investment-*.test.ts
  docs/investment-module-architecture.md
```

Phase 1 **不改 Alaya 任何服务端代码**；Phase 2 起才新增 `investmentResearch/` 模块。

---

## 3. Phase 0 — 契约与原则冻结（0.5–1 天）

**目标**：把第 1 节六项决策与附录 A 契约写成文档并双仓库落库，后续争议回到文档裁决。

**步骤**

1. 在 Alaya 仓库新建 `docs/investment-module-architecture.md`，内容 = 本文第 0/1 节 + 附录 A/B。
2. 在 worldpay77 仓库新建 `contracts/investment_event.schema.json`（按附录 A 写 JSON Schema），并建 `integrations/alaya/` 空骨架 + README。
3. 在 Alaya 创建投研载体：`POST /api/projects` 建项目（如 `investment-research`），确认其存在活跃 cycle（`importBusinessSignals` 要求项目有 cycle 才能挂信号）；`POST /api/projects/:id/org-modules` 注册 `WorldPay ResearchOS` 模块。

**验证**

```bash
# schema 自身合法
python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/investment_event.schema.json')))"
# Alaya 项目与模块就位
curl -s localhost:5000/api/projects | jq '.[] | {id, name}'
curl -s localhost:5000/api/projects/$PID/org-modules | jq
```

**退出标准**：两仓库各一个 PR 合并；schema 校验通过；Alaya 中投研 project + org module 可见且有活跃 cycle。

---

## 4. Phase 1 — 最小事件链路（2–4 天）

**目标**：一次 worldpay run 的元数据与研究信号，以事件形式幂等进入 Alaya，并可在 Alaya 中看到。**不碰闸门、不碰预测、不改 worldpay 核心、不改 Alaya 服务端。**

**步骤**

1.1 实现 `export_events.py`：读取一次 run 的 `data/research_runs/`、`data/research_signals/`、`data/pull_requests/`，产出 `investment_run_started`、`research_signal_created`、`research_prompt_created` 三类事件到 `data/exports/events-{run_id}.jsonl`。每行过 schema 校验；`sha256` 取自源 YAML 文件。重跑同一 run 输出逐字节一致（事件 ID 确定性生成，列表排序后写出）；`--out /dev/stdout` 模式下 stdout 只含 JSONL 本体，日志与进度一律走 stderr——V2 的 diff 验证依赖这一点。

```bash
uv run python integrations/alaya/export_events.py --run-id RUN-xxx \
  --out data/exports/events-RUN-xxx.jsonl
```

1.2 实现 `push_to_alaya.py`：把 jsonl 行映射为信号行，批量（≤500/批，与端点上限一致）POST 现有端点：

```bash
uv run python integrations/alaya/push_to_alaya.py \
  --events data/exports/events-RUN-xxx.jsonl \
  --alaya-url http://localhost:5000 --project-id $PID
```

字段映射（落 `external_business_signals` 表，已核实字段）：`source="worldpay_researchos"`、`sourceId=源实体 ID（RS-*/PR-*/RUN-*）`、`signalType=event_type`、`observedAt=事件 UTC 时间`、`payload=事件 payload + source_artifact_path + sha256 + as_of_date（信封 replay=true 时一并并入，供统计过滤）`、`sensitivityLevel/riskLevel` 按契约默认、**`dedupeKey=event_id`**。其余必填默认值以 `server/businessSignals.ts: normalizeBusinessSignal` 为准，实现时对照一次。pusher 默认开启 `--verify-artifacts`：推送前用事件 `sha256` 比对本地 artifact，不一致则该事件记 errors 不推送。

1.3 跑一次真实 morning run 作为数据源：

```bash
uv run orchestrator run --type full --brief-type morning --date 2026-06-11
```

1.4 导出 → 推送 → 在 Alaya 查看。

**验证（全部通过才算完成）**

```bash
# V1 幂等：推送两次，第二次 imported=0、skipped=N，总行数不变
uv run python integrations/alaya/push_to_alaya.py ... | jq '{imported, skipped}'
curl -s "localhost:5000/api/projects/$PID/business-signals" | jq length   # 两次之间不变

# V2 导出确定性：同 run 导出两次，diff 为空
diff <(uv run python ... export_events.py --run-id RUN-xxx --out /dev/stdout) \
     <(uv run python ... export_events.py --run-id RUN-xxx --out /dev/stdout)

# V3 审计留痕：导入动作出现在 event_log（先 .schema 看列名再查）
# 注意：sqlite3 直连仅限只读验证；任何写入必须走 service 层/API（D6）
sqlite3 alaya-app/data.db '.schema event_log'
sqlite3 alaya-app/data.db "select count(*) from external_business_signals where source='worldpay_researchos';"

# V4 信号可回链：任取一条信号，payload 内 source_artifact_path 指向的 YAML 存在且 sha256 一致
```

- 自动化：worldpay 侧 pytest 覆盖 exporter（fixture run → 期望 jsonl 快照）；桥接侧用 mock HTTP 测 pusher 的分批与重试。
- 负向用例一：jsonl 中混入缺 `event_id` 的行 → pusher 报错该行并继续，退出码非 0。
- 负向用例二：导出后篡改某个源 artifact → `--verify-artifacts` 检出 sha256 不匹配，该事件不推送、退出码非 0（即 V4 的自动化形态）。

**退出标准**：V1–V4 通过；CI 绿；Alaya 信号列表里能按 `signalType` 看到该 run 的 signals 与 prompts，并能点回 worldpay 原始 artifact 路径。

**回滚**：删 `integrations/alaya/`，Alaya 零代码改动，无迁移。

---

## 5. Phase 2 — Deep Research 闸门 + 双向回写（4–6 天）

**目标**：`PR-*` prompt 成为 Alaya meaning gate；人在 Alaya 回填/跳过后，结果**物化回 worldpay 文件**，引擎下一轮真实消费。这是修订 #1 的落点，也是本路线图与原建议最大的差异。

**步骤**

2.1 Alaya 侧新增 `server/investmentResearch/importer.ts` + 端点 `POST /api/projects/:id/investment/import-events`：只处理需要建实体的事件类型。`research_prompt_created` → 经 `storage.createGate()` / humanGateService 建 `type="meaning"` 的 pending gate（gate payload 带 `pr_id`、prompt 文本、`source_artifact_path`）。同一 `pr_id` 重复导入不重复建闸（查既有 gate 先行）。所有写入走 service 层并落 `event_log`（PRINCIPLES 底线 3）。

2.2 `push_to_alaya.py` 升级为分发器：signal 类事件走原 business-signals 端点；gate 类事件走新端点。

2.3 实现 `sync_gates.py`（worldpay 侧轮询，本地优先、无 webhook 依赖）：

```text
GET /api/human-gates?projectId=$PID  → 过滤 resolved 且带 pr_id 的投研闸
  approve + 回填内容 → 写 data/perplexity_results/PR-*_filled.yaml（含答案、来源、prompt_text，复刻 webui 保存格式）
  reject / skip 理由  → 写 PR-*_skipped.yaml
  写完后在 id_map.sqlite 记 synced，避免重复写
```

已核实消费链：`business_agents/_common/perplexity_results.py` 读 `{prompt_id}_filled.yaml`；`knowledge_store.py` 由全部 `*_filled.yaml` 重建知识库——**写对这个文件，引擎自然消费，无需改 worldpay 核心**。

2.4 回填后的研究结论同时作为 Alaya 知识候选：importer 对 `research_prompt_filled` 建 `knowledge_items`（初始 draft/active，禁直 strong），tags 含 `domain:investment`、`ticker:*`、`source_pr_id:*`；知识去重键 = `source_pr_id`，同键重复事件不重复建条。`research_prompt_skipped` **不进知识路径**，仅落 decision_log（与附录 A 一致）。filled/skipped 事件的**前置实体是同 pr_id 的 `research_prompt_created` 信号（P1 层），不是 gate**——与闸门解耦；若 Alaya 存在同 pr_id 的 pending gate，importer 收到 filled/skipped 时以事件来源为 actor 将该闸 resolve 并留审计（顺带消除 webui 直接回填导致 Alaya 闸悬挂的缝隙），不存在则不补建。

**验证**

```bash
# 端到端单条链路
# 1) Phase 1 流程推入含 PR-20260611-NVDA 的事件
curl -s "localhost:5000/api/human-gates?projectId=$PID" | jq '.[] | select(.status=="pending")'
# 2) 在 Alaya Web 回填并 approve（或 Telegram 审批）
curl -s -X POST localhost:5000/api/human-gates/$GID/approve -d '{...回填内容...}'
# 3) 同步回 worldpay
uv run python integrations/alaya/sync_gates.py --alaya-url http://localhost:5000 --project-id $PID
ls data/perplexity_results/ | grep PR-20260611-NVDA   # _filled.yaml 出现
# 4) 引擎消费验证：重跑委员会，Agent 不得再报"未回填"，confidence cap 解除
uv run orchestrator rerun --run-id RUN-xxx --from-step partners
```

- 幂等：`sync_gates.py` 连跑两次，第二次零写入。
- 冲突保护：worldpay 本地已存在 `_filled.yaml` 而 Alaya 又 resolve 同一 PR → 同步器不覆盖，告警并要求人工裁决（文件先到者赢，留审计）。
- skip 路径：reject 闸 → `_skipped.yaml` → 下一轮 Agent confidence cap 仍生效且 `waiting_conditions` 可追溯。

**退出标准**：一条 prompt 完整走完"产生 → Alaya 闸 → 回填 → 文件回写 → 引擎消费"并有双侧审计记录；filled 与 skipped 两条路径测试均绿；webui 原回填入口同时可用（两入口写同一文件格式，互不破坏）。

**回滚**：停用 `sync_gates.py` + 下线新端点即可退回 Phase 1 状态；已写入的 filled.yaml 与人工回填等价，无需清理。

---

## 6. Phase 3 — 决策进 Prediction Ledger（4–6 天）

**目标**：Chairman 结论从"归档报告"变为"可验证预测"，接通 Alaya 误差归因内核。

**步骤**

3.1 exporter 增加 `chairman_brief_created`、`decision_case_created` 事件（源：`data/briefs/`、decision case 产物）。
3.2 桥接对每个 decision_case 调 `POST /api/predictions`：每个 ticker 一组 claims（1/7/30/90 天价格区间或 thesis 检查点），属性带 `future_data_allowed=false`、`as_of_date`、`source_artifact_path`；返回的 prediction id 写入 `id_map.sqlite`（`decision_case_id → prediction_id`）。重复事件查 id_map 先行，保证幂等。
3.3 exporter 增加 `outcome_snapshot_created`（源：`orchestrator/core/learning.py: refresh_outcome_snapshots()` 的产物；payload 透传快照原生字段 `window_days` / `window_end_date` / `decision_date` / `outcome_as_of` 及价格与 source_url，并增带 `price_start_date` / `price_end_date`——这需要 worldpay 一处两行纯增量改动：`build_outcome_snapshots_for_case` 输出补这两个日期字段，不改任何计算、附单测；口径见 D4）。导出规则：**仅对非 pending 快照发事件**——pending/not_due 无价格、不构成观察值；同一 `(case_id, window)` 至多导出一条（由 `id_map.sqlite` 记账）。桥接据 id_map 调 `PATCH /api/predictions/:id/observation`，随后 `PATCH /api/predictions/:id/error` 触发 `compute_error` / `classify_error`；drift 超限的 observation 按 D4 ④ 打标降权。
3.4 红队事件 `risk_audit_created` 进 Alaya：fatal flaw 类经 importer 建 `type="risk"` gate（阻塞性沿用 Alaya 既有 blocking 语义）；以 `audit id` 查重先行、重复事件不重复建闸（与 2.1 的 pr_id 规则同构），`audit id → gate id` 映射记入 id_map。

**验证**

```bash
# 造一条短窗口验证链（用 1 日窗口避免等 7 天）
uv run orchestrator run --type full --brief-type morning --date 2026-06-10
# 导出+推送 → 确认 prediction 建立
curl -s localhost:5000/api/projects/$PID/predictions | jq '.[] | {id, status}'
# 次日刷新 outcome → 导出 → 推送
uv run python -c "from orchestrator.core.learning import refresh_outcome_snapshots; ..."  # 或对应 CLI 步骤
curl -s localhost:5000/api/cycles/$CID/predictions | jq '.[] | {status, error}'  # observation 已挂、error 已算
```

- 关键断言：价格 observation 写入后，thesis 的最终判定仍停在"待人工/证据复核"，**不**自动闭环为对错（D6）。
- 幂等：同一 snapshot 事件重推不产生第二条 observation。
- 边界用例：构造停牌 fixture（`end_date` 后连续无行、随后复牌）→ observation 带 `window_drift` 与正确的 `roll_forward_days`；停牌未复牌至 cutoff → 不导出事件、不产生 observation。

**退出标准**：至少 1 个真实 decision_case 走完 prediction → observation → error → 归因；id_map 可逆查询；审计链完整。

**回滚**：predictions 为追加型资产，停桥接即可冻结；不需要删数据。

---

## 7. Phase 4 — 知识 SoR 落地与反向过滤（1–2 周）

**目标**：兑现 D3——知识状态机以 Alaya 为准，worldpay store 变成过滤后的读视图，杜绝双库漂移（修订 #6）。

**步骤**

4.1 历史回填：对每个存量 `*_filled.yaml`，按原始时间序生成 **`research_prompt_created`（`replay=true`）+ `research_prompt_filled`** 配对事件，重放进 Phase 2 同一条导入通道（不另写第二套写入逻辑）。`replay=true` 的 created 只落信号、**不建 pending gate**（附录 A 规则），从而满足 filled 的前置（同 pr_id created 信号，见 2.4），又不在 Alaya 留下一批无人处理的悬挂闸。tags 体系：`domain:investment` / `ticker:*` / `sector:*` / `theme:*` / `source:perplexity` / `source_pr_id:*`。`source_pr_id` 去重键保证与 P2 实时链路已导入的条目自然防重（重放计 skipped），不产生重复 knowledge_items。replay 事件照常落 business signal——审计保真，`observedAt` 取历史原始时间——但 payload 必带 `replay=true`，统计与信号面板默认按该标记过滤，避免一次性灌入的历史信号扭曲时间线（P4 在数据层即可区分，UI 过滤在 Phase 5 落地）。
4.2 strong 晋级唯一路径 = `POST /api/knowledge/:id/approve`（人类，PRINCIPLES 底线 2）；隔离 = `POST /api/knowledge/:id/quarantine`。
4.3 实现 `sync_knowledge_filter.py`：定期拉取 Alaya 中 `quarantined/conflict/stale` 的投研知识，按 `source_pr_id` 写 `data/perplexity_results/quarantine_list.yaml`。
4.4 worldpay 侧唯一一处核心改动：`business_agents/_common/knowledge_store.py` 加载时若存在 quarantine_list，则**剔除**名单内条目进入 Agent 上下文（高风险证据过滤只增不减，呼应 Alaya 底线 4）。带单测：名单内条目不得出现在重建后的 store。

**验证**

```bash
# 在 Alaya 隔离一条知识 → 同步 → 重建 store → 引擎上下文不含该条
curl -s -X POST localhost:5000/api/knowledge/$KID/quarantine
uv run python integrations/alaya/sync_knowledge_filter.py ...
uv run pytest tests/ -k quarantine
# 注入验证：同 ticker 再研究，Alaya 侧 active/strong 知识可检索注入；strong 数量只能由人工 approve 增加
curl -s "localhost:5000/api/knowledge?projectId=$PID" | jq '[.[] | select(.status=="strong")] | length'
```

**退出标准**：隔离知识双侧同时失效；strong 全部有人类审批记录；冲突知识进 knowledge review 而非被删除；`knowledge_store.py` 改动有独立单测且 worldpay 全量测试仍绿。

**回滚**：删除 quarantine_list.yaml 即恢复原行为（过滤钩子设计为"文件不存在 = 不过滤"）。

---

## 8. Phase 5 — 调度与 UI 收敛（后置，按触发条件进入）

**进入条件**：附录 A 契约连续 2 周无 breaking change，且 Phase 1–4 验收全绿。此前不投入。

- 调度：优先用 worldpay 自带 `daemon.py` 定时跑 run + 导出 + 推送（cron 串联三个命令即可）；只有当确需 Alaya scheduler 统一掌握节奏时，再评估 Alaya 调 worldpay webui 的 HTTP 触发（仍不 spawn）。
- UI 迁移顺序维持原建议：Investment Runs / Report Center → Deep Research Gates → Stock Timeline / Decision Cases → Partner Performance → Stock Pool。每迁一页，旧 Jinja 页保留只读一个迭代周期再下线。
- 仓库形态复评：满足进入条件后再讨论 `git subtree add --prefix modules/investment-research/engine ...`；在那之前双仓库就是终态。

---

## 9. 端到端验收 Runbook（最终 Goal 的逐步验证）

前置：两侧应用各自启动（worldpay `uv run python webui.py` @7777；Alaya `npm run dev` @5000）；Alaya 已有投研 project（含活跃 cycle）+ org module；`.env` 双侧就绪。**鉴权约定**：Alaya 处于 shadow/staging/production 模式（或已设置 `ALAYA_API_KEY`）时，本节及全文所有 `curl` 必须加 `-H "Authorization: Bearer $ALAYA_API_KEY"`（见 D7）；文中示例按本地开发模式书写，故省略该头。

| Day | 操作 | 验证命令 / 预期 |
| --- | --- | --- |
| D0-1 | `uv run orchestrator run --type full --brief-type morning --date <D0>` | `data/research_runs/` 出现 RUN-*；webui Report Center 可见 |
| D0-2 | `export_events.py` → `push_to_alaya.py` | 返回 `imported>0`；重推一次 `imported=0, skipped=N` |
| D0-3 | 检查闸门 | `GET /api/human-gates` 出现 pending meaning gates（含 cold-start PR） |
| D0-4 | 在 Alaya 回填 1 条、跳过 1 条 → `sync_gates.py` | `data/perplexity_results/` 同时出现 `_filled.yaml` 与 `_skipped.yaml` |
| D0-5 | `orchestrator rerun --from-step partners` | filled 的 ticker confidence cap 解除；skipped 的仍 cap 且 waiting_conditions 留痕 |
| D0-6 | brief / decision_case 事件推送 | `GET /api/projects/$PID/predictions` 出现 open prediction |
| D1 | 刷新 1 日 outcome → 导出推送 | prediction 挂上 observation，error 已计算 |
| D7 | 刷新 7 日 outcome → 同上 | 7D claim 归因完成；thesis 判定仍待人工复核（不自动闭环） |
| D7+ | 人在 Alaya 审一条知识为 strong；另一条 quarantine → `sync_knowledge_filter.py` | strong 有审批记录；quarantine 条目从引擎 store 消失 |
| D8 | 对同一 ticker 再跑 run | worldpay：PerplexityContext=filled，Agent 引用历史研究；Alaya：检索到 active/strong 知识 |

**最终检查清单**（全勾 = 项目目标达成）：

- [ ] 幂等：任意导入重放零副作用
- [ ] 审计：抽查 3 条跨系统写入，event_log/trace 可回答"谁、何时、依据哪个 artifact"
- [ ] 回写：Alaya 闸门结果在 worldpay 文件系统物化且被引擎消费
- [ ] 账本：prediction→observation→error→归因 全链可见
- [ ] 治理：无自动 strong；quarantined 不进引擎；冲突进 review
- [ ] 边界：全程无下单/券商调用；Partner Performance 未注入 F/W/G
- [ ] 独立性：停掉任一侧，另一侧本职功能不受影响（桥接积压、不报错退出）

---

## 10. 风险登记与回滚总览

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 语义混淆（Alaya cycle ≠ worldpay run） | 事件强制带 `domain/as_of_date/source_artifact_path/future_data_allowed` | 事件可重放，修正映射后重导 |
| 回填双入口冲突（webui 与 Alaya 同时回填同一 PR） | 文件先到者赢 + 同步器告警人工裁决 | 文件即真相，无需数据修复 |
| 价格结果被当 thesis 真相 | observation 与 thesis 判定分离，复核必留人工步骤 | — |
| 投研知识被自动拔成 strong | 唯一晋级路径走 approve API；CI 断言导入测试"不产生 strong" | quarantine API 一键隔离 |
| 桥接脚本静默丢事件 | 每事件处理结果计数（imported/skipped/errors），非零 errors 退出码非 0 | 重放 jsonl |
| 契约抖动拖垮双仓库 | 契约改动需双仓库同 PR 评审；版本号进信封 `schema_version` | 旧版本事件保留解析器一个周期 |
| 过早合仓 | Phase 5 触发条件制 | 双仓库期间任一阶段可独立 revert |
| 历史回填一次性灌入大量历史信号 | 信号 payload 必带 `replay=true`，统计/面板默认过滤（4.1）；dedupeKey 防重复导入 | 按 `payload.replay` 批量识别清理；知识条目按 `source_pr_id` 定位 |
| importer 代 resolve 悬挂闸误判 | 仅限同 pr_id、actor 标注来源、event_log 全留痕（2.4） | 经 `POST /api/human-gates/:id/revoke` 撤销（端点已核实存在），按审计定位误判范围 |
| 停牌导致窗口漂移或观察值缺失 | `roll_forward_days` 超阈打 `window_drift` 降权复核；pending 不导出（D4 ④ / 3.3） | drift 标记可批量复审；pending 无数据落账本，无需回滚 |

---

## 附录 A · 事件契约 v1

**信封字段（除标注可选外全事件必带）**：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `schema_version` | string | 固定 `"1"`，breaking change 必须递增 |
| `event_id` | string | 全局唯一、确定性：`evt_{run_id}_{event_type}_{业务主键}`；**导入侧 dedupeKey** |
| `event_type` | enum | 见下表 |
| `domain` | string | 固定 `investment_research` |
| `run_id` | string | 所属 worldpay run |
| `occurred_at` | string | UTC ISO 8601 |
| `as_of_date` | string | 决策基准日（YYYY-MM-DD，交易日语义）；窗口推算与取数严格按 D4 三基准：自然日加法 + `first_row_on_or_after` 向后顺延取数 |
| `market` | string | 如 `US`；决定时区与价格数据所属交易所；**不**用于窗口长度计算（窗口为自然日，见 D4） |
| `future_data_allowed` | boolean | 恒为 `false` |
| `replay` | boolean | **可选**，默认 `false`；历史回填重放标记，语义见 4.1 与下方"两条知识事件的边界"。落 JSON Schema 时**不入 required**、写 `default: false`，否则非回填事件被迫携带 |
| `source_artifact_path` | string | worldpay data/ 相对路径 |
| `sha256` | string | 源 artifact 哈希 |
| `payload` | object | 事件类型专属字段 |

**事件类型与去向**：

| event_type | 业务主键 | Alaya 去向（Phase） |
| --- | --- | --- |
| `investment_run_started` | run_id | business signal（P1） |
| `research_signal_created` | RS-* | business signal（P1） |
| `research_prompt_created` | PR-* | business signal（P1）+ meaning gate（P2；`replay=true` 不建闸） |
| `research_prompt_filled` | PR-* | knowledge candidate, draft/active（P2） |
| `research_prompt_skipped` | PR-* | decision_log（P2） |
| `partner_recommendation_created` | rec id | agent_runs 索引（P3，可选） |
| `chairman_brief_created` | brief id | decision 索引（P3） |
| `decision_case_created` | case id | prediction（P3） |
| `risk_audit_created` | audit id | risk gate（P3） |
| `outcome_snapshot_created` | case id+窗口 | observation → error（P3；仅非 pending 快照，至多一条） |
| `knowledge_card_created` | card id | knowledge item（P4，限非 PR 派生卡片） |

**幂等与顺序规则**：重复 `event_id` 必须无副作用（信号层由 dedupeKey 保证；gate/prediction/observation 层由 importer 先查 + id_map 保证；知识层由 `source_pr_id` / card id 保证）；文件内按行序处理；前置实体缺失 → 记 errors 跳过，整批退出码非 0；禁止部分成功后静默吞错。前置实体按事件类型定义：filled/skipped 的前置 = 同 pr_id 的 created **信号**（非 gate，见 2.4）；`replay=true` 事件按 4.1 历史回填语义处理（created 不建闸）。

**两条知识事件的边界**：PR 派生知识（即来自回填）一律且只由 `research_prompt_filled` 驱动写入；`knowledge_card_created` 保留给**非 PR 派生**条目（人工卡片、合并/衍生卡片），在该类条目出现前是空载事件。两者落同一 `knowledge_items` 表，靠去重键互斥，杜绝双路径重复写入；P4 的历史回填同受去重键约束（见 4.1）。

**版本治理（schema_version）**：breaking 判定标准——删除/改名信封字段、改变既有 event_type 语义、改变任一幂等键、payload 新增必填项，命中任一即 breaking；仅新增可选 payload 字段为非 breaking。升级流程：双仓库各一个 PR、描述互相引用、同一评审人；**先合 Alaya**（importer 同时接受 N 与 N-1 主版本），**后合 worldpay**（exporter 切到 N）；一个发布周期后移除 N-1 解析器。

---

## 附录 B · 数据映射速查（修订版）

| worldpay 概念 | 路径（已核实） | Alaya 落点 | SoR | 阶段 |
| --- | --- | --- | --- | --- |
| Stock Pool | `data/stock_pool/` | 模块配置，不进通用 knowledge | worldpay | — |
| Research Signal | `data/research_signals/RS-*` | `external_business_signals` | worldpay 产生 / Alaya 索引 | P1 |
| Deep Research Prompt | `data/pull_requests/PR-*.yaml` | meaning gate（pending） | Alaya（闸门状态） | P2 |
| 回填 / 跳过 | `data/perplexity_results/PR-*_filled/_skipped.yaml` | gate resolve 的物化；filled → knowledge 候选，skipped → decision_log | Alaya 状态 / worldpay 文件 | P2 |
| F/W/G Recommendation | `data/recommendations/` | `agent_runs` 索引 | worldpay | P3 |
| Chairman Brief / Decision Case | `data/briefs/` 等 | `predictions`（claims 1/7/30/90） | worldpay 产生 artifact / Alaya 持 prediction 账本 | P3 |
| Red Team Audit | `data/red_team_audits/` | risk gate + action ledger | Alaya | P3 |
| Outcome Snapshot | `learning.py: refresh_outcome_snapshots` | `observations` → error 归因 | Alaya | P3 |
| Knowledge | `knowledge_store.py`（由 filled 重建） | `knowledge_items` 状态机 | **Alaya**；worldpay 为过滤读视图 | P4 |
| Partner Performance | `partner_performance.py` | 仅 Chairman/人可见上下文 | worldpay | 冻结规则 |

---

## 附录 C · 里程碑与工期

| 阶段 | 工期（单人兼职） | 关键交付 | 硬性退出标准 |
| --- | --- | --- | --- |
| P0 契约冻结 | 0.5–1 天 | 架构文档 + schema + Alaya 项目/模块 | schema 校验过、双仓 PR 合并 |
| P1 事件链路 | 2–4 天 | exporter + pusher | 幂等 V1–V4 全过 |
| P2 闸门回写 | 4–6 天 | importer.ts + sync_gates | filled/skipped 双路径 E2E 绿 |
| P3 预测账本 | 4–6 天 | prediction/observation 桥接 + id_map | 1 条真实归因链完整 |
| P4 知识 SoR | 1–2 周 | 知识同步 + quarantine 过滤钩子 | 隔离双侧生效、无自动 strong |
| P5 调度/UI | 后置 | 按触发条件进入 | 契约稳定 2 周 |
| **端到端验收** | P4 后 1 周观察期 | 第 9 节 Runbook | 检查清单全勾 |

合计：约 4–7 周到达终态（含 P4 后 1 周端到端观察期；不含 P5，不含返工缓冲）。其中改动 worldpay 引擎**行为**的唯一之处是 P4 的 `knowledge_store.py` 过滤钩子（1–2 周为无返工估算）；另有 P3 一处两行纯增量输出字段（`learning.py` 快照补 `price_start_date` / `price_end_date`，不改任何计算）。若 P4 吃紧，优先压缩 4.1 历史回填范围（只回填活跃 ticker），不要砍 4.4 的隔离过滤钩子。每阶段独立可回滚，任何一阶段失败不污染已交付能力。
