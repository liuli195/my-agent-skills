---
name: release-flow
description: Use when a project needs a reusable GitHub-based release flow with setup, preflight, publish, and CI publish phases.
---

# Release Flow

Release Flow（发布流程）标准化一个项目的 fixed release（固定版本发布）和 latest channel（最新通道）发布。

Use this skill when the user wants to:

- enable release-flow in a project,
- run release preflight checks with `tag`, `version`, and `bumpPlugins`,
- trigger a GitHub workflow release,
- inspect CI release trace fields from workflow output.

## Boundaries

- Project setup writes only `.release-flow/config.yaml`, `.release-flow/projection.yaml`, and a thin GitHub Workflow entry after explicit authorization.
- `.release-flow/config.yaml` is release-flow generic config; `.release-flow/projection.yaml` owns project marketplace identity, required GitHub Actions Variables, generators, and transforms.
- Codex `.agents/plugins/marketplace.json` is a generated release projection artifact and is not required on the source branch.
- Local commands do not create release plan files, release records, branches, tags, or release summaries.
- `bumpPlugins` is required; an empty value means catalog/projection-only release.
- Plugin scripts and templates stay inside this plugin package.
- Local publish commands do not create branches, create tags, or push commits.
- GitHub repository settings are modified only after explicit user authorization.
- 禁止在当前对话未获得用户明确确认时修改 GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量）或 repository settings（仓库设置）；未确认时只能输出 remote tasks（远端待办）。

## Commands

Run commands from the target repository root:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py setup --project .
```

Read `.release-flow/config.yaml` and `.release-flow/projection.yaml` before running release commands.

Use `preflight`（发布前检查） before `publish`（发布）. Trigger publish（发布） only with explicit authorization:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py publish --project . --tag v0.1.1 --version 0.1.1 --bump-plugins agent-guard --authorize-publish
```
