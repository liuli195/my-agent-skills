# Plugin Runtime Update（插件运行时更新）

Runtime code（运行时代码）随 Agent Guard Plugin（代理守卫插件）安装和更新，不复制到目标项目。

## 命令

```powershell
python ../agent-guard/scripts/install_agent_guard_plugin.py dry-run --target <codex|claude|all> --scope <personal|repo|all> --codex-repo-marketplace <repo-root>/.agents/plugins/marketplace.json --claude-repo-marketplace <repo-root>/.claude-plugin/marketplace.json --codex-personal-marketplace <codex-personal>/.agents/plugins/marketplace.json --claude-personal-marketplace <claude-personal>/.claude-plugin/marketplace.json
```

默认 dry-run（试运行），只输出将更新的 Plugin（插件）目标位置、marketplace（市场）入口和 Hook（钩子）能力。只有用户明确授权时才运行：

```powershell
python ../agent-guard/scripts/install_agent_guard_plugin.py install --target <codex|claude|all> --scope <personal|repo|all> --codex-repo-marketplace <repo-root>/.agents/plugins/marketplace.json --claude-repo-marketplace <repo-root>/.claude-plugin/marketplace.json --codex-personal-marketplace <codex-personal>/.agents/plugins/marketplace.json --claude-personal-marketplace <claude-personal>/.claude-plugin/marketplace.json --authorize-install
```

发布后使用 marketplace subscription（市场订阅）：

```powershell
codex plugin marketplace add <owner>/<repo> --ref marketplace
claude plugin marketplace add <owner>/<repo>@marketplace
```

## 边界

- 只更新用户级 Plugin（插件）文件和 marketplace（市场）入口。
- 不复制 Runtime code（运行时代码）到目标项目。
- 不写目标项目 Hook（钩子）或 Git 配置。
- 保留 Guard Profile（守卫画像）。
- 保留 `.local/guard/*` 运行态、Session Focus Binding（会话焦点绑定）、确认记录和人工覆盖记录。

验证使用：

```powershell
python ../agent-guard/scripts/install_agent_guard_plugin.py verify --target <codex|claude|all> --scope <personal|repo|all> --codex-repo-marketplace <repo-root>/.agents/plugins/marketplace.json --claude-repo-marketplace <repo-root>/.claude-plugin/marketplace.json --codex-personal-marketplace <codex-personal>/.agents/plugins/marketplace.json --claude-personal-marketplace <claude-personal>/.claude-plugin/marketplace.json
```
