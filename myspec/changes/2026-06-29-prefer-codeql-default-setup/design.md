## Context

PR Flow init（拉取请求流程初始化）已经把 CodeQL security check（CodeQL 安全检查）从 PR status checks（拉取请求状态检查）里拆出来，但旧文案和 validate（校验）仍把本地 CodeQL workflow（工作流）当作合格扫描来源。这会让 agent（代理）默认走 Advanced setup（高级配置），而用户期望默认使用 GitHub CodeQL Default setup（GitHub CodeQL 默认配置）。

## Goals / Non-Goals

**Goals:**
- CodeQL security check（CodeQL 安全检查）开启时，默认 remote task（远端待办）要求启用 CodeQL Default setup（CodeQL 默认配置）。
- PR status checks（拉取请求状态检查）只展示非安全扫描检查，不再提供 CodeQL（代码查询扫描）相关检查。
- validate（校验）保持只读，不确认远端状态，只输出可执行 remote tasks（远端待办）。

**Non-Goals:**
- 不自动调用 GitHub API（GitHub 接口）启用 Default setup（默认配置）。
- 不删除已有 Advanced setup（高级配置）workflow（工作流）。
- 不新增 PR Flow（拉取请求流程）配置字段。

## Decisions

- 用现有 `setup.github.codeScanning`（代码扫描配置）表达 CodeQL（代码查询扫描）开关，不新增 `defaultSetup` 字段。现有配置已经足够表达用户意图。
- validate（校验）不再用本地 workflow（工作流）判断扫描来源是否满足。它无法确认远端 Default setup（默认配置）状态，因此固定输出启用 Default setup（默认配置）的 remote task（远端待办）更诚实。
- PR status checks（拉取请求状态检查）规则直接排除 `Analyze Python`、`Analyze (python)`、`Analyze (actions)` 和 `CodeQL`。CodeQL（代码查询扫描）门禁由 Rulesets（规则集）的 `Require code scanning results`（要求代码扫描结果）表达。

## Verification Notes

- Tests must prove local config（本地配置） continues to use only `setup.github.codeScanning`（代码扫描配置） and does not introduce `defaultSetup` or equivalent new fields（等价新字段）。
- Tests must prove validate（校验） does not call GitHub API（GitHub 接口） or `gh` CLI（GitHub 命令行工具） to inspect remote Default setup（默认配置）。

## Risks / Trade-offs

- 已经使用 Advanced setup（高级配置）的仓库仍会看到启用 Default setup（默认配置）的待办。Mitigation（缓解）：文案明确这是默认推荐，不自动改远端。
- validate（校验）不会证明远端已配置。Mitigation（缓解）：继续使用 `not inspected`（未检查）/ remote task（远端待办）语义，不声称远端已确认。
