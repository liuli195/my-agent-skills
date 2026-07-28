# My Spec

## Purpose

本 capability（能力）定义 OpenSpec（开放规格）在 Pi、Claude 和 Codex 中的可发现入口、范围隔离、确认门禁与确定性操作行为。

## Requirements

### Requirement: Pi 规格命令按空闲状态路由

系统 MUST 提供 `/my-spec`、`/my-spec-add`、`/my-spec-review` 和 `/my-spec-audit`；代理忙碌时必须警告且不发送请求，空闲时必须路由到对应 Skill（技能）。

#### Scenario: 用户调用规格命令

- **WHEN** 用户在 Pi（编码代理）中调用任一规格命令
- **THEN** 系统按代理是否空闲执行警告或发送对应 Skill（技能）请求
### Requirement: 规格入口保持范围隔离

系统 MUST 让 add 入口只读取用户指定文档、review 入口只读取 `openspec/specs/`，并让 audit 入口只读取 Git（版本管理）可见文件且排除主规格、`.local/spec-work/` 和二进制文件。

#### Scenario: 用户选择规格入口

- **WHEN** 用户选择 add、review 或 audit 入口
- **THEN** 系统只扫描该入口允许的材料范围
### Requirement: 规格变更须经逐项决策和最终确认

系统 MUST 对冲突、删除和低可信候选逐项展示，在最终确认前不得修改主规格，并在应用后校验失败时恢复原规格。

#### Scenario: 规格流程产生待决候选

- **WHEN** 审计或审查产生冲突、删除或低可信候选
- **THEN** 系统一次展示一项，并在全部待决项处理后展示完整差异、等待最终确认再应用
### Requirement: OpenSpec 操作错误可见且重复执行稳定

系统 MUST 对无效主规格或 Delta（增量规格）返回非零结果和可识别错误，并确保相同输入的重复预览或应用不产生额外变化。

#### Scenario: 用户提交无效规格

- **WHEN** 主规格或 Delta（增量规格）不符合结构规则
- **THEN** 系统返回非零结果和可识别错误

#### Scenario: 用户重复执行相同变更

- **WHEN** 用户对相同基线重复预览或应用同一 Delta（增量规格）
- **THEN** 系统保持结果不变
### Requirement: 规格插件在三类宿主中可发现

系统 MUST 让 `my-spec` 同时可被 Pi、Claude 和 Codex 发现，并公开四个规格 Skill（技能）。

#### Scenario: 宿主加载本地插件市场

- **WHEN** Pi、Claude 或 Codex 加载本地插件市场
- **THEN** 市场中出现 `my-spec`，且四个规格 Skill（技能）均可发现
### Requirement: 规格运行文件集中在本地目录

系统 MUST 将 my-spec 的共享锁、当前命令状态、输入、主规格指纹、决定、Delta（增量规格）、预览和恢复材料保存在 `.local/spec-work/`，不得在仓库根目录创建 `.spec-work/`。

#### Scenario: 规格入口创建运行文件

- **WHEN** 任一 my-spec 入口开始处理规格任务
- **THEN** 所有临时运行文件均位于 `.local/spec-work/`
