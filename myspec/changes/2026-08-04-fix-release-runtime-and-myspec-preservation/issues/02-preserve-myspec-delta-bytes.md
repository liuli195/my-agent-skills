# 02 — 保持 Delta 应用的非目标规格字节

**关联问题：** #259

**What to build（构建内容）：** 让公开 `myspec apply-delta`（应用增量）入口在预览和最终原子应用中只写入实际变化或新增的规格文件，保留非目标文件的原始字节和行尾。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** completed

- [x] Delta 只修改一个能力时，非目标规格文件的原始字节完全不变。
- [x] 预览和最终原子应用使用相同的保持规则；目标和新增文件使用 `LF`（换行符）。
- [x] 回归案例覆盖原始 `LF` 与 `CRLF` 两种行尾，并通过主规格校验。
- [x] 目标语义变化、删除内容、应用前置失败和重复应用继续符合现有行为。
- [x] 回归检查通过 Windows（视窗操作系统）真实公开入口验证。
- [x] Build and Verify（构建与验证）快速检查通过。

## Behavior evidence（行为证据）

- 红灯依据：基线预览写入器会重新渲染所有规格；新增混合 `LF`/`CRLF` 字节保持案例在基线上失败。
- 绿灯：`python -m pytest -q -p no:cacheprovider tests/test_my_spec.py -k test_myspec_cli_preserves_untouched_lf_and_crlf_bytes_for_preview_and_apply`，1 项通过；相关 Delta 应用测试合计 7 项通过。
- 公开入口冒烟：通过 `node plugins/my-spec/bin/myspec.js` 执行预览、前置失败、最终 `apply-delta` 和重复应用，非目标文件字节保持、删除内容生效、目标文件使用 `LF`，主规格校验通过。
- 快速验证：`build-and-verify verify --project .` 实际执行 `verify.myspec`、`verify.my-spec`（95 项通过、2 项跳过）、`verify.local-build-contract`、`verify.runtime-boundaries` 和 `verify.build-and-verify`，全部通过；未运行完整模式。
