# 01 — 明确主要阶段依赖与四个门禁状态

**Parent（父问题）：** GitHub Issue（问题）#250

**What to build（交付结果）：** Requirements（需求）、Implementation（实施）和 Delivery（交付）在正文前声明核心依赖及各自门禁；四个门禁能够从使用条件、上一依赖门禁、检查清单、待用户确认内容清单和下一步门禁完整追踪。Initialization（初始化）和 Resume（恢复）只在正文补充对应规则。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [ ] Requirements、Implementation 和 Delivery 在正文前都有 `MUST — Dependencies（依赖）` 与 `MUST — Gate（门禁）`。
- [ ] 每个依赖块列出准确 Skill（技能）、加载时机、失败行为和恢复位置。
- [ ] 必需依赖缺失、不可读、加载失败或被替代时停止，不以自建入口绕过。
- [ ] 每个正式门禁包含使用条件、上一依赖门禁、检查清单、待用户确认内容清单和下一步门禁。
- [ ] 上一依赖门禁和下一步门禁说明状态转移条件，不只记录编号。
- [ ] 门禁 1 完成 Requirements；获批需求产物发布并提交后转入门禁 2。
- [ ] 门禁 2 进入 Implementation；实施、验证和审查达到完成条件后转入门禁 3。
- [ ] 门禁 3 进入 Delivery；Implementation 的票据、验证和整体审查达到完成条件后，才能开始正式规格处理。
- [ ] 门禁 4 是 Delivery 内的 PR（拉取请求）交付授权门禁；正式 MySpec（自有规格）差异获批、应用并校验后才能通过。
- [ ] 门禁 4 没有下一正式门禁，流程最终完成仍由 PR 实际合并、目标分支同步和安全清理判定。
- [ ] Initialization 和 Resume 不增加 MUST 块。
- [ ] Initialization 正文说明正式初始化入口、单独授权、来源门禁和返回同一门禁重新检查。
- [ ] Resume 正文说明上一已通过门禁、当前待确认门禁、下一步门禁和对应阶段依赖的恢复规则。
- [ ] 不新增第五个正式门禁、权限体系或平行状态文件。
- [ ] 现有契约检查覆盖三个 MUST 文档、两个正文文档和四个门禁状态转移。
- [ ] 新 Pi（编码代理）进程真实冒烟证明缺少门禁 2 授权时停止、报告恢复入口且 Git（版本管理）状态不变。
- [ ] Build and Verify（构建与验证）相关检查通过。
