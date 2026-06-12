# Subject Resolution（主体解析）

Subject Resolver（主体解析器）由 Guard Profile（守卫画像）定义。Runtime（运行时）只提供上下文和标准事件字段，不固定任何通用 Subject Key（主体键）。

`subject-resolver.yaml` 至少包含：

- `subject.identity_fields`：组成 Subject Key（主体键）的字段。
- `subject.required_fields`：创建或匹配实例必须存在的字段。
- `subject.optional_fields`：额外隔离字段，例如 repo（仓库）、worktree（工作树）、branch（分支）、session（会话）或外部 ID。
- `subject.context_sources`：可读取的上下文来源，例如 `context` 和 `event`。
- `subject.existing_match_policy`：如何匹配已有实例。
- `subject.create_policy`：何时允许创建实例。
- `subject.ambiguous_policy`：多个实例匹配时如何处理。

规则：

- 显式激活优先匹配已有实例；没有匹配时才按 `create_policy` 创建。
- `identity_fields` 和当前存在的 `optional_fields` 共同进入 Subject Key（主体键）；字段来源必须来自 `context_sources`。
- `required_fields` 或 `identity_fields` 缺失时返回 `no_subject_match`，写审计，不创建实例。
- `existing_match_policy: exact` 表示用完整 Subject Key（主体键）匹配已有状态文件。
- 普通用户话术不能隐式创建强约束实例，除非画像明确允许。
- `target_hint` 只能作为线索，不能作为权威身份。
- `agent_id`、`session_id`、`task_id` 不能作为所有画像的强制字段；是否需要由画像决定。
- 无法解析或解析歧义时写审计，并给出修复建议。
