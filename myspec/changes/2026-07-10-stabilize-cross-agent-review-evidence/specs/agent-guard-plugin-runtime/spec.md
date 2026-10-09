## MODIFIED Requirements

### Requirement: Global Command Guard evidence uses dual path model
系统 MUST 为 Global Command Guard（全局命令守卫点）区分 guard-defined evidence（守卫定义证据）和 external artifact（外部产物）。当通过结论由主 agent（主代理）根据上游报告作出时，Agent Guard（代理守卫） MUST 定义默认 evidence（证据）目录，并且只在主代理显式调用通用记录入口后机械写入；当被守卫流程本身已经生成稳定可检查产物时，Agent Guard（代理守卫） MUST 只登记并校验原始路径，不复制、不搬运、不接管目录。

#### Scenario: guard-defined evidence 使用默认目录
- **WHEN** Guard Profile（守卫画像）声明的 artifact（产物）属于 guard-defined evidence（守卫定义证据）
- **THEN** Runtime（运行时） MUST 从 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json` 读取证据

#### Scenario: guard-defined evidence 由主代理显式记录
- **WHEN** guard-defined evidence（守卫定义证据）需要写入 pass marker（通过标记）
- **THEN** 主 agent（主代理） MUST 在 Guard（守卫）检查前显式调用 `record-evidence`（记录证据）
- **AND** Runtime（运行时）只能机械校验并写入，不得自主生成业务结论

#### Scenario: guard-defined evidence 使用标准字段
- **WHEN** guard-defined evidence（守卫定义证据）写入 pass marker（通过标记）
- **THEN** marker（标记） MUST 使用 `guard-evidence/v1`（守卫证据第一版）字段契约

#### Scenario: external artifact 保持只读
- **WHEN** `artifacts.yaml`（产物注册文件）中的目标 artifact（产物）不属于 guard-defined evidence（守卫定义证据）
- **THEN** Agent Guard（代理守卫） MUST 只读取和校验该外部产物
- **AND** `record-evidence`（记录证据） MUST 拒绝覆盖该产物

#### Scenario: cross-agent-review pass marker 使用 guard-defined evidence
- **WHEN** Global Command Guard（全局命令守卫点）校验 Cross Agent Review（跨代理审查）的 pass marker（通过标记）
- **THEN** 该 artifact（产物） MUST 注册为 `type: json`（数据类型）且 `owner: agent-guard`（代理守卫拥有）的 guard-defined evidence（守卫定义证据）
- **AND** 注册路径 MUST 使用 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** `{artifact_id}` MUST 为该 Guard Profile（守卫画像）声明的 `cross_agent_review_pass`
- **AND** `{subject_id}` MUST 来自命令捕获值，Comet change（双星变更）场景下等于 `change`

## ADDED Requirements

### Requirement: 通用 record-evidence 入口
Agent Guard Runtime（代理守卫运行时） MUST 提供通用 `record-evidence`（记录证据）入口，供主代理在完成语义判断后显式记录任意 Guard Profile（守卫画像）声明的 guard-defined JSON evidence（守卫定义数据证据）。该入口 MUST 不硬编码业务 workflow（工作流）、审查技能、profile id（画像编号）、artifact id（产物编号）或证据业务字段。

#### Scenario: 显式选择画像来源
- **WHEN** 主代理调用 `record-evidence`（记录证据）
- **THEN** 调用 MUST 明确提供 project（项目）或 user（用户）profile source scope（画像来源范围）、`profile_id`（画像编号）和 `artifact_id`（产物编号）
- **AND** Runtime（运行时） MUST 只从所选来源的 `.agents/guards/<profile_id>/artifacts.yaml`（产物注册文件）解析产物
- **AND** Runtime（运行时） MUST NOT 在另一个来源范围中猜测或回退查找同名画像

#### Scenario: 只写守卫定义数据证据
- **WHEN** 目标 artifact（产物）存在于 `artifacts.yaml`（产物注册文件）
- **THEN** Runtime（运行时） MUST 要求该产物声明 `type: json`（数据类型）和 `owner: agent-guard`（代理守卫拥有）
- **AND** 任一条件不满足时，Runtime（运行时） MUST 拒绝写入并报告目标不是 guard-defined evidence（守卫定义证据）

#### Scenario: 从画像安全解析路径
- **WHEN** 目标产物通过所有权检查
- **THEN** Runtime（运行时） MUST 只使用该产物的 `path`（路径）模板
- **AND** Runtime（运行时） MUST 注入 `profile_id`、`artifact_id`、`subject_id`、当前 `git_head`（提交头）和当前 12 位 `git_head_short`（短提交头）
- **AND** Runtime（运行时） MUST 拒绝缺失模板值、绝对路径、Windows drive path（Windows 驱动器路径）和项目目录逃逸

#### Scenario: 当前仓库状态决定提交字段
- **WHEN** Runtime（运行时）准备记录证据
- **THEN** 它 MUST 从 `--project` 指向的 Git（版本控制）仓库读取当前完整 `HEAD`（提交头）
- **AND** 当前 worktree（工作区） MUST 干净
- **AND** 调用方 MUST NOT 覆盖 `head_ref` 或 `head_ref_short`

#### Scenario: 标准字段由 Runtime 注入
- **WHEN** 主代理提供 `producer`（生产方）、`subject_type`（对象类型）、`subject_id`（对象编号）和 JSON object（数据对象）业务字段
- **THEN** Runtime（运行时） MUST 注入 `schema_version: guard-evidence/v1`、`status: pass`、`producer`、`profile_id`、`artifact_id`、`subject_type`、`subject_id`、`head_ref`、`head_ref_short` 和 `created_at`
- **AND** Runtime（运行时） MUST 拒绝业务字段对象包含任一保留标准字段

#### Scenario: 原子写入证据
- **WHEN** 画像、产物、路径、仓库和业务字段均有效
- **THEN** Runtime（运行时） MUST 在目标目录创建同目录临时文件并通过 atomic replace（原子替换）写入 `pass.json`
- **AND** 命令输出 MUST 包含 `status: evidence_recorded`、当前完整提交头、12 位短提交头和可复制证据路径

#### Scenario: 写入失败不留下半文件
- **WHEN** JSON（数据）读取、目录创建、临时文件写入或原子替换失败
- **THEN** Runtime（运行时） MUST 返回失败状态
- **AND** Runtime（运行时） MUST NOT 把部分 JSON（数据）暴露为有效目标证据
