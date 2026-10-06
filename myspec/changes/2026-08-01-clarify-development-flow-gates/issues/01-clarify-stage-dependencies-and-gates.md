# 01 — 明确主要阶段依赖与四个门禁状态

**Parent（父问题）：** GitHub Issue（问题）#250

**What to build（交付结果）：** Requirements（需求）、Implementation（实施）和 Delivery（交付）在正文前声明核心依赖及各自门禁；四个门禁能够从使用条件、上一依赖门禁、检查清单、待用户确认内容清单和下一步门禁完整追踪。Initialization（初始化）和 Resume（恢复）只在正文补充对应规则。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-human

- [x] Requirements、Implementation 和 Delivery 在正文前都有 `MUST — Dependencies（依赖）` 与 `MUST — Gate（门禁）`。
- [x] 每个依赖块列出准确 Skill（技能）、加载时机、失败行为和恢复位置。
- [x] 必需依赖缺失、不可读、加载失败或被替代时停止，不以自建入口绕过。
- [x] 每个正式门禁包含使用条件、上一依赖门禁、检查清单、待用户确认内容清单和下一步门禁。
- [x] 上一依赖门禁和下一步门禁说明状态转移条件，不只记录编号。
- [x] 门禁 1：完成 Requirements（需求）通过后，获批需求产物发布并提交，再转入门禁 2：进入 Implementation（实施）。
- [x] 门禁 2：进入 Implementation（实施）通过后开始实施；实施、验证和审查达到完成条件后转入门禁 3：进入 Delivery（交付）。
- [x] 门禁 3：进入 Delivery（交付）通过后，才能开始正式规格处理。
- [x] 门禁 4：授权 PR（拉取请求）交付只有在正式 MySpec（自有规格）差异获批、应用并校验后才能通过。
- [x] 门禁 4：授权 PR 交付没有下一正式门禁，流程最终完成仍由 PR 实际合并、目标分支同步和安全清理判定。
- [x] Initialization 和 Resume 不增加 MUST 块。
- [x] Initialization 正文说明正式初始化入口、单独授权、来源门禁和返回同一门禁重新检查。
- [x] Resume 正文说明上一已通过门禁、当前待确认门禁、下一步门禁和对应阶段依赖的恢复规则。
- [x] 不新增第五个正式门禁、权限体系或平行状态文件。
- [x] 现有契约检查覆盖三个 MUST 文档、两个正文文档和四个门禁状态转移。
- [x] 新 Pi（编码代理）进程真实冒烟证明缺少门禁 2：进入 Implementation（实施）的授权时停止、报告恢复入口且 Git（版本管理）状态不变。
- [x] Build and Verify（构建与验证）相关检查通过。

## Behavior evidence（行为证据）

- Red（红灯）：Build and Verify 首次运行时，三个新增契约检查因缺少统一依赖块、门禁块和正文恢复规则而失败；补充主 Skill（技能）的门禁名称检查后，同一入口因缺少四个正式名称继续失败。
- Green（绿灯）：同一 Build and Verify 快速入口最终通过，仓库 Python（Python 语言）检查 66 项及 Pi Development Flow、Pi Subagent Policy（Pi 子代理策略）Node.js（运行时）检查 10 项全部通过。
- User-entry smoke（用户入口冒烟）：临时 Git（版本管理）仓库中的新 Pi 进程收到“仅说继续但要求修改”后，停止在 Gate 2 — Enter Implementation（进入实施），报告下一步 Gate 3 — Enter Delivery（进入交付），`marker.txt` 未变化且 Git 状态为空。
- Review（审查）：Standards（规范）与 Spec（规格）整体审查发现的正文重复和 Gate 3 状态转换问题已修复；两项定向复核均无阻断问题。
- Unresolved risk（未解决风险）：无。
