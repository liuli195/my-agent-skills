# Brainstorm Summary

- Change: fix-issues-122-123-124
- Date: 2026-07-01

## 确认的技术方案

本次修复三个 issue，采用删除和局部值更新为主：

- #122：直接删除 `cross-agent-review run --fake-reviewer-results`，不保留兼容参数、隐藏开关或环境变量。测试改用进程内 monkeypatch 注入 reviewer 输出。
- #123：升级现有 workflow 中已有的 Action 和 Node 版本引用。`checkout` 升到 v5，`setup-node` 升到 v6，`setup-python` 升到 v6，`full-verify` 的 Node 改为 24。CodeQL Action 保持 v4，因为没有 v5 主线。
- #123 验收必须扫描所有 active workflow 和 release-flow workflow template 的 `uses:` 与显式 runtime 版本；能升级的升级，不能升级的写明例外。
- #124：只改 `diagnose` 的下一步建议。缺 upstream 时输出 `DISPATCH_REQUIRED`、`reason: missing_upstream`，保留 branch/baseBranch，`nextCommand` 复用现有 `complete` PR body 命令格式。真正 push 仍由 `complete` 的既有安全逻辑处理。

## 关键取舍与风险

- 删除 fake reviewer 参数会改测试调用方式；这是预期破坏性修复。
- Action 主版本升级依赖现代 GitHub runner；本仓库使用 `ubuntu-latest`，风险低。
- 不复制 `complete` 的 push 逻辑到 `diagnose`，避免两个入口维护同一安全判断。

## 测试策略

- cross-agent-review：覆盖参数被拒绝、成功路径仍可通过 monkeypatch reviewer 输出、真实 dispatch 路径仍存在。
- workflow：文本检查所有 active workflow 和 release-flow template 不再出现旧值，并锁定 CodeQL v4 例外。
- PR Flow：覆盖 missing upstream、新 PR、已有 upstream 的 diagnose 输出，且 missing upstream 从 CLI 入口跑。
- 端到端回归：cross-agent-review run、release-flow workflow template/current workflow validation、PR Flow diagnose missing-upstream。
- 运行 OpenSpec strict 校验和受影响测试。

## Spec Patch

已回写 delta spec：

- `cross-agent-review`
- `release-flow-plugin`
- `local-plugin-build-checks`
- `pr-flow-plugin`
