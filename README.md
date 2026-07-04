# GOTRA

GOTRA 是一个研究认知系统，不是荐股系统、交易信号系统或收益证明系统。

当前主线是 **GOTRA v4.0 Ksana cognition flywheel**：先生成研究任务书和公开证据包，再由 K 深度研究底稿、F/W/G 独立视角、主席综合、红队反证、研究质量闸门、知识闸门、内部 Alaya 回读和读者边界闸门共同形成可审计的公开研究产物。

生产读者页面在配套仓库 [`gotra-public-ledger`](https://github.com/amanayayatu-tech/gotra-public-ledger) 提供，线上地址是 [gotra.me](https://gotra.me/)。

## 当前状态

最新已落档状态：

| 项目 | 当前值 |
| --- | --- |
| 后端仓库 | `/opt/gotra` |
| v4 后端代码基线 | `main@acd6cfa`，clean；README refresh 提交可能在此之上 |
| v4 结果 | `PASS_WITH_REVIEW_ITEMS_2H_V40_KSANA_COGNITION_FLYWHEEL` |
| 证据层级 | `2h pressure` |
| 压测时长 | `7232s` |
| 完整通过 loop | `13` |
| production artifact | `gotra.daily_reader_brief.v4` / `gotra.full_analyst.symbol.v4` |
| execution model | `deep_research_dossier_then_parallel_perspectives` |
| methodology | `ksana_cognition_flywheel_v4` |
| public safety | `ok` |
| Alaya readback | `verified` |
| 前端产品化 | `PASS_V40_FRONTEND_PRODUCTIZATION_SMOKE`，`gotra-public-ledger` PR `#56`，`main@35ba6fa` |

这说明 v4 后端链路和 v4 前端读者路径已经通过短压测与 production smoke。它**不等于** `10h/formal acceptance`，也不是科学公开证明、业绩证明、投资建议或交易信号。

## GOTRA 是什么

GOTRA 用来：

- 把研究对象、研究任务、证据、缺口、分歧、反证、质量闸门和知识沉淀过程记录下来；
- 在公开安全边界内生成可阅读、可复核、可审计的研究产物；
- 让 `data_gap`、`needs_review`、红队质疑和未解决问题留在明面上，而不是包装成确定答案；
- 将研究过程和工程证据分层保存，避免把 smoke、压力测试、正式验收、科学结论或投资结论混在一起；
- 通过 GOTRA repo 内部的 Alaya cognition flywheel / memory / readback state 做知识回读和反馈，不接入外部 Alaya 服务。

GOTRA 不是：

- 投资建议；
- 交易信号；
- 买入、卖出、持有、加仓、减仓指令；
- 目标价或仓位建议；
- 收益承诺或业绩证明；
- science/public proof；
- 自动交易或券商下单系统；
- 外部 Alaya 项目的客户端。

## v4 研究链路

v4 的核心链路是：

```text
stock selection
  -> Research Task Planner
  -> Evidence Packet Builder
  -> K Deep Research Dossier
  -> F/W/G Independent Perspective Agents in parallel
  -> Chairman Synthesis
  -> Red Team Audit / Counter-Evidence
  -> Research Quality Gate
  -> Alaya / Knowledge Gate
  -> Alaya Write
  -> Readback Verification
  -> Reader Boundary Gate
  -> Public Artifact
  -> daily_reader_brief.v4
  -> gotra-public-ledger reader
```

中文解释：

- **Research Task Planner / 研究任务书**：说明为什么今天研究这只股票、今天必须回答什么、哪些证据是必需的、哪些缺口不能假装完整。
- **Evidence Packet / 证据包**：整理公开安全证据、来源 freshness、missing required sources、stale sources 和 `data_gap`。
- **K Deep Research Dossier / K 深度研究底稿**：先于 F/W/G 生成，形成主要研究底稿和待验证问题。
- **F/W/G Independent Perspectives / F/W/G 独立视角**：基于研究任务书、证据包和 K 底稿独立并行研究，各自产生 hash、timing 和 private record。
- **Chairman Synthesis / 主席综合**：综合 K 与 F/W/G，指出一致、冲突、证据强弱、不确定性和观察条件。
- **Red Team Audit / 红队反证审计**：攻击薄弱假设、过度确定、证据缺口和公开边界风险。红队不是 Judge。
- **Research Quality Gate / 研究质量闸门**：输出 `candidate | watch | avoid | needs_review | data_gap | high_uncertainty` 等研究状态。
- **Knowledge Gate / 知识闸门**：决定哪些知识可沉淀，哪些只是临时观察，哪些 unresolved questions 进入下一轮。
- **Alaya Readback / 内部 Alaya 回读**：验证 task、evidence、K dossier、agents、chairman、red team、quality gate、knowledge gate 和 public payload 的 hash。
- **Reader Boundary Gate / 读者边界闸门**：不隐藏研究内容，只确保公开表达不会被误读为投资建议或交易信号。

## 版本与 Schema

当前 v4 版本名：

| 类型 | 值 |
| --- | --- |
| prompt template | `gotra.full_analyst.prompt.v4.ksana_cognition_flywheel` |
| symbol schema | `gotra.full_analyst.symbol.v4` |
| daily reader schema | `gotra.daily_reader_brief.v4` |
| research task schema | `gotra.full_analyst.research_task.v2` |
| evidence packet schema | `gotra.full_analyst.evidence_packet.v2` |
| K dossier schema | `gotra.full_analyst.k_deep_research_dossier.v1` |
| perspective schema | `gotra.full_analyst.perspective_agent.v4` |
| chairman schema | `gotra.full_analyst.chairman_synthesis.v4` |
| red team schema | `gotra.full_analyst.red_team_audit.v4` |
| research quality gate | `gotra.full_analyst.research_quality_gate.v1` |
| knowledge gate | `gotra.cognition_flywheel.knowledge_gate.v1` |
| Alaya event schema | `gotra.cognition_flywheel.full_analyst_memory.v4` |

v2、v3、v3.5 的 fallback 仍保留，用于读取旧产物和避免历史报告断裂。不要把 v3.5 的 `PASS_WITH_REVIEW_ITEMS` 升级成 v4 pass，也不要把 v4 的 2h pressure 升级成 10h/formal acceptance。

## 主要入口

### Full Analyst v4 pipeline

核心脚本：

```bash
scripts/public_stock_pool_full_analyst_pipeline.py
```

查看参数：

```bash
cd /opt/gotra
/opt/gotra/.venv/bin/python scripts/public_stock_pool_full_analyst_pipeline.py --help
```

典型 v4 本地/服务器 canary 形态：

```bash
cd /opt/gotra
/opt/gotra/.venv/bin/python scripts/public_stock_pool_full_analyst_pipeline.py \
  --mode full-analyst-production-loop \
  --v40-cognition-flywheel \
  --execution-model deep_research_dossier_then_parallel_perspectives \
  --llm-runner codex-cli \
  --alaya-mode real \
  --max-concurrency 3 \
  --agent-concurrency 4 \
  --retries 1
```

生产发布必须按当次控制提示词决定是否加 `--publish-static`。不要把 local canary、smoke、production smoke 和正式验收混成一个结论。

### Daily stock-pool public report

传统 public stock-pool report 仍存在，和 v4 Full Analyst 不是同一层：

```bash
cd /opt/gotra
/root/.local/bin/uv run python scripts/public_stock_pool_report.py --mode morning-global --publish-static
/root/.local/bin/uv run python scripts/public_stock_pool_report.py --mode evening-hk --publish-static
```

`public_stock_pool_report.py` 写的是 public-safe 日报/状态产物；`public_stock_pool_full_analyst_pipeline.py` 写的是 Full Analyst / v4 cognition flywheel 研究产物。不要把两者的 `status.json` 混读。

## 生产产物

常用生产路径：

```text
/var/www/gotra-public-ledger/reports/daily_reader_brief.json
/var/www/gotra-public-ledger/reports/status_full_analyst_evening_hk.json
/var/www/gotra-public-ledger/reports/latest/
/var/www/gotra-public-ledger/reports/full-analyst/
```

重要字段：

```text
schema=gotra.daily_reader_brief.v4
symbol_schema=gotra.full_analyst.symbol.v4
methodology_version=ksana_cognition_flywheel_v4
execution_model=deep_research_dossier_then_parallel_perspectives
run_status=completed_with_review_items
public_scan_status=ok
alaya_readback_status=verified
```

如果 `status.json` 显示 partial 或 data gap，要先确认它属于传统 daily stock-pool report 还是 Full Analyst v4，不要直接判定 v4 失败。

## 验证命令

后端 focused checks：

```bash
cd /opt/gotra
/opt/gotra/.venv/bin/python -m pytest tests -q -k "full_analyst or research_task or evidence_packet or k_dossier or perspective_agent or chairman or red_team or knowledge_gate or alaya or public_safe"
/opt/gotra/.venv/bin/python scripts/public_stock_pool_full_analyst_pipeline.py --help
```

通用 checks：

```bash
cd /opt/gotra
/opt/gotra/.venv/bin/python -m pytest tests -q
git diff --check
```

文档-only 改动通常至少跑：

```bash
git diff --check
```

## 证据层级

阅读 GOTRA 结果时按以下层级解释：

| 层级 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| local checks | 代码、schema、fixture、lint/test/build 或脚本 help 可通过。 | 生产可用、研究质量稳定、正式验收。 |
| smoke evidence | 某条正向路径、生产路由或 canary 可读可跑。 | 长时间稳定、10h acceptance、科学证明。 |
| 2h pressure | v4 在指定窗口内完成多轮 production smoke/contract/HTTP/nginx 检查。 | 10h/formal acceptance、投资有效性、收益证明。 |
| 6h/10h/formal acceptance | 需要单独明确运行、证据文件和最终结论。 | 默认不能由 2h pressure 推导。 |
| science/public/performance claim | 需要完全不同的协议和证据。 | 本仓库当前不声称。 |
| trading/investment claim | 需要合规和交易层证据。 | GOTRA 不提供。 |

当前 v4 已完成的是 `2h pressure` + 前端 productization smoke，不是 10h/formal acceptance。

## Alaya 边界

本仓库里 Alaya 只表示 GOTRA repo 内部 cognition flywheel / knowledge memory / feedback / readback state。

禁止把它解释为：

- 外部 `/Users/peachy/Documents/alaya`；
- 外部 alaya repo；
- `ALAYA_BASE_URL`；
- `ALAYA_WRITE_PATH`；
- 外部知识库服务或商业产品。

公开产物里可以说明 Alaya readback verified，但不得暴露 secrets、raw provider I/O、完整内部 prompt、API key、Authorization/Bearer token。

## Artifact Hygiene

不要提交生成产物或敏感产物：

- raw provider/API outputs；
- Codex CLI transcripts；
- `.env*`，但 `.env.example` 除外；
- API keys、tokens、auth JSON；
- SQLite/DB files；
- `*.tar.gz`、`*.bundle`、zip archives；
- validation logs、review bundles、release bundles；
- private audit records，除非有明确 public-safe contract；
- `/tmp/gotra-*` 证据目录内容。

## 相关文档

核心契约：

- [`SPEC.md`](SPEC.md)
- [`docs/AUTONOMY_RUNBOOK.md`](docs/AUTONOMY_RUNBOOK.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/PUBLIC_STOCK_POOL_REPORT_AUTOMATION_RUNBOOK.md`](docs/PUBLIC_STOCK_POOL_REPORT_AUTOMATION_RUNBOOK.md)

历史 baseline 和边界文档仍保留，但它们代表旧证据族。阅读时要用对应版本和证据层级解释，不要把旧 baseline 叙事当成当前 v4 产品说明。

## License

[MIT](LICENSE)
