# my-spec-review

只读取 `myspec/specs/`，不得读取仓库其他文件。该入口不与 `my-spec-audit` 的全仓库范围重叠。

1. 调用 `myspec state-init` 获取共享运行锁并记录主规格指纹。
2. 检查全局标题、正文、Scenario（场景）及能力间关系。
3. 标题和正文完全相同的确定重复可以自动合并；标题不同但语义等价、标题相同但正文不同、Scenario（场景）部分重叠都作为冲突。
4. 只有规格内部明确写明废止、停止支持、替代或旧版本失效时，才生成过期删除候选。措辞陈旧、缺少引用或疑似矛盾不是过期证据。
5. 删除、冲突和需要语义决定的格式问题必须组成完整 `conflicts` 清单，并在首次展示前调用 `myspec state-set-conflicts` 一次性保存；只保存数量或第一项无效。
6. 状态为 `WAITING_DECISION` 时禁止重新扫描获取下一项。调用 `myspec state-current` 一次只展示一条，并展示证据、原因和推荐答案；所有删除必须通过 `myspec state-decide` 逐条确认，并用 `myspec state-status` 报告稳定的总数和剩余数。
7. 只自动修复空行、层级、尾随空格、文件末尾换行和 Delta（增量规格）区块顺序。缺失 `MUST`/`SHALL`、Scenario（场景）、`WHEN` 或 `THEN` 必须逐条决定。
8. 没有未决项后用 `myspec apply-delta` 生成预览，用 `myspec validate-main` 校验预览并用 `myspec diff` 展示完整差异；等待最终确认后重查指纹并用 `myspec apply-delta` 原子应用。

最终校验失败时恢复原规格；不得扫描文档、测试或代码来补充判断。
