# 01 — 修复 PR Flow 工作树实体清理

**What to build:** 让用户通过 PR Flow（拉取请求流程）显式删除关联工作树时，无论 Git（版本管理）还是 Orca（工作树管理器）负责删除登记，都能完成目标实体工作树目录清理，并只在登记和实体目录均消失后报告完成。

**Blocked by:** None — can start immediately

**Status:** completed

- [x] 统一 Git/Orca 删除后的工作树删除后置条件；登记仍存在时不得删除实体目录。
- [x] 使用 Python 标准库完成残留目标目录删除，保留共享目录联接点指向的主工作树依赖目录。
- [x] 删除失败时返回非零停止状态，不输出 `cleanup_complete`，不在已注销目标内重建 `.pr-flow`，并提供外部恢复动作。
- [x] 通过真实 Windows 公共清理入口验证 Git 路径、目录联接点、目标目录消失和共享哨兵保留。
- [x] 验证 Orca 路径、脏工作树、主工作树、默认不删除和既有长路径行为保持兼容。

## Behavior evidence（行为证据）

- Red（红灯）：修复前真实 Windows 探针中，`git worktree remove` 返回 0、Git 登记消失，但目标目录仍保留两个 Junction；断言目标不存在失败。
- Green（绿灯）：`python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py` 通过，285 项通过；Junction 公开清理回归和 Orca 路径回归均通过。
- User-entry Smoke（用户入口冒烟）：`test_cleanup_removes_junction_residue_without_shared_targets` 通过；目标目录和 Git 登记消失，主工作树共享 `.venv`、`node_modules` 哨兵保留。
- Failure behavior（失败行为）：物理删除失败时状态写入控制工作树，目标不重建 `.pr-flow`，输出 `physical_worktree_remove_failed` 和可执行 `rmdir` 恢复命令。
- Fast Verification（快速验证）：`build-and-verify verify --project . --base 34b74c105fc7b5e04e966a38397e9ed03fb7c98c` 通过，`checked` 非空，状态为 `passed`。
- Build（构建检查）：`build-and-verify build --project .` 通过。
- Review（审查）：Standards（规范）审查无硬性违规；Spec（规格）初审发现 Orca 真实 Junction 验证和恢复命令表达不足，已修复；定向复审结论为无阻塞发现。
- Unresolved risk（未解决风险）：完整验证未运行；标准库删除失败后的真实文件锁场景未在本机强制制造，但失败状态和恢复路径已有回归覆盖。
