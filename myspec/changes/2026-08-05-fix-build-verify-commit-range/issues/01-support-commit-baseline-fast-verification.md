# 01 — 支持提交基线快速验证并拒绝空检查假通过

**What to build（交付结果）：** 让维护者能够在提交后、干净或隔离的验证工作树中运行快速验证，明确使用固定验证基线选择受影响检查；没有适用检查时报告跳过而不是通过，缓存命中仍被视为有效通过。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [x] 快速验证支持显式验证基线，并只选择基线到当前提交之间受影响的检查。
- [x] 验证基线在验证工作树中固定解析；其他工作树的提交和未提交改动不影响结果。
- [x] 验证工作树分离 HEAD、基线分支被其他工作树检出时仍可验证。
- [x] 验证工作树有未提交改动、基线无效或基线与完整验证组合时明确失败。
- [x] 无变更和无匹配检查分别报告 `skipped/no_changed_files` 与 `skipped/no_matching_checks`，不得报告通过。
- [x] 至少选中一个检查时，实际执行通过或有效通过缓存命中均报告 `status: passed`，并且 `checked` 非空。
- [x] 未指定基线时，现有暂存、未暂存和未跟踪文件选择行为保持不变。
- [x] Pi Development Flow 集成验证契约要求使用固定基线，并拒绝 `checked` 为空的假通过证据。
- [x] 真实命令入口覆盖公共行为，现有进程内分支测试保留选择和状态回归；旧运行时迁移行为不作兼容扩展。

## Behavior evidence（行为证据）

- Red（红灯）：初次 Build and Verify（构建与验证）快速验证发现新增真实命令测试未登记运行时边界；补充最小入口登记后转绿。
- Green（绿灯）：`pytest tests/test_build_and_verify_plugin.py tests/test_local_plugin_build_checks.py tests/test_test_runtime_boundaries.py -q` → 269 passed；`node --test tests/pi_development_flow.test.mjs` → 12 passed。
- Smoke（冒烟）：`node plugins/build-and-verify/bin/build-and-verify.js verify --project . --base 8401d502` → `checked` 非空、`status: passed`；同一入口无基线且工作树干净时 → `status: skipped`、`reason: no_changed_files`。
- Review（审查）：Standards（规范）与 Spec（规格）双轴审查及定向复审均未发现未解决阻塞项。
- Unresolved risk（未解决风险）：全局 `build-and-verify` 启动器仍指向旧安装版本，不能识别 `--base`；未修改用户级安装，已使用当前工作树的真实 Node.js（运行时）入口完成冒烟。
