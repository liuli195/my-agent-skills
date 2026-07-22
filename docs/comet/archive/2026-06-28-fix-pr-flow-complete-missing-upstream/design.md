## 根因

`diagnose`（诊断）入口在查询 PR（拉取请求）前检查 `@{u}`，而 `complete`（收尾）直接进入 `find_pr/create_pr`（查找/创建拉取请求）。当分支没有 `upstream`（上游分支）时，`gh pr create`（创建拉取请求）只能返回底层错误。

## 修复方案

提取一个最小共享检查函数，在 `complete`（收尾）创建或同步 PR（拉取请求）前调用。非目标分支缺少 `upstream`（上游分支）时返回 `PUSH_REQUIRED`（需要推送）。

## 验证

新增一个进程内测试，模拟当前功能分支没有 `upstream`（上游分支），断言 `complete`（收尾）不调用 `gh`，并写入 `PUSH_REQUIRED`（需要推送）。
