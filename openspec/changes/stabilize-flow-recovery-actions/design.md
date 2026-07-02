## Context

现有 PR Flow（拉取请求流程）已经有多个局部恢复路径，例如缺 upstream（上游分支）、safe auto-push（安全自动推送）、EOF（连接提前结束）重试和 ruleset（规则集）等待。但这些路径的 reason（原因）、stop state（停止状态）和恢复动作分散在不同函数里。Release Flow（发布流程）preflight（预检）也只输出错误列表，缺少稳定的下一步出口。

## Goals / Non-Goals

**Goals:**

- 用最小共享分类表统一已知可恢复错误。
- 保证可恢复 stop state（停止状态）都有 `nextAction`（下一步动作）或 `nextCommand`（下一条命令）。
- 给 Release Flow preflight（发布预检）补有序下一步提示。
- 用仓库级测试防止同类错误再次退回普通异常。

**Non-Goals:**

- 不新增状态机。
- 不自动创建、合并 PR（拉取请求）。
- 不自动发布。
- 不新增依赖。

## Decisions

1. PR Flow（拉取请求流程）只加小型分类表。

   复用现有 `reason`（原因）和 stop state（停止状态），把 `gh`（GitHub 命令行）鉴权、瞬时查询失败、等待检查和输入错误集中映射。相比新增错误框架，这能少改文件，也更符合现有脚本结构。

2. Release Flow（发布流程）只在 preflight（预检）输出层补下一步。

   `preflight_errors`（预检错误）继续负责校验；新增轻量 helper（辅助函数）把错误翻译成有序动作。这样不改变发布执行逻辑。

3. 防回归用仓库级测试扫契约，不逐个 case（用例）堆测试。

   测试重点是“可恢复状态必须可恢复”，而不是为每个调用点复制同样断言。

## Risks / Trade-offs

- [Risk] 分类表漏掉新的可恢复 reason（原因） → 仓库级测试要求新增可恢复状态必须带恢复动作。
- [Risk] 过度把真实异常归为可恢复 → 分类只覆盖已知文本和已有流程上下文，未知失败继续保守停止。
- [Risk] 输出变长 → 只补下一步，不加说明性长文。
