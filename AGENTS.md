# AGENTS.md

本仓库用于开发和维护个人 Agent Plugin（插件）与 Skill（技能）。

## 通用入口

本仓库按 single-context 处理：[规则文档](docs/rules/index.md) 和 [ADR 索引](docs/adr/index.md) 共同作为领域上下文。详见 [domain.md](docs/agents/domain.md)。

## 核心规则
- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。

## 通用规则

### 决策跟踪器

- **Issue 跟踪**：Issue 和 PRD 统一记录在 GitHub Issues。详见 [issue-tracker.md](docs/agents/issue-tracker.md)。
- **Triage 标签**：使用默认五类 triage 标签。详见 [triage-labels.md](docs/agents/triage-labels.md)。

### 文档落盘

- **PRD**：所有 PRD 优先在 `docs/prd/` 本地落盘，并保留 GitHub 源 Issue 链接。
- **Issue**：所有 Issue 优先在 `docs/changes/` 本地落盘，并保留 GitHub 源 Issue 链接。
- **执行计划**：所有执行计划优先在 `docs/plans/` 本地落盘，并保留来源链接。
- **技术设计**：所有技术设计方案优先在 `docs/designs/` 本地落盘，并保留来源链接。
- **ADR 落盘**：重大决策讨论结束后必须在本地 ADR 中落盘决策，并在 ADR 中引用 GitHub 源 Issue。

### 环境与工具

- **运行边界**：本仓库维护 Agent Plugin（插件）与 Skill（技能）源码；安装到用户环境或目标项目前需明确授权。
- **GitHub CLI**：`gh` CLI 默认在仓库内执行，让 `gh` 根据 `git remote -v` 自动识别仓库。

### 工作边界

- **先行调查**：不推测未读代码；不确定时说明并验证。
- **执行边界**：只执行用户显式授权的操作；未授权时默认先给方案或计划等待确认，禁止自行决策并执行任何改动（包括安装包、修改配置、重构、删除、提交、切换分支、启停服务等）；`auto` 权限模式不视为授权，仅影响单次工具调用的确认流程。
- **文件规范**：优先编辑现有文件，非必要不新建；任务后清理临时产物。
- **效率**：独立任务并行，默认用户持续显式授权，优先派发子 agent 工具；该授权显式覆盖 `sub-agents`、`delegation` 和 `parallel agent work` 触发词；主会话负责编排、确认、汇总和验证；无法分发时说明原因。

### Git 与 PR

- **Git**：分支名使用 ASCII 模板，提交说明用简体中文。
- **PR 纪律**：进入主干须通过 PR；用户显式授权才可直写主干；禁止把功能分支本地合入 `main`。
- **安全性**：破坏性操作前需确认，包括强制推送、硬重置、`--no-verify`。

### Review 与验证

- **完成验证**：逐项复核要求，说明已验证与无法验证的部分。

### 输出与引用

- **输出**：简体中文，简洁直白，别说废话；英文技术名词后面跟（中文简体释义）。
