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

## Guard Runtime（守卫运行时）

- `assets/templates/guard-runtime/guard_runner.py`：项目级 Runtime（运行时）统一 CLI（命令行接口）。
- `assets/templates/guard-runtime/hook_event_adapter.py`：Hook（钩子）事件到标准事件 envelope（信封）的适配器。

使用规则：

- Runtime（运行时）只执行通用机制，不写具体业务规则。
- Runtime（运行时）骨架由初始化或更新脚本复制，入口文档只引用模板，不复写实现。

## Hook（钩子）

- `assets/templates/codex-hooks/hooks.json`：Codex Hook（Codex 钩子）安装模板。
- `assets/templates/git-hooks/pre-push`：Git `pre-push` hook（推送前钩子）模板。

使用规则：

- Hook（钩子）只捕获和标准化事件。
- Hook（钩子）拒绝外部动作只能来自 Runtime（运行时）返回的 `deny`。
- Hook（钩子）不创建 Guard Instance（守卫实例），不推进状态。
