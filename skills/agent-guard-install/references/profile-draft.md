# Profile Draft（画像草案）

Guard Profile（守卫画像）草案是初始化输入，但不会写入目标项目。

## 模板来源

- 已确认调研输入：`../agent-guard/assets/templates/guard-profile/confirmed-notes.yaml`
- 最小画像骨架：`../agent-guard/assets/templates/guard-profile/minimal/`
- 简报模板：`../agent-guard/assets/templates/guard-profile/minimal/brief-template.md`

文件形状和默认字段以模板为准，不在本文重复字段清单。

## 校验

```powershell
python ../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>
```

校验必须在初始化或同步前通过。新 Guard Profile（守卫画像）不得在 `GUARD-MANIFEST.yaml` 中声明 `mode`；旧画像如包含 `mode`，必须迁移到 `states[].permissions`。

当 `source.kind` 是 `grill-with-docs-confirmed-notes` 时，`source.status` 必须是 `confirmed`。这表示本轮已先完成术语、决策、边界、场景、例外和文档变更确认。

## 边界

- 可以生成或更新画像草案。
- 可以生成 Implementation Plan（实施计划），说明后续初始化、Session Focus（会话焦点）和 Plugin Hook（插件钩子）接入步骤。
- 不初始化 `.agents/guards/<id>/`。
- 不安装 Hook（钩子）。
- 不修改被守卫对象。
- 不把任意既有目录当作合法草案；草案应来自本轮确认记录或已明确授权的更新输入。
