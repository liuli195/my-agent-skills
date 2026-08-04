# 01 — 合并三四门禁并更新流程契约

**What to build（交付结果）：** 将 Pi Development Flow（Pi 开发流程）从四个编号门禁收敛为三个编号门禁和一个 Completion Check（完成检查），使用户从 Pi Skill（技能）入口看到统一的新名称、状态转移和交付路径。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [x] Gate 1 使用 `Requirements Confirmation（需求确认）`，且需求检查、发布条件和下一步语义保持不变。
- [x] Gate 2 使用 `Implementation and Verification（实施和验证）`，且实施授权、验证、审查和停止条件保持不变。
- [x] 原 Gate 3 和 Gate 4 合并为 `Specification Archival and Delivery（规格存档并交付）`，不再暴露 Gate 4。
- [x] 合并后的 Gate 3 在一次输出中覆盖正式规格差异和 PR 交付动作；一次确认同时授权应用、校验和交付，不再追加确认。
- [x] Completion Check 保持原有行为，并改为跟随 Gate 3。
- [x] 输出模板、阶段参考文档、初始化、恢复、领域词汇表和契约测试全部使用三个 Gate 的新契约。
- [x] 本地 Pi Package 资源加载入口和 Build and Verify（构建与验证）快速检查证明新 Skill 可发现、引用完整且契约检查通过。

## Behavior evidence（行为证据）

- Red（红灯）：契约检查在旧四门禁标题仍存在或新三门禁状态转移尚不存在时失败；测试曾按预期失败 3 项。
- Green（绿灯）：`node --test tests/pi_development_flow.test.mjs` 通过，11 项测试全部通过，覆盖新标题、状态转移、输出模板、Gate 3 一次确认自动应用和交付、Completion Check。
- Smoke（冒烟）：本地 Pi Package 资源加载入口发现 `pi-development-flow` Skill 及其全部参考文档；Build and Verify（构建与验证）快速验证通过，67 项契约检查和 11 项运行边界检查通过。
- Review（审查）：以 `4017eef7` 为固定点完成 Standards（规范）与 Spec（规格）审查；发现的 Gate 2/Gate 3 状态语义问题已在 `121f6ac1` 修复，用户指出重复确认后已在 `3f919550` 和 `d3ea3f89` 统一为一次确认自动执行，并完成验证，无阻断项。
- Unresolved risk（未解决风险）：正式主规格已应用；交付仍需在 Gate 3 的同一次确认后自动执行。
