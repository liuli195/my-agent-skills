## Context

当前最慢的测试集中在 build-and-verify（构建与验证）相关文件，但根因是仓库没有普通测试和 E2E（端到端测试）的边界。只优化单个文件会让未来测试重新引入真实 subprocess（子进程）、CLI（命令行）、临时 git（版本控制）仓库或 cache（缓存）扫描。

## Goals / Non-Goals

**Goals:**

- 建立全仓库测试运行边界。
- 只保留必要真实 E2E（端到端测试）。
- 将分支逻辑测试改为 in-process（进程内）和 fake runner（假执行器）。
- 防止未来普通测试重新引入高成本行为。

**Non-Goals:**

- 不新增性能测试框架。
- 不删除所有 E2E（端到端测试）。
- 不靠提高并行度作为根因修复。

## Decisions

1. 用一个仓库级守门测试扫描 `tests/`。

   扫描使用 Python AST（Python 语法树），按 test function identity（测试函数身份）归属发现直接或通过本仓库已有 helper（辅助函数）/ fixture（测试夹具）触发的 `subprocess`（子进程）、真实 CLI（命令行）入口、临时 git（版本控制）初始化和大范围 cache（缓存）扫描。无需新依赖。

2. 白名单按测试函数身份登记。

   allowlist（白名单）键使用 file path + qualified test function（文件路径加限定测试函数）格式，参数化测试按同一个 test function（测试函数）登记理由；不按文件放行，避免一个 E2E（端到端测试）文件继续堆入大量慢测试。

3. 先保留少量真实入口，再收缩重复分支测试。

   E2E（端到端测试）只证明发布形态可运行；逻辑分支用已有函数和 fake runner（假执行器）覆盖。build-and-verify（构建与验证）的真实 verify（验证）入口保留默认 fast verify（快速验证），full verify（完整验证）分支走进程内覆盖。

4. Full（完整验证）目标以整体耗时为准。

   `maxParallel`（最大并行检查数）固定为 `0`，保持与机器资源兼容；各 Pytest（测试工具）检查继续使用 `pytestXdistWorkers: "auto"`。runner（执行器）在外部未设置 `PYTEST_XDIST_AUTO_NUM_WORKERS`（Pytest 自动工作进程数）时，给并行检查里的 `auto` 加 4 个 worker（工作进程）的稳定上限，避免多个检查互相争抢 CPU（处理器）。优化重点放在删掉重复真实流程：PR Flow（拉取请求流程）、Release Flow（发布流程）、Cross Agent Review（跨代理审查）、Agent Guard（代理守卫）和 Build and Verify（构建与验证）的非必要 E2E（端到端测试）改为进程内或 fake runner（假执行器）。

5. 两个后续 OpenSpec（开放规格）脚手架随提交保留。

   用户授权当前 commit（提交）一起包含 `stabilize-flow-recovery-actions` 和 `stabilize-version-runtime-sync`。这两个目录只保存后续 change（变更）的 proposal/design/tasks/spec（提案/设计/任务/规格）草案，不作为 `guard-test-runtime-boundaries` 的实现完成项。

## Risks / Trade-offs

- [Risk] AST（语法树）扫描无法覆盖任意动态调用链 → 首版覆盖本仓库已有 helper（辅助函数）和 fixture（测试夹具）形态，新增绕过形态时扩展守门规则。
- [Risk] 过度限制真实集成覆盖 → 每个关键入口保留必要 E2E（端到端测试）。
- [Risk] 改测试时影响现有覆盖 → 先加守门，再逐步把重复慢路径迁到进程内测试。
- [Risk] Full（完整验证）耗时有运行波动 → 以新鲜完整验证结果为准，不靠提高并行度遮盖慢测试。
