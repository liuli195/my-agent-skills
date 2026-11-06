## 根因

`diagnose`（诊断）直接把所有非零 `gh pr view`（查看拉取请求）返回值归为 `gh_pr_view_failed`（查看失败），没有复用已有 `gh_pr_not_found`（未找到拉取请求）判断。

## 修复方案

在 `diagnose`（诊断）处理 `gh pr view`（查看拉取请求）失败时，先判断是否未找到 PR（拉取请求）。如果当前分支不是目标分支，则返回 `DISPATCH_REQUIRED`（需要外部进展），原因 `pr_missing`，下一步 `complete`（收尾）。

## 验证

新增进程内测试模拟功能分支已有 `upstream`（上游分支）但无 PR（拉取请求），断言 `diagnose`（诊断）返回 `DISPATCH_REQUIRED`。
