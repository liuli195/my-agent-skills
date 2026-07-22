## 背景

OpenSpec baseline 已建立，当前 agent-guard 契约位于 `openspec/specs/**`。旧 docs 中的 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 已经不应继续作为活跃文档入口。

本 change 的终态不是“给旧目录加说明”，而是删除这 5 个旧目录。目录里确实不能直接删除的内容，必须先移动到目录外的 archive 路径，再删除原目录。

## 目标 / 非目标

**目标：**

- 删除 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd`。
- 对目录内文件先分类：可删除的直接删除，不可删除但有历史价值的移动归档。
- 更新活跃规则、上下文、测试和引用文档，避免继续指向被删除目录。
- 让 `openspec/specs/**` 成为当前契约入口。

**非目标：**

- 不保留这 5 个目录中的任何文件作为活跃文档。
- 不新增旧目录跳转页。
- 不重写 OpenSpec baseline 主规格。
- 不修改 `docs/rules/**` 或 `docs/research/**`。
- 不改 runtime、plugin、skill 行为源码。

## 决策

1. **目录级删除是终态。**

   `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 最终都必须不存在。任何需要保留的内容必须先移出这些目录。

2. **文件处理采用 delete-first。**

   已被 OpenSpec baseline 完整吸收、且没有必要作为证据保存的文件直接删除。旧 change/issue 记录和空索引文件属于默认删除对象。

3. **历史证据移到统一 archive。**

   ADR、design 和 PRD 文档包含决策背景、方案对比、用户故事或较长实现背景，先移动到 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/`。移动后的文件只表示历史证据，不作为当前契约。

4. **活跃引用必须同步切换。**

   `AGENTS.md`、`docs/agents/domain.md`、测试和引用文档中不能继续把被删除目录作为上下文入口。当前事实引用 OpenSpec specs；历史追溯引用 archive。

5. **archive 不是当前事实。**

   Archive 中的旧 PRD/ADR/design 可用于理解来源，但不得作为需求、验收或行为判断的当前权威。

## 风险 / 取舍

- [风险] 删除 5 个目录后，旧路径引用会失效。→ 缓解：执行前扫描引用，执行时同步更新活跃引用。
- [风险] 直接删除旧 change/issue 文档会丢失部分叙述性历史。→ 缓解：这些内容已被 OpenSpec baseline 和 Git 历史覆盖，删除优先。
- [风险] 移动后的 archive 仍可能被误读为当前事实。→ 缓解：活跃入口不指向 archive 作为当前契约，只在需要历史追溯时引用。
- [风险] AGENTS 规则仍要求未来文档落到被删除目录。→ 缓解：同步更新 AGENTS 的文档落盘规则，让后续工作使用 OpenSpec change 或新的已授权位置。

## 迁移计划

1. 扫描 5 个目标目录内所有文件，按“删除 / 移动归档”分类。
2. 创建 `openspec/changes/archive/2026-06-16-baseline-agent-guard-docs-migration/source-docs/`。
3. 移动需要保留的 ADR、design 和 PRD 历史证据。
4. 删除可直接删除的旧 change/issue、plans 和索引文件。
5. 删除空的 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans`、`docs/prd` 目录。
6. 更新 `AGENTS.md`、`docs/agents/domain.md`、相关测试和引用文档。
7. 运行 OpenSpec strict validate（严格校验）、引用扫描和对应测试。

## 开放问题

无。
