# My Spec

## Purpose

本 capability（能力）定义 MySpec（自有规格）在 Pi、Claude 和 Codex 中的可发现入口、范围隔离、确认门禁与确定性操作行为。

## Requirements

### Requirement: 规格技能使用宿主原生入口

系统 MUST 让 Pi、Claude 和 Codex 通过各自原生 Skill（技能）机制调用四个 my-spec 技能，不得注册把技能名称重新包装成普通用户消息的代理命令。

#### Scenario: Pi 调用规格技能

- **WHEN** 用户在 Pi（编码代理）中显式调用 my-spec 技能
- **THEN** 系统 MUST 使用 `/skill:my-spec`、`/skill:my-spec-add`、`/skill:my-spec-review` 或 `/skill:my-spec-audit`
- **THEN** Pi MUST 通过原生 Skill（技能）展开处理参数和 `SKILL.md`

#### Scenario: Claude 调用规格技能

- **WHEN** 用户在 Claude（代码代理）插件中显式调用 my-spec 技能
- **THEN** 系统 MUST 使用 `/my-spec:my-spec`、`/my-spec:my-spec-add`、`/my-spec:my-spec-review` 或 `/my-spec:my-spec-audit`

#### Scenario: Codex 调用规格技能

- **WHEN** 用户在 Codex（代码代理）中显式调用 my-spec 技能
- **THEN** 系统 MUST 使用 `$my-spec`、`$my-spec-add`、`$my-spec-review` 或 `$my-spec-audit`

#### Scenario: Pi 包不代理原生技能

- **WHEN** Pi 加载 my-spec 包
- **THEN** 包 MUST 只通过 `pi.skills` 公开技能资源
- **THEN** 包 MUST NOT 注册 `/my-spec`、`/my-spec-add`、`/my-spec-review` 或 `/my-spec-audit` 扩展命令
- **THEN** 包 MUST NOT 发送 `Use the <skill> skill` 形式的普通用户消息来模拟技能调用
### Requirement: 规格插件在三类宿主中可发现

系统 MUST 让 `my-spec` 同时可被 Pi、Claude 和 Codex 发现，并公开四个规格 Skill（技能）。

#### Scenario: 宿主加载本地插件市场

- **WHEN** Pi、Claude 或 Codex 加载本地插件市场
- **THEN** 市场中出现 `my-spec`，且四个规格 Skill（技能）均可发现
### Requirement: 规格入口保持范围隔离

系统 MUST 让 add 入口处理 Agent（代理）为当前请求选取的会话、文档、代码或其他相关证据且不要求指定文档，让 review 入口只读取 `myspec/specs/`，并让 audit 入口只读取 Git（版本管理）可见文件且排除主规格、`.local/spec-work/` 和二进制文件。Audit（审计）在主规格库不存在时 MUST 将其视为空库完成初始化；review（审查）只能依据规格库内部的明确证据判断重复、冲突或过期。

#### Scenario: 用户选择规格入口

- **WHEN** 用户选择 add、review 或 audit 入口
- **THEN** 系统只扫描该入口允许的材料范围

#### Scenario: 用户未为 add 指定文档

- **WHEN** 用户调用 add 入口但没有指定文档
- **THEN** Agent（代理）可以从当前请求的相关证据中提取可验证行为，且不得自动扩展为全仓库审计

#### Scenario: Audit 初始化空规格库

- **WHEN** 用户调用 audit 入口且 `myspec/specs/` 不存在
- **THEN** 系统 MUST 将主规格基准视为空库并生成初始 Delta（增量规格）
- **THEN** 系统 MUST NOT 要求用户改用独立初始化命令

#### Scenario: Review 只依据内部证据判断问题

- **WHEN** 用户调用 review 入口
- **THEN** 标题和正文完全相同的确定重复 MAY 自动合并
- **THEN** 标题不同但语义等价、标题相同但正文不同或 Scenario（场景）部分重叠 MUST 逐项决定
- **THEN** 只有规格内部明确声明废止、停止支持、替代或旧版本失效时，系统 MAY 生成过期删除候选
- **THEN** 无语义影响的格式问题 MAY 自动修复，可能改变语义的格式问题 MUST 逐项决定
### Requirement: 规格变更须经逐项决策和最终确认

系统 MUST 在首次展示前完整保存全部冲突、删除和低可信候选的正文、证据、原因及推荐答案，并从保存清单逐项读取和记录决定；在最终确认前不得修改主规格，并在应用后校验失败时恢复原规格。系统 MUST 支持接受、忽略、修改后接受和暂缓，并确保修改后的内容精确进入预览、暂缓内容不进入预览、忽略决定仅属于当前运行。

#### Scenario: 规格流程产生待决候选

