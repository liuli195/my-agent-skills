# 01 — 保持修改需求的原有顺序

**What to build（构建内容）：** 当用户通过 MySpec（自有规格）修改同一 capability（能力）中的 Requirement（需求）时，预览、差异和正式应用保持原有标题顺序，只展示正文真实变化，同时保持跨能力修改和其他 Delta（增量规格）操作的既有行为。

**Blocked by（前置票据）：** None — can start immediately（无，可立即开始）。

**Status（状态）：** ready-for-agent

- [x] 修改首部、中部或尾部 Requirement（需求）后，标题顺序保持不变。
- [x] `myspec diff`（规格差异）不包含纯位置移动造成的 Requirement（需求）整块删除与新增。
- [x] 跨能力 `MODIFIED`（修改）继续移动到目标能力。
- [x] `ADDED`（新增）、`REMOVED`（删除）和 `RENAMED`（改名）行为保持不变。
- [x] 相同输入的重复预览和应用保持稳定。
- [x] 打包并隔离安装后的裸 `myspec` CLI（命令行程序）冒烟通过。

## Behavior Evidence（行为证据）

- Red（红灯）：打包 CLI（命令行程序）测试得到 `['中部', '尾部', '首部']`，准确复现首部修改被移到末尾。
- Green（绿灯）：同一测试通过，并覆盖首部、中部、尾部、正文变化、差异、正式应用、重复执行及跨能力移动。
- User-entry smoke（用户入口冒烟）：隔离安装后的裸 `myspec` 完成预览、差异和正式应用，结果通过。
- Review（审查）：Standards（规范）与 Spec（规格）初审阻断均已修复；定向复审无阻断项。
- Unresolved risk（未解决风险）：无。
