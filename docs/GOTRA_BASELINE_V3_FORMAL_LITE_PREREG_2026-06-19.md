# GOTRA Baseline v3 / Formal-Lite Preregistration & Design Spec (2026-06-19)

> 本文件是 Baseline v3 的**预注册（preregistration）+ 设计规范 + 可执行 goal**。
> 它在「看到任何 v3 结果之前」冻结：实验臂定义、输入层、公平性约束、指标、统计检验、接受边界、反作弊规则。
> 最后一节是 Codex 可直接执行的 goal，引用仓库真实存在的脚本、CLI、模块。
>
> 上游证据链：
> `docs/GOTRA_BASELINE_V2_THREE_ARM_PREREG_2026-06-18.md` →
> `docs/GOTRA_BASELINE_V2_EVIDENCE_FREEZE_2026-06-19.md` →
> `docs/GOTRA_BASELINE_V2_NEXT_LAYER_DESIGN_2026-06-19.md` → 本文件。
>
> 本文件不改变 v2 已冻结的任何定义或结果。它定义一个**新的、独立预注册**的实验层。

---

## 0. 为什么需要 v3（动机与上游结论）

### 0.1 v2 给了我们什么

v2 三臂 pilot（`PROVIDER_PILOT_PASS`, n=60 paired points, Kimi-K2.6）的冻结结论是**负/中性信号**：

```text
direction_hit_rate:  direct 0.383 > full 0.300 > ksana 0.267
MSE:                 direct 193.28 < ksana 224.88 < full 225.48
Policy A cum return:  direct 17.49 > ksana 7.57 > full 6.58
```

`direct_llm` 在每个指标上都不劣于、甚至优于更复杂的臂。

### 0.2 v2 为什么不能下任何系统性结论（v3 必须解决的根因）

逐条对应 v2 代码审查（见 PR #8 review）发现的结构性限制：

| 根因 | v2 的事实 | 对结论的影响 | v3 的应对 |
| --- | --- | --- | --- |
| **R1 输入太弱** | 仅 price_features（21/63/126d 收益 + drawdown）+ 32 行 adj_close | price-only 任务下裸 LLM 已足够，复杂 workflow 只增约束不增信息 | §3 双输入层：`price_only` vs `richer_research` |
| **R2 ksana 是 formatting 不是 research** | `build_prompt_payload` 中 F/W/G/Chairman 字面是「Use only included price-derived evidence」，即对同一 packet 的角色化改写 | 测的是「ksana 作为格式化」而非「ksana 作为研究」，注定无信息增益 | §2 加诊断臂 `ksana_formatting_only`，把两件事分开 |
| **R3 alaya feedback 不成熟** | 6 个 6 月间隔日期；最早日期 0 feedback；`feedback_used_count` 普遍极低 | 「没有 feedback 的 full_gotra」被当成了 alaya treatment | §4 warm-up 期 + feedback-eligible 子集分层评估 |
| **R4 样本太小、无统计** | n=60，无显著性检验、无置信区间 | 0.383 vs 0.300 在 n=60 下统计上不可区分 | §6 规模放大 + §7 paired bootstrap + HAC |
| **R5 prompt burden 不对等** | 复杂臂承担更多角色/格式约束 | 复杂臂指标可能被系统性拉偏 | §5 prompt 公平性约束（reasoning 长度/角色复杂度对齐） |
| **R6 单 provider** | 仅 Kimi-K2.6 | provider-robustness 未知 | §8 repeat-run + 可选 secondary provider sanity check |
| **R7 指标错配产品价值** | 仅 MSE/MAE/hit/PnL | 没覆盖 gotra「可审计内容平台」的核心价值 | §9 分离的 product-metric 轨道 |

### 0.3 v3 的目标（明确写下，防止目标漂移）

> **v3 的目标不是把实验调到 `full_gotra` 赢。**
> v3 的目标是回答四个可证伪的问题：
> 1. richer input 是否是 gotra 优势的必要条件？
> 2. ksana 的价值来自「研究」还是仅「格式化」？
> 3. 成熟的 alaya feedback 在 feedback-eligible 日期上是否有增益？
> 4. full_gotra 是否能在不显著恶化预测指标的前提下，改善可审计性/内容产品指标？

如果答案是「都没有」，那是一个**合法的、可发表的内部研究负结论**，而不是失败。

---

## 1. 范围与边界（Purpose & Boundary）

本预注册定义 **Baseline v3 = Formal-Lite internal research layer**。

```text
是：       预注册的、放大规模的、多臂的内部研究实验
是：       带统计检验（paired bootstrap + HAC）的内部结论层
不是：     OOS 接受层（需单独预注册）
不是：     Stage9 / paper trading / live ledger
不是：     科学/公开声明
不是：     交易建议
```

