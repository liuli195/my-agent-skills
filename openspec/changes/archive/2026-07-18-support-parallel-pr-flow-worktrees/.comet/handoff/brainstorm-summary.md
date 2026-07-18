# Brainstorm Summary

- Change: support-parallel-pr-flow-worktrees
- Date: 2026-07-18

## 确认的技术方案

- OpenSpec（开放规格）是需求事实源，当前交接包哈希为 `441c17c22d300c23253e6181953f30d273f86c0078c1cc0fa96fe7a556c2c4e1`。
- 采用现有脚本内的最小共享函数方案：只在 `pr_flow.py` 中增加工作树解析、状态路径、文件锁、远端快照和安全删除函数，不拆模块、不新增运行时层或第三方依赖。
- `main` 在分发 complete（完整流程）、tweak（小改）、cleanup（清理）或 hotfix（热修复）前，按规范工作树路径取得 common Git dir（共享 Git 目录）中的单个非阻塞文件锁；内部 cleanup（清理）直接复用外层锁。
- diagnose（诊断）只探测锁及读取持锁者元数据，不写运行状态；竞争修改命令直接输出 `flow_locked`，不经过会写文件的 `stop` 路径。
- `write_status` 保留 `.pr-flow/last-status.json`，并把同一载荷写入按源分支哈希命名的 `.pr-flow/runs/<branch-key>.json`；上下文由现有 Git（版本控制）命令和当前详情补齐。
- 一个远端提交快照函数复用现有 hotfix（热修复）读取逻辑；complete（完整流程）和 tweak（小改）在任何远端修改前验证目标基线，门禁后通过 PR（拉取请求）的 `headRefOid`、`baseRefOid` 再复核。
- required checks（必需检查）直接使用 `gh pr checks --required --json ...`；不建立第二套检查模型。
- cleanup（清理）通过 `git worktree list --porcelain -z` 识别占用，定位到最新远端目标提交的 detached HEAD（分离头）后按实时 Git（版本控制）状态删除源分支；显式删除工作树调用原生命令并回读清单。

## 关键取舍与风险

- 继续扩展现有大脚本，但用相邻的小函数集中共享规则；只有出现第二个消费者时才考虑拆模块。
- 锁文件是否存在不代表占用，只以操作系统加锁结果为准；进程退出后锁自动释放。
- 目标基线落后沿用 `base_outdated`，源提交变化沿用 `head_moved`，检查等待沿用 `checks_pending`，其他检查阻断沿用 `checks_or_review_blocking`。
- cleanup（清理）部分失败后根据实时 Git（版本控制）状态重试，不保留步骤检查点。
- 目标提交仍可能在最后复核与 GitHub（代码托管平台）合并调用之间变化；不新增平台适配层，最终由现有合并门禁裁决。

## 测试策略

- 定向测试继续放在 `tests/test_pr_flow_cli.py`，复用现有命令替身和裸仓库夹具，覆盖状态隔离、锁竞争、门禁顺序、提交变化、清理重试及显式删除。
- 端到端回归使用真实裸远端、两个关联工作树和独立子进程，GitHub（代码托管平台）交互沿用现有假命令；使用事件文件同步并发时点，不依赖固定等待时间。
- 破坏性删除至少验证主工作树、脏工作树、不使用强制参数、外部删除回读和 hotfix（热修复）同步条件。
- 完整验证使用仓库现有 Build and Verify（构建与验证）入口，并运行 Plugin（插件）打包测试与 OpenSpec（开放规格）严格校验。

## Spec Patch

无。
