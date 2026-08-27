# 06 — 迁移 Skill 与 Plugin Sync

**What to build:** MySpec（自有规格）的四个 Skill（技能）和 Plugin Sync（插件同步）全部改用统一 CLI（命令行程序），使用户从任一原生 Agent（代理）入口完成原有规格流程时都不再依赖包内脚本路径或第二套安装规则。

**Blocked by:** 05 — 统一更新、安装锁和中断恢复.

**Status:** ready-for-agent

- [ ] 四个 Skill（技能）的状态、校验、预览、差异和应用操作只调用 `myspec` 业务子命令。
- [ ] Skill（技能）说明中不存在 `spec_ops.py` 相对路径、绝对安装路径或要求大模型解析脚本位置的步骤。
- [ ] 旧直接脚本入口被删除，确定性规格逻辑只保留一份实现。
- [ ] Pi、Claude、Codex 的原生 Skill（技能）调用名称和 add／review／audit 范围隔离保持不变。
- [ ] Plugin Sync（插件同步）只委托 `myspec init`、`doctor` 和 `update`，不复制 MySpec（自有规格）的路径、市场、模式或版本规则。
- [ ] 现有逐项决策、中断继续、严格校验、原子应用和错误可见性通过安装后 CLI（命令行程序）回归。
- [ ] 迁移测试证明旧来源仅禁用未删除，且三个 Agent（代理）不会重复展示同名 Skill（技能）。
