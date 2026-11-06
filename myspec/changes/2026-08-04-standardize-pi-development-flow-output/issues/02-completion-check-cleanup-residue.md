# 02 — 增加完成检查与清理残留确认

**What to build（交付结果）：** 在 Gate 4 — Authorize PR Delivery（授权 PR 交付）之后增加 Completion Check（完成检查），准确区分最终完成和清理未完成；发现实体工作树残留时报告并请求明确的强制清理授权。

**Blocked by（阻塞项）：** 01 — 固定 Development Flow 输出模板

**Status（状态）：** ready-for-agent

- [x] Completion Check 在 Gate 4 后执行，但不新增第五个正式授权门禁。
- [x] 只有验收、验证、正式规格、PR 合并、目标分支同步和安全清理均完成时，才报告 `最终完成`。
- [x] Git 工作树登记和分支已清理、但实体目录仍存在时，报告 `未完成`、精确路径和原因。
- [x] 仅在检测到残留时询问是否授权强制清理。
- [x] 默认不执行强制删除；用户拒绝时保留残留并报告恢复位置。
- [x] 用户授权清理后重新执行 Completion Check。
- [x] 未请求的本地安装、客户端同步、市场刷新和发布不阻塞完成结论。
- [x] 契约检查或真实入口冒烟覆盖最终完成、残留未完成和授权后重新检查路径。

## Behavior evidence（行为证据）

- Red（红灯）：Completion Check 契约测试在完成检查段落和 Gate 4 下一步关系尚不存在时失败。
- Green（绿灯）：`node --test tests/pi_development_flow.test.mjs` 通过，覆盖最终完成条件、残留路径/原因/证据、拒绝授权和授权后重检规则。
- Smoke（冒烟）：本地 Pi Package 资源加载入口和 Build and Verify（构建与验证）快速验证通过。
- Review（审查）：整体审查和定向复核发现的摘要字段、第五门禁表述、术语和残留证据问题均已修复。
- Unresolved risk（未解决风险）：实际强制清理仍需独立、明确授权的清理动作；本变更不自动执行。
