## 背景

`docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 中的 agent-guard 历史文档已经迁移到 OpenSpec baseline（基线）。这些目录继续存在，会让旧 PRD（产品需求文档）、旧 ADR（架构决策记录）、旧 design（设计）和旧 issue/change 记录继续进入活跃上下文。

本 cleanup change（清理变更）的最终目标是删除以下 5 个目录：

- `docs/adr`
- `docs/changes`
- `docs/designs`
- `docs/plans`
- `docs/prd`

目录内文件按 delete-first（删除优先）处理：能删就删；不能直接删、但仍有历史证据价值的，先移动到目标目录之外的 archive（归档）路径，再删除原目录。

## 变更内容

- 删除 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 这 5 个旧目录。
- 直接删除已被 OpenSpec baseline 完整吸收、且无必要保留的旧 change/issue 文档和空索引文档。
- 将不能直接删除的历史证据移动到 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/`，移动后原目录仍必须删除。
- 更新活跃上下文引用，让 `AGENTS.md`、`docs/agents/domain.md`、相关测试和引用文档不再依赖被删除目录。
- 明确 `openspec/specs/**` 是当前契约权威，archive 中的旧文档只用于历史追溯。

## 能力

**新增能力：**
- `legacy-docs-openspec-navigation`: 管理 OpenSpec baseline 迁移后旧 docs 目录的删除、必要归档、活跃引用切换和权威边界。

**修改能力：**
- 无。

## 影响

- 最终必须删除的目录：
  - `docs/adr`
  - `docs/changes`
  - `docs/designs`
  - `docs/plans`
  - `docs/prd`
- 计划直接删除的旧文档：
  - `docs/changes/0018-split-agent-guard-skill-entrypoints.md`
  - `docs/changes/0020-required-skill-load-statements.md`
  - `docs/changes/0021-0029-agent-guard-plugin-runtime-session-focus.md`
  - `docs/changes/0031-remove-agent-guard-hooks-entrypoint.md`
  - 5 个目标目录内的 `index.md` 或空索引文件。
- 计划移动到 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/` 后再删除原目录：
  - `docs/adr/0001-agent-guard-architecture.md`
  - `docs/adr/0002-agent-guard-plugin-runtime-session-focus.md`
  - `docs/designs/0017-agent-guard-plugin-runtime-session-focus.md`
  - `docs/designs/0030-agent-guard-brief-injection-flow.md`
  - `docs/prd/0017-agent-guard-plugin-runtime-session-focus-prd.md`
  - `docs/prd/0030-agent-guard-brief-injection-flow-prd.md`
  - `docs/prd/agent-guard-prd.md`
- 计划更新活跃引用：
  - `AGENTS.md`
  - `docs/agents/domain.md`
  - `tests/test_agent_guard_prd_full_e2e.py`
  - `tests/test_extract_guard_model.py`
  - `plugins/agent-guard/skills/agent-guard-install/references/research-and-extract.md`
- 不受影响：
  - `docs/rules/**`
  - `docs/research/**`
  - runtime（运行时）、plugin（插件）、skill（技能）行为源码。
