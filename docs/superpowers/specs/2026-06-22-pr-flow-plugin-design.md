---
comet_change: add-pr-flow-plugin
role: technical-design
canonical_spec: openspec
---

# PR Flow Plugin 技术设计

## 背景

本仓库已有 `release-flow` Plugin（发布流程插件）、`cross-agent-review` Plugin（跨代理审查插件）和 `agent-guard` Plugin（代理守卫插件）。`pr-flow` Plugin（PR 流程插件）只处理个人仓库的 PR Flow（拉取请求流程），不承担发布、审查执行或 Hook（钩子）守卫职责。

本设计针对高频问题：创建或同步 PR、等待 checks（检查）、判断 review gate（审查门禁）、合并后 cleanup（清理）。#51 的清理问题是首版核心场景。

## 目标

- 提供独立 `pr-flow` Plugin，覆盖个人仓库日常 PR Flow。
- 让 `cleanup` 成为独立入口，完整覆盖已合并 PR 的本地和远端分支清理。
- 提供 `diagnose` 解释当前流程卡点和固定 stop state（停机状态）。
- 支持 `hotfix` 和 `tweak` 两条清晰捷径。
- 保持首版轻量，不把低频 GitHub Rulesets（GitHub 规则集）治理做重。

## 非目标

- 不提供 dry-run（试运行）。
- 不自动写 GitHub Rulesets 或 Branch Protection（分支保护）。
- 不做 Issue（议题）绑定、closing link（关闭链接）或 PRD（产品需求文档）发布。
- 不生成 GitHub workflow（工作流）。
- 不把 authorization phrase（授权短语）扩展成权限系统。
- 不建设通用 review evidence（审查证据）平台。

## 架构

采用多入口 Skill（技能）加共享脚本内核。

Skill 入口：

- `pr-flow`：总入口和 diagnose。
- `pr-flow-init`：初始化 `.pr-flow/config.yaml`、PR body template（拉取请求正文模板）和 Rulesets 建议。
- `pr-flow-complete`：创建或同步 PR、等待 checks、执行 review gate、合并和 cleanup。
- `pr-flow-cleanup`：单独处理已合并 PR 的分支清理。
- `pr-flow-hotfix`：处理显式允许目标分支的紧急直推。
- `pr-flow-tweak`：处理跳过 review gate 的小改动 PR。

共享脚本：

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- 各 Skill 只负责解释入口和边界，确定性逻辑集中在脚本中。

## 配置模型

`.pr-flow/config.yaml` 纳入 Git（版本管理）。本地运行状态由 `.pr-flow/.gitignore` 忽略。

配置采用 `defaults` 加 `branches` 覆盖：

```yaml
defaults:
  baseBranch: main
  mergeStrategy: merge
  reviewGate:
    mode: github
  wait:
    timeoutSeconds: 600
    pollSeconds: 15
  pr:
    bodyTemplatePath: .pr-flow/pr-template.md
    requiredSections:
      - Summary
      - Scope
      - Verification
      - Risk
      - Rollback
  hotfix:
    verifyCommand: ".\\.venv\\Scripts\\python.exe -m pytest"

branches:
  main:
    remote: origin
    allowHotfixPush: true
```

本地状态：

- `.pr-flow/runs/`：本地运行记录。
- `.pr-flow/last-status.json`：最近一次 diagnose 或命令 stop state。

## Init

`pr-flow-init` 只做低风险本地初始化：

- 创建 `.pr-flow/config.yaml`。
- 创建 `.pr-flow/pr-template.md`。
- 创建 `.pr-flow/.gitignore`。
- 输出 GitHub Rulesets 建议配置。

它不调用 `gh api`，不写远端设置，也不声称已回读验证 Rulesets。Rulesets 是低频需求，由用户或 agent 按建议手工配置。

## Diagnose

`diagnose` 读取本地 git、配置和 GitHub PR 状态，输出固定 stop state：

- `PUSH_REQUIRED`：当前分支没有远端 head branch（功能分支）。
- `DISPATCH_REQUIRED`：checks 未完成或需要外部系统启动。
- `REPLY_OR_FIX_REQUIRED`：checks 或 review gate 阻塞。
- `EXCEPTION_REQUIRED`：状态异常，不能安全判断下一步。

