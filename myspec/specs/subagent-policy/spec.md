# Subagent Policy（子代理策略）

## Purpose

提供独立于旧 Pi 子代理策略的固定角色契约，在委派前验证当前宿主 Adapter（适配器），并要求主 Agent（代理）以实际结果而非完成报告验收子代理。

## Requirements

### Requirement: 独立子代理策略入口与固定角色契约

系统 MUST 通过独立的纯 Skill（技能）包提供 `subagent-policy`，固定 Explorer（调查者）、Implementer（实施者）、Reviewer（审查者）和 Architect（架构师）的职责、模型、思考强度与读写边界，并 SHALL 让主 Agent（代理）决定是否委派、何时委派以及调用几个角色。Explorer 使用 `gpt-5.6-luna` 与 `low`（低），Implementer 使用 `gpt-5.6-luna` 与 `max`（最高），Reviewer 使用 `gpt-5.6-sol` 与 `medium`（中等），Architect 使用 `gpt-5.6-sol` 与 `medium`（中）；四个角色优先使用宿主已配置的具名代理；只有 Implementer 可以在明确授权范围内写入。

#### Scenario: 当前宿主发现独立策略

- **WHEN** 当前宿主加载 `subagent-policy`
- **THEN** 宿主发现不包含脚本或 Extension（扩展）的纯 Skill（技能），并读取四个固定角色契约

#### Scenario: 主代理按需选择角色

- **WHEN** 主 Agent（代理）判断一个任务适合委派
- **THEN** 主 Agent（代理）根据任务性质选择最匹配的固定角色、模型、思考强度和读写边界；简单或无法独立拆分的任务可以不委派

#### Scenario: 架构师优先使用网页 ChatGPT

- **WHEN** 主 Agent（代理）委派 Architect（架构师）任务
- **THEN** 优先使用宿主提供的 `awehitch/SKILL.md`（技能）路径；网页 ChatGPT 不可用时回退到本地具名 Architect（架构师），具名代理不可用时再按通用代理回退规则处理，并声明回退
### Requirement: 子代理策略在委派前安全停止与结果验收

系统 MUST 让主 Agent（代理）优先使用宿主现有的具名子代理入口；宿主不支持具名代理时 SHALL 回退到通用代理，并传达同一角色契约和读写边界。每次委派提示词 MUST 写明角色、具体目标、范围与非目标、已有证据、读写边界、宿主相关资源和预期返回内容；宿主对工具、沙箱、Extension（扩展）或 Skill（技能）有不同表达时 SHALL 在提示词中说明，不要求专用 Adapter（适配器）或固定配置格式。指定模型或思考强度不可用时 SHALL 改用宿主默认的模型和思考强度承载同一角色，并声明回退；角色职责与读写边界不因回退改变。具名只读代理的实际边界被宿主或父会话覆盖时，主 Agent（代理）仍可使用该具名代理完成只读任务，但 MUST 声明“只读边界回退”，并核对没有未授权的仓库写入。主 Agent（代理）在依赖子代理结果前 MUST 验证实际文件、差异、版本管理状态和检查证据。

#### Scenario: 使用不同宿主的子代理入口

- **WHEN** 宿主提供通用调用、具名角色或其他原生子代理入口
- **THEN** 主 Agent（代理）通过该入口传达同一角色契约和任务提示词，不因宿主配置格式不同而停止委派

#### Scenario: 固定模型或思考强度不可用

- **WHEN** 宿主无法使用所选角色规定的模型或思考强度
- **THEN** 主 Agent（代理）改用宿主默认的模型和思考强度承载同一角色，四个角色的职责与读写边界不因回退改变，并在委派提示词与结果验收中显式声明回退

#### Scenario: 具名只读代理边界被覆盖

- **WHEN** 具名 Explorer（调查者）、Reviewer（审查者）或 Architect（架构师）的实际权限不是只读
- **THEN** 主 Agent（代理）保留该具名角色继续执行只读任务，明确报告“只读边界回退”，并确认没有未授权的仓库写入；该情况不改写为通用代理回退

#### Scenario: 子代理报告完成

- **WHEN** 子代理返回完成报告
- **THEN** 主 Agent（代理）把报告作为线索，验证实际结果和角色边界后再接受任务完成
### Requirement: 子代理策略按依赖与步骤组织代理指令

系统 MUST 让 `subagent-policy` 依次提供角色契约、主代理决策、四类委派提示词和结果验收，并 SHALL 让每类提示词明确该角色的任务范围、读写边界和返回证据。多个可写任务 MUST 在共享工作区串行，独立只读任务 MAY 并行。

#### Scenario: 代理加载子代理策略

- **WHEN** Agent（代理）加载 `subagent-policy`
- **THEN** 文档依次说明四个固定角色、主 Agent（代理）的按需选择原则、宿主中立的提示词要求和实际结果验收
