## ADDED Requirements

### Requirement: 用户级 Skill 安装兼容层移除
系统 MUST 不再把 user-level Skill installation（用户级技能安装）、Claude Junction（Claude 目录联接）或旧 install scripts（安装脚本）作为 Agent Guard Plugin（代理守卫插件）的发布、订阅或验证契约。

#### Scenario: 扫描旧安装脚本
- **WHEN** 检查仓库发布入口
- **THEN** `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py` 不作为 Agent Guard 安装入口存在

#### Scenario: 验证发布契约
- **WHEN** Agent Guard Plugin（代理守卫插件）发布契约被验证
- **THEN** 验证只依赖 plugin package（插件包）、marketplace entry（市场条目）、manifest（清单）、hooks（钩子）、runtime（运行时）和 Skill（技能）入口，不依赖 `.agents/skills/agent-guard` 或 `.claude/skills/agent-guard` Junction（目录联接）

## MODIFIED Requirements

### Requirement: 共享核心资源
系统 MUST 把共享 scripts（脚本）、assets（资源）和 common references（通用参考资料）保留在核心 `agent-guard` Skill（技能）区域，同时让场景化入口引用这些共享资源而不是复制它们。

#### Scenario: 场景入口使用共享脚本
- **WHEN** 场景化入口需要共享 script（脚本）或 template（模板）
- **THEN** 它通过相对路径引用共享核心资源，而不是复制资源目录

#### Scenario: 插件包验证
- **WHEN** Agent Guard Plugin package verification（插件包验证）运行
- **THEN** 它检查核心共享资源、四个场景化入口、产品 manifest（清单）和 marketplace subscription（市场订阅）契约，而不是检查 user-level Skill installation（用户级技能安装）
