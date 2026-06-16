# Issue #18: 拆分 agent-guard 技能入口

GitHub Issue: https://github.com/liuli195/my-agent-skills/issues/18

后续调整：Issue [#31](https://github.com/liuli195/my-agent-skills/issues/31) 已决定 MVP 删除独立 `$agent-guard-hooks` 入口。当前保留 4 个场景入口：`$agent-guard-install`、`$agent-guard-init`、`$agent-guard-update`、`$agent-guard-run`。

## 已确认方案

把当前统一的 `$agent-guard` Skill（技能）拆成 4 个按使用场景触发的入口，并保留旧 `$agent-guard` 作为薄路由入口。

新入口：

- `$agent-guard-install`：安装守卫。调研被守卫对象，生成或更新 Guard Profile（守卫画像）草案，并校验草案；不写目标项目，不初始化，不安装 Hook（钩子）。
- `$agent-guard-init`：初始化守卫。第一次创建项目级或用户级运行位置，写入已校验 Guard Profile（守卫画像）和 Guard Runtime（守卫运行时）；已存在时默认中止。
- `$agent-guard-update`：更新守卫。维护已初始化守卫，升级 Guard Runtime（守卫运行时）或同步已校验 Guard Profile（守卫画像）；未初始化时默认中止，不改画像业务语义。
- `$agent-guard-run`：运行守卫。激活 Guard Instance（守卫实例）、读取 Guard Brief（守卫简报）、提交标准事件并处理状态推进结果。

旧 `$agent-guard` 只负责识别用户意图并路由到上述入口；意图不明确时先询问，不直接执行完整流程。

## 目录结构

```text
plugins/agent-guard/skills/
  agent-guard/
  agent-guard-install/
  agent-guard-init/
  agent-guard-update/
  agent-guard-run/
```

插件包内的 `agent-guard` 保留共享 `scripts/`、`assets` 和通用 `references/`。4 个入口包含 `SKILL.md` 和自己的场景化 `references/`，通过相对路径引用共享脚本和模板，不复制共享脚本或模板目录。

## 验收口径

- [ ] 新增 4 个场景入口，且每个入口的 `description` 只触发自己的场景。
- [ ] 旧 `$agent-guard` 改为薄路由入口，列出路由表和模糊意图处理规则。
- [ ] 共享 `scripts/`、`assets/` 只保留在 `plugins/agent-guard/skills/agent-guard/`，场景文档放在对应入口的 `references/` 中。
- [ ] 用户级安装脚本同步 5 个 Skill 目录：共享核心入口加 4 个场景入口。
- [ ] 安装验证确认共享核心资源完整、4 个入口存在、入口文档存在，且入口不复制共享脚本和模板。
- [ ] AGENTS/CLAUDE 或相关文档说明 4 个入口名称、适用场景和旧入口兼容策略。
- [ ] 增加测试或验证脚本覆盖入口存在、共享资源可达、旧入口薄路由有效。

## 不进入本 issue

- 不拆出架构/术语查询入口。
- 不拆出用户级 Skill 安装或 Codex/Claude 兼容入口。
- 不修改 Guard Runtime（守卫运行时）业务语义。
