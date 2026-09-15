## Context

`complete`（收尾）和 `tweak`（小改）共享 `run_lifecycle`（生命周期流程），并在创建或同步 PR（拉取请求）前调用同一个 safe auto-push（安全自动推送）函数。当前函数只计算 ahead（领先）提交数，不计算 behind（落后）提交数，因此 ahead/behind（领先/落后）分叉会落到普通 `git push`（推送）失败路径。

## Goals / Non-Goals

**Goals:**

- complete（收尾）和 tweak（小改）在 upstream（上游分支）落后时不自动 push（推送）。
- 停止状态明确提示先同步 upstream（上游分支），再重跑原命令。

**Non-Goals:**

- 不自动执行 rebase（变基）或 pull（拉取）。
- 不改变 hotfix（热修复）和 release-flow（发布流程）发布推送。
- 不新增依赖或配置。

## Decisions

- 使用 Git（版本管理）现有能力 `rev-list --count HEAD..@{u}` 计算 behind（落后）数。理由：和当前 ahead（领先）计算对称，不需要新依赖。
- behind（落后）大于 0 时返回 `EXCEPTION_REQUIRED`（需要人工处理），而不是 `PUSH_REQUIRED`（需要推送）。理由：此时普通 push（推送）不是正确下一步。
- 恢复指引保留原 lifecycle（生命周期）命令作为 retry command（重试命令），复用现有 `pr_body_next_command`（正文命令生成）输出。

## Risks / Trade-offs

- [Risk] `git pull --rebase`（变基拉取）可能遇到冲突。Mitigation: 流程只提示，不自动执行。
- [Risk] behind-only（只落后）分支现在会停止，而不是继续创建或同步 PR（拉取请求）。Mitigation: 这是正确的 fail closed（保守失败），因为本地不是最新 upstream（上游分支）。
