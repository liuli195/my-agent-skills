# 02 — 让 Build and Verify 使用开发实现身份管理验证缓存

## Parent（父问题）

GitHub Issue（问题）#296

**What to build（构建内容）：** 让 Build and Verify（构建与验证）通过自身公开入口采用已经由 MySpec（自有规格）证明可用的共享身份接缝，并把开发实现身份纳入验证缓存判断。完成后，只安装和运行 Build and Verify 就能独立证明正确行为。

**Blocked by（前置项）：** 01 — 让 MySpec 使用主干实现安全操作任意目标工作树

**Status（状态）：** ready-for-agent

- [ ] `build-and-verify doctor` 在开发模式报告只由 Build and Verify Tool Implementation Closure（工具实现闭包）决定、可复现的身份。
- [ ] 只修改 Build and Verify 或共享生命周期实现会改变其身份；只修改 MySpec、工具链记录、规格、测试或普通配置不会改变其工具身份。
- [ ] fast verify（快速验证）和 full verify（完整验证）写入的缓存包含当前发布版本或开发实现身份；旧缓存缺少该身份时自动失效而无需人工删除。
- [ ] 开发实现变化会使已有通过缓存失效并重新运行检查；实现未变且其他缓存输入未变时仍可复用缓存。
- [ ] `.build-and-verify/config.json` 不属于工具身份，但配置变化仍通过现有配置摘要使对应缓存失效。
- [ ] 发布模式继续使用固定包版本；build（构建检查）不使用验证缓存的现有行为保持不变。
- [ ] 受控打包并安装后，通过公开 `doctor` 和连续 `verify` 运行覆盖缓存命中、实现变化失效、无关变化保持和配置变化失效。
