# Tasks

- [x] 1. 修复 Claude 清单路径前缀：`plugins/agent-guard/.claude-plugin/plugin.json` 的 `hooks` 改为 `./hooks/hooks.json`、`skills` 改为 `./skills`
- [x] 2. 修复 Codex 清单路径前缀：`plugins/agent-guard/.codex-plugin/plugin.json` 同上
- [x] 3. 更新测试断言：`tests/test_agent_guard_plugin_package.py` 第 62-63 行 `hooks` 断言改为 `./hooks/hooks.json`
- [x] 4. 运行 agent-guard 相关测试与插件打包校验，确认通过
