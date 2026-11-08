---
name: my-spec-review
description: 审查 MySpec（自有规格）规格库内部的冲突、重复和过期项。当用户要求只审查 myspec/specs/ 时使用。
---

# my-spec-review

> 随包命令约定：本文件的 `myspec <参数>` 均指本次实际加载插件的 `node <verified-plugin-root>/bin/myspec.js <参数>` 参数数组，不是PATH中的裸命令。包根从当前官方技能/安装记录核实；没有真实路径时只取得本任务同版本官方完整资源，保留目录关系，缺失即停止，不猜缓存或回退旧全局npm。一次会话固定同一实现，不改变业务目标工作树。

只审查 `myspec/specs/`，不得读取仓库其他文件。

执行前读取：

1. [公共规则](../my-spec/references/myspec-rules.md)
2. [规格审查流程](../my-spec/references/review.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作使用本次已核验插件的随包Node启动器；不得绕过启动器运行内部Python实现。

已有会话或草案不得覆盖、手动删锁。失败预览仅按统一入口的安全恢复边界，用 `myspec state-abort`（会话中止）核对精确身份、外部无活动确认及旧规格基线，先归档再解锁；未知或部分应用现场必须拒绝。恢复只读取本次状态、草案、归档及主规格，不扩展审查材料范围；导入后重新分析、逐项决定、完整预览并等待新的最终确认。