**Formal-Lite 的定义**：规模与统计严谨度高于 pilot，但仍是内部研究；其正向结论只能支持「internal research claim」，**不能**支持 OOS / 科学 / 公开 / 交易声明。这与 v2 prereg §5 的分层表（V2 formal-lite → V3 formal/OOS）一致；本文件即 v2 prereg 表中的「V2 formal-lite」层的完整化，并向「V3 formal/OOS」预留接口。

> 命名说明：v2 prereg §5 把「formal-lite」记为分层表里的 V2 行、把「formal/OOS」记为 V3 行。本文件用 **Baseline v3** 指代「比 v2 pilot 更高一层的 formal-lite 实验」，与文件名 `BASELINE_V3` 一致。OOS/forward-live 仍是更高一层，需另行预注册。

---

## 2. 实验臂定义（Arms）— 核心设计：四臂

v2 是三臂。**v3 改为四臂**，新增一个诊断臂，这是 v3 最重要的设计决策。

| Arm | 小学生说法 | 技术定义 | 回答的问题 |
| --- | --- | --- | --- |
| `direct_llm` | 裸学生直接答题 | 同 provider/model、同 packet、同 schema；无 ksana、无 alaya、无 feedback | 裸 LLM 的水平 |
| `ksana_formatting_only` | 老师把同一份资料换个格式念一遍 | 同 raw packet + F/W/G/Chairman **角色结构**，但**不接入任何独立证据源** | ksana 的「格式化」本身有无价值（≈ v2 的 `ksana_only`） |
| `ksana_real_research` | 老师真的去查了多源资料 | 同 raw packet + **真实多源、时间受限的研究 artifact**（新闻/财报/基本面/事件/治理，全部 `availability_date <= decision_date`） | ksana 的「研究」有无价值 |
| `full_gotra` | 老师查了资料 + 有错题本 | `ksana_real_research` + 成熟 alaya 知识状态/历史错误归因/置信度更新，且 strong knowledge 需人类闸门 | 完整 gotra 的增益 |

### 2.1 为什么必须加 `ksana_formatting_only`（设计理由）

v2 的致命混淆是：`ksana_only` 实际是 formatting，但它被解读为「ksana 研究流程」。结果 ksana 输了，但我们**无法区分**是：

- (a) 「ksana 这个研究理念」不行，还是
- (b) 「当前把 ksana 实现成纯格式化」不行。

加诊断臂后，v3 可以做这个关键三角对照：

```text
ksana_formatting_only vs direct_llm
  → 隔离「格式化/角色结构」本身的净效应（预期≈0 或为负，作为 sanity check）

ksana_real_research vs ksana_formatting_only
  → 隔离「真实研究信息」的净增益（这才是 ksana 理念的真实检验）

ksana_real_research vs direct_llm
  → ksana 完整研究流程 vs 裸 LLM

full_gotra vs ksana_real_research
  → 在「真实研究」之上，alaya 错题本的额外增益
```

**权衡（trade-off）**：四臂使每个 paired point 的 provider 调用从 3 次增加到 4 次，成本 +33%。这是可接受的，因为没有诊断臂就无法解释 v2 的负结论——省这 33% 会让整个 v3 失去因果可解释性。

### 2.2 隔离的强制实现要求（继承 v2 的结构性隔离）

v3 必须保持 v2 已验证的**双层隔离**（PR #8 审查确认 v2 此处实现正确，v3 必须不退化）：

- **输入侧**：payload 构建时，臂特有的 key 物理上不存在于不该有的臂（v2 `build_prompt_payload` 模式）。
  - `direct_llm`：无 `ksana_*`、无 `alaya_*`；当 `input_layer=richer_research_packet` 时可见同一组原始 time-bounded `research_artifacts`，但不可见 ksana workflow 产物或 alaya feedback。
  - `ksana_formatting_only`：有角色结构 key，但其内容**不得**包含任何 price packet 之外的证据；无 `alaya_*`。
  - `ksana_real_research`：有角色结构 key + `research_artifacts`（多源）；无 `alaya_*`。
  - `full_gotra`：以上全部 + `alaya_feedback_history` + `alaya_knowledge_state`。
- **输出侧**：解析时强制 ref 隔离（v2 `parse_provider_decision` 模式）：
  - `direct_llm`：`ksana_refs=[]`、`alaya_memory_refs=[]`，否则不计 scored。
  - `ksana_formatting_only` / `ksana_real_research`：`alaya_memory_refs=[]`，否则不计 scored。
  - `full_gotra`：`alaya_memory_refs` 仅允许引用本次 payload 中 `alaya_feedback_history[].feedback_ref` 的稳定 id；无可用 feedback 时必须为空。

新增的「证据源隔离审计」（v3 新增，针对 R2）：

```text
ksana_formatting_only 的 research_artifacts 必须为空或仅含 price-derived 派生项；
任何非 price 来源出现在 formatting_only 臂 → research_source_leak 违规 → 不计 scored。
```

