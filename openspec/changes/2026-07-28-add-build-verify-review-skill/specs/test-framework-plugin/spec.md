## ADDED Requirements

### Requirement: Build and Verify（构建与验证）提供引导式配置审查

系统 MUST 通过独立 `build-and-verify-review` Skill（构建与验证审查技能）扫描目标仓库、审查已有构建与验证配置，并在用户确认后生成和写入优化配置。

#### Scenario: 审查复用引导式初始化发现规则
- **WHEN** agent（代理）使用 `build-and-verify-review` Skill（构建与验证审查技能）
- **THEN** Skill（技能） MUST 直接读取 `build-and-verify-init`（构建与验证初始化）的生态识别规则
- **THEN** Skill（技能） MUST NOT 复制生态识别规则或新增扫描程序
- **THEN** 扫描 MUST NOT 运行候选 command（命令）

#### Scenario: 审查比较可发现入口与配置检查项
- **WHEN** 目标仓库存在 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 同时审查 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）
- **THEN** 完整性审查 MUST 比较可发现仓库入口与配置检查项
- **THEN** 完整性审查 MUST NOT 声称判断测试用例是否覆盖全部业务行为

#### Scenario: 审查执行固定合理性检查
- **WHEN** agent（代理）审查 configured checks（配置检查项）
- **THEN** agent（代理） MUST 检查命令来源、构建或验证分组、重复关系、`paths`（受影响路径）、`inputs`（缓存输入）、副作用风险和废弃字段
- **THEN** agent（代理） MUST 按缺失、错误、重复、缓存和风险分组展示结果
- **THEN** agent（代理） MUST NOT 修改仓库脚本、测试代码或运行参数

#### Scenario: 审查保守处理候选置信度
- **WHEN** 扫描产生 High（高）、Medium（中）和 Low（低）置信度候选
- **THEN** High（高）置信度遗漏 MUST 默认进入修改草案
- **THEN** Medium（中）置信度候选 MUST 等待用户明确选择
- **THEN** Low（低）置信度或有副作用候选 MUST 仅显示风险，除非用户明确选择，否则不得进入草案

### Requirement: Build and Verify（构建与验证）审查在优化前要求确认

`build-and-verify-review` Skill（构建与验证审查技能） MUST 让用户逐项选择建议并整体确认最终差异后，才能修改目标配置。

#### Scenario: 用户逐项选择建议
- **WHEN** 审查产生配置修改建议
- **THEN** 用户 MUST 能逐项接受或拒绝建议
- **THEN** 允许的建议 MUST 限于增加遗漏项、删除有证据的重复或失效项、修正分组、修正 `paths`（受影响路径）与 `inputs`（缓存输入），以及迁移废弃字段
- **THEN** 系统 MUST NOT 自动调整并行数、超时或完整验证预算

#### Scenario: 最终差异要求明确确认
- **WHEN** 用户完成逐项选择
- **THEN** agent（代理） MUST 展示合并后的最终配置差异
- **THEN** agent（代理） MUST 等待整体写入确认
- **THEN** 用户沉默、拒绝或未完成确认时，目标配置 MUST 保持不变

#### Scenario: 已确认优化复用初始化写入路径
- **WHEN** 用户明确确认最终配置差异
- **THEN** agent（代理） MUST 复用初始化入口的定向依赖检查和环境检查
- **THEN** agent（代理） MUST 通过现有 `init --config --overwrite`（初始化覆盖命令）备份并写入配置
- **THEN** agent（代理） MUST NOT 直接覆盖 `.build-and-verify/config.json`（配置文件）

### Requirement: Build and Verify（构建与验证）审查验证已确认优化

系统 MUST 在确认的配置成功写入并通过结构校验后运行一次完整验证，且失败不得触发自动回滚。

#### Scenario: 成功写入后运行完整验证
- **WHEN** 优化配置成功写入并通过结构校验
- **THEN** agent（代理） MUST 运行 `verify --full`（完整验证）
- **THEN** agent（代理） MUST 报告完整验证结果

#### Scenario: 配置失败生成新修正草案
- **WHEN** 完整验证因配置错误或命令不可用而失败
- **THEN** agent（代理） MUST 报告证据并生成新的修正草案
- **THEN** 新草案 MUST 再次经过逐项选择和整体确认
- **THEN** agent（代理） MUST NOT 自动回滚配置

#### Scenario: 仓库失败保持可见
- **WHEN** 新增或修正的检查项发现真实仓库失败
- **THEN** agent（代理） MUST 保留已确认配置并报告失败
- **THEN** agent（代理） MUST NOT 将真实仓库失败误报为配置优化失败
- **THEN** 只有用户明确授权时才能从备份恢复
