# AGENTS.md

本仓库用于开发和维护个人 Agent Plugin（插件）与 Skill（技能）。

## 核心规则
- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。

## 通用规则

### 环境与工具

- **运行边界**：本仓库维护 Agent Plugin（插件）与 Skill（技能）源码；安装到用户环境或目标项目前需明确授权。
- **GitHub CLI**：`gh` CLI 默认在仓库内执行，让 `gh` 根据 `git remote -v` 自动识别仓库。
- **构建与验证**：使用 build-and-verify Skill（技能）执行构建检查和验证；禁止自行新增构建和验证入口。

### 工作边界

- **先行调查**：不推测未读代码；不确定时说明并验证。
- **执行边界**：只执行用户显式授权的操作；未授权时默认先给方案或计划等待确认，禁止自行决策并执行任何改动（包括安装包、修改配置、重构、删除、提交、切换分支、启停服务等）；`auto` 权限模式不视为授权，仅影响单次工具调用的确认流程。
- **文件规范**：优先编辑现有文件，非必要不新建；任务后清理临时产物。

### Git 与 PR

- **Git**：分支名使用 ASCII 模板，提交说明用简体中文。
- **PR 纪律**：进入主干须通过 PR；用户显式授权才可直写主干；禁止把功能分支本地合入 `main`。
- **安全性**：破坏性操作前需确认，包括强制推送、硬重置、`--no-verify`。

### Review 与验证

- **完成验证**：逐项复核要求，说明已验证与无法验证的部分。
- **完整集成测试**：所有改动都必须运行覆盖对应主流程的端到端回归；端到端回归必须从用户入口或发布形态跑完整业务流程，不能用几个单元测试拼接替代。

### 输出与引用

- **输出**：简体中文，使用用户语言，禁止技术语言。英文名词后面必须跟（中文释义）。

<comet-ambient-resume>
<!-- Managed by Comet. Edits inside this block may be replaced by comet init/update. -->
<!-- Contract: comet.resume_probe.v2 -->

## Comet Ambient Resume

在这个仓库中，开始处理需要改动或调查的任务前，如果可能存在活跃 Comet workflow，把当前用户请求传入只读探针：`comet resume-probe . --stdin --json`。

- 只信任返回的 `workflow`、`skill` 和 `entrySource`；它们只由项目配置或无配置兼容回退决定。不得扫描或切换另一套 workflow。
- 如果 probe 返回 `auto_resume`，简短说明选中的 active change，并进入 `nextCommand` 指向的永久入口。不要把状态命令当作恢复入口直接推进。
- 如果 probe 返回 `ask_user`，只问一个简短问题并等待用户回复。
- 如果 probe 返回 `out_of_scope` 或 `none`，不要进入 Comet workflow。
- 如果配置或状态无效且没有 `nextCommand`，停止并报告原因；不要猜测另一个 workflow。
- 不能只因为存在 active change 就把无关任务挂到该 change。Native 的未提交改动由 Native 入口检查，不由探针自动归因。
</comet-ambient-resume>