- **WHEN** add、review 或 audit 产生冲突、删除或低可信候选
- **THEN** 系统一次性保存完整清单，一次展示其中一项，并在全部待决项处理后展示完整差异、等待最终确认再应用
- **THEN** 只有数量、缺少证据、重复标识或不完整候选正文的清单 MUST 被拒绝

#### Scenario: 用户决定第一项后继续

- **WHEN** 系统已保存完整待决清单且用户决定当前项
- **THEN** 系统从同一清单返回下一项并保持总数和顺序稳定，不得重新扫描获取下一项
- **THEN** 重复决定、越序决定和不受支持的决定值 MUST 被拒绝

#### Scenario: 用户修改、暂缓或忽略候选

- **WHEN** 用户选择修改后接受
- **THEN** 系统 MUST 将修改后的决定绑定到当前候选，并让预览只反映获准内容
- **WHEN** 用户选择暂缓
- **THEN** 该候选 MUST NOT 进入预览
- **WHEN** 用户选择忽略
- **THEN** 该决定 MUST NOT 成为跨运行的长期事实源

#### Scenario: 中断后继续逐项决定

- **WHEN** my-spec 运行在逐项决定期间被中断后继续
- **THEN** 系统 MUST 返回原清单中的同一当前项、稳定总数和既有决定
- **THEN** 系统 MUST NOT 重新扫描以重建剩余候选
### Requirement: 规格运行文件集中在本地目录

系统 MUST 将 my-spec 的共享锁、当前命令状态、输入、主规格指纹、决定、Delta（增量规格）、预览和恢复材料保存在 `.local/spec-work/`，不得在仓库根目录创建 `.spec-work/`。同一仓库 MUST 同时只允许一个 my-spec 运行；已有锁不得只因超时而自动删除。继续或应用前 MUST 校验主规格和输入指纹，成功应用后 MUST 清理本次运行状态。

#### Scenario: 规格入口创建运行文件

- **WHEN** 任一 my-spec 入口开始处理规格任务
- **THEN** 所有临时运行文件均位于 `.local/spec-work/`

#### Scenario: 同一仓库已有规格运行

- **WHEN** 新的 my-spec 入口发现共享锁已存在
- **THEN** 系统 MUST 停止并报告已有运行
- **THEN** 系统 MUST NOT 仅根据锁的时间自动删除它

#### Scenario: 基线或证据在继续前变化

- **WHEN** 当前主规格指纹或本次输入指纹与保存状态不一致
- **THEN** 系统 MUST 拒绝继续使用旧决定、Delta 或预览
- **THEN** 系统 MUST 要求重新分析

#### Scenario: 原子应用完成或失败

- **WHEN** 用户最终确认且预览校验通过
- **THEN** 系统 MUST 只原子替换 `myspec/specs/`
- **THEN** 最终校验成功后系统 MUST 清理本次锁、备份和工作状态
- **WHEN** 替换后最终校验失败
- **THEN** 系统 MUST 恢复原主规格且不得触碰规格目录之外的用户内容
### Requirement: MySpec 操作错误可见且重复执行稳定

系统 MUST 通过 PATH（可执行文件搜索路径）中的裸 `myspec` CLI（命令行程序）执行状态、校验、预览、差异和应用操作，不得定位或解析包内脚本路径；系统 MUST 对无效主规格或 Delta（增量规格）返回非零结果和可识别错误，并确保相同输入的重复预览或应用不产生额外变化。主规格 MUST 包含 Purpose（目的）、Requirements（需求）、全局唯一的 Requirement 标题、`MUST` 或 `SHALL`，以及至少一个包含非空 `WHEN` 和 `THEN` 的 Scenario（场景）。Delta MUST 只支持 RENAMED、REMOVED、MODIFIED 和 ADDED，并按该顺序应用。

#### Scenario: Skill 执行确定性操作

- **WHEN** 任一 MySpec Skill（技能）执行状态、校验、预览、完整差异或应用操作
- **THEN** Skill MUST 直接调用 `myspec` 及对应既有业务子命令
- **THEN** Skill MUST NOT 包含 `spec_ops.py` 路径、绝对安装路径或要求 Agent（代理）选择脚本位置

#### Scenario: 用户提交无效主规格

- **WHEN** 主规格缺少必要结构、全局标题不唯一、Requirement 缺少 `MUST`/`SHALL` 或 Scenario 缺少非空 `WHEN`/`THEN`
- **THEN** 系统 MUST 返回非零结果和可识别错误

#### Scenario: 用户提交无效 Delta

- **WHEN** Delta 包含未知操作、重复处理同一 Requirement、引用不存在的标题、添加已存在标题或提供不完整的 MODIFIED Requirement
- **THEN** 系统 MUST 返回非零结果和可识别错误
- **THEN** 系统 MUST NOT 修改主规格

#### Scenario: 用户重复执行相同变更

- **WHEN** 用户对相同基线重复预览或应用同一 Delta（增量规格）
- **THEN** 系统保持结果不变
