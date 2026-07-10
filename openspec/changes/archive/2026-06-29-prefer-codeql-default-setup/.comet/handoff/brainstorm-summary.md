# Brainstorm Summary

- Change: prefer-codeql-default-setup
- Date: 2026-06-29

## 确认的技术方案

复用现有 `setup.github.codeScanning`（代码扫描配置）作为 CodeQL security check（CodeQL 安全检查）开关，不新增配置字段。开启时，PR Flow init（拉取请求流程初始化）默认输出启用 CodeQL Default setup（CodeQL 默认配置）和配置 Rulesets（规则集）code scanning（代码扫描）门禁的 remote tasks（远端待办）。

## 关键取舍与风险

validate（校验）不查询 GitHub（代码托管平台）远端，因此不声明 Default setup（默认配置）已启用；即使存在本地 `codeql-action` workflow（工作流），也仍输出启用 Default setup（默认配置）的 remote task（远端待办）。

配置契约不扩张：配置草案、写入配置和 validate（校验）继续只使用 `setup.github.codeScanning`（代码扫描配置），不新增 `defaultSetup` 或等价配置字段。

## 测试策略

用现有 `tests/test_pr_flow_cli.py`（PR Flow 命令行测试）覆盖问答模板、配置草案、校验说明和 validate（校验）输出。

补充验证：覆盖 validate（校验）不调用 GitHub API（GitHub 接口）/`gh` CLI（GitHub 命令行工具），配置草案不新增字段，OpenSpec validation（规格校验），以及 pr-flow-init（拉取请求流程初始化）到 validate（校验）和 init（初始化）写入的端到端回归。

## Spec Patch

已写入 delta spec（增量规格）：`openspec/changes/prefer-codeql-default-setup/specs/pr-flow-plugin/spec.md`。
