## Why

Comet full workflow（完整工作流）目前在 build（构建）进入 verify（验证）前已有 cross-agent-review（跨代理审查）门禁，但 design（设计）进入 build（构建）前没有规划产物审查门禁。这样会让 proposal（提案）、design（设计）、tasks（任务）存在冲突或缺口时过早进入实现。

## What Changes

- 在 Comet design（设计）阶段守卫收尾命令执行前增加 planning-review（规划审查）门禁。
- 通过已有 Agent Guard Global Command Guard（全局命令守卫点）和 artifacts.yaml（产物注册文件）校验 planning-review（规划审查）通过标记。
- 引入双轨 evidence（证据）规则：原流程没有产物时使用 Agent Guard（代理守卫）默认 evidence 目录；原流程已有产物时只登记原路径。
- 删除 Agent Guard Plugin（代理守卫插件）内置的 Comet review gate（comet 审查门禁）Guard Profile（守卫画像）模板，不再在插件中保留业务配置副本。
- 用外部用户级 Guard Profile（守卫画像）配置表达 design -> build 与 build -> verify 两个 Comet（流程）边界，测试中按需构造配置，不依赖插件模板。
- 保持 Comet（流程）、Agent Guard（代理守卫）和 planning-review（规划审查）边界分离：Agent Guard 只校验证据，不执行 planning-review。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `comet-agent-review-gate`: 增加 design（设计）进入 build（构建）前的 planning-review（规划审查）通过门禁。
- `agent-guard-core`: 移除 Agent Guard Plugin（代理守卫插件）对内置 Comet review gate（comet 审查门禁）Guard Profile（守卫画像）模板来源的认可，避免业务配置耦合进插件。
- `agent-guard-plugin-runtime`: 为 Global Command Guard（全局命令守卫点）定义 guard-defined evidence（守卫定义证据）的默认目录规则，同时保留 external artifact（外部产物）原路径登记模式。

## Impact

- 删除 Agent Guard（代理守卫）插件中的 Comet review gate（comet 审查门禁）模板和镜像模板，并更新相关包验证。
- 影响 Guard Profile（守卫画像）校验、插件包内容测试、Global Command Guard（全局命令守卫点）运行时回归测试和 evidence（证据）路径文档。
- 不改变 Comet（流程）阶段链，不新增 wrapper（包装命令），不修改 planning-review（规划审查）Skill（技能）的只读审查边界。
