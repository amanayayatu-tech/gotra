# Gotra 项目规约

> 本文件是给 AI coding agent 与协作者使用的紧凑操作规约。Gotra 应被视为一个
> 独立项目；外部仓库、服务、子模块只作为依赖存在，不在本规约中记录或暴露其
> 内部实现细节。

## 语言约定

本项目面向协作者和 agent 的规约、说明、报告、任务书默认使用中文。命令、路径、
环境变量、API 字段、代码标识和必要英文专有名词保持原样。

## 命令

除非特别说明，所有命令都从仓库根目录运行。

### 初始化

```bash
git submodule update --init --recursive
uv sync --frozen
cp .env.example .env
```

依赖子模块的检查必须先成功执行 `git submodule update --init --recursive`。如果
子模块不可用，只跳过对应的依赖检查，并明确报告原因。

下面只是 `.env.example` 的最小节选，完整配置以 `.env.example` 为准。

```bash
LLM_PROVIDER=codex_cli
LLM_MODEL=gpt-5.5
CODEX_PROVIDER_REASONING_EFFORT=xhigh
CODEX_PROVIDER_SANDBOX=read-only
CODEX_PROVIDER_CLEAN=1
AUTO_JUDGE=true
```

Phase BT 运行时，外部研究相关 key，例如 `PERPLEXITY_API_KEY` 和 `PPLX_API_KEY`，
必须保持未设置或空值，即使这些变量出现在 `.env.example` 中。

### 核心验证

```bash
uv run ruff check . --force-exclude
uv run pytest -q
git diff --check
```

如果 `.github/workflows/ci.yml` 中列出了子模块相关 guard，且子模块已初始化，应一并
运行。CI workflow 是精确 guard 路径和脚本的权威来源。

### CI 安全检查

权威安全闸位于 `.github/workflows/ci.yml`。在声明改动已达到 CI-ready 前，需要把
本地检查与该 workflow 对齐。当前 CI 覆盖：

- Ruff。
- 全量 pytest。
- 回测修复相关测试。
- heuristic BT canary。
- 直连 vendor LLM import guard。
- 直连 vendor endpoint / SDK dependency guard。
- 仓库卫生 guard。
- 子模块 orchestration guard。

不要把 workflow 脚本复制到本 spec。CI 如有变化，先改 workflow，本节只保留描述性
摘要。

### 分阶段专项检查

```bash
uv run pytest -q tests/test_judge_agent.py tests/test_judge_llm.py tests/test_auto_quarantine.py
uv run pytest -q tests/test_perplexity_executor.py tests/test_sync_gates.py
uv run pytest -q tests/test_daemon_run.py tests/test_reporting_ext.py
uv run pytest -q tests/test_backtest_analyze.py tests/test_backtest_ledger.py tests/test_backtest_parallel.py tests/test_backtest_walk_forward.py tests/test_backtest_price_cache.py
```

### Daemon 干跑

```bash
uv run python -m gotra.daemon_orchestration.run --once --type morning --dry-run
uv run python -m gotra.daemon_orchestration.run --once --type evening --dry-run
```

daemon CLI 必须带 `--once`。这是单个窗口的编排入口，不是长期运行服务的契约。

### 回测命令

sampled heuristic 验证只检查 plumbing：

```bash
uv run python -m gotra.backtest.walk_forward \
  --run-id bt_sampled_local \
  --mode sampled \
  --provider heuristic \
  --ledger sqlite \
  --parallel-mode ticker-chains \
  --provider-concurrency 2 \
  --token-budget 100000
```

分析已有 run，不调用 provider、不访问网络：

```bash
uv run python -m gotra.backtest.analyze \
  --run-root data/backtest/runs/<RUN_ID> \
  --min-paired-coverage 0.95
```

比较 baseline replay 与 reference run：

```bash
uv run python -m gotra.backtest.compare_runs \
  --reference-run data/backtest/runs/<REFERENCE_RUN_ID> \
  --candidate-run data/backtest/runs/<CANDIDATE_RUN_ID> \
  --arm baseline \
  --threshold 0.95
```

任何 `codex_cli` full/monthly provider run 都属于高成本动作，启动前必须取得明确批准。

## 目标

Gotra 是一个可审计的投研自动化与回测项目。它负责协调研究输入、决策记录、报告
和 walk-forward 验证，同时保持严格审计能力，并确保长期知识晋级仍受人类控制。

