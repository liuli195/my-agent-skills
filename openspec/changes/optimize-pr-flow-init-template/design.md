## Context

`pr-flow-init`（拉取请求流程初始化）已经拆成入口 Skill（技能）和三个 reference（参考文件），但当前问答仍沿用旧模型：先问目标分支，再问 review gate（审查门禁），最后把 protected branches（受保护分支）、required checks（必需检查）、required review（必需审查）作为远端建议选项。实际交互证明这个模型会让用户和 agent（代理）混淆本地运行配置、GitHub Rulesets（GitHub 规则集）和可执行远端待办。

本变更只优化初始化模板和测试契约。`pr_flow.py`（脚本）继续只负责只读 validate（校验）和已确认配置写入，不自动读取或修改 GitHub（代码托管平台）远端设置。

## Goals / Non-Goals

**Goals:**

- 把问答模板改为自动检查 + 6 个主问题。
- 用 GitHub 官方规则名表达远端待办。
- 区分本地将写入、GitHub 当前状态、GitHub 推荐配置和校验结果。
- 保留“已有配置不能代替用户回答或确认”的保护约束。
- 保留 plugin entrypoint（插件入口）路由验收，确认 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）仍指向 init（初始化）能力；只有文案冲突时才改这些入口文件。

**Non-Goals:**

- 不新增 GitHub（代码托管平台）远端自动配置命令。
- 不改变 `complete`、`cleanup`、`hotfix`、`tweak`（收尾、清理、热修复、小改）运行语义。
- 不重新设计 PR Flow（拉取请求流程）运行时配置结构。

## Decisions

### 1. 问答从“字段驱动”改为“用户决策驱动”

采用 6 个主问题：默认 PR target branch（拉取请求目标分支）、branch protection（分支保护）目标、PR status checks（拉取请求状态检查）、CodeQL security check（CodeQL 安全检查）、hotfix（热修复）直推、merge methods（合并方式）。hotfix（热修复）授权短语只在允许 hotfix 后作为补充问题出现。

替代方案是保留旧 `reviewGate`（审查门禁）问题并补说明。该方案仍会让用户把本地 review gate（审查门禁）误解为 GitHub PR review（拉取请求代码审查），因此放弃。

### 2. branch protection（分支保护）用 Rulesets（规则集）表达

模板把 branch protection（分支保护）定义为 GitHub Rulesets（GitHub 规则集）中的 branch ruleset（分支规则集），并明确启用 `Require a pull request before merging`（合并前要求拉取请求）。默认 `required_approving_review_count: 0`，表示要求通过 PR（拉取请求）改分支，但不强制 approving review（批准审查）。

### 3. PR status checks（拉取请求状态检查）单独问

PR status checks（拉取请求状态检查）需要具体 check name（检查名称）。当自动检查没有发现可用 PR 工作流时，模板只能记录“待新增或识别 PR status checks 后再启用 `Require status checks to pass before merging`”，不能编造检查名。

### 4. 草案展示面向用户，而不是面向 YAML（配置格式）

`config-draft.md`（配置草案规则）先要求展示用户可读表格：本地将写入、GitHub 当前状态、GitHub 推荐配置、风险和待办。YAML（配置格式）只作为附录，避免用户先看到配置细节而看不出流程含义。

### 4a. CodeQL 安全检查单独问

模板在 PR status checks（拉取请求状态检查）后追加 CodeQL security check（CodeQL 安全检查）问题，只提供“开启”和“不开启”两个选项。选择开启时，远端待办必须要求在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），并选择 `CodeQL` 作为 code scanning tool（代码扫描工具）。

### 5. 校验摘要输出可执行远端待办

`validation.md`（校验规则）不只列 `setup suggestion`（配置建议）字符串，还要求按 error（错误）、warning（警告）、remote tasks（远端待办）分组。远端待办必须可执行，例如创建 branch ruleset（分支规则集）、启用 `Require a pull request before merging`、设置 `required_approving_review_count: 0`、配置 Rulesets bypass（规则集绕过权限）。

### 6. GitHub 不可检查时必须显式降级

自动检查只能展示真实读取到的 GitHub（代码托管平台）当前状态。若 GitHub access（GitHub 访问权限）、`gh` CLI（GitHub 命令行工具）或 network（网络）不可用，模板必须显示 `not inspected`（未检查）或 `no access`（无权限），并且只输出推荐远端待办，不得声明远端当前状态已确认。

## Risks / Trade-offs

- 风险：reference（参考文件）文案变长。缓解：入口 Skill（技能）仍保持短，只把细节放进 references（参考文件）。
- 风险：`setup.github`（GitHub 配置建议）字段无法表达所有远端配置细节。缓解：本变更只要求展示可执行待办，不要求脚本消费或完整建模远端规则。
- 风险：旧测试只检查关键词，不能保证交互质量。缓解：新增测试锁定 6 问、官方规则名和用户可读摘要结构。

## Open Questions

无。当前方案已确认：源分支删除策略不再作为问题询问，默认保持 GitHub auto-delete head branch（自动删除源分支）关闭，由 PR Flow cleanup（拉取请求流程清理）负责。
