---
name: agent-guard-run
description: 运行守卫：激活 Session Focus Instance（会话焦点实例）、切换焦点、关闭实例、提交标准事件并处理状态推进结果。Use when 用户要运行、激活、切换、关闭、提交事件、推进一个已初始化守卫，或记录 guard-defined evidence（守卫定义证据）。
---

# agent-guard-run

用于运行已初始化的守卫。

立即执行：提交任何 `state_completed` 事件前，读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）。禁止跳过此步骤。

## 边界

- 如果还没有 Session Focus Instance（会话焦点实例），先激活。
- 如果已有 Session Focus Instance（会话焦点实例），按当前焦点提交事件。
- 提交 `state_completed` 前必须读取当前会话焦点实例的最新 Guard Brief（守卫简报）。
- 不安装 Hook（钩子）。
- Hook（钩子）不推进状态；状态推进只能由主 agent（主代理）主动提交标准事件。
- guard-defined evidence（守卫定义证据）只能在主 agent（主代理）完成语义判断后记录；Runtime（运行时）不承担业务判断。

## 流程

1. 确认 Agent Guard Plugin（代理守卫插件）已安装，目标项目已有 Guard Profile（守卫画像）。
2. 激活实例：如果没有 Guard Instance（守卫实例），读取 `references/activate.md`，运行 `../agent-guard/scripts/activate_guard.py`。
3. 读取简报：读取 `references/brief.md`，运行 `../agent-guard/scripts/render_guard_brief.py` 读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）。
4. 提交事件：提交任何 `state_completed` 前，先读取最新 Guard Brief（守卫简报），再按 `references/events.md` 准备事件。
5. 记录证据：需要写入 guard-defined evidence（守卫定义证据）时，主 agent（主代理）先完成语义判断，再按 `references/events.md` 调用 `record-evidence`。
6. 关闭实例：需要关闭 Guard Instance（守卫实例）时，读取 `references/close.md`，运行 Plugin Runtime（插件运行时）的 `close-instance` 命令。
7. Global Command Guard（全局命令守卫）拦截和排障按 `references/events.md` 处理。
8. 运行 `../agent-guard/scripts/run_guard_event.py` 并报告状态、审计位置和下一步。
