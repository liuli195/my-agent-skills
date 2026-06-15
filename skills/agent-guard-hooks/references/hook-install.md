# Hook Install（钩子安装）

Hook（钩子）由 Agent Guard Plugin（代理守卫插件）发布。安装默认只做 dry-run（试运行），只有用户明确授权才写入用户级插件位置。

## 安装入口

```powershell
python ../agent-guard/scripts/install_agent_guard_plugin.py dry-run --target <codex|claude|all>
```

默认输出：

- Codex / Claude Plugin（插件）目标位置。
- marketplace（市场）入口位置。
- 将安装的 `SessionStart` / `PreToolUse` lifecycle Hook（生命周期钩子）。
- 不会写目标项目 Hook（钩子）或 Git 配置的安全说明。

只有显式传入 `install --target <codex|claude|all> --authorize-install` 时才会写入用户级插件位置。

## 验证入口

```powershell
python ../agent-guard/scripts/install_agent_guard_plugin.py verify --target <codex|claude|all>
```

验证必须确认：

- Plugin manifest（插件清单）存在且可解析。
- Hook（钩子）只声明 `SessionStart` 和 `PreToolUse`。
- Hook Router（钩子路由器）不接收 `--profile`。
- 不写目标项目 Hook（钩子）。
- 不写 Git Hook（Git 钩子）或 Git 配置。
