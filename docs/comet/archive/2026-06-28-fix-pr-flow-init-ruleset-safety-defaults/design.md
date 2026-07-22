## 修复方案

在 `references/questionnaire.md`（问答模板）的 branch protection（分支保护）场景中，补充两条选择后果：

- 远端待办默认启用 `Restrict deletions`（限制删除）。
- 远端待办默认启用 `Block force pushes`（阻止强制推送）。

这两项只进入 `setup.github`（GitHub 配置建议）和 remote tasks（远端待办），不改变本地运行配置，也不让插件直接调用 GitHub API（接口）。

## 验证方式

用现有初始化问卷测试锁定模板内容，先新增断言，再补问卷文本，最后运行相关 PR Flow（拉取请求流程）测试和 OpenSpec（开放规格）校验。
