# Template Index（模板索引）

模板是文件形状、默认骨架和可复制内容的权威来源。reference（参考文档）只说明使用场景、边界和验证入口，不复写完整模板内容。

本文中的 `assets/...` 和 `scripts/...` 路径相对 `skills/agent-guard/`。各场景入口文档中的 `../agent-guard/...` 路径相对对应入口 Skill（技能）根目录。

## Guard Profile（守卫画像）

- `assets/templates/guard-profile/confirmed-notes.yaml`：调研确认记录输入模板。
- `assets/templates/guard-profile/minimal/`：最小可校验 Guard Profile（守卫画像）目录模板。
- `assets/templates/guard-profile/minimal/brief-template.md`：Guard Brief（守卫简报）默认模板。

使用规则：

- 新画像草案从已确认的 `confirmed-notes.yaml` 提取，不手写一份看似完整的画像。
- 画像字段结构以 `minimal/` 中的 YAML（YAML 配置格式）为基准。
- 校验以 `scripts/validate_guard_profile.py` 为准。

## Plugin Runtime（插件运行时）

- `scripts/install_agent_guard_plugin.py`：安装或验证 Agent Guard Plugin（代理守卫插件）的入口。
- `../../plugins/agent-guard/hooks/hooks.json`：Plugin（插件）发布的 `SessionStart` / `PreToolUse` lifecycle Hook（生命周期钩子）配置。
- `../../plugins/agent-guard/scripts/hook_router.py`：Hook Router（钩子路由器）。
- `../../plugins/agent-guard/scripts/guard_runtime/`：通用 Runtime code（运行时代码）。

使用规则：

- Runtime（运行时）只执行通用机制，不写具体业务规则。
- Runtime code（运行时代码）随 Plugin（插件）安装，不复制到目标项目。
- Hook（钩子）只捕获和标准化 `SessionStart` / `PreToolUse`。
- Hook（钩子）不创建 Guard Instance（守卫实例），不推进状态，不绑定 Guard Profile（守卫画像）。
