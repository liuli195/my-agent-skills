---
comet_change: support-parallel-pr-flow-worktrees
role: technical-design
canonical_spec: openspec
---

# PR Flow 多工作树并行技术设计

## 背景

PR Flow（拉取请求流程）当前把调用目录、`.pr-flow/last-status.json` 和单工作树分支切换当作隐含前提。多个关联工作树并行执行时，这些前提会造成状态覆盖、重复修改、过期目标基线被继续使用，以及 cleanup（清理）切换已被其他工作树占用的目标分支。

OpenSpec（开放规格）继续作为需求事实源。本设计只细化实现结构、数据流、错误恢复和测试策略，不创建第二份需求规格。

## 设计原则

- 只修改现有 `pr_flow.py` 和相关 Skill（技能）说明，不拆出新运行模块。
- 复用现有 Git（版本控制）封装、GitHub CLI（GitHub 命令行工具）封装、停止状态和恢复动作。
- 使用 Python（编程语言）标准库和 Git（版本控制）原生命令，不新增依赖或配置。
- 不增加全局锁、共享 Runtime（运行时）、自动变基、自动合并目标基线或冲突解决。
- 修改命令在一个工作树内串行，不同工作树保持并行。

## 命令分发与工作树锁

### 工作树身份

命令入口先通过 Git（版本控制）解析：

- 规范化的工作树绝对路径；
- common Git dir（共享 Git 目录）；
- 当前源分支和当前提交；
- 配置中的目标分支与对应远端。

路径先解析为绝对路径；Windows（微软操作系统）再使用大小写无关的规范形式参与哈希。`worktree-key` 直接使用 `hashlib.sha256` 对规范工作树路径计算，不引入身份类或注册表。

### 锁位置与生命周期

complete（完整流程）、tweak（小改）、cleanup（清理）和 hotfix（热修复）由 `main()` 在命令分发前获取：

```text
<common-git-dir>/pr-flow-locks/<worktree-key>.lock
```

锁覆盖整个修改命令。complete（完整流程）和 tweak（小改）在合并后直接调用内部 cleanup（清理）函数，因此继续处于同一个外层锁内，不重复获取锁。

锁为非阻塞操作系统文件锁：

- Windows（微软操作系统）使用 `msvcrt.locking`；
- 其他平台使用 `fcntl.flock`；
- 锁文件存在不代表占用，以实际加锁结果为准；
- 进程退出时操作系统释放锁，文件可保留复用。

持锁者在进入命令主体前写入并刷新最小元数据：命令、工作树、源分支、进程号、actor（执行者）和重试命令。竞争修改命令拿锁失败后只读取这些信息，直接输出 `DISPATCH_REQUIRED / flow_locked`（需要外部进展 / 流程已锁定），不调用会写状态的 `stop()`。

diagnose（诊断）只探测锁并读取元数据。发现活动锁时不写 `.pr-flow/runs/` 或 `.pr-flow/last-status.json`；无活动锁时保留现有诊断状态写入行为。

## 运行状态隔离

`write_status()` 保留现有兼容输出：

```text
.pr-flow/last-status.json
```

同时把相同载荷写入：

```text
.pr-flow/runs/<branch-key>.json
```

`branch-key` 使用 `hashlib.sha256` 对源分支名计算。源分支优先从当前流程详情中的 `sourceBranch`、`headRefName` 或 `branch` 获取，再回退到当前 Git（版本控制）分支；cleanup（清理）进入 detached HEAD（分离头）后仍使用 PR（拉取请求）的源分支。

状态载荷在现有 `status`、`command` 和 `details` 外补齐：

- common Git dir（共享 Git 目录）；
- 规范工作树路径；
- 源分支与目标分支；
- 流程类型；
- PR（拉取请求，可为空）；
- 当前源提交与已读取的目标提交。

这些字段由现有 Git（版本控制）查询和命令详情组合生成，不新增状态对象层。锁竞争路径完全绕过 `write_status()`，避免覆盖持锁流程。

## 远端目标基线

现有 hotfix（热修复）目标读取逻辑收敛为一个远端提交快照函数：执行 `git fetch <remote> <branch>`，再解析 `<remote>/<branch>` 提交。diagnose（诊断）、complete（完整流程）、tweak（小改）和 hotfix（热修复）复用该函数。

complete（完整流程）和 tweak（小改）在自动推送、创建 PR（拉取请求）、修改正文、合并等远端修改之前验证：最新远端目标提交必须是当前源提交的祖先。失败时输出 `base_outdated`，包含源/目标提交和同步后重试命令；不额外预测冲突，也不修改源分支。只读的 PR（拉取请求）查询允许先执行。

hotfix（热修复）在完整验证前记录远端目标提交，在验证和当前会话授权后重新读取。目标已变化时停止并要求重新同步和完整验证；相等时才允许推送。推送后继续复用现有远端回读校验。

## PR 门禁与合并复核

`PR_VIEW_FIELDS` 增加 `baseRefOid`。进入门禁前记录 PR（拉取请求）的 `headRefOid` 和 `baseRefOid`。

required checks（必需检查）直接调用：

```text
gh pr checks <pr> --required --json bucket,name,state,workflow,link
```

处理规则：

- 返回集合必须非空；
- `pending` 使用现有 `checks_pending`；
- 空集合、缺失、`fail`、`cancel` 或无法绑定当前源提交的结果使用现有 `checks_or_review_blocking`；
- tweak（小改）只跳过 review gate（审查门禁），不跳过必需检查。

