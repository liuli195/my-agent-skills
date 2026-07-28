## Context

`pr_flow.py`（拉取请求流程脚本）已有默认 PR body template（拉取请求正文模板）配置和 `update_pr_body`（更新正文）函数，但 `complete`（收尾）创建 PR（拉取请求）时只调用 `gh pr create --fill`，没有消费模板，也没有写 closing references（关闭引用）。`tweak`（小改）有单独的正文模板，导致正文规则分叉。

本次目标是修根因：把 PR body（拉取请求正文）作为 `complete`（收尾）和 `tweak`（小改）的统一输入契约，而不是让脚本猜内容。

## Goals / Non-Goals

**Goals:**

- `complete`（收尾）和 `tweak`（小改）共用同一套正文生成、校验和写入逻辑。
- 默认模板收敛为 `Summary`、`Scope`、`Closing References` 三节，并保留完整注释指南。
- `--summary` 和 `--scope` 由主 agent（主代理）显式填写。
- `--fixes` 只从调用参数生成 `Fixes #<number>`，未提供时写 `None`。
- stop state（停止状态）继续使用 `EXCEPTION_REQUIRED`、`DISPATCH_REQUIRED` 等既有名称。

**Non-Goals:**

- 不自动从提交、分支名、issue（问题单）历史或 PR（拉取请求）状态推断正文。
- 不新增依赖。
- 不引入变量模板系统。
- 不覆盖已有人工正文。
- 不改 `hotfix`（热修复）和 `cleanup`（清理）行为。

## Decisions

### 统一 helper（辅助函数）生成正文

新增最小 helper（辅助函数）负责：

- 读取 `defaults.pr.bodyTemplatePath`（正文模板路径）和 `defaults.pr.requiredSections`（必需章节）。
- 校验模板存在且包含三节。
- 忽略 HTML comment（HTML 注释）和空白后判断正文是否为空。
- 用 `--summary`、`--scope`、`--fixes` 生成最终正文。
- 为模板错误和人工正文冲突输出明确 details（详情）：模板路径、缺失章节、PR（拉取请求）编号、冲突原因和下一步动作。

不用模板变量引擎。三节正文是固定结构，直接拼接更少代码，也更清楚。

### 参数由主 agent（主代理）提供

`complete`（收尾）和 `tweak`（小改）都新增：

- `--summary`
- `--scope`
- `--fixes`，允许重复

`tweak`（小改）保留 `--reason`，但不再用它生成 PR body（拉取请求正文）。这样两条路径完全统一正文规则。

### 校验放在远端动作前

`complete`（收尾）必须在自动推送前校验正文输入和模板。否则缺正文时可能已经推送分支。`tweak`（小改）也在进入生命周期前校验。

新建 PR（拉取请求）时，`create_pr`（创建拉取请求）必须直接使用统一生成的正文；可以继续用 `--fill`（自动填充）辅助标题，但必须用 `--body-file`（正文文件）覆盖自动正文。这样不会让 GitHub CLI（GitHub 命令行工具）的提交摘要替代三节模板。

已有 PR（拉取请求）场景在 `find_pr`（查找拉取请求）后处理，且“不覆盖”只适用于当前命令开始前已经存在的人工正文：

- 正文为空：进入 checks（检查）和 merge（合并）前写入正文。
- 正文非空：不覆盖。
- 正文非空且传入 `--fixes`：停止并提示人工补 closing references（关闭引用）。

### diagnose（诊断）只提示，不改正文

`diagnose`（诊断）读取 PR body（拉取请求正文）状态：

- 无 PR（拉取请求）时，`nextCommand`（下一步命令）给出带正文参数的完整示例。
- 已有空正文 PR（拉取请求）时，输出 `EXCEPTION_REQUIRED` 和 `reason: pr_body_required`。

## Risks / Trade-offs

- [Risk] 现有裸 `complete --project .` 命令会停止。Mitigation: 更新 `pr-flow-complete`（收尾技能）和 `diagnose`（诊断）输出，让调用方明确看到新参数。
- [Risk] 已有人工正文但缺 closing refs（关闭引用）时不能自动补。Mitigation: 最小修复优先不覆盖人工正文；提示用户手工补充。
- [Risk] 测试桩需要新增 `body`（正文）字段。Mitigation: 只在测试 helper（辅助函数）默认补非空正文，正文相关测试显式传空值。

## Migration Plan

无需数据迁移。新初始化仓库会得到三节模板；已有仓库若仍是旧五节模板或旧 `requiredSections`（必需章节），`complete`（收尾）和 `tweak`（小改）必须按模板错误停止，输出 `reason: pr_body_required`、`templatePath`（模板路径）、`missingSections`（缺失章节）和可执行修复提示。脚本不做旧模板兼容转换，避免出现两套正文规则。

## Open Questions

无。
