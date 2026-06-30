## 1. PR Flow CodeQL default setup

- [x] 1.1 Update tests to require CodeQL Default setup（CodeQL 默认配置） guidance, exclude CodeQL checks（CodeQL 检查） from PR status checks（拉取请求状态检查）, and reject new `defaultSetup` or equivalent config fields（等价配置字段）.
- [x] 1.2 Update PR Flow init（拉取请求流程初始化） guidance and validate（校验） output to prefer CodeQL Default setup（CodeQL 默认配置） while keeping validate（校验） local-only and not inspecting GitHub（代码托管平台） remote state.
- [x] 1.3 Run OpenSpec validation（规格校验）, focused `tests/test_pr_flow_cli.py`（PR Flow 命令行测试）, and an end-to-end regression（端到端回归） covering pr-flow-init（拉取请求流程初始化） guidance, validate（校验） output, and init（初始化） local config write.
