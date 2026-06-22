## Context

本仓库维护个人 Agent Plugin（插件）和 Skill（技能）。已有 `release-flow` Plugin 处理发布流程，`cross-agent-review` Plugin 处理跨代理审查证据，`agent-guard` Plugin 处理通用流程守卫。`pr-flow` 应独立处理 PR Flow（拉取请求流程），不把发布、审查执行或 Hook（钩子）守卫混入首版。

#51 反复出现的痛点是 PR 合并后的 cleanup（清理）：需要人工串联确认合并状态、删除远端 head branch（功能分支）、同步 base branch（目标分支）、删除本地分支并检查最终状态。完整 PR Flow 还需要创建或同步 PR、等待 checks（检查）、判断 review gate（审查门禁）、合并和清理。对个人仓库而言，低频的 GitHub Rulesets（GitHub 规则集）配置不值得在首版做成自动写远端工具。

## Goals / Non-Goals

**Goals:**

- 提供适合个人仓库的 `pr-flow` Plugin，覆盖日常 PR 创建、诊断、合并和清理。
- 让 #51 的合并后 cleanup 成为一条独立、可复用、可测试的入口。
- 保留 `hotfix` 和 `tweak` 两条明确捷径，但边界简单。
- 保持配置可共享、本地状态可忽略、命令行为可诊断。

**Non-Goals:**

- 不自动写 GitHub Rulesets 或 Branch Protection（分支保护）。
- 不提供 dry-run（试运行）模式。
- 不做 Issue（议题）绑定、closing link（关闭链接）或 PRD（产品需求文档）发布。
- 不生成 GitHub workflow（工作流）。
- 不把 authorization phrase（授权短语）设计成权限系统。
- 不把 review evidence（审查证据）抽象成复杂通用平台；首版先接 `cross-agent-review` 产物。

## Decisions

### 1. 多入口 Skill + 共享脚本内核

`pr-flow` 采用多入口 Skill：

- `pr-flow`：总入口和 diagnose。
- `pr-flow-init`：仓库初始化。
- `pr-flow-complete`：完整 PR 流程。
- `pr-flow-cleanup`：合并后清理。
- `pr-flow-hotfix`：热修复直推。
- `pr-flow-tweak`：小改动路径。

各入口调用同一个 `scripts/pr_flow.py`。这样用户入口清楚，测试和实现仍集中在一套确定性脚本里。

替代方案是单个大 Skill 加大脚本。它首版更少文件，但后续命令说明会堆在一起，难以保持边界。

### 2. `init` 只生成本地配置和远端规则建议

`pr-flow-init` 只写 `.pr-flow/config.yaml`、PR body template 和 `.pr-flow/.gitignore`，并输出 GitHub Rulesets 建议。它不调用 `gh api` 写远端，也不回读验证远端规则。

原因：Rulesets 是低频设置，自动写入会引入权限、失败恢复和误改远端规则问题；对个人仓库首版不划算。需要配置时，由用户或 agent 按建议手工配置即可。

### 3. 不做 dry-run

首版不提供 dry-run。安全性来自 diagnose、硬性前置检查、固定 stop state、高风险动作的确认和执行后回读验证。

原因：dry-run 会让每个命令维护预览路径和执行路径两套逻辑。对个人仓库，先用 `diagnose` 看状态，再执行具体命令更简单。

### 4. 配置采用 defaults + branches 覆盖

`.pr-flow/config.yaml` 纳入 Git。它包含默认规则和少量分支覆盖：

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
    allowHotfixPush: false
```

`allowHotfixPush` 默认必须是 `false`。需要启用 hotfix（热修复）直接推送时，用户必须在目标分支配置中显式改为 `true`。

本地状态放在 `.pr-flow/runs/` 和 `.pr-flow/last-status.json`，由 `.pr-flow/.gitignore` 忽略。

### 5. Review gate 配置化，但首版实现克制

`reviewGate.mode` 支持 `skip`、`github`、`local`、`dual`。`local` 和 `dual` 首版只支持 `cross-agent-review` 的 `review-pass.json`。后续如果多个来源真的出现，再抽象通用 JSON evidence 契约。

这样保留扩展点，但不在首版提前建设证据平台。

### 6. Cleanup 是独立核心入口

`pr-flow-cleanup` 不依赖 complete。它只处理已合并 PR 的 head branch 清理和 base branch 同步，并输出最终状态。

cleanup 的硬性拒绝条件：

- PR 未合并。
- worktree（工作区）不干净。
- head branch 不匹配当前 PR。
- head branch 等于 base branch，存在删除目标分支风险。
- 无法确认远端和本地分支最终状态。

cleanup 不查询 GitHub Branch Protection（分支保护）或 Rulesets（规则集）。首版只保证不删除 base branch（目标分支），并只删除 PR 的 head branch。

### 7. Hotfix 是显式紧急路径

`hotfix` 不创建 PR。它只允许作用于配置里 `allowHotfixPush: true` 的目标分支，并要求用户显式指定目标分支。

执行顺序：

1. fetch 目标分支。
2. 验证当前提交基于目标分支最新 head。
3. 确认 authorization phrase 配置存在且算法受支持。
4. 运行 `hotfix.verifyCommand`。
5. 校验 authorization phrase。
6. push 到目标分支。
7. 回读远端目标分支，确认等于预期提交。
8. 写入最小本地审计记录。

authorization phrase 只是确认短语，不是安全机制。真正的远端写入权限仍由 GitHub Rulesets bypass（规则集绕过权限）和凭证决定。

authorization phrase 使用 `phraseHashAlgorithm: md5` 是有意的兼容选择：它只替代用户输入“我确认”，不是权限边界，也不承诺防离线破解。真正的安全边界仍是 GitHub 凭证、Rulesets bypass（规则集绕过权限）、目标分支 allow-list（允许列表）、基线一致校验和验证命令。

### 8. Tweak 只跳过 review gate

`tweak` 必须走 PR。它跳过 review gate，但仍执行 checks、merge 和 cleanup。用户必须提供 reason，系统把 reason 写进 PR body。

不限制文件范围。个人仓库里文件范围规则很容易变成误报来源，首版把判断责任留给用户。

## Risks / Trade-offs

- Hotfix 直推风险高 → 限制目标分支、校验基线、强制验证命令、授权短语确认、push 后回读。
- 不自动写 Rulesets 可能让初始化不完整 → init 输出明确建议配置，由用户或 agent 手动执行。
- 不做 dry-run 可能减少预览能力 → 用 diagnose 和硬性前置检查承担安全边界。
- `local` review evidence 首版只支持 `cross-agent-review` → 保持实现小；需要更多 evidence 来源时再扩展。
- `tweak` 不限制文件范围可能被误用 → 必须写 reason，并在 PR body 留痕。

## Migration Plan

这是新增 Plugin，无现有用户数据迁移。实现后需要：

1. 新增 `plugins/pr-flow/` package。
2. 新增 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json`。
3. 新增 Skill 入口和共享脚本。
4. 更新 release projection，把 `pr-flow` 加入发布插件清单。
5. 通过测试和包校验后再发布。

## Open Questions

- 首版 `cross-agent-review` evidence 的默认路径是否固定为 `.local/cross-agent-review/.../review-pass.json`，还是由 `.pr-flow/config.yaml` 配置。
- `required checks` 首版是否完全手写配置，还是 init 从已有 PR 中给出候选但不自动写入。
