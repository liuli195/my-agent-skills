# 01 — 阻止发布输入同版本漂移

**What to build:** 为 Release Flow（发布流程）增加统一的发布输入漂移检查，使 marketplace（插件市场）插件和 NPM（Node 包管理器）插件在源码或打包输入变化但版本提升遗漏时都无法通过 preflight（发布前检查）。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] 单一插件注册表声明每个插件的发布输入、版本文件和发布形态。
- [x] `release-flow` 与 `pr-flow` 的源码变化在未选择版本提升时被 preflight 拒绝。
- [x] `build-and-verify` 与 `my-spec` 的插件源码、NPM 元数据、共享管理模块和共享打包器变化在未选择版本提升时被 preflight 拒绝。
- [x] NPM 发布目标即使不在 marketplace projection（市场投影）中也会被检查。
- [x] 选中的插件如果内容变化但版本未相对发布基线提升，会被拒绝。
- [x] NPM 插件的两个插件清单和 `package.json` 版本必须保持一致并符合本次发布版本。
- [x] 无插件发布输入变化时，未选插件和投影-only（仅投影）发布仍然通过。
- [x] 回归测试通过真实 `release_flow.py preflight` 命令覆盖两种发布形态及共享 NPM 输入。
- [x] 现有 NPM 候选包完整性检查和发布行为保持不变。

## Behavior evidence

- 真实 CLI（命令行）回归覆盖市场插件漂移、未投影市场插件漂移、两个 NPM 插件漂移、共享 `management.py`、共享 `pack.py`、NPM 元数据、版本降级、预发布版本递增和投影-only 发布。
- 受影响回归测试：`87 passed`。
- Build and Verify（构建与验证）快速验证：`status: passed`。
- Code Review（代码审查）规范轴和规格轴终审：无阻断项。
- 当前源码自身修改了 `release-flow` 的发布输入，因此未提升其版本时，真实 preflight 会按预期拒绝发布。
