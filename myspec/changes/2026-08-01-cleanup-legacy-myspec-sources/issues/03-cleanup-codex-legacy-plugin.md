# 03 — Clean up Codex Legacy MySpec Plugin

## Parent

GitHub issue #252

**What to build:** Make Codex initialization remove the exact legacy MySpec plugin record and cache after the independent plugin is verified, while preserving the shared marketplace and unrelated plugins.

**Blocked by:** None — can start immediately.

**Status:** ready-for-human

- [x] Packed `myspec init --codex` removes only the exact legacy plugin through the Codex command interface.
- [x] The shared marketplace, unrelated plugins, and unrelated cache remain unchanged.
- [x] An already-clean state succeeds without a removal call and reports an empty removal result.
- [x] A failed or incomplete detected removal returns nonzero and a retry can converge.
- [x] doctor（诊断）does not report a Legacy MySpec Source when only the shared marketplace remains.
- [x] Packed CLI verification covers observable plugin state, command calls, result fields, and doctor output.

## Evidence（证据）

- Red（红灯）：Build and Verify（构建与验证）的 `verify.my-spec` 失败，因为初始化仍返回 `disabledLegacyPlugins` 并保留旧插件。
- Green（绿灯）：同一快速验证在 `verify.my-spec` 中以 89 个通过、2 个跳过完成。
- User-entry smoke（用户入口冒烟）：打包候选与真实 Codex（代码代理）在隔离 HOME（用户目录）中运行；`init --codex` 删除了预置旧插件，`doctor --codex` 只报告稳定来源。
- Review（审查）：Standards（规范）审查发现状态值不合规，已改为 `ready-for-human`；Spec（规格）审查未发现问题。Targeted follow-up（定向复审）未发现未解决或新增问题。
- Unresolved risk（未解决风险）：无。
