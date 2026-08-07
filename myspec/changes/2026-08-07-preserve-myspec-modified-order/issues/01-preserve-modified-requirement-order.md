# 01 — 保持修改需求的原有顺序

**What to build（构建内容）：** 当用户通过 MySpec（自有规格）修改同一 capability（能力）中的 Requirement（需求）时，预览、差异和正式应用保持原有标题顺序，只展示正文真实变化，同时保持跨能力修改和其他 Delta（增量规格）操作的既有行为。

**Blocked by（前置票据）：** None — can start immediately（无，可立即开始）。

**Status（状态）：** ready-for-agent

- [ ] 修改首部、中部或尾部 Requirement（需求）后，标题顺序保持不变。
- [ ] `myspec diff`（规格差异）不包含纯位置移动造成的 Requirement（需求）整块删除与新增。
- [ ] 跨能力 `MODIFIED`（修改）继续移动到目标能力。
- [ ] `ADDED`（新增）、`REMOVED`（删除）和 `RENAMED`（改名）行为保持不变。
- [ ] 相同输入的重复预览和应用保持稳定。
- [ ] 打包并隔离安装后的裸 `myspec` CLI（命令行程序）冒烟通过。
