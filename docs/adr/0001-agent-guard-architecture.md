# 0001 Agent Guard Architecture

状态：草案

## 决策

`agent-guard` 作为用户级 Skill 维护生成和升级能力。生成后的项目级 Guard Runtime 和 Guard Profile 必须可以独立运行，并且不得修改被守卫对象。

## 原因

守卫逻辑需要和目标 Skill、流程或任务说明解耦，避免目标对象更新时覆盖守卫能力。

## 后果

- 业务规则写入 Guard Profile。
- Hook 只捕获和标准化事件。
- Runtime 只执行通用机制。
- 阻断必须来自明确 Guard Instance。
