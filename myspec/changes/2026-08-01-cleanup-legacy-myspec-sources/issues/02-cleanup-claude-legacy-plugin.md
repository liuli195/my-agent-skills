# 02 — Clean up Claude Legacy MySpec Plugin

## Parent

GitHub issue #252

**What to build:** Make Claude initialization uninstall the exact legacy MySpec plugin after the independent plugin is verified, while preserving persistent data, the shared marketplace, and unrelated plugins.

**Blocked by:** None — can start immediately.

**Status:** implemented

- [x] Packed `myspec init --claude` uninstalls only the exact legacy plugin with persistent-data preservation.
- [x] The shared marketplace, unrelated plugins, and persistent user data remain unchanged.
- [x] An already-clean state succeeds without an uninstall call and reports an empty removal result.
- [x] A failed or incomplete detected uninstall returns nonzero and a retry can converge.
- [x] doctor（诊断）does not report a Legacy MySpec Source when only the shared marketplace remains.
- [x] Packed CLI verification covers observable plugin state, command calls, result fields, and doctor output.

## Evidence（证据）

- Red（红灯）：Build and Verify（构建与验证）的 `verify.my-spec` 失败，因为初始化仍返回 `disabledLegacyPlugins` 并保留旧插件。
- Green（绿灯）：审查修复后，同一快速验证在 `verify.my-spec` 中以 86 个通过、2 个跳过完成。
- User-entry smoke（用户入口冒烟）：打包候选与真实 Claude（代码代理）在隔离 HOME（用户目录）中运行；`init --claude` 删除了预置旧插件并保留持久数据，`doctor --claude` 只报告稳定来源。
- Review（审查）：初始 Spec（规格）审查发现清理前只检查启用状态，没有验证独立插件版本和安装内容；已修复并通过打包 CLI（命令行程序）测试。Targeted follow-up（定向复审）未发现未解决或新增问题。
- Unresolved risk（未解决风险）：无。
