# Issue tracker: GitHub

本仓库的 issues 和 PRD 存放在 GitHub Issues。执行 issue 相关操作时使用 `gh` CLI。

## 约定

- 创建 issue：`gh issue create --title "..." --body "..."`
- 读取 issue：`gh issue view <number> --comments`
- 列出 issue：`gh issue list --state open --json number,title,body,labels,comments`
- 评论 issue：`gh issue comment <number> --body "..."`
- 添加或移除标签：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- 关闭 issue：`gh issue close <number> --comment "..."`

在仓库 clone 内执行时，`gh` 会根据 `git remote -v` 自动识别 GitHub 仓库。

## 当 skill 提到“发布到 issue tracker”

创建一个 GitHub issue。

## 当 skill 提到“读取相关 ticket”

执行 `gh issue view <number> --comments`。
