# Extraction Method（提取方法）

生成 Guard Profile（守卫画像）前先调研被守卫对象。目标是把模糊要求整理成可校验的模型，不是直接写 Hook（钩子）。

按场景读取：

- 需要采访用户：读“必用方法”和“提取顺序”。
- 需要运行提取器：读“草案生成输入”。
- 需要落地计划：读“实施计划输出”。

## 必用方法

调研阶段必须使用 `$grill-with-docs`（带文档拷问方法）的工作方式：

- 一次只问一个关键问题，并给出推荐答案。
- 如果问题能通过读取现有代码、CONTEXT.md（上下文文档）、docs/adr（架构决策记录）或已有配置回答，先查证再提问。
- 遇到模糊词时，立刻收敛成规范术语；如果现有文档里有冲突，先指出冲突并要求确认。
- 用具体场景压测边界，例如并发任务、缺失产物、手动覆盖、状态歧义和 Hook（钩子）绕过。
- 术语确定后，默认只记录待确认术语和建议补丁；只有用户明确授权时，才按目标仓库规则更新 CONTEXT.md（上下文文档）和 ADR（架构决策记录）。

## 草案生成输入

`extract_guard_model.py` 不直接采访用户。它只接收已经通过 `$grill-with-docs`（带文档拷问方法）校准过的结构化 YAML（YAML 配置格式），然后生成 Guard Profile（守卫画像）草案和 Implementation Plan（实施计划）。

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
- `profile`：`id`、`name`、`description`、`mode`
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

## 实施计划输出

调研完成后必须生成 `implementation-plan.md`。它描述如何从草案进入落地，不替代 Guard Profile（守卫画像）配置，也不安装 Hook（钩子）。

实施计划必须包含：

- 初始化：生成 Guard Runtime（守卫运行时）和 Guard Profile（守卫画像）目录的前置动作，以及“不修改被守卫对象、不默认安装 Hook（钩子）、不默认启用阻断”的约束。
- 配置：列出 activation（激活）、subject（主体）和业务规则放置位置。
- 守卫点划分：把每个 Guard Point（守卫点）单独列出，说明模式和依赖产物。
- 单个守卫点单独实施计划：每个 Guard Point（守卫点）独立确认、独立启用、独立验证、先 record/warn（记录/警告）再由用户授权 block（阻断）、可独立回滚。

## 提取顺序

按这个顺序提问和整理：

1. Target Model（目标模型）：守卫什么、边界是什么、目标来源是什么。
2. Activation Model（激活模型）：什么时候显式激活、是否允许创建新实例、初始状态是什么。
3. Subject Resolver（主体解析器）：用哪些字段识别同一个 Subject（主体），缺字段或多匹配时怎么处理。
4. Execution Model（执行模型）：agent（代理）应按哪些节点推进，哪些下一步允许或禁止。
5. Observation Model（观察模型）：从哪些事件、文件、命令输出或人工确认判断进展。
6. State Machine（状态机）：把执行模型收敛成可运行的状态和转换。
7. Guard Point（守卫点）：每个转换或入口上检查什么，失败时记录、警告还是阻断。
8. Artifact（产物）：哪些产物是外部引用，哪些由守卫生成，哪些是迁移候选。
9. Hook Binding（钩子绑定）：哪些 Hook（钩子）或人工事件触发 Runtime（运行时）。
10. Validation Plan（验证计划）：先验证文件和引用，再验证运行时行为。

不要一次性迁移所有守卫点。优先选择一个低风险守卫点，先记录或警告，稳定后再由用户显式授权阻断。
