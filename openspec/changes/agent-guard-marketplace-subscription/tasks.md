## 1. Contract And Test Baseline

- [ ] 1.1 更新 `agent-guard-plugin-runtime` 和 `agent-guard-skill-entrypoints` specs，确认 marketplace subscription（市场订阅）是唯一发布入口。
- [x] 1.2 调整 installer tests（安装器测试），覆盖 `target` 与 `scope` 分离、personal marketplace（个人市场）、repo marketplace（仓库市场）和 GitHub `marketplace` 发布分支。
- [x] 1.3 调整 package tests（插件包测试），校验 `.codex-plugin`、`.claude-plugin`、hooks、runtime 和 Skill 入口，不再校验 user-level Skill installation（用户级技能安装）。
- [x] 1.4 删除或替换旧 `test_user_skill_install.py`，确保测试不再引用 Claude Junction（Claude 目录联接）或 `.agents/skills/agent-guard` 安装兼容层。

## 2. Marketplace Installer

- [x] 2.1 重构 `install_agent_guard_plugin.py`，把 `--target codex|claude|all` 和 `--scope personal|repo|all` 分开处理。
- [x] 2.2 实现 personal marketplace（个人市场）和 repo marketplace（仓库市场）的 dry-run 输出、授权写入和验证。
- [x] 2.3 生成并校验 Codex `.agents/plugins/marketplace.json` 与 Claude `.claude-plugin/marketplace.json`，两者共享 `plugins/agent-guard` 插件包。
- [x] 2.4 生成并校验 Codex entry（条目）包含 `source`、`policy.installation`、`policy.authentication` 和 `category`。
- [x] 2.5 保持安全声明：不初始化 Guard Profile（守卫画像）、不安装 project hooks（项目钩子）、不修改 git config（Git 配置）。

## 3. Remove Legacy Install Path

- [x] 3.1 删除 `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py`。
- [x] 3.2 更新 `scripts/install/README.md` 或删除旧 README，避免继续指向 user-level Skill installation（用户级技能安装）。
- [x] 3.3 更新 Agent Guard Skill references（参考文档），把 Plugin update（插件更新）说明改为 marketplace subscription（市场订阅）流程。

## 4. Verification

- [ ] 4.1 运行 `openspec validate --all --strict --json`。
- [ ] 4.2 运行相关 pytest（测试）：plugin package、plugin installer、plugin runtime e2e 和被修改的 extraction tests。
- [ ] 4.3 定向扫描确认没有活跃文档或测试继续引用旧 user-level Skill installation（用户级技能安装）兼容层。