项目主张不是“模型能预测市场”。更窄的目标是：每一次研究决策都能留下从 signal、
prediction、observation、error attribution、knowledge update、quarantine 到长期
`strong` 知识人工批准的可审计链路。

## 权威来源

- `SPEC.md`：面向 agent 的紧凑操作规约。
- `README.md`：项目公开说明、快速开始和当前状态。
- `.github/workflows/ci.yml`：CI 命令和 guard 脚本的权威来源。
- `docs/AUTONOMY_RUNBOOK.md`：可执行阶段契约与安全规则。
- `docs/ROADMAP.md`：项目路线图。
- `docs/BT_PARALLEL_RUNNER_REPAIR_PLAN.md`：BT runner 修复计划与正式验收 caveat。
- `docs/PATH_SYNC_REVIEW_20260615.md`：本地 checkout / path 同步说明。
- `data/backtest/PREREGISTERED.md`：BT universe、gate、hypothesis 和 anti-p-hacking
  规则。
- `methodologies/autonomy_v1.md`：自主化、外部研究、审计与 human-only promotion 边界。

如果这些文件冲突，采用更严格的安全/审计规则。回答当前分支、子模块或 run 状态前，
必须用 git 和 artifact 读取验证真实本地状态。

## 技术栈

- Python `>=3.11`；CI 使用 Python `3.12`。
- 包管理：`uv`。
- 测试框架：`pytest`。
- Lint：`ruff`，line length 100，Python target `py311`。
- 主要数据/验证库：`pandas`、`numpy`、`scipy`、`statsmodels`、`pydantic`、
  `jsonschema`、`PyYAML`、`tenacity`、`httpx`、`yfinance`。
- 本地依赖可以通过 git submodule 提供；把它们视为依赖，不视为 gotra 拥有的实现空间。
- CI：`.github/workflows/ci.yml` 中的 GitHub Actions。

## 项目结构

```text
gotra/
  gotra/
    backtest/                # walk-forward runner、audit、ledger、analyzer、report
    daemon_orchestration/    # morning/evening 单窗口编排入口
    judge_agent/             # gate judge client、polling、auto-quarantine
    perplexity_executor/     # gotra 侧外部研究 auto-fill operator
    reporting_ext/           # Markdown/HTML report 与 notifier
  integrations/              # gotra 拥有的 integration adapter
  contracts/                 # 跨系统 JSON schema contract
  data/backtest/             # preregistered protocol 进 git；runtime artifact 忽略
  docs/                      # runbook、roadmap、repair plan、checkout note
  engine/                    # 外部 engine dependency 区域；不要在 spec 暴露内部实现
  methodologies/             # gotra autonomy methodology
  tests/                     # gotra tests
```

用通用命令检查依赖状态：

```bash
git submodule status --recursive
```

不要假设子模块已初始化，也不要从旧记忆里假设它的 pin。

## 代码风格

遵循现有 Python 风格：typed functions、`Path` 文件路径、dataclass 表达结构化
config/result、显式 JSON artifact、小而纯的审计辅助函数。

本地风格示例：

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DaemonRunConfig:
    brief_type: str
    data_dir: Path = Path("data")
    dry_run: bool = False
