# Extraction Method（提取方法）

生成 Guard Profile（守卫画像）草案前先调研被守卫对象。目标是把模糊要求整理成已确认的结构化事实，再由提取器生成可校验草案；初始化只发布已校验草案，不负责重新调研。

按场景读取：

- 需要采访用户：读“必用方法”和“提取顺序”。
- 需要运行提取器：读“从调研记录生成草案”。
- 需要初始化落地：读“草案到初始化”。
- 需要落地计划：读“实施计划输出”。

## 必用方法

调研阶段必须使用 `$grill-with-docs`（带文档拷问方法）的工作方式：

- 一次只问一个关键问题，并给出推荐答案。
- 如果问题能通过读取现有代码、CONTEXT.md（上下文文档）、docs/adr（架构决策记录）或已有配置回答，先查证再提问。
- 遇到模糊词时，立刻收敛成规范术语；如果现有文档里有冲突，先指出冲突并要求确认。
- 用具体场景压测边界，例如并发任务、缺失产物、手动覆盖、状态歧义和 Hook（钩子）绕过。
- 术语确定后，默认只记录待确认术语和建议补丁；只有用户明确授权时，才按目标仓库规则更新 CONTEXT.md（上下文文档）和 ADR（架构决策记录）。

初始化调研必须明确三件事：

1. 根据本次调用确认要生成和初始化的 Guard Profile（守卫画像），并让调用里的画像 ID 和 `profile.id` 对齐。
2. 默认启用 Guard Injection（守卫注入），让初始化后 agent（代理）可以读取 latest Guard Brief（最新守卫简报）并按 session（会话）去重注入。
3. 询问并记录是否启用 Hook（钩子）。如果确认启用，实施计划必须把 Hook（钩子）安装列为初始化后的授权步骤。

## 从调研记录生成草案

`extract_guard_model.py` 不直接采访用户。它只接收已经通过 `$grill-with-docs`（带文档拷问方法）校准过的结构化 YAML（YAML 配置格式），然后生成 Guard Profile（守卫画像）草案和 Implementation Plan（实施计划）。

这里的 Guard Profile（守卫画像）草案是初始化的输入，但不是随便找来的既有画像目录。它必须来自本轮调研确认结果，并且要先通过 `validate_guard_profile.py` 校验。

命令：

```powershell
python .agents\skills\agent-guard\scripts\extract_guard_model.py <confirmed-notes.yaml> --output <guard-profile-dir>
```

输入必须包含：

- `grill_with_docs.status: confirmed`
- `grill_with_docs.confirmed_decisions`
- `grill_with_docs.terminology`
- `grill_with_docs.boundaries`
- `grill_with_docs.scenarios`
- `grill_with_docs.exceptions`
- `grill_with_docs.documentation_changes`
- `initialization.requested_profile_ref`
- `initialization.guard_injection.enabled`
- `initialization.hook_installation.enabled`
- `profile`：`id`、`name`、`description`
- `target`：`id`、`type`、`name`、`source`、`boundary`
- `activation`
- `subject`
- `execution`
- `observation`
- `state_machine`
- `guard_points`
- `artifacts`
- `hook_bindings`
- `validation.items`

输入模板见 `assets/templates/guard-profile/confirmed-notes.yaml`。实际输入不能把必填列表留空，空列表会触发 `needs_confirmation`。

如果缺少关键字段、`grill_with_docs.status` 不是 `confirmed`，或边界要求修改被守卫对象，提取器必须输出 `needs_confirmation`，并把字段交回 `$grill-with-docs`（带文档拷问方法）继续追问。不要生成看似完整但不可验证的配置。

## 草案到初始化

初始化不解析 `confirmed-notes.yaml`，也不采访用户。初始化只接收已调研生成、已校验通过的 Guard Profile（守卫画像）草案目录，并把它发布到目标位置。

项目级初始化：

```powershell
python .agents\skills\agent-guard\scripts\init_project_guard.py --profile <guard-profile-draft-dir> --project <target-project>
```

用户级初始化：

```powershell
python .agents\skills\agent-guard\scripts\init_user_guard.py --profile <guard-profile-draft-dir> --user-guard-root <user-guard-root>
```

初始化阶段的职责边界：

- 可以复制已校验草案到目标 Guard Profile（守卫画像）目录。
- 可以生成通用 Guard Runtime（守卫运行时）骨架和初始化说明。
- 不负责调研、不改写被守卫对象。
- 如果调研已确认启用 Hook（钩子），初始化后再通过 Hook（钩子）安装入口完成安装；安装本身仍需要用户明确授权。
- 不把任意既有 Guard Profile（守卫画像）目录当作合法输入；输入应来自本流程的调研和提取步骤。
- 不新增或改写 `deny` 状态权限；`deny` 只能来自草案中的 `states[].permissions` 明确声明。

## 实施计划输出

调研完成并生成草案后必须生成 `implementation-plan.md`。它描述如何从草案进入落地，不替代 Guard Profile（守卫画像）配置，也不安装 Hook（钩子）。

实施计划必须包含：

- 初始化：说明草案来自本轮调研确认结果、已经通过校验，以及“不修改被守卫对象、不默认安装 Hook（钩子）”的约束。
- 守卫注入：说明 Guard Injection（守卫注入）默认开启，以及 agent（代理）如何读取和去重 latest Guard Brief（最新守卫简报）。
- Hook（钩子）：说明调研是否确认启用 Hook（钩子）；如果启用，列出安装入口和授权要求。
- 配置：列出 activation（激活）、subject（主体）和业务规则放置位置。
- 守卫点划分：把每个 Guard Point（守卫点）单独列出，说明检查内容和依赖产物。
- 单个守卫点单独实施计划：每个 Guard Point（守卫点）独立确认、独立启用、独立验证、可独立回滚。

## 提取顺序

按这个顺序提问和整理：

1. Target Model（目标模型）：守卫什么、边界是什么、目标来源是什么。
2. Initialization（初始化）：根据本次调用确认画像，默认启用 Guard Injection（守卫注入），并确认是否启用 Hook（钩子）。
3. Activation Model（激活模型）：什么时候显式激活、是否允许创建新实例、初始状态是什么。
4. Subject Resolver（主体解析器）：用哪些字段识别同一个 Subject（主体），缺字段或多匹配时怎么处理。
5. Execution Model（执行模型）：agent（代理）应按哪些节点推进，哪些下一步允许或禁止。
6. Observation Model（观察模型）：从哪些事件、文件、命令输出或人工确认判断进展。
7. State Machine（状态机）：把执行模型收敛成可运行的状态和转换。
8. Guard Point（守卫点）：每个转换上检查什么，失败时如何阻止状态推进。
9. Artifact（产物）：哪些产物是外部引用，哪些由守卫生成，哪些是迁移候选。
10. Hook Binding（钩子绑定）：哪些 Hook（钩子）事件用于权限评估，哪些主 agent（主代理）事件用于状态推进。
11. Validation Plan（验证计划）：先验证文件和引用，再验证运行时行为。

不要一次性迁移所有守卫点。优先选择一个低风险守卫点，先验证状态推进和产物读取，再扩展到更多状态。
