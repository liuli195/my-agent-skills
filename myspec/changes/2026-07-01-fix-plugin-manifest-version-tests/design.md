## Context

`pr-flow`（拉取请求流程）和 `build-and-verify`（构建与验证）插件 manifest（清单）版本已经由 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json` 声明。对应测试又维护 `PLUGIN_VERSION`（插件版本）常量，形成第二份版本来源。

## Goals / Non-Goals

**Goals:**

- 删除测试里的第二份 manifest version（清单版本）常量。
- 保留双端 manifest（清单）一致性检查。
- 复用当前测试 helper（辅助函数）和 JSON（数据格式）读取能力。

**Non-Goals:**

- 不新增版本注册表。
- 不改变 manifest（清单）内容。
- 不修改发布流程。

## Decisions

- 测试读取 Codex（代码助手）和 Claude（代码助手）manifest（清单）后逐字段断言。理由：真实版本只在 manifest（清单）里维护。
- `version`（版本）只断言两份 manifest（清单）相等，不断言具体版本字符串。理由：版本提升只需要改发布 manifest（清单）。

## Risks / Trade-offs

- [Risk] 测试不再固定某个具体版本字符串。Mitigation: release-flow（发布流程）preflight（发布前检查）已经负责发布版本匹配；包测试只负责结构和双端一致性。
