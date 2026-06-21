## Why

个人仓库的 PR Flow（拉取请求流程）已经反复出现同一类人工成本：创建或同步 PR、等待 checks（检查）、判断 review gate（审查门禁）、合并后清理本地和远端分支。#51 暴露的合并后 cleanup（清理）尤其高频，而且容易漏掉远端分支、本地分支或 base branch（目标分支）同步状态。

本 change（变更）引入独立 `pr-flow` Plugin（插件），把日常 PR Flow 做成可复用、低复杂度、适合个人仓库的工具；它不把低频 GitHub Rulesets（GitHub 规则集）治理自动化做重。

## What Changes

- 新增 `pr-flow` Plugin（插件）及多入口 Skill（技能）：
  - `pr-flow`：总入口和 diagnose（诊断）。
  - `pr-flow-init`：生成 `.pr-flow/config.yaml`、PR body template（拉取请求正文模板）和 GitHub Rulesets 建议。
  - `pr-flow-complete`：创建或同步 PR、等待 checks、执行 review gate、合并、清理。
  - `pr-flow-cleanup`：单独清理已合并 PR，覆盖 #51。
  - `pr-flow-hotfix`：紧急 hotfix（热修复）直推目标分支。
  - `pr-flow-tweak`：非 bug（缺陷）小改动路径，走 PR 但跳过 review gate。
- 新增共享确定性脚本 `scripts/pr_flow.py`，由各 Skill 调用。
- 新增仓库配置 `.pr-flow/config.yaml`，纳入 Git（版本管理）。
- 新增本地状态目录约定 `.pr-flow/runs/` 和 `.pr-flow/last-status.json`，由 `.pr-flow/.gitignore` 忽略。
- 保留固定 stop state（停机状态）：`PUSH_REQUIRED`、`DISPATCH_REQUIRED`、`REPLY_OR_FIX_REQUIRED`、`EXCEPTION_REQUIRED`。
- 明确移除首版过度设计：
  - 不提供 dry-run（试运行）机制。
  - 不自动写 GitHub Rulesets。
  - 不做 Branch Protection（分支保护）回退。
  - 不做 Issue（议题）绑定或 closing link（关闭链接）。
  - 不生成 GitHub workflow（GitHub 工作流）。
  - 不把 authorization phrase（授权短语）扩展成权限系统。

## Capabilities

### New Capabilities

- `pr-flow-plugin`: 定义个人仓库可复用 PR Flow Plugin 的配置、命令入口、普通 PR 流程、cleanup、hotfix、tweak、诊断和安全边界。

### Modified Capabilities

- 无。

## Impact

- 新增 `plugins/pr-flow/` Plugin 包结构。
- 新增 `openspec/specs/pr-flow-plugin/` 主规格，归档后成为当前契约。
- 更新 release projection（发布投影）时需要把 `pr-flow` 加入发布插件清单。
- 需要新增脚本测试，覆盖 init、diagnose、complete、cleanup、hotfix、tweak 和 stop state。
