# prefer-orca-worktree-removal 验证报告

## 结论

通过。实现满足 proposal（提案）、design（设计）和 `pr-flow-plugin`（拉取请求流程插件）delta spec（增量规格）的要求，可进入 archive（归档）阶段。

## 验证摘要

| 维度 | 结果 | 证据 |
| --- | --- | --- |
| 完整性 | 通过 | `tasks.md`（任务清单）9/9 项完成。 |
| 正确性 | 通过 | Orca（工作区管理器）优先、Git（版本管理）回退、Orca（工作区管理器）失败停止和路径规范化均有命令桩回归。 |
| 一致性 | 通过 | 保持既有主工作树、脏工作树和无强制删除边界；未新增依赖、配置、终端关闭或 `git pull`（拉取）。 |

## 需求与场景映射

- 默认不删除工作树：现有 `--remove-worktree`（删除工作树参数）触发条件保持不变，`run_cleanup()`（运行清理）仅在显式参数下调用删除器：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:2348`。
- 非 Orca（工作区管理器）目标与不可用回退：`find_orca_worktree_id()`（查找 Orca 工作树标识）对不可执行、失败、无效 JSON（数据格式）和无匹配返回 `None`（无匹配），`remove_worktree()`（删除工作树）随后调用既有非强制 Git（版本管理）删除：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:1213`、`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:1252`。参数化回归：`tests/test_pr_flow_cli.py:565`。
- Orca（工作区管理器）已登记目标：规范化路径匹配后使用完整 `worktreeId`（工作树标识）调用 `orca worktree rm --worktree id:<id> --json`（Orca 工作树删除），不调用 Git（版本管理）删除且不带 `--force`（强制参数）：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:1244`。回归：`tests/test_pr_flow_cli.py:526`。
- 路径规范化：测试以 Windows（视窗）大写和斜杠形式提供 Orca（工作区管理器）路径，匹配目标绝对路径：`tests/test_pr_flow_cli.py:539`。
- Orca（工作区管理器）已登记但删除失败：抛出 `orca_worktree_remove_failed`（Orca 工作树删除失败），保留标准错误且不回退 Git（版本管理）：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:1247`。回归：`tests/test_pr_flow_cli.py:592`。
- 既有安全边界：主工作树和脏工作树仍在 Orca（工作区管理器）探测前被拒绝，成功后仍回读 Git（版本管理）工作树清单：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:1235`。
- 并发锁回归：完整 PR Flow（拉取请求流程）测试发现 Windows（视窗）空锁文件在获取锁前初始化会产生 `PermissionError`（权限错误）；实现改为三个共享锁路径均先取得锁后写入首字节：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:384`、`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:416`。失败前已复现，修复后并发端到端测试连续 6 次通过。

## 设计一致性

- Orca（工作区管理器）命令优先解析 `ORCA_CLI_COMMAND`（Orca 命令环境变量），开发环境使用 `orca-dev`（Orca 开发命令），Linux（Linux 系统）使用 `orca-ide`（Orca 集成开发环境命令），避免将 Linux（Linux 系统）屏幕阅读器误用为 Orca（工作区管理器）：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:283`。
- Orca（工作区管理器）删除成功与 Git（版本管理）删除成功共享同一工作树清单回读；已登记目标的删除失败不会尝试第二个删除器。
- 三份技能说明同步阐明 Orca（工作区管理器）优先、Git（版本管理）回退、失败停止与无强制删除边界：`plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md:12`、`plugins/pr-flow/skills/pr-flow-complete/SKILL.md:14`、`plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md:18`。
- 本 change（变更）配置 `review_mode: off`（审查模式关闭），依照 Tweak（小改）直接构建预设未自动请求额外代码审查；完整回归、规格映射和差异检查已执行。

## 验证证据

执行于 2026-07-21：

```text
python -m pytest tests/test_pr_flow_cli.py -q
205 passed

python -m pytest tests/test_pr_flow_cli.py::test_linked_worktrees_complete_independently_through_cli -q
修复后连续 6 次通过

openspec validate prefer-orca-worktree-removal --strict --no-interactive
Change 'prefer-orca-worktree-removal' is valid

python .build-and-verify/runtime/build_and_verify.py build --project .
status: passed

python .build-and-verify/runtime/build_and_verify.py verify --project . --full
status: passed
```

最终完整 build-and-verify（构建与验证）结果：69 项本地构建契约、284 项 Agent Guard（代理守卫）、58 项 Release Flow（发布流程）、218 项 PR Flow（拉取请求流程）、215 项 Cross-Agent Review（跨代理审查）、204 项 build-and-verify（构建与验证）及 16 项 OpenSpec（开放规格）检查通过。

## 非阻断观察

Agent Guard（代理守卫）端到端检查仍有 6 条既有 Windows（视窗）子进程 UTF-8（统一编码）读取警告；完整验证退出成功，且警告不属于本 change（变更）的行为偏差。