检查和 review gate（审查门禁）完成后再次读取 PR（拉取请求）。源提交变化沿用 `head_moved`；目标提交变化使本轮检查、审查和可合并结果失效，并按 `base_outdated` 要求重新运行。

最终合并继续使用 `gh pr merge --match-head-commit <head>` 固定源提交。GitHub CLI（GitHub 命令行工具）没有目标提交匹配参数，因此目标提交只保证在合并调用前完成最后复核；调用后的竞争由 GitHub（代码托管平台）现有分支规则或合并队列裁决，不增加平台适配层。

## 工作树发现与安全清理

### 工作树清单

工作树发现使用：

```text
git worktree list --porcelain -z
```

解析器按空字符读取记录和字段，保留工作树路径、提交、分支、detached（分离头）和 prunable（可清理）标记。所有路径规范化后再比较，以支持空格、中文和转义字符。

删除本地源分支前，检查除当前目标外的全部工作树；任何工作树仍检出 `refs/heads/<source>` 时，在删除远端或本地源分支前停止并报告占用路径。

### cleanup 清理顺序

cleanup（清理）先完成全部只读预检：

1. PR（拉取请求）已合并；
2. 工作区干净；
3. PR（拉取请求）源/目标分支有效且源分支不是目标分支；
4. 当前工作树仍位于源分支，或者是一次合法重试：已位于最新远端目标提交的 detached HEAD（分离头）；
5. 源分支未被其他工作树检出；
6. 最新远端目标提交可读取。

全部通过后依次执行：

1. 将当前工作树定位到最新远端目标提交的 detached HEAD（分离头）；
2. 远端源分支存在时删除并确认，不存在时视为已完成；
3. 本地源分支存在时使用安全删除，已不存在时视为已完成；
4. 写入最终目标提交和分离头状态。

不再记录 `completedCleanupSteps`（已完成清理步骤），也不保留“禁止重跑”恢复分支。失败后重新读取实时 Git（版本控制）状态：只有已确认完成的动作被跳过，新的不安全状态仍立即停止。

### 显式删除工作树

`--remove-worktree`（删除工作树参数）接入 cleanup（清理）、complete（完整流程）、tweak（小改）和 hotfix（热修复）：

- 默认未传参数时保留工作树；
- complete（完整流程）和 tweak（小改）把参数传给内部 cleanup（清理）；
- hotfix（热修复）只有推送回读成功且当前提交等于最新远端目标提交时才进入共享删除函数，不查询 PR（拉取请求）；
- 主工作树或脏工作树拒绝删除；
- 只调用原生 `git worktree remove <path>`，不传 `--force`；
- 删除后重新读取工作树清单，目标仍存在则报告失败。

命令从待删除工作树内部运行时，只完成安全收尾并输出一条带原参数的外部重试命令。从目标工作树外部通过 `--project`（项目路径参数）运行时，完成安全收尾后直接删除并核验工作树。

锁文件位于 common Git dir（共享 Git 目录），因此删除目标工作树时不会持有目标目录内的锁文件。

## 错误和恢复语义

- `flow_locked`：不等待、不写状态，输出活动流程、actor（执行者）和重试命令。
- `base_outdated`：不自动变基或合并，输出同步命令并要求重新运行。
- `head_moved`：废弃旧门禁结果，要求基于新源提交重新运行。
- `checks_pending`：保留等待恢复动作。
- `checks_or_review_blocking`：覆盖空、缺失、失败、取消或过期的必需检查，不新增原因代码。
- cleanup（清理）部分失败：根据实时分支和工作树状态重试，不覆盖其他工作树，不删除目标分支。
- hotfix（热修复）目标变化或回读不一致：禁止删除工作树，保留现有审计记录和重新完整验证要求。

## 测试设计

### 定向测试

继续扩展 `tests/test_pr_flow_cli.py`，复用现有 `CommandStub`（命令替身）、假 `gh`（GitHub 命令）和裸仓库模板：

- 两个工作树写入不同运行状态和锁；同一工作树的竞争命令不改写状态；diagnose（诊断）只读报告锁。
- 工作树清单解析覆盖带空格路径、分支占用和主工作树识别。
- `base_outdated` 在自动推送和其他远端修改前停止。
- 必需检查覆盖非空成功、空、缺失、等待、失败和过期；源/目标提交变化废弃旧结果。
- hotfix（热修复）覆盖验证期间目标推进、推送前停止、推送后回读，以及不查询 PR（拉取请求）的显式删除。
- cleanup（清理）覆盖主工作树、脏工作树、其他工作树占用源分支、进入分离头后的部分失败重试、默认保留、内部调用提示和外部删除回读。
- 所有工作树删除断言不出现 `--force`。

### 端到端回归

复用现有 `init_complete_project` 裸仓库夹具，创建两个关联工作树、两个源分支和各自独立的假 GitHub（代码托管平台）响应，并用独立子进程验证两个 complete（完整流程）可同时完成且状态互不覆盖。远端推进、失败、冲突、分支占用和显式删除继续由上方已有定向场景覆盖，避免在并发端到端测试中重复整套边界矩阵。

### 完整验证

- `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py`
- `python scripts/local_plugin_build.py`
- 仓库 Build and Verify（构建与验证）完整模式；
- `openspec validate --all --strict --no-interactive`

## 非目标

- 不拆分 `pr_flow.py`。
- 不新增配置、依赖或通用工作流运行框架。
- 不自动解决业务冲突。
- 不修改、清理或强制删除其他工作树中的用户改动。
- 不提供目标提交的服务端原子绑定保证。
