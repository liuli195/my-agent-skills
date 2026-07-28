## MODIFIED Requirements

### Requirement: Comet review gate 使用用户级 Global Command Guard

系统 MUST 使用用户级 Global Command Guard（全局命令守卫点）表达 Comet verify（验证）前的 review gate（审查门禁），但 hotfix（热修复）和 tweak（小改）workflow（工作流）不需要 cross-agent-review（跨代理审查）通过标记。

#### Scenario: full workflow 继续要求 cross-agent-review

- **WHEN** Comet full（完整）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **AND** 当前 change（变更）和当前 HEAD（提交头）没有有效 cross-agent-review（跨代理审查）pass marker（通过标记）
- **THEN** Global Command Guard（全局命令守卫点）拒绝该命令

#### Scenario: hotfix workflow 不触发 cross-agent-review 门禁

- **WHEN** Comet hotfix（热修复）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **THEN** Global Command Guard（全局命令守卫点）不得因为缺少 cross-agent-review（跨代理审查）pass marker（通过标记）拒绝该命令

#### Scenario: tweak workflow 不触发 cross-agent-review 门禁

- **WHEN** Comet tweak（小改）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **THEN** Global Command Guard（全局命令守卫点）不得因为缺少 cross-agent-review（跨代理审查）pass marker（通过标记）拒绝该命令
