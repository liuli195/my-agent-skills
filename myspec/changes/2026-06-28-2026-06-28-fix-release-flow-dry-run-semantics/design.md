## Design

本次 tweak（小改）不增加新模式和新依赖，只删除误导性入口，并复用已有临时 projection（发布投影）检查路径。

## 修复方案

`release-init`（发布初始化）只创建正式本地 release plan（发布计划）。它不再接受 `--dry-run`（试运行），也不再写 `dryRun`（试运行标记）。

`preflight`（发布前检查）不再接收 `--channel-tree`（通道树）。发布前只验证配置、变量、版本、manifest（清单）和 projection（发布投影）是否能在临时目录生成，并在检查结束后自动清理临时目录。

`ci-publish`（持续集成发布）不再接收 `--dry-run`（试运行）。远端写入仍必须显式传入 `--authorize-ci-publish`（授权持续集成发布）。

`publish --dry-run`（发布试运行）保留为纯输出预览，并使用 `release_tag`（发布标签）、`git_tag_created`（Git 标签是否创建）、`local_branch_created`（本地分支是否创建）和 `push_run`（是否推送）字段，避免重复 `tag`（标签）字段。

## Boundaries

- 不新增 `preview-only`（仅预览）或 `dry-run-plan`（试运行计划）模式。
- 不新增 `drift-check`（漂移检查）命令。
- 不引入新依赖。
- 不改 GitHub Workflow（GitHub 工作流）的正式发布路径。
