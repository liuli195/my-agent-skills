# Agent Guard User Skill Install（用户级技能安装）

本文件说明源码仓库到用户级 Skill（技能）的同步，不属于 Agent Guard（代理守卫）5 个运行场景。

当前以 Codex（Codex 代理）为主：

- 用户级 Skill（技能）源码来自插件包内的 `plugins/agent-guard/skills/`，根目录不再保留旧 `skills/agent-guard*` 副本。
- `agent-guard` 是共享核心和薄路由入口。
- `agent-guard-install`、`agent-guard-init`、`agent-guard-update`、`agent-guard-run` 和 `agent-guard-hooks` 是按场景触发的入口。
- 当前仓库初始化不安装用户级 Skill（技能），不创建 Claude Junction（Claude 目录联接），也不初始化目标项目守卫。

安装验证：

```powershell
python scripts\install\verify_install.py
```

用户级 Skill（技能）安装：

```powershell
scripts\install\install_user_skill.ps1
```

默认 dry-run（试运行），只有 `-AuthorizeInstall` 才同步文件。同步范围包括：

```text
.agents\skills\agent-guard
.agents\skills\agent-guard-install
.agents\skills\agent-guard-init
.agents\skills\agent-guard-update
.agents\skills\agent-guard-run
.agents\skills\agent-guard-hooks
```

共享 `scripts` 和 `assets` 只保留在 `agent-guard`。5 个场景入口可以包含自己的 `references`，但不复制共享脚本和模板。

Claude（Claude 代理）兼容通过 Junction（目录联接）复用同一份用户级 Skill（技能）：

```text
C:\Users\liuli\.claude\skills\agent-guard
  -> C:\Users\liuli\.agents\skills\agent-guard
```

Junction（目录联接）同步使用：

```powershell
scripts\install\sync_claude_junction.ps1
```

默认 dry-run（试运行），只有 `-AuthorizeSync` 才创建缺失 Junction（目录联接）或刷新错误指向的 Junction（目录联接）。
