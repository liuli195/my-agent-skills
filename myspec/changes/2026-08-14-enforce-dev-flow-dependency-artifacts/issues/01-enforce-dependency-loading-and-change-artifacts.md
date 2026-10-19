# 01 — 强制依赖加载与变更产物

**What to build:** 强化 `dev-flow` 的依赖发现、阶段调用、MySpec 变更产物和两个门禁的可观察检查，确保依赖缺失或产物不完整时在正确恢复位置停止。

**Blocked by:** None

**Status:** ready-for-agent

## 验收条件

- [x] 入口保持薄路由；宿主技能清单按精确技能名解析唯一 `location`，共享但未列出的技能使用 `~/.agents/skills/<skill-name>/SKILL.md`，阶段相对文档相对 `dev-flow` 的 `SKILL.md` 目录。
- [x] 名称缺失、路径不存在、不可读、frontmatter `name` 不匹配或多个入口时立即停止，并报告缺口、失败阶段和恢复阶段。
- [x] 需求阶段依次实际调用 `subagent-policy`、Architect 使用 `codebase-design`、`grill-with-docs` 调用 `grilling` 与 `domain-modeling`、`to-spec`、`to-tickets`；Full 与 Fast 都实际使用后两者。
- [x] 实施阶段明确首次委派前的 `subagent-policy`、每票红灯到绿灯前的 `tdd`、正式验证前的 `build-and-verify` 和独立审查前的 `code-review`。
- [x] `to-spec` 写入 `myspec/changes/<change-name>/spec.md`，`to-tickets` 在同一目录写入 `issues/NN-<slug>.md`，遵循 `docs/agents/issue-tracker.md` 且不使用 `.scratch`。
- [x] 门禁一读取并核对 spec 与全部 issues 的命名、状态、顺序、阻塞、可观察范围和测试接缝；缺失、空白或不一致时停止并保留恢复位置。
- [x] 门禁二预览准备实际调用官方 `my-spec`；需要规格变更时调用 `my-spec-add`；门禁二授权后调用 `pr-flow-complete`，并在授权前重新核对已批准 change 的产物、实际差异、验证证据和正式规格预览。
- [x] 变更范围只包含 `plugins/dev-flow/skills/dev-flow/`、`tests/dev_flow.test.mjs`、本 change 的 `spec.md` 与 `issues/01-enforce-dependency-loading-and-change-artifacts.md`；不新增第三门禁或其他产物文件。

**Spec reference:** `myspec/changes/2026-08-14-enforce-dev-flow-dependency-artifacts/spec.md`
