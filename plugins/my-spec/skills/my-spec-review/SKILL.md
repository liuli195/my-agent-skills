---
name: my-spec-review
description: 审查 MySpec（自有规格）规格库内部的冲突、重复和过期项。当用户要求只审查 myspec/specs/ 时使用。
---

# my-spec-review

只审查 `myspec/specs/`，不得读取仓库其他文件。

执行前读取：

1. [公共规则](../my-spec/references/myspec-rules.md)
2. [规格审查流程](../my-spec/references/review.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作调用裸 `myspec ...` CLI（命令行程序），不得解析包内脚本路径。

已有会话或草案不得覆盖、手动删锁。失败预览仅按统一入口的安全恢复边界，用 `myspec state-abort`（会话中止）核对精确身份、外部无活动确认及旧规格基线，先归档再解锁；未知或部分应用现场必须拒绝。恢复只读取本次状态、草案、归档及主规格，不扩展审查材料范围；导入后重新分析、逐项决定、完整预览并等待新的最终确认。