---

## 3. 输入层设计（Input Packets）— 双层

针对 R1，v3 定义**两个并列的输入层**，每个臂在两层上各跑一次（input_layer 作为实验因子）。

| input_layer | 内容 | 目的 |
| --- | --- | --- |
| `price_only_packet` | 与 v2 等价：price_features + 近 N 行 adj_close | 复现 v2 条件，作为对照基线 |
| `richer_research_packet` | price_only + 时间受限的多源材料（见 §3.1） | 检验 gotra 优势是否需要 richer input |

这样 v3 可以回答 R1：

```text
若 gotra 仅在 richer_research_packet 下显现优势，而在 price_only 下不显现
  → 结论：gotra 的价值依赖 richer input，v2 的负结论是「输入太弱」所致，而非系统无效。
```

### 3.1 richer_research_packet 的内容与硬约束

内容（每项都必须带 source + timestamp）：

```text
news_items            新闻/事件，带发布时间戳
earnings_context      财报要点（已公布的）
fundamentals_snapshot 基本面快照（截至 decision_date 可得）
valuation_context     估值上下文
sector_context        行业/同业变化
governance_risk        监管/治理/公司治理风险信号
catalyst_calendar      已知的、decision_date 前已公开的事件日历
```

**时间受限硬约束（time-bounded，针对未来数据泄漏）**：

```text
对 richer_research_packet 中每一条材料：availability_date <= decision_date 必须成立。
任何一条 availability_date > decision_date → future_data_violation → 整个 step 作废（沿用 v2 future_data_violations 机制）。
材料中不得包含 actual_change_pct、未来价格、或任何 decision_date 之后才可知的信息。
catalyst_calendar 只能包含「在 decision_date 之前已经公开了日程」的事件，不能因为事件本身发生在未来就泄漏其结果。
```

**数据来源诚实性约束（针对 R2 的延伸）**：

```text
richer_research_packet 的材料必须标注真实来源（real / synthetic / unverified）。
synthetic 或 unverified 材料必须在 step 与 summary 中显式计数（synthetic_evidence_count）。
若某臂的优势主要来自 synthetic 材料，结论中必须显式披露，不得当作真实信息增益。
```

> 设计理由：v2 的 ksana 之所以是 formatting，本质是没有独立证据源。如果 v3 用 synthetic 材料假装 richer，会重蹈覆辙。因此 v3 把「材料真实性」作为一等公民显式追踪，宁可承认材料是 synthetic 并据此降级结论，也不伪装信息增益。

---

## 4. Alaya treatment 设计 — warm-up + 分层评估

针对 R3：v2 把「没有 feedback 的 full_gotra」当成了 alaya treatment，这是无效的。

### 4.1 Warm-up 期

```text
时间网格分两段：
  warm_up 段:  最早的若干 decision_date，仅用于产生 alaya feedback，不计入最终 scoring。
  scored 段:   warm_up 之后的 decision_date，计入最终统计。
```

设计理由：alaya 的价值是「错题本复利」，需要先积累已成熟（matured）的历史反馈。warm-up 段让 scored 段的 full_gotra 真正拿到非空、成熟的 feedback。warm-up 段的 step 仍写盘（用于审计与产生 feedback），但在统计层被排除。

### 4.2 Feedback 成熟性与可用性（继承 v2 的 matured_feedback 机制）

```text
feedback 仅当 outcome_availability_date <= decision_date 时才对该 decision_date 可用（v2 matured_feedback 模式）。
feedback 快照按 wave（每个 decision_date）冻结；wave 内不得看到本 wave 任何点的 outcome（v2 已验证无泄漏，v3 不得退化）。
feedback 历史必须按 (ticker, input_layer) 隔离，price_only_packet 不得读取 richer_research_packet 产生的 feedback，反之亦然。
每个 full_gotra alaya_memory_ref 必须匹配本次 payload 可见的 feedback_ref，且该 feedback 的 availability_date <= decision_date。
quarantined / stale / conflict 知识必须被过滤排除。
strong knowledge 不得自动越权晋级（strong_knowledge_auto_approval_allowed=False，需人类闸门）。
```

### 4.3 分层评估（防止把「无 feedback」当成「alaya 无效」）

full_gotra 必须在三个子集上分别报告，且**主结论只看 feedback-eligible 子集**：

```text
all_scored_points              所有 scored 段的点
feedback_available_subset      该点 feedback_used_count > 0
high_quality_feedback_subset   该点 feedback 满足密度/质量阈值（见下）
```

追踪指标（每个点）：

```text
feedback_used_count            实际用到的成熟 feedback 条数
feedback_age_days              最老/最新 feedback 距 decision_date 的天数
quarantine_excluded_count      被隔离排除的知识条数
full_gotra_scored_points       full_gotra 在 scored 段的分母
full_gotra_feedback_available_scored_points  feedback_used_count > 0 的 full_gotra scored 点
C4_feedback_eligible_paired_points  C4/H2 实际进入 feedback-eligible 配对的点数
```

