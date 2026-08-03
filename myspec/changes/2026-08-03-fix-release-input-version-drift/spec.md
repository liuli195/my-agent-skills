# 发布输入同版本漂移防护规格

## Problem Statement

Release Flow（发布流程）当前只比较未选插件的版本号，不比较其实际 Release Input（发布输入）。发布工作流随后会把源分支的完整快照写入 marketplace（插件市场）分支，因此插件源码可以在版本号不变时进入新发布。NPM（Node 包管理器）插件还存在共享打包输入和 `package.json` 未被通用版本检查覆盖的风险。

这会使同一个插件版本对应不同内容，并让依赖版本号判断更新的消费者继续使用旧内容。

## Solution

Release Flow（发布流程）的 preflight（发布前检查）必须以 Release Baseline（发布基线）为依据，同时检查每个发布目标的 Release Input（发布输入）和版本文件。

当发布输入相对发布基线发生变化时，插件必须被列入 `bumpPlugins`（提升插件列表），并且所有版本文件必须完成本次发布版本提升；否则发布必须失败。

检查必须同时覆盖：

- marketplace（插件市场）插件 `release-flow` 和 `pr-flow`；
- NPM 插件 `build-and-verify` 和 `my-spec`；
- NPM 插件目录、NPM 元数据、共享管理模块和共享打包器等会影响候选包的输入；
- 未被 marketplace projection（市场投影）列出的 NPM 发布目标。

现有 NPM 候选包生成、安装验证和发布完整性校验继续作为最终产物检查，不新增发布依赖。

## User Stories

1. As a release maintainer（发布维护者）, I want preflight to reject changed marketplace plugin content without a selected version bump, so that source changes cannot enter a release under an old plugin version.
2. As a release maintainer（发布维护者）, I want preflight to reject changed NPM plugin content without a selected version bump, so that an NPM package is not silently left unpublished.
3. As a release maintainer（发布维护者）, I want shared NPM packaging inputs to be associated with every affected NPM plugin, so that a shared management or packaging change cannot update only one package.
4. As a release maintainer（发布维护者）, I want all version files for an NPM plugin to be checked together, so that package metadata and plugin manifests cannot drift apart.
5. As a release maintainer（发布维护者）, I want a selected plugin whose content changed but whose version did not advance from the release baseline to be rejected, so that selecting a plugin alone cannot bypass the version requirement.
6. As a release maintainer（发布维护者）, I want unchanged unselected plugins to remain valid, so that independent plugin versioning and catalog-only releases remain possible.
7. As a release maintainer（发布维护者）, I want the check to cover NPM targets independently of the marketplace projection, so that removing an NPM package from a catalog cannot disable its release guard.
8. As a release maintainer（发布维护者）, I want failures to identify the plugin that requires a bump, so that I can correct the version through the normal PR Flow（拉取请求流程） path.
9. As a plugin consumer（插件使用者）, I want a published plugin version to represent stable content, so that version-based update behavior does not hide source changes.

## Implementation Decisions

- Keep `bumpPlugins` as an explicit selection of plugins whose versions are intended to advance; do not force all plugins to share the global release version.
- Extend the single plugin registry（插件注册表） with each target's release inputs and version files.
- Use the remote release channel as the Release Baseline（发布基线） and compare Git-visible content, including additions and deletions.
- Treat marketplace plugin directories as their release inputs.
- Treat each NPM plugin directory plus the shared management module and packer as release inputs, because the packer replaces plugin files and determines the candidate package.
- Check the two plugin manifests for every plugin, and also check `package.json` for NPM plugins.
- Check all registered NPM targets even when the marketplace projection does not list them.
- Reuse the existing NPM candidate and integrity checks; do not download or compare new external artifacts in the generic preflight path.
- Keep catalog identity and projection-only changes outside plugin version-bump requirements when no plugin Release Input changed.
- Preserve the existing first-release and missing-baseline behavior: a target without a usable release baseline requires an explicit bump.

## Testing Decisions

- Test the public `release_flow.py preflight` command against temporary Git repositories containing an old release channel and a current source tree.
- Cover a changed marketplace plugin with an empty selection, a changed NPM plugin with an empty selection, and a changed shared NPM input with only one NPM plugin selected.
- Cover package metadata drift, selected content with no version advancement, valid selected content with all version files advanced, and unchanged unselected targets.
- Keep existing tests for repeated selections, remote source-reference checks, projection validation, NPM candidate packaging, and release publication behavior.
- Do not test only the new helper or pre-seed `preflight_errors`; each regression case must exercise the real CLI boundary.

## Out of Scope

- Automatically editing or committing plugin versions.
- Forcing all four plugins to use one version number.
- Changing NPM packaging, publishing credentials, or registry behavior.
- Refreshing Claude or Codex caches.
- Publishing a release, pushing a branch, or changing GitHub repository settings.
- Comparing consumer cache contents during release preflight.

## Further Notes

The fix is a release-integrity guard. A content change may still be released independently, but it must carry an explicit plugin version bump and selection. Existing release and NPM publication safeguards remain in place as downstream checks.
