---
name: agent-guard-hooks
description: 接入 Hook（钩子）：dry-run、安装或验证 Agent Guard Plugin（代理守卫插件）提供的 lifecycle Hook（生命周期钩子）。Use when 用户要安装、验证、检查、接入或排查 Agent Guard Hook。
---

# agent-guard-hooks

用于接入或验证 Hook（钩子）。

立即执行：安装或验证 Hook（钩子）前，读取 `references/hook-install.md`。禁止跳过此步骤。

## 边界

- Hook（钩子）只捕获事件、标准化事件并调用 Runtime（运行时）。
- Hook（钩子）不写业务规则。
- Hook（钩子）不创建 Guard Instance（守卫实例）。
- Hook（钩子）不推进状态。
- 默认 dry-run（试运行）；只有用户明确授权才安装。

## 流程

1. 读取 `references/hook-install.md`。
2. 需要理解事件适配时，读取 `references/hook-adapter.md`。
3. 需要理解 Runtime（运行时）返回结果时，读取 `references/hook-results.md`。
4. 运行 `../agent-guard/scripts/install_agent_guard_plugin.py dry-run --target <codex|claude|all>` 查看 dry-run。
5. 用户明确授权后才运行 `install --target <codex|claude|all> --authorize-install`。
6. 验证时使用 `verify --target <codex|claude|all>`。
7. 输出 Plugin（插件）安装位置、marketplace（市场）入口、Hook（钩子）能力和风险提示。
