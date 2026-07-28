## 根因

`merge_pr`（合并拉取请求）把所有 `gh pr merge`（合并拉取请求）非零返回都抛成 `gh_pr_merge_failed`（合并拉取请求失败）。其中 GitHub Rulesets（GitHub 规则集）未满足属于外部等待，不是不可恢复异常。

## 修复方案

在 `merge_pr`（合并拉取请求）失败时检查输出文本。命中 `base branch policy prohibits the merge`（目标分支策略禁止合并）时抛出 `ruleset_merge_blocking`（规则集阻塞合并），由生命周期入口映射成 `DISPATCH_REQUIRED`（需要外部进展）。

## 验证

新增测试模拟 GitHub（代码托管平台）策略阻止合并，断言最终状态为 `DISPATCH_REQUIRED`。
