---
name: release-flow
description: Use when a project needs a reusable GitHub-based release flow with setup, preflight, publish, CI publish, and complete formal plugin archives.
---

# Release Flow

Release Flow（发布流程）标准化一个项目的 fixed release（固定版本发布）和 latest channel（最新通道）发布。

Use this skill when the user wants to:

- enable release-flow in a project,
- run release preflight checks with `tag`, `version`, and `bumpPlugins`,
- trigger a GitHub workflow release,
- inspect CI release trace fields from workflow output,
- build and retain complete formal plugin archives for the separately authorized synchronization stage.

## 运行前提

脚本需要 Python（编程语言）及本技能 `requirements.txt` 声明的 PyYAML（配置解析库）。复用现有环境，确认本次实际解释器；缺库时由原入口报告解释器和声明位置，只报告缺失，由用户决定是否安装。

Git（版本管理工具）、gh（代码托管命令工具）及认证只在相应仓库检查、远端查询或发布功能实际需要时核对；本地模板生成及配置校验不设置统一远端工具门槛。发布流水线中构建软件包所需 Node.js（节点运行时）和 npm（软件包管理器）继续由既有流水线准备，不扩大为全部技能调用的前置条件。

## Boundaries

- Project setup writes only `.release-flow/config.yaml`, `.release-flow/projection.yaml`, and a thin GitHub Workflow entry after explicit authorization.
- `.release-flow/config.yaml` is release-flow generic config; `.release-flow/projection.yaml` owns project marketplace identity, required GitHub Actions Variables, generators, and transforms.
- Codex `.agents/plugins/marketplace.json` is a generated release projection artifact and is not required on the source branch.
- Setup, preflight, and local publish commands do not create release plan files, release records, branches, tags, or release summaries.
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
python <plugin-root>/skills/release-flow/scripts/release_flow.py publish --project . --tag v0.1.1 --version 0.1.1 --bump-plugins release-flow --authorize-publish
```


## 正式完整产物与同步边界

本技能负责版本、发布前检查、GitHub（代码托管）正式发布及完整正式插件归档，不读取或写入个人插件账号，不安装、卸载或切换客户端。个人对象创建/更新由插件同步技能唯一编排官方 Creator（插件创建器），不得通过 app-server（客户端服务）发布。

本仓库继续在原 ci-publish（持续集成发布）之后，从精确正式标签的干净源码构建 dot-release-packages.tar（完整正式包），保留原产物名、来源/版本/摘要、隐藏文件和执行模式；不将个人认证放入持续集成，不增加另一发布工作流。版本发布、完整包保留和后续账号同步分别报告，后续失败不能重发已成功正式版本。

原打包入口仍为目标仓库 plugins/tool-lifecycle/pack.py snapshots（完整快照命令），正式模式使用 RELEASE（正式）及准确 release-ref（正式标签引用）；其作用是构建和记录内容，不证明个人账号已收到，也不安装插件。同步阶段复核官方发布记录、标签提交及归档，再使用对应官方工具。


## Private upstream release assets

After the official release succeeds and the exact clean tag is checked out, build own snapshots first, then run `python <tag-tree>/plugins/tool-lifecycle/private_sources.py --project <tag-tree> --output <sibling-artifact-directory>`. Source and output trees must be disjoint. `.release-flow/private-sources.json` records fixed official upstream commits, archive and license digests, the exact official skill list and precise Boolean adaptations. Only configuration is committed; fetched upstream files, adapted skills and package directories never enter the tag tree or public marketplace projection. Original skill bodies, support files and license bytes are preserved outside the explicitly configured metadata tokens.

The combined complete archive is uploaded only after private projection succeeds. A failed private build does not undo or repeat the already successful GitHub/npm release. Preserve the failure and partial artifacts; inspect them, then rebuild the archive in a fresh sibling output for the same verified tag. Never overwrite a release or silently publish an incomplete delivery archive. Account creation/update remains plugin-sync's separate host Creator workflow.
