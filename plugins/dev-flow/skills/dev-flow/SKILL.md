---
name: dev-flow
description: 在同一个 Git（版本管理）工作树和非 main（主干）功能分支中编排一项开发变更；当变更必须依次经过需求、串行实施、验证、审查和 PR（拉取请求）交付时使用。
---

# 开发流程

这是纯 Skill（技能）路由，只提供入口和阶段顺序；阶段规则以对应参考文档为准。

## MUST — 必须依赖

- 按阶段加载并实际使用对应参考文档：需求使用 [requirements.md](references/requirements.md)，实施与验证使用 [implementation.md](references/implementation.md)，规格与交付使用 [delivery.md](references/delivery.md)。
- 依赖发现统一使用宿主技能清单，按精确技能名解析唯一 `location`；共享但未列出的技能读取 `~/.agents/skills/<skill-name>/SKILL.md`，并对该入口执行同样校验。
- 阶段内相对文档相对当前 `dev-flow` SKILL.md 目录解析，不根据调用目录或猜测的安装位置改写路径。
- 名称缺失、路径不存在、不可读、frontmatter `name` 不匹配或多个入口时立即停止，报告缺口、失败阶段和恢复阶段，并保留该恢复位置。

## 流程编排

1. 只读核对入口前提，确认仓库、工作树、分支和固定基线具备可复核证据。
2. 按顺序阅读并执行[需求](references/requirements.md)，准备`门禁一——开始开发`。
3. 取得门禁一对当前动作的明确授权后，阅读并执行[实施与验证](references/implementation.md)。
4. 实施、验证和限定审查完成后，阅读并执行[规格与交付](references/delivery.md)，准备`门禁二——规格与交付`。
5. 全流程只有两个正式确认；完整展示当前门禁内容后，取得用户对当前门禁动作的明确授权；语义不明确时停留澄清。每次确认在对应动作及失败恢复期间持续有效，需求或测试接缝改变时返回需求路由。
6. 每次输出包含“核心摘要”和“确认后进入的下一步”两个区块；完成检查不是第三个授权门禁。
