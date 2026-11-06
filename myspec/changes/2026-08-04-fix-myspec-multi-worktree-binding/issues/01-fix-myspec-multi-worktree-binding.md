# 01 — 修复 MySpec 多工作树源码绑定

**关联问题：** #283

**What to build（构建内容）：** 让开发模式的裸 `myspec` CLI（命令行程序）在源码工作树与目标规格工作树不一致时安全阻断规格写入，并为多工作树开发者提供可验证的手工切换路径。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** completed

- [x] `doctor` 报告实际源码工作树、源码提交、目标工作树、目标提交和匹配结果。
- [x] 源码工作树与目标规格工作树不一致时，`apply-delta` 在任何预览、备份或主规格替换前返回稳定错误，且目标文件字节不变。
- [x] 通过 `myspec init --dev --source <目标工作树>` 重新绑定后，目标工作树的预览、原子应用和重复应用成功。
- [x] 回归测试通过真实裸 CLI 覆盖同一仓库的两个隔离工作树，并覆盖混合 `LF`/`CRLF` 规格库的非目标文件字节保持。
- [x] 公共 MySpec 技能文档说明绑定切换、诊断检查和开发模式串行应用限制。
- [x] 正式变更规格与实现行为一致，未扩大到自动动态绑定或并行开发运行时。

## Behavior evidence（行为证据）

- 红灯：在开发源码包无法取得全局 npm（包管理器）根目录时，新增回归断言发现 `apply-delta` 原本返回成功并生成预览。
- 绿灯：`python -m pytest -q -p no:cacheprovider tests/test_my_spec.py -k test_packed_myspec_dev_binding_blocks_cross_worktree_apply_until_switch`，1 项通过。
- 公开入口冒烟：同一测试通过已安装 MySpec 包的裸 CLI、真实 `git worktree`、手工 `init --dev --source` 切换，覆盖错绑阻断、诊断、预览、原子应用、重复应用和混合换行字节保持。
- Build and Verify（构建与验证）快速检查：`verify.local-build-contract` 67 项、`verify.my-spec` 96 项（2 项跳过）、`verify.runtime-boundaries` 11 项、`verify.build-and-verify` 215 项通过；未运行完整模式。
- 审查：规范审查和规格审查首轮发现两个问题（绑定探针失败放行、测试未使用同一 Git 工作树），已修复；定向复核结论为无需阻断。
- 额外检查：`node plugins/my-spec/bin/myspec.js validate-main myspec/specs` 通过，`git diff --check` 通过。
