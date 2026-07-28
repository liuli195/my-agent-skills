## Why

Agent Guard（代理守卫）和 PR Flow（拉取请求流程）当前均假设 Codex（编码助手）或 Claude（克劳德）的插件运行方式。Pi（编码助手）虽然可以加载技能，但没有 Agent Guard（代理守卫）的自动生命周期适配，且 PR Flow（拉取请求流程）的脚本入口依赖源码仓库路径，导致目标仓库中的调用不可靠。

## What Changes

- 为 Agent Guard（代理守卫）增加仅限 Pi（编码助手）的最小运行时适配：复用既有 Guard Profile（守卫画像）、Session Focus（会话焦点）、Router（路由器）和判定语义；不改变 Codex（编码助手）与 Claude（克劳德）的 Hook（钩子）行为。
- 使 Pi（编码助手）通过原生生命周期事件触发 Agent Guard（代理守卫）既有判定；不新增 Guard Runtime（守卫运行时）能力、项目级 Pi（编码助手）配置、全局记忆或子代理框架。
- 使 PR Flow（拉取请求流程）从已安装插件自身解析 `pr_flow.py`（PR Flow 脚本），不再要求目标仓库存在源码仓库的 `plugins/pr-flow` 路径；保持现有仓库入口、规则和验证语义。
- 修复 PR Flow（拉取请求流程）恢复命令的脚本路径生成，并补齐 Pi（编码助手）、Codex（编码助手）和 Claude（克劳德）的兼容性回归验证。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `agent-guard-plugin-runtime`: 增加 Pi（编码助手）最小自动生命周期适配，并保持现有守卫运行时与宿主行为边界。
- `pr-flow-plugin`: 支持从安装后的插件位置执行技能脚本和生成可复用的恢复命令。

## Impact

- 受影响代码：`plugins/agent-guard`（代理守卫插件）、`plugins/pr-flow`（拉取请求流程插件）及其测试。
- 依赖与边界：Pi（编码助手）适配只调用 Pi（编码助手）原生扩展生命周期和 Agent Guard（代理守卫）既有运行时；不依赖、导入、配置或修改其他插件。
- 变更保持为单一 OpenSpec（开放规格）change（变更），因为两项适配共享同一 Pi（编码助手）运行时边界和端到端验证；它们不会引入独立发布能力或目标仓库配置。
