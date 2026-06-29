---
comet_change: prefer-codeql-default-setup
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-29-prefer-codeql-default-setup
status: final
---

# Prefer CodeQL Default Setup Design

## 背景

PR Flow init（拉取请求流程初始化）已经把 CodeQL security check（CodeQL 安全检查）从 PR status checks（拉取请求状态检查）里拆出，但仍把 CodeQL scan producer（CodeQL 扫描结果来源）描述成“创建或启用”，并允许把 `Analyze Python` 放进状态检查。这会让 agent（代理）默认偏向 Advanced setup（高级配置）workflow（工作流），而不是用户期望的 GitHub CodeQL Default setup（GitHub CodeQL 默认配置）。

## 方案

复用现有 `setup.github.codeScanning`（代码扫描配置）作为 CodeQL security check（CodeQL 安全检查）开关，不新增配置字段。

开启 CodeQL（代码查询扫描）时，PR Flow init（拉取请求流程初始化）只输出 remote tasks（远端待办）：

- 启用 CodeQL Default setup（CodeQL 默认配置）。
- 在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL`，阈值使用 GitHub 默认阈值。

PR status checks（拉取请求状态检查）只展示非安全扫描检查。`Analyze Python`、`Analyze (python)`、`Analyze (actions)` 和 `CodeQL` 都不作为状态检查选项展示。

## validate（校验）

validate（校验）保持只读，不调用 GitHub API（GitHub 接口），不声明远端 Default setup（默认配置）已经启用。

只要配置声明 `setup.github.codeScanning`（代码扫描配置），validate（校验）就输出：

- `enable CodeQL Default setup`
- `configure GitHub Rulesets CodeQL code scanning`

即使项目存在本地 `codeql-action` workflow（工作流），也仍输出 Default setup（默认配置）remote task（远端待办）。

本次不新增 `defaultSetup` 或等价配置字段。配置草案、写入配置和 validate（校验）继续只使用 `setup.github.codeScanning`（代码扫描配置）表达 CodeQL security check（CodeQL 安全检查）。

## 测试

用 `tests/test_pr_flow_cli.py`（PR Flow 命令行测试）覆盖：

- 问答模板要求 Default setup（默认配置）。
- PR status checks（拉取请求状态检查）段落不展示 CodeQL（代码查询扫描）相关检查选项。
- config draft（配置草案）和 validation（校验说明）使用 Default setup（默认配置）表述。
- validate（校验）在有本地 `codeql-action` workflow（工作流）时仍输出 Default setup（默认配置）remote task（远端待办）。
- validate（校验）不调用 `gh` CLI（GitHub 命令行工具）或 GitHub API（GitHub 接口）读取远端状态。
- 配置草案和写入配置不新增 `defaultSetup` 或等价配置字段。
- 运行 OpenSpec validation（规格校验）和 pr-flow-init（拉取请求流程初始化）到 validate（校验）/init（初始化）写入的端到端回归。
