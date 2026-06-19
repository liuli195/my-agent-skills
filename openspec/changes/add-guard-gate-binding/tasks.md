## 1. 全局命令守卫点契约

- [x] 1.1 为有效的通用 `global-command-guards.yaml` 配置添加校验器测试。
- [x] 1.2 为缺少命令模式、缺少证据路径、不支持的 JSON 谓词、缺少必需捕获值、非法 `value_from` 添加校验器测试。
- [x] 1.3 扩展 Guard Profile（守卫画像）校验，允许在没有 Session Focus（会话焦点）配置的情况下声明全局命令守卫点。
- [x] 1.4 更新 Guard Profile 模板，新增可选的 `global-command-guards.yaml`。
- [x] 1.5 校验同一个 `global-command-guards.yaml` 内的 guard id 必须唯一；不同 profile 或不同 source scope 中允许同名 guard id。

## 2. 共享 Agent Guard（代理守卫）抽象

- [ ] 2.1 从现有 PreToolUse（工具使用前）命令提取逻辑中抽象可复用的 command context（命令上下文）能力。
- [ ] 2.2 从 Session Focus permission（会话焦点权限）规则匹配中抽象可复用的命令匹配能力。
- [ ] 2.3 从 `json_artifact` 检查中抽象 JSON 字段读取和 predicate（谓词）评估能力。
- [ ] 2.4 在 `json_artifact` 检查和全局命令守卫点之间共享 predicate 校验常量。
- [ ] 2.5 抽象后保持现有 Session Focus permission 行为不变。
- [ ] 2.6 新增 Global Command Guard Collector（全局命令守卫收集器），收集项目级和用户级所有 `global-command-guards.yaml`。
- [ ] 2.7 为每条规则生成 effective guard id（有效守卫 ID）：`<source_scope>:<profile_id>:<guard_id>`。

## 3. 命令解析与上下文

- [ ] 3.1 为通用命令模式匹配和 named capture（命名捕获）提取添加测试。
- [ ] 3.2 添加 Comet 风格验证边界命令的配置 fixture（夹具），证明能力不是硬编码 Comet。
- [ ] 3.3 添加 Windows PowerShell 包装 Git Bash 命令的测试。
- [ ] 3.4 实现命令文本标准化、命令模式匹配和命名捕获提取。
- [ ] 3.5 提供上下文值来源，例如捕获变量和当前 `git_head`。
- [ ] 3.6 提供内置上下文值：`source_scope`、`profile_id`、`guard_id`、`effective_guard_id`、`runtime_scope`。

## 4. 运行时拦截

- [ ] 4.1 添加 PreToolUse 测试，证明没有 Session Focus 时仍会执行全局命令守卫点。
- [ ] 4.2 添加缺少 evidence（证据）、`head_ref` 过期、evidence 通过、缺少必需捕获值的测试。
- [ ] 4.3 在 `route_pre_tool_use` 中先评估有效全局命令守卫集，再进入 Session Focus permission。
- [ ] 4.4 复用共享 JSON 检查能力校验配置的 evidence。
- [ ] 4.5 返回机器可读的拒绝输出，包含 `reason`、`next`、`suggestion`、匹配的有效守卫 ID 列表、失败守卫列表、捕获值和审计路径。
- [ ] 4.6 审计记录必须区分全局命令守卫点和会话焦点权限检查。
- [ ] 4.7 添加作用域测试：用户级安装或用户级静态规则在项目命令中默认使用 `.local/guard`；显式用户作用域使用 `~/.agents/guard`；Comet change review 不从用户级运行目录读取证据。
- [ ] 4.8 添加多来源测试：多个项目级 profile、用户级 + 项目级 profile 同时贡献规则时，所有匹配规则必须全部通过。
- [ ] 4.9 添加同名规则测试：不同 source scope 或 profile 下同名 guard id 不冲突，evidence 路径和审计使用有效守卫 ID。

## 5. 回归与文档

- [ ] 5.1 验证没有全局命令守卫点匹配时，现有 Session Focus PreToolUse 行为不变。
- [ ] 5.2 验证全局命令守卫点允许后，后续 Session Focus permission 仍可拒绝命令。
- [ ] 5.3 更新 Agent Guard 运行文档，解释“会话焦点守卫”和“全局命令守卫点”的差异。
- [ ] 5.4 更新目录和运行时文件约定文档，说明插件安装范围、静态画像范围、运行态数据范围的差异。
- [ ] 5.5 运行聚焦的 Agent Guard runtime 和 validator 测试。
- [ ] 5.6 运行仓库完整测试套件。
