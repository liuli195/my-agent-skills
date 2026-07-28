## 1. Regression Test

- [x] 1.1 更新 Agent Guard package 测试，覆盖 Claude manifest 不得声明标准 `hooks/hooks.json`。
- [x] 1.2 运行定向测试并确认它在当前实现下失败。

## 2. Fix

- [x] 2.1 从 Agent Guard Claude manifest 移除 `hooks` 字段，保留 Codex manifest hooks 字段。
- [x] 2.2 运行定向测试确认修复通过。

## 3. Verification

- [x] 3.1 运行 release-flow/agent-guard 相关回归、OpenSpec specs strict validation 和 diff 检查。
