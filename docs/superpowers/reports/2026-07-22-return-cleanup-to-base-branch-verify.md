# return-cleanup-to-base-branch 验证报告

## 当前结论

实现、规格与用户授权的仓库规则改动均通过完整验证。归档前一次被 OpenSpec（开放规格）阻止，原因是 delta spec（增量规格）重命名了两个既有场景标题；现已恢复原场景标题并保留本 change（变更）的新增行为。实际 delta 合并仍须在用户下一次归档确认后执行。

## 完整性

`tasks.md`（任务清单）共 16 项，均已完成：

- cleanup（清理）在目标分支可用时检出该分支、在已同步占用时保持 detached HEAD（分离头）、处理检出期间新增占用、串行化竞争检出，以及从已同步目标分支重试源分支删除。
- 缺失本地目标分支时，创建、检出并回读提交一致性。
- 用户授权的 `AGENTS.md`（代理规则）改动已原样带入隔离工作树，要求使用 build-and-verify（构建与验证）Skill（技能）入口执行构建与验证。
- delta spec（增量规格）恢复了 `Cleanup merged PR` 和 `Cleanup creates a missing local base branch` 的既有标题，避免 OpenSpec（开放规格）归档将既有场景视为删除。

## 正确性与设计一致性

- `run_cleanup()` 在删除源分支前切离源分支、更新并检出可用目标分支，随后回读当前 `HEAD`、本地目标分支与固定远端快照：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:2216`。
- 目标分支被其他工作树占用时，完成状态记录 `baseCheckout.status: skipped` 与占用原因；检出期间才发生占用时，重新读取工作树清单而非解析 Git（版本管理）错误文本：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:2221`。
- 共享 Git（版本管理）目录和目标分支的短生命周期锁仅保护占用重读、更新、检出决定和提交回读：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:389`、`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:2193`。
- 源分支删除失败后，仅当当前目标分支、本地引用和本次远端快照一致时接受重试：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:2144`。
- 实现保持单次 `fetch`（拉取）远端快照边界，未增加 cleanup（清理）路径中的 `git pull`（拉取）、依赖、配置或跨工作树写入。
- 本 Tweak（小改）以 `openspec/changes/return-cleanup-to-base-branch/design.md`（OpenSpec 设计）作为设计依据；独立 Superpowers Design Doc（超级能力设计文档）不是该预设流程产物。

## 验证证据

执行于 2026-07-22：

```text
openspec validate return-cleanup-to-base-branch --strict --no-interactive
Change 'return-cleanup-to-base-branch' is valid

python .build-and-verify/runtime/build_and_verify.py build --project .
status: passed

python .build-and-verify/runtime/build_and_verify.py verify --project . --full
status: passed
```

完整 build-and-verify（构建与验证）结果：

- 69 项本地构建契约检查通过。
- 284 项 Agent Guard（代理守卫）检查通过。
- 58 项 Release Flow（发布流程）检查通过。
- 213 项 PR Flow（拉取请求流程）检查通过。
- 215 项 Cross-Agent Review（跨代理审查）检查通过。
- 204 项 build-and-verify（构建与验证）检查通过。
- 16 项 OpenSpec（开放规格）检查通过，其中包含本 change（变更）。

## 非阻断观察

Agent Guard（代理守卫）端到端检查仍出现 6 条既有 Windows（视窗）子进程 UTF-8（统一编码）读取警告；完整验证退出成功，且该警告在本 change（变更）前已存在，不是本次行为偏差。
