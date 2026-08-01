# 明确 Pi Development Flow（Pi 开发流程）阶段依赖与门禁

## Problem Statement

Development Flow（开发流程）已经定义四个门禁等待点，但阶段参考文档没有在执行入口完整声明本阶段依赖和门禁状态。执行者可能进入正文后才发现约束，遗漏必须加载的 Skill（技能），混淆门禁的使用时机、上一依赖门禁和下一步门禁，或者用后续授权追认此前修改。

## Solution

在 Requirements（需求）、Implementation（实施）和 Delivery（交付）参考文档开头分别增加 `MUST — Dependencies（依赖）` 与 `MUST — Gate（门禁）`。依赖块声明准确 Skill、加载时机、失败行为和恢复位置；每个门禁声明使用条件、上一依赖门禁、检查清单、待用户确认内容清单和下一步门禁。

Requirements 通过门禁 1 完成；Implementation 通过门禁 2 进入并通过门禁 3 完成；Delivery 通过门禁 4 进入。Initialization（初始化）和 Resume（恢复）暂不增加 MUST（必须）块，只在正文补充依赖、授权、门禁返回和恢复规则。

## User Stories

1. 作为 Development Flow 使用者，我希望进入主要阶段前看到核心依赖，以便缺少准确 Skill 时立即停止。
2. 作为 Development Flow 使用者，我希望每个门禁说明使用条件，以便只在正确的阶段位置等待确认。
3. 作为 Development Flow 使用者，我希望每个门禁说明上一依赖门禁和下一步门禁，以便追踪完整门禁状态。
4. 作为 Development Flow 使用者，我希望每个门禁列出检查清单，以便确认进入或完成阶段所需证据。
5. 作为 Development Flow 使用者，我希望每个门禁列出必须向用户展示的待确认内容，以免用模糊问题获得授权。
6. 作为需求确认者，我希望需求、测试接缝和纵向票据获批并发布后，Requirements 阶段才完成。
7. 作为实施授权者，我希望门禁 1 通过并展示完整实施计划后，门禁 2 才允许进入 Implementation。
8. 作为规格确认者，我希望实施、验证和审查完成，并批准正式 MySpec（自有规格）差异后，门禁 3 才允许完成 Implementation。
9. 作为交付授权者，我希望门禁 3 通过并展示完整交付内容后，门禁 4 才允许进入 Delivery。
10. 作为初始化使用者，我希望初始化授权不会被记作第五个开发门禁，也不会代替原门禁。
11. 作为恢复流程使用者，我希望 Resume 根据已有证据识别上一已通过门禁、当前待确认门禁和下一步门禁。
12. 作为维护者，我希望契约检查能发现依赖块、门禁字段、阶段归属或状态转移缺失。
13. 作为维护者，我希望真实 Pi（编码代理）证明实施授权缺失时流程停止且仓库保持不变。

## Implementation Decisions

### 统一 MUST（必须）块

- Requirements、Implementation 和 Delivery 在正文前统一使用 `MUST — Dependencies（依赖）` 与 `MUST — Gate（门禁）`。
- Initialization 和 Resume 暂不增加 MUST 块，相关规则补充到现有正文。
- 不新增第五个正式门禁，也不建设新的权限体系或独立状态文件。

### 依赖规则

- Requirements 的核心依赖包括 `grill-with-docs`（带文档拷问）、`domain-modeling`（领域建模）、`to-spec`（生成规格）和 `to-tickets`（拆分票据）；`wayfinder`（路径规划）仅在跨会话决策需要时加载。
- Implementation 的核心依赖包括适用于功能、缺陷和集成行为的 `tdd`（测试驱动开发）、验证使用的 `build-and-verify`（构建与验证）及审查使用的 `code-review`（代码审查）；`pi-subagent-policy`（Pi 子代理策略）仅在决定委派时加载。
- Delivery 根据风险和变更类型加载 `my-spec-add`（新增自有规格）、`pr-flow-complete`（完整拉取请求流程）或 `pr-flow-tweak`（小改流程）；发生冲突时加载 `resolving-merge-conflicts`（解决合并冲突）。
- 每个依赖块声明加载时机。必需依赖缺失、不可读、加载失败或被替代时停止，并报告当前产物和恢复位置。
- 不得用自建入口或普通 Git（版本管理）命令绕过正式 Skill。

### 门禁统一字段

每个正式门禁必须声明：

1. `Usage Condition（使用条件）`；
2. `Previous Gate（上一依赖门禁）`；
3. `Checks（检查清单）`；
4. `Confirmation Output（待用户确认内容清单）`；
5. `Next Gate（下一步门禁）`。

上一依赖门禁和下一步门禁同时说明状态转移所需证据，不能只写门禁编号。

### 四个门禁状态

- 门禁 1 是 Requirements 的完成门禁。它没有上一正式门禁；用户批准需求产物，并且获批产物已经发布、提交且工作树干净后，才能转入门禁 2。
- 门禁 2 是 Implementation 的进入门禁。它依赖门禁 1；通过只表示允许开始实施。只有票据、验证和审查达到完成条件后，才能进入门禁 3。
- 门禁 3 是 Implementation 的完成门禁。它依赖门禁 2；用户批准完整 MySpec 差异，并且差异成功应用和校验后，才能转入门禁 4。
- 门禁 4 是 Delivery 的进入门禁。它依赖门禁 3；通过后进入交付，没有下一正式门禁。Development Flow 最终完成仍要求 PR（拉取请求）实际合并、目标分支同步和安全清理完成。

### Initialization（初始化）与 Resume（恢复）

- Initialization 正文说明进入条件、对应正式初始化入口、初始化计划确认、来源门禁和返回同一门禁重新检查的规则。
- 初始化授权不是第五个正式门禁，不能代替需求发布、实施、正式规格或交付授权。
- Resume 正文说明如何从规格、票据、行为证据、Git、工作树和 PR 状态识别上一已通过门禁、当前待确认门禁及下一步门禁。
- Resume 在继续前加载当前门禁对应阶段文档及其依赖，不从“继续”“恢复”等表达推断授权，也不保存平行流程状态。

## Testing Decisions

- 扩展现有 Pi Development Flow 契约检查，验证 Requirements、Implementation 和 Delivery 在正文前包含两个统一 MUST 块。
- 契约检查验证每个正式门禁包含使用条件、上一依赖门禁、检查清单、待用户确认内容清单和下一步门禁。
- 契约检查验证门禁 1 至门禁 4 的阶段归属、顺序和状态转移条件。
- 契约检查验证 Initialization 和 Resume 没有新增 MUST 块，但正文包含对应依赖、授权、返回和恢复规则。
- 最高公开测试接缝是在临时 Git（版本管理）仓库启动新的 Pi 进程，加载本地 Development Flow 包，并在缺少门禁 2 实施授权时请求修改。
- 真实冒烟必须证明流程停止、报告从门禁 2 恢复，并且 Git 状态保持不变。
- 所有正式检查通过 Build and Verify 入口运行。

## Out of Scope

- 不新增第五个正式门禁。
- 不建设新的授权范围、权限体系或门禁状态存储。
- 不给 Initialization 或 Resume 增加 MUST 块。
- 不修改插件程序、Pi 本体或用户级 Skill。
- 不修改用户或机器配置、安装状态及外部客户端。
- 不改变四个门禁原有顺序和业务含义。

## Further Notes

本变更解决 GitHub Issue（问题）#250。变更属于 Standard（标准）Flow Level（流程等级）：它修复 Development Flow 的可观察执行规则，但实现只涉及 Skill 文本、契约检查和只读真实冒烟。