high_quality_feedback 阈值（预先冻结，防止事后调参）：

```text
feedback_used_count >= 3
且 至少 1 条 feedback_age_days >= 30（即真正成熟过一个 horizon）
```

> 反作弊：阈值在此处冻结。不得在看到结果后调整阈值以让 full_gotra 在某子集上「赢」。

---

## 5. Prompt 公平性约束 — 对齐 burden

针对 R5：v2 的复杂臂承担更多格式/角色约束，可能系统性拉偏。

```text
所有臂共享同一 output schema 与同一 DECISION_JSON_ALLOWED_KEYS（沿用 v2）。
所有臂的 system prompt「输出格式约束」部分必须逐字相同。
臂之间唯一允许的 prompt 差异是 ARM_CONTRACT 的 task 段与 allowed/forbidden context（即「能看什么信息」），
  不允许在复杂臂里附加额外的「写更长 reasoning」「列更多 role」之类的产出负担。
reasoning 长度不设硬上限，但必须在 step 里记录 reasoning_chars，并在 summary 中按臂报告 reasoning_chars 分布，
  以便事后诊断「复杂臂是否因为被迫写更长 reasoning 而偏离指标」。
```

设计理由：公平性的本质是「臂之间只在『可用信息』上不同，不在『被要求做多少额外动作』上不同」。把信息差与产出负担差解耦，才能把指标差异归因到信息，而非格式。

---

## 6. Universe & Time Grid（规模）

针对 R4，放大到 formal-lite 规模（与 v2 prereg §5 的「V2 formal-lite」行一致）：

```text
tickers:        30-50（覆盖美股 + 港股，沿用 v2 的市场构成并扩充）
dates:          12-24 个月度 decision_date（每月首个交易日）
  其中 warm_up: 最早 3-6 个月度日期（不计入 scoring）
  其中 scored:  其余 9-18 个月度日期
horizon_days:   30
arms:           4（direct_llm, ksana_formatting_only, ksana_real_research, full_gotra）
input_layers:   2（price_only_packet, richer_research_packet）
```

paired point 预算（粗算）：

```text
provider 调用数 = tickers × dates × arms × input_layers
最小：  30 × 12 × 4 × 2 = 2,880 调用
最大：  50 × 24 × 4 × 2 = 38,400 调用
scored paired points（每个 (ticker, scored_date, input_layer) 是一个四臂配对）：
  最小约 30 × 9 = 270 个配对组（× 2 input_layer = 540）
  上限约 50 × 18 = 900 个配对组（× 2 input_layer = 1,800）
```

> 成本权衡：四臂 + 双输入层使调用量相对 v2（180）放大 16-200 倍。
> 缓解：v3 必须复用 v2 已实现的 cache（cache_key 含 input_layer，见 §10）、并发 ramp、circuit breaker。
> 若预算不足，**降规模而非降臂数/输入层数**——臂与输入层是因果识别的核心，不能砍。
> 允许的最小可发布配置：30 tickers × 12 dates（含 3 warm-up）× 4 arms × 2 layers。低于此则状态为 `DATA_INSUFFICIENT`。

---

## 7. 指标与统计设计（Metrics & Statistics）

### 7.1 预测指标（primary，沿用 v2 口径以保证可比）

```text
direction_hit_rate
expected_change_pct MSE
expected_change_pct MAE
Policy A return（long-only；v3 明确标注为「无成本、无做空」的对照口径，不作收益声明）
calibration（新增：confidence 与实际命中的可靠性曲线 / Brier 分量）
abstain_quality（新增：abstain 时实际波动是否更大，即 abstain 是否「该弃权」）
source_kind_counts（新增：real / synthetic / unverified / price_derived / unknown 的证据源计数）
```

**direction_hit 规则（冻结）**：

```text
provider direction 允许 long / avoid / neutral / watch / short。
actual_change_pct >= +2% → actual_direction=long。
actual_change_pct <= -2% → actual_direction=avoid；此时 avoid 与 short 都计为 downside hit。
其他区间 → actual_direction=neutral。
```

### 7.2 内容产品指标（secondary，单独轨道，针对 R7）

```text
evidence_coverage          决策引用的证据条数 / 可用证据条数
reasoning_auditability      reasoning 是否可追溯到具体 evidence_refs（结构化可检验）
error_attribution_quality   full_gotra 对历史错误的归因是否与实际误差方向一致
ledger_completeness         step/ledger 必填字段完整率
claim_specificity           direction + expected_change_pct + confidence 的具体度
risk_disclosure_quality     risk_factors 是否非空且与已知风险相关
explanation_consistency      同 ticker 相邻 decision_date 的解释是否自洽
```

