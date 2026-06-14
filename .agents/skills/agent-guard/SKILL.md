---
name: agent-guard
description: 生成、激活、安装和维护解耦的 Agent Guard（代理守卫）系统。用于用户要求守卫 Skill（技能）、workflow（工作流）、node（节点）、command（命令）、artifact lifecycle（产物生命周期）、Codex lifecycle behavior（Codex 生命周期行为）、PR review order（PR 审查顺序）、Hook enforcement（钩子强制执行）、Guard Injection（守卫注入）、Guard Brief（守卫简报）、Guard Runtime（守卫运行时）或 Guard Profile（守卫画像）时。
---

# agent-guard

使用此 Skill（技能）创建和维护解耦的 Guard Runtime（守卫运行时）与 Guard Profile（守卫画像）系统。

核心规则：

- 生成或更新 Guard Profile（守卫画像）前，先调研被守卫对象。
- 生成、更新或初始化 Guard Profile（守卫画像）时，如果本轮没有已确认的 `confirmed-notes.yaml`，必须先使用 `$grill-with-docs`（带文档拷问方法）完成调研确认；禁止直接生成画像、运行提取器或初始化。
- 不修改被守卫的 Skill（技能）、workflow（工作流）或目标对象。
- 业务规则写入 Guard Profile（守卫画像），不要写入 Hook（钩子）或 Runtime（运行时）。
- 安装 Hook（钩子）前必须获得用户明确授权。
- 初始化项目级或用户级 Guard Profile（守卫画像）前必须获得用户明确授权。
- 配置会拒绝操作的 `deny` 状态权限前必须获得用户明确授权。

处理流程：

1. 识别场景：确认用户是在生成、激活、安装、升级、校验还是排查 Agent Guard（代理守卫）。
2. 按场景读取：只读取下表对应 reference（参考文档）和入口脚本。
3. 生成、更新或初始化画像时：先确认本轮是否已有 `grill_with_docs.status: confirmed` 的 `confirmed-notes.yaml`；没有就先使用 `$grill-with-docs`（带文档拷问方法）调研。
4. 生成或更新画像时：读取 `references/extraction-method.md`，用已确认调研记录生成 Guard Profile（守卫画像）草案。
5. 修改画像后：运行 `validate_guard_profile.py <guard-profile-dir>` 校验文件、字段和引用。
6. 写入项目、用户级目录、安装 Hook（钩子）或配置会拒绝操作的 `deny` 状态权限前：先取得用户明确授权。
7. 交付结果：说明产物、校验结果和仍需确认的术语或权限策略。

按场景读取：

| 场景 | 读取 | 入口 |
| --- | --- | --- |
| 用户询问架构、术语或边界 | `references/architecture.md`、`references/terminology.md` | 无 |
| 调研被守卫对象并生成草案 | `references/extraction-method.md` | `scripts/extract_guard_model.py` |
| 编写或校验 Guard Profile（守卫画像） | `references/guard-profile.md` | `scripts/validate_guard_profile.py` |
| 初始化、激活或运行 Guard Runtime（守卫运行时） | `references/runtime-contract.md` | `scripts/init_project_guard.py`、`scripts/init_user_guard.py`、`scripts/activate_guard.py`、`scripts/run_guard_event.py` |
| 升级 Guard Runtime（守卫运行时） | `references/runtime-contract.md` | `scripts/upgrade_guard_runtime.py` |
| 解析 Guard Instance（守卫实例）身份 | `references/subject-resolution.md` | 由 Runtime（运行时）调用 |
| 安装或验证 Hook（钩子） | `references/hook-contract.md` | `scripts/install_hooks.py` |
| 读取或注入 Guard Brief（守卫简报） | `references/guard-injection.md` | `scripts/render_guard_brief.py` |
| 校验或安装用户级 Skill（技能）并兼容 Claude（Claude 代理） | `references/codex-claude-compat.md` | 源码仓库根目录的 `scripts/install/*.ps1`、`scripts/install/verify_install.py` |

命令参数和输出契约以对应 reference（参考文档）为准。不要为了一个场景读取无关 reference。
