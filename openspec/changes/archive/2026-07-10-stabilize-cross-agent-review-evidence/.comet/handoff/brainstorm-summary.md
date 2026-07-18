# Brainstorm Summary

- Change: stabilize-cross-agent-review-evidence
- Date: 2026-07-10

## 确认的技术方案

- 用户已确认采用完整方案 B：优先修复 Cross Agent Review（跨代理审查），不侵入 Comet（双星工作流）内部。
- Cross Agent Review（跨代理审查）只产出审查事实；主代理负责语义通过判断。
- Agent Guard（代理守卫）拥有通用 `record-evidence`（记录证据）入口及 Guard Profile（守卫画像）证据契约。
- Planning Review（规划审查）保持只读，主代理把五字段结果交给通用证据入口。
- 完整 `HEAD`（提交头）绑定、12 位短提交路径和 `guard-evidence/v1`（守卫证据第一版）保持不变。
- 不安装或同步用户级 Plugin（插件）或 Guard Profile（守卫画像）。

实施结构：

1. Cross Agent Review（跨代理审查）从 Git（版本控制）生成单一文件清单，按精确权威上下文、调用方带理由的 `summary_only`（仅摘要）和默认 `full_review`（完整审查）分类。
2. 两个角色通过独立并发子进程执行，父进程在每个角色返回后原子更新 `review-state.json`（审查状态文件）。
3. `retry`（重试）只运行失败或超时角色；`revalidate`（重新校验）只接受 `checkbox-only`（仅复选框）和 `mapping-fields-only`（仅映射字段），且禁止链式复用。
4. Agent Guard Runtime CLI（代理守卫运行时命令行）新增通用 `record-evidence`（记录证据），仅写 `owner: agent-guard`（代理守卫拥有）的 JSON（数据）产物。
5. 删除 Cross Agent Review（跨代理审查）`mark-pass`（标记通过），保留现有门禁路径和平面检查。

## 关键取舍与风险

- `summary_only`（仅摘要）是主要输入降噪，不是排除；未分类文件仍完整审查。
- 独立并发子进程比单一批量派发多一点调度代码，但能在一个角色超时时保存另一个结果。
- 机械复用仅覆盖两种可证明变化，宁可拒绝也不猜测语义安全。
- 通用证据入口固定注入标准字段，调用方只提供业务字段，避免不同审查流程复制证据契约。
- 放弃只做文档过滤的最小方案，因为它不能解决证据所有权和跨提交复用；放弃 `guard-evidence/v2`（守卫证据第二版）及通用策略框架，因为现有第一版格式足够且迁移成本无必要。

## 测试策略

- 单元测试先固定分类、路径范围、状态原子更新、失败角色重试和两个机械校验器的正反边界。
- Agent Guard（代理守卫）测试覆盖画像来源、产物所有权、安全路径、干净工作区、保留字段和原子写入。
- 两条发布形态端到端回归分别覆盖 Cross Agent Review（跨代理审查）与 Planning Review（规划审查）到 Global Command Guard（全局命令守卫点）放行。
- 最后运行 OpenSpec（开放规格）严格校验、定向测试、包检查和仓库 full（完整）验证。

## Spec Patch

- 已确认回写：Planning Review（规划审查）五字段对象使用 UTF-8（统一编码）、键排序、紧凑分隔符、保留非 ASCII（非英文字符）、无尾随换行的规范 JSON（数据对象）序列化；`report` 平面字段固定为 `inline:review`，`report_hash` 为 `sha256:<lowercase hex>`（安全哈希小写十六进制）格式。
- 深化设计收敛：角色原始输出直接保存在 `review-state.json`（审查状态文件），不增加另一套默认结果文件目录；debug（调试）模式仍可保留现有原始文件。
