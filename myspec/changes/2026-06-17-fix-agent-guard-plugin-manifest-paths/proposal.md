## Why

通过 Claude Code `/hooks` 安装 agent-guard 插件时失败，报错：

```
Validation errors: hooks: Invalid input, skills: Invalid input
```

根因：`.claude-plugin/plugin.json` 和 `.codex-plugin/plugin.json` 两个清单的 `hooks`、`skills` 路径字段缺少 `./` 前缀。

Claude Code 与 Codex CLI 都要求清单路径字段必须以 `./` 开头（相对插件根）：

- Claude Code：官方文档 `Path behavior rules` 明确规定，且本地已成功安装的 agentmemory 插件实证使用 `"./skills/"`；当前无前缀路径直接触发清单校验失败，安装被拒。
- Codex CLI：官方 spec 规定路径应以 `./` 开头，解析器源码 `manifest.rs` 用 `strip_prefix("./")` 解析，缺前缀则 `warn` 并忽略该字段。Codex 桌面端当前 hook 能跑，是默认目录扫描（`hooks/hooks.json` 约定位置）兜底的结果，manifest 字段本身是无效死字段。

## What Changes

为两份清单的 `hooks`、`skills` 字段补上 `./` 前缀，并同步更新断言该字段的测试：

- `plugins/agent-guard/.claude-plugin/plugin.json`：`hooks` → `./hooks/hooks.json`，`skills` → `./skills`
- `plugins/agent-guard/.codex-plugin/plugin.json`：同上
- `tests/test_agent_guard_plugin_package.py`：更新 `hooks` 字段断言为 `./hooks/hooks.json`

修复后路径解析指向同一文件（`hooks/hooks.json`、`skills/`），不改变实际加载位置，仅使清单字段符合两端校验规则。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。本修复不改变 spec 级验收场景：`agent-guard-plugin-runtime` 规格要求"只注册 `SessionStart` 和 `PreToolUse` lifecycle hooks"，`hooks/hooks.json` 内容本身一直符合该要求，本次仅修正清单路径字段格式。

## Impact

- 受影响代码：agent-guard 插件两份清单 + 一个测试文件。
- 影响：Claude Code 可正常安装该插件；Codex 从"靠默认目录扫描兜底"变为"manifest 字段正确生效"，无行为回归。
- 不涉及接口、架构、依赖或数据库变更。
