# 01 — 在所有开发流程入口前明确依赖与四个门禁

**Parent（父问题）：** GitHub Issue（问题）#250

**What to build（交付结果）：** 五份 Development Flow（开发流程）参考文档在正文前说明核心依赖、适用门禁、通过条件和恢复入口；缺少授权时，真实 Pi（编码代理）停止且不修改仓库。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [ ] Requirements（需求）、Implementation（实施）、Delivery（交付）、Initialization（初始化）和 Resume（恢复）在正文前都有依赖块和门禁块。
- [ ] 依赖块列出本入口核心外部 Skill（技能），并要求缺失、不可读、加载失败或被替代时停止。
- [ ] 门禁块说明检查清单、通过条件、必须单独等待的确认和失败后的恢复入口。
- [ ] 四个既有门禁的顺序和含义保持不变，不新增第五个开发门禁。
- [ ] Requirements 负责门禁 1 并停在门禁 2；Implementation 以门禁 2 进入并停在门禁 3；Delivery 负责门禁 3 和门禁 4。
- [ ] Initialization 不把初始化授权升级为开发门禁；Resume 只识别四个门禁中的首个未完成项。
- [ ] 实施授权不能追认门禁前修改，也不能授权已确认实施计划之外的修改。
- [ ] 现有契约检查覆盖全部五份参考文档及其门禁职责。
- [ ] 新 Pi 进程真实冒烟证明缺少授权时停止、报告恢复入口且 Git（版本管理）状态不变。
- [ ] Build and Verify（构建与验证）相关检查通过。
