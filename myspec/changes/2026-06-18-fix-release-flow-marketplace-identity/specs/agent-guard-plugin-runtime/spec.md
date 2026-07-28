## ADDED Requirements

### Requirement: Installer 使用共享 marketplace identity
Agent Guard installer（安装器）MUST 使用 release-flow 共享 marketplace identity（市场身份）生成和验证 marketplace catalog（市场目录），不得把正式 marketplace 名称只硬编码在 installer 内部。

#### Scenario: 默认 catalog root 读取 identity
- **WHEN** installer 生成 Codex 或 Claude marketplace catalog
- **THEN** Codex catalog name 和 display name MUST 来自共享 marketplace identity
- **THEN** Claude catalog name 和 owner name MUST 来自共享 marketplace identity

#### Scenario: 验证拒绝 identity 不一致
- **WHEN** installer 验证 marketplace catalog
- **THEN** 它 MUST 拒绝和共享 marketplace identity 不一致的 catalog name、display name 或 owner name
- **THEN** 错误输出 MUST 指出实际值和期望值

### Requirement: Source repo 与 repo scope marketplace 边界
系统 MUST 区分本仓库 source branch（源分支）的 marketplace 文件边界和 installer 的 repo scope（仓库作用域）安装行为。

#### Scenario: 本仓库 main 不需要 Codex repo marketplace
- **WHEN** Agent Guard Plugin 在本仓库 source branch 中开发
- **THEN** installer package verification（包验证）MUST NOT 要求 `.agents/plugins/marketplace.json` 作为持久源文件存在
- **THEN** Codex repo-local marketplace 缺失 MUST NOT 被视为插件包不完整

#### Scenario: 目标项目 repo scope 仍可显式写入
- **WHEN** 用户以 repo scope 对目标项目运行授权安装
- **THEN** installer MAY 写入用户显式传入的 Codex repo marketplace 路径
- **THEN** 该行为 MUST NOT 重新要求本仓库 main 分支保存 Codex repo-local marketplace 文件
