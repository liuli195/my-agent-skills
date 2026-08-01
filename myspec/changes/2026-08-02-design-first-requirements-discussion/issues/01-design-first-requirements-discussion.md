# 01 — 设计优先的需求讨论

**What to build（构建内容）:** 用户发起新的 Development Flow（开发流程）需求时，流程先使用 `codebase-design`（代码架构）形成整体方案并获得方向确认，之后才使用 `grill-with-docs`（带文档拷问）和 `domain-modeling`（领域建模）讨论未决细节；既有四个 Gate（门禁）保持不变。

**Blocked by（前置项）:** None — can start immediately（无，可立即开始）。

**Status（状态）:** ready-for-agent

- [ ] `codebase-design`（代码架构）是需求阶段的首个 MUST（强制）依赖，并纳入生成规格和票据前的当次读取证据。
- [ ] 方向确认是普通讨论步骤；已确认事项不重复拷问，只有推翻整体设计的答案才回到方案确认。
- [ ] `grill-with-docs`（带文档拷问）、`domain-modeling`（领域建模）和多会话 `wayfinder`（路径规划）路线遵循该顺序，不新增状态文件或第五个 Gate（门禁）。
- [ ] 初始化检查列出准确的需求阶段技能；技能入口说明可自然匹配该流程。
- [ ] 现有 Pi（代理）本地 Package（包）加载与需求契约测试通过。
