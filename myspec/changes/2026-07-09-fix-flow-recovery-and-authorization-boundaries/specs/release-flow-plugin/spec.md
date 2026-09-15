## MODIFIED Requirements

### Requirement: 发布前检查
系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、发布输入、manifest（插件清单）、source ref（源引用）、发布投影和远端发布冲突。

#### Scenario: 多个 preflight 问题输出汇总路径
- **WHEN** preflight（发布前检查）同时发现多个错误
- **AND** every emitted error（错误） is release（发布）冲突、manifest（清单）版本不匹配、source ref（源引用）未合入版本提升 or plugin（插件）需要一并提升版本
- **THEN** preflight（发布前检查） MUST keep printing each underlying error（底层错误）
- **THEN** preflight（发布前检查） MUST print exactly one summary next action（汇总下一步动作） for the multi-error set
- **THEN** the summary MUST describe the current state and handling path（处理路径）, including that release（发布） conflicts require the user and agent（代理） to choose the release version（发布版本） before rerunning preflight（发布前检查）
- **THEN** the summary MUST describe manifest（清单）、source ref（源引用） and plugin（插件） version issues as requiring the PR（拉取请求） path
- **THEN** the summary MUST NOT infer or suggest a latest version（最新版本） or next version（下一版本）

#### Scenario: 未跟踪 preflight 问题保留逐条恢复提示
- **WHEN** preflight（发布前检查）同时发现多个错误
- **AND** at least one error（错误） is not release（发布）冲突、manifest（清单）版本不匹配、source ref（源引用）未合入版本提升 or plugin（插件）需要一并提升版本
- **THEN** preflight（发布前检查） MUST keep per-error nextAction（逐条下一步动作） output for errors（错误） that already have one

### Requirement: 项目启用阶段
系统 MUST 提供 project setup（项目启用）阶段，用于生成目标项目配置，并输出 GitHub Actions（GitHub 自动化任务）权限配置方案。首版 MUST NOT 在没有额外实现仓库上下文和认证回读前修改 GitHub 仓库设置。

#### Scenario: Remote governance changes require current confirmation
- **WHEN** Release Flow（发布流程） guidance mentions GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量） or repository settings（仓库设置）
- **THEN** Skill（技能） guidance MUST prohibit modifying those remote settings without explicit confirmation in the current conversation
- **THEN** without confirmation, the Skill（技能） MUST only output remote tasks（远端待办）