**边界（硬性，写入结论模板）**：

```text
product 指标可支持「可审计内容平台」claim。
product 指标不可单独支持 trading / OOS / 科学 claim。
若 full_gotra 在 product 指标上赢、但在预测指标上显著恶化超过容差，结论必须如实记录为「内容价值有、预测无优势甚至变差」。
```

### 7.3 统计检验（v2 缺失，v3 必须实现）

主比较（均为 paired，按 (ticker, decision_date, input_layer) 配对）：

```text
C1  ksana_formatting_only − direct_llm          （格式化净效应，sanity）
C2  ksana_real_research − ksana_formatting_only  （真实研究净增益）
C3  ksana_real_research − direct_llm
C4  full_gotra − ksana_real_research             （alaya 净增益，仅 feedback-eligible 子集）
C5  full_gotra − direct_llm
```

每个比较，对 MSE 损失差（loss = MSE）：

```text
方法 1（点估计 + 时序稳健）：
  hac_mean_test(loss_diffs)   ← 在每个 ticker 或 ticker/input_layer cluster 内运行
  （HAC 不得把不同 ticker 或不同 input_layer 串成一条连续时间序列；cluster 内返回 mean_loss_diff / hac_lag / z_score / p_value）

方法 2（分布稳健）：
  paired bootstrap 置信区间（v3 新增；按 ticker 聚类重采样，防止把同 ticker 的多日期当独立样本）
  报告 95% CI 与 bootstrap p 值

聚类原则：
  bootstrap 以 ticker 为聚类单元重采样（cluster bootstrap），因为同 ticker 跨日期强相关。
  cluster bootstrap 少于 2 个 cluster 时必须返回 statistical_test_completed=false / insufficient_reason=not_enough_clusters，不得显著通过。
  `passed` 若保留，仅是 `right_arm_better_significant` 的兼容别名；报告层必须使用显式字段。
  HAC 以 (ticker 内按 decision_date 排序) 或 (ticker,input_layer 内按 decision_date 排序) 的损失差序列计算长程方差。
```

> 复用说明：仓库现有 `statistics.py::paired_loss_differences` / `drift_window_results` 是为旧两臂 `baseline`/`alaya` 硬编码的。**v3 不得直接复用它们的 arm 名**；需要：
> - 复用通用的 `hac_mean_test(values)`（输入是一串 float，与 arm 名无关，可直接用）；
> - 新增一个 v3 专用的 `paired_loss_differences_v3(steps, left, right, *, input_layer=None)`，泛化 arm 名与 input_layer 过滤；
> - 新增 cluster bootstrap 函数；
> 这些新增必须有 focused tests（见 §11）。

### 7.4 预注册假设（H1/H2/H3，看结果前冻结）

```text
H1 (ksana 研究价值):
   C3 在 richer_research_packet 上：ksana_real_research 的 MSE 显著低于 direct_llm
   （hac p<0.05 且 cluster-bootstrap 95% CI 不含 0，方向为 ksana 更优）。
   预期：仅在 richer 层可能成立；price_only 层预期不成立。

H2 (alaya 反馈价值):
   C4 在 feedback_available_subset（或 high_quality_feedback_subset）上：
   full_gotra 的 MSE 显著低于 ksana_real_research。
   仅在 feedback-eligible 子集上检验；不得在无成熟 feedback 的点上检验 H2。

H3 (内容产品价值):
   full_gotra 在 §7.2 product 指标上优于 direct_llm，
   且预测指标恶化不超过预先冻结的容差 τ。
   τ 定义（冻结）：full_gotra 的 MSE 相对 ksana_real_research 上升不超过 5%（相对值），
   且 direction_hit_rate 下降不超过 2 个百分点。

诊断（非假设，但必须报告）:
   C1 (formatting 净效应) 与 C2 (真实研究净增益) 必须如实报告，
   用于解释 v2 负结论究竟来自「ksana 理念」还是「formatting 实现」。
```

---

## 8. Provider variance（针对 R6）

```text
主 provider/model：预先声明并冻结（建议沿用一个已稳定的，如 Kimi-K2.6 或 GLM-5.2，按当时可用性决定并写入 manifest）。
repeat-run variance：对同 provider 用同 prompt 重复运行 R 次（建议 R=2-3），评估 LLM 随机性对结论的影响。
  temperature 必须固定（如 0.0，沿用 v2）；repeat 仍可能因 provider 端非确定性产生差异，正是要量化的对象。
secondary provider sanity check（可选，预算允许时）：换一个 provider 重跑 scored 段的一个子集，仅作 robustness。
```

**硬性原则（反作弊）**：

```text
provider variance 是 robustness check，不是调参工具。
不得通过换 provider / 换 model / 换 max_tokens 来「凑」出 full_gotra 获胜。
provider / model / base_url / max_tokens 一旦在 manifest 冻结，scored 段内不得更改。
```

