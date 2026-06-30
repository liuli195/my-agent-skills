# 验证报告：fix-agent-guard-plugin-manifest-paths

- 日期：2026-06-17
- Change：fix-agent-guard-plugin-manifest-paths
- 验证模式：light（手动覆盖；规模评估误判为 full，实际实现改动仅 3 文件）
- 分支：fix/agent-guard-plugin-manifest-paths
- Base：b62cad6 / Head：804b797

## 修复概述

agent-guard 插件两份清单（`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`）的 `hooks`、`skills` 路径字段缺少 `./` 前缀，导致：

- Claude Code：`/hooks` 安装校验失败（`hooks: Invalid input, skills: Invalid input`），无法安装。
- Codex CLI：解析器 `strip_prefix("./")` 失败，字段被忽略，靠默认目录扫描兜底（audit 日志确认 hook 仍在跑）。

修复：为两份清单的 `hooks`、`skills` 补 `./` 前缀，并同步测试断言。修复后路径解析指向同一文件，不改变实际加载位置。

## 实际改动文件（排除 change 产物）

| 文件 | 改动 |
|------|------|
| `plugins/agent-guard/.claude-plugin/plugin.json` | `hooks`/`skills` 加 `./` 前缀 |
| `plugins/agent-guard/.codex-plugin/plugin.json` | 同上 |
| `tests/test_agent_guard_plugin_package.py` | 第 62-63 行断言改为 `./hooks/hooks.json` |

## Light 验证 6 项检查

| # | 检查项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | tasks.md 全部完成 | PASS | 4/4 `[x]`，0 未完成 |
| 2 | 改动与 tasks 一致 | PASS | `git diff main...HEAD`：3 文件，改动内容与 tasks 描述一致 |
| 3 | 构建/测试通过 | PASS | `python -m pytest tests/ -q` → 81 passed |
| 4 | 相关测试通过 | PASS | agent-guard 相关 81 项全过 |
| 5 | 无安全问题 | PASS | 静态路径字面量，无密钥、无 unsafe、无路径穿越（无 `..`/动态拼接） |
| 6 | 简化代码审查 | PASS | 审查范围：正确性/安全/边界。结论 Ready to proceed，无 Critical/Important |

## 简化代码审查结论

- Critical：无
- Important：无
- Minor（可选，未采纳）：`"skills": "./skills"` 缺尾斜杠，agentmemory 实证用 `"./skills/"`。两形式功能等价（均解析到同一目录），无缺陷，测试通过，保持现状以维持最小修复范围。

Windows 路径解析复核：`./` 前缀在 Windows 无副作用，清单用正斜杠，两端宿主均能规范化。

## 根因消除确认

`grep '"(hooks\|skills)":'` 两份清单均带 `./` 前缀，无残留无前缀路径。

## 结论

验证通过，无 CRITICAL 或 IMPORTANT 问题，可进入归档前最终确认。