```

处理结构化数据时优先使用 JSON、YAML、SQLite、pydantic、jsonschema 等已有工具，
避免临时字符串解析。

## 测试规则

- 先运行触达模块的 targeted tests。
- 声称代码改动 ready 前，至少运行 `uv run ruff check . --force-exclude`、
  `uv run pytest -q` 和 `git diff --check`。
- 查看 `.github/workflows/ci.yml`，确认是否还有与当前改动相关的额外 guard。
- 如果改动 BT runner / analyzer / ledger / parallelism，运行 BT 测试组，并尽量跑
  至少一个 heuristic sampled canary；若无法运行，说明限制和风险。
- 如果改动外部研究边界，运行 `tests/test_perplexity_executor.py`，并在可用时运行相关
  CI 子模块 guard。
- 如果改动 integration 或 judge 行为，必须证明写入走审计路径，并保留 human-only
  strong promotion。
- 如果某项检查不能运行，明确说明原因和剩余风险。

## 边界

### Always

- 在作出状态判断前验证真实本地状态：branch、dirty tree、submodule state、当前
  artifact、相关 run JSON。
- 除非 runbook 明确要求跟踪，generated artifact 不进 git。
- LLM 调用必须留在批准的 provider interface 与 Codex CLI 路径之后。
- BT 输入可用性必须可审计：`availability_date <= T`，或价格行切片到
  `date <= decision_date`。
- 判断 BT run 健康时读取/生成 `system_health.json`、`summary.json`、
  `event_log.jsonl`、`quality_summary.json`。
- 只有 sampled/local correctness 得到验证时，表述为 `BT-sampled PASS`。
- 保留负面或混合科学结果，如实报告，不改口径。
- `active -> strong` 知识晋级保持 human-only。

### Ask First

- 启动 full/monthly `codex_cli` provider BT run，或任何可能消耗大量 token 的动作。
- 修改 preregistered BT hypothesis、threshold、window、universe，或 `95%` baseline
  replay direction-agreement gate。
- 新增依赖、修改 `uv.lock`、修改 CI。
- 修改 `contracts/investment_event.schema.json`、其他 `contracts/` schema 或跨系统 API
  语义。
- 编辑外部依赖/子模块源码，或更新子模块 pointer。
- 修改任何可能影响 `strong` promotion 的行为。
- 删除失败测试、失败 run artifact、cache evidence 或 reviewer bundle。

### Never

- 绝不提交 secrets、`.env`、API key、token、SQLite DB、validation log、provider cache、
  BT run directory、generated report、patch、tarball、pyc 文件。
- 绝不在 gotra business code 中直接 import OpenAI/Anthropic SDK，或调用 direct vendor
  endpoint。
- 绝不在外部依赖/子模块代码中加入外部研究 API 调用。
- 绝不在设置了 `PERPLEXITY_API_KEY` 或 `PPLX_API_KEY` 的情况下运行 Phase BT。
- 绝不绕过审计 API/service path 做 raw write。
- 绝不自动把知识晋级为 `strong`。
- 绝不在看到 run output 后放宽 gate。禁止 p-hacking。
- 绝不把 CI、heuristic、sampled 或 plumbing-only evidence 说成 full Stage 3 科学验收。

## 回测验收

BT 有两类必须分开的 verdict：

- Correctness / plumbing：无 future-data audit violation、无 crash、artifact 可审计、
  budget/pause 状态清晰、event actor 存在、本地 deterministic tests/canaries 通过。
- Scientific hypotheses：`data/backtest/PREREGISTERED.md` 中的 H1/H2/H3，包括正式 gate
  要求 baseline replay direction agreement 达到或超过 `95%`。

具体 run id、replay count、当前 pass/fail 状态不在本 spec 中维护。作出状态判断前，
读取当前 run artifact、`README.md` 和 BT repair/status 文档。

heuristic sampled run 的有效终态表述是：

```text
BT-sampled PASS: plumbing/audit/cache/budget/report chain validated.
No full monthly/provider scientific claim was proven.
```

## Git 工作流

- 保留无关用户改动，不回滚自己没改的文件。
- 使用小而清晰的 phase-scoped branch 和 commit。CI branch filter 以
  `.github/workflows/ci.yml` 为准。
- source、tests、schemas、preregistration、durable docs 进 git。
- `FIX_REPORT_*.md`、`*.patch`、`REVIEW_BUNDLE_*.tar.gz`、`validation-logs/`、
  `data/backtest/prices/`、`data/backtest/runs/`、`data/backtest/REPORT_backtest*`、
  SQLite DB、本地 cache 不进 git。
- 子模块/依赖 pointer 变更视为显式 dependency update，需要审阅。

## Agent 工作流

使用带闸门的流程：

1. Specify：重述用户可见目标和成功/失败标准。
2. Plan：识别触达模块、精确验证命令和边界。
3. Tasks：拆成可独立测试的小任务。
4. Implement：做最小必要改动，先跑 targeted checks，再按风险运行更广检查。

大型任务不要把整份 runbook 塞进上下文。用本 spec 当地图，再只打开相关源文档和
代码路径。

## 开工前当前状态检查

```bash
git status --short --branch
git submodule status --recursive
git ls-files data/backtest/REPORT_backtest.md data/backtest/prices data/backtest/runs
uv run ruff check . --force-exclude
```

最后一个命令对只读排查是可选的；但在声明代码改动 clean 前必须运行。
