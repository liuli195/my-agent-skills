# PR Flow Init Validation

## validate（校验）输出

validation results（校验结果）必须按下面三组展示。

### error（错误）

配置不可用，init（初始化）必须停止且不写入。

示例：
- YAML（配置格式）无效。
- `defaults.baseBranch`（默认目标分支）为空。
- hotfix（热修复）允许直推但缺少授权、验证命令或 remote（远端名）。

### warning（警告）

配置可写入，但存在流程风险。

示例：
- GitHub（代码托管平台）auto-delete head branch（自动删除源分支）和 PR Flow cleanup（拉取请求流程清理）职责重叠。
- tweak（小改）只跳过插件内 review gate（审查门禁），不得声称绕过远端 required review（必需审查）。

### remote tasks（远端待办）

需要用户或后续 agent（代理）另行处理的 GitHub（代码托管平台）事项。remote tasks（远端待办）必须可执行，不得只写“配置 GitHub”。

示例：
- 创建或更新 branch ruleset（分支规则集）。
- 启用 `Require a pull request before merging`（合并前要求拉取请求）。
- 设置 `required_approving_review_count: 0`。
- 新增或识别 PR status checks（拉取请求状态检查）后，启用 `Require status checks to pass before merging`（合并前要求状态检查通过）。
- 如启用 CodeQL security check（CodeQL 安全检查），启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。
- 配置 allowed merge methods（允许合并方式）。
- 配置 Rulesets bypass（规则集绕过权限）。

GitHub access（GitHub 访问权限）、`gh` CLI（GitHub 命令行工具）或 network（网络）不可用时，GitHub 当前状态必须显示 `not inspected`（未检查）或 `no access`（无权限）。这种情况下只能输出推荐 remote tasks（远端待办），不能声明远端状态已确认。

## 依赖矩阵

| 场景 | validate（校验）规则 |
| --- | --- |
| hotfix（热修复） | `allowHotfixPush: true` 要求 `authorization.phraseHashAlgorithm: md5`、非空 `authorization.phraseHash`、非空 `hotfix.verifyCommand`、非空 `remote`，并输出 Rulesets bypass（规则集绕过权限）远端待办。 |
| branch protection（分支保护） | 通过 GitHub Rulesets（GitHub 规则集）远端待办表达；本地 init（初始化）不写远端。 |
| PR status checks（拉取请求状态检查） | 没有具体 check name（检查名称）时，只能输出新增或识别检查后的远端待办，不得编造名称。 |
| CodeQL security check（CodeQL 安全检查） | 开启时输出 GitHub（代码托管平台）远端待办：启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。 |
| merge methods（合并方式） | `merge`、`squash`、`rebase` 输出对应 GitHub（代码托管平台）allowed merge methods（允许合并方式）远端待办。 |
| cleanup（清理） | auto-delete head branch（自动删除源分支）和 PR Flow cleanup（清理）同时存在时输出 warning（警告）。 |
| fast/full verify（快速/完整验证） | full verify（完整验证）只作为显式 `hotfix.verifyCommand`（热修复验证命令）或 PR CI（拉取请求持续集成）建议，不从证据路径推断。 |

## 写入摘要

init（初始化）写入后只说明本地文件路径和 GitHub（代码托管平台）远端待办摘要，不声明远端已配置。
