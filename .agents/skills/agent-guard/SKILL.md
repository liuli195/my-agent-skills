---
name: agent-guard
description: 生成、激活、安装和维护解耦的 Agent Guard（代理守卫）系统。用于用户要求守卫 Skill（技能）、workflow（工作流）、node（节点）、command（命令）、artifact lifecycle（产物生命周期）、Codex lifecycle behavior（Codex 生命周期行为）、PR review order（PR 审查顺序）、Hook enforcement（钩子强制执行）、Guard Injection（守卫注入）或 Guard Profile（守卫画像）时。
---

# agent-guard

使用此 Skill（技能）创建和维护解耦的 Guard Runtime（守卫运行时）与 Guard Profile（守卫画像）系统。

核心规则：

- 生成守卫配置前，先调研被守卫对象。
- 不修改被守卫的 Skill（技能）、workflow（工作流）或目标对象。
- 业务规则写入 Guard Profile（守卫画像），不要写入 Hook（钩子）或 Runtime（运行时）。
- 安装 Hook（钩子）前必须获得用户明确授权。
- 启用 blocking mode（阻断模式）前必须获得用户明确授权。
- 初始化项目级或用户级 Guard Profile（守卫画像）前必须获得用户明确授权。

核心流程：

1. 识别请求：确认用户是在生成、激活、安装、升级还是校验 Agent Guard（代理守卫）。普通模糊话术不能创建强约束 Guard Instance（守卫实例）。
2. 调研对象：读取 `references/extraction-method.md`，用 `$grill-with-docs`（带文档拷问方法）提炼被守卫对象、术语、边界、状态、证据和例外。
3. 生成草案：如果已有 `$grill-with-docs`（带文档拷问方法）确认记录，使用 `extract_guard_model.py` 转成 Guard Profile（守卫画像）草案和 Implementation Plan（实施计划）；不要在提取器里直接采访用户。
4. 选择产物：按调研结果决定生成或更新 Guard Profile（守卫画像）、项目级 Guard Runtime（守卫运行时）骨架、Hook Binding（钩子绑定）、Guard Brief（守卫简报）模板或 Validation Plan（验证计划）。
5. 保持解耦：不要修改被守卫对象；业务规则只写入 Guard Profile（守卫画像），Runtime（运行时）和 Hook（钩子）只保留通用机制。
6. 先验后改：生成或修改画像后，运行 `validate_guard_profile.py <guard-profile-dir>` 校验文件、字段和引用。
7. 授权后执行：只有用户明确授权时，才初始化目标项目守卫、安装 Hook（钩子）或启用 blocking mode（阻断模式）。
8. 交付结果：说明生成了哪些产物、校验结果、仍需用户确认的术语或阻断策略。

按场景读取：

| 场景 | 读取 | 入口 |
| --- | --- | --- |
| 理解系统边界 | `references/architecture.md`、`references/terminology.md` | 无 |
| 调研被守卫对象并生成草案 | `references/extraction-method.md` | `scripts/extract_guard_model.py` |
| 编写或校验 Guard Profile（守卫画像） | `references/guard-profile.md` | `scripts/validate_guard_profile.py` |
| 初始化、激活或运行 Guard Runtime（守卫运行时） | `references/runtime-contract.md` | `scripts/init_project_guard.py`、`scripts/init_user_guard.py`、`scripts/activate_guard.py`、`scripts/run_guard_event.py` |
| 解析 Guard Instance（守卫实例）身份 | `references/subject-resolution.md` | 由 Runtime（运行时）调用 |
| 安装或验证 Hook（钩子） | `references/hook-contract.md` | `scripts/install_hooks.py` |
| 读取或注入 Guard Brief（守卫简报） | `references/guard-injection.md` | `scripts/render_guard_brief.py` |
| 校验或安装用户级 Skill（技能）并兼容 Claude（Claude 代理） | `references/codex-claude-compat.md` | 源码仓库根目录的 `scripts/install/*.ps1`、`scripts/install/verify_install.py` |

命令参数和输出契约以对应 reference（参考文档）为准。不要为了一个场景读取无关 reference。