---

## 9. 反作弊规则（Anti-Cheating，看结果前冻结）

继承 v2 prereg §8，并针对 v3 新增：

```text
[继承自 v2]
- 不得根据结果删除 ticker/date 行。
- 不得调阈值让 full_gotra 赢。
- 不得把 confidence 当成投票一致性。
- 不得用 actual_change_pct 生成信号。
- 不得在看到结果后更改主指标。

[v3 新增]
- 不得在看到结果后调整 warm-up 长度、high_quality_feedback 阈值、或容差 τ。
- 不得在看到结果后增删 input_layer 或 arm。
- 不得把 synthetic 证据当作真实信息增益（必须 synthetic_evidence_count 显式披露）。
- 不得通过换 provider/model/max_tokens 追胜（§8）。
- 不得隐藏任何一个臂（尤其不得隐藏 direct_llm 基线与 ksana_formatting_only 诊断臂）。
- 不得在无成熟 feedback 的点上检验 H2 并据此声称「alaya 失败」。
- 不得把 product 指标的优势提升为 trading/OOS/科学声明。
- 预注册哈希：本文件合并后，其 git commit SHA 即为预注册锚点；H1/H2/H3 与所有阈值以该 commit 为准。
```

---

## 10. 工程实现要求（Engineering Requirements）

### 10.1 复用 v2 已验证的机制（不得退化）

```text
- 双层臂隔离（输入侧 payload key + 输出侧 ref 校验）。
- future_data_violations 审计（decision_inputs <= decision_date；outcome_inputs <= outcome_as_of）。
- 保守 normalization（仅 trim / fence 剥离 / 首个平衡 JSON 提取；不补字段、不用 LLM 修 JSON）。
- input_echo 双重检测（payload key + raw 前缀）。
- per-wave matured_feedback 快照（feedback 仅在整 wave 完成后 append）。
- circuit breaker / 并发 ramp / 超时重试。
- 证据分层（local checks / provider-runtime health / pilot evidence / formal acceptance / science claim）。
```

### 10.2 v3 新增的工程项

```text
- input_layer 作为一等因子：CLI 参数、payload、cache_key、step、summary、manifest 全链路携带。
- cache_key 必须新增 input_layer 维度：
    baseline_v3:<definition_version>:<provider>:<model>:<base_url>:max_tokens=<n>:<arm>:<input_layer>:<prompt_hash>
  防止两个 input_layer 的结果串用。
- 四臂支持：ARMS 扩展为 (direct_llm, ksana_formatting_only, ksana_real_research, full_gotra)。
- research_artifacts 字段（richer 层）：带 source / availability_date / source_kind(real|synthetic|unverified)。
- research_source_leak 审计（formatting_only 臂不得含非 price 证据）。
- warm_up 标记：step 带 scoring_segment(warm_up|scored)；统计层排除 warm_up。
- reasoning_chars 记录与按臂分布报告。
- product 指标计算（§7.2）。
- 统计层：hac_mean_test 复用 + paired_loss_differences_v3 + cluster_bootstrap_ci 新增。
- provider decision identity 校验：返回 JSON 的 arm/ticker/decision_date/horizon_days 必须匹配 task point，
  否则 schema_contract_error，不计 scored，不写入成功 cache。
- strict decision JSON key 校验：DECISION_JSON_ALLOWED_KEYS 之外的 top-level key 一律 schema_contract_error，
  不静默丢弃未知字段。
- provider_max_tokens 必须进入真实 provider request path；若某路径未调用真实 provider API，需显式记录
  provider_max_tokens_applied=false 与 reason。
- 新的 definition_version 字符串：baseline-v3-four-arm-2026-06-19（区别于 v2）。
- 新的 schema 名：gotra.baseline_v3.four_arm_decision.v1 / .step.v1 / .summary.v1。
```

### 10.3 Run artifacts

```text
允许的 run namespace: data/backtest/runs/baseline_v3_four_arm_*
每个 run 写: summary.json / manifest.json / ledger.jsonl /
  direct_llm/step_*.json / ksana_formatting_only/step_*.json /
  ksana_real_research/step_*.json / full_gotra/step_*.json
run artifacts 不是 git artifacts（与 v2 一致，PR 不得提交 runs/）。
```

---

## 11. 测试要求（Tests，沿用 v2 的 focused-test 纪律）

新脚本 `tests/test_baseline_v3_four_arm.py` 必须覆盖：

