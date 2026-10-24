# 强制开发流程依赖加载与变更产物

## Problem Statement

Development Flow（开发流程）虽然列出了阶段依赖，但 Agent（代理）可能无法自然发现只能由用户调用的 Skill（技能），也可能只记录技能名称而未实际加载。需求阶段还没有把 `to-spec`（转为规格）和 `to-tickets`（转为票据）的输出明确保存到 `myspec/changes/`，门禁因此无法证明批准的规格和票据真实存在。

## Solution

本变更的可观察契约是：为 Development Flow 增加统一、可移植的技能入口解析规则；在每个阶段的 MUST（必须）块和实际步骤中声明依赖、调用时机与失败停止位置。需求阶段把规格和逐票文件保存到同一 change（变更）目录，门禁一和门禁二读取并核对这些文件后才允许继续。

## User Stories

1. 作为开发流程使用者，我希望 Agent 能从确定入口找到每项阶段依赖，以免流程静默漏掉技能。
2. 作为开发流程使用者，我希望每项技能在对应步骤被实际调用，而不是只出现在依赖清单中。
3. 作为开发流程使用者，我希望技能缺失、不可读、名称错误或入口不唯一时流程停止并报告恢复位置。
4. 作为需求确认者，我希望 `to-spec` 把规格保存到当前 change 目录，以便审阅稳定的需求依据。
5. 作为需求确认者，我希望 `to-tickets` 把每张纵向票据分别保存到同一 change 目录，以便核对顺序和阻塞关系。
6. 作为实施授权者，我希望门禁一检查规格和票据真实存在且内容一致，再允许开始开发。
7. 作为交付授权者，我希望门禁二重新核对已批准文档、实际差异、验证证据和正式规格预览，再允许应用规格和交付。

## Implementation Decisions

- `dev-flow` 入口保持薄路由，并统一规定依赖入口解析：先从宿主技能清单按精确名称解析唯一 `location`；共享但未列出的技能从 `~/.agents/skills/<skill-name>/SKILL.md` 读取；阶段相对文档相对当前 `dev-flow` 的 `SKILL.md` 目录解析。
- 名称缺失、路径不存在、不可读、frontmatter `name` 不匹配或入口不唯一时立即停止，报告失败依赖、阶段和恢复位置，不自行替代。
- 需求阶段依次调用 `subagent-policy`、由 Architect 使用的 `codebase-design`、`grill-with-docs` 及其 `grilling` 与 `domain-modeling`、`to-spec`、`to-tickets`；Fast 与 Full 都调用后两项。
- 实施阶段在首次委派前调用 `subagent-policy`，每票红灯到绿灯前调用 `tdd`，正式验证前调用 `build-and-verify`，独立审查前调用 `code-review`。
- 交付阶段调用官方 `my-spec` 路由；需要规格变更时调用 `my-spec-add` 准备预览并在门禁二授权后应用；随后调用 `pr-flow-complete`。
- `to-spec` 写入 `myspec/changes/<change-name>/spec.md`；`to-tickets` 按依赖顺序分别写入同一目录的 `issues/NN-<slug>.md`，不使用 `.scratch`。
- 门禁一读取并核对规格和全部票据；门禁二重新读取这些文档并与实际差异、验证证据及正式规格预览核对。
- 保持两个正式确认，不增加新门禁或额外状态文档。

## Testing Decisions

- 通过现有 `tests/dev_flow.test.mjs` 和真实 Pi Package（包）资源加载入口检查 `dev-flow` 及三个阶段文档。
- 检查统一入口解析与失败停止规则、全部依赖名称、每项依赖的调用时机、change 产物路径和两个门禁的文件核对要求。
- 使用 `node --test tests/dev_flow.test.mjs` 作为红灯到绿灯检查。
- 使用固定基线的 Build and Verify（构建与验证）作为正式验证入口。

## Out of Scope

- 不复制或修改用户级共享技能。
- 不修改技能安装状态或宿主配置。
- 不新增第三个正式门禁。
- 不新增 `verification.md`、`delivery.md` 或 `gate-checks.md`。
- 不改变现有 PR Flow（拉取请求流程）清理语义。

## Further Notes

本变更使用 Full（完整）Flow Level（流程等级），因为它修复 Development Flow 自身的阶段依赖、需求产物和门禁行为。该范围构成一个可独立观察的纵向票据。
