# 合并 Pi Development Flow（Pi 开发流程）门禁并统一交付

## Problem Statement

Pi Development Flow（Pi 开发流程）当前使用四个编号门禁：需求、实施、正式规格确认和 PR（拉取请求）交付。第三和第四个门禁属于同一条交付准备与执行链，但被拆成两个流程节点，导致流程状态、输出模板和恢复位置需要额外维护。

## Solution

保留 Requirements（需求）、Implementation（实施）和 Delivery（交付）三个阶段，将流程收敛为三个编号门禁，并保留最后的 Completion Check（完成检查）：

1. Gate 1 改名为 `Requirements Confirmation（需求确认）`，业务语义和授权边界不变。
2. Gate 2 改名为 `Implementation and Verification（实施和验证）`，业务语义和授权边界不变。
3. 将原 Gate 3 和 Gate 4 合并为 `Specification Archival and Delivery（规格存档并交付）`，在同一个 Gate 3 中完成正式规格存档、PR 交付授权和交付流程。
4. `Completion Check — 完成检查` 保持不变，作为第三个门禁之后的最终完成判定。

## User Stories

1. 作为 Development Flow（开发流程）使用者，我希望只看到三个编号门禁，以便更快判断当前处于需求、实施还是交付阶段。
2. 作为需求确认者，我希望 Gate 1 只改名称而不改变需求产物、票据和工作树确认条件。
3. 作为实施授权者，我希望 Gate 2 只改名称而不改变实施计划、验证、审查和停止条件。
4. 作为规格维护者，我希望正式 MySpec（自有规格）差异在第三个门禁中完成确认、应用和校验。
5. 作为 PR 交付授权者，我希望正式规格存档和 PR 交付动作在同一个 Gate 3 流程中连续处理，同时保留明确的交付授权。
6. 作为流程执行者，我希望恢复逻辑只需要识别三个门禁和一个完成检查，不再产生 Gate 3 与 Gate 4 之间的虚假恢复状态。
7. 作为仓库维护者，我希望现有 Completion Check（完成检查）的最终完成、清理残留和强制清理授权行为不变。

## Implementation Decisions

### Three-gate state machine（三级门禁状态机）

- 固定标题为：
  - `Gate 1 — Requirements Confirmation（需求确认）`
  - `Gate 2 — Implementation and Verification（实施和验证）`
  - `Gate 3 — Specification Archival and Delivery（规格存档并交付）`
  - `Completion Check — 完成检查`
- Gate 1 仍是需求产物发布和提交前的确认点。
- Gate 2 仍是实施授权点；实施完成、行为证据、风险匹配验证和整体审查通过后才能进入 Gate 3。
- Gate 3 接收 Gate 2 的完成结果，先按 `my-spec-add`（新增自有规格）的原始流程确认、应用并校验正式规格差异，再执行明确授权的 PR 交付动作。
- Gate 3 合并编号和流程节点，不隐式合并授权含义：`my-spec-add` 的规格确认和 PR 交付授权仍是两个有明确范围的连续确认步骤，均归属于 Gate 3。
- Gate 3 完成后进入 Completion Check；不再存在 Gate 4。

### Documentation and domain contract（文档和领域契约）

- 同步更新主 Skill（技能）入口、Requirements（需求）、Implementation（实施）、Delivery（交付）、Initialization（初始化）、Resume（恢复）和输出模板参考文档。
- 输出模板改为三个 Gate 标题和一个 Completion Check 标题；四个固定区块的名称、顺序和唯一性不变。
- 更新领域词汇表中的 Gate 3 定义，使其描述规格存档并交付，不再引用旧的 Gate 3 — Enter Delivery（进入交付）。
- 正式主规格差异由实施完成后的 `my-spec-add` 生成、确认、应用和校验；实施阶段不直接修改正式 `myspec/specs/`。
- 不修改 Pi Extension（Pi 扩展）运行时代码，也不改变 PR Flow（拉取请求流程）的底层行为。

## Testing Decisions

- 扩展现有 Development Flow（开发流程）契约检查，验证三个固定 Gate 标题、Completion Check 标题、四个固定输出区块和 Gate 1 → Gate 2 → Gate 3 → Completion Check 的状态转移。
- 验证所有阶段参考文档、初始化和恢复规则不再要求 Gate 4，并且 Gate 3 同时覆盖正式规格和 PR 交付内容。
- 验证 Gate 3 仍引用 `my-spec-add` 的原始确认，并保留独立 PR 交付授权，不把规格确认误当作交付授权。
- 通过本地 Pi Package（包）资源加载入口进行真实加载冒烟，确认新 Pi 进程可以发现技能及其全部参考文档。
- 使用 Build and Verify（构建与验证）快速入口运行相关契约检查；不执行无关的完整端到端回归。

## Out of Scope

- 不改变 Gate 1、Gate 2 的业务条件和授权边界。
- 不改变 Completion Check 的检查项目、清理残留处理或强制清理授权规则。
- 不修改 Pi Extension、PR Flow、MySpec CLI（命令行程序）或其他底层实现。
- 不执行本地安装、客户端同步、市场刷新、Release Flow（发布流程）、推送、PR 创建、合并或最终清理。
- 不在 Gate 1 或实施阶段直接修改正式主规格。

## Further Notes

该变更是流程契约的收敛：减少编号门禁数量，但不删除正式规格确认或 PR 交付授权。历史变更记录中的旧 Gate 名称保持不改；当前 Skill（技能）实现、契约测试和正式主规格在本变更交付时统一迁移。
