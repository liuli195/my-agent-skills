# Subagent Policy（子代理策略）

## Purpose

提供独立于旧 Pi 子代理策略的固定角色契约，在委派前验证当前宿主 Adapter（适配器），并要求主 Agent（代理）以实际结果而非完成报告验收子代理。

## Requirements

### Requirement: 独立子代理策略入口与固定角色契约

系统 MUST 通过独立的纯 Skill（技能）包提供 `subagent-policy`，固定 Explorer、Implementer、Reviewer 和 Architect 的角色描述、模型、思考强度、能力、提示模式及提示词，并在首次委派前根据当前宿主实际配置验证完整契约。

#### Scenario: 当前宿主发现独立策略

- **WHEN** 当前宿主从新策略 Package（包）加载 Skill（技能）资源
- **THEN** 宿主发现 `subagent-policy`，且该 Package 不加载脚本或 Extension（扩展）

#### Scenario: 固定角色契约完全匹配

- **WHEN** 当前宿主 Adapter（适配器）能够证明目标角色的全部配置与固定契约完全一致
- **THEN** 策略允许主 Agent 选择该宿主原生角色，且不临时覆盖模型、思考强度、能力或提示词
### Requirement: 子代理策略在委派前安全停止与结果验收

系统 MUST 在角色契约任一字段不匹配、无法证明或缺少已验证宿主 Adapter（适配器）时于委派前停止，并 SHALL 要求主 Agent 根据实际角色、运行元数据、文件、分支、差异及检查证据验收返回结果。

#### Scenario: 宿主策略不能证明

- **WHEN** 角色字段不匹配、无法证明或当前宿主没有已验证 Adapter
- **THEN** 策略在委派前明确停止，且不选择默认、通用、未登记或回退角色

#### Scenario: 子代理报告完成

- **WHEN** 子代理返回完成报告
- **THEN** 主 Agent 在依赖结果或宣告完成前验证实际任务证据，而不把报告本身视为完成证明
