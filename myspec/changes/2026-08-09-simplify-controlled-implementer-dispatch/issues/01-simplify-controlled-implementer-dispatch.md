# 01 — 收窄受控 Implementer 派发并强化 Gate 2 编排

**关联问题：** #306、#312

**What to build:** 将受控 Implementer（实施者）派发器收窄为只限制目标工作树的透明适配器，并把提示词构造、实施、证据检查、返工、审查和验收全部编排在现有 Development Flow（开发流程）Skill（技能）文件中。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

## Acceptance criteria

- 派发接口只接收 `prompt`（提示词）、`description`（描述）、`worktree_path`（工作树路径）和 `expected_branch`（预期分支）。
- 派发器验证目标为已登记的非主 Git worktree（Git 工作树）、匹配预期分支，并把规范路径绑定为 Implementer 的实际工作目录。
- 派发器固定启动 Implementer，原样传递提示词和描述，不再接收、读取或验证票据路径。
- 派发器不构造提示词，不判断提交、工作区、测试、审查、验收或流程状态，也不增加特殊模型、资源、恢复或超时行为。
- 现有直接 `Agent` 调用护栏继续阻断 Implementer、未知角色和恢复型可写调用绕过受控入口。
- 顶层 Skill 只承担阶段路由、门禁顺序和强上下文指针；Gate 2 规则集中到现有实施文档。
- Gate 2 明确使用 Single Writer（单写者）：主 Agent（代理）编排和检查证据，Git 可见实施修改由绑定工作树的 Implementer 完成，Reviewer（审查者）只报告。
- 实施文档按 `READY`、`RETURNED`、`REWORK_REQUIRED`、`ACCEPTED`、`BLOCKED` 组织有序步骤，每一步有可检查的完成标准。
- Development Flow 使用实施文档内的短清单构造自包含提示词；每次写入派发只有一个明确目标，票据实施目标只对应本票据。
- Implementer 返回只能进入 `RETURNED` 和证据检查；只有聚焦提交、干净工作区、限定差异、固定基线验证、真实冒烟和必要审查满足不可变票据后才能进入 `ACCEPTED`。
- 证据不足或审查阻断时，主 Agent 构造新的自包含提示词并通过同一派发器返工；主 Agent 不直接接管修改。
- 票据在 Gate 2 期间保持不可变，不写回实施证据或修订；需求冲突返回需求阶段。
- 门禁确认只请求一次并在执行及恢复期间保持有效；后续动作失败只报告准确恢复动作，恢复成功后直接进入下一门禁。
- 自动检查覆盖提示词和描述精确透传、工作树绑定、错误目标拒绝、直接调用阻断、Skill 关键状态和旧语义移除。
- 真实 Pi（编码代理）冒烟覆盖“返回但证据不足 → 全新派发返工 → 证据满足后验收”以及 Reviewer 阻断后的派发修复和定向复审。
- 真实冒烟前后主工作区无本次流程造成的 Git 可见修改。
- 固定 Git 基线 Build and Verify（构建与验证）通过且 `checked` 非空；高风险整体审查无未解决阻断项。

## TDD and verification

1. 先更新公开工具和 Skill 文本契约检查，使旧接口、直接实施许可、固定票据提示词、返回即完成和重复门禁确认语义产生预期红灯。
2. 最小修改派发接口和现有 Skill 文本，使同一检查转绿。
3. 运行受影响的 Node.js（运行环境）检查和固定基线 Build and Verify。
4. 从真实 Pi Package（包）入口运行临时主工作区与功能工作树冒烟，记录工作树、提交、工作区、验证、审查修复和主工作区无副作用证据。
5. 使用 `code-review`（代码审查）完成高风险票据审查和有边界的整体审查；本单票变更可由一次完整审查同时满足两者。

## Boundaries

- 不新增 Skill、引用文件、提示词模板、运行时状态机、证据账本、公开验证工具或依赖。
- 不修改 Pi 本体、第三方子代理、持久角色配置、Gate 3 或 PR 交付行为。
- 不进行与本次执行路径无关的全仓 Skill 文案清理。
- 不兼容旧 session 的旧派发参数。
