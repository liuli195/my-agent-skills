## Why

Agent Guard Plugin（代理守卫插件）已经转向 Plugin-first（插件优先），但当前安装契约仍混杂了旧的 user-level Skill（用户级技能）同步、Claude Junction（Claude 目录联接）和非标准 marketplace（市场）文件。需要把发布与订阅面收敛到 Codex 和 Claude 可使用的插件包，并支持 personal marketplace（个人市场）与 repo marketplace（仓库市场）。

## What Changes

- **BREAKING**: 移除 user-level Skill installation（用户级技能安装）兼容路径，不再保留 `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py` 作为 Agent Guard 发布契约。
- **BREAKING**: 移除 Claude Junction（Claude 目录联接）作为 Claude 兼容方式；Claude 兼容改由插件包内 `.claude-plugin/plugin.json` 和同一插件内容验证。
- 将 Agent Guard Plugin 的安装/验证契约改为 marketplace subscription（市场订阅）优先，覆盖 Codex 与 Claude 两个目标。
- 正式订阅源指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本。
- 本仓库维护 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json` 两套 marketplace catalog（市场目录），共享同一个 `plugins/agent-guard` 插件包。
- 支持 personal marketplace（个人市场）和 repo marketplace（仓库市场）两类入口；默认不写用户目录，所有写入仍需要明确授权。
- 对 marketplace entry（市场条目）使用当前插件约定：`source` 对象、`policy.installation`、`policy.authentication` 和 `category`。
- 更新相关测试和 OpenSpec specs，使验证不再引用旧用户级 Skill 安装兼容层。

## Capabilities

### New Capabilities

### Modified Capabilities
- `agent-guard-plugin-runtime`: 插件安装/验证要求改为 marketplace subscription，并支持 personal/repo marketplace。
- `agent-guard-skill-entrypoints`: 删除 user-level Skill installation verification 作为发布契约，场景化 Skill 入口只由插件包发布。

## Impact

- `plugins/agent-guard/.codex-plugin/plugin.json`
- `plugins/agent-guard/.claude-plugin/plugin.json`
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`
- `plugins/agent-guard/skills/agent-guard*/SKILL.md` 和相关 reference（参考文档）
- `scripts/install/` 下旧用户级 Skill 安装脚本
- `tests/test_agent_guard_plugin_installer.py`
- `tests/test_agent_guard_plugin_package.py`
- `tests/test_agent_guard_plugin_runtime_e2e.py`
- `tests/test_user_skill_install.py`
- `openspec/specs/agent-guard-plugin-runtime/spec.md`
- `openspec/specs/agent-guard-skill-entrypoints/spec.md`
