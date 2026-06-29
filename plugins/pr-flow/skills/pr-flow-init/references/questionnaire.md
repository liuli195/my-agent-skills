# PR Flow Init Questionnaire

agent（代理）必须按本文件执行，不能临场编造问题。现有 `.pr-flow/config.yaml`（配置文件）、branch state（分支状态）或 history（历史记录）只能作为参考，不能代替用户回答或最终确认。

交互硬约束：每次只提出一个问题。必须等用户回答当前问题后，才能进入下一个问题；不得一次性列出全部问题让用户批量回答。

## 场景：automatic inspection（自动检查）

固定动作：提问前先做只读检查，并用表格展示已检查到的当前状态。

检查范围：
- default branch（默认分支）。
- remote branches（远端分支）。
- GitHub Rulesets（GitHub 规则集）。
- branch protection（分支保护）。
- merge methods（合并方式）。
- auto-delete head branch（自动删除源分支）。
- available PR status checks（可用拉取请求状态检查）。

降级规则：如果 GitHub access（GitHub 访问权限）、`gh` CLI（GitHub 命令行工具）或 network（网络）不可用，GitHub 当前状态必须显示 `not inspected`（未检查）或 `no access`（无权限），只能输出推荐远端待办，不能声明远端状态已确认。

选择后果：不写本地配置，不写 GitHub（代码托管平台）远端配置。

跳转规则：继续 default PR target branch（默认拉取请求目标分支）场景。

## 场景：default PR target branch（默认拉取请求目标分支）

固定问题：默认 PR target branch（默认拉取请求目标分支）是哪一个？

固定选项：
- 当前 default branch（默认分支）：推荐，通常是 `main`。
- 其他已检查到的 remote branch（远端分支）：只在用户明确选择时使用。
- 自定义分支名：只在用户明确提供时使用。

选择后果：写入 `defaults.baseBranch`（默认目标分支）。

跳转规则：继续 branch protection（分支保护）场景。

## 场景：branch protection（分支保护）

固定问题：哪些分支需要通过 GitHub Rulesets（GitHub 规则集）做 branch protection（分支保护）？

固定选项：
- 从 automatic inspection（自动检查）得到的 remote branches（远端分支）逐项列出，让用户多选。
- 默认 PR target branch（默认拉取请求目标分支）：如果存在于 remote branches（远端分支）中，标注为推荐。
- 暂不配置远端保护。

选项规则：
- 不得固定写死 release、main 或其他分支名。
- 如果没有检查到 remote branches（远端分支），先说明当前状态为 `not inspected`（未检查）或 `no access`（无权限），再让用户手工输入要保护的分支名或选择暂不配置。

选择后果：
- 本地配置只记录 `setup.github`（GitHub 配置建议），不自动写远端。
- 选择一个或多个保护分支时，派生写入 `defaults.reviewGate.mode: github`，表示本地 PR Flow（拉取请求流程）不做本地审查门禁，审查与保护交给 GitHub（代码托管平台）远端规则。
- 选择“暂不配置远端保护”时，不得派生 `defaults.reviewGate.mode: github`；保持现有或默认 `reviewGate.mode` 不变。
- 远端待办必须写成创建或更新 branch ruleset（分支规则集）。
- 远端待办必须启用 `Require a pull request before merging`（合并前要求拉取请求）。
- 默认写明 `required_approving_review_count: 0`，表示要求通过 PR（拉取请求）修改受保护分支，但不强制 approving review（批准审查）。
- 远端待办必须默认启用 `Restrict deletions`（限制删除）。
- 远端待办必须默认启用 `Block force pushes`（阻止强制推送）。

跳转规则：继续 CodeQL security check（CodeQL 安全检查）场景。

## 场景：CodeQL security check（CodeQL 安全检查）

固定问题：是否启用 CodeQL security check（CodeQL 安全检查）？

固定选项：
- 开启：启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。
- 不开启：不生成 CodeQL（代码扫描工具）远端待办。

选择后果：
- 开启：只写入 `setup.github`（GitHub 配置建议）remote task（远端待办），包含启用 CodeQL Default setup（CodeQL 默认配置）和 Rulesets rule（规则集规则），不自动写 GitHub（代码托管平台）远端。
- 不开启：不写 CodeQL（代码扫描工具）远端待办。

跳转规则：
- 开启：继续 PR status checks（拉取请求状态检查）场景；后续只展示非安全扫描 check name（检查名称）。
- 不开启：继续 PR status checks（拉取请求状态检查）场景；后续只展示非安全扫描 check name（检查名称）。

## 场景：PR status checks（拉取请求状态检查）

固定问题：是否要求 PR status checks（拉取请求状态检查）通过后才能合并？

固定选项：
- 暂不启用：适合没有稳定 PR 工作流的仓库。
- 启用已检查到的非安全扫描 check name（检查名称）。
- 先记录待办：新增或识别 PR status checks（拉取请求状态检查）后，再启用远端规则。

