# Agent Guard Marketplace Subscription 验证报告

## 结论

| 维度 | 状态 |
| --- | --- |
| Completeness（完整性） | PASS：15/15 OpenSpec tasks 已完成 |
| Correctness（正确性） | PASS：delta spec 场景均有实现和测试证据 |
| Coherence（一致性） | PASS：实现符合 OpenSpec design 和技术设计文档 |

最终评估：无 CRITICAL、IMPORTANT 或 WARNING 问题。可以进入 PR 和归档前确认。

## 验证命令

- `openspec validate --all --strict --json`：6 passed / 0 failed
- `C:\Users\liuli\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_agent_guard_plugin_installer.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_runtime_e2e.py -q`：24 passed
- `git diff --check`：通过
- targeted legacy scan：无 active docs/tests/scripts 把旧 user-level Skill installation 或 Claude Junction 当作当前 Agent Guard 发布入口

## 覆盖说明

- Marketplace subscription（市场订阅）：Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json` 均指向 `plugins/agent-guard`。
- Installer（安装器）：`--target codex|claude|all` 与 `--scope personal|repo|all` 分离处理；dry-run 默认不写入；install 需要 `--authorize-install`。
- Safety（安全边界）：installer 不初始化 Guard Profile（守卫画像）、不安装 project hooks（项目钩子）、不修改 git config（Git 配置）。
- Legacy removal（旧路径移除）：旧 `scripts/install/install_user_skill.ps1`、`sync_claude_junction.ps1`、`verify_install.py` 和 `tests/test_user_skill_install.py` 已删除。
- GitHub 发布分支：用户订阅说明使用 `marketplace` 分支，不使用 tag 或 commit 固定引用。

## 扫描残留分类

允许残留仅包括：

- 测试中断言旧脚本不存在。
- 当前 proposal/design/plan/spec 中作为迁移背景、删除说明或否定性契约出现。
- `docs/rules/index.md` 的仓库通用 user-level Skill 授权规则。
- `openspec/changes/archive/**` 的历史归档内容。
