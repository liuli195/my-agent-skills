## Purpose

本 capability（能力）定义 OpenSpec baseline（基线）迁移后旧 docs 目录的清理基线：删除旧 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 目录，把仍需追溯的历史源文档纳入 OpenSpec archive（归档），并确保当前契约入口指向 `openspec/specs/**`。

## Requirements

### Requirement: 旧 docs 目录必须删除
系统 MUST 删除 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans` 和 `docs/prd` 这 5 个旧目录。

#### Scenario: cleanup implementation 完成
- **WHEN** cleanup implementation（清理实现）完成
- **THEN** `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans` 和 `docs/prd` 均不存在

### Requirement: 删除优先文件处理
系统 MUST 对 5 个旧目录内可删除文件采用 delete-first（删除优先）策略。

#### Scenario: 文件已被 baseline 吸收
- **WHEN** 旧文件的当前契约和必要事实已经进入 OpenSpec baseline（基线）
- **THEN** 系统删除该文件，而不是移动或保留

### Requirement: 不能删除的历史证据必须移出目标目录
系统 MUST 将不能直接删除、但仍有历史证据价值的文件移动到 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/`。

#### Scenario: 文件仍有历史追溯价值
- **WHEN** 旧文件包含 ADR（架构决策记录）、design（设计）或 PRD（产品需求文档）历史证据
- **THEN** 系统先将文件移动到 archive（归档）目录，再删除原 5 个旧目录

### Requirement: 不允许旧目录内保留例外文件
系统 MUST 不在 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans` 或 `docs/prd` 中保留任何例外文件。

#### Scenario: cleanup 遇到 index 或空索引文件
- **WHEN** cleanup 扫描到 5 个旧目录内的 `index.md` 或空索引文件
- **THEN** 系统删除该文件，并继续删除对应旧目录

### Requirement: 活跃引用切换
系统 MUST 将活跃上下文、规则和测试中指向 5 个旧目录的引用切换到 OpenSpec specs 或 archive 路径。

#### Scenario: 活跃文件引用旧 docs 目录
- **WHEN** `AGENTS.md`、`docs/agents/domain.md`、测试或引用文档指向 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans` 或 `docs/prd`
- **THEN** 系统更新引用，使当前契约入口指向 `openspec/specs/**`，历史证据入口指向 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/**`

### Requirement: OpenSpec 当前权威
系统 MUST 将 `openspec/specs/**` 作为 agent-guard 当前契约权威，并将 archive 中的旧文档限定为历史证据。

#### Scenario: 读者查找当前 agent-guard 契约
- **WHEN** 读者或 agent（代理）需要判断当前 agent-guard 行为
- **THEN** 系统通过活跃入口指向 OpenSpec specs，而不是旧 docs 或 archive 文档

### Requirement: 清理验证
系统 MUST 在完成 cleanup implementation 前验证 OpenSpec、目录删除结果和引用边界。

#### Scenario: cleanup verification 执行
- **WHEN** cleanup implementation 完成
- **THEN** `openspec validate --all --strict --json` 通过，5 个旧目录均不存在，并且定向扫描确认活跃引用不再指向这些旧目录