```text
- 四臂 payload 边界隔离（direct 无 ksana/alaya；formatting_only 有角色无独立证据无 alaya；
  real_research 有研究 artifact 无 alaya；full 有 alaya）。
- research_source_leak 审计：formatting_only 含非 price 证据 → 违规。
- 两个 input_layer 的 payload 差异正确，且 cache_key 含 input_layer 且两层不互相命中。
- future-data guard：richer_research_packet 任一材料 availability_date > decision_date → future_data_violation。
- warm_up 段 step 被写盘但被统计层排除。
- matured_feedback 在 v3 网格下仍无未来泄漏（继承 v2 测试并适配四臂）。
- 输出侧 ref 隔离（沿用 v2）。
- normalization 边界（沿用 v2：不补字段、不修 JSON）。
- input_echo 检测（沿用 v2）。
- 统计：hac_mean_test 在已知输入上的数值正确；paired_loss_differences_v3 按 arm/input_layer 正确配对；
  cluster_bootstrap_ci 在固定 seed 下可复现。
- product 指标计算在构造样本上的正确性。
- summary counters / paired coverage / synthetic_evidence_count。
- provider_max_tokens / definition_version / schema 名出现在 manifest/summary/step/cache_key。
```

---

## 12. 接受边界与状态机（Acceptance）

```text
FORMAL_LITE_PASS
   规模达到最小可发布配置（§6）且 paired_coverage>=0.95 且 future-data violations=0 且 provider_error_rate<=0.05，
   且统计层完整运行（H1/H2/H3 检验均已计算，无论正负）。
   注意：PASS 指「实验有效完成、可下内部结论」，不预设结论方向。

FORMAL_LITE_INCONCLUSIVE
   实验有效完成，但 H1/H2/H3 的 CI 跨 0 / p>=0.05，无法下方向性结论。

FORMAL_LITE_NEGATIVE
   实验有效完成，且证据方向性地不支持 ksana/alaya 增益（CI 显著偏向 direct/简单臂）。

PROVIDER_BLOCKED
   canary 在并发 1 仍失败，或主 provider 不可用且未获授权 fallback。

DATA_INSUFFICIENT
   规模低于 §6 最小配置，或 feedback-eligible 子集太小（H2 不可检验）。
```

支持/不支持的声明（写入结论模板）：

```text
可支持: 「在 v3 formal-lite 内部研究条件下，<H1/H2/H3 的具体结论>」（internal research claim）。
可支持: full_gotra 的内容产品价值（若 H3 成立），明确标注为内容平台价值而非投资有效性。
不可支持: 任何 OOS / forward-live / 科学 / 公开 / 交易声明——这些需要单独预注册的更高层实验。
仍需后续: forward/live ledger 才能支持产品上线与公开 track record。
```

---

## 13. 与 v2 的差异速查（Changelog vs v2）

| 维度 | v2 | v3 |
| --- | --- | --- |
| 臂数 | 3 | **4**（加 `ksana_formatting_only` 诊断臂） |
| 输入层 | 1（price-only） | **2**（price_only + richer_research） |
| ksana 实质 | formatting | **区分 formatting vs real_research** |
| alaya 评估 | 全部点混评 | **warm-up + feedback-eligible 子集分层** |
| 规模 | 10×6, n=60 | **30-50 × 12-24（含 warm-up）** |
| 统计 | 无显著性 | **HAC + cluster bootstrap CI** |
| provider | 单次 Kimi | **repeat-run variance + 可选 secondary** |
| 指标 | 仅预测 | **预测 + 内容产品双轨道** |
| 公平性 | 未控 burden | **控 reasoning/role burden** |
| cache_key | 无 input_layer | **含 input_layer** |
| definition_version | baseline-v2-three-arm-2026-06-18 | baseline-v3-four-arm-2026-06-19 |

---

## 14. CODEX 可执行 GOAL（实现层）

> 下面是给 Codex 的可直接执行 goal。它**不**直接跑 provider（provider run 需单独授权与 .env），而是先完成**实现 + mock 验证 + 测试**这一可在本地确定性完成的层，并把 provider run 留作显式 gate。这与 v2 的「先 mock_pass / 再 canary / 再 pilot」纪律一致。

