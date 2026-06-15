---
name: agent-guard
description: 路由到具体 Agent Guard（代理守卫）场景入口。Use when 用户只说 agent-guard 或守卫，且没有明确 install/init/update/run/hooks 场景。
---

# agent-guard

这是 Agent Guard（代理守卫）的薄路由入口。只做场景识别和转发，不承载完整流程细节。

## 路由表

| 用户意图 | 转到 |
| --- | --- |
| 调研被守卫对象，生成或更新 Guard Profile（守卫画像）草案 | `$agent-guard-install` |
| 第一次初始化项目级或用户级守卫 | `$agent-guard-init` |
| 升级 Guard Runtime（守卫运行时），或同步已校验画像到已初始化守卫 | `$agent-guard-update` |
| 激活 Guard Instance（守卫实例）、读取 Guard Brief（守卫简报）、提交事件 | `$agent-guard-run` |
| dry-run、安装或验证 Codex Hook（Codex 钩子）和 Git Hook（Git 钩子） | `$agent-guard-hooks` |

## 规则

- 用户意图明确时，立即加载对应入口，不在本入口继续执行。
- 用户意图不明确时，先问一个简短问题确认要使用哪个入口。
- 中枢 `references/` 只保留通用概念和模板索引；场景流程在各入口自己的 `references/` 中。
- 共享 `scripts/` 和 `assets/` 仍在 `skills/agent-guard/` 下维护。
- 具体命令参数和输出契约以对应场景入口、共享模板和共享脚本为准。
