## Context

`complete`（完成流程）当前在没有 PR（拉取请求）时调用 `missing_upstream_state`（缺少上游状态），发现没有 upstream（上游分支）就返回 `PUSH_REQUIRED`（需要推送）。这保护了安全边界，但也阻止了功能分支的完整收尾。

现有规格已经要求 `setup.github`（GitHub 配置建议）不能被运行命令消费，所以不能把 `setup.github.branchRulesets`（GitHub 分支规则集）作为运行判断来源。

## Goals / Non-Goals

**Goals:**

- 只在本地干净、非默认目标分支、远端确认不受保护时自动普通推送。
- 远端保护状态查询失败时 fail closed（失败即停止）。
- 保留 `PUSH_REQUIRED`（需要推送）作为推送失败后的停止状态。

**Non-Goals:**

- 不新增配置字段。
- 不做 `force push`（强制推送）。
- 不改变 `diagnose`（诊断）和 `hotfix`（热修复）行为。

## Decisions

- 使用 `gh api repos/{owner}/{repo}/rules/branches/<branch>` 查询当前分支会命中的 active rules（有效规则）数量。
- 查询失败、字段缺失或无法解析时返回 `EXCEPTION_REQUIRED`（需要人工处理），不推送。
- 推送命令仍走现有 `git`（版本管理）封装；无 upstream（上游分支）时执行 `git push -u <remote> <branch>`，已有 upstream（上游分支）时执行 `git push`。
- 不读取 `setup.github`（GitHub 配置建议），保持现有运行边界。

## Risks / Trade-offs

- GitHub（代码托管平台）查询需要 `gh`（GitHub 命令行）登录和网络可用；失败时停止会更保守。
- active rules（有效规则）数量大于 0 时一律视为受保护；这可能拦住只限制删除等较轻规则，但不会误推送到保护范围内。
