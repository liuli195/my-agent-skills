---
name: release-flow
description: Use when a project needs a reusable GitHub-based release flow with setup, release-init, preflight, publish, and summarize phases.
---

# Release Flow

Release Flow（发布流程）标准化一个项目的 fixed release（固定版本发布）和 latest channel（最新通道）发布。

Use this skill when the user wants to:

- enable release-flow in a project,
- create a release plan for a tag,
- run release preflight checks,
- trigger a GitHub workflow release,
- summarize release results.

## Boundaries

- Project setup writes only `.release-flow/config.yaml`, `.release-flow/projection.yaml`, `.release-flow/.gitignore`, and a thin GitHub Workflow entry after explicit authorization.
- `.release-flow/config.yaml` is release-flow generic config; `.release-flow/projection.yaml` owns project marketplace identity, required GitHub Actions Variables, generators, and transforms.
- Codex `.agents/plugins/marketplace.json` is a generated release projection artifact and is not required on the source branch.
- Project setup does not create `.release-flow/releases/<tag>/release-plan.json`.
- Plugin scripts and templates stay inside this plugin package.
- Local publish commands do not create branches, create tags, or push commits.
- GitHub repository settings are modified only after explicit user authorization.

## Commands

Run commands from the target repository root:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py setup --project .
```

Read `.release-flow/config.yaml` and `.release-flow/projection.yaml` before running release commands.
