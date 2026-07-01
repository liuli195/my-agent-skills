# fix-claude-agent-guard-duplicate-hooks 验证报告

日期：2026-06-18

## 结论

验证通过。根因已消除：Agent Guard Claude manifest 不再声明标准 `hooks/hooks.json`，避免 Claude 自动加载后再次通过 manifest 重复加载；Codex manifest 继续声明 `./hooks/hooks.json`。

## 验证摘要

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| Tasks | PASS | 5/5 tasks 已完成 |
| OpenSpec change | PASS | `openspec validate "fix-claude-agent-guard-duplicate-hooks" --strict` |
| OpenSpec specs | PASS | `openspec validate --specs --strict`，6 passed / 0 failed |
| Regression | PASS | 相关回归 72 passed |
| TDD RED | PASS | 定向测试先失败，失败点为 Claude manifest 仍含 `hooks` |
| TDD GREEN | PASS | 删除 Claude manifest `hooks` 后定向测试通过 |
| Diff check | PASS | `git diff --check` 无输出 |
| Code review | PASS | 轻量审查未发现正确性、安全或边界阻塞 |

## 执行命令

- `python -m pytest tests/test_agent_guard_plugin_package.py::test_plugin_manifests_are_valid_json -q`
  - RED：1 failed，断言 `"hooks" not in claude_manifest` 失败
  - GREEN：1 passed
- `python -m pytest tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_installer.py tests/test_release_flow_plugin_package.py tests/test_release_flow_cli.py -q`
  - 结果：72 passed
- `openspec validate "fix-claude-agent-guard-duplicate-hooks" --strict`
  - 结果：valid
- `openspec validate --specs --strict`
  - 结果：6 passed / 0 failed
- `git diff --check`
  - 结果：exit 0，无输出

## 实现对照

- `plugins/agent-guard/.claude-plugin/plugin.json`
  - 删除 `hooks: ./hooks/hooks.json`
- `plugins/agent-guard/.codex-plugin/plugin.json`
  - 保留 `hooks: ./hooks/hooks.json`
- `tests/test_agent_guard_plugin_package.py`
  - 固定 Codex manifest 继续声明 hooks
  - 固定 Claude manifest 不声明标准 hooks 文件
  - 固定插件包仍包含 `hooks/hooks.json`
- `openspec/changes/fix-claude-agent-guard-duplicate-hooks/specs/agent-guard-plugin-runtime/spec.md`
  - 记录平台 manifest 差异，避免后续回归

## 后续

归档后需要提交 hotfix，通过 PR 合并到 `main`，然后 bump 四个 plugin manifest 到 `0.1.4` 并发布两个插件。
