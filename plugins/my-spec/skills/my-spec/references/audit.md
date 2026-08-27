# my-spec-audit

以当前主规格为基准，对照整个仓库审计；主规格不存在时按空规格库初始化。

1. 调用 `myspec state-init` 获取共享运行锁并记录输入与主规格指纹。
2. 运行 `git ls-files --cached --others --exclude-standard` 获取范围，排除 `myspec/specs/`、`.local/spec-work/` 和二进制文件。不要自行维护另一套忽略清单。
3. 只提取用户或外部系统可观察、可验证的行为，不把文件结构、函数、内部算法或待办写入规格。
4. 按“主规格 → 明确需求/设计/用户文档 → 端到端测试 → 实现代码 → 注释/示例/历史文档”展示证据。顺序只影响展示和建议，不能自动覆盖。
5. 来源冲突、删除和低可信候选必须组成完整 `conflicts` 清单，并在首次展示前调用 `myspec state-set-conflicts` 一次性保存；只保存数量或第一项无效。
6. 状态为 `WAITING_DECISION` 时禁止重新扫描获取下一项。调用 `myspec state-current` 一次只展示一条候选、来源证据、原因和推荐答案，通过 `myspec state-decide` 保存决定和推进游标，并用 `myspec state-status` 报告稳定的总数和剩余数；禁止批量接受。
7. 规格为空时，为确定项生成初始 Delta（增量规格）；已有规格时只生成相对变化。没有明确证据不得推断删除或改名。
8. 没有未决项后用 `myspec validate-delta` 校验 Delta（增量规格），用 `myspec apply-delta` 生成预览，用 `myspec validate-main` 校验预览，再用 `myspec diff` 展示完整差异并等待最终确认。
9. 确认后重查主规格指纹并用 `myspec apply-delta` 原子应用；最终校验失败时恢复原规格。

运行完成后不保留审计报告、忽略决定或暂缓决定。
