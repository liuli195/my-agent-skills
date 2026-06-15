# Research And Extract（调研和提取）

本流程把用户需求整理为已确认的结构化事实，再生成 Guard Profile（守卫画像）草案。

## 必须先调研

调研阶段必须使用 `$grill-with-docs`（带文档拷问方法）：

- 一次只问一个关键问题，并给出推荐答案。
- 能从现有代码、CONTEXT.md（上下文文档）、docs/adr（架构决策记录）或已有配置回答的问题，先查证再提问。
- 遇到模糊词时，先收敛成规范术语；文档冲突必须指出并要求确认。
- 用具体场景压测边界，例如并发任务、缺失产物、手动覆盖、状态歧义和 Hook（钩子）绕过。
- 术语确定后，默认只记录待确认术语和建议补丁；只有用户明确授权才更新目标仓库文档。

调研输出必须符合 `../agent-guard/assets/templates/guard-profile/confirmed-notes.yaml`。

## 提取命令

`extract_guard_model.py` 不采访用户，只接收已确认的 `confirmed-notes.yaml`，然后生成 Guard Profile（守卫画像）草案和 Implementation Plan（实施计划）。

```powershell
python ../agent-guard/scripts/extract_guard_model.py <confirmed-notes.yaml> --output <guard-profile-dir>
```

如果缺少关键字段、`grill_with_docs.status` 不是 `confirmed`，或边界要求修改被守卫对象，提取器必须输出 `needs_confirmation`，并交回 `$grill-with-docs` 继续追问。

## 提取顺序

1. Target Model（目标模型）：守卫什么、边界是什么、目标来源是什么。
2. Initialization（初始化意图）：本次要生成哪个画像，是否默认启用 Guard Injection（守卫注入），是否计划后续接入 Hook（钩子）。
3. Activation Model（激活模型）：什么时候显式激活、是否允许创建新实例、初始状态是什么。
4. Subject Resolver（主体解析器）：用哪些字段识别同一个 Subject（主体），缺字段或多匹配时怎么处理。
5. Execution Model（执行模型）：agent（代理）应按哪些节点推进，哪些下一步允许或禁止。
6. Observation Model（观察模型）：从哪些事件、文件、命令输出或人工确认判断进展。
7. State Machine（状态机）：把执行模型收敛成可运行状态和转换。
8. Guard Point（守卫点）：每个转换上检查什么，失败时如何阻止状态推进。
9. Artifact（产物）：哪些产物是外部引用，哪些由守卫生成，哪些是迁移候选。
10. Hook Binding（钩子绑定）：哪些 Hook（钩子）事件用于权限评估，哪些主 agent（主代理）事件用于状态推进。
11. Validation Plan（验证计划）：先验证文件和引用，再验证运行时行为。

不要一次性迁移所有守卫点。优先选择一个低风险守卫点，先验证状态推进和产物读取，再扩展到更多状态。
