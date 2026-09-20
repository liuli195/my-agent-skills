# 01: 建立迁移安全门

**What to build:** 在不改变现有运行状态的前提下，保存 `0.2.1` 安装、本地补丁、配置和状态的可核验回滚材料，并在本仓库预置 `readonly`（只读）权限。

**Blocked by:** None (can start immediately).

**Status:** completed

- [x] 回滚材料覆盖安装包、`.orig`、配置、状态和版本信息，且恢复步骤可执行。
- [x] `0.3.2` 首次加载本仓库前已经显式设置 `readonly`。
- [x] 不修改其他工作区的权限配置。