安全性主要由 `diagnose`、硬性前置检查和执行后回读承担，而不是 dry-run。

## Complete

`complete` 的流程：

1. 检查 worktree（工作区）和当前分支状态。
2. 确认远端 head branch；缺失时输出 `PUSH_REQUIRED`。
3. 创建或同步 PR。
4. 等待配置中的 checks。
5. 执行配置中的 review gate。
6. 用当前 head commit（头提交）锁定合并目标。
7. 按配置执行 `merge`、`squash` 或 `rebase`。
8. 调用 cleanup。

合并必须锁定 head commit，避免 PR 在审查后移动。

## Review Gate

`reviewGate.mode` 支持：

- `skip`
- `github`
- `local`
- `dual`

首版 `local` 和 `dual` 只支持 `cross-agent-review` 的 `review-pass.json`。默认路径建议可配置；如果配置缺失，脚本给出清晰错误，不自动猜多个路径。

后续如果出现多个 evidence 来源，再设计通用 JSON evidence 契约。

## Cleanup

`cleanup` 是独立核心入口，覆盖 #51。

成功路径：

1. 确认 PR 已合并。
2. 确认 worktree 干净。
3. 确认 head branch 匹配当前 PR。
4. 删除远端 head branch。
5. 切回并同步 base branch。
6. 删除本地 head branch。
7. 输出最终分支状态。

拒绝条件：

- PR 未合并。
- worktree 不干净。
- head branch 与 PR 不匹配。
- 目标分支是保护分支或配置禁止清理。
- 无法确认最终远端或本地状态。

cleanup 不因为 authorization phrase 功能额外增加确认；它只遵循原本 cleanup 规则。

## Hotfix

`hotfix` 是紧急路径，不创建 PR。

前置条件：

- 目标分支在配置中显式 `allowHotfixPush: true`。
- 命令显式指定目标分支。
- 当前提交基于目标分支最新 head commit。
- `hotfix.verifyCommand` 通过。
- authorization phrase 确认通过。

执行后必须回读远端目标分支，确认远端等于预期 head commit。最小审计记录只保存目标分支、before/after commit（前后提交）、actor（执行者）、timestamp（时间）和验证结果。

authorization phrase 只是“我确认”的替代。真正远端权限仍由 GitHub 凭证和 Rulesets bypass（规则集绕过权限）决定。

## Tweak

`tweak` 是非 bug 小改动路径。

规则：

- 必须走 PR。
- 只跳过 review gate。
- 不跳过 checks、merge、cleanup。
- 用户必须提供 reason（原因）。
- reason 必须写入 PR body。
- 不限制文件范围，由用户负责判断是否属于小改动。

## 测试策略

- 配置测试：验证 init 生成 config、template、gitignore 和 Rulesets 建议，且不写远端。
- Diagnose 测试：覆盖四个 stop state。
- Lifecycle 测试：覆盖 PR 创建或同步、checks 轮询、review gate、head-locked merge 和 cleanup 编排。
- Cleanup 测试：覆盖 #51 成功路径和未合并 PR、dirty worktree、分支不匹配等拒绝场景。
- Hotfix 测试：覆盖 allow-list、基线一致、验证命令、授权短语和远端回读。
- Tweak 测试：覆盖 reason 必填、PR body 标记、跳过 review gate 但保留后续流程。
- Package 测试：验证 Codex/Claude manifest 和 release projection 包含 `pr-flow`。

## 风险

- Hotfix 直推风险高。缓解：目标分支 allow-list、基线一致、验证命令、授权短语和远端回读。
- 不自动写 Rulesets 可能让初始化不完整。缓解：init 输出明确建议，让用户或 agent 手工配置。
- 不做 dry-run 会减少预览能力。缓解：diagnose 和硬性前置检查必须清楚。
- `tweak` 不限制文件范围可能被误用。缓解：强制 reason 写入 PR body。

## Spec Patch

无。当前 OpenSpec delta spec 已覆盖本设计。
