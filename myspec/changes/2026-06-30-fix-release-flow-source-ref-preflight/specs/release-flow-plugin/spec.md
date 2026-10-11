## MODIFIED Requirements

### Requirement: 发布前检查

系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、发布输入、manifest（插件清单）、source ref（源引用）、发布投影和远端发布冲突。

#### Scenario: 检查配置文件

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 `.release-flow/config.yaml`（配置文件）存在且合法
- **THEN** 系统 MUST 验证 `.release-flow/projection.yaml`（投影配置）存在且合法

#### Scenario: 检查发布输入

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 `tag`（标签）和 `version`（版本）一致
- **THEN** 系统 MUST 验证 `bumpPlugins`（提升插件列表）存在且只包含已注册插件

#### Scenario: 检查版本一致性

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 只要求 `bumpPlugins`（提升插件列表）声明的插件 manifest（插件清单）版本等于发布版本
- **THEN** 系统 MUST 拒绝未声明插件的 manifest（插件清单）版本不同于远端发布通道同路径版本

#### Scenario: 检查 source ref 已包含版本提升

- **WHEN** 执行 preflight（发布前检查）
- **AND** `bumpPlugins`（提升插件列表）声明了需要提升版本的插件
- **THEN** 系统 MUST 验证远端 `sourceRef`（源引用）中这些插件 manifest（插件清单）版本等于发布版本
- **THEN** 任一版本提升尚未进入远端 `sourceRef`（源引用）时 MUST 拒绝继续
- **THEN** 错误 MUST 指出需要先通过 PR（拉取请求）把版本提升合入 `sourceRef`（源引用）

#### Scenario: 检查发布投影

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 projection（投影）可以由单一 Plugin registry（插件注册表）生成
- **THEN** 系统 MUST 拒绝无法生成的发布投影
- **THEN** 系统 MUST NOT 要求用户在源码分支运行正式 marketplace（市场）projection（投影）

#### Scenario: 检查远端发布冲突

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 检查远端 tag（标签）是否已存在
- **THEN** 系统 MUST 检查 GitHub Release（GitHub 发布）是否已存在
- **THEN** 任一已存在时 MUST 拒绝继续

#### Scenario: 不检查 GitHub Rulesets

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST NOT 读取 GitHub Rulesets（GitHub 规则集）
- **THEN** 系统 MUST NOT 声称已验证 GitHub Rulesets（GitHub 规则集）
