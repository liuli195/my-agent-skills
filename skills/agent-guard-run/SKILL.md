---
name: agent-guard-run
description: 运行守卫：激活 Guard Instance（守卫实例）、读取 Guard Brief（守卫简报）、提交标准事件并处理状态推进结果。Use when 用户要运行、激活、查看简报、提交事件或推进一个已初始化守卫。
---

# agent-guard-run

用于运行已初始化的守卫。

立即执行：提交任何 `state_completed` 事件前，读取最新 Guard Brief（守卫简报）。禁止跳过此步骤。

## 边界

- 如果还没有 Guard Instance（守卫实例），先激活。
- 如果已有 Guard Instance（守卫实例），先读取 Guard Brief（守卫简报）。
- 提交 `state_completed` 前必须读取最新 Guard Brief（守卫简报）。
- 不安装 Hook（钩子）。
- Hook（钩子）不推进状态；状态推进只能由主 agent（主代理）主动提交标准事件。

## 流程

1. 确认目标项目已有 Guard Runtime（守卫运行时）和 Guard Profile（守卫画像）。
2. 激活实例：如果没有 Guard Instance（守卫实例），读取 `references/activate.md`，运行 `../agent-guard/scripts/activate_guard.py`。
3. 读取简报：读取 `references/brief.md`，运行 `../agent-guard/scripts/render_guard_brief.py` 或项目级 `guard_runner.py brief`。
4. 提交事件：提交任何 `state_completed` 前，先读取最新 Guard Brief（守卫简报），再按 `references/events.md` 的标准事件运行规则准备事件。
5. 运行 `../agent-guard/scripts/run_guard_event.py` 并报告状态、审计位置和下一步。
