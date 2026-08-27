## MODIFIED Requirements

### Requirement: 固定生命周期钩子集合
系统 MUST 在第一版 plugin-runtime baseline（插件运行时基线）中只注册 `SessionStart` 和 `PreToolUse` lifecycle hooks（生命周期钩子）。

#### Scenario: 校验钩子配置
- **WHEN** hook configuration（钩子配置）被校验
- **THEN** 它包含 `SessionStart` 和 `PreToolUse`，并排除 Git hooks（Git 钩子）、`UserPromptSubmit`、`PostToolUse`、subagent hooks（子代理钩子）和 Claude `PermissionRequest`

#### Scenario: Hook 保持画像无关
- **WHEN** lifecycle hook command（生命周期钩子命令）运行
- **THEN** 它不接收 profile（画像）参数，也不在 hook（钩子）层选择 Guard Profile（守卫画像）

#### Scenario: 平台 manifest 避免重复加载
- **WHEN** package verification（包验证）检查 Agent Guard manifest（清单）和标准 `hooks/hooks.json`
- **THEN** Codex manifest MUST 声明 `hooks: ./hooks/hooks.json`
- **THEN** Claude manifest MUST NOT 声明标准 `hooks/hooks.json`
- **THEN** 标准 `hooks/hooks.json` MUST 继续位于插件包内并只包含 `SessionStart` 和 `PreToolUse`
