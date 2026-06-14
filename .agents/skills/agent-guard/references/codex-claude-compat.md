# Codex（Codex 代理）与 Claude（Claude 代理）兼容

当前以 Codex（Codex 代理）为主：

- 用户级源码维护在 `my-agent-skills/.agents/skills/agent-guard`。
- Codex（Codex 代理）通过显式 `$agent-guard`、`/skills` 或明确自然语言触发。
- Codex Lifecycle Hook（Codex 生命周期钩子）只作为可选接入点，安装前必须由用户授权。
- 当前仓库初始化不安装用户级 Skill（技能），不创建 Claude Junction（Claude 目录联接），也不初始化目标项目守卫。

以下命令都从 `my-agent-skills` 源码仓库根目录运行，不是从 `.agents/skills/agent-guard/` 目录运行。

用户级安装验证使用：

```powershell
python scripts\install\verify_install.py
```

该命令只读取状态并输出：

- `source_skill`：源码仓库里的 Skill（技能）骨架是否完整。
- `user_skill`：用户级 `.agents\skills\agent-guard` 是否存在且完整。
- `claude_junction`：Claude Junction（目录联接）是 `missing`、`wrong_target` 还是 `correct_target`。
- 安全声明：未初始化目标项目、未安装 Hook（钩子）。

用户级 Skill（技能）安装使用：

```powershell
scripts\install\install_user_skill.ps1
```

默认 dry-run（试运行），只有 `-AuthorizeInstall` 才同步文件。

Claude（Claude 代理）兼容通过 Junction（目录联接）复用同一份用户级 Skill（技能）：

```text
C:\Users\liuli\.claude\skills\agent-guard
  -> C:\Users\liuli\.agents\skills\agent-guard
```

Junction（目录联接）同步使用：

```powershell
scripts\install\sync_claude_junction.ps1
```

默认 dry-run（试运行），只报告当前状态和建议动作。只有 `-AuthorizeSync` 才创建缺失 Junction（目录联接）或刷新错误指向的 Junction（目录联接）。

Junction（目录联接）创建和刷新属于安装流程，不属于 Guard Profile（守卫画像）契约校验。不要在没有用户明确授权时执行。
