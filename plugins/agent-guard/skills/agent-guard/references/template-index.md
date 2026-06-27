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

## Global Command Guard（全局命令守卫）

- `assets/templates/guard-profile/minimal/global-command-guards.yaml`：命令级拦截配置示例。
- `assets/templates/guard-profile/minimal/artifacts.yaml`：artifact（产物）路径声明，用于把证据路径从守卫配置中抽离。

使用规则：

- install 阶段生成场景化配置，init 阶段发布配置，update 阶段同步已校验配置，run 阶段只按 Runtime（运行时）结果处理拦截；troubleshoot（排障）先看对应场景 reference。
- 如果上游流程已有稳定产物，拦截应引用 `artifacts.yaml` 中的原始 artifact（产物）路径，不复制或搬运临时 pass marker（通过标记）。
- 如果上游流程没有稳定产物，Agent Guard（代理守卫）可以在 `artifacts.yaml` 中定义 guard-defined evidence（守卫定义证据）默认路径：`.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`。该文件由主 agent（主代理）在上游检查通过后写入，Runtime（运行时）只负责读取和校验。
- `deny.reason`、`deny.next` 和 `deny.suggestion` 可以在 Guard Profile（守卫画像）中场景化配置；Runtime（运行时）只透传或渲染，不内置业务流程。
- 禁止新增 reviewed wrapper。
- 对真正已有的 external artifact（外部产物），禁止复制 pass marker（通过标记）到 `.local/guard/evidence` 绕过原始路径。
- 禁止把 `verify --apply` 作为主拦截点。
- 禁止在 Agent Guard 中实现 cross-agent-review 内部流程。

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
