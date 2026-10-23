## MODIFIED Requirements

### Requirement: 发布输入选择提升插件

系统 MUST 使用 `bumpPlugins`（提升插件列表）声明本次发布需要提升版本的插件。

版本漂移比较基准 MUST 是远端发布通道 `origin/<channelBranch>`（远端通道分支）中同路径 manifest（插件清单）的版本。

#### Scenario: 只提升部分插件

- **WHEN** `bumpPlugins`（提升插件列表）只包含部分插件
- **THEN** preflight（发布前检查）MUST 只要求这些插件的 manifest（插件清单）版本等于发布版本
- **THEN** 未声明插件的 manifest（插件清单）版本 MUST 等于远端发布通道同路径 manifest（插件清单）版本

#### Scenario: 不提升插件

- **WHEN** `bumpPlugins`（提升插件列表）为空列表
- **THEN** preflight（发布前检查）MUST 不要求任何插件 manifest（插件清单）版本等于发布版本
- **THEN** 任何 manifest（插件清单）版本与远端发布通道同路径 manifest（插件清单）版本不一致 MUST 被拒绝

#### Scenario: CLI 重复声明提升插件

- **WHEN** 用户重复传入 `--bump-plugins`（提升插件版本参数）
- **THEN** preflight（发布前检查）、publish（发布）和 `ci-publish`（CI 发布）MUST NOT 静默丢弃前面的插件
- **AND** 系统 MUST 将重复参数合并为同一个 `bumpPlugins`（提升插件列表）或输出明确错误
