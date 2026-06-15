---
name: agent-guard-install
description: 安装守卫：调研被守卫对象，生成或更新未初始化的 Guard Profile（守卫画像）草案，并校验草案。Use when 用户要安装守卫、生成画像草案、更新画像草案或提取新的守卫模型。
---

# agent-guard-install

用于把用户需求安装成一个已校验的 Guard Profile（守卫画像）草案。

立即执行：在调研、生成或更新任何 Guard Profile（守卫画像）前，使用 Skill 工具加载 `$grill-with-docs`。禁止跳过此步骤。

## 边界

- 只生成或更新画像草案。
- 不写目标项目。
- 不初始化 `.agents/guards/<id>/`。
- 不安装 Hook（钩子）。
- 没有本轮已确认的 `confirmed-notes.yaml` 时，不得生成、更新或校验为可初始化画像。

## 流程

1. 加载 `$grill-with-docs` 并完成被守卫对象调研。
2. 确认 `confirmed-notes.yaml` 中 `grill_with_docs.status: confirmed`。
3. 读取 `references/research-and-extract.md`，使用 `../agent-guard/scripts/extract_guard_model.py` 生成或更新 Guard Profile（守卫画像）草案。
4. 读取 `references/profile-draft.md`，运行 `../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>` 校验草案。
5. 输出草案路径、校验结果和仍需用户确认的风险。