检查项展示规则：
- 每个 check name（检查名称）必须附带用途说明后才能让用户选择。
- 用途说明至少包含：来源 workflow/job（工作流/任务）、验证内容、失败影响。
- 如果无法判断某个 check name（检查名称）的用途，必须标注“用途未识别”，不得假装已理解。
- 不得展示 CodeQL（代码扫描工具）生成的 check name（检查名称）。
- CodeQL security gate（CodeQL 安全门禁）默认由 `Require code scanning results`（要求代码扫描结果）表达。

选择后果：
- 如果用户选择启用但没有具体 check name（检查名称），必须记录 remote task（远端待办）：新增或识别 PR status checks（拉取请求状态检查）后再启用 `Require status checks to pass before merging`（合并前要求状态检查通过）。
- agent（代理）不得编造 check name（检查名称）。

跳转规则：继续 hotfix（热修复）场景。

## 场景：hotfix（热修复）直推

固定问题：是否允许 hotfix（热修复）直接推送受保护目标分支？

固定选项：
- 不允许：推荐。
- 允许：只在用户明确授权时使用。

选择后果：
- 不允许：写入 `allowHotfixPush: false`（不允许热修复直推）。
- 允许：写入 `allowHotfixPush: true`（允许热修复直推）、`hotfix.verifyCommand`（热修复验证命令）和 `remote`（远端名），继续 authorization phrase（授权短语）场景，并生成 Rulesets bypass（规则集绕过权限）远端待办。

跳转规则：
- 不允许：继续 merge methods（合并方式）场景。
- 允许：继续 authorization phrase（授权短语）场景。

## 场景：authorization phrase（授权短语）

固定问题：hotfix（热修复）授权短语如何处理？

固定选项：
- `reuse existing authorization phrase`：复用现有授权短语哈希。
- `create new authorization phrase`：新设授权短语并写入新的哈希。

选择后果：只允许二选一。不得要求用户手工提供 MD5（MD5 哈希算法）值；如果需要新设，由 agent（代理）根据用户确认的短语生成配置草案。

配置草案必须写入：
- `authorization.phraseHashAlgorithm: md5`。
- `authorization.phraseHash`，值为复用的现有哈希或新设授权短语生成的哈希。

跳转规则：继续 merge methods（合并方式）场景。

## 场景：merge methods（合并方式）

固定问题：允许哪些 merge methods（合并方式）？

固定选项：
- `merge`：普通合并。
- `squash`：压缩合并。
- `rebase`：变基合并。
- 多选：只保留用户明确允许的方式。

选择后果：
- 写入本地默认 merge strategy（合并策略）。
- 在 `setup.github`（GitHub 配置建议）中记录 allowed merge methods（允许合并方式）远端待办。

跳转规则：继续 GitHub 推荐配置场景。

## 场景：GitHub 推荐配置

固定动作：在最终写入确认前，展示 GitHub（代码托管平台）remote tasks（远端待办）摘要。

固定展示内容：
- GitHub 当前状态：只展示 automatic inspection（自动检查）真实读到的状态；未检查时显示 `not inspected`（未检查）或 `no access`（无权限）。
- GitHub 推荐配置：列出将由人工或后续 agent（代理）执行的 remote tasks（远端待办）。
- 明确说明：这些是推荐配置，不代表 init（初始化）已经写入 GitHub（代码托管平台）远端。

选择后果：不写本地配置，不写 GitHub（代码托管平台）远端配置。

跳转规则：继续最终写入确认。

## 场景：最终写入确认

固定问题：最终如何处理本次 PR Flow（拉取请求流程）初始化配置？

固定选项：
- 不写入，放弃本次配置。
- 只写入本地配置。
- 按 remote tasks（远端待办）完成 GitHub（代码托管平台）配置，然后再写入本地配置。

选择后果：
- 不写入，放弃本次配置：停止，不写入 `.pr-flow/config.yaml`、`.pr-flow/pr-template.md` 和 `.pr-flow/.gitignore`。
- 只写入本地配置：仅在 validate（校验）没有 error（错误）时运行 init（初始化）写入本地文件，不写 GitHub（代码托管平台）远端配置。
- 按 remote tasks（远端待办）完成 GitHub（代码托管平台）配置，然后再写入本地配置：agent（代理）先按远端待办执行 GitHub（代码托管平台）配置，再在 validate（校验）没有 error（错误）时运行 init（初始化）写入本地文件。用户选择此选项，即代表用户授权进行 GitHub（代码托管平台）配置。
- GitHub（代码托管平台）配置由 agent（代理）执行；插件不提供 GitHub（代码托管平台）配置脚本能力。
- 用户沉默 MUST NOT 被视为确认。

跳转规则：选项 1 停止；选项 2 运行 init（初始化）写入本地配置；选项 3 先完成 remote tasks（远端待办），再运行 init（初始化）写入本地配置。

## 禁止重复问题

branch protection（分支保护）已经表达是否要求通过 PR（拉取请求）修改分支。PR status checks（拉取请求状态检查）已经表达是否要求检查通过。后续不得再单独询问 required review（必需审查）或 required checks（必需检查）作为重复主问题。
