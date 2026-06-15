# Init Boundaries（初始化边界）

初始化是第一次创建运行位置，不是升级、覆盖或 Hook（钩子）安装。

## 允许

- 复制已校验 Guard Profile（守卫画像）草案。
- 写入项目级或用户级画像说明。
- 输出初始化说明和后续接入建议。

## 禁止

- 不重新调研。
- 不改写被守卫对象。
- 不安装 Hook（钩子）。
- 不复制 Runtime code（运行时代码）到目标项目。
- 不预建 `.local/guard/*` 运行态目录。
- 不把任意既有 Guard Profile（守卫画像）目录当作合法输入。
- 不新增或改写 `deny` 状态权限；`deny` 只能来自草案中的 `states[].permissions` 明确声明。

## 已存在处理

已有同名画像默认 `abort`（中止）。只有用户明确选择更新流程时，才转到 `$agent-guard-update` 使用 `--on-existing update`。

`.local/guard/state/`、`.local/guard/session-focus/`、`.local/guard/session-observations/`、`.local/guard/audit/` 和 `.local/guard/locks/` 是运行时路径，由 Plugin Runtime（插件运行时）按需创建。
