# 对齐 Gate 3 与 MySpec 委托

## Problem Statement

Pi Development Flow（Pi 开发流程）的 `SKILL.md`（技能入口）规定 Gate 3 — Enter Delivery（进入交付）通过 `my-spec-add`（新增自有规格）确认正式 MySpec（自有规格）差异；但 Delivery（交付）参考文档和正式规格把 Gate 3 写成正式规格处理开始前的确认，并要求 Gate 3 通过后才调用 `my-spec-add`。这使同一门禁出现两套顺序，并诱导流程在已授权应用差异后把预期的主规格变化误作例外。

## Solution

Development Flow（开发流程）在 Gate 3 委托 `my-spec-add`（新增自有规格）的既有流程：该技能生成完整预览、展示差异并等待最终确认；此最终确认即 Gate 3 的确认。该技能原子应用并校验差异成功后，Gate 3 才通过，并进入 Gate 4 — Authorize PR Delivery（授权 PR 交付）。

Development Flow（开发流程）不复制 `my-spec-add` 的指纹、预览、冲突、失败或恢复规则；该技能未完成时，流程保留产物并按该技能的恢复位置继续。实施票据只修改流程说明和检查；正式 MySpec（自有规格）差异是票据完成后由 Gate 3 应用的交付产物。

## User Stories

1. 作为交付授权者，我希望 Gate 3 展示完整正式规格差异，以便只批准实际将被应用的内容。
2. 作为流程执行者，我希望应用已批准差异后直接进入 Gate 4，以免把已授权的主规格变化误报为例外。
3. 作为维护者，我希望 Development Flow（开发流程）只委托 `my-spec-add`（新增自有规格）的既有校验与恢复流程，以免两处规则漂移。

## Implementation Decisions

- 保持四个既有门禁的编号、名称和业务含义不变。
- 实施票据不直接修改正式 MySpec（自有规格）；该差异由 Gate 3 通过 `my-spec-add`（新增自有规格）在实施票据完成后生成、确认和应用。
- Gate 3 的确认复用 `my-spec-add`（新增自有规格）展示完整预览差异后的最终确认；该确认授权原子应用与校验。
- Gate 3 仅在 `my-spec-add`（新增自有规格）成功应用并校验后通过；Gate 4 只在此后确认 PR（拉取请求）交付动作。
- Development Flow（开发流程）仅声明委托时机与门禁转移，不实现或描述 `my-spec-add` 的内部校验和恢复程序。

## Testing Decisions

- 在现有 Pi Development Flow（Pi 开发流程）契约检查中验证 Gate 3 在 `my-spec-add`（新增自有规格）完成后才转入 Gate 4，且不再要求 Gate 3 通过后才调用该技能。
- 用新的 Pi（编码代理）冒烟覆盖 Gate 3 委托、最终确认、成功应用与进入 Gate 4 的可观察路径。

## Out of Scope

- 修改 `my-spec-add`（新增自有规格）插件、CLI（命令行程序）或其校验和恢复规则。
- 新增门禁、授权范围、状态文件或例外路径。
- 执行本地安装、客户端同步、市场刷新或发布。

## Further Notes

本变更修复重新打开的 GitHub Issue（问题）#250，并复用现有单票据、单工作树路径。
