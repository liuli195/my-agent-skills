## 1. Scope Confirmation

- [x] 1.1 确认终态必须删除 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd`。
- [x] 1.2 确认 5 个旧目录内文件按“能删就删，不能删先移动归档”处理。
- [x] 1.3 确认 `docs/rules/**`、`docs/research/**` 和 runtime/plugin/skill 行为源码不纳入本次清理。

## 2. Move Historical Evidence

- [x] 2.1 创建 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/` 归档目录。
- [x] 2.2 移动 `docs/adr/0001-agent-guard-architecture.md` 到归档目录。
- [x] 2.3 移动 `docs/adr/0002-agent-guard-plugin-runtime-session-focus.md` 到归档目录。
- [x] 2.4 移动 `docs/designs/0017-agent-guard-plugin-runtime-session-focus.md` 到归档目录。
- [x] 2.5 移动 `docs/designs/0030-agent-guard-brief-injection-flow.md` 到归档目录。
- [x] 2.6 移动 `docs/prd/0017-agent-guard-plugin-runtime-session-focus-prd.md` 到归档目录。
- [x] 2.7 移动 `docs/prd/0030-agent-guard-brief-injection-flow-prd.md` 到归档目录。
- [x] 2.8 移动 `docs/prd/agent-guard-prd.md` 到归档目录。

## 3. Delete Old Directory Contents

- [x] 3.1 删除 `docs/changes/0018-split-agent-guard-skill-entrypoints.md`。
- [x] 3.2 删除 `docs/changes/0020-required-skill-load-statements.md`。
- [x] 3.3 删除 `docs/changes/0021-0029-agent-guard-plugin-runtime-session-focus.md`。
- [x] 3.4 删除 `docs/changes/0031-remove-agent-guard-hooks-entrypoint.md`。
- [x] 3.5 删除 5 个目标目录内所有 `index.md` 或空索引文件。
- [x] 3.6 删除空目录 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd`。

## 4. Update Active References

- [x] 4.1 更新 `AGENTS.md`，让当前契约入口指向 `openspec/specs/**`，并移除对 5 个旧目录的文档落盘要求。
- [x] 4.2 更新 `docs/agents/domain.md`，移除对旧 `docs/adr/**` 活跃入口的依赖。
- [x] 4.3 更新 `tests/test_agent_guard_prd_full_e2e.py` 中的旧 ADR 路径引用。
- [x] 4.4 更新 `tests/test_extract_guard_model.py` 中的旧 ADR 路径引用。
- [x] 4.5 更新 `plugins/agent-guard/skills/agent-guard-install/references/research-and-extract.md` 中的旧 ADR 路径引用。

## 5. Verification

- [x] 5.1 运行 `openspec validate --all --strict --json`。
- [x] 5.2 检查 `Test-Path docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 均为 false。
- [x] 5.3 运行定向 `rg` 检查，确认活跃引用不再指向 5 个已删除旧目录。
- [x] 5.4 运行受影响测试，至少覆盖引用变更涉及的测试文件。
- [x] 5.5 检查 `git diff -- docs AGENTS.md tests plugins openspec`，确认 diff（差异）符合本 change 范围。