```text
GOAL: 实现 Baseline v3 four-arm formal-lite harness（实现 + mock + tests 层），不进 provider run。

REPO: 本地 /Users/peachy/Documents/gotra
BRANCH: 从当前分支新建 codex/baseline-v3-four-arm-impl-20260619
PREREG: 本文件 docs/GOTRA_BASELINE_V3_FORMAL_LITE_PREREG_2026-06-19.md（合并后的 commit SHA 为预注册锚点）

只读参照（不得修改语义）:
  scripts/baseline_v2_three_arm_pilot.py
  tests/test_baseline_v2_three_arm_pilot.py
  gotra/backtest/statistics.py        # 复用 hac_mean_test
  gotra/backtest/audit.py             # 复用 audit_run / future-data 思路
  gotra/backtest/price_cache.py       # 复用 read_price_cache
  gotra/backtest/protocol.py          # 复用 parse_date / add_months / ticker_slug

实现清单（全部带 focused tests，见 prereg §11）:
  1. 新脚本 scripts/baseline_v3_four_arm.py，以 v2 脚本为骨架，新增:
     - ARMS = (direct_llm, ksana_formatting_only, ksana_real_research, full_gotra)
     - DEFINITION_VERSION = "baseline-v3-four-arm-2026-06-19"
     - schema 名 gotra.baseline_v3.four_arm_decision.v1 / .step.v1 / .summary.v1
     - input_layer 因子 (price_only_packet | richer_research_packet)，全链路携带
     - cache_key 新增 input_layer 维度（见 prereg §10.2）
     - research_artifacts 字段 + source_kind(real|synthetic|unverified) + availability_date
     - research_source_leak 审计（formatting_only 不得含非 price 证据）
     - warm_up/scored 段标记 scoring_segment，统计层排除 warm_up
     - reasoning_chars 记录与按臂分布
     - 双层臂隔离（输入侧 payload key + 输出侧 ref 校验，沿用 v2 模式，不得退化）
     - future_data_violations 扩展到 richer_research_packet 的每条材料
     - 保守 normalization / input_echo 双检测 / per-wave matured_feedback（沿用 v2）
  2. gotra/backtest/statistics.py 新增（不改旧两臂函数）:
     - paired_loss_differences_v3(steps, left, right, *, input_layer=None, segment="scored", cluster_by_input_layer=False)
     - cluster_bootstrap_ci(loss_diffs_by_ticker, *, iters=10000, seed, alpha=0.05, left_arm="", right_arm="")
     - 复用现有 hac_mean_test(values)
  3. product 指标计算函数（prereg §7.2）写在 v3 脚本内或新模块 gotra/backtest/product_metrics_v3.py
  4. CLI 参数新增: --input-layer (both|price_only|richer)，--warm-up-dates N，--repeat-run-index K
  5. 新测试 tests/test_baseline_v3_four_arm.py（覆盖 prereg §11 全部条目）

验证 gate（必须全绿才算实现层完成）:
  uv run python -m py_compile scripts/baseline_v3_four_arm.py
  uv run ruff check --no-cache scripts/baseline_v3_four_arm.py tests/test_baseline_v3_four_arm.py gotra/backtest/statistics.py
  uv run pytest -q tests/test_baseline_v3_four_arm.py
  uv run python scripts/baseline_v3_four_arm.py --mode mock --input-layer both \
    --tickers AAPL,MSFT,NVDA --dates 2024-01-02,2024-02-01,2024-03-01,2024-04-01 \
    --warm-up-dates 1 --run-id baseline_v3_four_arm_mock_impl_check
    → 期望 status=MOCK_PASS，paired_coverage 合理，future_data_violations=0，research_source_leak=0

边界（硬性，沿用 prereg §9 反作弊）:
  - 不进 provider run（provider/canary/pilot 留作单独授权的后续 goal）。
  - 不提交 data/backtest/runs/* 到 git。
  - 不修改 v2 脚本/测试/文档的语义；v2 结论与定义保持冻结。
  - 不读取或打印任何 .env* secret。
  - 不实现任何「看结果调参」的便捷开关。
  - PR 标题: "Implement Baseline v3 four-arm formal-lite harness (impl + mock + tests)"
  - PR 描述必须声明: 这是实现层冻结，非 formal-lite pass，非 provider evidence，非科学/OOS/交易声明。

完成后输出:
  - 实现差异摘要、测试通过数、mock 验证 summary 关键字段
  - 一份 docs/GOTRA_BASELINE_V3_IMPL_RESULT_<UTC>.md，记录实现层证据边界（沿用 v2 result 文档体例）
```

### 14.1 后续（单独授权的 provider goal，本 goal 不执行）

```text
provider run 是独立 goal，需用户单独授权 + .env 就绪，遵循 v2 的 canary→ramp→pilot 纪律:
  1. mock_pass（已在实现层完成）
  2. provider-canary（1-3 tickers，并发=1）→ 全绿才进下一步
  3. 并发 ramp 探针（2→4→...）每步零 429/零 provider error/零 schema/零 future-data
  4. provider formal-lite run（§6 规模，含 warm-up），写 runs/，跑统计层
  5. 写 docs/GOTRA_BASELINE_V3_RESULT_<UTC>.md：报告 C1-C5、H1/H2/H3、状态机判定
provider run 的状态由 §12 状态机判定；任何正向结论仅为 internal research claim。
```

---

## 15. 一句话总结

> v3 不是为了让 gotra 赢，而是为了让「gotra 到底在什么条件下有价值」这个问题**可证伪、可复现、可审计**。
> 四臂分离格式化与研究，双输入层分离信息与噪声，warm-up + 子集分离成熟与稀疏的 alaya，
> HAC + cluster bootstrap 给出统计可信度，反作弊规则锁死事后调参——
> 无论结论正负，它都是一个诚实的内部研究结果。
