# my-spec-add

Agent（代理）根据当前请求自主选取会话、文档、代码或其他相关证据，并与当前 `myspec/specs/` 对照；不得自动扩展为全仓库审计。

1. 调用 `myspec state-init` 获取共享运行锁，记录主规格与 Agent 实际使用证据的输入指纹，状态设为 `ANALYZING`。
2. 从相关证据提取可观察、可验证的行为，按主规格分类为新增、修改、删除、明确改名、确定重复或冲突。
3. 标题和正文相同的内容不产生变更。删除、来源冲突和低可信候选必须组成完整 `conflicts` 清单。
4. 首次展示前调用 `myspec state-set-conflicts` 一次性保存完整清单；只保存数量或第一项无效。
5. 状态为 `WAITING_DECISION` 时禁止重新分析获取下一项。调用 `myspec state-current` 一次只展示一条候选全文、来源证据、不能自动决定的原因和推荐答案；只接受“接受、忽略、修改后接受、暂缓”之一，并通过 `myspec state-decide` 保存决定和推进游标。暂缓不进入预览。
6. 用 `myspec state-status` 确认没有未决项后生成 Delta（增量规格），用 `myspec validate-delta` 和 `myspec apply-delta` 校验并生成完整预览。
7. 用 `myspec validate-main` 校验预览，用 `myspec diff` 展示完整差异，状态为 `READY_TO_APPLY` 时等待最终确认。
8. 确认后重查主规格指纹并用 `myspec apply-delta` 原子应用；最终校验成功才清理工作区。失败恢复原规格并保留诊断现场。

禁止一次展示全部冲突或批量采用建议。相同输入和决定应产生相同预览；已满足的内容不应再次生成 Delta（增量规格）。
